# Google Calendar Re-authorization & Troubleshooting

## Objective
Restore administrative access and resolve Google Calendar integration issues, specifically addressing the `ServiceNotAllowed` error during the OAuth flow.

## Issue Description
When attempting to connect the Google Calendar via the Admin Portal, the user was redirected to `access.workspace.google.com/ServiceNotAllowed`. This prevented the OAuth flow from reaching the Google consent screen and acquiring the necessary refresh tokens.

## Root Cause Analysis
The `ServiceNotAllowed` error is specific to Google Workspace. It occurs when a user attempts to access a Google service (like Calendar or OAuth consent for Calendar) that has been explicitly disabled for their organizational unit (OU) or account by the Workspace Administrator. 

In this scenario:
1. The OAuth app configuration in Google Cloud (Client ID, Redirect URIs) was correct and functioning as expected.
2. The `mattnicomn10@gmail.com` account is a standard test account.
3. **The Root Cause:** The browser session had multiple Google accounts active. When the OAuth redirect occurred, Google automatically defaulted to a primary Workspace-managed account where Google Calendar was disabled or the OAuth scope was restricted by policy, leading to the `ServiceNotAllowed` block before the consent screen could even render for the intended test user.

## Resolution
1. **Session Isolation:** Signed out of all conflicting Google Workspace accounts in the browser.
2. **Targeted Login:** Explicitly logged into the target Google account (`mattnicomn10@gmail.com`) before initiating the flow.
3. **Re-authorization:** Initiated the "Connect Google Calendar" flow from the Tog and Dogs Admin portal.
4. **Consent:** Successfully reached the "Unverified App" warning (confirming the app is correctly in Testing mode) and granted Calendar access.
5. **Success:** The token exchange completed successfully, and the Admin portal now displays the integration as **Connected**.

## Future Prevention & Best Practices
- **Use Incognito/Clean Profiles:** When authorizing backend system integrations (like Calendar sync), always use an Incognito window or a dedicated browser profile to prevent cross-account contamination.
- **Verify the Target Account:** If you encounter `access.workspace.google.com` errors for an application intended for a standard `@gmail.com` account, immediately check the top-right profile icon to confirm which account Google is trying to authorize.
- **Testing Mode Constraints:** While the Google Cloud OAuth app remains in "Testing" mode, ensure any new accounts requiring Calendar synchronization are explicitly added to the "Test Users" list in the Google Cloud Console.

## Final Production Validation (May 2026)
A final end-to-end programmatic validation was performed to confirm Google Calendar synchronization behaves correctly across the Request lifecycle:
1. **Approval:** Workflow safely blocks approval until the required Meet & Greet is marked complete.
2. **Assignment (Create):** Assigning a scheduled time and worker correctly triggers `POST` to Google Calendar API and persists the resulting `event_id` to DynamoDB.
3. **Idempotency (Update):** Modifying the scheduled time correctly reads the existing `google_event_id` and performs a `PUT` update rather than creating duplicates.
4. **Cancellation (Delete):** Cancelling the request correctly triggers a Google API `DELETE` and cleans up the event ID from DynamoDB.

**Discovered Defects:**
- **UI State Issue:** `MG_COMPLETED` was incorrectly classified as a "Data Issue" by the Admin Dashboard, hiding valid records from the approval queue. **(Fixed in commit `fc79c49` and deployed via CloudFront)**
- **Backend Edge Case (Race Condition):** If an admin clicked "Assign" precisely at the exact millisecond after clicking "Approve", the async Job Creation Lambda (`job_handler`) might not have finished resolving the `job_id`. This could cause `assignment_handler` to create an orphaned Job record and momentarily duplicate Calendar events if the operation was repeated rapidly. This only manifests during split-second programmatic testing; the natural UI delay (polling for the Job ID) safely mitigates this for human operators.

**Status:** The Google Calendar integration is fully verified and stable for production use.

## Hardening Update (May 2026)
Following the final validation, a targeted backend hardening fix was implemented to completely mitigate the identified edge-case race condition:
1. **Idempotent Job Resolution:** The `assignment_handler` was updated to dynamically query for existing Job records via table scan if the UI invokes an assignment before the `job_id` is linked to the Request.
2. **Graceful Degradation:** If the Job is still initializing, the API now returns a clean `404 Not Found` with instructions to wait, rather than creating an orphaned record.
3. **Null Handling:** Removed an issue where `job_handler` could persist a DynamoDB `NULL` value for `google_event_id`, which previously obscured fallback lookups during calendar syncs.
