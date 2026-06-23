# Matthew's Production Monitoring Checklist

**Last Updated:** Release 18I  
**Audience:** Matthew / Developer / Technical Support  
**Release Type:** Documentation-only  
**Portal URL:** [https://toganddogs.usmissionhero.com](https://toganddogs.usmissionhero.com)  

---

## Purpose

This checklist gives Matthew a copy/paste-ready monitoring routine for supporting the Tog & Dogs Operations Portal while Ryan is unavailable and before broader production rollout. It consolidates exact resource names, safe inspection commands, normal-state expectations, and action thresholds into a single reference.

**Use this document for read-only observation only.** All commands below are safe inspection queries. Do not modify production data or AWS settings during routine monitoring.

---

## Key Reference

| Resource | Value |
|---|---|
| **Portal URL** | `https://toganddogs.usmissionhero.com` |
| **AWS Profile** | `usmissionhero-website-prod` |
| **DynamoDB Table** | `togs-and-dogs-prod-data` |
| **CloudWatch Log Group Pattern** | `/aws/lambda/togs-and-dogs-prod-*` |
| **Postmark Dashboard** | `https://account.postmarkapp.com/servers` |
| **Admin Notification Email** | `mbn@usmissionhero.com` |
| **Support From Email** | `support@usmissionhero.com` |

### Confirmed Lambda Function Names (from Terraform)

| Function | Purpose |
|---|---|
| `togs-and-dogs-prod-intake` | Public booking intake form handler |
| `togs-and-dogs-prod-admin` | Admin dashboard API handler |
| `togs-and-dogs-prod-review` | Booking review/approval handler |
| `togs-and-dogs-prod-assign` | Staff assignment handler |
| `togs-and-dogs-prod-job` | Multi-day job expansion handler |
| `togs-and-dogs-prod-cancellation` | Booking cancellation + calendar cleanup |
| `togs-and-dogs-prod-google-auth` | Google Calendar OAuth + daily health check |
| `togs-and-dogs-prod-postmark-webhook` | Postmark delivery webhook (bounces, spam) |
| `togs-and-dogs-prod-device` | Push notification device registration |
| `togs-and-dogs-prod-ses-feedback` | SES feedback processing (legacy fallback) |

### Calendar Health Check Schedule
- **EventBridge Rule:** `togs-and-dogs-prod-calendar-health-check`
- **Schedule:** Runs once daily
- **Target:** `togs-and-dogs-prod-google-auth` Lambda (action: `health_check`)

---

## What Normal Looks Like

When the system is healthy, you should see all of the following:

- [ ] **0 CloudWatch alarms** in `ALARM` state
- [ ] **0 unexpected Lambda errors** in the past 24 hours across all `togs-and-dogs-prod-*` functions
- [ ] **Postmark recent sends** showing `Delivered` status — no bounce or complaint spikes
- [ ] **Monthly Postmark quota** below 80% of the configured `POSTMARK_MONTHLY_LIMIT`
- [ ] **0 failed notification records** in DynamoDB (no ledger entries stuck in `failed` status)
- [ ] **0 suppression records** added for unexpected addresses
- [ ] **Google Calendar health check** completing without auth errors (check `togs-and-dogs-prod-google-auth` logs daily)
- [ ] **Portal accessible** at `https://toganddogs.usmissionhero.com` — returns 200, not 502/500

---

## Daily Quick Check (~5–10 minutes)

Run these checks each morning. All commands below are read-only and safe against production.

### 1. CloudWatch Lambda Errors (Last 24 Hours)

Open the AWS Console → CloudWatch → Log Insights, select all log groups matching `/aws/lambda/togs-and-dogs-prod-*`, and run:

```
fields @timestamp, @message
| filter @message like /ERROR/ or @message like /Unhandled error/
| sort @timestamp desc
| limit 50
```

Or via CLI (example — verify log group names in Console first):

```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/togs-and-dogs-prod-intake \
  --start-time $(date -d '24 hours ago' +%s000) \
  --filter-pattern "ERROR" \
  --profile usmissionhero-website-prod
```

**Repeat for key functions:** `togs-and-dogs-prod-admin`, `togs-and-dogs-prod-assign`, `togs-and-dogs-prod-cancellation`.

> **Normal:** 0 unhandled errors. Occasional `WARNING:` logs (e.g. notification dry-run, calendar health pings) are expected and safe.

---

### 1b. Tenant Resolution Fallbacks/Failures (Release 18D Observation)

Monitor the status of tenant resolution alarms and log metrics during the 7+ day observation window:
- Verify that `togs-and-dogs-prod-tenant-resolution-fallback` and `togs-and-dogs-prod-tenant-resolution-failed` alarms remain in the **OK** state.
- In CloudWatch Logs Insights, run this query over the Lambda logs to search for any fallback or failure occurrences:
  ```
  fields @timestamp, @message
  | filter @message like /TENANT_RESOLUTION_FALLBACK/ or @message like /TENANT_RESOLUTION_FAILED/
  | sort @timestamp desc
  | limit 10
  ```
- **Normal:** 0 results. If any fallback occurs, pause the multi-tenant migration and investigate the logs to identify the user flow lacking `custom:company_id`.

---

### 2. Google Calendar Health Check (Daily Auto-Run)

The EventBridge rule `togs-and-dogs-prod-calendar-health-check` triggers the `togs-and-dogs-prod-google-auth` Lambda once per day. Check its log group for the latest execution:

```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/togs-and-dogs-prod-google-auth \
  --start-time $(date -d '24 hours ago' +%s000) \
  --filter-pattern "health_check" \
  --profile usmissionhero-website-prod
```

> **Normal:** A completed health-check log entry with no auth errors. If you see `token_revoked`, `oauth_error`, or `refresh_failed`, Google Calendar needs reauthorization — see [google-calendar-reauthorization.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/operations/google-calendar-reauthorization.md).

---

### 3. Postmark Delivery Dashboard

Open: `https://account.postmarkapp.com/servers`

Check:
- [ ] Recent outbound messages show `Delivered`
- [ ] No new `Hard Bounce` or `Spam Complaint` entries since last check
- [ ] No messages stuck in `Queued` or `Rejected`

> **Normal:** All sends delivered. 0 hard bounces. 0 spam complaints.

---

### 4. Portal Availability Check

Open [https://toganddogs.usmissionhero.com](https://toganddogs.usmissionhero.com) in a browser:

- [ ] Public booking page loads at `/book`
- [ ] Admin dashboard loads at `/admin`
- [ ] No 502, 500, or CORS errors visible in browser dev tools

---

## Weekly Check (~20–30 minutes, suggested: Friday)

### 1. Postmark Monthly Quota Usage

Check the current month's notification send count in DynamoDB. Update the `SK` month value to the current month:

```bash
aws dynamodb get-item \
  --table-name togs-and-dogs-prod-data \
  --key '{"PK": {"S": "QUOTA#tog_and_dogs"}, "SK": {"S": "MONTH#2026-05"}}' \
  --profile usmissionhero-website-prod
```

Check CloudWatch logs for any quota threshold warnings (emitted at 80%, 90%, 100%):

```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/togs-and-dogs-prod-intake \
  --start-time $(date -d '7 days ago' +%s000) \
  --filter-pattern "NOTIFICATION_QUOTA_WARNING" \
  --profile usmissionhero-website-prod
```

> **Normal:** Monthly count well below `POSTMARK_MONTHLY_LIMIT`. No `NOTIFICATION_QUOTA_WARNING` log entries.

---

### 2. Failed Notification Records Scan

Scan DynamoDB for any notification ledger entries that failed to deliver. In the AWS Console → DynamoDB → `togs-and-dogs-prod-data` → Explore Items, filter for items where `PK` begins with `NOTIF#` and `status` equals `failed`.

Alternatively, check CloudWatch Insights across notification-related Lambdas for `failed` status entries:

```
fields @timestamp, @message
| filter @message like /NOTIFICATION_METADATA/ and @message like /failed/
| sort @timestamp desc
| limit 20
```

> **Normal:** 0 entries with `status: failed`. Status values of `sent`, `delivered`, `skipped_disabled`, or `suppressed` are all expected non-error states.

---

### 3. Suppression Record Check

Check if any new email addresses have been added to the suppression list since last week. In the AWS Console → DynamoDB → `togs-and-dogs-prod-data`, scan for items where `PK` begins with `SUPPRESSION#`.

To check a specific address:

```bash
aws dynamodb get-item \
  --table-name togs-and-dogs-prod-data \
  --key '{"PK": {"S": "SUPPRESSION#client@example.com"}, "SK": {"S": "METADATA"}}' \
  --profile usmissionhero-website-prod
```

> **Normal:** No new suppression records for legitimate, active client addresses. Suppression records for addresses that hard-bounced are expected and correct.

---

### 4. Lambda Error Trend (7-Day View)

In CloudWatch → Log Insights, run over all `/aws/lambda/togs-and-dogs-prod-*` log groups for the past 7 days:

```
fields @timestamp, @log, @message
| filter @message like /ERROR/ or @message like /Unhandled error/
| stats count(*) as error_count by bin(1d)
| sort @timestamp asc
```

> **Normal:** 0 errors per day across all functions. Any consistent daily error count warrants investigation.

---

### 5. Google Calendar Auth State (Weekly Confirmation)

Verify the daily health-check has been running cleanly for the past 7 days:

```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/togs-and-dogs-prod-google-auth \
  --start-time $(date -d '7 days ago' +%s000) \
  --filter-pattern "health_check" \
  --profile usmissionhero-website-prod
```

Also check the admin settings panel in the portal for any reconnection alert badges.

> **Normal:** 7 daily health-check invocations visible in logs, all completing without auth errors.

---

## When to Act

| Signal | Threshold | Action |
|---|---|---|
| **CloudWatch alarm fires** | Any alarm in `ALARM` state | Investigate immediately. Check the specific Lambda log group for the triggering error. See [emergency-response-checklist.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/operations/emergency-response-checklist.md). |
| **Lambda unhandled errors** | Any `Unhandled error` in a handler log | Read the full stack trace. If it's calendar-related, check Google auth. If it's DynamoDB-related, check table health. |
| **Postmark hard bounce / spam complaint** | Any new entry | Check if the address is a real client. If so, contact the client to resolve their inbox. If it's a test/junk address, no action needed. |
| **Postmark quota at 80%** | `NOTIFICATION_QUOTA_WARNING` in logs at 80% | Monitor more closely. No action yet, but plan for a limit increase if volume continues. |
| **Postmark quota at 90%** | `NOTIFICATION_QUOTA_WARNING` in logs at 90% | Evaluate whether to increase `POSTMARK_MONTHLY_LIMIT` via Terraform or reduce notification volume. |
| **Postmark quota at 100%** | Hard stop active — sends blocked | Immediate action required. Increase `POSTMARK_MONTHLY_LIMIT` via Terraform deploy or disable hard stop (`POSTMARK_QUOTA_HARD_STOP=false`). See [notification-system-runbook.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/operations/notification-system-runbook.md). |
| **Google Calendar auth error** | `token_revoked`, `oauth_error`, or `refresh_failed` in google-auth logs | Reauthorize immediately via the Settings panel in the portal. See [google-calendar-reauthorization.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/operations/google-calendar-reauthorization.md). |
| **Failed notification records > 0** | Any `status: failed` in the ledger | Review the notification log entry. If it's a transient failure, re-approval of the booking may re-trigger. If persistent, investigate the Lambda logs for that request. |
| **Repeated Lambda errors (same handler, same day)** | 3+ errors in 24 hours from the same function | Treat as a production incident. Check log details, assess impact on real client requests, escalate if bookings are affected. |
| **Portal returns 502 / 500** | Any HTTP 5xx from the portal URL | Check API Gateway logs and the relevant handler Lambda. May indicate a deployment issue or DynamoDB connectivity problem. |

---

## Notification Kill Switches (Emergency Only)

Only use these during active incidents. These require a Terraform deploy to apply permanently, or can be set as environment variable overrides for immediate effect:

| Switch | Environment Variable | Effect |
|---|---|---|
| Stop all email sends | `NOTIFICATION_DRY_RUN=true` | Simulates success, logs entries, but no emails are dispatched |
| Disable all notifications | `NOTIFICATIONS_ENABLED=false` | Skips all notification processing entirely |
| Disable a specific event type | e.g. `NOTIFY_CLIENT_ON_APPROVAL=false` | Blocks that specific notification event only |
| Route all sends to test inbox | `NOTIFICATION_TEST_RECIPIENT_OVERRIDE=mbn@usmissionhero.com` | All emails go to this address only — protects real clients during debugging |
| Switch to log-only mode | `NOTIFICATION_PROVIDER=log_only` | No external API calls — all notification activity only logged |

See [notification-system-runbook.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/operations/notification-system-runbook.md) for full details.

---

## Do Not Do During Routine Monitoring

1. **Do NOT manually edit production DynamoDB records** during monitoring — read only. Only make data changes if an incident specifically requires it, and only after confirming the correct record.
2. **Do NOT change Terraform or AWS settings** (IAM roles, environment variables, API Gateway config) as part of a routine monitoring pass. Changes require a planned deploy.
3. **Do NOT purge real client or booking records** during monitoring. Purging is permanent and irreversible.
4. **Do NOT edit Google Calendar events directly** for active bookings. Always make scheduling changes inside the Operations Portal to prevent calendar sync drift.
5. **Do NOT toggle `NOTIFICATION_DRY_RUN` or `NOTIFICATIONS_ENABLED`** without a specific reason and awareness of the impact — toggling these stops all client and staff emails.

---

## Related Documents

| Document | Purpose |
|---|---|
| [notification-system-runbook.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/operations/notification-system-runbook.md) | Postmark quota ops, suppression management, kill switches |
| [emergency-response-checklist.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/operations/emergency-response-checklist.md) | Step-by-step incident response for outages and sync failures |
| [google-calendar-reauthorization.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/operations/google-calendar-reauthorization.md) | How to reconnect Google Calendar after token expiry |
| [admin-quick-reference.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/operations/admin-quick-reference.md) | Business operations reference for Ryan/Matthew |
| [production-smoke-test-checklist.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/validation/production-smoke-test-checklist.md) | Repeatable E2E smoke test after deployments |
