# Triage & Planning — Release 22Y: Smoke Test Findings Triage

**Date:** 2026-07-11
**Type:** Planning / Triage (Read-Only)
**Status:** ✅ **TRIAGE COMPLETE / FINDING 2 LOCALLY VALIDATED AND INDEPENDENTLY REVIEWED / STAFF PASSWORD RESET STATE AWARENESS COMPLETE / NOT DEPLOYED**

---

## 🌟 Triage Summary

Matthew executed the Release 22X controlled production smoke test after the Release 22V deployment. The core workflows (Profile Editor drawer stability, Client Portal multi-day bookings, date range displays, and visit windows) passed validation. However, three specific findings require triage:
1. **Finding 1 (Protected Admin Deletion):** Admin deletion and modification expectations on platform-protected accounts.
2. **Finding 2 (Password Reset Error):** Running a password reset on certain user accounts throws a Cognito state error.
3. **Finding 3 (Google Calendar Disconnect No-op):** Disconnecting Google Calendar does not update the UI or clear the connection.

This document analyzes the root causes and recommends the implementation path.

---

## 🔍 Detailed Finding Triage

### 🛠️ Finding 1 — Protected Admin Deletion/Disable Expectations

#### Current Behavior
- **Frontend UI:** The destructive action buttons (**Turn Off Login Access**, **Delete Login Account**, **Unlink Login**, and **Delete Profile**) in `AdminDashboard.jsx` are disabled when selecting a protected platform admin or self-profile:
  ```javascript
  disabled={selectedStaffForDrawer.is_protected || isSelf(selectedStaffForDrawer)}
  ```
- **Backend Enforcement:** In `src/backend/handlers/admin_handler.py`, the backend checks `is_protected` or `is_self` for destructive actions, logging `BLOCKED_PROTECTED_ACCOUNT_ACTION` and returning a `403 Forbidden` error:
  ```python
  if action in ['disable', 'unlink', 'delete_profile', 'delete_cognito']:
      if is_protected or is_self:
          return error(403, "Action blocked: This is a protected platform account or your own account.", event)
  ```

#### Decision & Recommendation
- **Product/Security Decision:**
  - **No UI Deletion/Disable/Unlinking:** Protected admins must not be deletable, disableable, or unlinkable through the normal administrative interface.
  - **Self-Delete/Disable Blocked:** Self-deletion and self-disabling must remain aggressively blocked for all administrative users to prevent accidental lockout.
  - **Safe Profile Edits Allowed:** Non-destructive profile edits (such as updating staff display names, assignment colors, and notes) may be permitted for protected admin accounts, provided they do not affect critical login identity bindings (such as `role`, `email`, or `cognito_sub`).
  - **Break-Glass Maintenance Procedure:** Any removal, role demotion, or unlinking of a protected admin account requires an offline, documented break-glass maintenance procedure with explicit, written approval from Matthew.
- **Future Recommendation:**
  - **Break-Glass Runbook:** Create a dedicated runbook in `docs/operations/break-glass-protected-admin-removal.md` detailing the manual AWS CLI / Terraform steps to securely modify or remove a protected account in emergencies.
- **UI Improvements:**
  - The UI currently disables the buttons and shows a hover tooltip. To prevent any user confusion, we will add a small inline text banner inside the "Account Security" drawer section when a protected account is selected (e.g., `🔒 Platform Protected: Security actions are write-locked.`).
  - No destructive "Delete", "Disable", or "Unlink" buttons are visible/clickable for protected accounts. The current disabled button + tooltip pattern is verified and correct.


---

### 🛠️ Finding 2 — Password Reset Error

#### Observed Issue
Matthew clicked “Send Password Reset Email” on a user and saw:
`An error occurred (NotAuthorizedException) when calling the AdminResetUserPassword operation: User password cannot be reset in the current state.`

