# Release Notes: Permanent Delete Records

## Issue
Deleted records were accumulating in the "Trash / Deleted" section with no option for permanent removal. This made auditing and managing test/validation records difficult for administrators.

## Fix
Implemented a production-safe "Permanent Delete" (Purge) workflow for records already in the `DELETED` status.

### Backend Safety Enforcement (`admin_handler.py`)
- Added a `PURGE` action that explicitly executes `DynamoDB.delete_item()`.
- **Status Guard**: The backend reads the existing record and rejects the purge if the current status is anything other than `DELETED`.
- **Auth Guard**: Restricted to users with 'Staff' or 'Admin' groups, or specific authorized support emails.
- **Audit Logging**: Each purge operation is logged to CloudWatch with the operator's email and timestamp.

### Frontend Safety Gate (`AdminDashboard.jsx`)
- **Scoped Visibility**: The "Delete Permanently" action button only appears for records with status `DELETED` and is exclusively shown in the "Trash / Deleted" view.
- **Individual Purge Protection**:
    - Requires a confirmation modal.
    - Explicitly warns that the action "cannot be undone".
    - Displays the name of the record being deleted.
    - **Double Confirmation**: Requires the user to type `DELETE` into a text field to enable the final destructive button.
- **Bulk Purge Protection**:
    - Available in the "Trash / Deleted" view.
    - Shows the exact count of records to be deleted.
    - Warns that the action is irreversible.
    - Filters selection to ensure only `DELETED` records are processed by the backend.

## Files Changed
- `src/backend/handlers/admin_handler.py`: Added `PURGE` logic and safety guards.
- `web/src/api/client.js`: Added `purgeRecord` API call.
- `web/src/components/AdminDashboard.jsx`: Added UI controls, state management, and safety modals.
- `web/src/Admin.css`: Added deep crimson styling for destructive purge buttons.

## Validation Performed
- **Backend**: `py -m py_compile` passed.
- **Frontend**: `npm run build` passed.
- **Security**: Sensitive string scan confirmed no exposed credentials.
- **Browser Validation (Live Production)**:
    - Verified individual "Delete Permanently" visibility in Trash only.
    - Verified "Type DELETE to confirm" requirement for individual purge.
    - Verified successful permanent deletion of test records (removed from DB and UI).
    - Verified "Restore to Active" still works for other deleted records.
    - Verified bulk purge correctly identifies counts and removes multiple records safely.
    - Confirmed no browser console errors or failed API requests during the workflow.

## Deployment Details
- **Terraform**: Applied via commit `e80fd71`.
- **Frontend**: Built and synced to S3.
- **CloudFront**: Invalidation ID `I971EGFPV2RLCLM0O4VADQGY52` (from previous turn closeout, confirmed active).
- **Final Commit**: `e80fd71aea4d1dedddfc3ddfe158f74b82149056`

## Final Status
Feature is fully deployed and validated in production.
- Single-record purge: **Active** (with typing confirmation)
- Bulk purge: **Active** (with count confirmation)
- Backend safety: **Enforced**
