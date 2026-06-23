# Release 18H: Post-Reconnect Calendar Sync Validation Plan

**Status:** Planning
**Date:** 2026-06-23
**Priority:** Medium (confirms reconnect restored full functionality)
**Scope:** Design safe controlled calendar sync validation without customer-facing side effects

---

## 1. Safest Validation Method

### Options Evaluated

| Method | Safety | Coverage | Risk | Recommendation |
|--------|--------|----------|------|----------------|
| Code review only (no write) | ✅ Safest | Low (no runtime proof) | None | ⚠️ Partial — confirms logic but not live sync |
| Create controlled test booking → verify calendar event | ✅ Safe if controlled | High | Low if test data used | ✅ **Recommended** |
| Use existing test booking (re-approve) | ⚠️ May trigger notifications | Medium | Medium | ⚠️ Only if notification-safe |
| Wait for next real booking | ❌ Uncontrolled | High | Customer data involved | ❌ Avoid for validation |

### Decision: Controlled Internal Test Booking

Create one clearly-labeled test booking via the admin offline booking flow, verify calendar event appears, then cancel/cleanup.

**This requires Matthew's explicit approval before execution.**

---

## 2. Test Data Strategy

### Proposed Test Record

| Field | Value | Notes |
|-------|-------|-------|
| Client name | `CalendarSyncTest_18H` | Clearly test — not a real client |
| Pet name | `TestPet_CalSync` | Clearly test |
| Service type | Dog walking (or simplest option) | Low-complexity |
| Start date | Tomorrow or day-after (short window) | Easy to verify in Calendar |
| Duration | 30 minutes or 1 hour | Standard |
| is_test_booking | `true` | Admin flag for identification |
| Notes | "Release 18H calendar sync validation — safe to delete" | Self-documenting |

### What Must NOT Be Used

- ❌ Real client names, emails, or phone numbers
- ❌ Real staff assignment (unless explicitly approved)
- ❌ Real scheduled dates that conflict with production visits
- ❌ Long-duration or multi-day bookings (keep minimal)

---

## 3. Notification Risk Assessment

### What Triggers Notifications

| Action | Sends Email? | Sends SMS? | Sends Push? |
|--------|-------------|-----------|------------|
| Create admin offline booking | ❌ (skips request-received email) | ❌ | ❌ |
| Approve request (review) | ✅ Client approval email | ❌ | ❌ |
| Assign staff | ✅ Staff assignment email | ❌ | ❌ |
| Cancel visit | ✅ Cancellation email | ❌ | ❌ |

### Notification Suppression Strategy

| Option | Feasibility | Recommendation |
|--------|-------------|----------------|
| Use admin offline booking (skips approval notification) | ✅ Built-in | ✅ **Use this path** |
| Use `is_test_booking = true` (may suppress some templates) | ⚠️ Check behavior | ✅ Set flag |
| No client email on test record | ✅ Prevents email delivery | ✅ **Omit client email** |
| Notification disabled env var | ❌ Would affect all tenants | ❌ Avoid |

### Safest Path: Admin Offline Booking With No Client Email

1. Create admin offline booking → no request-received email (built-in behavior)
2. Omit client email on test record → no notification can be delivered
3. Calendar sync still fires (it doesn't depend on notification email)
4. Result: calendar event created without any external communication

---

## 4. Calendar Validation Checklist

| # | Check | Method | Expected | Approval? |
|---|-------|--------|----------|-----------|
| 1 | Admin offline booking creates test record | Admin dashboard action | 200 + record in DynamoDB | **Yes — Matthew approves** |
| 2 | Booking triggers calendar sync | CloudWatch logs show calendar sync attempt | `CALENDAR_SYNC_SUCCESS` or event ID returned | Follows from #1 |
| 3 | Google Calendar event appears | Check Matthew's linked Google Calendar | Event titled with test pet/client info | Visual check |
| 4 | Event date/time is correct | Compare to test booking date | Matches start date/time | Visual check |
| 5 | Event description does not expose secrets | Inspect event body | Contains service/pet info, no tokens/passwords | Visual check |
| 6 | No email/SMS/push sent | Check Postmark/CloudWatch | Zero notification sends for test record | Verify |
| 7 | DynamoDB record has `google_event_id` | Read record (if accessible) | Field populated | AG read-only check |
| 8 | Cancel/delete test booking | Admin action | Record cancelled/archived | **Yes — Matthew approves** |
| 9 | Calendar event removed/cancelled | Check Google Calendar | Event deleted or marked cancelled | Visual check |
| 10 | No side effects on production data | Review admin dashboard | Other bookings unchanged | Visual check |

---

## 5. Cleanup Plan

### After Validation Succeeds

| Step | Action | Method |
|------|--------|--------|
| 1 | Cancel the test booking | Admin dashboard → cancel action |
| 2 | Verify calendar event is removed | Check Google Calendar |
| 3 | Archive/delete test booking if preferred | Admin dashboard → archive |
| 4 | Confirm no orphan data | Admin list shows clean |

### If Validation Fails

| Scenario | Action |
|----------|--------|
| Calendar event NOT created | Check CloudWatch for sync errors; token may need re-validation |
| Event created with wrong data | Delete event manually in Google Calendar; investigate code |
| Notification sent unexpectedly | Document; verify client email was omitted on test record |
| DynamoDB write error | Record may be partially created; investigate and cleanup |

### Cleanup Safety

- Test booking marked `is_test_booking = true` and `CalendarSyncTest_18H` name → clearly identifiable
- Cancellation removes the calendar event via sync
- Archiving the DynamoDB record is safe and non-destructive
- No real customer data involved

---

## 6. Required Matthew Approval Gate

**AG must NOT create any booking, job, or calendar event until Matthew explicitly approves:**

1. The exact test data values (client name, pet name, date)
2. That no real client email is included
3. That the admin offline booking path is acceptable
4. That cleanup via cancellation is acceptable

### Approval Format

Matthew should confirm:
- "Approved: create one test booking with [test data] on [date], no client email, cancel after verification."

---

## 7. Recommended AG Execution Release

**18I — Post-Reconnect Calendar Sync Controlled Validation Execution**

| Step | Action |
|------|--------|
| 1 | Matthew approves exact test data and action |
| 2 | AG creates admin offline booking (no client email) |
| 3 | AG verifies CloudWatch shows calendar sync success |
| 4 | Matthew visually confirms Google Calendar event exists |
| 5 | AG cancels test booking |
| 6 | Matthew confirms event removed from Calendar |
| 7 | AG documents closeout |

---

## 8. What This Document Does NOT Authorize

- ❌ Creating bookings/jobs/calendar events
- ❌ Approving requests
- ❌ Assigning staff
- ❌ Cancelling bookings
- ❌ Sending emails/SMS/push
- ❌ Making payments
- ❌ Code changes
- ❌ OAuth reconnect (already done in 18G)
- ❌ Token inspection
- ❌ DynamoDB writes
- ❌ Terraform/AWS changes
- ❌ Enabling strict mode
- ❌ Creating a second tenant
- ❌ Ryan/tester changes

This is a planning document. Execution (18I) requires Matthew's explicit approval of the exact test scenario.
