# Phase 1B.5C-D.1: Platform-Managed Protected Admin Controls & Billing Cache Hardening

**Release Date:** 2026-07-29  
**Status:** ✅ **VALIDATED AND CLOSED**  
**Implementation Commit:** `ed7a01f` (`feat(admin): add platform-managed protected admin controls`)  
**Deployment Date:** 2026-07-29 (deployment and seed performed between D.1 commit and D.2 commit)  
**Validated:** 2026-07-30 (Matthew authenticated production validation)

---

## 🛠️ Overview of Changes

This release introduces data-driven platform-managed protected admin status and hardens the billing cache expiration logic.

### 1. Platform-Managed Protected Admin Controls
- **Data-Driven Flag (`is_platform_protected`)**: Added boolean `is_platform_protected` attribute on staff profile records in DynamoDB (`COMPANY#<company_id>` / `STAFF#<staff_id>`).
- **Computed Protection (`is_protected`)**: Evaluated as `True` if `is_platform_protected === True` **OR** if the profile matches existing environment configuration / fallback system protected identifiers (`admin@toganddogs.com`, `mbn@usmissionhero.com`, `support@usmissionhero.com`, `74b86488-1011-7029-bb6d-dad984e1463c`).
- **Response Enrichment (`is_config_protected`)**: Profile responses include `is_protected`, `is_platform_protected`, and `is_config_protected` so the UI can distinguish system config locks from data-driven platform protection.
- **Backend PATCH Actions (`/admin/staff/{staff_id}`)**:
  - `set-protected`: Allows authorized callers (Owner, Platform Admin, or Protected Admin) to set `is_platform_protected = True`. Emits `SET_PROTECTED_ADMIN` audit log.
  - `unset-protected`: Allows authorized callers to set `is_platform_protected = False`. Rejects self-unprotect attempts (403 Forbidden), config-protected profiles (403 Forbidden), and unprotecting the last protected admin in the system (400 Bad Request). Emits `UNSET_PROTECTED_ADMIN` audit log.
- **Frontend Controls**:
  - Added "Protected Platform Admin" toggle control in Staff Detail Drawer (View & Edit Modes).
  - Visible/enabled for Owner or Protected Admin callers.
  - Disabled for self profile (`Cannot unprotect self`) and locked for config-protected accounts (`Locked by system config`).
  - Triggers confirmation modal before `set-protected` or `unset-protected` execution.

### 2. Billing Cache Hardening (`src/backend/common/billing.py`)
- Added `TypeError` handling to `_is_cache_expired(entitlement)` so invalid or `None` timestamp values safely return `True` (cache expired) instead of raising an unhandled 500 exception.
- Strictly bounded: No changes to tier limits, subscription status logic, entitlement enforcement rules, Stripe webhooks, pricing plans, or budget monitoring.

---

## 🔒 Protection & Data Safety Guarantees

- **No System Protection Removed**: All system config-protected accounts (`Admin_Root`, `USmissionhero`, `admin@toganddogs.com`, `support@usmissionhero.com`, `mbn@usmissionhero.com`) remain 100% protected. Attempting `unset-protected` on system config accounts is rejected with HTTP 403 Forbidden.
- **Production Seed**: Matthew's staff profile was seeded with `is_platform_protected = true` in production DynamoDB. See Deployment Reconciliation section below for evidence classification.

---

## 🧪 Test Results & Build Verification

- **Backend Unit Tests**: **56 Passed / 0 Failed** (1.41s)
  - `test_platform_protected_admin.py` (8/8 passed)
  - `test_billing_cache_hardening.py` (1/1 passed)
  - `test_protected_accounts.py` & `test_r6h_protected_config.py` (14/14 passed)
  - Entitlement test suite (`test_r17b`, `test_r17d`, `test_r17g`) (33/33 passed)
- **Frontend Component Tests**: **133 Passed / 0 Failed across 12 files** (4.13s)
  - `AdminStaffProtectedAdmin.test.jsx` (8/8 passed)
  - Full component suite (125/125 passed)
- **Production Build Artifacts (`web/dist`)**:
  - `dist/index.html` (1.47 kB)
  - `dist/assets/index-B_Bar5e4.css` (83.70 kB)
  - `dist/assets/index-Cbij9TXy.js` (1,049.99 kB)

