# Release 7S: Internal Hardening Backlog — Low-Risk Cleanup

**Status:** Planning
**Priority:** Low (housekeeping while Ryan is unavailable)
**Risk to Production:** None (tests + documentation + gitignore only)
**Terraform Required:** No
**Backend Behavior Changes:** None
**Frontend Behavior Changes:** None
**Scope:** Test coverage, .gitignore cleanup, documentation tidying

---

## 1. Current Findings

### 1.1 Test Coverage Assessment

| Area | Tests Exist? | Coverage Quality |
|------|-------------|-----------------|
| Multi-day JOB expansion | ✅ `test_r7e_multi_day_jobs.py` | Good — 20+ cases including selected_dates |
| Multi-day cancellation | ✅ `test_r7e_cancellation.py` | Good |
| Multi-day assignment | ✅ `test_r7g_assignment_multiday.py` | Good |
| Notification dedup | ✅ `test_r7f_notification_dedup.py` | Good |
| Notification templates (multi-day) | ✅ `test_r7f_template_multiday.py` | Good |
| Notification content polish | ✅ `test_r7j_notification_content_polish.py` | Good — selected_dates context |
| Calendar hardening (7D) | ✅ `test_r7d_calendar_hardening.py` | Good |
| Calendar all-day fallback | ✅ `test_r6g_calendar_all_day.py` | Good |
| Calendar retry | ✅ `test_r6g_calendar_retry.py` | Good |
| Calendar token handling | ✅ `test_r6g_calendar_token.py` | Good |
| Postmark webhook | ✅ `test_r6i_postmark_webhook.py` | Good |
| Notification ledger | ✅ `test_r6i_notification_ledger.py` | Good |
| Quota controls | ✅ `test_r6j_quota_controls.py` | Good |
| RBAC and purge safety | ✅ `test_rbac_and_purge_safety.py` | Good |
| Protected accounts | ✅ `test_r6h_protected_config.py` | Good |
| Offline booking | ✅ `test_r6f_offline_booking.py` | Good |
| Optional email (7A) | ✅ `test_r7a_optional_email.py` | Good |
| Device registration (7C) | ✅ `test_r7c_device_registration.py` | Good |
| Intake validation (basic) | ✅ `test_intake_validation.py` | Partial — see gap below |
| **Terms/Privacy acceptance validation** | ❌ **Missing** | No dedicated tests for rejection of missing/invalid acceptance fields |
| **Public intake selected_dates path** | ❌ **Missing** | No test verifying the public intake handler correctly processes `selected_dates` |

### 1.2 Untracked Kiro Spec Folders

| Folder | Git Status | Recommendation |
|--------|-----------|---------------|
| `.kiro/specs/postmark-notifications/` | Gitignored ✅ | Leave as-is |
| `.kiro/specs/terms-and-privacy-policy/` | Untracked (shows in `git status`) | **Add to .gitignore** |
| `.kiro/specs/mobile-admin-ux-polish/` | Tracked (committed) ✅ | Leave as-is |

The `terms-and-privacy-policy` folder is the only one cluttering `git status`. It should be gitignored like `postmark-notifications`.

### 1.3 Code Cleanliness

| Finding | Severity | Notes |
|---------|----------|-------|
| No TODO/FIXME/HACK comments | ✅ Clean | |
| SES client has deprecation docstring | ✅ Acceptable | Preserved as fallback, clearly marked |
| No dead imports or unused files found | ✅ Clean | |
| `test_r4a_intake.py` exists but may be legacy | Very Low | Referenced in agent operating model as "untracked unless explicitly included" |

### 1.4 Documentation State

| Document | Status | Notes |
|----------|--------|-------|
| Admin Quick Reference | ✅ Complete (7Q) | 14 sections, daily/weekly rhythm |
| Emergency Response Checklist | ✅ Complete (7Q) | 7 scenarios |
| Production Smoke Test | ✅ Complete (7Q) | 5 scenarios (A–E) |
| Ryan Handoff Guide | ✅ Complete (7R) | Trial checklist, monitoring guide |
| Notification Runbook | ✅ Complete (6J) | Quota, suppression, kill switches |
| Offline Client Guide | ✅ Complete (7B) | Full workflow |
| Google Calendar Guide | ✅ Complete (6G) | Reauth, troubleshooting |
| Release Checklist | ✅ Complete | Pre/post deploy, rollback |

**No documentation gaps found that can be closed without Ryan's input.**

---

## 2. Recommended Release 7S Scope

### Safe Work While Ryan Is Unavailable

