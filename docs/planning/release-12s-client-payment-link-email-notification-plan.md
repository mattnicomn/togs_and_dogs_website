# Release 12S: Client Payment Link Email Notification Plan

**Status:** Planning
**Priority:** Medium (enhances payment workflow but admin can manually copy/send links today)
**Risk to Production:** None (planning only)
**Terraform Required:** No
**Code Changes:** None
**Scope:** Plan the client-facing email notification for payment links

---

## 1. Current State

### What Works Today

- Admin generates a Stripe Checkout payment link via CareCard UI
- Link is displayed in the admin interface with a "Copy Link" button
- Admin manually sends the link to the client (text, email, verbal)
- Webhook processes payment and updates request status

### What's Missing

- No automated email to the client after payment link generation
- Admin must copy the link and manually deliver it every time
- No audit trail for "payment link sent to client via email"

---

## 2. When Should Email Be Sent?

### Option A: Automatic After Link Generation (Not Recommended)

- Email fires immediately when admin clicks "Generate Payment Link"
- Risk: admin may want to review the link first, adjust amount, or not send yet
- Risk: accidental email to client during sandbox testing

### Option B: Separate "Send Payment Email" Button (Recommended MVP)

- Admin generates link → reviews it → explicitly clicks "Send Payment Email"
- Two-step process prevents accidental sends
- Admin can copy the link without emailing if they prefer text/verbal delivery
- Clear audit trail: "admin chose to email this link at this time"

### Option C: Combined with Checkbox (Future Enhancement)

- "Generate Payment Link" dialog includes an optional checkbox: "☐ Email link to client"
- Checkbox unchecked by default during sandbox
- Checked by default after live mode activation
- Nice UX but more complex — defer to later

### Recommendation: Option B for MVP

Generate link and send email are separate explicit actions. This is safest for sandbox testing and gives admin full control.

---

## 3. Postmark Email Template

### Template Name

`payment-request`

### Subject Line

```
Payment Required — Your Booking with Togs & Dogs
```

### Template Variables

| Variable | Source | Example |
|----------|--------|---------|
| `client_name` | Request record `client_name` | "Brea Rockwell" |
| `pet_names` | Request record `pet_names` or `pet_name` | "Luna & Max" |
| `service_type` | Request record `service_type` (formatted) | "Dog Walking" |
| `start_date` | Request record `start_date` (formatted) | "July 15, 2025" |
| `amount_display` | Derived from `payment_amount_cents` | "$75.00" |
| `payment_url` | Request record `stripe_payment_url` | Stripe Checkout URL |
| `business_name` | Constant or tenant config | "Togs & Dogs" |
| `business_email` | Constant or tenant config | "support@toganddogs.com" |
| `expiry_note` | Constant | "within 30 minutes of opening" |

### Email Body (HTML Template Concept)

```
Hi {client_name},

Your booking has been approved! Please complete payment to confirm your service.

━━━━━━━━━━━━━━━━━━━━━━━━━
Service: {service_type}
Pet(s): {pet_names}
Date: {start_date}
Amount: {amount_display}
━━━━━━━━━━━━━━━━━━━━━━━━━

[Pay Now →] {payment_url}

Payment must be completed {expiry_note} of opening the link.
If the link has expired, please contact us and we'll send a new one.

Questions? Reply to this email or contact us at {business_email}.

Thanks,
{business_name}
```

### Sandbox Mode Addition

While in sandbox/test mode, prepend a warning banner:

```
⚠️ TEST MODE — This is a sandbox payment link. Do not use a real card.
Use test card: 4242 4242 4242 4242
```

This banner should be removed when live mode is activated.

---

## 4. Audit/Logging Requirements

### Notification Ledger Entry

Follow existing notification ledger pattern (from Release 6I):

```json
{
  "PK": "NOTIF#{message_id}",
  "SK": "LEDGER#{timestamp}",
  "notification_type": "payment_request",
  "recipient_email": "brearockwell@gmail.com",
  "company_id": "tog_and_dogs",
  "request_id": "abc123",
  "stripe_checkout_session_id": "cs_test_...",
  "payment_amount_cents": 7500,
  "sent_at": "2025-07-01T10:00:00Z",
  "sent_by": "mattnicomn10@gmail.com",
  "delivery_status": "sent",
  "postmark_message_id": "msg_...",
  "template_alias": "payment-request"
}
```

### Request Record Update

After email is sent, update the request record:

```json
{
  "payment_email_sent_at": "2025-07-01T10:00:00Z",
  "payment_email_sent_by": "mattnicomn10@gmail.com",
  "payment_email_recipient": "brearockwell@gmail.com"
}
```

---

## 5. Backend/API Design

### Endpoint

```
POST /admin/requests/{requestId}/send-payment-email
```

### Authorization

- Owner or Admin role only (Cognito-authenticated)
- Tenant ownership validated

### Request Body

```json
{
  "client_id": "client_xyz"
}
```

No additional fields needed — amount, payment URL, client email are all on the request record already.

### Response (200)

```json
{
  "message": "Payment email sent successfully",
  "recipient": "brearockwell@gmail.com",
  "postmark_message_id": "msg_..."
}
```

### Guard Logic (Before Sending)