---

## 🚀 Corrected Deployment Expectation

- **Backend Zip Hash Change**: Updating backend files (`protected_accounts.py`, `admin_handler.py`, `billing.py`) updates `backend.zip` (`data.archive_file.backend_zip.output_base64sha256`).
- **Lambda Function Impact**: In this repository (`infra/prod/main.tf`), all **13 Lambda functions** (`intake`, `admin`, `review`, `assign`, `job`, `google_auth`, `pet`, `cancellation`, `device`, `ses_feedback`, `postmark_webhook`, `stripe_webhook`, `platform`) reference `../../backend.zip`.
- **Expected Terraform Action**: **13 Lambda functions updated in-place** and API Gateway deployment stage cycle.
- **0 resources created, 0 resources destroyed**.
- **No Unrelated Infrastructure Changes**: Confirming no changes to AWS Budgets, Cognito User Pools, DynamoDB table schemas, IAM policies, S3 bucket configurations, CloudFront distribution settings, Stripe API, Google Calendar API, or mobile/EAS builds.
- **Frontend Deployment Target**:
  - S3 Hosting Bucket: `s3://togs-and-dogs-prod-toganddogs-hosting`
  - CloudFront Distribution ID: `E35L00QPA2IRCY`


---

## 📋 Deployment Reconciliation (Added 2026-07-30)

This release note was originally written before deployment. The deployment and seed were performed on 2026-07-29, but this focused release note was not updated at that time. A focused command-level deployment record was not created. The following reconciliation documents what is confirmed versus what is missing.

### Confirmed Repository Evidence

- Implementation commit `ed7a01f` is in `main` history (authored 2026-07-29 13:03 EDT).
- Local test results documented above (56 backend + 133 frontend pass).
- Phase 1B.5C-D.2 release note (committed at `1854315`, authored 2026-07-29 13:58 EDT) states: "Following the successful production seeding of data-driven protection (`is_platform_protected = true`) on Matthew's profile." This presupposes D.1 deployment and seed were completed before D.2 was committed.
- `docs/project-continuity/current-state.md` records D.1 as "DEPLOYED & SEEDED IN PRODUCTION" (present since commit `e1a62ab`, authored 2026-07-30 by Matthew).
- `docs/release-notes/index.md` records D.1 as "✅ DEPLOYED & SEEDED IN PRODUCTION" (same commit).
- Saved Terraform plans exist: `infra/prod/phase-1b5c-d1.tfplan` and `infra/prod/phase-1b5c-d1-lambdas-only.tfplan`.
- Matthew-approved project history proceeded to D.2 implementation only after the recorded seed state.

### Evidence Not Preserved in a Focused Record

- Exact Terraform apply output
- Exact resources changed and resource IDs
- Backend package hash (CodeSha256) deployed
- S3 sync output
- CloudFront invalidation ID
- Production seed command and parameters
- DynamoDB post-seed verification output
- Authenticated production validation result

### Authoritative Status Determination

Later authoritative continuity records consistently document that D.1 was deployed and that Matthew's existing staff profile was seeded with `is_platform_protected = true`. The original command-level deployment and seed evidence was not preserved in a focused deployment record, so those operational details remain documented but independently unverified.

**Reconciled Status: DEPLOYED AND SEEDED / AWAITING MATTHEW PRODUCTION VALIDATION**

---

## ✅ Matthew Production Validation Checklist

Matthew completed authenticated production validation on 2026-07-30:

1. ✅ Opened Platform Admin / Staff Management.
2. ✅ Located Matthew's staff profile.
3. ✅ Profile displayed **Access: Protected**.
4. ✅ **Protected Platform Admin** control was checked (data-driven `is_platform_protected` flag active).
5. ✅ Interface displayed "Cannot unprotect self" — self-unprotection blocked.
6. ✅ **Turn Off Login Access** was disabled for the protected profile.
7. ✅ **Unlink Login** was disabled for the protected profile.
8. ✅ Ordinary destructive staff-management controls were unavailable for the protected profile.
9. ✅ Other staff profiles were **not** incorrectly shown as protected.
10. ✅ No raw database keys, tokens, credentials, or private authentication data were exposed.

**Status: VALIDATED AND CLOSED**