| # | Item | Type | Effort | Risk |
|---|------|------|--------|------|
| 1 | **Add Terms/Privacy acceptance validation tests** | Tests only | 30 min | None |
| 2 | **Add public intake `selected_dates` processing test** | Tests only | 20 min | None |
| 3 | **Add `.kiro/specs/terms-and-privacy-policy/` to .gitignore** | Gitignore | 2 min | None |
| 4 | **Run full test suite and confirm 100% pass** | Validation | 5 min | None |

**Total: ~1 hour. Zero production behavior changes. Zero deployment risk.**

---

## 3. Detailed Implementation

### 3.1 Terms/Privacy Acceptance Validation Tests

**File:** `tests/backend/test_r7n_acceptance_validation.py` (new)

| # | Test | Description |
|---|------|-------------|
| 1 | `test_missing_accepted_terms_rejected` | Submit without `accepted_terms` → 400 |
| 2 | `test_missing_accepted_privacy_rejected` | Submit without `accepted_privacy` → 400 |
| 3 | `test_accepted_terms_false_rejected` | `accepted_terms: false` → 400 |
| 4 | `test_accepted_terms_string_rejected` | `accepted_terms: "true"` (string, not bool) → 400 |
| 5 | `test_empty_terms_version_rejected` | `terms_version: ""` → 400 |
| 6 | `test_long_terms_version_rejected` | `terms_version: "x" * 21` → 400 |
| 7 | `test_valid_acceptance_succeeds` | All fields valid → 200 (existing test confirms this, but explicit) |
| 8 | `test_admin_created_exempt` | Admin booking without acceptance → 200 |
| 9 | `test_portal_path_exempt` | Authenticated client portal without acceptance → 200 |
| 10 | `test_acceptance_stored_on_record` | Valid submission → DynamoDB item has all acceptance fields |

### 3.2 Public Intake `selected_dates` Processing Test

**File:** `tests/backend/test_r7e_intake_selected_dates.py` (new)

| # | Test | Description |
|---|------|-------------|
| 1 | `test_selected_dates_stored_on_req_record` | Submit with `selected_dates` → stored on REQ item |
| 2 | `test_selected_dates_sets_start_end` | `selected_dates: [Jul 1, Jul 5, Jul 8]` → `start_date=Jul 1`, `end_date=Jul 8` |
| 3 | `test_selected_dates_dedup_and_sort` | Unsorted/duplicate dates → stored sorted and deduped |
| 4 | `test_selected_dates_invalid_filtered` | Invalid dates in array → filtered out |
| 5 | `test_single_date_in_array_treated_normally` | `selected_dates: ["2026-07-01"]` → single-day behavior |

### 3.3 Gitignore Update

Add to `.gitignore`:

```
# Kiro specs (untracked unless explicitly promoted)
.kiro/specs/postmark-notifications/
.kiro/specs/terms-and-privacy-policy/
```

---

## 4. Items Explicitly Deferred Until Ryan Tests

| Item | Reason |
|------|--------|
| Any frontend behavior changes | Requires Ryan's visual validation |
| Any backend behavior changes | Requires production smoke test |
| Notification template wording adjustments | Requires Ryan's content approval |
| Admin CareCard acceptance display | Low priority, requires Ryan's UX feedback |
| Mobile app foundation (Release 8A) | Blocked until Ryan confirms web is stable |
| Push notification enablement | Blocked until mobile app exists |

---

## 5. Files Affected

| File | Change | New? |
|------|--------|------|
| `tests/backend/test_r7n_acceptance_validation.py` | New test file | ✅ New |
| `tests/backend/test_r7e_intake_selected_dates.py` | New test file | ✅ New |
| `.gitignore` | Add terms-and-privacy-policy to ignored specs | Modified |

### Files NOT Changed

- No backend handler code
- No frontend code
- No CSS
- No Terraform
- No notification logic
- No API changes
- No DynamoDB schema changes

---

## 6. Acceptance Criteria

- [ ] `tests/backend/test_r7n_acceptance_validation.py` — all 10 tests pass
- [ ] `tests/backend/test_r7e_intake_selected_dates.py` — all 5 tests pass
- [ ] Full backend test suite passes (all existing tests still green)
- [ ] `.gitignore` updated — `git status` no longer shows `terms-and-privacy-policy` as untracked
- [ ] No production code modified
- [ ] No deployment performed

---

## 7. Validation Plan

