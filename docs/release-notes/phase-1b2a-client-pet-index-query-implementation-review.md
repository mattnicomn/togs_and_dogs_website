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

## Three-Path Code Assessment: SOUND

All three paths correctly implement:
- ✅ Canonical client GetItem before Query (`PK=COMPANY#{company_id}, SK=CLIENT#{client_id}`)
- ✅ Return empty/safe response on failed ownership
- ✅ ClientPetIndex Query by client_id
- ✅ Full pagination (while loop with ExclusiveStartKey)
- ✅ entity_type = 'PET' filter
- ✅ Missing company_id exclusion (`if not p_company`)
- ✅ Mismatched company_id exclusion (`p_company != company_id`)
- ✅ is_active=False exclusion
- ✅ Missing is_active treated as active (only explicit False excluded)
- ✅ Client-portal path sanitizes with `sanitize_booking_for_role`
- ✅ Response contract `{"pets": [...]}` preserved
- ✅ `_get_client_pets` signature updated to accept company_id; both callers updated
- ✅ No Scan fallback anywhere in the implementation
- ✅ No raw identifiers logged on denial

## Remaining Scan Inventory: CLEAR

No pet-by-client Scan remains. All remaining `.scan()` calls are unrelated:
- `platform_handler.py` — tenant metadata listing
- `device_handler.py` — push-token deduplication
- `assignment_handler.py` — orphaned-job race-condition fallback
- `admin_handler.py` — export, requests listing, admin-record resolution

## Duplication Assessment: ACCEPTABLE FOR BOUNDED RELEASE

The Query+filter logic is repeated three times. Future cleanup into a shared helper is recommended but is NOT a release blocker. Each instance is short, readable, and independently testable.

## Full-Suite Comparison

| Metric | Baseline (pre-change) | Candidate |
|--------|----------------------|-----------|
| Collected | 725 | 725 |
| Passed | 654 | 656 |
| Failed | 71 | 69 |
| Warnings | ~100 | 102 |

- **Candidate-only NEW failures: 0** ✅
- **Baseline failures now passing: 2** (existing pet-list tests that previously failed with Scan mocks now pass with Query mocks — expected improvement)
- **Net effect:** +2 passing tests, -2 failures — implementation fixes previously broken test paths

## Focused Test Coverage: INSUFFICIENT

Only 2 of the 26 planned test requirements have meaningful dedicated assertions:

| Category | Covered | Not Covered |
|----------|---------|-------------|
| Ownership validation | Partial (1-2) | 3-4 requirements missing |
| Query mechanics | 0 | IndexName, no-Scan, pagination (5 requirements) |
| Filtering | 0 | company_id, is_active (6 requirements) |
| Contract/error | Partial (1) | Exception, empty result, client-portal, helper (5 requirements) |
| Privacy | 0 | Denial logging (1 requirement) |

**Total:** ~3 of 26 meaningfully covered. **~23 requirements lack dedicated test assertions.**

## Compile and Formatting

- Python compile: PASSED ✅
- `git diff --check`: PASSED ✅

---

## Recommendation: **NEEDS LOCAL TEST HARDENING**

The code implementation is architecturally correct and the full-suite comparison shows zero candidate-only failures. However, the focused test matrix required for safe production deployment is severely under-covered. Before Terraform plan generation can be approved, AG must add dedicated tests for:

**Critical (security and correctness):**
- Canonical client not found → empty response, no Query
- Cross-tenant denial → empty response, no Query
- Missing company_id excluded from results
- Mismatched company_id excluded from results
- No Scan called (explicit `table.scan.assert_not_called()`)

**Important (pagination and contract):**
- Multiple Query pages combined
- Empty page with LastEvaluatedKey continuation
- is_active=False excluded
- Missing is_active treated as active
- Empty Query result
- Query exception handling

**Recommended (completeness):**
- Client-portal path coverage
- pet_profile helper direct coverage
- IndexName assertion

---

## Next Approval Gate

**Matthew approves AG to add focused Query-cutover tests locally** (no code logic changes, no deployment, no AWS access). After tests pass and Kiro re-reviews, Terraform plan generation may proceed.
