# Phase 1B.5C-D.1: Platform-Managed Protected Admin Controls & Billing Cache Hardening

**Release Date:** 2026-07-29  
**Status:** 🛠️ **IMPLEMENTED LOCALLY / NOT DEPLOYED / NOT SEEDED**  
**Approval Gates:** Awaiting Matthew's explicit approval before commit, push, Terraform plan/apply, S3 sync, CloudFront invalidation, or DynamoDB profile seed.

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
- **Matthew's Profile Unseeded**: Matthew's staff profile (`mattnicomn10@gmail.com`) has **not** been updated or seeded in production DynamoDB. The proposed seed script remains unexecuted pending explicit approval.

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
