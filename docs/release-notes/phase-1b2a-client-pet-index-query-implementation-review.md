# Phase 1B.2A: ClientPetIndex Query Implementation Review

**Date:** 2026-07-19
**Reviewer:** Kiro
**Status:** NEEDS LOCAL TEST HARDENING

---

## Implementation Commit Reviewed

`c372223` — feat(backend): implement local ClientPetIndex query cutover and fix listing test mocks

## Files Changed

| File | Change |
|------|--------|
| `src/backend/handlers/pet_handler.py` | Replace 2 Scan paths with ClientPetIndex Query + tenant defense |
| `src/backend/common/pet_profile.py` | Replace `_get_client_pets()` Scan with ClientPetIndex Query; add company_id parameter |
| `tests/backend/test_r6f_offline_booking.py` | Update 2 existing test mocks for Query behavior |

---

## Three-Path Code Assessment: SOUND

All three documented pet-by-client Scan paths were replaced with ClientPetIndex Query. No remaining production pet-by-client Scan exists.

### Path 1: Client Portal (GET /client/pets)
- ✅ Derives `client_id` from `resolve_client_identity(event)`
- ✅ Derives `company_id` from `get_current_company_id(event)`
- ✅ Validates canonical client via `GetItem(PK=COMPANY#{company_id}, SK=CLIENT#{client_id})`
- ✅ Returns `{"pets": []}` on failed validation (no Query executed)
- ✅ Queries `ClientPetIndex` by `client_id`
- ✅ Full pagination (while loop with `ExclusiveStartKey`)
- ✅ Filters: `entity_type == 'PET'`, company_id present and matches, `is_active` not explicitly `False`
- ✅ Sanitizes response with `sanitize_booking_for_role(item, 'client')`
- ✅ Returns `{"pets": [...]}`

### Path 2: Admin Listing (GET /admin/pets?clientId={id})
- ✅ Derives `client_id` from query parameter
- ✅ Derives `company_id` from `get_current_company_id(event)`
- ✅ Validates canonical client via `GetItem(PK=COMPANY#{company_id}, SK=CLIENT#{client_id})`
- ✅ Returns `{"pets": []}` on failed validation (no Query executed)
- ✅ Queries `ClientPetIndex` by `client_id`
- ✅ Full pagination (while loop with `ExclusiveStartKey`)
- ✅ Filters: `entity_type == 'PET'`, company_id present and matches, `is_active` not explicitly `False`
- ✅ Returns `{"pets": [...]}`

### Path 3: Internal Helper (_get_client_pets in pet_profile.py)
- ✅ Signature updated: `_get_client_pets(client_id, company_id)`
- ✅ Validates canonical client via `GetItem(PK=COMPANY#{company_id}, SK=CLIENT#{client_id})`
- ✅ Returns `[]` on failed validation (no Query executed)
- ✅ Queries `ClientPetIndex` by `client_id`
- ✅ Full pagination (while loop with `ExclusiveStartKey`)
- ✅ Filters: `entity_type == 'PET'`, company_id present and matches, `is_active` not explicitly `False`
- ✅ Exception handling: catches all, logs warning, returns `[]`
- ✅ Both callers (`create_or_link_pets_from_request`, `_rebuild_pet_summary`) updated to pass `company_id`

---

## Ownership and Tenant-Defense Assessment: CORRECT

- Canonical client GetItem occurs before any Query
- No Query is issued when ownership validation fails
- company_id mismatch or absence silently excludes the record (no error exposed to caller)
- Cross-tenant denial does not log raw identifiers (only generic warning message)
- Admin path requires `owner` or `admin` role
- Client-portal path requires `client` role and identity-resolved client_id
- Internal helper accepts company_id from trusted internal callers only

---

## Pagination Assessment: CORRECT

All three paths implement identical pagination:
```python
while True:
    resp = table.query(**query_kwargs)
    items.extend(resp.get('Items', []))
    last_key = resp.get('LastEvaluatedKey')
    if not last_key:
        break
    query_kwargs['ExclusiveStartKey'] = last_key
```

- Handles empty first page followed by populated pages (LastEvaluatedKey drives continuation)
- Handles multiple pages (Items accumulated across iterations)
- Terminates cleanly when LastEvaluatedKey is absent
- No page-size limit artificially truncates results

---

## company_id and is_active Assessment: CORRECT

- Records missing `company_id`: excluded (`if not p_company`)
- Records with mismatched `company_id`: excluded (`p_company != company_id`)
- Records with `is_active` explicitly `False`: excluded (`p.get('is_active') is False`)
- Records with `is_active` explicitly `True`: included
- Records missing `is_active`: included (only explicit `False` is excluded)

This correctly handles the 13 legacy records missing company_id (excluded from results) and legacy records missing is_active (treated as active).

---

## Response Contract Assessment: PRESERVED

- All three paths return `{"pets": [...]}` (handler paths) or `list` (helper path)
- Client-portal path applies `sanitize_booking_for_role` before return
- Admin path returns unsanitized (existing behavior preserved)
- Helper returns raw filtered list (existing internal contract preserved)

---

