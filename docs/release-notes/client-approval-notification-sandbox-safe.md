# Release Notes: Client Approval Notification (SES Sandbox-Safe)

## Overview
Implemented a robust, sandbox-safe notification system for client approvals. This ensures that notifications are handled safely while AWS SES is still in sandbox mode, preventing accidental delivery to unverified recipients.

## Features
- **Notification Modes**: Introduced `NOTIFICATION_MODE` to control delivery behavior.
    - `log_only`: Default mode. Notifications are generated and logged to CloudWatch but no email is sent.
    - `ses_sandbox`: Sends emails only to recipients in the `SES_SANDBOX_ALLOWED_RECIPIENTS` allowlist.
    - `ses_production`: Sends emails normally through SES.
- **Duplicate Prevention**: Implemented metadata tracking on Request records to prevent duplicate approval notifications for the same record.
- **Admin Feedback**: The Admin Dashboard now displays specific feedback from the notification system (e.g., "Email sent", "Email skipped", "Notification logged").
- **Custom Templates**: Updated approval email templates with the requested "Requested date/time" and follow-up messaging.

## Technical Details
- **New Metadata Fields**:
    - `approval_notification_status`: Current status of the notification (e.g., "Email sent.").
    - `approval_notification_sent_at`: Timestamp of the last successful or logged notification.
    - `approval_notification_mode`: The mode used for the last notification.
    - `approval_notification_last_message`: The specific result message from the SES client.
- **Fail-Safe Design**: Notification failures or skips do not block the status transition to `APPROVED`.

## Configuration
Added the following environment variables:
- `NOTIFICATION_MODE`: `log_only` (default) | `ses_sandbox` | `ses_production`
- `SES_SANDBOX_ALLOWED_RECIPIENTS`: Comma-separated list of verified email addresses.

## Verification
- Validated via `py_compile` for backend integrity.
- Validated via `npm run build` for frontend integrity.
- Manual verification paths established for all delivery modes.
