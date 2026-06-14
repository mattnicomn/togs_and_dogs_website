# Release 11D: Tenant Enforcement Hardening Plan

**Status:** Planning
**Priority:** High (must complete before any second tenant is created)
**Risk to Production:** Medium (behavior changes to existing endpoints)
**Terraform Required:** No
**Backend Changes:** Yes (handler-level validation additions)
**Scope:** Add post-read tenant validation to all direct-item-access paths

---

## 1. Current Tenant Model Summary

| Component | Status After 11A-11C |
|-----------|---------------------|
| `TENANT#tog_and_dogs / METADATA` record | ✅ Created (11C) |
| `get_current_company_id(event)` | ✅ Used in 30+ handler locations |
| Staff/Client profiles under `COMPANY#{company_id}` PK | ✅ Scoped by key design |
| Request list queries with `company_id` filter | ✅ Applied |
| `validate_tenant_ownership(item, event)` | ❌ Defined but **never called** |
| Post-read tenant check on REQ/JOB/PET lookups | ❌ Missing |
| Export endpoint tenant filtering | ❌ Missing |
| Notification quota per-tenant scoping | ❌ Hardcoded `tog_and_dogs` |
| `attribute_not_exists(company_id)` fallback | ⚠️ Present — leaks in multi-tenant |

---

## 2. Handlers/Endpoints Requiring Hardening

### Critical: Direct get_item Without Post-Read Validation

| Handler | Endpoint | Record Type | Risk |
|---------|----------|-------------|------|
| `review_handler.py` | POST /admin/review | REQ# | High — any known request_id accessible |
| `cancellation_handler.py` | POST /client/cancel, PUT /admin/cancel/decision | REQ# | High |
| `assignment_handler.py` | POST /admin/assign | REQ#, JOB# | Medium — validates staff via company but not request |
| `admin_handler.py` | GET /admin/requests (single-item) | REQ# | High |
| `admin_handler.py` | POST /admin/job/complete | JOB# | High |
| `admin_handler.py` | POST /admin/requests (PURGE/DELETE/ARCHIVE) | REQ# | High |
| `pet_handler.py` | GET /admin/pets/{petId} | PET# | Medium — indirect via client |
| `pet_handler.py` | PUT /admin/pets/{petId} | PET# | Medium |
| `job_handler.py` | Lambda trigger | REQ# (input) | Low — internal invocation |

### Critical: Scan/Query Without Tenant Filter

| Handler | Endpoint | Issue |
|---------|----------|-------|
| `admin_handler.py` | GET /admin/export-data | Full table scan, ALL records returned |
| `admin_handler.py` | `_resolve_admin_record` (scan fallback) | Scans entire table for orphan resolution |

### Medium: Hardcoded Single-Tenant Logic

| Location | Issue |
|----------|-------|
| `service.py` `_get_monthly_send_count` | `get_item("QUOTA#tog_and_dogs", ...)` |
| `service.py` `_increment_monthly_send_count` | `Key={"PK": "QUOTA#tog_and_dogs", ...}` |
| `service.py` `_write_ledger_entry` | Fallback: `company_id = "tog_and_dogs"` |

---

## 3. Proposed Shared Tenant Validation Strategy

### Decision: Extend Existing `validate_tenant_ownership()`

The function already exists with the correct logic. It just needs to be **called** after every direct `get_item` that uses user-supplied identifiers.

```python
# common/auth.py — already exists:
def validate_tenant_ownership(item, event):
    if not isinstance(item, dict):
        return
    item_company = item.get('company_id')
    if not item_company:
        item_company = DEFAULT_COMPANY_ID
    caller_company = get_current_company_id(event)
    if item_company != caller_company:
        raise PermissionError("Forbidden: Cross-tenant data access detected")
```

### Usage Pattern (Add After Every get_item)

```python
# Before (current — no validation):
item = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")
if not item:
    return not_found(...)

# After (hardened):
item = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")
if not item:
    return not_found(...)
try:
    validate_tenant_ownership(item, event)
except PermissionError:
    return error(403, "Forbidden: Cross-tenant access denied", event)
```

### Why Not a New Function?

The existing `validate_tenant_ownership` is:
- Already imported via `from common.auth import ...`
- Correctly resolves both item's company_id and caller's company_id
- Raises `PermissionError` which handlers can catch
- Handles the `DEFAULT_COMPANY_ID` fallback for legacy records

