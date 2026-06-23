# Release 18K: Phase 2 Entitlement Gate Design — Client and Booking Limits

**Status:** Design Complete
**Date:** 2026-06-23
**Priority:** Medium (next enforcement layer before second-tenant work)
**Scope:** Design client count limit and monthly booking limit enforcement

---

## 1. Phase 2 Gates Summary

| Gate | Limit Key | When Checked | Priority |
|------|-----------|--------------|----------|
| **Client count limit** | `max_active_clients` | Before client profile creation | ✅ Phase 2 |
| **Monthly booking limit** | `max_monthly_bookings` | Before booking/request creation | ✅ Phase 2 |
| Subscription-status login gate | `subscription_status` | On login/session bootstrap | ⏳ Deferred (Phase 3) |
| Monthly notification limit refinement | `max_monthly_notifications` | Already partially enforced via QUOTA# | ⏳ Deferred |

---

## 2. Client Limit Behavior

### What Counts as a Client

| Record Type | Counts Toward Limit? | Rationale |
|-------------|---------------------|-----------|
| Active client (`CLIENT#` under `COMPANY#`) | ✅ Yes | Active resource consumer |
| Disabled client | ✅ Yes | Still holds a profile slot |
| Archived client | ❌ No | Freed capacity; can be restored but not active |
| Admin-created (offline) client | ✅ Yes | Same as any other client |
| Self-registered client (intake) | ✅ Yes | Consumes slot on creation |
| Duplicate client records | ⚠️ Count each | No dedup logic currently; address in cleanup if needed |

### Count Query

```python
# Count active (non-archived) clients
resp = table.query(
    KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("CLIENT#"),
    Select='COUNT',
    FilterExpression=Attr('status').ne('archived') | Attr('status').not_exists()
)
active_client_count = resp.get('Count', 0)
```

**Note:** If `status` field is not consistently present on client records, fall back to counting all CLIENT# records (same as staff behavior). Refinement can come later.

### Where the Gate Applies

| Endpoint | Handler | Gate |
|----------|---------|------|
| `POST /admin/clients` (create client) | admin_handler.py | `check_limit(company_id, 'max_active_clients', count)` |
| `POST /admin/staff/onboard` → auto-client-create (if applicable) | admin_handler.py | Same check |
| `POST /requests` (intake creates client profile) | intake_handler.py | `check_limit(company_id, 'max_active_clients', count)` |

### Denial Response

```json
{
  "statusCode": 403,
  "body": { "error": "Client limit reached (20/20). Upgrade your plan to add more clients." }
}
```

### Platform Admin Display

```
Clients: 18/100 (Professional)
```

---

## 3. Monthly Booking Limit Behavior

### What Counts as a Booking

| Item | Counts? | Rationale |
|------|---------|-----------|
| New booking request (intake form) | ✅ Yes | Primary billing unit |
| Admin offline booking | ✅ Yes | Same service delivery |
| Multi-day booking (1 request, N days) | ✅ Counts as 1 | Request is the billing unit, not individual days |
| Child JOB records (per-day expansion) | ❌ No | Internal scheduling detail |
| Cancelled booking (before service) | ⚠️ Still counts | Was created and consumed capacity; prevents gaming |
| Test bookings (`is_test_booking = true`) | ❌ No | Admin testing should not consume quota |
| Completed visits | ❌ N/A | Limit is on creation, not completion |

### MVP Definition

> **Monthly booking limit = count of new REQ# records created under a tenant during the current calendar month, excluding test bookings.**

### Multi-Day Handling

A multi-day booking creates 1 REQ# record + N JOB# child records. Only the REQ# creation increments the monthly counter. This is the fairest model for pricing — one service request = one booking regardless of duration.

### Month Boundary

If a request is created on Jan 31 for service Feb 1–5:
- Counts toward **January's** monthly limit (creation date, not service date)
- This is the simplest, most predictable model

### Usage Counter Design

```
PK: USAGE#{company_id}
SK: BOOKINGS#{YYYY-MM}

{
  "company_id": "tog_and_dogs",
  "period": "2026-06",
  "count": 47,
  "last_incremented_at": "2026-06-23T10:00:00Z"
}
```

