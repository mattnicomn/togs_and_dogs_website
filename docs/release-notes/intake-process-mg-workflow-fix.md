# Release Notes: Intake Process M&G Workflow Fix

## Issue
Clicking "Process" on a new request (e.g., in `PROFILE_CREATED` status) from the Intake Queue would immediately open the "Approve Booking" modal and default to an `APPROVE` action. If the workflow required a Meet & Greet, this caused the backend to appropriately reject the action, but forced the admin into a confusing UI loop.

## Root Cause
The "Process" button in `MasterScheduler.jsx` was hardcoded to trigger a decision modal with `type: 'APPROVE'`, bypassing the status-aware workflow routing.

## UI Correction
- Converted the `APPROVE` modal into a dynamic `WORKFLOW_REVIEW` modal.
- The modal now parses the request's current state and presents the exact same buttons as the List view's action dropdown.
- For `PROFILE_CREATED`, admins can now correctly choose "Require Meet & Greet" or "Quote Needed".
- For `MEET_GREET_REQUIRED`, the primary action is safely presented as "Mark M&G Complete".
- Successful actions automatically close the modal, clear any previous errors, and trigger a dashboard refresh.

## Backend Guardrail Status
- **Unchanged and Active.** The backend `review_handler.py` continues to block any direct `APPROVE` attempts if the workflow mandates an unresolved Meet & Greet.

## Validation Matrix
- [x] `PROFILE_CREATED` + Process opens a multi-option action panel instead of defaulting to Approve.
- [x] `PROFILE_CREATED` can move to `MEET_GREET_REQUIRED`.
- [x] `MEET_GREET_REQUIRED` clearly shows "Mark M&G Complete".
- [x] "Mark M&G Complete" succeeds without triggering approval errors.
- [x] `MG_COMPLETED` properly exposes the path to `QUOTE_NEEDED` or `APPROVED`.
- [x] Successful actions immediately dismiss stale error messages.

## Deployment Details
- **Production URL:** [https://toganddogs.usmissionhero.com/admin](https://toganddogs.usmissionhero.com/admin)
- **Commit Hash:** [to be populated]
- **CloudFront Invalidation ID:** `ID0K35IYP3YST8DMI889ZI4LMG`