No new abstraction needed. Just call it.

---

## 4. Post-Read Validation Pattern

### For Direct Item Lookups (REQ#, JOB#, PET#)

```python
from common.auth import validate_tenant_ownership

# After get_item:
item = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")
if not item:
    return not_found(f"Request {request_id} not found", event)
try:
    validate_tenant_ownership(item, event)
except PermissionError:
    # Log the attempt for audit
    print(f"SECURITY: Cross-tenant access attempt by {get_claims(event).get('email')} for REQ#{request_id}")
    return error(403, "Forbidden", event)
```

### For PET Records (Indirect Ownership)

PET records don't have `company_id` directly. Validation path:
1. Get the PET record → extract `client_id` from SK
2. Check that a CLIENT profile exists under the caller's company: `get_item(f"COMPANY#{company_id}", f"CLIENT#{client_id}")`
3. If client doesn't belong to caller's company → 403

```python
# PET tenant validation:
pet = get_item(f"PET#{pet_id}", f"CLIENT#{client_id}")
if not pet:
    return not_found(...)

# Verify the client belongs to the caller's company
company_id = get_current_company_id(event)
client_check = get_item(f"COMPANY#{company_id}", f"CLIENT#{client_id}")
if not client_check:
    return error(403, "Forbidden", event)
```

---

## 5. Query/Scan Hardening

### Export Endpoint Fix

**Current:**
```python
response = _table.scan(**scan_kwargs)  # No filter — returns ALL tenants
```

**Hardened:**
```python
from common.auth import get_current_company_id
company_id = get_current_company_id(event)

scan_kwargs["FilterExpression"] = Attr('company_id').eq(company_id) | Attr('company_id').not_exists()
# OR: post-filter results
items = [i for i in items if i.get('company_id', DEFAULT_COMPANY_ID) == company_id]
```

### `_resolve_admin_record` Scan Fallback

This function scans for orphan records by ID fragments. Add company_id post-filter:
```python
found_items = [i for i in found_items if i.get('company_id', DEFAULT_COMPANY_ID) == company_id]
```

### Remove `attribute_not_exists(company_id)` Fallback

**Current (in ALL-scan query):**
```python
"(company_id = :cid OR attribute_not_exists(company_id))"
```

**Strategy:**
1. First: backfill any records missing `company_id` with `"tog_and_dogs"` (one-time migration)
2. Then: remove the `attribute_not_exists` clause
3. Result: records without company_id are invisible (fail closed)

**Phasing:** Do the backfill in 11D implementation; remove the fallback in 11E after confirming all records have company_id.

---

## 6. Notification Quota Remediation

### Current (Hardcoded)

```python
get_item("QUOTA#tog_and_dogs", f"MONTH#{month_key}")
table.update_item(Key={"PK": "QUOTA#tog_and_dogs", "SK": f"MONTH#{month_key}"}, ...)
```

### Hardened

```python
company_id = record.get('company_id') or 'tog_and_dogs'
get_item(f"QUOTA#{company_id}", f"MONTH#{month_key}")
table.update_item(Key={"PK": f"QUOTA#{company_id}", "SK": f"MONTH#{month_key}"}, ...)
```

**Risk:** Low. The existing `QUOTA#tog_and_dogs` record stays valid for Ryan's tenant. Future tenants get their own quota counter automatically.

---

## 7. Test Plan

### Same-Tenant Access (Must Succeed)

| # | Test | Expected |
|---|------|----------|
| 1 | Admin fetches REQ# belonging to own company | ✅ 200 + data |
| 2 | Admin assigns staff within own company | ✅ 200 + success |
| 3 | Staff completes JOB# belonging to assigned visit | ✅ 200 + completed |
| 4 | Client views own bookings | ✅ 200 + list |
| 5 | Export returns only own company data | ✅ Only tog_and_dogs records |

### Cross-Tenant Access (Must Fail)

| # | Test | Expected |
|---|------|----------|
| 6 | Admin fetches REQ# from different company_id | ❌ 403 Forbidden |
| 7 | Admin assigns staff to cross-tenant request | ❌ 403 Forbidden |
| 8 | Staff completes JOB# from different tenant | ❌ 403 Forbidden |
| 9 | Admin exports data with forged company_id | ❌ Only caller's data returned |
| 10 | GET pet belonging to cross-tenant client | ❌ 403 Forbidden |

### Missing company_id (Must Fail Closed)

