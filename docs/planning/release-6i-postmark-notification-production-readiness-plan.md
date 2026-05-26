# Release 6I: Postmark Notification Production Readiness — Plan

## Objective
Harden the existing Postmark notification delivery system for sustained production use. The system is already live — this release adds operational maturity (webhook handling, audit ledger, quota awareness) without disrupting the working `notify_event()` entrypoint.

---

## Design Principles

1. **`notify_event()` is the production API.** All existing call sites remain unchanged. No new `send_notification()` function is introduced unless explicitly documented as a wrapper.
2. **Kill switches are sacred.** `NOTIFICATIONS_ENABLED=false` disables all processing. `NOTIFICATION_DRY_RUN=true` logs only — never sends, never consumes quota.
3. **Suppression is pre-send.** The existing `resolver.py` → `suppression.py` check runs before any provider call. Webhook-based suppression adds to the same DynamoDB suppression list.
4. **Non-blocking.** Notification failures, ledger writes, and quota checks never block business workflows.
5. **Existing env var names are authoritative.** No conflicting names introduced.

---

## Current Production State

### Entrypoint
```python
# Called from review_handler, assignment_handler, cancellation_handler, intake_handler, admin_handler
notify_event(event_type, record)
```

### Flow
```
notify_event()
  → NotificationConfig() reads env vars
  → Check NOTIFICATIONS_ENABLED (if false → skip all)
  → Check DRY_RUN (if true → log only, no send, no quota)
  → Check idempotency (CUSTOMER_APPROVED only: approval_notification_status)
  → resolve_notification_recipients() → suppression check
  → Build template context → get_template()
  → get_notification_client() → PostmarkClient or SESClient
  → PostmarkClient.send_email() → DRY_RUN/ENABLED check again → live send
  → Update approval metadata (CUSTOMER_APPROVED only)
  → Log NOTIFICATION_METADATA
```

### All Notification Events (In Scope)
| Event | Template | Recipients | Status |
|-------|----------|-----------|--------|
| `REQUEST_RECEIVED` | ✅ Polished | Admin | Live |
| `CUSTOMER_APPROVED` | ✅ Polished | Client | Live (with idempotency) |
| `STAFF_ASSIGNED` | ✅ Polished | Staff | Live |
| `VISIT_SCHEDULED` | ✅ Polished | Client | Live |
| `VISIT_CANCELLED` | ✅ Polished | Client + Staff + Admin | Live (VISIT_BOOKING only) |
| `VISIT_TIME_CHANGED` | Stub | Client | Deferred (no trigger exists) |
| `WELCOME_INVITE_CLIENT` | ✅ Pre-existing | Client | Live |
| `WELCOME_INVITE_STAFF` | ✅ Pre-existing | Staff | Live |

### Existing Kill Switches
| Variable | Effect |
|----------|--------|
| `NOTIFICATIONS_ENABLED=false` | Skip ALL processing (no logs, no sends, no quota) |
| `NOTIFICATION_DRY_RUN=true` | Log template/recipient data but never call Postmark API |
| `NOTIFICATION_TEST_RECIPIENT_OVERRIDE` | Redirect all sends to a single test address |
| `NOTIFY_*` per-event flags | Disable individual event types |

### Existing Env Var Names (Authoritative — Do Not Rename)
```
NOTIFICATIONS_ENABLED
NOTIFICATION_DRY_RUN
NOTIFICATION_MODE
NOTIFICATION_PROVIDER
NOTIFICATION_EMAIL_FROM
NOTIFICATION_EMAIL_FROM_NAME
NOTIFICATION_ADMIN_EMAIL
NOTIFICATION_REPLY_TO
NOTIFICATION_PORTAL_URL
NOTIFICATION_ROUTE_MODE
NOTIFICATION_TEST_RECIPIENT_OVERRIDE
POSTMARK_SERVER_TOKEN_SECRET_NAME
POSTMARK_MESSAGE_STREAM
NOTIFY_ADMIN_ON_REQUEST_RECEIVED
NOTIFY_CLIENT_ON_APPROVAL
NOTIFY_CLIENT_ON_SCHEDULED
NOTIFY_STAFF_ON_ASSIGNMENT
NOTIFY_CLIENT_ON_CANCELLED
NOTIFY_STAFF_ON_CANCELLED
NOTIFY_ADMIN_ON_FAILED_DELIVERY
```

---

