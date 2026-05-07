# Production Client Validation Account

This document defines the standard persona used for validating the Tog & Dogs Client Portal in the production environment.

## Test Account Details

- **Email/Username**: `alex@example.com`
- **Role**: `client`
- **Group Membership**: `client` (Cognito)
- **DynamoDB Profile**: Linked to `CLIENT#alex_test` in `togs-and-dogs-prod-data`

## Credential Management

> [!IMPORTANT]
> **Security Policy**
> - Do not store the password for this account in the repository, documentation, screenshots, or chat transcripts.
> - The password must be retrieved or rotated manually by an authorized operator using the AWS CLI or Cognito Console.
> - This account was rotated on 2026-05-06 following initial setup.

### Rotation Command Template
To rotate the password manually:
```bash
aws cognito-idp admin-set-user-password \
  --user-pool-id <prod-user-pool-id> \
  --username alex@example.com \
  --password <new-secure-password> \
  --permanent \
  --profile <prod-profile>
```

## Validation Persona Usage

This account is seeded with the following test records to verify the portal's lifecycle display:
1. **Pending Review**: Dog Walking (May 9)
2. **Approved**: Pet Sitting (May 11) - Verifies the "Ryan will follow up" messaging.
3. **Scheduled**: Dog Walking (May 14) - Verifies assigned staff visibility.

### Cleanup Procedure
Before handing the portal over to actual clients or the owner (Ryan) for production use, these records should be removed from DynamoDB unless they are intentionally preserved for ongoing smoke testing.

To remove test records:
```bash
aws dynamodb delete-item --table-name togs-and-dogs-prod-data --key '{"PK": {"S": "REQ#alex_req_pending"}, "SK": {"S": "CLIENT#alex_test"}}' --profile <prod-profile>
aws dynamodb delete-item --table-name togs-and-dogs-prod-data --key '{"PK": {"S": "REQ#alex_req_approved"}, "SK": {"S": "CLIENT#alex_test"}}' --profile <prod-profile>
aws dynamodb delete-item --table-name togs-and-dogs-prod-data --key '{"PK": {"S": "REQ#alex_req_scheduled"}, "SK": {"S": "CLIENT#alex_test"}}' --profile <prod-profile>
```
