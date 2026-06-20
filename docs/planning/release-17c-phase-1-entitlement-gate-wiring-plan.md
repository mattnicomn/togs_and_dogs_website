# Release 17C: Phase 1 Entitlement Gate Wiring Plan

**Status:** Planning
**Priority:** High (first real enforcement in production)
**Risk to Production:** Low (enforcement disabled by default; gates only fire when enabled)
**Terraform Required:** Yes (add `ENTITLEMENT_ENFORCEMENT_ENABLED` env var to relevant Lambdas)
**Code Changes:** Yes (handler modifications)
**Scope:** Wire Phase 1 entitlement checks into 3 low-risk endpoints

---

## 1. Phase 1 Endpoints to Wire

| # | Endpoint | Handler File | Gate Type | Risk |
|---|----------|--------------|-----------|------|
| 1 | `GET /admin/export-data` | `admin_handler.py` | Feature flag: `export_enabled` | Low |
| 2 | `GET /admin/auth/google` (initiate connection) | `google_auth_handler.py` | Feature flag: `google_calendar_enabled` | Low |
| 3 | `POST /admin/staff/onboard` | `admin_handler.py` | Limit: `max_staff` | Low |

---

## 2. Gate 1: Export Data Access

### Location

```
src/backend/handlers/admin_handler.py
Line ~220: if http_method == 'GET' and path == '/admin/export-data':
```

### Implementation

```python
# After role check, before scan:
from common.entitlement import check_feature, EntitlementDenied

try:
    check_feature(company_id, 'export_enabled')
except EntitlementDenied as e:
    return error(403, str(e), event)
```

### Behavior

| Tier | `export_enabled` | Result |
|------|------------------|--------|
| Starter | `False` | 403: "This feature requires a higher plan." |
| Professional | `True` | ✅ Allowed |
| Premium | `True` | ✅ Allowed |
| Enterprise | `True` | ✅ Allowed |

### Current tog_and_dogs Impact

- Tier: `professional` → `export_enabled = True` → **no change in behavior**
- Only blocks if enforcement is enabled AND tenant is on Starter tier

### HTTP Response (Denied)

```json
{
  "statusCode": 403,
  "body": { "error": "This feature requires a higher plan. Upgrade to access data export." }
}
```

### Frontend Impact

- Admin dashboard export button should show upgrade message if 403 returned
- Current UX: export button always visible — no change until 17D/17E

### Mobile Impact

- Export is web-only — no mobile impact

### Tests Required

| Test | Input | Expected |
|------|-------|----------|
| Professional tier → export allowed | `export_enabled = True` | 200 |
| Starter tier → export denied | `export_enabled = False` | 403 |
| Enforcement disabled → export allowed regardless | `ENTITLEMENT_ENFORCEMENT_ENABLED = false` | 200 |
| Missing tenant → export allowed (fail-open) | No TENANT record | 200 |

---

## 3. Gate 2: Google Calendar Connection

### Location

```
src/backend/handlers/google_auth_handler.py
Line ~114: def initiate_auth(event):
```

### Implementation

```python
# At the top of initiate_auth(), after role/auth check:
from common.entitlement import check_feature, EntitlementDenied
from common.auth import get_current_company_id

company_id = get_current_company_id(event)
try:
    check_feature(company_id, 'google_calendar_enabled')
except EntitlementDenied as e:
    return error(403, str(e), event)
```

### Behavior

| Tier | `google_calendar_enabled` | Result |
|------|---------------------------|--------|
| Starter | `False` | 403: "Google Calendar requires a higher plan." |
| Professional | `True` | ✅ Allowed |
| Premium | `True` | ✅ Allowed |

### Important: Existing Calendar Connection

- Gate applies to **initiating a NEW connection** (`GET /admin/auth/google` → OAuth flow)
- Does **NOT** gate ongoing calendar sync (review_handler, assignment_handler call calendar sync internally)
- Does **NOT** disconnect an already-connected calendar
- Does **NOT** gate health checks or status queries

### Endpoints to Gate vs NOT Gate

