# Request Record Data Integrity Cleanup

## Issue
Malformed request records appeared in the Request List as `--- ()` / `UNKNOWN`.

## Root Cause
Historical/test artifacts plus older permissive intake validation allowed records missing `pet_names` or status to be created in the database.

## Current Request Care status
The Request Care portal is not malfunctioning after the fix. The intake process has been hardened.

## Correction
- **Intake Validation**: Backend now requires `pet_names` for all new intake submissions.
- **Cleanup Workflow**: Missing-status or malformed records can now be moved to Trash/DELETED by an Admin or Owner.
- **Purge Guard**: Permanent purge still requires the record to be in the `DELETED` status first.
- **UI Visibility**: The Admin Dashboard now clearly labels malformed records with `⚠️ MALFORMED RECORD` to distinguish them from valid entries.

## Safety Controls
- **No Direct Purge**: Direct `PURGE` of missing-status records is prohibited; they must first move through the `DELETED` state.
- **Authorization**: Cleanup actions are restricted to Admin and Owner roles only.
- **Access Control**: Staff and Client users cannot perform or see these cleanup actions.

## Affected Records
- 2 historical/test records with missing status.
- 1 active legacy intake record missing `pet_names`.
- 3 already-DELETED legacy records missing `pet_names`.

## Recommended Cleanup
- Move the first 3 records to Trash.
- Bulk purge all 6 records only after verification that they are indeed junk, test, or legacy artifacts.

## Deployment
- **Backend/Terraform**: Verified clean and up to date.
- **Frontend**: Deployed to production.
- **CloudFront Invalidation ID**: `I8ZUMT5SR55A708HJ8ZP550AH`

## Follow-up
- Perform a valid Request Care submission test.
- Verify that submissions with missing pet names are rejected.
- Execute the final malformed record purge after administrative verification.
