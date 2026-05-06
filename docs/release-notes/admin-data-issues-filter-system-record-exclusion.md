# Release Note: Admin Data Issues Filter Hardening

## Overview
This update resolves a bug where the Admin Portal's "Data Issues" count was falsely inflated by corrupted audit logs and system metadata. These non-request records are now correctly filtered out of the Request List view.

## Changes
- **Backend**: Updated the `/admin/requests` API to only return items matching `REQ#` or `JOB#` patterns when scanning for all active records.
- **Frontend**: Implemented `isRequestLikeRecord` as a safety guardrail in the Admin Dashboard to ignore system prefixes (`AUDIT#`, `COMPANY#`, `STAFF#`, `CLIENT#`, `CONFIG#`, `PROFILE#`) during data issue classification.

## Impact
- **Data Issues Count**: Reduced from 69 to 0 (in the current production environment).
- **UI Performance**: Slight improvement in list rendering by excluding unrelated system records.
- **Data Integrity**: Corrupted `MALFORMED_AUDIT` records (1,244 items) remain in the database for future investigation but no longer pollute administrative workflows.

## Verification
- Verified via `scripts/cleanup_zombie_data_issues.py --scope visible-data-issues` (Count: 0).
- Verified backend deployment to `togs-and-dogs-prod-admin`.
- Verified frontend deployment and CloudFront invalidation.
