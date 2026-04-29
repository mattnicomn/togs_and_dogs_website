# Release Notes: Staff and Client Cognito Profile Reconciliation

## Issue
Administrators experienced visibility issues where valid Cognito users were missing from management portals.

## Root Cause
Queries relied on static DynamoDB entries ignoring raw identity provider memberships.

## Data Model Fixes
The endpoints `GET /admin/staff` and `GET /admin/clients` now seamlessly combine both datasets securely. 

## Tenant Boundaries
Mappings are isolated strictly under `COMPANY#tog_and_dogs` filters.

### Revised Components
- `src/backend/handlers/admin_handler.py`
- `web/src/components/AdminDashboard.jsx`

## Validation Results
Deployment matches expectations cleanly:
- **Terraform state**: Standardized Lambda properties.
- **S3 syncing**: Frontend assets uploaded completely.
- **CloudFront Cache reset**: `I7ZDYK5JEHT6Y1QC5HOCBL8KL9`

**Latest Commit**: `beb2da8`