## Remaining Scan Inventory: CLEAR

No production pet-by-client Scan remains. All remaining `.scan()` calls are unrelated to this release:

| File | Function/Context | Purpose |
|------|------------------|---------|
| `platform_handler.py` | Tenant metadata listing | Platform admin tenant list |
| `platform_handler.py` | Tenant bookings count | Platform admin stats |
| `device_handler.py` | Push-token dedup | Device registration |
| `assignment_handler.py` | Orphaned-job fallback | Race condition recovery |
| `admin_handler.py` | Record resolution | Admin record lookup |
| `admin_handler.py` | Requests listing | Admin queue display |
| `admin_handler.py` | Export-data | Data export |
| `admin_handler.py` | Paginated requests | Admin request list |

Each remaining Scan is outside this release's scope and serves a different functional purpose.

---

## Duplication Assessment: ACCEPTABLE FOR BOUNDED RELEASE

The Query+filter logic is repeated three times (two handler paths + one helper). Each instance is:
- Short (approximately 15 lines)
- Readable and self-contained
- Independently testable

**Assessment:** Future cleanup into a shared helper is recommended but is NOT a release blocker. The bounded scope makes the duplication acceptable for this release.

---

## Focused Coverage Matrix

### Requirements and Coverage Status

| # | Requirement | Status | Evidence |
|---|-------------|--------|----------|
| 1 | Canonical client ownership success | PARTIALLY COVERED | `test_admin_can_list_client_pets` mocks get_item returning Item; does not assert GetItem was called with correct key |
| 2 | Canonical client missing | NOT COVERED | No test where get_item returns no Item for admin path |
| 3 | Cross-tenant ownership denial | PARTIALLY COVERED | `test_client_pets_tenant_isolation` tests filtering but not ownership denial (mock returns Item) |
| 4 | Query uses ClientPetIndex | NOT COVERED | No assertion on IndexName in query kwargs |
| 5 | Query partition condition uses client_id | NOT COVERED | No assertion on KeyConditionExpression |
| 6 | No Scan invocation | NOT COVERED | No `table.scan.assert_not_called()` assertion |
| 7 | One-page Query | PARTIALLY COVERED | `test_admin_can_list_client_pets` mock returns single page (no LastEvaluatedKey), but does not assert single call |
| 8 | Multiple Query pages | NOT COVERED | No multi-page mock |
| 9 | Empty page with LastEvaluatedKey followed by populated page | NOT COVERED | No empty-then-populated mock |
| 10 | ExclusiveStartKey propagation | NOT COVERED | No assertion on continuation token passing |
| 11 | Missing company_id excluded | NOT COVERED | No pet record with missing company_id in test data |
| 12 | Mismatched company_id excluded | COVERED WITH MEANINGFUL ASSERTION | `test_client_pets_tenant_isolation` includes cross-company pet and asserts it's excluded |
| 13 | Matching company_id included | COVERED WITH MEANINGFUL ASSERTION | `test_admin_can_list_client_pets` asserts active matching pet is returned |
| 14 | Explicit is_active=False excluded | COVERED WITH MEANINGFUL ASSERTION | `test_admin_can_list_client_pets` includes is_active=False pet, asserts only 1 returned |
| 15 | Explicit is_active=True included | COVERED WITH MEANINGFUL ASSERTION | Same test includes is_active=True pet, asserts it's in result |
| 16 | Missing is_active treated active | NOT COVERED | No pet record with is_active absent in listing tests |
| 17 | Empty Query result | NOT COVERED | No test returning empty Items from query |
| 18 | Response remains {"pets": [...]} | PARTIALLY COVERED | Tests assert `"pets" in body` but not shape-only contract |
| 19 | Query exception behavior | NOT COVERED | No test simulating query exception |
| 20 | Admin path | COVERED WITH MEANINGFUL ASSERTION | `test_admin_can_list_client_pets` exercises admin path |
| 21 | Client portal path | NOT COVERED | No test exercising GET /client/pets |
| 22 | Internal pet_profile helper | NOT COVERED | No direct test of `_get_client_pets` |
| 23 | Both internal helper callers | NOT COVERED | No test verifying both callers pass company_id |
| 24 | No Query when ownership validation fails | NOT COVERED | No test asserting query not called on GetItem miss |
| 25 | No Scan fallback | NOT COVERED | Same as #6 |
| 26 | No raw identifiers logged on denial | NOT COVERED | No test inspecting log output on denial |

### Coverage Summary

| Category | Count |
|----------|-------|
| COVERED WITH MEANINGFUL ASSERTION | 4 |
| PARTIALLY COVERED | 4 |
| NOT COVERED | 18 |
| **Total** | **26** |

---

## Full-Suite Baseline/Candidate Comparison

### Verified Baseline (pre-change, from local closeout documentation)

| Metric | Count |
|--------|-------|
| Collected | 725 |
| Passed | 654 |
| Failed | 71 |
| Warnings | 102 |

### Candidate (post-change, verified 2026-07-19)

| Metric | Count |
|--------|-------|
| Collected | 725 |
| Passed | 656 |
| Failed | 69 |
| Warnings | 102 |

