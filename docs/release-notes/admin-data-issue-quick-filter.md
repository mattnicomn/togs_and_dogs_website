# Release Note - Admin Data Issue Quick Filter

## Purpose
Add a dedicated quick filter in the Admin Request List to help administrators identify and manage records with data integrity issues.

## Data Issue Criteria
A record is flagged as a "Data Issue" if any of the following are true:
- Missing or blank status.
- Status is set to `UNKNOWN`.
- Missing or blank Client/Customer name.
- Missing or blank Pet name(s).
- Display would default to `--- (No Client Name)`.
- Status is not in the recognized lifecycle enumeration (e.g., legacy or malformed states).

## RBAC Visibility
- **Visible to**: Admin and Owner roles only.
- **Hidden from**: Staff and Client roles.
- The filter is dynamically added to the sidebar based on the `canViewRequestList` capability.

## Safety Constraints
- **Read-Only Filter**: This is a frontend filtering enhancement only.
- **No Backend Changes**: No modifications were made to the Lambda handlers or DynamoDB.
- **Destructive Actions**: Permanent delete remains restricted to the Trash/Deleted view and only for records already in `DELETED` status.

## UI Enhancements
- New filter option: `⚠️ Data Issues`.
- Dynamic record count displayed next to the filter label.
- Explicit empty state message: `No data issue records found.`
- Retains existing `⚠️ MALFORMED RECORD` visual cues within the list rows.

## Validation Results
- `npm run build`: Passed.
- Frontend-only verification: Confirmed no backend or infrastructure drift.
- RBAC Check: Filter only appears for authorized roles.

## Deployment Details
- **Environment**: Production
- **Deployment Method**: S3 Sync & CloudFront Invalidation
- **URL**: https://toganddogs.usmissionhero.com/
