# Release 17A: Entitlement Enforcement Design

**Status:** Design Complete
**Date:** 2026-06-20
**Priority:** High (critical path to multi-business-owner readiness)
**Scope:** Technical design for enforcing tier-based entitlements across the platform

---

## 1. Existing Entitlement/Tier Code Inventory

### Already Implemented (src/backend/common/billing.py)

| Component | Location | Status |
|-----------|----------|--------|
| `TIER_LIMITS` dict | billing.py lines 28–67 | ✅ Defined (starter/professional/premium/enterprise) |
| `TenantEntitlement` class | billing.py lines 91–160 | ✅ Defined with `is_access_allowed`, `is_read_only`, `is_blocked` |
| `get_tenant_entitlement(company_id)` | billing.py lines 168–195 | ✅ With 5-min cache, fail-closed |
| `invalidate_entitlement_cache()` | billing.py lines 198–202 | ✅ For webhook-driven refresh |
| `ALLOWED_STATUSES` | billing.py | `('active', 'trialing')` |
| `BLOCKED_STATUSES` | billing.py | `('canceled', 'paused', 'disabled')` |
| Grace period logic | TenantEntitlement properties | 7-day grace → 7-day read-only → blocked |
| Admin override | `admin_override_until` field | Allows access regardless of status |

### Tenant Metadata (DynamoDB)

| Field | Current Value (tog_and_dogs) |
|-------|------------------------------|
| `subscription_tier` | `professional` |
| `subscription_status` | `active` |
| `limits` | Professional tier defaults |
| `feature_flags` | Not explicitly set (derives from tier) |
| `admin_override_until` | null |

### Handlers That Currently BYPASS Entitlement

| Handler | Actions That Should Be Gated |
|---------|------------------------------|
| `admin_handler.py` | Staff creation, client creation, export, payment-session |
| `intake_handler.py` | Booking request creation (monthly limit) |
| `assignment_handler.py` | Staff assignment (requires active subscription) |
| `review_handler.py` | Request approval → triggers job/calendar (requires active) |
| `pet_handler.py` | Pet creation (tied to client limit indirectly) |
| `google_auth_handler.py` | Calendar connection (feature flag) |
| `cancellation_handler.py` | Requires active subscription |

### Handlers That Should NOT Be Gated

| Handler | Reason |
|---------|--------|
| `stripe_webhook_handler.py` | Processes billing events (must always work) |
| `postmark_webhook_handler.py` | Processes delivery events (system-level) |
| `notification_feedback_handler.py` | SES bounce handling (system-level) |
| `job_handler.py` | Internal invocation from Step Functions |
| `device_handler.py` | Device registration (low-risk, needed for push) |

---

## 2. Entitlement Model

### Subscription Statuses and Access Levels

| Status | Access Level | Enforcement |
|--------|-------------|-------------|
| `active` | Full access | All features per tier |
| `trialing` | Full access | All features per tier (trial period) |
| `past_due` (≤7 days) | Full access + warning | Grace period — warn but don't block |
| `past_due` (7–14 days) | Read-only | Can view but not create/modify |
| `past_due` (>14 days) | Blocked | Login denied |
| `canceled` | Blocked | Login denied, redirect to resubscribe |
| `paused` | Blocked | Login denied, redirect to resume |
| `disabled` | Blocked | Admin-disabled (break-glass) |

### Feature Flags (Boolean)

| Flag | Starter | Professional | Premium |
|------|---------|--------------|---------|
| `google_calendar_enabled` | ❌ | ✅ | ✅ |
| `export_enabled` | ❌ | ✅ | ✅ |
| `custom_branding_enabled` | ❌ | ❌ | ✅ |
| `video_evidence_enabled` | ❌ | ❌ | ✅ |

### Numeric Limits

| Limit | Starter | Professional | Premium | Enterprise |
|-------|---------|--------------|---------|------------|
| `max_staff` | 1 | 5 | 15 | 999999 |
| `max_active_clients` | 20 | 100 | 500 | 999999 |
| `max_monthly_bookings` | 50 | 250 | 1000 | 999999 |
| `max_monthly_notifications` | 100 | 500 | 2000 | 999999 |

### Soft vs Hard Limits

| Limit Type | Behavior | User Experience |
|------------|----------|----------------|
| **Hard limit** (staff, clients) | Block creation, return 403 | "Staff limit reached. Upgrade to add more." |
| **Soft limit** (bookings/month) | Warn at 80%, block at 100% | "You've used 80% of monthly bookings." then block |
| **Feature flag** | Hide/disable in UI, return 403 in API | Feature not shown; API returns upgrade prompt |

---

## 3. Enforcement Architecture

### Where Checks Happen

```
Request → API Gateway → Lambda Handler
                          ↓
                   get_current_company_id(event)
                          ↓
                   get_tenant_entitlement(company_id)  ← EXISTING (cached)
                          ↓
                   check_entitlement(entitlement, action, context)  ← NEW
                          ↓
                   [proceed OR return 403 with upgrade message]
```

### Proposed Helper Function

