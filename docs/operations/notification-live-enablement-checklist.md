# Operations: Notification Live Enablement Checklist

This checklist defines the steps required to transition the Tog and Dogs notification system from **Dry-Run** to **Live** delivery.

## Pre-Flight Requirements
- [ ] **SES Domain Verification**: Ensure `toganddogs.usmissionhero.com` is fully verified in the AWS console.
- [ ] **SES Production Access**: Confirm if the AWS account has been moved out of the SES Sandbox. If not, **all** recipient emails must be individually verified in AWS SES.
- [ ] **Sender Email**: Confirm `notifications@toganddogs.usmissionhero.com` is the desired sender address.
- [ ] **Admin Recipient**: Confirm `mbn@usmissionhero.com` is the correct destination for admin alerts.

## Enablement Procedure
Perform these steps one at a time to monitor stability.

### Step 1: Internal Live Test
1. Set `NOTIFICATION_DRY_RUN = false` in `infra/prod/locals.tf` for the **Intake Lambda ONLY** (via local override if possible, or temporary global apply).
2. Perform a test intake submission using an internal/verified email address.
3. Confirm receipt of a branded HTML email.
4. Verify link functionality and display quality.

### Step 2: Global Enablement
1. Set `NOTIFICATIONS_ENABLED = true` in `infra/prod/locals.tf`.
2. Set `NOTIFICATION_DRY_RUN = false` in `infra/prod/locals.tf`.
3. Run `terraform apply`.

### Step 3: Progressive Monitoring
1. Monitor CloudWatch logs for `SES_SEND_SUCCESS` or `SES_SEND_ERROR`.
2. Check the SES Dashboard for Bounces or Complaints.
3. Verify with a test staff member that `STAFF_ASSIGNED` alerts are received.

## Rollback Instructions
If delivery issues occur or incorrect emails are sent:
1. **Immediate Halt**: Run `terraform apply` with `NOTIFICATION_DRY_RUN = true` in `locals.tf`.
2. **Global Disable**: Set `NOTIFICATIONS_ENABLED = false` if the system is causing workflow delays (unlikely due to non-blocking design).

## Contact Information
For technical support or SES configuration changes, contact US Mission Hero Support.
