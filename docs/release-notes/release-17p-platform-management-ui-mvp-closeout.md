# Release 17P: Platform Management UI MVP Implementation — Closeout

**Status:** ✅ Completed  
**Type:** Web Frontend Implementation & Deployment  
**Date:** 2026-06-21  
**Baseline:** Release 17N access bootstrap completed, frontend build compiler validated.

---

## 1. Context

This release implements the first multi-tenant Platform Management Console UI at `/platform-admin/*` routes to allow usmissionhero operators to manage registered tenants. The console interfaces with the already-deployed secure backend platform APIs.

---

## 2. Implemented Pages and Navigation

We introduced four new pages and wired them into the React Router configuration in `web/src/App.jsx`:

| Route | View Component | Description |
|---|---|---|
| `/platform-admin` | `PlatformAdmin.jsx` | Searchable grid of registered tenants displaying Display Name, Company ID, Subscription Tier, Subscription Status, and Registration Date. |
| `/platform-admin/tenants/:companyId` | `PlatformTenantDetail.jsx` | Deep-dive page showing Metadata, Entitlements summary (resolved from active tier), current usage counts (approximate Staff, Client, and Bookings metrics), Internal Platform Notes, and Edit controls. |
| `/platform-admin/audit` | `PlatformAuditLog.jsx` | Operational audit trail table showing timestamps, action events, target tenants, structured change values (from/to), and masked actor identities. |

### Access Guard & Dynamic Header

- **Frontend Route Guard**: Access to all `/platform-admin` paths is strictly checked via `PlatformAdminGuard` in `App.jsx`. It inspects Cognito groups for `platform_admin` on mount.
- **Redirection**: Unauthenticated users are redirected back to the `/admin` login page. Authorized standard tenant staff/owners are redirected to the standard `/admin` dashboard.
- **Dynamic Header link**: A bold **Platform Admin** nav link is dynamically rendered in the main navigation header *only* when the active Cognito session includes the `platform_admin` group.

---

## 3. Entitlement Edit Controls & Safety Warnings

The tenant detail page includes an **Edit Subscription** form which calls the secure `PATCH /platform/tenants/{company_id}` API:

- **Supported Fields**: Display Name, Subscription Tier, Subscription Status, Admin Override Expiration, and Internal Notes.
- **Override Integration**: Utilizes a timezone-safe HTML5 `datetime-local` input that correctly converts values to ISO UTC format (`YYYY-MM-DDTHH:MM:00Z`) or sets them to `null` if cleared.
- **Internal Notes**: Maps notes to the `notes` field in the database, preserving privacy since notes are only visible to platform admins.
- **Confirmation Diff Modal**: Displays all changed parameters in a clean from-to list before triggering the PATCH request.
- **Enforcement Warnings**: Auto-detects risky changes inside the confirmation modal:
  - *Tier Downgrades*: Displays warning about potential entitlement violations (staff/client limit overflows).
  - *Suspensions (Canceled/Disabled)*: Alerts that this action will block all tenant accounts (owners, sitters, clients) from logging in.
  - *Past Due Status*: Alerts that the tenant will enter a degraded 7-day grace period.

---

## 4. Privacy and Security Guardrails

- **Actor Masking**: The audit log table automatically masks private administrator emails (e.g. `mat***@gmail.com`) to prevent accidental leaks.
- **Restricted Access**: The Platform Admin Console has no interfaces for destructive actions (e.g. tenant deletion), direct DynamoDB editing, modifying Cognito accounts, or editing Stripe payment keys.
- **Platform Separation**: Platform admins are blocked from accessing normal `/admin` tenant bookings or private client data (address, phone, email, pets) unless they also possess tenant-level permissions.

---

## 5. Build & Compilation Results

We ran the production client build process to verify the frontend output:

- **Command**: `npm run build` in `web/`
- **Output**:
  - `dist/index.html` (1.47 kB)
  - `dist/assets/index-CntSnVuv.css` (69.70 kB)
  - `dist/assets/index-DA8qGAyA.js` (927.43 kB)
- **Result**: Compilation completed successfully with zero warnings/errors.

---

## 6. Test Results

We ran the backend test suites to ensure that no shared authentication or authorization logic was regressed:

- **Command**: `C:\Users\mattn\Desktop\lambda_package\python.exe -m pytest tests/backend/test_r17l_platform_admin.py`
- **Result**: **12/12 passed** (100% success rate, no regressions).

---

## 7. Deployment & CDN Invalidation

The compiled frontend dist assets were successfully synchronized to AWS S3, and the CloudFront cache was invalidated:

- **S3 Sync**: `aws s3 sync web/dist/ s3://togs-and-dogs-prod-toganddogs-hosting --delete` (successful, 5 uploads/deletes)
- **CloudFront Invalidation**: triggered for distribution `E35L00QPA2IRCY`
- **Invalidation ID**: `IBOU17N5FCPQ46NK73P2WUOODM` (status: `InProgress`)

---

## 8. Post-Deployment Smoke Validation

A browser subagent verified the live production site (`https://toganddogs.usmissionhero.com/`):

1. **Public Site Loads**: Verified the main portal landing loads correctly and displays "Client Portal" ✅
2. **Staff Portal Loads**: Verified `/admin` correctly loads the staff login panel ✅
3. **Route Guard and Redirection**: Verified that navigating to `/platform-admin` while unauthenticated redirects the browser to `/admin` immediately ✅

*PATCH mutations against `tog_and_dogs` production tenant metadata were intentionally skipped.* No data alterations were performed.

---

## 9. Operational Guarantees

- No tenant metadata was modified during verification ✅
- No second tenant was created ✅
- No Cognito membership modifications occurred ✅
- No Stripe Dashboard, Postmark, live key, payment, email/SMS, mobile, EAS, TestFlight, or App Store Connect changes occurred ✅

---

## 10. Files Changed

### New Files Created
- `web/src/api/platform.js` (Platform Admin API helper client)
- `web/src/components/PlatformAdmin.css` (Console styling system)
- `web/src/components/PlatformAdmin.jsx` (Console dashboard view)
- `web/src/components/PlatformTenantDetail.jsx` (Tenant detail & edit view)
- `web/src/components/PlatformAuditLog.jsx` (Audit log view)
- `docs/release-notes/release-17p-platform-management-ui-mvp-closeout.md` (this closeout note)

### Modified Files
- `web/src/api/client.js` (exported request fetch helper)
- `web/src/App.jsx` (wired router and auth header checks)
- `docs/release-notes/index.md` (added release note index entry)

---

## 11. Next Release & Defect Remediation

*   [**Release 17P-Fix1: Platform Admin UI CORS Preflight Remediation**](release-17p-fix1-platform-admin-fetch-cors-remediation.md) (2026-06-21) — Resolved data fetch preflight OPTIONS failures.
*   [**Release 17P-Fix2: Platform Admin Edit Flow Review/Confirmation Fix**](release-17p-fix2-platform-admin-edit-review-flow.md) (2026-06-21) — Refactored the edit flow into a secure, state-driven step modal with diff review and validation.

**Release 17Q:** Matthew manual platform-admin UI smoke testing and authorization validation using his `platform_admin` credentials.
