# SES Production Access Re-Request Package

## 1. Identity Verification Status
- **Domain Identity**: `toganddogs.usmissionhero.com`
    - Status: **SUCCESS** (Verified)
    - DKIM: **SUCCESS** (2048-bit RSA)
- **Email Identity**: `mbn@usmissionhero.com`
    - Status: **SUCCESS** (Verified)

## 2. Deliverability Configuration
- **SPF**: Configured via the domain verification process.
- **DKIM**: Active and verified for `toganddogs.usmissionhero.com`.
- **DMARC**: DMARC record exists for the root domain `usmissionhero.com`.
- **Configuration Set**: `togs-and-dogs-prod-config-set` is active and configured to track Bounces and Complaints.

## 3. Bounce and Complaint Handling
We have implemented a robust, automated feedback loop to maintain high deliverability and sender reputation:
- **Architecture**: SES → SNS Topic (`togs-and-dogs-prod-ses-feedback`) → AWS Lambda (`togs-and-dogs-prod-ses-feedback`).
- **Processing Logic**: 
    - **Permanent Bounces**: Automatically adds the recipient email to an internal suppression list in DynamoDB.
    - **Complaints**: Automatically adds the recipient email to the internal suppression list.
- **Enforcement**: The application's notification service checks the suppression list before every dispatch attempt to prevent sending to invalid or complaining addresses.

## 4. Current Application State
- **Notification Mode**: `NOTIFICATION_MODE=log_only` (Active in Production).
- **Safety Guardrails**: 
    - **Duplicate Prevention**: The system tracks notification metadata on records to prevent redundant emails for the same event.
    - **Non-Blocking Architecture**: Notification dispatch is decoupled from the main workflow; failures or skips do not block status transitions or database updates.
- **Sandbox Safety**: All notifications are currently logged only or restricted to a verified admin allowlist (`mbn@usmissionhero.com`). No emails are sent to unverified clients.

## 5. Use Case Summary
- **Type**: Transactional approval notifications.
- **Volume**: Low (Initial estimate: 10-50 emails per week).
- **Target**: Registered clients of the Tog & Dogs pet care platform.
- **Content**: Critical status updates for service requests (e.g., "Your Tog & Dogs request was approved").
- **Opt-in**: Emails are exclusively triggered by direct client actions (submitting a service request) and represent expected transactional communications. We do not send marketing, bulk, or unsolicited emails.

## 6. Recommended Re-Request Text
> We are requesting production access for AWS SES to send transactional approval notifications for our pet care platform, Tog & Dogs (toganddogs.usmissionhero.com).
>
> Our use case is strictly transactional: we notify registered clients when their pet care service requests have been reviewed and approved. These communications are expected by recipients and are only sent in response to a specific request they have submitted.
>
> We have implemented a robust deliverability and reputation management framework:
> 1. **Identity & Authentication**: Our sending domain (toganddogs.usmissionhero.com) is fully verified with DKIM (2048-bit).
> 2. **Automated Feedback Loop**: We use a dedicated Configuration Set with SNS and Lambda to automatically process Bounces and Complaints. 
> 3. **Suppression Management**: Permanent bounces and complaints are automatically added to an internal suppression list, which our application checks before every dispatch attempt to prevent repeat sends.
> 4. **Safety & Governance**: Our system includes duplicate prevention and rate governance to protect our sender reputation.
>
> We expect a low initial volume of 10-50 emails per week. We do not send marketing, bulk, or unsolicited emails.

## 7. Remaining Setup Tasks
- [ ] Final verification of DMARC `p=none` or `p=quarantine` policy for `toganddogs.usmissionhero.com` (if specifically required by AWS).
- [ ] Perform one final end-to-end test in `ses_sandbox` mode with the verified admin email to confirm feedback loop logging.
