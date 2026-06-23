# Release 18M: Phase 2 Entitlement Controlled Validation Plan

**Status:** Planning
**Date:** 2026-06-23
**Priority:** Medium (confirms Phase 2 gates work before second-tenant or tier changes)
**Scope:** Design safe production validation for client limit and monthly booking counter

---

## 1. Validation Methods

| Method | Safety | Coverage | Recommendation |
|--------|--------|----------|----------------|
| Read-only verification (inspect counter/logs) | ✅ Safest | Low | ✅ Do first |
| Unit/regression test review (already passed) | ✅ Safe | High (logic) | ✅ Already done (18L) |
| Controlled admin test client creation | ⚠️ Creates data | Medium | ✅ With Matthew approval |
| Controlled admin test booking (is_test_booking=true) | ⚠️ Creates data | High | ✅ With Matthew approval |
| Force denial by lowering tier limit | ❌ Risky | High | ❌ Do not modify limits |

### Recommended Approach: Layered

1. **Step 1:** Read-only CloudWatch/DynamoDB check (no writes)
2. **Step 2:** Create one test client with no email (Matthew approves)
3. **Step 3:** Create one test booking with `is_test_booking=true` (Matthew approves)
4. **Step 4:** Verify counter behavior + cleanup

---

## 2. Test Data Strategy

### Test Client

| Field | Value | Notes |
|-------|-------|-------|
| Client name | `Phase2Test_18M_Client` | Clearly internal test |
| Email | (omit) | No notification delivery |
| Phone | (omit) | No contact risk |
| Company | `tog_and_dogs` | Current tenant |
| Notes | "Release 18M Phase 2 validation — safe to archive" | Self-documenting |

### Test Booking

| Field | Value | Notes |
|-------|-------|-------|
| Client | `Phase2Test_18M_Client` (created above) | Links to test client |
| Pet name | `TestPet_Phase2` | Clearly test |
| Service | Dog walking (simplest) | Low complexity |
| Start date | Tomorrow or +2 days | Short window |
| `is_test_booking` | `true` | **Exempt from monthly counter** |
| Notes | "Release 18M validation — safe to cancel" | Self-documenting |

### Counter Validation Booking (Optional, Separate)

To verify the counter actually increments, a SECOND booking WITHOUT `is_test_booking=true` may be needed:

| Field | Value | Notes |
|-------|-------|-------|
| Same test client | `Phase2Test_18M_Client` | No real client |
| Pet | `TestPet_Counter` | Clearly test |
| `is_test_booking` | `false` (or omitted) | **Should increment counter** |
| Purpose | Verify USAGE# record appears with count=1 | Then cancel/cleanup |

**This second booking requires separate Matthew approval because it increments the real monthly counter.**

---

## 3. Validation Scenarios

| # | Scenario | Method | Expected | Approval? |
|---|----------|--------|----------|-----------|
| 1 | Client creation below limit (Professional: ~30/100) | Create test client | 200 + client record created | **Yes** |
| 2 | Client count increments | Platform Admin shows +1 client | Count increases | Follows from #1 |
| 3 | Test booking with `is_test_booking=true` | Admin offline booking | 200 + booking created, counter NOT incremented | **Yes** |
| 4 | Verify USAGE# record absent or unchanged | Read-only DynamoDB check | No USAGE# increment for test booking | Read-only |
| 5 | Normal booking (counter test) — optional | Admin offline booking without test flag | 200 + USAGE# incremented to 1 | **Yes (separate)** |
| 6 | Verify USAGE# record present after normal booking | Read-only check | `USAGE#tog_and_dogs / BOOKINGS#2026-06` count=1 | Read-only |
| 7 | Phase 1 gates still work (export) | GET /admin/export-data | 200 (professional allowed) | No (read-only) |
| 8 | Phase 1 gates still work (calendar) | GET /admin/auth/status | Connected (already validated in 18G/18I) | No |
| 9 | Platform Admin functional | /platform-admin loads, shows updated counts | Tenant detail accurate | No |
| 10 | Cancel test booking(s) | Admin cancellation action | Record cancelled | **Yes** |

### Denial Path Validation

Client limit denial (100/100) and booking limit denial (250/250) cannot be safely tested without:
- Lowering tier limits (not recommended) OR
- Creating 100 fake clients / 250 fake bookings (impractical)

**Decision:** Rely on unit tests (passed in 18L) for denial path coverage. Production validation confirms the ALLOWED path + counter mechanics work correctly.

---

## 4. Notification/Payment/Calendar Risk Assessment

| Action | Sends Email? | Creates Calendar Event? | Payment? |
|--------|-------------|------------------------|----------|
| Create test client (no email) | ❌ No (no email address) | ❌ No | ❌ |
| Admin offline booking | ❌ No (skips request-received email) | ✅ **Yes** (calendar sync is connected) | ❌ |
| Cancel booking | ⚠️ May attempt cancellation email | ✅ **May delete calendar event** | ❌ |

### Calendar Event Risk

