# Release 20D: Disabled Tenant Backend Access Enforcement Plan

**Status:** Planning
**Date:** 2026-06-27
**Priority:** High (hardening gap — disabled tenants can still call APIs)
**Scope:** Design centralized backend enforcement so disabled tenants are blocked at the API layer

---

## 1. Problem

When `subscription_status = disabled`:
- `get_tenant_entitlement()` correctly returns `is_blocked = true`
- However, most tenant-scoped API endpoints do NOT call `check_subscription_active()` before returning data
- `/admin/tenant-info` returns 200 with full tenant details instead of blocking
- System relies on frontend reading the status and redirecting — this is insufficient for security

**Risk:** A disabled tenant owner who bypasses the frontend (curl, Postman, direct API call) can still read business data.

---

## 2. Disabled-Tenant Response Contract

### Standard Blocked Response

```json
{
  "statusCode": 403,
  "body": {
    "error": "TenantDisabled",
    "message": "Your business account is currently inactive. Please contact support to reactivate.",
    "contact": "support@usmissionhero.com"
  }
}
```

### Minimal Status Response (For Frontend Bootstrap)

One endpoint MAY return a limited response so the frontend can show the "account disabled" page:

```json
{
  "statusCode": 200,
  "body": {
    "company_id": "test_tenant_alpha",
    "display_name": "Test Tenant Alpha",
    "subscription_status": "disabled",
    "is_access_allowed": false,
    "contact": "support@usmissionhero.com"
  }
}
```

This returns NO operational data (no staff, clients, bookings, etc.).

---

## 3. Endpoint Classification

### Must Block (403 TenantDisabled)

All tenant-scoped operational endpoints:

| Route | Handler | Reason |
|-------|---------|--------|
| `GET /admin/requests` | admin_handler | Business data |
| `POST /admin/requests` | admin_handler | Write operation |
| `GET /admin/staff` | admin_handler | Business data |
| `POST /admin/staff` | admin_handler | Write operation |
| `POST /admin/staff/onboard` | admin_handler | Write operation |
| `GET /admin/clients` | admin_handler | Business data |
| `POST /admin/clients` | admin_handler | Write operation |
| `GET /admin/pets` | admin_handler | Business data |
| `GET /admin/export-data` | admin_handler | Sensitive bulk data |
| `POST /admin/review` | review_handler | Write operation |
| `POST /admin/assign` | assignment_handler | Write operation |
| `POST /admin/job/complete` | admin_handler | Write operation |
| `POST /client/cancel` | cancellation_handler | Write operation |
| `PUT /admin/cancel/decision` | cancellation_handler | Write operation |
| `GET /admin/auth/google` | google_auth_handler | Integration setup |
| `DELETE /admin/auth/google` | google_auth_handler | Integration teardown |
| `GET /client/requests` | admin_handler | Business data |
| `GET /client/pets` | pet_handler | Business data |
| `POST /admin/payment-session` | admin_handler | Financial operation |
| `POST /admin/requests/{id}/send-payment-email` | admin_handler | Communication |
| `POST /requests` (intake) | intake_handler | Creates records for tenant |

### May Return Minimal Status (200 with Limited Data)

| Route | Handler | Returned Data |
|-------|---------|---------------|
| `GET /admin/tenant-info` | admin_handler | company_id, display_name, subscription_status, is_access_allowed ONLY |
| `GET /admin/auth/status` | google_auth_handler | Connection status only (already tenant-gated in 19K) |

### Platform Admin (Always Available — No Tenant Block)

| Route | Handler | Reason |
|-------|---------|--------|
| `GET /platform/tenants` | platform_handler | Platform admin manages ALL tenants |
| `GET /platform/tenants/{id}` | platform_handler | Includes disabled tenants |
| `PATCH /platform/tenants/{id}` | platform_handler | Can re-enable disabled tenants |
| `GET /platform/audit` | platform_handler | Cross-tenant audit visibility |

### Public/System (Unaffected by Tenant Disable)

| Route | Handler | Reason |
|-------|---------|--------|
| `POST /webhooks/stripe` | stripe_webhook_handler | System-level, no tenant auth |
| `POST /webhooks/postmark` | postmark_webhook_handler | System-level |
| `GET /admin/auth/callback` | google_auth_handler | OAuth callback (stateless) |

---

## 4. Recommended Backend Helper Approach

### Centralized Check in `common/entitlement.py`

Extend the existing `check_subscription_active()` function:

```python
def require_active_tenant(event):
    """
    Call at the top of every tenant-scoped handler.
    Returns the entitlement object if active.
    Raises EntitlementDenied with TenantDisabled if blocked.
    """
    company_id = get_current_company_id(event)
    ent = get_tenant_entitlement(company_id)
    
    if ent.is_blocked:
        raise EntitlementDenied(
            "Your business account is currently inactive. Please contact support to reactivate.",
            upgrade_hint="contact_support",
            error_code="TenantDisabled"
        )
    return ent
```