```python
# src/backend/common/entitlement.py (NEW MODULE)

from common.billing import get_tenant_entitlement
from common.auth import get_current_company_id
from common.response import error

class EntitlementDenied(Exception):
    """Raised when an action is denied due to entitlement limits."""
    def __init__(self, message, upgrade_hint=None):
        super().__init__(message)
        self.upgrade_hint = upgrade_hint

def check_subscription_active(event):
    """
    Verify tenant has active subscription. Fail-closed.
    Call at the top of write-operation handlers.
    """
    company_id = get_current_company_id(event)
    ent = get_tenant_entitlement(company_id)
    
    if not ent.is_access_allowed:
        if ent.is_read_only:
            raise EntitlementDenied(
                "Account is past due. Read-only access until payment is updated.",
                upgrade_hint="update_payment"
            )
        raise EntitlementDenied(
            "Subscription is inactive. Please reactivate to continue.",
            upgrade_hint="resubscribe"
        )
    return ent

def check_feature(event, feature_flag):
    """Check if a feature flag is enabled for the tenant's tier."""
    ent = check_subscription_active(event)
    if not ent.limits.get(feature_flag, False):
        raise EntitlementDenied(
            f"This feature requires a higher plan.",
            upgrade_hint="upgrade"
        )
    return ent

def check_limit(event, limit_key, current_count):
    """Check if a numeric limit would be exceeded."""
    ent = check_subscription_active(event)
    max_allowed = ent.limits.get(limit_key, 0)
    if current_count >= max_allowed:
        raise EntitlementDenied(
            f"Limit reached ({current_count}/{max_allowed}). Upgrade for more capacity.",
            upgrade_hint="upgrade"
        )
    return ent
```

### Handler Integration Pattern

```python
# Example: admin_handler.py — staff creation
from common.entitlement import check_limit, EntitlementDenied

try:
    # Count existing staff for this tenant
    staff_count = count_staff(company_id)
    check_limit(event, 'max_staff', staff_count)
except EntitlementDenied as e:
    return error(403, str(e), event)

# Proceed with staff creation...
```

---

## 4. Initial Enforceable Gates (Priority Order)

### Phase 1: Low-Risk, High-Value (17B)

| Gate | Handler | Check | Risk |
|------|---------|-------|------|
| Export access | admin_handler (export) | `check_feature(event, 'export_enabled')` | Low — returns 403, no data loss |
| Google Calendar | google_auth_handler | `check_feature(event, 'google_calendar_enabled')` | Low — blocks new connections only |
| Staff count limit | admin_handler (staff onboard) | `check_limit(event, 'max_staff', count)` | Low — blocks creation only |

### Phase 2: Medium-Risk, Important (17C)

| Gate | Handler | Check | Risk |
|------|---------|-------|------|
| Client count limit | admin_handler (client create) | `check_limit(event, 'max_active_clients', count)` | Medium — need accurate count |
| Booking monthly limit | intake_handler | `check_limit(event, 'max_monthly_bookings', month_count)` | Medium — need monthly counter |
| Subscription active (write ops) | review, assignment, cancellation | `check_subscription_active(event)` | Medium — blocks all writes if inactive |

### Phase 3: Higher-Risk, Deferred (17D+)

| Gate | Handler | Check | Notes |
|------|---------|-------|-------|
| Login blocked for canceled | Auth layer / session | Status check | Deferred — requires frontend changes |
| Notification monthly limit | notification service | Already partially exists (quota) | Needs tenant parameterization |
| Mobile client app access | API response | Tier check | Deferred — low urgency |

---

## 5. What Must NOT Be Enforced Yet

| Rule | Reason |
|------|--------|
| Do NOT block tog_and_dogs login | Current production must remain operational |
| Do NOT enforce booking limits for tog_and_dogs | Ryan's active workflow must not break |
| Do NOT block staff operations mid-visit | Safety risk if staff can't complete a visit |
| Do NOT enforce Stripe subscription lifecycle checks | Live Stripe not active (EIN pending) |
| Do NOT gate based on `subscription_status` initially | tog_and_dogs is `active` but lifecycle isn't Stripe-driven yet |

### Safe Introduction Strategy

1. **Implement enforcement code but wrap in a feature flag** (`ENTITLEMENT_ENFORCEMENT_ENABLED`)
2. Initially set to `false` for tog_and_dogs (existing tenant unaffected)
3. Set to `true` only for new tenants created after provisioning is built
4. Optionally: enable per-handler ("soft launch" one gate at a time)

---

## 6. Fail-Safe Behavior

| Scenario | Behavior | Rationale |
|----------|----------|-----------|
| Tenant metadata missing | **Allow access** (log warning) | Don't break existing ops for missing data |
| DynamoDB read fails | **Allow access** (log error) | Availability over enforcement |
| `subscription_status` unknown/null | **Allow access** (treat as active) | Legacy data compatibility |
| `STRIPE_ENV = sandbox` | **Skip subscription lifecycle checks** | Sandbox doesn't have real subscriptions |
| Protected admin account | **Always allow** (bypass all checks) | Matthew/root must never be locked out |
| `ENTITLEMENT_ENFORCEMENT_ENABLED = false` | **Skip all checks** | Feature flag off = no enforcement |
| Tenant is tog_and_dogs + no explicit limits set | **Use professional tier defaults** | Current behavior preserved |

