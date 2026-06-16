# Release 12O: Stripe Payment Session State Guard and Duplicate Payment Protection Plan

**Status:** Planning
**Priority:** High (prevents duplicate payment and accounting risk)
**Risk to Production:** Low (additive guard logic, no behavioral regression for valid flows)
**Terraform Required:** No
**Code Changes:** Yes (admin_handler.py guard + tests)
**Scope:** Add payment_status state guard to POST /admin/payment-session endpoint

---

## 1. Problem Statement

### Current Risky Behavior

The `POST /admin/requests/{requestId}/payment-session` endpoint in `admin_handler.py` (lines ~1970–2060) **unconditionally** updates the request record with:

```python
"SET payment_status = :ps, ..."
":ps": "payment_link_sent"
```

No guard checks the existing `payment_status` before overwriting.

### Risk Scenario

```
1. Admin creates payment session → payment_status = payment_link_sent ✅
2. Client pays via Checkout → webhook fires → payment_status = paid ✅
3. Admin accidentally clicks "Send Payment Request" again
4. Endpoint creates NEW Checkout Session → payment_status = payment_link_sent ❌
5. Client receives second payment link
6. Client pays again → double-charged
```

### Impact

- Client charged twice for the same booking
- `payment_status` regresses from `paid` → `payment_link_sent`
- Accounting mismatch: two PaymentIntents for one booking
- Admin trust erosion

---

## 2. Proposed Status Guard Matrix

### Blocked Statuses (Return Error, No Session Created)

| Current payment_status | Response | Reason |
|------------------------|----------|--------|
| `paid` | 409 Conflict: "Payment already received" | Prevent double-charge |
| `refunded` | 409 Conflict: "Request has been refunded" | Recharge requires explicit future workflow |
| `waived` | 409 Conflict: "Payment was waived" | Override requires explicit future workflow |

### Allowed Statuses (Proceed with Session Creation)

| Current payment_status | Behavior |
|------------------------|----------|
| `null` / not set | ✅ Create session (first payment request) |
| `payment_link_sent` | ✅ Create new session (previous may have expired) |
| `payment_failed` | ✅ Create session (retry after failure) |
| `expired` | ✅ Create session (previous session expired) |

### Decision: Allow Re-Creation for `payment_link_sent`

When `payment_status = payment_link_sent`:
- The existing Checkout Session may have expired (30-min default)
- Admin intends to resend a fresh link
- Creating a new session is safe — old session expires naturally
- **Do NOT attempt to return the old session URL** (it may be expired and unusable)
- Simply create a fresh session and update the record

---

## 3. Proposed Implementation

### Guard Logic (Before Stripe API Call)

```python
# After retrieving request_item (step 3), before creating Stripe session (step 5):

BLOCKED_PAYMENT_STATUSES = ('paid', 'refunded', 'waived')

current_payment_status = request_item.get('payment_status')
if current_payment_status in BLOCKED_PAYMENT_STATUSES:
    return error(409, f"Cannot create payment session: request payment status is '{current_payment_status}'", event)
```

### Placement in admin_handler.py

Insert immediately after the tenant ownership validation (step 4) and before the Stripe session creation (step 5):

```python
# 4. Validate tenant ownership
...

# 4b. Payment status guard — prevent duplicate/invalid payment sessions
BLOCKED_PAYMENT_STATUSES = ('paid', 'refunded', 'waived')
current_payment_status = request_item.get('payment_status')
if current_payment_status in BLOCKED_PAYMENT_STATUSES:
    return error(409, f"Cannot create payment session: request payment status is '{current_payment_status}'", event)

# 5. Create Stripe Checkout Session
...
```

### Response Format

```json
{
  "statusCode": 409,
  "body": {
    "error": "Cannot create payment session: request payment status is 'paid'"
  }
}
```

---

## 4. API Response Codes Summary

| Scenario | HTTP Status | Message |
|----------|-------------|---------|
| Success: session created | 200 | "Payment session created successfully" |
| Already paid | 409 | "Cannot create payment session: request payment status is 'paid'" |
| Already refunded | 409 | "Cannot create payment session: request payment status is 'refunded'" |
| Already waived | 409 | "Cannot create payment session: request payment status is 'waived'" |
| Request not found | 404 | "Request {id} not found for client {id}" |
| Cross-tenant access | 403 | "Forbidden" |
| Missing amount_cents | 400 | "Missing required amount_cents in request body" |
| Stripe API error | 500 | "Stripe session creation failed: {details}" |

---

## 5. Test Cases

### New Tests to Add

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | Paid request blocks session creation | `payment_status = "paid"` on request item | 409 + "payment status is 'paid'" |
| 2 | Refunded request blocks session creation | `payment_status = "refunded"` on request item | 409 + "payment status is 'refunded'" |
| 3 | Waived request blocks session creation | `payment_status = "waived"` on request item | 409 + "payment status is 'waived'" |
| 4 | No payment_status allows session creation | `payment_status` key absent | 200 + session created |
| 5 | Null payment_status allows session creation | `payment_status = None` | 200 + session created |
| 6 | payment_link_sent allows new session (resend) | `payment_status = "payment_link_sent"` | 200 + new session created |
| 7 | payment_failed allows retry session | `payment_status = "payment_failed"` | 200 + session created |