| Check | Failure Response |
|-------|-----------------|
| Request not found | 404 |
| Cross-tenant access | 403 |
| No `stripe_payment_url` on request | 400: "No payment link exists — generate one first" |
| `payment_status` is `paid` | 409: "Payment already received" |
| `payment_status` is `refunded` or `waived` | 409: "Payment status is {status}" |
| Client has no email address | 400: "Client has no email on file" |
| Postmark send fails | 500: "Email delivery failed" |

### Idempotency / Dedup

- Allow re-sending (admin may resend if client didn't receive or link expired)
- Each send creates a new ledger entry (not deduplicated — admin explicitly chose to send)
- Rate limit: maximum 3 sends per request per hour (prevent accidental spam)

---

## 6. Frontend UX

### Button Placement

In CareCard "Pricing & Payment" section, when `payment_status = payment_link_sent`:

```
┌─────────────────────────────────────────────┐
│ Stripe Payment Status: [Link Sent]          │
│ Payment Amount: $75.00                      │
│                                             │
│ Payment Link:                               │
│ ┌─────────────────────────────────────────┐ │
│ │ https://checkout.stripe.com/c/pay/cs... │ │
│ │                          [Copy Link]    │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ [Test Payment Page]  [Send Payment Email]   │
│                                             │
│ ⚠️ SANDBOX: Do not send to real clients    │
└─────────────────────────────────────────────┘
```

### "Send Payment Email" Button States

| State | Button |
|-------|--------|
| payment_link_sent + client has email | Enabled: "Send Payment Email" |
| payment_link_sent + no client email | Disabled: "No client email on file" |
| paid | Hidden (no send needed) |
| No payment link yet | Hidden (must generate first) |
| Email recently sent (<5 min) | Disabled: "Email sent ✓" (with timestamp) |

### Confirmation Modal

```
┌────────────────────────────────────────────┐
│ Send Payment Email                          │
│                                             │
│ Recipient: brearockwell@gmail.com           │
│ Amount: $75.00                              │
│ Service: Dog Walking                        │
│                                             │
│ ⚠️ SANDBOX: This is a test email.          │
│ Do not send to real clients yet.            │
│                                             │
│ [Cancel]  [Send Email]                      │
└────────────────────────────────────────────┘
```

### Success/Error Banners

- Success: "✓ Payment email sent to brearockwell@gmail.com"
- Error: "Failed to send email: {error message}"

---

## 7. Validation Plan

### Sandbox Testing Approach

1. Use Matthew-controlled recipient only (`mattnicomn10@gmail.com` or `mattnicomn10@yahoo.com`)
2. Do NOT send to real clients (Ryan's customers) until live mode is explicitly approved
3. Verify email arrives in inbox
4. Verify payment link in email is clickable and leads to Stripe Checkout
5. Verify notification ledger entry was written
6. Verify request record has `payment_email_sent_at` field

### Postmark Test/Sandbox Options

- Postmark supports a "Sandbox" server for testing without sending real emails
- Alternatively, use a real Postmark server but send only to Matthew-controlled addresses
- Confirm with Matthew which approach is preferred

### Test Sequence

| Step | Actor | Action |
|------|-------|--------|
| 1 | AG | Deploy backend endpoint + template |
| 2 | AG | Deploy frontend "Send Payment Email" button |
| 3 | Matthew | Open admin, generate payment link for test request |
| 4 | Matthew | Click "Send Payment Email" |
| 5 | Matthew | Confirm email arrives at controlled address |
| 6 | Matthew | Confirm link in email works (opens Checkout) |
| 7 | AG | Verify ledger/audit records |

---

## 8. Phased Implementation

| Release | Scope | Type |
|---------|-------|------|
| **12S** | Planning (this document) | Docs |
| **12T** | Backend: send-payment-email endpoint + Postmark template | Backend code |
| **12U** | Frontend: "Send Payment Email" button + confirmation modal | Frontend code |
| **12V** | Sandbox validation: end-to-end email delivery test | Integration test |
| **Future** | SMS support, auto-send option, live mode | Enhancement |

### 12T Scope (Backend)

- New handler route: `POST /admin/requests/{requestId}/send-payment-email`
- Postmark template: `payment-request`
- Guard logic (paid/refunded/waived/no-link/no-email checks)
- Notification ledger write
- Request record update (`payment_email_sent_at`)
- Unit tests

### 12U Scope (Frontend)

- "Send Payment Email" button in CareCard (payment_link_sent state)
- Confirmation modal
- Success/error banner
- Disabled states
- Sandbox warning

---

## 9. Non-Goals

| ❌ Item | Reason |
|---------|--------|
| SMS/text notification | Future enhancement |
| Auto-send on link generation | Too risky for MVP; admin should control |
| Email for subscription billing | Separate track |
| Email to Ryan's real clients | Not until live mode approved |
| Email template designer/editor | Use Postmark's built-in template system |
| Payment reminder emails | Future enhancement |
| Receipt email after payment | Stripe handles this natively |

---

## 10. What This Document Does NOT Authorize

- ❌ Writing code
- ❌ Creating Postmark templates
- ❌ Sending any emails
- ❌ Creating Checkout Sessions
- ❌ Making payments
- ❌ Writing to DynamoDB
- ❌ Modifying Terraform
- ❌ Deploying anything
- ❌ Stripe API calls
- ❌ Cognito changes
- ❌ Mobile/EAS/TestFlight changes
- ❌ Committing secrets

This is a planning document only. Backend implementation requires separate explicit approval (Release 12T).