## Phase 1: Postmark Webhook Integration (~4-6 hours)

### Scope
Receive Postmark delivery event callbacks and auto-suppress bounced/complained addresses.

### Webhook Authentication
- **Requirement:** Do NOT allow unauthenticated public POSTs to suppress client/staff emails.
- **Design:** Store a webhook secret in Secrets Manager or env var (`POSTMARK_WEBHOOK_SECRET`). Postmark sends this as a custom header or the webhook URL includes a secret token path segment.
- **Validation:** Handler checks the secret before processing any payload. Invalid/missing secret → 401 Unauthorized.
- **Alternative:** Use a non-guessable URL path segment (e.g., `/webhooks/postmark/{random-token}`) as a lightweight auth mechanism. Postmark supports this pattern.

### Webhook Handler Behavior
| Postmark RecordType | Action |
|--------------------|--------|
| `Delivery` | Log `NOTIFICATION_WEBHOOK_DELIVERY` (no suppression) |
| `Bounce` (HardBounce) | Add recipient to existing suppression list (`SUPPRESSION#{email}`) |
| `Bounce` (SoftBounce) | Log only (do not suppress) |
| `SpamComplaint` | Add recipient to suppression list |
| `Open` | Log only (optional) |
| `Click` | Log only (optional) |

### Integration with Existing Suppression
- Webhook handler calls `suppress_email(email, reason)` from `common/notifications/suppression.py`
- Same DynamoDB `SUPPRESSION#{email}` / `METADATA` pattern
- Existing `is_suppressed()` check in `resolver.py` automatically blocks future sends

### Kill Switch Interaction
- Webhooks are receive-only — they don't send emails
- `NOTIFICATIONS_ENABLED` and `DRY_RUN` do not affect webhook processing (webhooks report what Postmark already sent)

### Files
- `src/backend/handlers/notification_feedback_handler.py` — update/extend for Postmark webhooks
- `infra/prod/main.tf` — webhook route (may already exist for SES feedback)
- `modules/api/main.tf` — API Gateway resource if needed

### Tests
- Authenticated webhook with valid secret → processes payload
- Unauthenticated/invalid secret → 401
- HardBounce → `suppress_email()` called
- SpamComplaint → `suppress_email()` called
- SoftBounce → logged, NOT suppressed
- Delivery → logged, NOT suppressed
- Invalid/malformed payload → 400
- Response within 5 seconds (Postmark requirement)

---

## Phase 2: Notification Ledger (Audit-Only) (~4-6 hours)

### Scope
Record every notification attempt in DynamoDB for audit/debugging. Does NOT replace existing idempotency.

### Relationship to Existing Idempotency
- **Existing:** `approval_notification_status` field on REQ records prevents duplicate CUSTOMER_APPROVED emails. This remains unchanged.
- **Ledger:** Supplements existing idempotency as an audit trail. Does NOT replace it.
- **No migration needed.** Ledger is additive — old records without ledger entries are fine.
- **Rollback:** Remove ledger writes from `service.py` → no behavior change (sends still work, idempotency still works).

### Ledger Record Schema
```
PK: NOTIF#{notification_id}
SK: REQUEST#{request_id}
Fields:
  notification_id (UUID)
  request_id
  event_type (REQUEST_RECEIVED, CUSTOMER_APPROVED, etc.)
  recipient_email (or domain only for privacy)
  status: ATTEMPTED | SENT | FAILED | SKIPPED_SUPPRESSED | SKIPPED_DISABLED | SKIPPED_DUPLICATE | BOUNCED | SPAM_COMPLAINT
  provider: postmark | ses | log_only
  provider_message_id (Postmark MessageID)
  error_message (if failed)
  company_id (from config, default: "tog_and_dogs")
  month_key (YYYY-MM for quota grouping)
  created_at (ISO 8601)
```

### company_id Handling
- Existing call sites may not provide `company_id` in the record
- Ledger uses `NotificationConfig` which doesn't have company_id
- **Solution:** Default to `"tog_and_dogs"` (single-tenant system). If `record.get('company_id')` exists, use it. Otherwise use the default.

