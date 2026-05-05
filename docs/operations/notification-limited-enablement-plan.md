# Notification Limited Enablement Plan

This plan outlines a staged rollout for live notifications to ensure operational stability and branding alignment.

## Rollout Stages

### Stage 1: Admin & Operational Visibility (Current Goal)
- **Scope**: `REQUEST_RECEIVED` only.
- **Recipient**: Admin/Owner only (`mbn@usmissionhero.com`).
- **Goal**: Immediate visibility of new business leads without alerting customers.
- **Config**:
    - `NOTIFICATIONS_ENABLED = true`
    - `NOTIFICATION_DRY_RUN = false`
    - `NOTIFY_ADMIN_ON_REQUEST_RECEIVED = true`
    - `NOTIFY_CLIENT_ON_APPROVAL = false` (and all other client/staff flags = false)
    - `NOTIFICATION_TEST_RECIPIENT_OVERRIDE = ""`

### Stage 2: Customer Welcome (Branding Check)
- **Scope**: `CUSTOMER_APPROVED`.
- **Recipient**: Clients (after Ryan approves wording).
- **Goal**: Professional onboarding experience.
- **Config**:
    - `NOTIFY_CLIENT_ON_APPROVAL = true`
    - Verify with one internal "test" client first.

### Stage 3: Service Confirmation
- **Scope**: `VISIT_SCHEDULED` and `VISIT_CANCELLED`.
- **Recipient**: Clients.
- **Goal**: Automated schedule management.

### Stage 4: Staff Coordination
- **Scope**: `STAFF_ASSIGNED` and `STAFF_CANCELLED`.
- **Recipient**: Dog Walkers / Staff.
- **Goal**: Full workforce automation.

---

## Operational Procedures

### Verification Steps (Per Stage)
1. **Infrastructure**: Apply Terraform toggle for the specific stage.
2. **Logs**: Monitor CloudWatch for `NOTIFICATION_SUCCESS`.
3. **Audit**: Verify original recipients in `NOTIFICATION_OVERRIDE` logs (if override is active) or standard logs.
4. **Receipt**: Confirm arrival at the intended inbox.

### Rollback (Emergency)
In case of duplicate sends, malformed templates, or SES errors:
1. **Immediate**: Run `terraform apply` with `NOTIFICATIONS_ENABLED=false`.
2. **Alternative**: Set `NOTIFICATION_DRY_RUN=true`.

### Maintenance
- Periodically check the [SES Dashboard](https://console.aws.amazon.com/ses/home?region=us-east-1#dashboard:) for Bounce/Complaint rates.
- Ensure `NOTIFICATION_ADMIN_EMAIL` is up to date for critical alerts.
