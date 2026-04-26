# Release Notes: Dispatcher Timeline Status Update (Corrective Fix)

## Issue (Follow-up)
The initial deployment improved UI reconciliation (modal closing and timeline filtering) but did not fully resolve the underlying persistence issue for records updated from the **DAY Dispatcher Timeline**. Specifically:
1.  **Partial Persistence**: Updates to lifecycle states (e.g., Deleted, Archived) from the timeline were only updating the parent `REQUEST` record but not the linked `JOB` record seen on the timeline.
2.  **Stale UI Display**: Reopening a record immediately after save sometimes showed the old status ("Intake") because the local state wasn't reconciled instantly and background fetches were subject to eventual consistency.

## Correction (Canonical Alignment)
This follow-up fix aligns the administrative workflow to ensure high-integrity persistence across all views:

- **Direct Record Updates**: The admin workflow now uses a "canonical" update mechanism for terminal lifecycle states (ARCHIVED, DELETED, COMPLETED, CANCELLED). Instead of relying on complex cross-record lookup logic in the review handler, the UI now updates the **exact record** being viewed using its unique primary keys (`PK`/`SK`).
- **Backend Flexibility**: The `admin_handler.py` has been expanded to support direct status updates for any valid terminal state, ensuring that `JOB` records on the timeline are updated with 100% reliability.
- **Instant UI Reconciliation**: `AdminDashboard.jsx` now updates the local `requests` array immediately upon receiving a successful response from the backend. This eliminates the "stale data" flash and ensures that reopening a record shows the correct status even before the background refresh completes.
- **Enhanced CareCard Feedback**: Added a loading state and robust asynchronous handling to the `CareCard` status update flow to provide clear feedback during the persistence process.

## Validation Performed
- **Intake → Deleted**: Verified record leaves timeline and persists correctly.
- **Scheduled → Completed**: Verified record leaves timeline and persists correctly.
- **Stale State Check**: Verified that reopening a record immediately after save shows the updated status.
- **Build Verification**: `npm run build` passed successfully.

## Future Recommendation: Permanent Delete
As requested, a "Permanent Delete" capability is recommended for a future release to allow clearing the database of old records.

### Recommended Design
- **Eligibility**: Only available for records already in `DELETED` or `ARCHIVED` status.
- **Security**: Hidden behind an admin-only role check with a typed confirmation (e.g., typing "DELETE").
- **Safety**: Should show a prominent warning that the action is irreversible.
- **Retention Policy**: Recommend a 30-90 day soft-delete period before records become eligible for permanent removal.
- **Implementation**: Prefer a dedicated backend hard-delete endpoint or a periodic cleanup Lambda.

## Repository Details
- **Correction Commit Hash**: `[TO_BE_FILLED]`
- **Deployment URL**: [https://toganddogs.usmissionhero.com/admin](https://toganddogs.usmissionhero.com/admin)
- **Status**: Deployment Pending Manual Validation