### Status Values (Consistent Across All Components)
| Status | When Set |
|--------|----------|
| `ATTEMPTED` | Before calling Postmark API |
| `SENT` | Postmark returns success (MessageID) |
| `FAILED` | Postmark returns error |
| `SKIPPED_SUPPRESSED` | Recipient is in suppression list |
| `SKIPPED_DISABLED` | NOTIFICATIONS_ENABLED=false |
| `SKIPPED_DUPLICATE` | Idempotency check prevented re-send |
| `BOUNCED` | Webhook reports bounce |
| `SPAM_COMPLAINT` | Webhook reports spam complaint |
| `DELIVERED` | Webhook reports successful delivery |

### Where Ledger Writes Happen
- In `service.py` `notify_event()` — after determining the outcome
- Ledger write is wrapped in try/except — failure does NOT block the send or the business operation

### Kill Switch Interaction
- `NOTIFICATIONS_ENABLED=false` → ledger records `SKIPPED_DISABLED` (still writes audit)
- `NOTIFICATION_DRY_RUN=true` → ledger records `SKIPPED_DISABLED` or a dry-run marker (still writes audit)
- This means the ledger always records what happened, even in disabled/dry-run mode

### Tests
- Send succeeds → ledger records SENT with message_id
- Send fails → ledger records FAILED with error
- Suppressed recipient → ledger records SKIPPED_SUPPRESSED
- Disabled mode → ledger records SKIPPED_DISABLED
- Duplicate send → ledger records SKIPPED_DUPLICATE
- Ledger write failure → send still succeeds (non-blocking)
- company_id defaults to "tog_and_dogs" when not in record

---

## Phase 3: Monthly Quota Awareness (~2-3 hours)

### Scope
Track monthly send count and warn at thresholds. Does NOT block sends.

### Quota Definition
- **Quota counts: provider-accepted sends only** (status = SENT)
- Failed sends, skipped sends, and dry-run logs do NOT count toward quota
- This aligns with Postmark's billing model (they count accepted messages)

### Counter Design
- DynamoDB atomic counter: `PK: QUOTA#{company_id}`, `SK: MONTH#{YYYY-MM}`
- Increment via `ADD` operation (atomic, safe for concurrent Lambda executions)
- Read current count before send to check thresholds (non-blocking — if read fails, send proceeds)

### Threshold Behavior
| Threshold | Action |
|-----------|--------|
| 80% (80/100) | Log `NOTIFICATION_QUOTA_WARNING_80` |
| 90% (90/100) | Log `NOTIFICATION_QUOTA_WARNING_90` |
| 100% (100/100) | Log `NOTIFICATION_QUOTA_LIMIT_REACHED` — do NOT block send |

### Kill Switch Interaction
- `DRY_RUN=true` → no quota increment (no send happened)
- `NOTIFICATIONS_ENABLED=false` → no quota increment (no send happened)
- Quota warnings are informational — they never block sends

### Env Vars (New)
```
NOTIFICATION_MONTHLY_QUOTA_LIMIT = "100"  # Default matches Postmark free tier
NOTIFICATION_QUOTA_WARNING_THRESHOLDS = "80,90,100"
```

### Tests
- Send increments counter
- Dry-run does NOT increment counter
- Disabled does NOT increment counter
- Failed send does NOT increment counter
- Counter at 79 → no warning
- Counter at 80 → warning logged
- Counter at 100 → limit warning logged, send still proceeds
- New month → counter starts at 0
- Concurrent sends → atomic increment (no race condition)

---

## Phase 4: SES Deprecation Documentation (~1 hour)

### Scope
Document SES as deprecated. Do NOT delete code yet.

### Actions
- Add deprecation comment to `ses_client.py`
- Document in ops guide that SES is not in the active send path
- Optionally remove `SES_PRODUCTION_MODE` env var (unused)
- Keep `SES_SANDBOX_ALLOWED_RECIPIENTS` for now (referenced in config but not used by Postmark path)
- Do NOT remove `ses_client.py` — it's the fallback if Postmark is ever disabled

### Tests
- Verify `NOTIFICATION_PROVIDER=ses` still works if explicitly set (fallback path)
- Verify `NOTIFICATION_PROVIDER=postmark` is the default and active path

---

## Terraform Impact

| Phase | Changes |
|-------|---------|
| Phase 1 | Webhook route (API Gateway), Lambda permission, possibly `POSTMARK_WEBHOOK_SECRET` env var |
| Phase 2 | No Terraform changes (uses existing DynamoDB table) |
| Phase 3 | New env vars: `NOTIFICATION_MONTHLY_QUOTA_LIMIT`, `NOTIFICATION_QUOTA_WARNING_THRESHOLDS` |
| Phase 4 | Optionally remove unused SES env vars |

