# Release Notes: Dispatcher Timeline Status Update Fix

## Issue
Within the Admin Dashboard **DAY Dispatcher Timeline** section, selecting a visit, changing its status to a terminal state (e.g., Archived, Deleted, Completed, or Cancelled), and clicking Save did not correctly persist the status or remove the visit from the active timeline view. Additionally, the visit record card (CareCard modal) would continue showing stale data after a successful save.

## Root Cause
1.  **Filtering Logic**: The `MasterScheduler` component incorrectly included all `JOB` entities in the active timeline, regardless of their lifecycle status. It was filtering by `entity_type === 'JOB'` without excluding terminal statuses like `ARCHIVED` or `DELETED`.
2.  **UI Reconciliation**: The `AdminDashboard` state and the `CareCard` modal state were not being properly reconciled after a status update. The modal remained open with the old record data, and the parent `requests` state was not being filtered correctly upon refresh for the scheduler view.

## Correction
- **Updated `MasterScheduler` Filtering**: The active timeline now explicitly excludes visits with statuses: `ARCHIVED`, `DELETED`, `COMPLETED`, `CANCELLED`, or `DECLINED`. Case normalization ensures that mixed-case status values from the backend are handled correctly.
- **Improved State Reconciliation**: 
    - The `onReviewAction` handler in `AdminDashboard` now automatically closes the `CareCard` modal upon a successful status update, ensuring the user returns to an updated timeline/list.
    - `fetchAllData` now correctly filters out `DELETED` records (alongside `ARCHIVED`) when in the `SCHEDULER` view.
- **Enhanced Save Flow**: The `CareCard` modal now checks for status changes during the main "Save Changes" flow. If a user changes the status dropdown and clicks the primary save button, the status update is triggered alongside any pet detail changes.
- **Case Normalization**: All status comparisons and initializations are now normalized to uppercase to prevent mismatches.

## Scope
- Frontend/Admin workflow status handling.
- No changes to infrastructure, auth, APIs, data model, or AWS resources.

## Validation Performed
- Verified that changing a visit status to **Archived** removes it from the active Day Dispatcher Timeline.
- Verified that the visit appears correctly in the **Archived** list view.
- Verified that **Deleted**, **Completed**, and **Cancelled** statuses behave similarly.
- Verified that normal status transitions (e.g., Scheduled → In Progress) remain visible on the timeline.
- Verified that bulk workflow actions in the list view continue to function as expected.
- Verified that the project builds successfully (`npm run build`).

## Deployment
- Standard frontend deployment to S3/CloudFront.
- Recommend CloudFront invalidation for `/index.html` and `/assets/*` after deployment.
