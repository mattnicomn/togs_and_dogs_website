# Release 12Q: Admin Payment Link UX and Client Payment Workflow Plan

**Status:** Planning
**Priority:** Medium-High (bridges backend Stripe foundation to admin usability)
**Risk to Production:** None (planning only)
**Terraform Required:** No
**Code Changes:** None
**Scope:** Plan the admin-facing payment controls, status display, and client payment delivery

---

## 1. Current State

### Backend (Complete)

| Capability | Status |
|------------|--------|
| POST /admin/requests/{requestId}/payment-session | ✅ Deployed |
| Stripe Checkout Session creation | ✅ Card-only, correct redirect domain |
| Webhook: checkout.session.completed | ✅ Updates payment_status to `paid` |
| Duplicate payment guard (12O/12P) | ✅ Blocks session for paid/refunded/waived |
| Billing event ledger | ✅ Records all payment events |
| Sandbox end-to-end validated | ✅ 12L/12N confirmed working |

### Frontend (Current CareCard.jsx)

The admin request detail card already has a "Payment Status" section:
- Displays `payment_status` field (dropdown in edit mode)
- Current dropdown options: Not Quoted, Quote Sent, Payment Pending, Accepted, Deposit Paid
- These are **legacy manual-entry values** that predate Stripe integration
- No "Generate Payment Link" button exists
- No Stripe Checkout URL display
- No payment amount input tied to Stripe

---

## 2. Recommended UX Placement

### Where Payment Controls Should Live

**Primary location:** Admin request detail card (CareCard.jsx) — "Pricing & Payment" section (already exists at bottom of card).

### New Payment Controls to Add

| Control | Location | Condition |
|---------|----------|-----------|
| "Generate Payment Link" button | Pricing & Payment section | Only when payment_status allows (null, failed, expired, payment_link_sent) |
| Amount input ($) | Inline with generate button | Pre-fill from `quote_amount` if available |
| Payment link display (copy-to-clipboard) | Below button after generation | Show when `stripe_payment_url` exists |
| "Resend Payment Link" button | Replace generate button | Show when payment_status = payment_link_sent |
| Payment status badge | Request list + detail header | Always visible |
| Paid confirmation | Detail card | Show when payment_status = paid (green badge + amount) |

### Where Payment Controls Should NOT Live