---

## Security Requirements

1. **Webhook authentication:** Secret-based validation before processing any webhook payload
2. **Suppression writes:** Only webhook handler and admin can add to suppression list
3. **Postmark token:** Remains in Secrets Manager, never in env vars or logs
4. **No PII in logs:** Recipient emails logged as domains only (existing behavior preserved)
5. **Quota counter:** Not security-sensitive but must be atomic to prevent race conditions

---

## Rollback Plan

| Scenario | Action |
|----------|--------|
| Webhook causing errors | Remove webhook URL from Postmark dashboard (instant, no deploy) |
| Ledger writes failing | Ledger is non-blocking — failures don't affect sends. Remove ledger code if needed. |
| Quota counter wrong | Counter is informational — doesn't block sends. Reset counter in DynamoDB. |
| Need to disable all notifications | `NOTIFICATION_DRY_RUN=true` → `terraform apply` |
| Need to switch away from Postmark | `NOTIFICATION_PROVIDER=log_only` → `terraform apply` |

---

## Validation Checklist

### Phase 1 (Webhooks)
- [x] Webhook endpoint responds to authenticated Postmark test ping
- [x] Unauthenticated request returns 401
- [x] Hard bounce auto-adds to suppression list
- [x] Spam complaint auto-adds to suppression list
- [x] Soft bounce logged but NOT suppressed
- [x] Delivery event logged
- [x] Invalid payload returns 400
- [x] Endpoint responds within 5 seconds
- [x] Suppressed email is blocked on next send attempt

#### Phase 1 Post-Apply Validation & Operations Notes
* **Route Validation & Endpoint:** The Postmark Webhook POST route is live at `/webhooks/postmark` (URL: `https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod/webhooks/postmark`). 
* **Secret Auth Enforcement:** The Lambda validates the `X-Postmark-Webhook-Secret` header case-insensitively. A strict `.strip()` comparison is performed to ignore any minor whitespace issues. If no secret is configured, the handler fails closed, rejecting all requests with `401 Unauthorized`.
* **Terraform Local Secret Deployment Correction:** Because background execution sessions lack terminal-specific environment variables like `$env:TF_VAR_postmark_webhook_secret`, running Terraform plans/applies from a local interactive PowerShell terminal is required to deploy the secret to the `POSTMARK_WEBHOOK_SECRET` environment variable of the Lambda.
* **PowerShell Testing Warning:** When testing external CLI tools like `curl.exe` in PowerShell, double quotes in variables are parsed and stripped. To send valid JSON payloads, either use native PowerShell cmdlets (`Invoke-RestMethod`) or save the JSON as a UTF-8 file (no BOM) and use `curl.exe -d "@payload.json"`.

### Phase 2 (Ledger)
- [ ] Every send attempt creates a ledger record
- [ ] Ledger records include: event_type, recipient domain, status, message_id, timestamp
- [ ] Failed sends recorded with error details
- [ ] Skipped sends (suppressed, disabled, duplicate) recorded
- [ ] Ledger writes don't block the send path
- [ ] Existing `approval_notification_status` idempotency still works
- [ ] company_id defaults safely when not provided

### Phase 3 (Quota)
- [ ] Monthly count increments on SENT only
- [ ] Dry-run/disabled/failed do NOT increment
- [ ] Warning logged at 80% threshold
- [ ] Warning logged at 90% threshold
- [ ] Limit warning at 100% — send still proceeds
- [ ] New month resets counter
- [ ] Concurrent sends don't corrupt counter

### Phase 4 (SES Cleanup)
- [ ] SES fallback still works if explicitly configured
- [ ] Postmark remains default provider
- [ ] Unused env vars documented/removed

---

## Items Explicitly Deferred

| Item | Reason |
|------|--------|
| `VISIT_TIME_CHANGED` template | No trigger exists in code |
| `send_notification()` as new API | Not needed — `notify_event()` is the stable entrypoint |
| SMS notifications | Different channel, different provider |
| Client notification preferences | Requires client portal UI |
| Email open/click tracking UI | Low priority |
| Multi-tenant notification isolation | Single tenant currently |
| Notification retry queue (SQS) | Calendar retry pattern is sufficient |
| Ledger replacing existing idempotency | Too risky — ledger supplements, doesn't replace |
