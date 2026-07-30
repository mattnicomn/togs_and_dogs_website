# Phase 1B.5C-D.2 Release Notes — Remove Legacy Config Protection for Admin_Root and USmissionhero

**Release Date**: July 29, 2026  
**Status**: ✅ **VALIDATED AND CLOSED**  
**Implementation Commit:** `1854315` (`feat(admin): remove legacy protected admin config`)  
**Scope**: Transition legacy system root accounts (`Admin_Root` / `admin@toganddogs.com` / `74b86488-1011-7029-bb6d-dad984e1463c` and `USmissionhero` / `mbn@usmissionhero.com`) out of legacy system config protection. Retain `support@usmissionhero.com` as the single permanent emergency fallback protected email.  
**Validated:** 2026-07-30 (production convergence confirmed via fresh Terraform refresh + Matthew authenticated validation)

---

### Deployment Convergence

Phase 1B.5C-D.2 was not deployed through a separate D.2 Terraform apply. A fresh Terraform refresh (`phase-1b5c-d2-lambdas-only-refresh-20260730.tfplan`) confirmed that production Lambda code and environment configuration were already converged to the D.2 implementation, establishing that D.2 was included in the earlier D.1 Lambda deployment.

The original saved plan (`phase-1b5c-d2-lambdas-only.tfplan`) was never applied. The fresh refresh plan was also not applied (it contained only an unrelated budget notification drift item).

**Production convergence evidence:**
- Fresh Terraform plan showed 0 Lambda changes pending (all 13 Lambdas already at D.2 state)
- Read-only AWS verification confirmed:
  - `admin@toganddogs.com` absent from protected-admin environment configuration
  - `mbn@usmissionhero.com` absent from protected-admin environment configuration
  - Legacy protected-subject configuration absent
  - `support@usmissionhero.com` remains as intentional emergency email exception
  - Profile-level `is_platform_protected` mechanism active
  - Matthew's seeded protected-profile attribute untouched
- No separate D.2 deployment timestamp, CloudFront invalidation, or Terraform apply output exists

**What was NOT changed:**
- No frontend deployment (no frontend source changes in D.2)
- No S3 sync
- No CloudFront invalidation
- No API Gateway deployment
- No DynamoDB schema or data migration
- No Cognito modification
- No tenant, Stripe, Calendar, or mobile changes

---

### Deployment Gate (Completed)

1. ~~Phase 1B.5C-D.1 production validation completed by Matthew~~ — ✅ DONE (2026-07-30).
2. ~~Matthew's explicit approval for D.2 deployment~~ — ✅ Convergence confirmed; no separate apply required.

---

### Overview

Following the successful production seeding of data-driven protection (`is_platform_protected = true`) on Matthew’s profile (`mattnicomn10@gmail.com`), `Admin_Root` and `USmissionhero` are no longer needed as active system-protected accounts.

Phase 1B.5C-D.2 removes their legacy identifiers from backend fallback defaults (`_FALLBACK_EMAILS` and `_FALLBACK_SUBS` in `src/backend/common/protected_accounts.py`) and infrastructure environment variables (`PROTECTED_ADMIN_EMAILS` and `PROTECTED_ADMIN_SUBS` in `infra/prod/locals.tf`). Both profiles now evaluate as un-protected accounts in `GET /admin/staff`, enabling full lifecycle management (including profile protection toggling and archiving) via the Staff Management UI.

---

### Key Changes

1. **Backend Protection Common Module (`src/backend/common/protected_accounts.py`)**:
   - Removed `admin@toganddogs.com` and `mbn@usmissionhero.com` from `_FALLBACK_EMAILS`.
   - Retained `support@usmissionhero.com` as the sole emergency fallback protected email.
   - Cleared `_FALLBACK_SUBS` (`_FALLBACK_SUBS = []`).

2. **Backend Staff Handler (`src/backend/handlers/admin_handler.py`)**:
   - Refactored `protected_accounts` function imports to reference `common.protected_accounts` dynamically, ensuring test reloads and runtime env evaluation operate on live configuration state.

3. **Infrastructure Configuration (`infra/prod/locals.tf`)**:
   - Updated `PROTECTED_ADMIN_EMAILS = "support@usmissionhero.com"`.
   - Updated `PROTECTED_ADMIN_SUBS = ""`.

4. **Backend Test Suite Updates**:
   - Updated `tests/backend/test_protected_accounts.py`, `tests/backend/test_r6h_protected_config.py`, `tests/backend/test_platform_protected_admin.py`, and `tests/backend/test_r22h_orphaned_identity.py` to assert `support@usmissionhero.com` as fallback protected and confirm `Admin_Root` / `USmissionhero` are un-protected by default.

---

### Verification Summary

- **Backend Pytest Suite**: 30/30 passed 100% across protected accounts test modules.
- **Frontend Vitest Suite**: 133/133 passed 100% across 12 component test files.
- **Data & Account Safety**:
  - ❌ Zero staff profiles deleted or archived during release.
  - ❌ Zero Cognito user accounts modified, deleted, or disabled.
  - ❌ Zero AWS Budget configurations modified.


---

### Production Validation (2026-07-30)

Matthew authenticated production validation confirmed:
- ✅ Profile displayed Access: Protected (data-driven `is_platform_protected` active)
- ✅ Protected Platform Admin was checked
- ✅ Self-unprotection was blocked ("Cannot unprotect self")
- ✅ Turn Off Login Access was disabled for the protected profile
- ✅ Unlink Login was disabled for the protected profile
- ✅ Ordinary destructive staff-management actions were unavailable
- ✅ Other staff profiles were not incorrectly shown as protected
- ✅ `admin@toganddogs.com` and `mbn@usmissionhero.com` no longer act as fallback-protected addresses
- ✅ `support@usmissionhero.com` remains the approved permanent emergency exception

**Status: VALIDATED AND CLOSED**

---

### Unrelated Infrastructure Discrepancy (Not D.2)

The fresh Terraform refresh plan identified one unrelated change:
- `aws_budgets_budget.project_budget` — Terraform proposes removing two manually configured budget notifications (100% actual, 80% forecasted) that were added outside Terraform in Phase 23B.
- This change is unrelated to D.2 and was NOT applied.
- Budget notification reconciliation remains deferred pending a separately scoped review and Matthew approval.
- See: `docs/planning/phase-23b-aws-budget-coverage-and-cost-visibility-dashboard.md`
