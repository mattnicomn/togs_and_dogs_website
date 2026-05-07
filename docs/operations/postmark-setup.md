# Operation Guide: Postmark Setup

## 1. Postmark Account Setup
1. Log in to the Postmark dashboard.
2. Verify the sender signature for `notifications@toganddogs.usmissionhero.com`.
3. Configure DKIM/SPF as recommended by Postmark.
   - **Status (2026-05-07):** PENDING. DKIM record `20260507131533pm._domainkey` not found in `usmissionhero.com` zone.
4. Note the **Server API Token** from the Server Settings > API Tokens tab.

## 2. AWS Secrets Manager Setup
1. Create a new secret in AWS Secrets Manager.
2. Name: `togs-and-dogs-prod/postmark/server-token`.
3. Value: **Plain text token string** (Implementation supports both raw string and JSON `{"token": "..."}`).
4. Verified: Secret exists and is readable by the Lambda IAM role.

## 3. Switching Providers
To activate Postmark in production:
1. Update `infra/prod/locals.tf`:
   ```hcl
   NOTIFICATION_PROVIDER = "postmark"
   NOTIFICATION_MODE     = "external_provider"
   ```
2. Run `terraform apply`.
3. Verify by approving a test request and checking the "Notification Details" in the admin dashboard or CloudWatch logs.

## 4. Troubleshooting
- **Token Fetch Failures**: Check the Lambda logs in CloudWatch for `Failed to fetch Postmark token from Secrets Manager`. Ensure the ARN matches exactly.
- **Provider Fallback**: If the provider fails, the system is designed to fail-safe and log the error without blocking the primary business workflow (Approval/Assignment).
