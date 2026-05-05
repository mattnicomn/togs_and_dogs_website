# Release Note: Phase 3C Live-Readiness & Internal Test

**Status:** SES Sandbox Verified - Recipient Verification Required
**Date:** 2026-05-05

## SES Status Verification
- **Verified Domain**: `toganddogs.usmissionhero.com` (**Success**)
- **Account Status**: **SES Sandbox** (`ProductionAccessEnabled: false`)
- **Sending Status**: Enabled
- **Production Request**: A previous request for production access was **DENIED** (Case: 177686512500473).
- **Recipient Verification**: **REQUIRED**. Since the account is in Sandbox, emails can only be sent to individually verified email addresses.

## Recommended Sender Identities
- **Sender**: `notifications@toganddogs.usmissionhero.com` (Authorized via domain verification)
- **Reply-To**: `mbn@usmissionhero.com` (Requires verification to receive test replies)
- **Admin Recipient**: `mbn@usmissionhero.com` (**REQUIRES VERIFICATION** before live test)

## Test Recipient Override
A safe override mechanism is implemented via the `NOTIFICATION_TEST_RECIPIENT_OVERRIDE` environment variable.
- **Behavior**: When set, all outgoing emails (including Client and Staff notifications) are intercepted and redirected to the override address.
- **Auditability**: The original intended recipients are logged in CloudWatch logs for verification.
- **De-duplication**: The system continues to ensure only one unique email is sent to the override address per event.

## Internal Live-Test Plan
To perform a safe internal test:
1. [ ] **Verify Test Recipient**: `mbn@usmissionhero.com` must be verified in AWS SES.
2. [ ] **Apply Infrastructure Toggle**:
    - `NOTIFICATIONS_ENABLED = true`
    - `NOTIFICATION_DRY_RUN = false`
    - `NOTIFICATION_TEST_RECIPIENT_OVERRIDE = mbn@usmissionhero.com`
3. [ ] **Trigger Workflow**: Perform a workflow action (e.g., Intake submission).
4. [ ] **Verify Receipt**: Confirm the email is received at the override address.
5. [ ] **Audit Logs**: Confirm CloudWatch logs show the original intended recipients.

## Rollback Steps
If any issues occur during the live test, immediately revert to safety via Terraform:
- **Option A**: `NOTIFICATIONS_ENABLED = false`
- **Option B**: `NOTIFICATION_DRY_RUN = true`

## Remaining Blockers for Production Enablement
1. **SES Production Access**: The account must be moved out of the Sandbox to send to unverified clients/staff.
2. **Review Denial**: Investigate and resolve the reason for the previous SES production access denial.
3. **Identity Verification**: Ensure `mbn@usmissionhero.com` is verified for the internal test.
