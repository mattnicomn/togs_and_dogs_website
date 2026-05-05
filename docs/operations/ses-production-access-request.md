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
- **Preferences**: Granular event-level notification toggles are implemented in our backend, allowing us to disable specific notification types (e.g., staff assignments) independently.

## 6. Deliverability & Security
- **Bounce/Complaint Handling**: We monitor SES metrics. If bounce rates exceed healthy thresholds, we have a global kill-switch (`NOTIFICATIONS_ENABLED=false`) to halt all traffic immediately.
- **Templates**: Branded HTML and Plain-Text templates are used. No sensitive internal IDs (PII or system secrets) are exposed in the content.
- **Testing**: We have successfully completed:
    1. Dry-run validation for all core events.
    2. Controlled internal live testing using a recipient override (`mbn@usmissionhero.com`).
    3. Infrastructure rollback validation.

## 7. Previous Denial Remediation (Case: 177686512500473)
We have since:
- Fully verified the `toganddogs.usmissionhero.com` domain.
- Implemented a modular, fail-safe notification architecture.
- Established clear recipient routing logic that respects business-defined preference flags.
- Validated all templates for professional branding and clear transactional intent.
