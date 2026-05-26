# Release 6J: Postmark Production Sending Enablement + Quota Controls — Plan

## Objective
Validate that the existing Postmark production sending system is fully operational, add monthly quota awareness to prevent unexpected overage, and document the operational runbook for sustained production use.

---

## Current State Assessment

### What Is Already Implemented (From Releases 6A–6I)

| Component | Status | Notes |
|-----------|--------|-------|
| Postmark as primary provider | ✅ Live | `NOTIFICATION_PROVIDER=postmark`, `NOTIFICATION_MODE=external_provider` |
| Live delivery (not dry-run) | ✅ Live | `NOTIFICATION_DRY_RUN=false` |
| Postmark account approved | ✅ | External delivery to gmail.com confirmed |
| All 6 active templates polished | ✅ | REQUEST_RECEIVED, CUSTOMER_APPROVED, STAFF_ASSIGNED, VISIT_SCHEDULED, VISIT_CANCELLED, WELCOME_* |
| Notification Ledger (DynamoDB) | ✅ | `_write_ledger_entry()` records all outcomes |
| Webhook handler (authenticated) | ✅ | `postmark_webhook_handler.py` with secret validation |
| Webhook → suppression integration | ✅ | HardBounce/SpamComplaint → `suppress_email()` |
| Webhook → ledger update | ✅ | `_update_ledger_status()` updates NOTIF# records |
| Suppression pre-check | ✅ | `resolver.py` → `is_suppressed()` before send |
| Idempotency (CUSTOMER_APPROVED) | ✅ | `approval_notification_status` field check |
| Non-blocking fail-safe | ✅ | All notification failures caught, never propagate |
| Kill switches | ✅ | `NOTIFICATIONS_ENABLED`, `NOTIFICATION_DRY_RUN`, per-event `NOTIFY_*` flags |
| Calendar sync reliability | ✅ | Release 6G — retry, health check, all-day fallback |
| Protected admin accounts | ✅ | Release 6H — configurable via env vars |

### What Is NOT Yet Implemented

| Component | Status | Priority for 6J |
|-----------|--------|-----------------|
| Monthly quota tracking/counter | ❌ Not built | **HIGH — Primary 6J scope** |
| Quota warning thresholds (80%, 90%, 100%) | ❌ Not built | HIGH |
| Quota CloudWatch alarm | ❌ Not built | MEDIUM |
| SES deprecation documentation | ❌ Not done | LOW |
| Operational runbook for notification system | ❌ Not done | MEDIUM |

---

## Questions Answered

### 1. What is already implemented from Release 6I?
Everything in the table above. The notification system is fully operational with Postmark live delivery, ledger audit trail, webhook suppression, and authentication.

### 2. What is missing to safely send production Postmark emails?
**Nothing is missing for sending.** Postmark is already sending production emails. What's missing is:
- Quota awareness (to warn before hitting the 100/month free tier limit)
- Operational runbook (for troubleshooting and monitoring)

### 3. Which events should be enabled first?
**All events are already enabled.** Every `NOTIFY_*` flag is `"true"` in production. All templates are polished and validated.

### 4. What environment variables or Terraform variables are required?
New for quota tracking:
```hcl
NOTIFICATION_MONTHLY_QUOTA_LIMIT       = "100"
NOTIFICATION_QUOTA_WARNING_THRESHOLDS  = "80,90,100"
```
These would be added to `notification_env_vars` in `locals.tf`.

### 5. How do we prevent AG-side Terraform applies from resetting secrets?
- `POSTMARK_SERVER_TOKEN_SECRET_NAME` points to a Secrets Manager ARN (not the token itself)
- `POSTMARK_WEBHOOK_SECRET` is a Terraform variable marked `sensitive = true`, set via `TF_VAR_postmark_webhook_secret` or `terraform.tfvars` (gitignored)
- Terraform `lifecycle { ignore_changes }` on secret values prevents drift

### 6. How should quota tracking work with the notification ledger?
- Count ledger records with `status = 'sent'` and `month_key = YYYY-MM` for the current month
- OR: maintain a separate atomic counter (`PK: QUOTA#tog_and_dogs`, `SK: MONTH#2026-05`) incremented on each successful send
- **Recommendation:** Atomic counter (faster than scanning ledger, no GSI needed)

