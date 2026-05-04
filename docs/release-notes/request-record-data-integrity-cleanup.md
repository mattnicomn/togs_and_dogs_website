# Request Record Data Integrity Cleanup (Updated Safety Rules)

## Issue
Malformed request records appeared in the Request List as `--- ()` / `UNKNOWN`.

## Root Cause
Historical/test artifacts plus older permissive intake validation allowed records missing `pet_names` or status to be created in the database.

## Correction
- **Intake Validation**: Backend now requires `pet_names` for all new intake submissions.
- **Two-Step Cleanup Workflow**: Malformed records must now be "Moved to Trash" before they can be permanently purged.
- **Deletion Marker**: The "Move to Trash" action now sets `status = DELETED` and a `deleted_at` timestamp marker.
- **Purge Guard**: Permanent `PURGE` is strictly restricted to records that are already in `DELETED`/`TRASH` status or have a `deleted_at` marker.
- **UI Visibility**: The Admin Dashboard clearly labels malformed records with `⚠️ DATA ISSUE: Missing Names` (including Request ID) and toggles between "Move to Trash" and "Delete Permanently" based on the record's deletion state.

## Safety Controls
- **No Direct Purge**: Direct `PURGE` of missing-status records without a deletion marker is prohibited.
- **Authorization**: Cleanup actions are restricted to Admin and Owner roles only.

## Affected Records
- Historical malformed/test records missing status or name fields.

## Recommended Cleanup
1. Identify records in the **Data Issues** view.
2. For records missing status, use the **Move to Trash** action.
3. Once moved to Trash, verify they are indeed junk artifacts and use **Delete Permanently**.

## Deployment
- **Backend/Terraform**: Verified clean and up to date.
- **Frontend**: Build verification complete.
