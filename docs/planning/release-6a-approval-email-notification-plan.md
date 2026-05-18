# Release 6A: Client Approval Email Notification — Deployment Plan

## Summary
Enable the CUSTOMER_APPROVED email notification by implementing the missing template method. Controlled deployment with dry-run validation before live delivery.

## Current State (Pre-Deploy)
- Notification infrastructure: FULLY DEPLOYED (Postmark client, resolver, config, suppression)
- `notify_event('CUSTOMER_APPROVED', request_item)` already called in review_handler on approval
- Terraform env vars: `NOTIFICATIONS_ENABLED=true`, `NOTIFICATION_DRY_RUN=false`, `NOTIFICATION_PROVIDER=postmark`
- Missing piece: `customer_approved()` template method → causes silent AttributeError → no emails sent
- Postmark account: Test Mode (restricted to `@usmissionhero.com` recipients until approved)

## Scope
- **In scope:** `customer_approved` branded template, stub templates for other events, dry-run validation
- **Out of scope:** Notification ledger, quota tracking, webhooks, full template polish for non-approval events

## Deployment Commands

### Prerequisites
```
aws sso login --profile usmissionhero-website-prod
```

### Step 1: Plan (Dry-Run Deploy)
```
cd infra\prod
terraform plan
```
Expected: Lambda code hash updates + `NOTIFICATION_DRY_RUN` env var change (`false` → `true`). No new resources.

### Step 2: Apply
```
terraform apply -auto-approve
```

### Step 3: Validate Dry-Run
1. In admin dashboard, approve a test request (client_email = `mbn@usmissionhero.com`)
2. Check CloudWatch logs for the review Lambda
3. Look for: `NOTIFICATION_DRY_RUN_LOG` with payload containing:
   - `event_key`: `{request_id}_CUSTOMER_APPROVED_{timestamp}`
   - `recipient_domains`: `["usmissionhero.com"]`
   - `subject_preview`: `"Your Tog & Dogs Request Has B..."`
   - `mode`: `external_provider`
   - `provider`: `postmark`
   - `dry_run`: `true`
4. Confirm NO `NOTIFICATION_CRITICAL_FAILURE` entries

### Step 4: Go-Live
After dry-run validation passes:
1. Edit `infra/prod/locals.tf`:
   ```hcl
   NOTIFICATION_DRY_RUN = "false"
   ```
2. `terraform apply -auto-approve`
3. Approve another test request (client_email = `mbn@usmissionhero.com`)
4. Check inbox for branded approval email
5. Verify HTML rendering, links, content accuracy

## Rollback Plan

| Scenario | Action | Command |
|----------|--------|---------|
| Emails malformed | Set DRY_RUN=true | Edit locals.tf → `terraform apply` |
| System errors | Disable notifications | Set ENABLED=false → `terraform apply` |
| Code bug | Revert template | `git checkout HEAD~1 -- src/backend/common/notifications/templates.py` → `terraform apply` |

## Risk Assessment
- **Low risk:** Postmark is in Test Mode — cannot deliver to non-`@usmissionhero.com` addresses
- **Low risk:** Dry-run mode prevents any delivery during initial validation
- **Low risk:** Notification failures are fail-safe (never block approval workflow)
- **Medium consideration:** Stub templates will start logging (not sending) for all event types

## Template Status

| Template | Ready for Live? | Notes |
|----------|----------------|-------|
| `customer_approved` | YES | Full branded HTML, polished copy |
| `request_received` | YES (admin only) | Minimal but appropriate for internal admin alerts |
| `visit_scheduled` | NO | Placeholder — needs branded HTML before client delivery |
| `staff_assigned` | YES (staff only) | Minimal but appropriate for internal staff alerts |
| `visit_cancelled` | NO | Placeholder — needs branded HTML before client delivery |
| `visit_time_changed` | N/A | No code path triggers this event currently |

## Go-Live Gating Options
If you want to enable ONLY `customer_approved` while keeping other client-facing templates from sending:
- Option A: Set `NOTIFY_CLIENT_ON_SCHEDULED = "false"` and `NOTIFY_CLIENT_ON_CANCELLED = "false"` in locals.tf
- Option B: Polish the remaining templates before go-live
- Option C: Accept Postmark Test Mode restriction as a natural gate (only `@usmissionhero.com` can receive)
