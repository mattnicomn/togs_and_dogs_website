# Release Notes: Bulk Permanent Delete Filter Fix

## Issue
Bulk permanent delete failed in filtered Request List sections (e.g., when timeframe filters were applied) with the error:
`Bulk permanent delete failed: purgeRecordsBulk is not defined`

## Root Cause
The `purgeRecordsBulk` function was defined and exported in `web/src/api/client.js` but was missing from the import list in `web/src/components/AdminDashboard.jsx`. This caused a `ReferenceError` when the "Delete Permanently" bulk action was invoked.

## Correction
- Added `purgeRecordsBulk` to the imports in `web/src/components/AdminDashboard.jsx`.
- Verified that the backend handler in `admin_handler.py` correctly supports the `PURGE` action with a `records` array and enforces the necessary safety checks.

## Safety Constraints Preserved
- **Authorization**: Bulk permanent delete remains restricted to Admin and Owner roles only.
- **Status Guard**: Only records already in the `DELETED` status can be purged.
- **Confirmation Gate**: The existing safety confirmation modal is retained.
- **Data Integrity**: Malformed records already moved to Trash can be bulk purged only because they are now in the `DELETED` state.

## Production URL
https://toganddogs.usmissionhero.com/admin

## Deployment Details
- **Sync Command**: `aws s3 sync web/dist s3://togs-and-dogs-prod-toganddogs-hosting/ --delete --profile usmissionhero-website-prod`
- **Invalidation Command**: `aws cloudfront create-invalidation --distribution-id E35L00QPA2IRCY --paths "/*" --profile usmissionhero-website-prod`