Since Google Calendar is reconnected (18G/18I), admin offline bookings WILL create calendar events. This is expected and validated behavior.

**Mitigation:** Use a past or near-future date. The calendar event will be created and then removed on cancellation. This is normal operational behavior.

### Notification Risk

- No client email = no notification delivery
- Admin offline booking path skips request-received template
- Cancellation MAY send admin notification (internal) — acceptable
- No SMS or push notifications

---

## 5. Cleanup Strategy

| Step | Action | Method |
|------|--------|--------|
| 1 | Cancel test booking(s) | Admin dashboard → cancel action |
| 2 | Verify calendar event(s) removed | Check Google Calendar |
| 3 | Archive test client | Admin dashboard → archive/disable |
| 4 | Verify USAGE# counter reflects actual state | Read-only check |
| 5 | Document closeout | Release notes with safe summary |

### Cleanup Safety

- Cancellation is a normal admin workflow — no destructive DynamoDB deletes
- Archiving client is non-destructive
- Calendar event removal is handled by sync on cancellation
- USAGE# counter is NOT decremented on cancellation (by design — counts creation, not active bookings)
- If counter validation booking was created, counter shows 1 for the month — acceptable

### Do NOT

- Do not manually delete DynamoDB records
- Do not modify USAGE# counter directly
- Do not lower tier limits
- Do not delete the tenant

---

## 6. CloudWatch/Observability Checks

| Check | Filter/Method | Expected |
|-------|---------------|----------|
| `ENTITLEMENT_ALLOWED` for client creation | Admin Lambda logs | Entry showing client limit check passed |
| `ENTITLEMENT_ALLOWED` for booking creation | Admin/Intake Lambda logs | Entry showing monthly booking check passed |
| No `ENTITLEMENT_DENIED` for tog_and_dogs | Admin Lambda logs | Zero denials (well under limits) |
| `TENANT_RESOLUTION_FALLBACK` | All Lambda logs | Zero (users have custom:company_id) |
| `TENANT_RESOLUTION_FAILED` | All Lambda logs | Zero (single mode active) |
| Calendar sync success | Admin Lambda logs | `CALENDAR_SYNC_SUCCESS` for test booking |

---

## 7. Stop Conditions

| Condition | Action |
|-----------|--------|
| Client creation returns unexpected 403 | Stop — investigate entitlement check |
| Booking creation returns unexpected 403 | Stop — investigate counter/limit |
| Counter increments for `is_test_booking=true` | Stop — exemption logic broken |
| Counter does NOT increment for normal booking | Stop — increment logic broken |
| ENTITLEMENT_DENIED fires for tog_and_dogs unexpectedly | Stop — investigate |
| Calendar event not created (sync regression) | Note but don't stop — calendar is secondary |
| Notification sent to real client | Stop — investigate (should be impossible with no email) |

---

## 8. Matthew Approval Gates

AG must NOT proceed until Matthew explicitly approves:

| # | Approval | What It Authorizes |
|---|----------|-------------------|
| A1 | Test client creation | Create `Phase2Test_18M_Client` with no email |
| A2 | Test booking (is_test_booking=true) | Create one booking for counter-exempt validation |
| A3 | Counter validation booking (optional) | Create one normal booking to verify counter increments |
| A4 | Cleanup via cancellation | Cancel test booking(s), archive test client |

Matthew can approve all at once or gate each step.

---

## 9. Expected AG Report Fields

After execution, AG reports:
- Test client created: yes/no + client count before/after
- Test booking created: yes/no + counter state
- Counter validation: exempt booking did NOT increment / normal booking DID increment
- Calendar event: created/not created
- Phase 1 gates: still functional (export/calendar/staff)
- Platform Admin: shows updated counts
- Cleanup: bookings cancelled, client archived
- CloudWatch: no unexpected denials or failures
- No real clients/notifications/payments affected

---

## 10. Recommended AG Execution Release

**18N — Phase 2 Entitlement Controlled Validation Execution**

| Step | Action |
|------|--------|
| 1 | Matthew approves test data + actions (A1–A4) |
| 2 | AG creates test client (no email) |
| 3 | AG creates test booking (`is_test_booking=true`) |
| 4 | AG verifies counter NOT incremented |
| 5 | (Optional) AG creates counter validation booking (normal) |
| 6 | AG verifies USAGE# record with count=1 |
| 7 | AG verifies CloudWatch logs |
| 8 | AG cancels test bookings, archives test client |
| 9 | AG documents closeout |

---

## 11. What This Document Does NOT Authorize

- ❌ Creating clients/bookings/jobs
- ❌ DynamoDB writes
- ❌ Calendar event creation
- ❌ Notifications
- ❌ Code changes
- ❌ Terraform/AWS changes
- ❌ Cognito changes
- ❌ Enabling strict mode
- ❌ Creating second tenant
- ❌ Modifying tier limits
- ❌ Stripe/Postmark/payment actions
- ❌ Ryan/tester changes

This is a planning document. Execution (18N) requires Matthew's approval at gates A1–A4.