### Increment Logic

```python
# After successful request creation:
table.update_item(
    Key={'PK': f'USAGE#{company_id}', 'SK': f'BOOKINGS#{current_month}'},
    UpdateExpression='SET #count = if_not_exists(#count, :zero) + :one, last_incremented_at = :now',
    ExpressionAttributeNames={'#count': 'count'},
    ExpressionAttributeValues={':zero': 0, ':one': 1, ':now': now_iso}
)
```

### Check Logic (Before Creation)

```python
# Before creating a request:
usage = get_item(f'USAGE#{company_id}', f'BOOKINGS#{current_month}')
current_count = usage.get('count', 0) if usage else 0
check_limit(company_id, 'max_monthly_bookings', current_count)
```

### Where the Gate Applies

| Endpoint | Handler | Gate |
|----------|---------|------|
| `POST /requests` (public intake) | intake_handler.py | Check monthly booking count before creation |
| Admin offline booking (POST /admin/requests action=create) | admin_handler.py | Same check |

### Denial Response

```json
{
  "statusCode": 403,
  "body": { "error": "Monthly booking limit reached (50/50). Upgrade your plan for more bookings." }
}
```

### Test Booking Exemption

```python
if body.get('is_test_booking'):
    # Skip monthly counter increment
    pass
else:
    increment_monthly_booking_count(company_id)
```

---

## 4. Tier Source of Truth

### Where Limits Live

```python
# src/backend/common/billing.py — TIER_LIMITS dict
TIER_LIMITS = {
    'starter': { 'max_active_clients': 20, 'max_monthly_bookings': 50, ... },
    'professional': { 'max_active_clients': 100, 'max_monthly_bookings': 250, ... },
    'premium': { 'max_active_clients': 500, 'max_monthly_bookings': 1000, ... },
    'enterprise': { 'max_active_clients': 999999, 'max_monthly_bookings': 999999, ... },
}
```

### Resolution Chain

```
Request → get_current_company_id(event) → get_tenant_entitlement(company_id)
  → TenantEntitlement.limits['max_active_clients'] / ['max_monthly_bookings']
  → check_limit(company_id, key, current_value)
```

### Platform Admin Display

```
Usage:
  Staff:    5/5   (Professional)
  Clients:  18/100
  Bookings: 47/250 (this month)
```

### Denial Logging

All Phase 2 denials emit:
```
ENTITLEMENT_DENIED: company=tog_and_dogs, check=max_active_clients, current=20, limit=20, tier=starter
```

Existing CloudWatch metric filters for `ENTITLEMENT_DENIED` automatically capture Phase 2 denials.

---

## 5. Idempotency and Race Conditions

### Counter Atomicity

The `update_item` with `if_not_exists + :one` is atomic at the DynamoDB level. Two concurrent requests will each increment correctly — the counter will reflect both.

### Race Condition on Limit Check

```
T1: Request A reads count = 249 (limit 250) → allowed
T2: Request B reads count = 249 → allowed
T3: Request A increments → count = 250
T4: Request B increments → count = 251 (OVER LIMIT)
```

**Impact:** Tenant could exceed limit by 1–2 bookings in a tight race.

**Mitigation for MVP:** Accept ±2 variance. At current scale (single tenant, low volume), this is negligible. For strict enforcement later, use DynamoDB conditional expression:

```python
ConditionExpression='#count < :limit'
```

### Counter Correction

If counter becomes inaccurate:
- Platform admin can see actual count vs counter value
- Manual correction: `update_item` to set correct count
- Or: derive from actual record count (query) and reset counter
- No automated correction in MVP

---

## 6. Test Strategy for AG