### Integration Pattern (Per Handler)

```python
# At the top of each tenant-scoped route, after auth:
from common.entitlement import require_active_tenant, EntitlementDenied

try:
    require_active_tenant(event)
except EntitlementDenied as e:
    return error(403, str(e), event)
```

### Platform Admin Bypass

Platform admin routes (`/platform/*`) do NOT call `require_active_tenant()`. They use their own `require_platform_admin()` check instead.

### Relationship to Existing Checks

| Check | Purpose | When |
|-------|---------|------|
| `require_active_tenant(event)` | Block disabled/canceled tenants | All tenant-scoped routes |
| `check_feature(company_id, flag)` | Gate tier-specific features | Feature-gated routes (Phase 1) |
| `check_limit(company_id, key, count)` | Enforce numeric limits | Write routes with limits (Phase 2) |
| `validate_tenant_ownership(item, event)` | Prevent cross-tenant data access | After item retrieval |

`require_active_tenant` should be the FIRST check after authentication, before any data access.

---

## 5. Special Case: /admin/tenant-info

### Recommendation: Return Minimal Status (Do NOT Block)

**Rationale:** The frontend needs to know the tenant is disabled so it can show an appropriate "account inactive" page instead of a generic error. Blocking this endpoint completely would leave the frontend with no information to display.

```python
# /admin/tenant-info — special case:
if path == '/admin/tenant-info' and http_method == 'GET':
    company_id = get_current_company_id(event)
    ent = get_tenant_entitlement(company_id)
    tenant = get_item(f"TENANT#{company_id}", "METADATA")
    
    # Return minimal info regardless of status (for frontend routing)
    return success({
        "company_id": company_id,
        "display_name": tenant.get('display_name', company_id) if tenant else company_id,
        "subscription_status": ent.subscription_status,
        "subscription_tier": ent.subscription_tier,
        "is_access_allowed": ent.is_access_allowed,
        "is_blocked": ent.is_blocked,
    }, event)
```

**What this does NOT return:** staff lists, client lists, bookings, financial data, tokens, or any operational business data.

---

## 6. Test Plan

### Unit Tests

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | Active tenant → `require_active_tenant` allows | status=active | Returns entitlement, no exception |
| 2 | Trialing tenant → allows | status=trialing | Returns entitlement |
| 3 | Disabled tenant → blocks | status=disabled | Raises EntitlementDenied (TenantDisabled) |
| 4 | Canceled tenant → blocks | status=canceled | Raises EntitlementDenied |
| 5 | Past-due within grace → allows | status=past_due, recent | Returns entitlement |
| 6 | Past-due beyond grace → blocks | status=past_due, old | Raises EntitlementDenied |
| 7 | Admin override active → allows despite disabled | override set, status=disabled | Returns entitlement |

### Integration Tests

| # | Test | Expected |
|---|------|----------|
| 8 | Active tenant GET /admin/requests → 200 | Normal response |
| 9 | Disabled tenant GET /admin/requests → 403 TenantDisabled | Blocked |
| 10 | Disabled tenant GET /admin/tenant-info → 200 (minimal) | Status info only |
| 11 | Platform admin GET /platform/tenants → 200 (includes disabled) | Works regardless |
| 12 | tog_and_dogs unaffected when test_tenant_alpha disabled | Normal 200 |
| 13 | Existing Phase 1/Phase 2 entitlement tests still pass | No regression |

---

## 7. Rollout Strategy

### Safe Deployment

1. Add `require_active_tenant()` call to each handler (behind existing enforcement flag)
2. Since `ENTITLEMENT_ENFORCEMENT_ENABLED=true` is already active, checks fire immediately
3. For tog_and_dogs (active): zero impact (check passes)
4. For test_tenant_alpha (currently active): zero impact
5. Only fires when a tenant is actually disabled

### Risk

**Very low** — the check only blocks when `subscription_status` is explicitly set to a blocked value. Current tenants are both `active`. No production impact until someone intentionally disables a tenant.

---

## 8. Recommended Release Sequence

| Release | Scope | Owner |
|---------|-------|-------|
| **20D** | Disabled tenant enforcement plan (this document) | ✅ Kiro (done) |
| **20E** | Backend implementation: add `require_active_tenant()` to all tenant routes | AG |
| **20F** | Controlled revalidation: disable test_tenant_alpha, verify 403s | AG + Matthew |
| **20G** | Owner onboarding simplification plan | Kiro |
| **20H** | External tester readiness checklist | Kiro |

---

## 9. What This Document Does NOT Authorize

- ❌ Code changes
- ❌ Deploying anything
- ❌ Disabling tenants
- ❌ Modifying handlers
- ❌ Terraform/AWS changes
- ❌ Cognito changes
- ❌ DynamoDB writes
- ❌ Stripe/Google Calendar/Postmark changes
- ❌ Mobile/TestFlight/App Store changes
- ❌ Ryan/tester changes

This is a planning document. Implementation (20E) requires separate approval.
