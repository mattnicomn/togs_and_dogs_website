# Phase 1B.5C-D.2 Release Notes — Remove Legacy Config Protection for Admin_Root and USmissionhero

**Release Date**: July 29, 2026  
**Status**: 🛠️ **LOCAL IMPLEMENTATION / NOT DEPLOYED / AWAITING MATTHEW DEPLOYMENT APPROVAL**  
**Implementation Commit:** `1854315` (`feat(admin): remove legacy protected admin config`)  
**Scope**: Transition legacy system root accounts (`Admin_Root` / `admin@toganddogs.com` / `74b86488-1011-7029-bb6d-dad984e1463c` and `USmissionhero` / `mbn@usmissionhero.com`) out of legacy system config protection. Retain `support@usmissionhero.com` as the single permanent emergency fallback protected email.

---

### Deployment Gate

D.2 deployment requires:
1. ~~Phase 1B.5C-D.1 production validation completed by Matthew~~ — ✅ DONE (2026-07-30).
2. Matthew's explicit approval for D.2 Terraform apply, S3 sync, and CloudFront invalidation.

Saved Terraform plan: `infra/prod/phase-1b5c-d2-lambdas-only.tfplan`

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
