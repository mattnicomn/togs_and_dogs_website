# Release 7F: Production Notifications Stabilization

**Status:** Planning
**Priority:** High (customer-facing correctness)
**Risk to Production:** Medium (notifications are already live — changes affect real email delivery)
**Terraform Required:** No (unless new env vars needed)
**Frontend Changes:** No

---

## 1. Current Production State — Already Live

**Critical finding:** Notifications are NOT in dry-run or planning state. They are **fully live in production** since Releases 6A–6J:

```
NOTIFICATIONS_ENABLED = true
NOTIFICATION_DRY_RUN = false
NOTIFICATION_PROVIDER = postmark
NOTIFICATION_MODE = external_provider
```

### What Is Already Working

| Event | Template | Recipient | Status |
|-------|----------|-----------|--------|
| `REQUEST_RECEIVED` | Admin notification (purple branded) | Admin (mbn@usmissionhero.com) | ✅ Live |
| `CUSTOMER_APPROVED` | Client approval confirmation | Client email | ✅ Live |
| `STAFF_ASSIGNED` | Staff assignment notification (purple) | Assigned staff email | ✅ Live |
| `VISIT_SCHEDULED` | Client visit confirmation (blue) | Client email | ✅ Live |
| `VISIT_CANCELLED` | Cancellation notice (red/neutral) | Client + Staff + Admin | ✅ Live |
| `VISIT_TIME_CHANGED` | Time change notice (stub) | Client email | ⚠️ Template exists, no trigger |
| `WELCOME_INVITE_STAFF` | Staff onboarding email | New staff email | ✅ Live |
| `WELCOME_INVITE_CLIENT` | Client portal invite | New client email | ✅ Live |

### Infrastructure Already In Place

| Component | Status |
|-----------|--------|
| Postmark sender signature | ✅ Verified, production-approved |
| Notification ledger (DynamoDB) | ✅ Recording all sends/skips/failures |
| Suppression list (bounce/spam) | ✅ Auto-suppressing via webhook |
| Postmark webhook handler | ✅ Processing bounces, spam, delivery |
| Monthly quota tracking | ✅ Atomic counters, 100/month limit |
| Per-event kill switches | ✅ All configurable via env vars |
| Duplicate prevention (approval) | ✅ `approval_notification_status` check |
| Recipient resolution | ✅ Email extraction + suppression check |
| Null-safety in templates | ✅ `_safe()` helper throughout |

---

## 2. The Actual Problem: Multi-Day Notification Behavior

With Release 7E (multi-day and selected-day bookings), the notification system has **new edge cases** that were not explicitly designed for:

### Current Behavior (Potentially Problematic)

