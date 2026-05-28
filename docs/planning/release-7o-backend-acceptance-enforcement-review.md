# Release 7O: Backend Terms/Privacy Acceptance Enforcement — Review

**Status:** Review Complete — NO IMPLEMENTATION NEEDED
**Finding:** The backend enforcement is already implemented and deployed.

---

## 1. Current Findings

### Backend Validation: ALREADY IMPLEMENTED ✅

The acceptance validation was implemented in commit `fb417a6` ("feat: implement Phase 1 Terms and Privacy Policy acceptance") and is currently deployed in production.

**Location:** `src/backend/handlers/intake_handler.py`, lines 381–394

**Current behavior:**

```python
if workflow_type == WorkflowType.CUSTOMER_INTAKE:
    acceptance_errors = []
    if body.get('accepted_terms') is not True:
        acceptance_errors.append('accepted_terms is required')
    if body.get('accepted_privacy') is not True:
        acceptance_errors.append('accepted_privacy is required')
    terms_version = body.get('terms_version', '')
    privacy_version = body.get('privacy_version', '')
    if not terms_version or len(str(terms_version)) > 20:
        acceptance_errors.append('terms_version is invalid')
    if not privacy_version or len(str(privacy_version)) > 20:
        acceptance_errors.append('privacy_version is invalid')
    if acceptance_errors:
        return bad_request("Terms of Use and Privacy Policy acceptance is required.", event)
```

### What This Validates

| Field | Validation | Enforced? |
|-------|-----------|-----------|
| `accepted_terms` | Must be exactly `True` (not truthy, not "true", not 1) | ✅ Yes |
| `accepted_privacy` | Must be exactly `True` | ✅ Yes |
| `terms_version` | Non-empty string, ≤20 characters | ✅ Yes |
| `privacy_version` | Non-empty string, ≤20 characters | ✅ Yes |

### What Is Exempt (Correctly)

| Path | Exempt? | Reason |
|------|---------|--------|
| Admin-created bookings (`source: 'admin_created'`) | ✅ Yes | Handled by `_handle_admin_created_booking()` which returns before the validation block |
| Authenticated portal submissions (`/client/requests`) | ✅ Yes | `workflow_type` is set to `VISIT_BOOKING` for portal path, validation only runs for `CUSTOMER_INTAKE` |
| Staff-options endpoint (`action: 'staff-options'`) | ✅ Yes | Returns before reaching validation |

### Acceptance Metadata Storage: ALREADY IMPLEMENTED ✅

After validation passes, the handler stores acceptance metadata on the REQ record:

```python
if workflow_type == WorkflowType.CUSTOMER_INTAKE:
    item['accepted_terms'] = True
    item['accepted_privacy'] = True
    item['terms_version'] = body.get('terms_version')
    item['privacy_version'] = body.get('privacy_version')
    item['accepted_at'] = datetime.utcnow().isoformat()
    item['accepted_by_email'] = client_email
    item['source'] = 'public_intake'
```

---

## 2. What Is Actually Missing (Minor Gaps)

| Gap | Severity | Recommendation |
|-----|----------|---------------|
| No backend unit tests for acceptance validation | Low | Add tests in a future release (7P or backlog) |
| Error message is generic ("acceptance is required") rather than listing specific missing fields | Very Low | Cosmetic — the frontend prevents this case anyway |
| No admin CareCard visibility of acceptance status | Low | Deferred — planned in original spec but not blocking |

---

## 3. Recommendation

**Release 7O is NOT needed.** The backend enforcement is already complete and deployed.

The gap Kiro previously identified has been resolved — it was implemented as part of the Terms & Privacy Policy Phase 1 work (commit `fb417a6`).

### Suggested Next Steps (Optional, Low Priority)

If Matthew wants to add test coverage for the acceptance validation:

1. Add `tests/backend/test_intake_acceptance.py` with cases for:
   - Valid submission with all acceptance fields → 200
   - Missing `accepted_terms` → 400
   - Missing `accepted_privacy` → 400
   - Empty `terms_version` → 400
   - `terms_version` > 20 chars → 400
   - Admin-created booking without acceptance → 200 (exempt)
   - Portal submission without acceptance → 200 (exempt)

2. This could be a small backlog task or folded into the next release that touches `intake_handler.py`.

---

## 4. Summary

| Question | Answer |
|----------|--------|
| Is backend acceptance validation implemented? | **Yes** — commit `fb417a6` |
| Is it deployed to production? | **Yes** — part of the current Lambda package |
| Can direct API calls bypass acceptance? | **No** — backend rejects `CUSTOMER_INTAKE` without valid acceptance fields |
| Are admin/offline bookings exempt? | **Yes** — correctly handled |
| Are portal submissions exempt? | **Yes** — correctly handled |
| Is Release 7O needed? | **No** — the work is already done |
| Should we add tests? | Optional — low priority backlog item |

---

## 5. No AG Implementation Needed

There is no implementation prompt for this release because the work is already complete. The release can be closed as "already implemented" or the task can be removed from the roadmap.

If Matthew wants the acceptance test coverage added, that can be a small task in the next release or a standalone backlog item.
