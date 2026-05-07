# Operation Guide: Postmark Setup

## 1. Postmark Account Setup
1. Log in to the Postmark dashboard.
2. Verify the sender signature for `notifications@toganddogs.usmissionhero.com`.
3. Configure DKIM/SPF as recommended by Postmark.
   - **Status (2026-05-07):** VERIFIED. Records are propagated and recognized by Postmark.
4. Note the **Server API Token** from the Server Settings > API Tokens tab.
   - **Status:** Verified and stored in AWS Secrets Manager.

## 2. Account Approval
**IMPORTANT:** The Postmark account is currently in "Test Mode" (Pending Approval).
1. Go to the Postmark Dashboard.
2. Click **"Request Approval"**.
3. Fill out the application with expected monthly volume (~100-500) and sending habits (transactional only).
4. **Restriction:** Until approved, Postmark only allows sending to addresses on the verified domain (`usmissionhero.com`).

## 3. AWS Secrets Manager Setup
1. Create a new secret in AWS Secrets Manager.
2. Name: `togs-and-dogs-prod/postmark/server-token`.
3. Value: **Plain text token string** (Implementation supports both raw string and JSON `{"token": "..."}`).
4. Verified: Secret exists and is readable by the Lambda IAM role.

## 4. Switching Providers
To activate Postmark in production:
1. Update `infra/prod/locals.tf`:
   ```hcl
   NOTIFICATION_PROVIDER = "postmark"
   NOTIFICATION_MODE     = "external_provider"
   NOTIFICATIONS_ENABLED  = "true"
   NOTIFICATION_DRY_RUN  = "false"
   ```
2. Run `terraform apply`.
3. Current Sender: `mbn@usmissionhero.com` (verified signature).
4. Verify by approving a test request and checking the "Notification Details" in the admin dashboard or CloudWatch logs.

## 5. Troubleshooting
- **Token Fetch Failures**: Check the Lambda logs in CloudWatch for `Failed to fetch Postmark token from Secrets Manager`. Ensure the ARN matches exactly.
- **Provider Fallback**: If the provider fails, the system is designed to fail-safe and log the error without blocking the primary business workflow (Approval/Assignment).