| Scenario | What Happens Now | Problem? |
|----------|-----------------|----------|
| 5-day booking approved | `CUSTOMER_APPROVED` fires ONCE for parent REQ | ✅ Correct — one approval email |
| Staff assigned to 1 child JOB | `STAFF_ASSIGNED` + `VISIT_SCHEDULED` fire for that JOB | ✅ Correct |
| Staff assigned to all 5 JOBs individually | 5× `STAFF_ASSIGNED` + 5× `VISIT_SCHEDULED` emails | ⚠️ Spam risk |
| Parent REQ cancelled (cascades to 5 JOBs) | `VISIT_CANCELLED` fires ONCE for parent REQ | ✅ Correct |
| Individual child JOB cancelled | No notification fires (cascade doesn't trigger notify) | ⚠️ Gap |
| Selected-dates booking (6 non-consecutive days) | Same as multi-day range | Same issues |

### Key Questions This Release Must Answer

1. **Should staff get 5 separate "You've been assigned" emails for a 5-day booking?** Or one consolidated email listing all dates?
2. **Should clients get 5 separate "Your visit is scheduled" emails?** Or one consolidated email?
3. **When one day of a multi-day booking is cancelled, should the client/staff be notified?**
4. **Should the notification template show the specific occurrence date or the full date range?**

---

## 3. Recommended Notification Rules for Multi-Day Bookings

### Rule 1: Approval — One Email Per Parent REQ (No Change)

When a multi-day or selected-dates booking is approved:
- Send ONE `CUSTOMER_APPROVED` email to the client
- Email should mention the full date range or list of selected dates
- Do NOT send per-JOB approval emails

**Current behavior is correct.** Approval fires on the parent REQ, not on child JOBs.

### Rule 2: Staff Assignment — One Email Per Assignment Action (Consolidate)

When staff is assigned to a multi-day booking:
- If all JOBs are assigned to the same staff in one action → ONE `STAFF_ASSIGNED` email listing all dates
- If JOBs are assigned individually (different staff per day) → one email per assignment action

**Current behavior needs a guard:** The assignment handler fires per-JOB. If Ryan assigns the same staff to 5 JOBs in sequence, the staff gets 5 emails. This is the primary spam risk.

**Proposed fix:** Add a dedup window — if the same `(staff_email, request_id)` pair received a `STAFF_ASSIGNED` notification within the last 5 minutes, skip the duplicate.

### Rule 3: Visit Scheduled — One Email Per Parent REQ (Consolidate)

When a multi-day booking's staff is assigned:
- Send ONE `VISIT_SCHEDULED` email to the client listing all scheduled dates
- Do NOT send per-JOB scheduled emails

**Proposed fix:** Only fire `VISIT_SCHEDULED` from the parent REQ context, not from individual JOB assignment. Or add the same dedup window as staff assignment.

### Rule 4: Individual Day Cancellation — Notify Once

When one day of a multi-day booking is cancelled:
- Send ONE notification to client + staff mentioning the specific cancelled date
- Do NOT re-notify about the remaining active days

**Current gap:** Individual JOB cancellation via cascade doesn't trigger `notify_event`. Only parent REQ cancellation does. This is actually acceptable for MVP — if Ryan cancels one day, he can communicate directly. Full per-day cancellation notifications can be added later.

### Rule 5: Parent REQ Cancellation — One Email (No Change)

When the entire multi-day booking is cancelled:
- Send ONE `VISIT_CANCELLED` email mentioning the full date range
- Do NOT send per-JOB cancellation emails

**Current behavior is correct.** Cancellation fires on the parent REQ.

---

## 4. Template Updates for Multi-Day Context

### What Templates Need

The existing templates use `ctx.get('start_date')` for the date display. For multi-day bookings, they should show:
- **Date range:** "July 1–5, 2026"
- **Selected dates:** "July 1, 3, 5, 8, 10, 12"
- **Single day:** "July 15, 2026" (unchanged)

### Proposed Template Context Enhancement

Add a `date_display` field to the normalized context:

```python
# In normalize_context():
selected_dates = context.get('selected_dates')
start_date = context.get('start_date')
end_date = context.get('end_date')
is_multi_day = context.get('is_multi_day')

if selected_dates and len(selected_dates) > 1:
    normalized['date_display'] = _format_date_list(selected_dates)
    normalized['is_multi_visit'] = True
elif is_multi_day and end_date and end_date != start_date:
    normalized['date_display'] = f"{start_date} to {end_date}"
    normalized['is_multi_visit'] = True
else:
    normalized['date_display'] = date_val
    normalized['is_multi_visit'] = False
```

Templates then use `ctx['date_display']` instead of raw `start_date`.

---

## 5. Idempotency Rules

### Existing Idempotency (Already Working)

| Event | Guard | Mechanism |
|-------|-------|-----------|
| `CUSTOMER_APPROVED` | `approval_notification_status` field on REQ | If already "Email sent." → skip |
| All events | Notification ledger | Records every send/skip for audit |

### New Idempotency Needed for Multi-Day

| Scenario | Guard | Mechanism |
|----------|-------|-----------|
| Same staff assigned to 5 JOBs in sequence | Dedup window | Check ledger: if `STAFF_ASSIGNED` sent to same email for same `request_id` within 5 min → skip |
| Client gets 5 `VISIT_SCHEDULED` for same booking | Dedup window | Same pattern: check ledger for recent send to same recipient + request_id |

### Implementation: Lightweight Dedup Check

```python
def _is_recent_duplicate(event_type, recipient, request_id, window_minutes=5):
    """Check if this exact notification was sent recently."""
    # Query ledger for recent entries matching event_type + recipient + request_id
    # If found within window_minutes → return True (skip)
    # Non-blocking: if query fails, allow send (fail-open)
```

---

## 6. Recipient Resolution for Multi-Day

### Current Resolution (Already Correct)

| Event | Recipient Source | Works for Multi-Day? |
|-------|-----------------|---------------------|
| `REQUEST_RECEIVED` | `config.ADMIN_EMAIL` | ✅ Yes (fires on parent REQ) |
| `CUSTOMER_APPROVED` | `record.client_email` | ✅ Yes (fires on parent REQ) |
| `STAFF_ASSIGNED` | `record.worker_id` (email) | ✅ Yes (fires per JOB with worker) |
| `VISIT_SCHEDULED` | `record.client_email` | ⚠️ Fires per JOB — needs dedup |
| `VISIT_CANCELLED` | Client + Staff + Admin | ✅ Yes (fires on parent REQ) |

### Offline Clients (No Email)

Already handled: `resolve_notification_recipients()` returns empty list when no email exists. Notification is skipped gracefully with ledger entry.

---

## 7. Implementation Phases

### Phase A: Audit & Dedup Guard (~0.5 day)

**Goal:** Prevent notification spam for multi-day bookings without changing any existing behavior for single-day bookings.

1. Add `_is_recent_duplicate()` helper to `service.py`
2. Call it before dispatch for `STAFF_ASSIGNED` and `VISIT_SCHEDULED` events
3. If duplicate detected → write `skipped_duplicate_window` to ledger, skip send
4. Window: 5 minutes (same recipient + same request_id + same event_type)
5. Single-day bookings: dedup check passes (no recent send exists) → unchanged behavior

**Files:** `src/backend/common/notifications/service.py`
**Risk:** Very low — adds a skip condition, doesn't change send logic

### Phase B: Template Multi-Day Context (~0.5 day)

**Goal:** Make email content accurate for multi-day bookings.

1. Add `date_display` and `is_multi_visit` to `normalize_context()` in `templates.py`
2. Update `customer_approved` template to show date range or selected dates
3. Update `visit_scheduled` template to show the specific occurrence date (from JOB context)
4. Update `staff_assigned` template to show the specific occurrence date
5. Update `visit_cancelled` template to show full range when parent REQ is cancelled

**Files:** `src/backend/common/notifications/templates.py`
**Risk:** Low — template rendering changes only; null-safe via `_safe()` helper

### Phase C: Validation & Monitoring (~0.5 day)

**Goal:** Confirm notifications are correct in production.

1. Create a test multi-day booking (3 days) → verify ONE approval email
2. Assign staff to all 3 JOBs → verify ONE staff email (dedup catches duplicates)
3. Cancel the booking → verify ONE cancellation email
4. Check notification ledger for correct entries
5. Check Postmark dashboard for delivery confirmation
6. Document results in validation notes

**Files:** None (operational validation)
**Risk:** None

---

## 8. Files Affected

| File | Change | Phase |
|------|--------|-------|
| `src/backend/common/notifications/service.py` | Add `_is_recent_duplicate()` dedup check | A |
| `src/backend/common/notifications/templates.py` | Add `date_display` context, update templates | B |
| `tests/backend/test_r7f_notification_dedup.py` | New test file | A |
| `tests/backend/test_r7f_template_multiday.py` | New test file | B |

### Files NOT Changed

- No handler changes (notification triggers are already in the right places)
- No Terraform changes
- No frontend changes
- No API client changes
- No `config.py` changes (all flags already exist)
- No `resolver.py` changes (recipient resolution already works)
- No `postmark_client.py` changes

---

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Dedup window too aggressive (skips legitimate sends) | Low | Medium | 5-minute window is conservative; only same recipient + request_id + event_type |
| Dedup window too loose (still sends duplicates) | Low | Low | Even without dedup, duplicates are annoying but not harmful |
| Template changes break existing single-day emails | Very Low | Medium | `date_display` falls back to `start_date` for single-day; null-safe |
| Ledger query for dedup adds latency | Very Low | Low | Non-blocking; if query fails, allow send (fail-open) |
| Multi-day template shows wrong dates | Low | Low | Test with real multi-day booking before closing |
| Ryan's current single-day bookings affected | Very Low | High | Dedup only fires when recent duplicate exists; single-day has no duplicates |

---

## 10. What This Release Does NOT Include

| Item | Reason | Future |
|------|--------|--------|
| Per-day cancellation notifications | Low priority; Ryan communicates directly | 7G |
| Consolidated "all days assigned" summary email | Complex template logic | 7G |
| Push notifications for multi-day | Release 7C scope (push not enabled yet) | 8A+ |
| Client notification preferences | Requires UI + backend | 8B+ |
| Notification retry on failure | Postmark handles retry internally | Not needed |
| SMS notifications | Different provider, different scope | Future |

---

## 11. Guardrails for AG

| Rule | Enforcement |
|------|-------------|
| Do NOT change `NOTIFICATIONS_ENABLED` or `NOTIFICATION_DRY_RUN` | These are already correctly set to `true`/`false` |
| Do NOT modify handler notification trigger points | Triggers are already in the correct places |
| Do NOT add `notify_event` calls to `job_handler.py` | JOB creation should NOT trigger notifications directly |
| Do NOT modify `postmark_client.py` or `config.py` | Provider layer is stable |
| Do NOT modify Terraform | No infrastructure changes needed |
| Dedup must be fail-open | If ledger query fails, ALLOW the send (never block notifications) |
| Template changes must be null-safe | Use `_safe()` for all new context fields |
| All changes must pass existing notification tests | `test_r6i_notification_ledger.py`, `test_r6b_templates.py` |

---

## 12. Test Requirements

### Phase A Tests (`test_r7f_notification_dedup.py`)

| # | Test | Description |
|---|------|-------------|
| 1 | `test_dedup_skips_recent_same_event` | Same event_type + recipient + request_id within 5 min → skipped |
| 2 | `test_dedup_allows_different_event_type` | Same recipient but different event_type → allowed |
| 3 | `test_dedup_allows_different_request_id` | Same event_type but different request → allowed |
| 4 | `test_dedup_allows_after_window_expires` | Same event after 6 minutes → allowed |
| 5 | `test_dedup_fail_open_on_query_error` | Ledger query fails → send proceeds |
| 6 | `test_single_day_not_affected_by_dedup` | Single-day booking → no dedup triggered |

### Phase B Tests (`test_r7f_template_multiday.py`)

| # | Test | Description |
|---|------|-------------|
| 1 | `test_date_display_single_day` | Single date → "2026-07-15" |
| 2 | `test_date_display_date_range` | Range → "2026-07-01 to 2026-07-05" |
| 3 | `test_date_display_selected_dates` | Selected → "Jul 1, Jul 3, Jul 5, Jul 8" |
| 4 | `test_approval_template_shows_date_display` | Multi-day approval email uses date_display |
| 5 | `test_staff_assigned_shows_occurrence_date` | Staff email shows specific day |
| 6 | `test_existing_single_day_templates_unchanged` | Regression: single-day templates identical |

---

## 13. AG Implementation Prompt (Phase A)

```
AG — implement Release 7F Phase A: Notification Dedup Guard for Multi-Day Bookings.

Backend-only change in src/backend/common/notifications/service.py.

1. Add a new helper function _is_recent_duplicate():

   def _is_recent_duplicate(event_type, recipient, request_id, window_minutes=5):
       """
       Checks the notification ledger for a recent send matching the same
       event_type + recipient + request_id within the dedup window.
       Returns True if a duplicate exists (should skip), False otherwise.
       Fail-open: if the query fails, returns False (allow send).
       """
       try:
           from common.db import table
           from boto3.dynamodb.conditions import Key, Attr
           from datetime import datetime, timezone, timedelta
           
           cutoff = (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).isoformat()
           
           # Query ledger entries for this request
           # PK pattern: NOTIF#<msg_id>, SK: REQUEST#<request_id>
           # We need to scan recent entries — use a targeted approach
           resp = table.query(
               IndexName='StatusIndex',  # or scan with filter
               ... # Implementation detail: query by request_id + filter by event_type + recipient + created_at > cutoff
           )
           # If any matching entry found with status='sent' and created_at > cutoff → duplicate
           ...
       except Exception as e:
           print(f"WARNING: Dedup check failed (fail-open): {e}")
           return False

   NOTE: The exact query pattern depends on available indexes. If no suitable
   index exists, use a simple scan with FilterExpression on entity_type='NOTIFICATION_LEDGER'
   + request_id + event_type + recipient_email + created_at > cutoff.
   Keep it non-blocking and fail-open.

2. In notify_event(), after the duplicate prevention check for CUSTOMER_APPROVED (existing),
   add a general dedup check for STAFF_ASSIGNED and VISIT_SCHEDULED:

   # Multi-day dedup guard (Release 7F)
   if event_type in ['STAFF_ASSIGNED', 'VISIT_SCHEDULED']:
       for r in recipients:
           if _is_recent_duplicate(event_type, r, request_id):
               _write_ledger_entry(request_id, event_type, r, 'skipped_duplicate_window', ...)
               # Remove this recipient from the send list
               recipients = [x for x in recipients if x != r]
       if not recipients:
           return {"success": True, "message": "Skipped: recent duplicate notification."}

3. Write tests: tests/backend/test_r7f_notification_dedup.py
   - test_dedup_skips_recent_same_event
   - test_dedup_allows_different_event_type
   - test_dedup_allows_different_request_id
   - test_dedup_allows_after_window_expires
   - test_dedup_fail_open_on_query_error
   - test_single_day_not_affected

4. Run:
   - python -m py_compile src/backend/common/notifications/service.py
   - pytest tests/backend/test_r7f_notification_dedup.py -v
   - pytest tests/backend/ -v (full suite, ensure no regressions)

Do NOT modify templates, handlers, config, Terraform, or frontend.
Do NOT deploy yet.
Return: files changed, test results, summary.
```

---

## 14. Commit Commands

```bash
# Phase A:
git add src/backend/common/notifications/service.py tests/backend/test_r7f_notification_dedup.py
git commit -m "feat: Release 7F Phase A — notification dedup guard for multi-day bookings"

# Phase B:
git add src/backend/common/notifications/templates.py tests/backend/test_r7f_template_multiday.py
git commit -m "feat: Release 7F Phase B — multi-day date display in notification templates"
```
