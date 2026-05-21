# Operation Guide: Postmark Setup

## 1. Postmark Account Setup
1. Log in to the Postmark dashboard.
2. Verify the sender signature for `notifications@toganddogs.usmissionhero.com`.
3. Configure DKIM/SPF as recommended by Postmark.
   - **Status (2026-05-07):** VERIFIED. Records are propagated and recognized by Postmark.
4. Note the **Server API Token** from the Server Settings > API Tokens tab.
   - **Status:** Verified and stored in AWS Secrets Manager.

## 2. Account Status
- **Status (2026-05-21):** PRODUCTION APPROVED. External delivery enabled.
- **Evidence:** CloudWatch logs from 2026-05-19 confirm successful Postmark delivery to `gmail.com` recipients. A Test Mode account cannot deliver to external domains, confirming production approval.
- **Configured Sender:** `support@usmissionhero.com` (accepted by Postmark in production sends)
- **Note:** Matthew should visually confirm in the Postmark dashboard whether sender identity is domain-level `usmissionhero.com` verification or an individual sender signature for `support@usmissionhero.com`.

## 3. AWS Secrets Manager Setup
1. Create a new secret in AWS Secrets Manager.
2. Name: `togs-and-dogs-prod/postmark/server-token`.
3. Value: **Plain text token string** (Implementation supports both raw string and JSON `{"token": "..."}`).
4. Verified: Secret exists and is readable by the Lambda IAM role.

## 4. Current Production Configuration
```hcl
NOTIFICATION_PROVIDER = "postmark"
NOTIFICATION_MODE     = "external_provider"
NOTIFICATIONS_ENABLED = "true"
NOTIFICATION_DRY_RUN  = "false"
NOTIFICATION_EMAIL_FROM = "support@usmissionhero.com"
```

## 5. Troubleshooting
- **Token Fetch Failures**: Check the Lambda logs in CloudWatch for `Failed to fetch Postmark token from Secrets Manager`. Ensure the ARN matches exactly.
- **Provider Fallback**: If the provider fails, the system is designed to fail-safe and log the error without blocking the primary business workflow (Approval/Assignment).

## 6. Rollback Instructions
To halt all email delivery immediately:
1. Update `infra/prod/locals.tf`:
   ```hcl
   NOTIFICATION_DRY_RUN = "true"
   ```
2. Run `terraform apply` (requires Matthew's approval).

To return to `log_only` mode:
1. Update `infra/prod/locals.tf`:
   ```hcl
   NOTIFICATION_PROVIDER = "log_only"
   NOTIFICATION_MODE     = "log_only"
   ```
2. Run `terraform apply` (requires Matthew's approval).