### Comparison

- **Candidate-only NEW failures: 0** ✅
- **Baseline failures now passing: 2** (test_admin_can_list_client_pets, test_client_pets_tenant_isolation — expected improvement from mock updates)
- **Newly collected tests: 0**
- **Unexplained count changes: None**

### Candidate Failing Node IDs (all 69 are pre-existing baseline failures)

All failures fall into known categories:
- `test_intake_validation.py` (6): PUBLIC_INTAKE_TENANT_RESOLUTION_FAILED — missing entitlement mock
- `test_protected_accounts.py` (3): TenantDisabled — missing require_active_tenant mock
- `test_r11e_tenant_enforcement.py` (3): TenantDisabled / fromisoformat — missing mocks
- `test_r12g_stripe_checkout.py` (8): TenantDisabled — missing require_active_tenant mock
- `test_r12t_payment_email.py` (8): TenantDisabled / fromisoformat — missing mocks
- `test_r18l_client_booking_limits.py` (2): Hardcoded date `2026-06` vs runtime `2026-07`
- `test_r4a_intake.py` (1): PUBLIC_INTAKE_TENANT_RESOLUTION_FAILED
- `test_r7a_optional_email.py` (3): fromisoformat / TENANT_RESOLUTION_FAILED
- `test_r7s_selected_dates.py` (12): PUBLIC_INTAKE_TENANT_RESOLUTION_FAILED
- `test_r7s_terms_acceptance.py` (12): PUBLIC_INTAKE_TENANT_RESOLUTION_FAILED
- `test_rbac_and_purge_safety.py` (8): fromisoformat — missing mocks
- `test_r11e_tenant_enforcement.py::test_pet_handler_get_same_tenant_succeeds` (1): TenantDisabled — missing require_active_tenant mock

None of these involve pet_handler Query paths, pet_profile, or ClientPetIndex.

---

## Compile and Formatting Checks

| Check | Result |
|-------|--------|
| `py_compile` — `src/backend/handlers/pet_handler.py` | ✅ OK |
| `py_compile` — `src/backend/common/pet_profile.py` | ✅ OK |
| `py_compile` — `tests/backend/test_r6f_offline_booking.py` | ✅ OK |
| `git diff --check` | ✅ Clean (no whitespace issues) |
| `git status` | ✅ Clean working tree |

---

## Documentation Correction

The local closeout document (`phase-1b2a-client-pet-index-query-cutover-local-closeout.md`) states:
> "All 19 local tests in test_r6f_offline_booking.py compile and pass successfully"

This is accurate — the 19 tests in that file do all pass. However, the closeout document does not claim the focused matrix is fully covered. The current-state document says:
> "Phase 1B.2A ClientPetIndex query cutover has been fully implemented and validated locally, with tests passing and scans replaced by bounded index queries."

This is factually correct but may be misleading without the caveat that the focused test matrix is only ~15% covered. The next approval gate (deployment) requires the focused test hardening to complete first.

No corrections to existing documentation are required — the statements are accurate within their context. This review document provides the additional focused-coverage detail.

---

## Restrictions Confirmed

The following did NOT occur during this review:
- ❌ No AWS access
- ❌ No Terraform action
- ❌ No backend or frontend application-code changes
- ❌ No deployment
- ❌ No production Query or Scan
- ❌ No remediation
- ❌ No production-data modification
- ❌ No Cognito write
- ❌ No tenant change or second-tenant creation
- ❌ No Google Play action
- ❌ No Stripe change
- ❌ No Google Calendar change
- ❌ No mobile-distribution change
- ❌ No Ryan-testing change

---

## Recommendation: **NEEDS LOCAL TEST HARDENING**

The code implementation is architecturally correct, the full-suite comparison shows zero candidate-only failures, and all compile/formatting checks pass. However, the focused test matrix required for safe production deployment has only 4 of 26 requirements meaningfully covered (15%).

### Required Before Deployment Approval

**Critical (must have):**
1. Canonical client not found → empty response, no Query issued
2. Cross-tenant ownership denial → empty response, no Query issued
3. Missing company_id pet excluded from results
4. No Scan invocation (`table.scan.assert_not_called()`)
5. Query uses ClientPetIndex (IndexName assertion)

**Important (should have):**
6. Multiple Query pages combined correctly
7. ExclusiveStartKey propagation
8. Missing is_active treated as active (included in results)
9. Empty Query result returns `{"pets": []}`
10. Query exception returns safe response

**Recommended (nice to have):**
11. Client-portal path end-to-end
12. pet_profile `_get_client_pets` direct test
13. No raw identifiers logged on denial

### Next Approval Gate

**Matthew approves AG to add focused Query-cutover tests locally** (no application logic changes, no deployment, no AWS access). After tests pass and Kiro re-reviews, Terraform plan generation for the Lambda package deployment may proceed.

---

## Starting/Ending State

| Item | Value |
|------|-------|
| Starting commit | `2238ff1` |
| Ending commit | (this review update) |
| Implementation commit reviewed | `c372223` |
| Branch | main |
| Working tree | clean |
