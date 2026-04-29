# Release Notes: Staff and Client Cognito Profile Reconciliation

## Issue
Administrators experienced visibility issues where valid Cognito users were missing from management portals.

## Root Cause
Queries relied on static DynamoDB entries ignoring raw identity provider memberships. Additionally, IAM permissions for Cognito list operations were missing for the Lambda.

## Data Model & Logic Fixes
- Added `cognito-idp:ListGroups` and `cognito-idp:ListUsersInGroup` to the Lambda execution role.
- The endpoints `GET /admin/staff` and `GET /admin/clients` now seamlessly combine both Cognito and DynamoDB datasets securely.
- UI elements in `AdminDashboard.jsx` filter assignable staff cleanly.

## Tenant Boundaries
Mappings are isolated strictly under `COMPANY#tog_and_dogs` filters.

### Revised Components
- `src/backend/handlers/admin_handler.py`
- `web/src/components/AdminDashboard.jsx`
- `modules/iam/main.tf`

## Validation Results
Deployment matches expectations cleanly:
- **Terraform state**: Standardized IAM permissions and Lambda properties.
- **S3 syncing**: Frontend assets uploaded completely.
- **CloudFront Cache reset**: `I7ZDYK5JEHT6Y1QC5HOCBL8KL9` & `IIJ7A3CQHOAY1D4GW4XIC4QP6` (Complete)

**Latest Code Commit**: `b212a19`
**Latest Docs Commit**: `d54dacd`
