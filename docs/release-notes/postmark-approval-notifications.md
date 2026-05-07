# Release Note: Postmark Approval Notifications

## Overview
Added support for Postmark as a pluggable transactional email provider for the Tog & Dogs portal. This provides a robust alternative to AWS SES for outgoing approval and scheduling notifications.

## Key Changes
- **Pluggable Provider Architecture**: The notification system can now toggle between `log_only`, `ses`, and `postmark` via environment variables.
- **Postmark Provider Implementation**: A new native Postmark client using standard Python libraries (no external dependencies required for Lambda).
- **Secure Secret Management**: Postmark Server Tokens are managed via AWS Secrets Manager and retrieved dynamically at runtime.
- **Enhanced Metadata**: Notification audit records in DynamoDB now include the `provider` field for better observability.

## Configuration
The following environment variables control the provider:
- `NOTIFICATION_PROVIDER`: `log_only` (default), `ses`, or `postmark`.
- `POSTMARK_SERVER_TOKEN_SECRET_NAME`: ARN or name of the secret in AWS Secrets Manager.
- `POSTMARK_MESSAGE_STREAM`: The message stream ID in Postmark (default: `outbound`).

## Status (2026-05-07)
- **DNS Verification**: VERIFIED. DKIM and Return-Path are successfully propagated and verified in Postmark.
- **Account Approval**: PENDING. Account is in "Test Mode" and restricted to sending to `usmissionhero.com` until manual approval is granted.
- **Secret Configuration**: VERIFIED. Secret `togs-and-dogs-prod/postmark/server-token` is provisioned and tested.
- **Provider Setting**: Postmark is ACTIVE in production (`NOTIFICATION_PROVIDER = "postmark"`).
- **Test Result**: SUCCESS. Approval notification successfully sent via Postmark (MessageId: `1132e21d-41f1-45e4-8c8c-28fc24df3afa`).

## Rollback Instructions
To return to `log_only` mode:
1. Update `infra/prod/locals.tf`:
   ```hcl
   NOTIFICATION_PROVIDER = "log_only"
   NOTIFICATION_MODE     = "log_only"
   ```
2. Run `terraform apply`.
