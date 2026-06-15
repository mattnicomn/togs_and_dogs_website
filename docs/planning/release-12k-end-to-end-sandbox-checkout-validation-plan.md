# Release 12K: End-to-End Sandbox Checkout Validation Plan

**Status:** Planning
**Priority:** High (first true payment integration test)
**Risk to Production:** Low-Medium (writes to production DynamoDB but uses clearly marked test data only)
**Terraform Required:** No
**Code Changes:** None
**Stripe Mode:** Sandbox only
**Scope:** Plan the controlled end-to-end sandbox Checkout flow with safe test data

---

## 1. Objective

Validate the full payment lifecycle in sandbox mode:

```
Admin creates payment session → Stripe Checkout URL → Test card payment
→ Stripe fires signed webhook → Lambda processes → DynamoDB updated
```

This is the first time real DynamoDB records will be written as part of the billing flow. The plan must ensure only clearly marked test data is affected.

---

## 2. Safety Constraints

| Constraint | Reason |
|------------|--------|
| Use only a clearly marked test request | Prevent real customer booking mutation |
| Do not use real client bookings | Ryan's active bookings must not be touched |
| Use Matthew-controlled test email | No real client receives payment emails |
| Stripe sandbox mode only | No real charges |
| Test card only (4242...) | No real payment method |
| Document test record identifiers | Enable audit and cleanup |

---

## 3. Test Data Strategy

### Option A: Use Existing Test Booking (Preferred if Available)

If a request record already exists that is:
- Marked with `is_test_booking: true`
- Status: `approved` (or equivalent)
- Client email: Matthew-controlled (e.g., `mattnicomn10@gmail.com` or `mattnicomn10@yahoo.com`)
- company_id: `tog_and_dogs`

Then use it directly. No new data creation needed.

### Option B: Create a New Test Request via Admin Portal

If no suitable test request exists:

1. Use the admin web portal to create a manual/offline booking
2. Set client to a Matthew-controlled profile
3. Mark as test booking (`is_test_booking: true`)
4. Approve the booking (status → approved)
5. Record the `request_id` for use in the validation

### Option C: Create a Test Request via DynamoDB (Last Resort)

Only if Options A/B are not feasible:
- AG creates a minimal test record directly in DynamoDB
- Must include: `company_id`, `client_id`, `client_email`, `status: approved`, `is_test_booking: true`
- Requires Matthew's explicit approval before any DynamoDB write

### Recommended Test Record Fields

```json
{
  "PK": "REQ#test_payment_validation_12k",
  "SK": "CLIENT#test_client_12k",
  "request_id": "test_payment_validation_12k",
  "client_id": "test_client_12k",
  "client_email": "mattnicomn10@gmail.com",
  "company_id": "tog_and_dogs",
  "status": "approved",
  "is_test_booking": true,
  "service_type": "dog_walking",
  "pet_names": ["TestDog"],
  "start_date": "2025-07-15",
  "created_at": "2025-07-01T00:00:00Z",
  "notes": "Release 12K sandbox payment validation - safe to delete"
}
```

---

## 4. Admin Authentication

### Who Calls the Payment-Session Endpoint

- Matthew's admin account: `mattnicomn10@gmail.com`
- Cognito sub: `b4a89428-9071-7063-dcad-983d4305dd8c`
- Group: admin (or owner)

### Token Retrieval

AG retrieves a valid Cognito JWT for the admin account using:
- AWS CLI `cognito-idp initiate-auth` or
- The admin web portal's existing auth flow

⚠️ **Do NOT print or log the full JWT token in docs or reports.** Confirm it is valid by checking the response status code.

---

## 5. Payment-Session Endpoint Call

### Request

```
POST https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod/admin/payment-session
Authorization: Bearer {cognito_jwt}
Content-Type: application/json

{
  "request_id": "test_payment_validation_12k",
  "client_id": "test_client_12k",
  "amount_cents": 5000,
  "description": "12K Sandbox Validation - Dog Walking Test"
}
```

### Expected Response (200)

```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_...",
  "session_id": "cs_test_...",
  "expires_at": 1719795600
}
```

### Expected Side Effects

- Request record updated: `payment_status = payment_link_sent`
- Request record updated: `stripe_checkout_session_id = cs_test_...`
- Request record updated: `payment_amount_cents = 5000`
- Request record updated: `payment_requested_at = <ISO timestamp>`

---

## 6. Stripe Checkout Test Payment

### Steps

1. Open the `checkout_url` from the response in a browser
2. Stripe Checkout page loads showing:
   - Amount: $50.00
   - Description: "12K Sandbox Validation - Dog Walking Test"
