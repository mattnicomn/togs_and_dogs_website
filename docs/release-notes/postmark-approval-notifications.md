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
- **DNS Verification**: FAILED/PENDING. DKIM and Return-Path records were not found in the authoritative Route 53 zone `Z0503253SXZ3072RWJHV` (`usmissionhero.com`).
- **Correction Needed**: Ensure `20260507131533pm._domainkey` (TXT) and `pm-bounces` (CNAME) are added to the `website-infra-sandbox` account's Route 53 zone.
- **Secret Configuration**: VERIFIED. Secret `togs-and-dogs-prod/postmark/server-token` is provisioned as plain text and readable by the application.
- **Provider Setting**: Production remains in `log_only` mode until DNS verification is complete.
- **Backend Code**: Verified to support both plain text and JSON-wrapped secrets.
