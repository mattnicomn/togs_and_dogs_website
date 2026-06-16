# Release 12N — Post-Patch Stripe Checkout Smoke Validation Plan

This document outlines the planning and readiness details for performing a safe post-patch smoke validation after the Release 12M Stripe Checkout deployment.

---

## 1. Safety and Reusability Check: Paid 12L Request

### Analysis of `/payment-session` Handler Behavior
Inspection of [`admin_handler.py` (lines 2011–2035)](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/admin_handler.py#L2011-L2035) reveals that the `/admin/requests/{requestId}/payment-session` endpoint executes an **unconditional update** on the request's DynamoDB record:
```python
table.update_item(
    Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
    UpdateExpression=(
        "SET payment_status = :ps, "
        "stripe_checkout_session_id = :sid, ..."
    ),
    ExpressionAttributeValues={
        ":ps": "payment_link_sent",
        ...
    }
)
```
There is no logic checking if the request's `payment_status` is already `paid`, and no check blocking duplicate session requests.

### Verdict: Reuse of 12L Request is UNSAFE
* **Result of reuse**: Triggering a new payment session on the 12L request (`cd211318-aa72-4bfc-829c-f450e6ffe6c2`) will instantly overwrite `payment_status` from `"paid"` back to `"payment_link_sent"`, regressing the state of the validated 12L test data.
* **Recommendation**: **Do not reuse the 12L request.**

---

## 2. Recommended Test Request Strategy

We must use a separate archived test booking to avoid regressing the 12L test data:

### Safe Existing Test Booking Candidates
DynamoDB scanning discovered the following archived test bookings that are **not paid** (`payment_status = None`):
1. **`REQ#552f1c69-d1b6-479f-8295-cb3f57a1f9ad`** (Client: `client_1697162f`, email: `brearockwell@gmail.com`)
2. **`REQ#a5567999-0254-44be-b7d2-4af6c247921d`** (Client: `client_1697162f`, email: `brearockwell@gmail.com`)
3. **`REQ#f622134b-85f8-4e99-966b-e784275073ba`** (Client: `client_1697162f`, email: `brearockwell@gmail.com`)

### Test Data Priority
* **Option A (Preferred)**: Run the smoke test using one of the existing archived test bookings listed above (e.g., `552f1c69-d1b6-479f-8295-cb3f57a1f9ad`).
* **Option B (Alternate)**: Create a new test request with `is_test_booking = true` under client `client_1697162f` (brearockwell@gmail.com) only after receiving Matthew's explicit approval.

---

## 3. Scope of Smoke Test: Session vs. Payment

* **Session Validation (Required)**: Calling the `/payment-session` endpoint to create a Stripe Checkout Session, then inspecting the Stripe API response to verify:
  1. `success_url` and `cancel_url` point to the correct production domain: `https://toganddogs.usmissionhero.com`.
  2. `payment_method_types` contains only `['card']`.
* **UI Verification (Required)**: Navigating to the generated `stripe_payment_url` to visually verify that only the Card input is shown (and dynamic payment methods like Klarna are absent).
* **Payment Completion (Optional)**: Completing a sandbox payment is **not strictly necessary** because Release 12L already validated that webhook signature verification, DynamoDB status updates (`payment_status = paid`), and billing ledger logging work perfectly end-to-end. 
* **Recommendation**: Limit 12N validation to **session/UI verification only**, unless Matthew explicitly requests end-to-end sandbox payment completion.

---

## 4. Smoke Validation Execution Sequence

Upon approval to execute, follow this sequence:
1. **Session Creation**: Make a POST request to `/admin/requests/{requestId}/payment-session` for the selected test request with `amount_cents = 100`.
2. **Payload Inspection**: Retrieve the generated Stripe Checkout Session from the Stripe API (or read the endpoint's response payload) to verify:
   * `success_url` matches: `https://toganddogs.usmissionhero.com/booking/{request_id}/success?session_id={CHECKOUT_SESSION_ID}`
   * `cancel_url` matches: `https://toganddogs.usmissionhero.com/booking/{request_id}/cancel`
   * `payment_method_types` matches: `["card"]`
3. **UX Verification**: Start a browser subagent to open the generated Stripe URL and verify:
   * The payment page renders properly.
   * Only the credit card form is displayed.
   * No Klarna/dynamic option appears.
4. **Final Check**: Stop at the Stripe Checkout screen. Do not run any transaction.

---

## 5. Matthew's Explicit Approvals Needed

Before proceeding to execution, Matthew must explicitly approve:
1. The choice of the test request (e.g., using `552f1c69-d1b6-479f-8295-cb3f57a1f9ad` or a new test booking).
2. Creating the Stripe Checkout Session (triggering the API Gateway POST call).
3. (Optional) Executing the sandbox test card payment.