3. Enter test card details:
   - Card: `4242 4242 4242 4242`
   - Expiry: Any future date (e.g., `12/30`)
   - CVC: Any 3 digits (e.g., `123`)
   - Name: `Test User`
   - ZIP: Any valid format (e.g., `12345`)
4. Click **"Pay"**
5. Stripe processes the test payment
6. Browser redirects to success URL (may 404 if frontend page doesn't exist yet — that's fine)

### Alternative: Stripe CLI

```powershell
# If Stripe CLI is installed and authenticated:
stripe checkout sessions create --mode=payment --line-items[0][price_data][currency]=usd --line-items[0][price_data][product_data][name]="Test" --line-items[0][price_data][unit_amount]=5000 --line-items[0][quantity]=1 --metadata[company_id]=tog_and_dogs --metadata[request_id]=test_payment_validation_12k --metadata[client_id]=test_client_12k --metadata[payment_type]=booking --metadata[environment]=sandbox
```

---

## 7. Expected Webhook Behavior

### Event: checkout.session.completed

After successful test payment, Stripe fires `checkout.session.completed` to:
```
POST https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod/webhooks/stripe
```

### Expected Processing

1. Lambda receives event
2. Signature verification passes (real Stripe-signed event)
3. Event type: `checkout.session.completed`
4. Metadata extracted: `company_id=tog_and_dogs`, `request_id=test_payment_validation_12k`, `payment_type=booking`
5. Idempotency check: new event → process
6. Booking payment handler:
   - Updates request record: `payment_status = paid`
   - Updates request record: `stripe_payment_intent_id = pi_...`
   - Updates request record: `payment_completed_at = <ISO timestamp>`
7. Billing ledger event written:
   - `PK: BILLING#tog_and_dogs`
   - `SK: EVENT#evt_...`
   - `event_type: checkout.session.completed`
   - `payment_type: booking`
   - `request_id: test_payment_validation_12k`
8. Entitlement cache invalidated for `tog_and_dogs`
9. Returns 200 to Stripe

---

## 8. Verification Checks

### 8.1 Stripe Dashboard

| Check | Expected |
|-------|----------|
| Checkout Session status | `complete` |
| Payment Intent status | `succeeded` |
| Amount | $50.00 |
| Metadata.company_id | `tog_and_dogs` |
| Metadata.request_id | `test_payment_validation_12k` |
| Metadata.payment_type | `booking` |
| Webhook delivery status | ✅ Delivered (200 response) |

### 8.2 CloudWatch Logs

| Check | Expected Log Pattern |
|-------|---------------------|
| Event received | `STRIPE_WEBHOOK_RECEIVED: type=checkout.session.completed, id=evt_...` |
| Event processed | `STRIPE_WEBHOOK_PROCESSED: type=checkout.session.completed, id=evt_..., company=tog_and_dogs` |
| No errors | Zero `BILLING ERROR` or `SECURITY` entries |
| No duplicates | Zero `STRIPE_WEBHOOK_DUPLICATE` entries |

### 8.3 DynamoDB (Read-Only Verification)

| Record | Field | Expected Value |
|--------|-------|----------------|
| `REQ#test_payment_validation_12k` | `payment_status` | `paid` |
| `REQ#test_payment_validation_12k` | `stripe_checkout_session_id` | `cs_test_...` |
| `REQ#test_payment_validation_12k` | `stripe_payment_intent_id` | `pi_...` |
| `REQ#test_payment_validation_12k` | `payment_completed_at` | ISO timestamp |
| `BILLING#tog_and_dogs / EVENT#evt_...` | `event_type` | `checkout.session.completed` |
| `BILLING#tog_and_dogs / EVENT#evt_...` | `payment_type` | `booking` |
| `BILLING#tog_and_dogs / EVENT#evt_...` | `processing_status` | `completed` |

---

## 9. Failure Handling

### Checkout Session Creation Fails

| Failure | Likely Cause | Action |
|---------|--------------|--------|
| 403 from API Gateway | Invalid/expired Cognito token | Re-authenticate |
| 400 from handler | Missing request_id, invalid amount | Fix input |
| 500 from handler | Stripe API error (key missing/invalid) | Check STRIPE_SECRET_KEY env var |
| Request not found | Test record doesn't exist | Create test record first |
| Tenant ownership error | company_id mismatch | Verify test record has `company_id = tog_and_dogs` |

### Webhook Signature Fails