### 7. What should be the exact rollback switch if anything goes wrong?
| Scenario | Action | Effect |
|----------|--------|--------|
| Stop all sends immediately | `NOTIFICATION_DRY_RUN=true` → `terraform apply` | Logs only, no Postmark API calls |
| Disable notifications entirely | `NOTIFICATIONS_ENABLED=false` → `terraform apply` | Skip all processing |
| Disable specific event | `NOTIFY_CLIENT_ON_APPROVAL=false` (etc.) → `terraform apply` | Skips that event type |
| Redirect to test address | `NOTIFICATION_TEST_RECIPIENT_OVERRIDE=mbn@usmissionhero.com` → `terraform apply` | All sends go to test address |
| Switch provider | `NOTIFICATION_PROVIDER=log_only` → `terraform apply` | No external sends |

---

## Recommended Phases

### Phase 1: Quota Tracking + Warning (~3 hours)

**Scope:** Add monthly send counter with threshold warnings.

**Implementation:**
1. Add `NOTIFICATION_MONTHLY_QUOTA_LIMIT` and `NOTIFICATION_QUOTA_WARNING_THRESHOLDS` env vars
2. In `service.py` after a successful send (`result.get('delivered') == True`):
   - Increment atomic counter: `PK: QUOTA#tog_and_dogs`, `SK: MONTH#{YYYY-MM}`
   - DynamoDB `ADD` operation (atomic, concurrent-safe)
3. Before send (non-blocking check):
   - Read current count
   - If at/above threshold → log `NOTIFICATION_QUOTA_WARNING_{threshold}`
   - **Never block sends** — quota is informational only
4. Dry-run and disabled sends do NOT increment counter

**Kill switch interaction:**
- `DRY_RUN=true` → no counter increment
- `NOTIFICATIONS_ENABLED=false` → no counter increment
- Failed sends → no counter increment (only SENT counts)

**Tests:**
- Successful send increments counter
- Dry-run does not increment
- Disabled does not increment
- Failed send does not increment
- Threshold warnings logged at correct levels
- Counter resets implicitly on new month (new SK)
- Concurrent sends use atomic ADD

### Phase 2: Operational Runbook (~1-2 hours)

**Scope:** Create `docs/operations/notification-system-runbook.md`

**Contents:**
- How to check current month's send count
- How to check suppression list
- How to query notification ledger for a specific request/client
- How to verify Postmark connection status
- How to disable/enable notifications
- How to add/remove suppressed addresses
- CloudWatch log patterns to search
- Alarm response procedures
- Monthly quota monitoring procedure

### Phase 3: SES Deprecation (~30 min)

**Scope:** Document SES as deprecated, add code comments.

- Add deprecation header to `ses_client.py`
- Document in runbook that SES is fallback-only
- Optionally remove `SES_PRODUCTION_MODE` env var (unused)

### Phase 4: Production Smoke Test Validation (~1 hour)

**Scope:** AG validates the complete notification flow end-to-end.

- Submit intake → verify REQUEST_RECEIVED email + ledger entry
- Approve → verify CUSTOMER_APPROVED email + ledger entry
- Assign worker → verify STAFF_ASSIGNED + VISIT_SCHEDULED emails + ledger entries
- Cancel → verify VISIT_CANCELLED email + ledger entry
- Verify quota counter incremented correctly
- Verify no duplicate sends (idempotency)
- Verify suppressed address is blocked

---

## Terraform Impact

| Phase | Changes |
|-------|---------|
| Phase 1 | 2 new env vars in `locals.tf` (quota limit + thresholds) |
| Phase 2 | None (docs only) |
| Phase 3 | Optionally remove 1 unused env var |
| Phase 4 | None (validation only) |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Quota counter race condition | Very Low | Counter off by 1 | DynamoDB ADD is atomic |
| Quota warning noise | Low | Alert fatigue | Only warn at 80/90/100, not every send |
| Exceeding Postmark free tier | Medium (if volume grows) | Sends fail after 100 | Quota warning gives advance notice; upgrade plan |
| Ledger write failure | Very Low | Audit gap | Non-blocking; send still succeeds |

---

## Estimated Effort

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1: Quota tracking | ~3 hours | Very Low |
| Phase 2: Operational runbook | ~1-2 hours | None |
| Phase 3: SES deprecation | ~30 min | None |
| Phase 4: Smoke test | ~1 hour | None |
| **Total** | **~5-6 hours** | |

---

## Items Explicitly Deferred

| Item | Reason |
|------|--------|
| Postmark plan upgrade | Not needed until volume exceeds 100/month regularly |
| Notification preferences per client | Requires client portal UI |
| SMS channel | Different provider, different scope |
| `VISIT_TIME_CHANGED` template activation | No trigger exists in code |
| Ledger GSI for recipient queries | Not needed until audit queries are frequent |
| Automated quota-exceeded alerting to client | Overkill for current volume |