| Endpoint | Gate? | Reason |
|----------|-------|--------|
| `GET /admin/auth/google` (initiate OAuth) | ✅ Yes | Prevents new connections on Starter |
| `GET /admin/auth/callback` (OAuth callback) | ❌ No | Must complete in-flight OAuth |
| `GET /admin/auth/status` | ❌ No | Read-only status check |
| `DELETE /admin/auth/google` (disconnect) | ❌ No | Allow disconnect anytime |
| Internal calendar sync (in review/assign handlers) | ❌ No | Don't break active workflows |

### Current tog_and_dogs Impact

- Tier: `professional` → `google_calendar_enabled = True` → **no change**

### Tests Required

| Test | Input | Expected |
|------|-------|----------|
| Professional tier → connect allowed | `google_calendar_enabled = True` | Normal OAuth flow |
| Starter tier → connect denied | `google_calendar_enabled = False` | 403 |
| Enforcement disabled → connect allowed | Feature flag off | Normal flow |

---

## 4. Gate 3: Staff Count Limit

### Location

```
src/backend/handlers/admin_handler.py
Line ~460: if http_method == 'POST' and '/admin/staff/onboard' in path:
```

Also consider:
```
Line ~398: if http_method == 'POST' and (path == '/admin/staff' or path.endswith('/admin/staff')):
```

Both endpoints create staff records. Gate both.

### Staff Count Logic

**How staff are currently counted:**
```python
resp = items_table.query(
    KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("STAFF#")
)
existing_staff = resp.get('Items', [])
```

**Count definition for limit purposes:**
- Count ALL staff records under `COMPANY#{company_id} / STAFF#*`
- Include active AND disabled/unlinked staff (they consume a slot)
- Rationale: inactive staff still hold a profile record and could be reactivated

**When to check:** BEFORE creating the new staff record (deny if `count >= max_staff`)

### Implementation

```python
# After role check, before creating staff:
from common.entitlement import check_limit, EntitlementDenied
from common.auth import get_current_company_id

company_id = get_current_company_id(event)

# Count existing staff
from boto3.dynamodb.conditions import Key
resp = items_table.query(
    KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("STAFF#"),
    Select='COUNT'
)
staff_count = resp.get('Count', 0)

try:
    check_limit(company_id, 'max_staff', staff_count)
except EntitlementDenied as e:
    return error(403, str(e), event)
```

### Behavior

| Tier | `max_staff` | Current Staff | Result |
|------|-------------|---------------|--------|
| Starter | 1 | 0 | ✅ Allow (1st staff) |
| Starter | 1 | 1 | 403: "Staff limit reached (1/1). Upgrade for more." |
| Professional | 5 | 4 | ✅ Allow (5th staff) |
| Professional | 5 | 5 | 403: "Staff limit reached (5/5). Upgrade for more." |

### Boundary: At Limit vs Over Limit

- `current_count >= max_allowed` → DENY (cannot create more)
- `current_count < max_allowed` → ALLOW

### Current tog_and_dogs Impact

- Tier: `professional` → `max_staff = 5`
- Current staff count: likely 1–3 (Ryan + possibly test staff)
- **No change in behavior** unless 5 staff already exist

### HTTP Response (Denied)

```json
{
  "statusCode": 403,
  "body": { "error": "Staff limit reached (5/5). Upgrade your plan to add more staff members." }
}
```

### Tests Required

| Test | Input | Expected |
|------|-------|----------|
| Count below limit → allowed | 2 staff, max 5 | 200 + staff created |
| Count at limit → denied | 5 staff, max 5 | 403 |
| Enforcement disabled → allowed | Any count, flag off | 200 |
| Missing tenant → allowed (fail-open) | No TENANT record | 200 |

---

## 5. Rollout Mode

### Default: Enforcement Disabled

```
ENTITLEMENT_ENFORCEMENT_ENABLED = false (Lambda env var)
```

When disabled:
- `check_feature()` returns immediately without blocking
- `check_limit()` returns immediately without blocking
- `check_subscription_active()` returns immediately without blocking
- Zero production impact

### Enabling: Per-Environment

```hcl
# infra/prod/main.tf — Lambda environment block:
ENTITLEMENT_ENFORCEMENT_ENABLED = "false"  # Change to "true" when ready
```

### Progressive Enablement