| Failure | Likely Cause | Action |
|---------|--------------|--------|
| 401 from Lambda | STRIPE_WEBHOOK_SECRET mismatch | Re-check terraform.tfvars value vs Stripe Dashboard |
| Timestamp too old | Clock skew or delayed delivery | Check Lambda logs for timestamp details |

### Webhook Processes But DynamoDB Update Fails

| Failure | Likely Cause | Action |
|---------|--------------|--------|
| ConditionalCheckFailed | Request record doesn't exist | Verify test record was created |
| Missing company_id in metadata | Checkout session created without metadata | Check payment-session handler metadata assignment |
| Unknown tenant | company_id in metadata doesn't match a TENANT record | Verify TENANT#tog_and_dogs exists |

### Duplicate Webhook Delivery

- Expected behavior: second delivery is skipped (idempotency check passes)
- Log shows: `STRIPE_WEBHOOK_DUPLICATE: event=evt_... already processed`
- No second DynamoDB update occurs

### No Webhook Delivered

- Check Stripe Dashboard → Webhooks → endpoint → Recent deliveries
- If "pending" or "failed": check endpoint URL, Lambda timeout, API Gateway health
- If no delivery shown: wait up to 60 seconds; Stripe may batch

---

## 10. Cleanup / Post-Validation

### Option A: Leave Test Record As-Is (Recommended)

- Test request remains with `payment_status = paid` and `is_test_booking = true`
- Clearly identifiable as test data
- No cleanup needed unless it interferes with admin UI

### Option B: Mark as Voided

- Update test request: `payment_status = voided_test`
- Add note: `"12K sandbox validation complete — test data only"`
- Requires a DynamoDB write (needs approval)

### Option C: Delete Test Records

- Delete `REQ#test_payment_validation_12k`
- Delete `BILLING#tog_and_dogs / EVENT#evt_...`
- **Only if Matthew explicitly approves**
- Do NOT delete real customer/tenant records

### Recommendation

**Leave as-is (Option A)** unless the test record shows in Ryan's admin UI. The `is_test_booking: true` flag should allow filtering.

---

## 11. Required Inputs

### From Matthew (Before Execution)

| Input | Purpose |
|-------|---------|
| Approval to create/use test request record | Test data strategy |
| Confirm test request_id to use (or approve new creation) | Endpoint call |
| Confirm admin Cognito auth method | Token retrieval |
| Approval to execute DynamoDB writes via webhook | Payment status update |

### From AG (During Execution)

| Input | Purpose |
|-------|---------|
| Valid Cognito JWT for admin account | API authentication |
| Stripe test card details (standard) | Checkout payment |
| CloudWatch log group name | Verification |

---

## 12. Execution Sequence

| Step | Actor | Action |
|------|-------|--------|
| 1 | Matthew | Approve test data strategy and grant execution approval |
| 2 | AG | Create or locate test request record (if needed) |
| 3 | AG | Retrieve admin Cognito token |
| 4 | AG | Call POST /admin/payment-session with test request |
| 5 | AG/Matthew | Open Checkout URL in browser |
| 6 | AG/Matthew | Complete payment with test card 4242... |
| 7 | (Automatic) | Stripe fires checkout.session.completed webhook |
| 8 | AG | Verify CloudWatch logs show successful processing |
| 9 | AG | Verify DynamoDB request record: payment_status = paid |
| 10 | AG | Verify billing ledger event record exists |
| 11 | AG | Report full validation results |
| 12 | AG | Commit closeout doc (if successful) |

---

## 13. Success Criteria

The sandbox validation is successful when:

1. ✅ Payment-session endpoint returns a valid Checkout URL
2. ✅ Stripe Checkout page loads with correct amount/description
3. ✅ Test card payment succeeds
4. ✅ Webhook delivered to Lambda with 200 response
5. ✅ Signature verification passes
6. ✅ Request record `payment_status` updated to `paid`
7. ✅ Billing ledger event written with correct metadata
8. ✅ No errors in CloudWatch
9. ✅ No real customer records affected
10. ✅ No live Stripe mode or real charges

---

## 14. What This Document Does NOT Authorize

- ❌ Executing the validation (requires separate approval)
- ❌ Writing to DynamoDB (planned but requires approval)
- ❌ Activating Stripe live mode
- ❌ Using real customer data
- ❌ Charging real payment methods
- ❌ Modifying code
- ❌ Terraform changes
- ❌ Frontend/mobile/EAS/TestFlight changes
- ❌ Cognito/Postmark/Google Calendar changes
- ❌ Deleting production records

This is a planning document only. Execution requires Matthew's explicit approval.