#### Cognito State Root Cause
- In AWS Cognito, when a user is invited/created using the `AdminCreateUser` API, their account is placed in the `FORCE_CHANGE_PASSWORD` (or `UNCONFIRMED`) state.
- Cognito's security policy **prohibits** resetting passwords for users who have not completed their initial login (i.e. they do not yet have a confirmed permanent password). Calling `AdminResetUserPassword` on these users throws `NotAuthorizedException`.
- Users in `orphaned` or `unlinked` states also cannot receive password reset emails.
- Currently, the frontend "Send Password Reset Email" button is enabled for any user as long as they are not protected or orphaned:
  ```javascript
  // L4025 in AdminDashboard.jsx
  disabled={selectedStaffForDrawer.is_protected || isSelf(selectedStaffForDrawer) || selectedStaffForDrawer.is_orphaned_identity}
  ```
  It does **not** check the `cognito_status`.

#### Recommendation
1. **Frontend Guardrail:** Disable the "Send Password Reset Email" button unless `cognito_status === 'CONFIRMED'`. Update the button title/tooltip to state:
   - *If FORCE_CHANGE_PASSWORD:* `"This user has not completed their first login. Use 'Resend Invite' or 'Set Temporary Password' instead."`
   - *If other invalid states:* `"Password reset is only available for active, confirmed logins."`
2. **Backend Guardrail:** Update `/reset-password` in `admin_handler.py` to catch `NotAuthorizedException` specifically and return a friendly, actionable error message:
   ```python
   except cognito.exceptions.NotAuthorizedException:
       return bad_request("Password reset is not available for this user's current login state. If they have not logged in yet, please use Resend Invite or Set Temporary Password.", event)
   ```

#### Bounded local frontend implementation — 2026-08-04

Matthew separately approved a frontend-only correction for Finding 2. The local candidate uses the existing `GET /admin/staff` response without changing `web/src/api/client.js` or inventing a new field. That response already carries raw `cognito_status` plus the Release 22H-derived staff `identity_state`; the actual invitation value is `linked_invited`, not `invitation_sent`.

The real AdminDashboard staff drawer now disables **Send Password Reset Email** when any existing guard applies—protected account, signed-in administrator's own account, or orphaned identity—or when `cognito_status === 'FORCE_CHANGE_PASSWORD'` or `identity_state === 'linked_invited'`. Eligible `CONFIRMED` / `linked_active` staff remain enabled. The existing explanation precedence remains protected → self → orphaned → initial-login state. A normal pending invitation explains that the user must complete initial login and points to both existing alternatives; when Resend Invite is independently disabled, the explanation names only Set Temporary Password. Resend Invite, Set Temporary Password, the reset confirmation modal, and confirmed-user `resetStaffPassword(staff_id)` dispatch remain otherwise unchanged.

Rendered coverage in `web/tests/AdminDashboardStaffPasswordReset.test.jsx` uses the real AdminDashboard staff-list and drawer path and proves:

- `FORCE_CHANGE_PASSWORD` and `linked_invited` disable normal reset;
- disabled interaction does not open the reset confirmation or dispatch `resetStaffPassword`;
- a confirmed user remains enabled and confirmation preserves the exact existing reset dispatch;
- protected, self, and orphaned guards remain disabled with their existing explanation precedence;
- Resend Invite and Set Temporary Password retain their existing behavior and exact API calls.

Local validation:

- focused password-reset state coverage: 7/7 passed;
- existing ClientDrawerEditorConsolidation rendered coverage: 38/38 passed;
- complete Vitest: 165/165 passed across 16 files;
- legacy web: 99/99 passed; 264 unique web tests passed across complete Vitest plus legacy suites;
- Vite production build: passed, 108 modules transformed; generated `index-D53dI4qG.js`, `index-bVFIMo3n.css`, and `usmh-logo-CrRnxp7-.png`;
- focused test lint: 0 errors and 0 warnings;
- AdminDashboard lint: 18 errors and 5 warnings, exactly matching the pre-change file baseline;
- candidate-introduced lint: 0 errors and 0 warnings.

