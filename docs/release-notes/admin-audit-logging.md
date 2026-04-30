# Request Record Admin Audit Logging

## Purpose
To provide a secure, immutable audit trail for destructive and sensitive lifecycle actions performed by administrators. This ensures accountability for record deletions, status changes, and bulk operations.

## Actions Audited
- **Move to Trash / DELETE**: Soft-delete transitions.
- **Restore**: Reverting records from `DELETED` to active states.
- **Archive**: Moving records to historical storage.
- **Cancel**: Administrative cancellation decisions.
- **Permanent Delete / PURGE**: Complete removal from DynamoDB.
- **Bulk Operations**: Tracking batch IDs for grouped lifecycle changes.
- **Review Transitions**: State changes during the administrative review workflow.

## Storage Pattern
- **Key Pattern**:
  - `PK = AUDIT#<request_id>`
  - `SK = <timestamp>#<audit_uuid>`
- **Database**: `togs-and-dogs-prod-data` (DynamoDB)

## Security and Privacy
- **Access Control**: Audit logs are only accessible to `Admin` and `Owner` roles via backend queries.
- **Least Privilege**: Staff and Client roles are blocked from accessing or viewing audit trails.
- **Data Privacy**: No secrets, auth tokens, or sensitive internal notes are stored in audit records. Metadata is limited to safe summaries (e.g., client/pet names).

## Validation Results
- **Move to Trash**: Audit record successfully created.
- **Permanent Purge**: Audit record created for successful deletions and rejected attempts (e.g., status mismatch).
- **Bulk Actions**: Verified that each record in a bulk operation generates a linked audit entry with a shared `bulk_op_id`.

## Production URL
https://toganddogs.usmissionhero.com/

## Deployment Details
- **Backend**: Deployed via Lambda update for `admin_handler`, `review_handler`, and `cancellation_handler`.
- **Infrastructure**: No new infrastructure required (single-table pattern).
