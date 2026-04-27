# Release Notes: Admin Bulk Trash and Restore Actions

## Issue
Admins could move individual archived visits to Trash but could not perform the same lifecycle action in bulk. This hindered efficient cleanup of large numbers of records.

## Change
Added bulk "Move selected to Trash" and "Restore selected to Active" lifecycle actions to the Admin Request List workflow controls.

### Scope
- **Admin Request List**: The bulk action toolbar now includes lifecycle transitions.
- **Trash / Deleted View**: Records moved to Trash are visible under the "Trash / Deleted" quick filter.
- **Restoration**: Records in Trash or Archived can be restored in bulk to the active "Intake Queue" (Pending Review).

### Safety Gates
- **Confirmation Required**: Bulk "Move selected to Trash" requires an explicit confirmation modal.
- **Informative Messaging**: The modal displays the count of selected records and explains that records are hidden but restorable.
- **Restoration Context**: Restoring records clearly states they will return to the Intake Queue phase.
- **Separation of Concerns**: Permanent deletion remains a separate, individual-record action protected by its own "Type DELETE" confirmation gate.

## Files Changed
- `web/src/components/AdminDashboard.jsx`: 
    - Added new lifecycle options to the bulk actions dropdown.
    - Enhanced the bulk confirmation modal with specific lifecycle warnings and count-based messaging.
    - Improved success notifications to describe the lifecycle action taken.

## Backend Impact
- **Frontend-only Update**: This change leverages existing backend handlers (`admin_handler.py` and `review_handler.py`) which already support the `DELETED`, `ARCHIVED`, and `PENDING_REVIEW` transitions. No Lambda updates were required.

## Deployment Details
- **Commit**: `aac71d999335520d2d312953259972302324976785`
- **Frontend Deployment**: Synced to S3 and CloudFront invalidated.
- **CloudFront Invalidation**: `I5037GGBTHWXW4FVOWY3VE5HK4` (Completed).

## Final Validation Results
- ✅ Verified bulk "Move to Trash" from Archived view.
- ✅ Verified bulk "Restore to Active" from Trash view.
- ✅ Verified confirmation modal displays correct count and warning text.
- ✅ Verified success notifications are descriptive and accurate.
- ✅ Verified no console errors or failed API requests during the workflow.
- ✅ Verified individual "Move to Trash" and "Restore" actions remain functional.
