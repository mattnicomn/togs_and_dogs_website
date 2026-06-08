# Release 9C Plan: Google Calendar Connection Status Banner

## 1. Context & Objectives
During the Release 9B production readiness gap review, Google Calendar sync stability was identified as a critical operational dependency. While the backend handles OAuth link/unlink flows and detects revoked tokens (marking them as `revoked` in AWS Secrets Manager), this status is currently buried in a System Integrations section within the settings side-panel. 

Admins lack immediate visibility if the calendar sync is disconnected or degraded. To prevent sitters from dispatching with out-of-sync schedules, Release 9C will introduce a highly visible, global status banner on the Admin Dashboard for calendar health tracking.

---

## 2. Technical Investigation

### Current Google Calendar OAuth & Token Flow
1. **Credentials Storage**: Client secrets are stored in Secrets Manager (configured via `GOOGLE_CLIENT_CREDS_NAME`). User tokens (refresh and access tokens) are stored in `GOOGLE_USER_TOKENS_NAME`.
2. **Access Token Refresh**: The backend checks token validity locally (updated timestamp vs. expires_in). If expired, it calls `https://oauth2.googleapis.com/token` to fetch a new access token.
3. **Revocation Detection**: If the refresh token is revoked or expired, the API returns an `invalid_grant` error. The backend catches this, calls `_mark_token_revoked`, and flags the stored credentials as `token_status = 'revoked'` in Secrets Manager.
4. **Current Status API**: The endpoint `GET /admin/auth/status` (in `google_auth_handler.py`) fetches stored tokens and performs a dry-run token refresh to determine connection health, returning one of four states:
   * `CONNECTED`: Token is present and successfully refreshed.
   * `VALIDATION_FAILED`: Token is marked `revoked` or the refresh request failed.
   * `NOT_CONNECTED`: Stored tokens are empty/missing.
   * `CREDENTIALS_MISSING`: Google Client credentials are not configured in Secrets Manager.
5. **Current UI Usage**: `AdminDashboard.jsx` polls `/admin/auth/status` when loading lists (requests, sitters, clients) and updates `googleStatus`. It is only displayed in the Settings panel.

### Current Failure Modes
* **Token Expired/Revoked**: Sync operations print warnings to logs but do not halt request transitions. The UI shows a transient warning toast, but admins can easily miss it.
* **Partial Failures**: The request status updates in DynamoDB, but Google Calendar fails to sync. The user must be notified immediately that calendar sync is degraded.

---

## 3. Backend Implementation Strategy
To avoid aggressively invoking Google APIs on every dashboard refresh, we will optimize the backend status check:
* **Local Check Cache**: Read tokens from Secrets Manager first. If the token is already flagged as `revoked` or is missing, return the status immediately without calling Google.
* **Rate-Limit Guard**: Ensure the `GET /admin/auth/status` endpoint does not perform a live refresh if the access token is still cached and valid.
* **Keep Endpoint Asynchronous**: The frontend will continue to query the endpoint asynchronously so dashboard load times are not blocked by Secrets Manager or Google OAuth latency.

---

## 4. Web Admin UI/UX Plan

### Global Dashboard Banner
A persistent banner will be rendered directly below the main Header of the Admin Dashboard if `googleStatus` is in a warning or disconnected state:

1. **Needs Reconnect (`VALIDATION_FAILED`)**:
   * **Visuals**: Urgent Warning (Orange/Amber background, white text, warning icon).
   * **Message**: `"⚠️ Action Required: Google Calendar connection has expired or been revoked. Reconnect Calendar immediately to resume automated sitter schedule sync."`
   * **Action**: A primary `"Reconnect Calendar"` button that triggers `initiateGoogleAuth()`.
2. **Config Error (`CREDENTIALS_MISSING`)**:
   * **Visuals**: Danger/Error (Red background, white text, error icon).
   * **Message**: `"❌ Configuration Error: Google OAuth Client ID/Secret is missing in Secrets Manager. Contact system administrator."`
3. **Not Connected (`NOT_CONNECTED`)**:
   * **Visuals**: Informational (Soft blue or gray background).
   * **Message**: `"ℹ️ Google Calendar is not connected. Sitter schedule sync is currently inactive."`
   * **Action**: `"Connect Calendar"` button.

*Note: If `googleStatus` is `CONNECTED`, no banner is rendered, keeping the dashboard clean.*

### Status Card Polish (Settings Panel)
Enrich the existing status card in the side-panel to show:
* Last check timestamp.
* Human-readable connection guidelines.

---

## 5. Operational Readiness Procedures
* **Operational Escalate & Recovery**: If Ryan sees the `Needs Reconnect` banner, he must click the Reconnect button, select the Tog & Dogs Google account, and grant consent. Once completed, the banner should immediately disappear.
* **Readiness Checklist Update**: Add a verification step to the readiness checklist (`docs/operations/ryan-production-readiness-checklist.md`) under Section 2 to verify that connection degradation triggers the warning banner and reconnection clears it.

---

## 6. Verification & Testing Plan
1. **Automated Unit Tests**:
   * Create [tests/backend/test_r9c_google_calendar_banner.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r9c_google_calendar_banner.py).
   * Mock Secrets Manager responses to return `revoked` tokens, empty tokens, and valid tokens.
   * Verify the `/admin/auth/status` endpoint returns the correct status string and payload.
2. **Web Build Verification**:
   * Run `npm run build` in `/web` to ensure JavaScript/React compilation succeeds with the new banner layout.
3. **Manual Staging Validation**:
   * Mock a revoked token in the staging Secrets Manager environment.
   * Confirm the warning banner renders correctly on the Admin Dashboard.
   * Perform OAuth reconnect and confirm the banner clears.

---

## 7. Deployment Plan
* **Backend Deployment**: Yes (Update `google_auth_handler.py` to optimize cache checks).
* **Web Deployment**: Yes (Update `AdminDashboard.jsx` to render the global banner).
* **Terraform Changes**: None (No new routes or resources).
* **Mobile/EAS Build**: None (Mobile layout is unaffected).

---

## 8. Rollback Plan
In case of layout breakages or API Gateway degradation:
1. Revert repository commits back to `45aafb1` (Release 9B).
2. Redeploy the admin Lambda package.
3. Sync the previous web build from `dist/` to the S3 bucket.
4. Perform CloudFront cache invalidation.

---

## 9. Implementation Prompt (DO NOT RUN UNTIL MATTHEW APPROVES)
```bash
# To implement Release 9C:
# 1. Add local-check optimization to GET /admin/auth/status in src/backend/handlers/google_auth_handler.py.
# 2. Add global banner rendering logic in web/src/components/AdminDashboard.jsx directly beneath the main header component.
# 3. Write unit tests in tests/backend/test_r9c_google_calendar_banner.py.
# 4. Verify locally using pytest and npm run build.
```