### Existing Tests (Must Still Pass)

- All tests in `test_r12g_stripe_checkout.py` that test successful creation should continue passing (they use requests without blocked statuses)
- Full suite 394+ tests must pass

---

## 6. Edge Cases

### Race Condition: Webhook Arrives During Session Creation

```
T0: Admin clicks "Send Payment"
T1: Client pays OLD session (from previous link)
T2: Webhook fires → payment_status = paid
T3: Admin handler reads request → sees payment_status = paid → blocks ✅
```

This is the CORRECT behavior. The guard catches the race.

### Race Condition: Admin Clicks Fast Twice

```
T0: Admin clicks "Send Payment" (first)
T1: First request reads request → payment_status = null → proceeds
T2: Admin clicks "Send Payment" (second, milliseconds later)
T3: Second request reads request → payment_status = null (update hasn't committed yet)
T4: Both create sessions
```

This race is acceptable for now:
- Both sessions are valid (only one can be paid)
- Stripe handles this gracefully (second payment = second session, client chooses one)
- True fix would require DynamoDB conditional write (add later if needed)
- Practical risk: very low (admin UI debounce prevents this)

### Checkout Session Expires But payment_status Remains `payment_link_sent`

- Admin calls endpoint again → allowed (creates fresh session)
- Old session remains in `payment_link_sent` state until webhook processes `checkout.session.expired`
- If expired webhook is handled, it could set `payment_status = payment_failed`
- If not handled yet, leaving as `payment_link_sent` is fine (admin can resend)

---

## 7. Files to Change

| File | Change |
|------|--------|
| `src/backend/handlers/admin_handler.py` | Add payment_status guard before Stripe session creation |
| `tests/backend/test_r12g_stripe_checkout.py` | Add 7 new test cases for blocked/allowed statuses |

---

## 8. Deployment Sequence

| Step | Actor | Action |
|------|-------|--------|
| 1 | AG | Implement guard logic in admin_handler.py |
| 2 | AG | Add new tests to test_r12g_stripe_checkout.py |
| 3 | AG | Run full test suite (`py -m pytest tests/backend/ -v`) |
| 4 | AG | Compile-check admin_handler.py |
| 5 | AG | Commit: "Release 12O: payment session state guard and duplicate payment protection" |
| 6 | AG | Push to origin/main |
| 7 | Matthew | Approve backend deployment (terraform apply for Lambda code update) |
| 8 | AG | Deploy backend (terraform apply — Lambda source_code_hash changes) |
| 9 | AG | Sandbox validation: attempt payment-session on a paid test record → verify 409 |
| 10 | AG | Sandbox validation: attempt payment-session on unpaid test record → verify 200 |

---

## 9. Validation After Deployment

### Positive Test (Should Succeed)

```
POST /admin/payment-session
Body: {"request_id": "test_unpaid_request", "client_id": "...", "amount_cents": 5000}
→ Expected: 200, new Checkout URL returned
```

### Negative Test (Should Block)

```
POST /admin/payment-session  
Body: {"request_id": "test_payment_validation_12k", "client_id": "...", "amount_cents": 5000}
→ Expected: 409, "Cannot create payment session: request payment status is 'paid'"
```

(The 12K/12L test record has `payment_status = paid` already.)

---

## 10. Rollback Considerations

If the guard causes unexpected issues:

- **False positives** (blocks valid requests): Check what `payment_status` value the request has. If it's an unexpected value not in the blocked list, the guard won't fire. If a value is wrongly in the blocked list, remove it.
- **Revert:** Single-file revert of admin_handler.py removes the guard
- **No data risk:** The guard only adds a check before Stripe API call — it doesn't modify data

---

## 11. Future Enhancements (Not In Scope)

| Enhancement | When |
|-------------|------|
| Admin "Force new payment" override button | When admin UI supports it |
| Conditional DynamoDB write to prevent race condition | If duplicate sessions become a real problem |
| Auto-expire old Checkout Sessions | When `checkout.session.expired` webhook is fully wired |
| Refund + re-charge workflow | When refund feature is built |
| Payment amount change (partial payment) | Future pricing flexibility release |

---

## 12. What This Document Does NOT Authorize

- ❌ Implementing the code changes
- ❌ Running tests
- ❌ Deploying to production
- ❌ Creating Checkout Sessions
- ❌ Making payments
- ❌ Writing to DynamoDB
- ❌ Modifying Terraform
- ❌ Activating Stripe live mode
- ❌ Frontend/mobile/EAS/TestFlight changes
- ❌ Committing secrets

This is a planning document only. Implementation requires separate explicit approval.