### Unit Tests

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | Client count under limit → allowed | 18 clients, max 100 | Pass |
| 2 | Client count at limit → denied | 100 clients, max 100 | 403 |
| 3 | Client count over limit → denied | 101 clients, max 100 | 403 |
| 4 | Monthly booking under limit → allowed | 47 bookings, max 250 | Pass |
| 5 | Monthly booking at limit → denied | 250 bookings, max 250 | 403 |
| 6 | Test booking exempt from counter | `is_test_booking = true` | Counter not incremented |
| 7 | Enforcement disabled → all allowed | Flag off | Pass regardless of count |
| 8 | Missing usage record → zero count (allowed) | No USAGE# record exists | Treated as 0 |
| 9 | Missing tenant → fail-open | No TENANT# record | Pass (single mode compatibility) |
| 10 | Counter increment is atomic | Concurrent mock | Both increment |
| 11 | Multi-day booking counts as 1 | 5-day booking | Counter +1, not +5 |
| 12 | Cancelled booking still counted | Cancelled after creation | Counter unchanged (already incremented) |
| 13 | Platform admin unaffected | Platform routes | No limit checks on /platform/* |
| 14 | Cross-tenant isolation | Two different company_ids | Each has own counter |

### Integration Tests

| # | Test | Method |
|---|------|--------|
| 15 | intake_handler blocks at monthly limit | Mock entitlement + counter at limit |
| 16 | admin_handler blocks client creation at limit | Mock entitlement + client count at limit |
| 17 | Existing Phase 1 tests still pass | Full regression |

---

## 7. Rollout Strategy

### Recommended: Observability-First (Same as Phase 1)

| Step | Action | Risk |
|------|--------|------|
| 1 | Implement counter + limit checks behind `ENTITLEMENT_ENFORCEMENT_ENABLED` | Zero (already defaults true, but can disable) |
| 2 | Deploy code — enforcement is active immediately for new limits | Low (professional tier has generous limits: 100 clients, 250 bookings) |
| 3 | Monitor CloudWatch for unexpected ENTITLEMENT_DENIED | Standard |
| 4 | If issues: rollback by setting enforcement to false | ~5 min |

### Why NOT Observability-Only First

Phase 1 proved the enforcement-disabled → enabled pattern is safe. For Phase 2:
- Professional tier limits (100 clients, 250 bookings) are well above current usage
- Enforcement will only fire if a lower-tier tenant exists (which doesn't yet)
- For tog_and_dogs Professional: effectively invisible (same as Phase 1)

### Strict Mode Consideration

Phase 2 gates do NOT depend on `TENANT_RESOLUTION_MODE=multi`. They use the same `check_limit()` pattern as Phase 1. They should be deployed regardless of strict-mode status.

---

## 8. Risk Matrix

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| 1 | Incorrectly blocking real client/booking creation | Low (pro tier is generous) | High | Phase 2 only fires at limit; pro tier has 100/250 headroom |
| 2 | Over-counting multi-day bookings | Low | Medium | Design counts 1 REQ# per booking, not child JOBs |
| 3 | Under-counting admin-created bookings | Low | Low | Same path through counter increment |
| 4 | Cross-tenant counter leak | Very low | High | Counter key includes company_id |
| 5 | Race condition (±2 bookings over limit) | Low | Low | Accept for MVP; conditional write later |
| 6 | No easy counter correction | Medium | Low | Manual update possible; derive from actual count |
| 7 | Confusing owner UX (limit message) | Low | Low | Clear message with current/max values |
| 8 | Counter not backfilled for historical months | N/A | None | Only counts forward; historical months have no counter |

---

## 9. Recommended Release Sequence

| Release | Scope | Owner |
|---------|-------|-------|
| **18K** | Phase 2 gate design (this document) | ✅ Kiro (done) |
| **18L** | Monthly booking counter + client limit implementation | AG |
| **18M** | Phase 2 deployment + controlled validation | AG + Matthew |
| **18N** | Platform Admin usage display refinement (show booking count) | AG |
| **18O** | Strict-mode final gate review (June 30 target) | Kiro + Matthew |

---

## 10. What This Document Does NOT Authorize

- ❌ Code changes
- ❌ Creating DynamoDB records
- ❌ Modifying handlers
- ❌ Deploying anything
- ❌ Creating bookings/clients
- ❌ Terraform/AWS changes
- ❌ Cognito changes
- ❌ Creating second tenant
- ❌ Enabling strict mode
- ❌ Stripe/Postmark/payment changes
- ❌ Ryan/tester changes

This is a design document. Implementation (18L) requires separate approval.