```bash
# Run new tests
pytest tests/backend/test_r7n_acceptance_validation.py -v
pytest tests/backend/test_r7e_intake_selected_dates.py -v

# Run full suite to confirm no regressions
pytest tests/backend/ -v

# Confirm gitignore works
git status  # Should NOT show .kiro/specs/terms-and-privacy-policy/
```

---

## 8. Risks and Rollback

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| New tests fail due to code behavior mismatch | Low | None | Fix the test, not the code (tests are documenting existing behavior) |
| Gitignore change accidentally ignores something important | Very Low | None | Only adding one specific path |

**Rollback:** Delete the new test files and revert the .gitignore line. No production impact.

---

## 9. Guardrails

- Do NOT modify any backend handler code
- Do NOT modify any frontend code
- Do NOT modify Terraform
- Do NOT deploy
- Do NOT change notification behavior
- Do NOT change DynamoDB, Cognito, or any AWS resource
- Tests must document EXISTING behavior, not introduce new behavior
- If a test reveals a bug, document it but do NOT fix it without Matthew's approval

---

## 10. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 7S: Internal Hardening (tests + gitignore only).

No production code changes. No deployment. Tests and gitignore only.

=== 1. Create tests/backend/test_r7n_acceptance_validation.py ===

Test the existing Terms/Privacy acceptance validation in intake_handler.py.
All tests should pass against the CURRENT code without modifications.

Tests:
- test_missing_accepted_terms_rejected: POST /requests with valid fields but no accepted_terms → 400
- test_missing_accepted_privacy_rejected: POST /requests with accepted_terms=True but no accepted_privacy → 400
- test_accepted_terms_false_rejected: accepted_terms=False → 400
- test_accepted_terms_string_rejected: accepted_terms="true" (string) → 400
- test_empty_terms_version_rejected: terms_version="" → 400
- test_long_terms_version_rejected: terms_version="x"*21 → 400
- test_valid_acceptance_succeeds: All valid → 200
- test_admin_created_exempt: source="admin_created" without acceptance → 200
- test_portal_path_exempt: path="/client/requests" with role=client without acceptance → 200
- test_acceptance_stored_on_record: Valid submission → put_item called with accepted_terms, accepted_privacy, terms_version, privacy_version, accepted_at, accepted_by_email, source="public_intake"

Mock pattern: Same as test_intake_validation.py (patch put_item, sfn).
For admin_created test: patch get_item to return a client profile, patch boto3.client for Lambda invoke.
For portal path test: set event path to "/client/requests" and mock resolve_client_identity.

=== 2. Create tests/backend/test_r7e_intake_selected_dates.py ===

Test the existing selected_dates processing in the public intake handler.
All tests should pass against the CURRENT code without modifications.

Tests:
- test_selected_dates_stored_on_req_record: Submit with selected_dates=["2026-07-01","2026-07-05","2026-07-08"] → put_item item has selected_dates field
- test_selected_dates_sets_start_end: selected_dates present → start_date=first, end_date=last
- test_selected_dates_dedup_and_sort: selected_dates=["2026-07-05","2026-07-01","2026-07-01"] → stored as ["2026-07-01","2026-07-05"]
- test_selected_dates_invalid_filtered: selected_dates=["2026-07-01","not-a-date","2026-07-05"] → stored as ["2026-07-01","2026-07-05"]
- test_single_date_in_array_treated_normally: selected_dates=["2026-07-01"] → start_date="2026-07-01", no multi-day behavior

Mock pattern: Same as test_intake_validation.py.
Include acceptance fields (accepted_terms=True, etc.) in all payloads since validation requires them.

=== 3. Update .gitignore ===

Change the existing line:
  .kiro/specs/postmark-notifications/

To:
  # Kiro specs (untracked unless explicitly promoted)
  .kiro/specs/postmark-notifications/
  .kiro/specs/terms-and-privacy-policy/

=== 4. Validation ===

Run:
- pytest tests/backend/test_r7n_acceptance_validation.py -v
- pytest tests/backend/test_r7e_intake_selected_dates.py -v
- pytest tests/backend/ -v (full suite)
- git status (confirm terms-and-privacy-policy no longer shows)

Do NOT modify any .py files in src/backend/.
Do NOT deploy.
Do NOT run terraform.

Return: files created/modified, test results, git status output.
```

---

## 11. Commit Command (After Approval)

```bash
git add tests/backend/test_r7n_acceptance_validation.py tests/backend/test_r7e_intake_selected_dates.py .gitignore
git commit -m "test: Release 7S — acceptance validation tests, intake selected_dates tests, gitignore cleanup"
```
