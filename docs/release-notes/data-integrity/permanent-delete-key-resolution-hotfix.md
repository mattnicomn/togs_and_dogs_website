# Release Notes: Permanent Delete Key Resolution Hotfix

## Issue
Admins were encountering the error: `"Permanent delete failed: Record not found"` when attempting to completely remove items from the admin section. Bulk purges were operating inefficiently.

## Root Cause
1. **Dynamic Key Variations**: While parent requests used standard single-table constraints, child operations shifted partition roles.
2. **Sequential Loop Overhead**: Processing multi-row deletes sequentially at the UI level caused state drift.

## Observed DynamoDB Schema
- **Parent Requests**: `PK=REQ#{id}`, `SK=CLIENT#{id}`
- **Child Jobs**: `PK=JOB#{id}`, `SK=REQ#{id}`

## Files Changed
- [admin_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/admin_handler.py)
- [client.js](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/api/client.js)
- [AdminDashboard.jsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/AdminDashboard.jsx)

## Verification Results
- **Individual Delete**: Direct PK/SK queries, inverted key shapes, and string scans delete successfully.
- **Bulk Delete**: Consolidated array payloads clear batch requests uniformly.
- **Safety Controls Preserved**: Blocks non-DELETED items natively.

## Deployment State
- **Terraform Result**: Modified 8 related microservice paths.
- **CloudFront Cache Clearing**: Processed under `I3A7EL13ZN7LWT6Z5U4ICOC0AS` (Status: Completed).

## Checkpoint Hashes
- **Hotfix Implementation**: `2458665`
- **Release Documentation update**: `556cd00`

