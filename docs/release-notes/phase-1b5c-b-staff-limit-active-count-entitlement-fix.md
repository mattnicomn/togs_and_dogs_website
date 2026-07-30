# Phase 1B.5C-B — Staff Limit Active-Count Entitlement Fix

**Status:** VALIDATED AND CLOSED

**Implementation Date:** 2026-07-28
**Deployment Date:** 2026-07-28 (deployed as part of Phase 1B.5C-B+C combined deployment from commit `510b063`, backend Terraform apply + S3 sync + CloudFront invalidation `IDDXHEGTSQV9QGXDJX2V03NT4P`)
**Validated:** 2026-07-30 (Matthew authenticated production validation)

---

## 1. Problem Statement

When attempting to create a new staff profile via the admin Staff Management drawer (either "Create Login & Profile" or "Create Profile Only"), the backend returns:

```json
{"error": "EntitlementDenied", "message": "Limit reached (5/5). Upgrade for more capacity.", "limit": "max_staff"}
```

**Root cause:** The `max_staff` entitlement check counts ALL staff records under `COMPANY#{company_id} / STAFF#*`, including archived/disabled records (`is_active = false`). The professional tier limit is `max_staff = 5`, and there are 5 total staff records in production.

Matthew's operational admin account (`mattnicomn10@gmail.com`) is not in the protected admin bypass list (which is reserved for root/platform accounts), so the enforcement applies.

---

## 2. Approved Product Behavior Change

**Previous behavior (Release 17C/17D):**
- Count ALL staff records (active + archived/disabled) toward `max_staff` limit.
- Rationale: "inactive staff still hold a profile record and could be reactivated."

**New behavior (Phase 1B.5C-B):**
- Count only ACTIVE staff records (`is_active != False`) toward `max_staff` limit.
- Archived/disabled staff (`is_active == False`) do not consume slots.
- Rationale: Archived profiles represent historical records, not active workforce capacity. Reactivation is a deliberate admin action.

This is a **deliberate product behavior change** approved by Matthew, not a bug fix of the original 17C/17D design intent.

---

## 3. Implementation Scope

### Backend Code Change

**File:** `src/backend/handlers/admin_handler.py`

Two locations changed (same pattern applied to both routes):

1. **POST /admin/staff** (profile-only creation, ~line 614):
   ```python
   # Before:
   check_limit(company_id, 'max_staff', len(existing_staff), context=event)
   
   # After:
   active_staff_count = len([s for s in existing_staff if s.get('is_active') != False])
   check_limit(company_id, 'max_staff', active_staff_count, context=event)
   ```

2. **POST /admin/staff/onboard** (login + profile creation, ~line 685):
   ```python
   # Before:
   check_limit(company_id, 'max_staff', len(existing_staff), context=event)
   
   # After:
   active_staff_count = len([s for s in existing_staff if s.get('is_active') != False])
   check_limit(company_id, 'max_staff', active_staff_count, context=event)
   ```

### Convention

- `is_active == False` → archived/disabled (not counted)
- `is_active == True` or `is_active` absent/None → active (counted)

This matches the established convention already used by the duplicate-name checks, the staff assignment filter, and the client-facing staff list.

---

## 4. What Was NOT Changed

- `src/backend/common/entitlement.py` — `check_limit()` remains generic
- `src/backend/common/billing.py` — `TIER_LIMITS` unchanged (`professional.max_staff = 5`)
- `src/backend/common/protected_accounts.py` — bypass list unchanged
- `infra/prod/locals.tf` — no protected email/sub additions
- `infra/prod/main.tf` — no env var changes
- Frontend — no changes
- Cognito — no changes
- DynamoDB production data — no changes

---

## 5. Tests Added

**File:** `tests/backend/test_r17d_entitlement_wiring.py`

4 new tests (Section 7: Phase 1B.5C-B):

| Test | Validates |
|------|-----------|
| `test_staff_creation_allowed_when_total_at_limit_but_active_below` | Profile-only creation succeeds when all existing staff are archived |
| `test_staff_onboard_allowed_when_total_at_limit_but_active_below` | Onboarding passes entitlement gate when existing staff are archived |
| `test_staff_creation_denied_when_active_count_at_limit` | Denial still occurs when active count reaches limit (even with archived records present) |
| `test_protected_admin_bypass_still_works_at_active_limit` | Protected admin bypass continues working at active limit |

All existing entitlement tests continue passing (the existing denial tests use `is_active: True` records, so behavior is unchanged for them).

---

## 6. Deployment Requirements

- Backend Lambda package rebuild (`backend.zip`)
- Terraform apply (0 added, 13 changed, 0 destroyed — Lambda `source_code_hash` update only)
- No API Gateway, Cognito, DynamoDB, or frontend deployment

---

## 7. Operational Note

With all 5 current production staff records still active, the limit remains 5/5 after this fix. To create a 6th staff member, Matthew must first archive at least one unused staff profile (e.g., "Staff Test User" or "USmissionhero") via the Staff Management drawer, which sets `is_active = false` and frees one slot.

---

## 8. Files Changed

- `src/backend/handlers/admin_handler.py` (Modified — 2 locations)
- `tests/backend/test_r17d_entitlement_wiring.py` (Modified — 4 new tests appended)
- `docs/release-notes/phase-1b5c-b-staff-limit-active-count-entitlement-fix.md` (New)

---

## 9. Deployment & Production Validation

**Deployed:** 2026-07-28 as part of the Phase 1B.5C-B+C combined deployment (commit `510b063`). Backend Terraform apply updated all 13 Lambda functions in-place (0 added, 13 changed, 0 destroyed). Frontend S3 sync and CloudFront invalidation (`IDDXHEGTSQV9QGXDJX2V03NT4P`) deployed the combined frontend bundle (artifact `index-FPO2J7dE.js`).

**Matthew Authenticated Production Validation (2026-07-30):**
- ✅ Platform Admin tenant usage displays Staff Users as 4 / 5
- ✅ Displayed active-staff count matches the expected active staff total
- ✅ Inactive or archived staff are not incorrectly counted toward the limit

**Status: VALIDATED AND CLOSED**
