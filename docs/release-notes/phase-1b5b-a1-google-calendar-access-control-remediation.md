# Phase 1B.5B-A.1: Google Calendar Integration Access Control Remediation

## 1. Discovered Access-Control Defect & Impact
* **Vulnerability Description**: Sitter (`staff`) and client/customer (`client`) roles had direct API access to initiate Google OAuth state generation (`GET /admin/auth/google`) and disconnect tenant-wide Google Calendar sync (`DELETE /admin/auth/google`). In addition, the frontend dashboard did not hide Connect/Reconnect buttons from sitters, allowing them to theoretically hijack or break the tenant-wide calendar connection.
* **Tenant-Wide Impact**: High. An unauthorized actor could disconnect the business-wide schedule sync, degrade dispatcher coordination, or link the tenant's schedule to an unapproved calendar.
* **Deployment Status**: **LOCAL ONLY / NOT DEPLOYED** (Remediation is completely bounded locally for evaluation).

---

## 2. Access Control Corrections

### Frontend Remediation
* **File Modified**: [AdminDashboard.jsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/AdminDashboard.jsx)
* **Capability Guard**: Added `canManageGoogleCalendarIntegration: ['owner', 'admin'].includes(role)` to the central capability definition.
* **Visibility Adjustments**:
  * Guarded the **Connect Calendar** / **Reconnect Calendar** button inside the Scheduler health banner to hide it from unauthorized roles.
  * Guarded the **Connect Calendar** action in the sidebar System Integrations card to hide it from unauthorized roles.
  * Preserved read-only visibility of calendar status (e.g. `CONNECTED`, `NOT_CONNECTED`, `VALIDATION_FAILED`) and degraded-state health warnings for `staff`.

### Backend Remediation
* **File Modified**: [google_auth_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/google_auth_handler.py)
* **API Guarding**:
  * `GET /admin/auth/google` (`initiate_auth`): Added role checks asserting that only `owner` and `admin` roles can proceed. Unauthorized calls (e.g., `staff`, `client`, `platform_admin`, `unknown`) receive a standard `403 Forbidden` response.
  * `DELETE /admin/auth/google` (`disconnect_auth`): Added identical role checks blocking unauthorized disconnect requests with `403 Forbidden`.
  * **Callback Flow Preservation**: The external OAuth callback route (`GET /admin/auth/callback`) is left interactive-role-check free since it is triggered by Google OAuth redirections without a JWT session, instead relying onsecure state tokens.
  * **Status endpoint access**: `GET /admin/auth/status` remains accessible to `staff` for read-only connectivity checks.

---

## 3. Authoritative Allowed Roles
* **Allowed Management Roles**: `owner`, `admin`
* **Denied Roles**: `staff`, `client`, `platform_admin` (intentionally blocked from tenant business routes), `unknown`.

---

## 4. Test Verification Summary

### Frontend Tests
* **New Test File**: [GoogleCalendarRBAC.test.jsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/tests/GoogleCalendarRBAC.test.jsx)
* **Scenarios Proven**:
  1. `staff` role sees calendar status and degraded health message but NOT connect button.
  2. `staff` role does not see Connect button in the integration card.
  3. `owner` role sees Reconnect button in health banner and Connect button in card.
  4. `admin` role sees Connect button when NOT_CONNECTED.
  5. Scheduler remains fully accessible to `staff`.
* **Combined Frontend Totals**: **200 passed / 0 failed**
  * Legacy Node Suite: **96 passed / 0 failed**
  * Vitest Component Suite: **104 passed / 0 failed** (including 5 new GoogleCalendarRBAC tests)
* **Vite Build**: Compiled cleanly (`built in 371ms`).
* **Lint Status**: Changed files are 100% lint-clean. Pre-existing baseline has 58 problems.

### Backend Tests
* **New Test File**: [test_google_auth_rbac.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_google_auth_rbac.py)
* **Scenarios Proven**:
  1. `staff` receives 403 from OAuth initiation.
  2. `client` receives 403 from OAuth initiation.
  3. `platform_admin` and `unknown` roles receive 403.
  4. `owner` and `admin` retain access and successfully generate state.
  5. Unauthorized disconnect calls (staff/client) receive 403.
  6. `owner` and `admin` can disconnect.
  7. Status check remains readable by `staff`.
* **Complete Pytest Suite Totals**:
  * Collected: **772**
  * Passed: **703** (700 baseline + 3 new RBAC tests)
  * Failed: **69** (Pre-existing baseline failures, 0 regressions)
  * Warnings: **108**

---

## 5. Review and Approval Gates
* [ ] **Kiro's Independent Re-Review**: Verify frontend capability propagation and backend handler role extraction.
* [ ] **Matthew's Approval**: Review local remediation documentation and test logs before authorize next deployment slice.
