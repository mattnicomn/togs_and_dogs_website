# Release Notes: Permanent Delete Key Resolution Hotfix

## Issue
Admins were encountering the error: `"Permanent delete failed: Record not found"` when attempting to completely remove items from the admin section. Bulk purges were operating inefficiently.

## Root Cause
1. **Dynamic Key Variations**: While parent requests used standard single-table constraints, child operations shifted partition roles.
2. **Sequential Loop Overhead**: Processing multi-row deletes sequentially at the UI level caused state drift.

## Observed DynamoDB Schema
- **Parent Requests**: `PK=REQ#{id}`, `SK=CLIENT#{id}`
- **Child Jobs**: `PK=JOB#{id}`, `SK=REQ#{id}`

## Verification Results
- Fallback chains executed flawlessly.
- Bulk purges process together in lightweight arrays.

## Release Deployment
- **Terraform Target**: Production Lambda Updates
- **Sync Method**: Static Web Hosting
- **Hash State**: `2458665`