| # | Test | Expected |
|---|------|----------|
| 11 | Record with `company_id = None` + non-default tenant caller | ❌ 403 or invisible |
| 12 | Record with missing company_id attribute + default tenant caller | ✅ Accessible (fallback matches) |

### Notification Quota (Per-Tenant)

| # | Test | Expected |
|---|------|----------|
| 13 | Notification sent for tog_and_dogs record | Increments `QUOTA#tog_and_dogs` |
| 14 | Notification sent for future tenant_x record | Increments `QUOTA#tenant_x` |

---

## 8. Safe Implementation Sequence

| Step | Scope | Risk | Release |
|------|-------|------|---------|
| 1 | Add `validate_tenant_ownership` import to all handlers | None (import only) | 11E |
| 2 | Add post-read validation to `review_handler.py` | Low | 11E |
| 3 | Add post-read validation to `cancellation_handler.py` | Low | 11E |
| 4 | Add post-read validation to `admin_handler.py` (single-item GET, job/complete, purge) | Low | 11E |
| 5 | Add post-read validation to `assignment_handler.py` | Low | 11E |
| 6 | Add indirect validation to `pet_handler.py` | Low | 11E |
| 7 | Add company_id filter to export endpoint | Low | 11E |
| 8 | Parameterize notification quota key | Low | 11E |
| 9 | Backfill any records missing company_id | Medium | 11F |
| 10 | Remove `attribute_not_exists(company_id)` fallback | Medium | 11F (after backfill confirmed) |

### Grouping

- **Release 11E:** Steps 1-8 (enforcement additions — all additive, fail-safe for current single-tenant)
- **Release 11F:** Steps 9-10 (migration + fallback removal — requires data verification first)

---

## 9. Rollback Strategy

### If Tenant Validation Causes Issues

If `validate_tenant_ownership` calls cause false-positive 403 errors:
1. Check which records are missing `company_id` (the `DEFAULT_COMPANY_ID` fallback handles these for now)
2. If widespread: temporarily revert the validation calls in the affected handler
3. Investigate: are records genuinely cross-tenant, or just missing the field?

### Key Safety Property

For the CURRENT single-tenant system (`tog_and_dogs` only):
- ALL records have `company_id = "tog_and_dogs"` OR no `company_id` (which defaults to `"tog_and_dogs"`)
- The caller's company is always `"tog_and_dogs"` (from env var fallback)
- Therefore: `validate_tenant_ownership` will ALWAYS pass for the current system

**The hardening is invisible to Ryan's workflow.** It only becomes meaningful when a second tenant exists.

---

## 10. Risks / Open Questions

| Risk | Impact | Resolution |
|------|--------|-----------|
| Records with null company_id fail validation | Medium | DEFAULT_COMPANY_ID fallback handles this (existing logic) |
| Additional DynamoDB reads for PET validation | Low | One extra get_item per PET access (negligible at scale) |
| Export performance with filter | Low | Filtering already happens; just makes it tenant-scoped |
| Legacy `_resolve_admin_record` scan | Low | Post-filter is sufficient; scan is already rare/fallback |
| Breaking existing tests | Medium | Tests use mock company_id; validate mock setups match |

---

## 11. What This Release Does NOT Do

| ❌ Does NOT | Reason |
|-------------|--------|
| Create a second tenant | Single-tenant enforcement only |
| Enable billing | Stripe is future (Release 12C) |
| Add Cognito custom attributes | Future (Release 11E+) |
| Fix the web/mobile app | Backend-only enforcement |
| Remove DEFAULT_COMPANY_ID fallback | Deferred until backfill confirmed (Release 11F) |
| Add tenant-aware notification routing | Future |

---

## 12. Recommended Implementation Release

**Release 11E: Tenant Enforcement Implementation**

AG adds `validate_tenant_ownership` calls to all high-risk handlers (Steps 1-8 above). Includes:
- Backend handler modifications
- Unit tests for same-tenant success + cross-tenant 403
- `py_compile` + `pytest` validation
- No Terraform changes
- Requires Matthew's explicit approval before deployment (`terraform apply`)

---

## 13. What This Document Does NOT Authorize

- ❌ Modifying any code
- ❌ Writing to DynamoDB
- ❌ Modifying Cognito
- ❌ Deploying to production
- ❌ Running builds (EAS or Terraform)
- ❌ Creating a second tenant

This is a planning document only. Implementation requires separate explicit approval.