1. Deploy with `false` → zero risk
2. Enable for one specific test request/scenario (manual DynamoDB check)
3. Enable globally for a single gate (export first — safest)
4. Monitor CloudWatch for `EntitlementDenied` exceptions
5. If clean for 24h, enable remaining gates

---

## 6. Safe Deny Behavior

| Scenario | Behavior |
|----------|----------|
| tog_and_dogs (professional, active) | All Phase 1 features allowed — no change |
| Protected/root admin | Bypass all checks (never blocked) |
| Missing TENANT metadata | Fail-open: allow access, log warning |
| DynamoDB read error | Fail-open: allow access, log error |
| Sandbox mode (`STRIPE_ENV=sandbox`) | Skip subscription status checks; still evaluate feature/limit flags |
| Unknown tier (not in TIER_LIMITS) | Default to starter limits (most restrictive safe fallback) |

---

## 7. Terraform Changes Needed

### Add Environment Variable to Relevant Lambdas

| Lambda | Needs `ENTITLEMENT_ENFORCEMENT_ENABLED`? |
|--------|------------------------------------------|
| `admin` | ✅ Yes (export + staff gates) |
| `google_auth` | ✅ Yes (calendar connect gate) |
| `stripe_webhook` | ❌ No (system-level) |
| `postmark_webhook` | ❌ No (system-level) |
| `intake` | ⚠️ Phase 2 (booking limit) |
| `review` | ⚠️ Phase 2 (subscription active) |
| `assign` | ⚠️ Phase 2 (subscription active) |
| `cancellation` | ⚠️ Phase 2 |
| `pet` | ⚠️ Phase 2 |
| `job` | ❌ No (internal) |
| `device` | ❌ No (low-risk) |

### Expected Terraform Plan

```
Plan: 0 to add, 2 to change, 0 to destroy.

~ aws_lambda_function.admin (environment variable added)
~ aws_lambda_function.google_auth (environment variable added)
```

---

## 8. Test Summary

### New Tests (in test_r17c_entitlement_gates.py)

| # | Test | Gate |
|---|------|------|
| 1 | Export allowed for professional tier | Export |
| 2 | Export denied for starter tier (enforcement enabled) | Export |
| 3 | Export allowed when enforcement disabled | Export |
| 4 | Export allowed when tenant missing (fail-open) | Export |
| 5 | Calendar connect allowed for professional | Calendar |
| 6 | Calendar connect denied for starter (enabled) | Calendar |
| 7 | Calendar connect allowed when disabled | Calendar |
| 8 | Staff creation allowed under limit | Staff |
| 9 | Staff creation denied at limit (enabled) | Staff |
| 10 | Staff creation allowed when disabled | Staff |
| 11 | Staff creation allowed when tenant missing | Staff |
| 12 | Protected admin bypasses all gates | All |

### Existing Tests Must Still Pass

- All 422 existing backend tests must pass unchanged
- No existing handler behavior is modified when enforcement is disabled

---

## 9. Recommended Implementation Release: 17D

**17D — Phase 1 Entitlement Gate Wiring Implementation**

Scope:
- Add `check_feature` call to export endpoint in admin_handler.py
- Add `check_feature` call to `initiate_auth` in google_auth_handler.py
- Add `check_limit` call to staff creation endpoints in admin_handler.py
- Add `ENTITLEMENT_ENFORCEMENT_ENABLED` env var to admin + google_auth Lambdas (Terraform)
- Add 12 new unit tests
- Set env var to `false` initially (zero production impact)
- Confirm all 434+ tests pass

**17E — Phase 1 Gate Activation**

Scope:
- Set `ENTITLEMENT_ENFORCEMENT_ENABLED = true` via Terraform apply
- Monitor CloudWatch for 24h
- Confirm tog_and_dogs (professional) is unaffected
- Document results

---

## 10. What This Document Does NOT Authorize

- ❌ Writing code
- ❌ Modifying handlers
- ❌ Running Terraform
- ❌ Deploying anything
- ❌ DynamoDB changes
- ❌ Enabling enforcement
- ❌ Stripe/Cognito/Postmark changes
- ❌ Mobile/frontend changes
- ❌ Adding Ryan

This is a planning document. Implementation requires separate Release 17D approval.