The complete Vitest run retained the existing jsdom navigation notice. The build retained the existing Vite `optimizeDeps` deprecation notice and large-chunk warning. No backend, API client, Cognito, Terraform, API Gateway, production-data, deployment, mobile, tester, Ryan, Stripe, tenant, or Google Calendar action occurred. The separately proposed backend exception handling remains deferred and was not implemented. Findings 1 and 3 remain unchanged. Passing local tests and this local closeout do not authorize deployment.

Independent Kiro review returned `READY_FOR_LOCAL_RELEASE_22Y_FINDING_2_CLOSEOUT` with `STRONG_RENDERED_BEHAVIORAL_COVERAGE`. It confirmed that backend-derived `linked_invited` covers enabled Cognito users whose status is not `CONFIRMED`, including `FORCE_CHANGE_PASSWORD`, `UNCONFIRMED`, and `RESET_REQUIRED`; that the direct and derived guards, protected/self/orphaned precedence, confirmed-user flow, tooltips, neighboring actions, validation evidence, and scope boundaries are correct; and that no correction is required.

**Finding 2 local status:** **LOCALLY VALIDATED AND INDEPENDENTLY REVIEWED / STAFF PASSWORD RESET STATE AWARENESS COMPLETE / NOT DEPLOYED**

---

### 🛠️ Finding 3 — Google Calendar Disconnect No-op

#### Observed Issue
Matthew connected Google Calendar, then clicked "Disconnect". After clicking OK, nothing changed in the UI.

#### Root Causes
1. **API Gateway Deployment Omission (Primary Root Cause):**
   In `modules/api/main.tf`, the API Gateway `DELETE` method and integration for `/admin/auth/google` are defined, but they are **missing** from the `triggers` block of the `aws_api_gateway_deployment.main` resource:
   ```hcl
   # modules/api/main.tf
   resource "aws_api_gateway_deployment" "main" {
     triggers = {
       redeployment = sha1(jsonencode([
         # ... admin_auth_google resource is present, but delete methods are missing!
       ]))
     }
   }
   ```
   Because it is missing from `triggers`, the `DELETE /admin/auth/google` route was never deployed to the active `prod` stage of the API Gateway, causing CORS or HTTP 403/404 failures during the request.
2. **UI State & Refresh Omission:**
   In `AdminDashboard.jsx`, the `handleDisconnectGoogle` function calls `disconnectGoogle()` and then calls `fetchGoogleStatus()`. However:
   - The tenant profile's `calendar_provider` database field remains set to `'google'`.
   - The UI lacks a success alert and does not reset the local `googleStatus` state immediately on disconnect success.

#### Recommendation
1. **Redeploy API Gateway:** Add `aws_api_gateway_method.delete_google_auth` and `aws_api_gateway_integration.delete_google_auth_lambda` to the `triggers` block of `aws_api_gateway_deployment.main` in `modules/api/main.tf` so that Terraform redeploys the stage with the `DELETE` method.
2. **CORS Options Alignment:** Ensure all Google Auth integration methods are correctly tracked in the Gateway deployment.
3. **UI Polish:** Update `handleDisconnectGoogle` to display a success alert, and clear the local `googleStatus` state so the UI toggles the button back to "Connect Calendar".

---

## 📅 Recommended Fix Release Sequence

We propose addressing these findings in **Release 22Z**:
- **Scope:** Frontend & Terraform API Gateway fixes.
- **Frontend Changes:**
  - `AdminDashboard.jsx`: Disable "Send Password Reset Email" for non-CONFIRMED logins; add inline banner explaining protected platform admin write-lock; update `handleDisconnectGoogle` to alert on success and reset state.
- **Backend Changes:**
  - `admin_handler.py`: Catch `NotAuthorizedException` in `/reset-password` and return a friendly error message.
- **Terraform Changes:**
  - `modules/api/main.tf`: Include `aws_api_gateway_method.delete_google_auth` and `aws_api_gateway_integration.delete_google_auth_lambda` in the deployment triggers to ensure API Gateway is redeployed.
