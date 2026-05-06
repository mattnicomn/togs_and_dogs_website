# SES Production Access Request Package: Tog and Dogs

## Case Tracking
- **Date Submitted**: 2026-05-05 (Planned)
- **AWS Case ID**: TBD
- **Current Status**: **Pending AWS Review**
- **Next Planned Stage**: Stage 1 (Admin-only `REQUEST_RECEIVED` notifications)

## 1. Business Use Case
Tog and Dogs is a professional pet care and dog walking business. We use AWS SES to send transactional notifications to our customers (pet owners) and staff members regarding booking requests, schedule confirmations, and service updates.

## 2. Infrastructure & Identity
- **Verified Domain**: `toganddogs.usmissionhero.com`
- **Sender Identity**: `notifications@toganddogs.usmissionhero.com`
- **Reply-To/Support**: `mbn@usmissionhero.com` (to be updated to branded support email post-sandbox).

## 3. Email Categories & Templates
All emails are transactional and triggered by specific user or administrative actions:
- **Request Received**: Confirmation to the customer that their care request has been received.
- **Customer Approved**: Notification to new customers that their onboarding/Meet & Greet is successful.
- **Visit Scheduled**: Confirmation of specific walking/sitting dates and assigned staff.
- **Staff Assigned**: Internal alert to dog walkers regarding new service assignments.
- **Cancellations**: Mutual confirmation when a service is cancelled by the business or client.

## 4. Expected Sending Volume
- **Initial Phase**: 5-10 emails per day.
- **Growth Phase**: Estimated under 50 emails per day.
- **Sandbox Compliance**: Current volume is significantly below the 200/day sandbox limit, but production access is required to reach unverified client/staff email addresses.

## 5. Recipient Source & Opt-Out
- **Source**: Recipients are exclusively registered customers who have submitted care requests via our official portal or staff members managed within our internal system.
- **Preferences**: Granular event-level notification toggles are implemented in our backend, allowing us to disable specific notification types independently.
- **Suppression**: We implement an automated suppression list. Any bounce or complaint event automatically blocks the recipient email address from all future communications.

## 6. Deliverability & Security
- **Feedback Loops**: We use an automated feedback loop (SES -> SNS -> Lambda) to process Bounces and Complaints in real-time.
- **Suppression Table**: A dedicated DynamoDB suppression table prevents re-sending to failed addresses, protecting our sender reputation.
- **Rate Controls**: We enforce application-level daily and per-minute send caps to ensure volume remains predictable and within approved limits.
- **Authentication**: We use DKIM and SPF to sign all outgoing communications from `toganddogs.usmissionhero.com`.

## 7. Previous Denial Remediation (Case: 177686512500473)
We have since addressed all previous concerns by:
- **Hardening Identity**: Fully verified the domain and sender identities.
- **Implementing Controls**: Built a robust, automated feedback and suppression system.
- **Limiting Scope**: Restricted the initial rollout to Stage 1A (verified admin notifications) only.
- **Audit Transparency**: Maintained detailed logs and audit trails for all notification events and deliverability metrics.