- Do NOT add to the intake form (client-facing, no payment at submission time)
- Do NOT add to the mobile staff app (staff don't handle payments)
- Do NOT add to the client portal yet (client receives link via email/copy)

---

## 3. Payment Status Display Rules

### Badge Rendering

| payment_status | Badge | Color | Label |
|----------------|-------|-------|-------|
| `null` / not set | None shown | — | — |
| `payment_link_sent` | 🟡 | Yellow/amber | "Payment Pending" |
| `paid` | 🟢 | Green | "Paid — $XX.XX" |
| `payment_failed` | 🔴 | Red | "Payment Failed" |
| `expired` | ⚪ | Gray | "Link Expired" |
| `refunded` | 🔵 | Blue | "Refunded" |
| `waived` | ⚪ | Gray italic | "Waived" |

### Request List Column

Add a small payment badge/icon next to each request in the admin list view:
- 🟡 dot = payment pending
- 🟢 dot = paid
- 🔴 dot = failed
- No dot = no payment requested

---

## 4. Admin Actions by Status

| Current payment_status | Available Actions |
|------------------------|-------------------|
| `null` / not set | "Generate Payment Link" (enter amount) |
| `payment_link_sent` | "Copy Link", "Resend" (creates new session), view amount |
| `paid` | View paid amount, view date, view receipt (link to Stripe) — NO generate |
| `payment_failed` | "Generate Payment Link" (retry) |
| `expired` | "Generate Payment Link" (retry) |
| `refunded` | View refund info — NO generate (blocked by 12O guard) |
| `waived` | View waiver note — NO generate (blocked by 12O guard) |

### "Generate Payment Link" Button Behavior

1. Admin clicks "Generate Payment Link"
2. Modal or inline form appears with:
   - Amount field (pre-filled from `quote_amount` if available, editable)
   - Description field (optional, pre-filled with service type + dates)
   - "Generate" confirmation button
3. Frontend calls `POST /admin/requests/{requestId}/payment-session` with `amount_cents` and `client_id`
4. On success (200): display the Checkout URL with "Copy Link" button
5. On 409 (already paid/refunded/waived): show error message inline
6. On 403: show "Access denied"
7. On 500: show "Stripe error — try again"

### "Resend" Button Behavior

Same as "Generate" — creates a fresh Checkout Session (old one may have expired). The 12O guard allows this because `payment_link_sent` is not in the blocked list.

---

## 5. Amount Entry Behavior

### Current Phase (Manual Entry)

- Admin enters the dollar amount manually
- Frontend converts to cents before API call: `amount_cents = Math.round(dollars * 100)`
- Pre-fill from `quote_amount` if the field exists on the request record

### Validation Rules

| Rule | Frontend | Backend |
|------|----------|---------|
| Required | ✅ Disable button if empty | ✅ 400 if missing |
| Positive integer (cents) | ✅ Validate > 0 | ✅ 400 if ≤ 0 |
| Minimum: $1.00 (100 cents) | ✅ Min input | ✅ Could add (or defer) |
| Maximum: $10,000 (1,000,000 cents) | ✅ Max input | ⚠️ Consider adding |
| Must be number, not string/bool | — | ✅ Already validated in 12G |

### Future: Auto-Calculation

A future release may auto-calculate amount from:
- Service type × duration × rate
- Multi-day visit count × per-visit price
- Package/discount rules

For now: admin enters manually. This matches Ryan's current quoting workflow.

---

## 6. Client Communication Workflow

### Phase 1 (12R): Admin Copies Link Manually

- After generating a payment link, admin sees the Checkout URL
- Admin copies it and sends to client via their preferred channel (text, email, portal message)
- No automated email yet

### Phase 2 (12S): Automated Email Notification

- After generating a payment link, system automatically sends a branded email to client
- Uses Postmark template
- Includes: amount, service description, "Pay Now" button → Checkout URL
- Requires new notification template and template ID in Lambda env

### Recommendation

**12R = admin UI only (copy link manually).** Email sending is Phase 2 (12S). This is cleaner because:
- Reduces 12R scope to pure frontend
- Email template design needs review
- Avoids accidental emails to real clients during sandbox testing
- Admin can still send links manually via text/email outside the app

---

## 7. Frontend/Backend Integration

### API Call from Frontend

```javascript
// When admin clicks "Generate Payment Link":
const response = await fetch(
  `${API_BASE}/admin/requests/${requestId}/payment-session`,
  {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${cognitoToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      request_id: requestId,
      client_id: clientId,
      amount_cents: Math.round(amountDollars * 100),
    }),
  }
);
```

### Response Handling

| Status | Action |
|--------|--------|
| 200 | Show success, display payment URL with copy button |
| 400 | Show validation error message |
| 403 | Show "Access denied" |
| 404 | Show "Request not found" |
| 409 | Show "Payment already received" or relevant blocked message |
| 500 | Show "Error creating payment session — try again" |

### After Successful Generation

- Update local state: `payment_status = "payment_link_sent"`
- Show Checkout URL with "Copy to Clipboard" button
- Optionally show amount and expiry time (30 min)
- Refresh request detail to reflect new payment fields

---

## 8. UX Safeguards

### Sandbox Mode Indicators

While in sandbox/test mode:
- Show a small "SANDBOX" label near the payment controls
- Use orange/amber accent to distinguish from future live payments
- Remove sandbox label only when live Stripe is activated (future release)

### Confirmation Modal

Before generating a payment link:
```
┌────────────────────────────────────┐
│ Generate Payment Link              │
│                                    │
│ Client: Brea Rockwell              │
│ Amount: $75.00                     │
│ Service: Dog Walking (5 visits)    │
│                                    │
│ This will create a Stripe Checkout │
│ session. The client will need to   │
│ complete payment within 30 minutes.│
│                                    │
│ [Cancel]  [Generate Link]          │
└────────────────────────────────────┘
```

### Warnings

- If `is_test_booking: true` → show "⚠️ Test booking" warning
- If request status is `archived` or `deleted` → show warning, still allow (admin override)
- If `payment_link_sent` already → show "Previous link may still be active. Generate a new one?"

---

## 9. Phased Implementation Sequence

| Release | Scope | Type |
|---------|-------|------|
| **12Q** | Planning (this document) | Docs |
| **12R** | Admin UI: payment controls in CareCard, amount input, generate button, status badges, copy link | Frontend |
| **12S** | Client email: Postmark payment request template, automated send after generation | Backend + template |
| **12T** | Payment success/cancel frontend pages | Frontend |
| **Future** | Owner subscription billing UI | Separate track |

### 12R Scope (Next Implementation)

Files likely to change:
- `web/src/components/CareCard.jsx` — add payment controls section
- `web/src/components/MasterScheduler.jsx` — add payment badge to request list (optional)
- Possibly a new `PaymentControls.jsx` component if the logic is complex enough to extract

### 12S Scope (Email Notification)

- New Postmark template: "Payment Request" 
- Backend: trigger notification after successful payment-session creation
- Requires template ID in Lambda env vars
- Audit trail: write to notification ledger

---

## 10. Legacy Payment Status Field Reconciliation

### Problem

CareCard.jsx currently has a manual dropdown with values:
- Not Quoted, Quote Sent, Payment Pending, Accepted, Deposit Paid

These are **pre-Stripe legacy values** stored in the same `payment_status` field.

### Recommendation

- **Do NOT remove the legacy dropdown** (may be used for non-Stripe manual quotes)
- **Add Stripe payment controls as a separate section** below the legacy dropdown
- When Stripe payment is active (stripe_checkout_session_id exists), the Stripe status takes visual priority
- Legacy values remain for requests that use manual quoting without Stripe

### Future Cleanup

A later release can migrate legacy `payment_status` values to a separate `quote_status` field, keeping `payment_status` exclusively for Stripe-backed states. Not in scope for 12R.

---

## 11. Validation Plan

### Frontend Testing (12R)

| Test | Method |
|------|--------|
| Generate button visible for unpaid request | Manual click-through |
| Generate button hidden for paid request | Manual click-through |
| Amount input validates positive numbers | Manual + unit test |
| 409 error displays correctly | Mock API response |
| Copy-to-clipboard works | Manual |
| Payment badge renders correctly per status | Visual review |
| Sandbox label shown | Visual review |

### Sandbox End-to-End (After 12R Deploy)

1. Load admin dashboard
2. Select an unpaid test request
3. Click "Generate Payment Link"
4. Enter amount ($50.00)
5. Confirm → see Checkout URL
6. Copy link → open in browser → see card-only Checkout
7. Verify 409 when clicking "Generate" on the same request after payment

---

## 12. What This Document Does NOT Authorize

- ❌ Implementing frontend changes
- ❌ Modifying CareCard.jsx or any component
- ❌ Creating Checkout Sessions
- ❌ Making payments
- ❌ Writing to DynamoDB
- ❌ Modifying Terraform
- ❌ Deploying anything
- ❌ Sending emails to clients
- ❌ Activating Stripe live mode
- ❌ Mobile/EAS/TestFlight changes
- ❌ Committing secrets

This is a planning document only. Frontend implementation requires separate explicit approval (Release 12R).