### Implementation

```python
def check_subscription_active(event):
    # Fail-safe: if enforcement is disabled, allow
    if not os.environ.get('ENTITLEMENT_ENFORCEMENT_ENABLED', '').lower() == 'true':
        return _default_entitlement(event)
    
    # Fail-safe: sandbox mode skips lifecycle checks
    if os.environ.get('STRIPE_ENV', 'sandbox') == 'sandbox':
        # Still check feature flags/limits, but don't block on subscription_status
        company_id = get_current_company_id(event)
        return get_tenant_entitlement(company_id)
    
    # Full enforcement for live mode
    ...
```

---

## 7. Migration/Backfill Needs

### Current tog_and_dogs Tenant State

| Field | Current | Needed for Enforcement | Action |
|-------|---------|------------------------|--------|
| `subscription_tier` | `professional` | ✅ Correct | None |
| `subscription_status` | `active` | ✅ Correct | None |
| `limits` | May not be explicitly set | Needed for limit checks | Backfill from TIER_LIMITS if missing |
| `feature_flags` | May not be set | Needed for feature checks | Derive from tier if missing |
| `billing_status_changed_at` | May not be set | Needed for grace period | Not urgent until live Stripe |

### Backfill Strategy

The `get_tenant_entitlement()` function already handles missing fields:
```python
limits = tenant.get('limits') or TIER_LIMITS.get(tier, TIER_LIMITS['starter'])
```

No DynamoDB migration needed. The code derives limits from `subscription_tier` if `limits` field is absent.

### Test Tenant Strategy

For testing enforcement without creating a second real tenant:
- Use a clearly-named test request/scenario
- Mock `get_tenant_entitlement()` in tests to return different tiers
- Unit tests cover all tier/status combinations (already partially exist in test_r12d)

---

## 8. Validation Strategy

### Unit Tests (17B)

| Test | Assertion |
|------|-----------|
| `check_subscription_active` with active → allows | No exception |
| `check_subscription_active` with canceled → raises | EntitlementDenied |
| `check_subscription_active` with past_due (grace) → allows | No exception |
| `check_subscription_active` with past_due (expired) → raises | EntitlementDenied (read-only) |
| `check_feature` with enabled flag → allows | No exception |
| `check_feature` with disabled flag → raises | EntitlementDenied |
| `check_limit` below max → allows | No exception |
| `check_limit` at max → raises | EntitlementDenied |
| Enforcement disabled (env var) → always allows | No exception |
| Sandbox mode → skips status check, still checks limits | Correct behavior |
| Missing tenant → allows with warning | No exception, log emitted |

### Integration Tests (17C)

| Test | Method |
|------|--------|
| Staff creation blocked when at limit | Mock entitlement, call handler |
| Export blocked for starter tier | Mock entitlement, call handler |
| Calendar connection blocked for starter | Mock entitlement, call handler |
| Normal operation unaffected (professional tier) | Real entitlement, call handler |

### Frontend/Mobile (17D)

| Test | Method |
|------|--------|
| Feature hidden when disabled in entitlement response | UI state check |
| Limit warning shown at 80% usage | UI display |
| 403 error handled gracefully with upgrade message | Error handling |

---

## 9. Recommended Release Breakdown

| Release | Scope | Effort | Depends On |
|---------|-------|--------|------------|
| **17A** | Design document (this) | ✅ Done | — |
| **17B** | Core helpers (`common/entitlement.py`) + unit tests + feature flag env var | Low | 17A |
| **17C** | Wire into Phase 1 gates (export, calendar, staff limit) + integration tests | Medium | 17B |
| **17D** | Wire into Phase 2 gates (client limit, booking limit, active subscription) | Medium | 17C |
| **17E** | Frontend entitlement UI states (feature hiding, limit warnings, upgrade messages) | Medium | 17C |
| **17F** | Mobile entitlement visibility (hide/show based on tier response) | Low | 17C |
| **17G** | Usage metering baseline (monthly booking counter per tenant) | Medium | 17D |

### Safe Deployment Order

1. 17B: Deploy helpers + env var `ENTITLEMENT_ENFORCEMENT_ENABLED=false` → zero risk
2. 17C: Wire Phase 1 gates → still disabled by feature flag → zero risk
3. Enable for one gate at a time (export first) → low risk, easy rollback
4. Monitor CloudWatch for EntitlementDenied exceptions → confirm only expected blocks
5. Enable remaining gates progressively

---

## 10. What This Document Does NOT Authorize

- ❌ Writing code
- ❌ Creating the entitlement module
- ❌ Modifying handlers
- ❌ Deploying anything
- ❌ DynamoDB changes
- ❌ Terraform changes
- ❌ Stripe/Cognito changes
- ❌ Mobile/frontend changes
- ❌ Creating a second tenant
- ❌ Inviting Ryan

This is a design document. Implementation begins with Release 17B (requires separate approval).
