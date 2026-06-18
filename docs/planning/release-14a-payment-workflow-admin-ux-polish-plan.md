# Release 14A: Payment Workflow Admin UX Polish Plan

**Status:** Planning
**Priority:** Medium (improves admin experience; safe to build while EIN is pending)
**Risk to Production:** None (planning only)
**Terraform Required:** No
**Code Changes:** None
**Scope:** Plan UX improvements for the admin payment workflow before live payments go active

---

## 1. Context

Stripe live activation is blocked pending EIN. The sandbox payment workflow is fully validated. This plan identifies admin/client UX polish that can be safely implemented now, so the experience is polished before real clients ever see a payment link.

---

## 2. Admin Request List Improvements

### Search and Filter

| Feature | Priority | Rationale |
|---------|----------|-----------|
| Search by client name | High | Admin needs to quickly find a specific client's booking |
| Search by pet name | Medium | Useful when client has multiple bookings |
| Search by request ID | Low | Rarely used, but helpful for support lookups |
| Search by email | Medium | Useful for payment follow-up |
| Payment status filter dropdown | High | Admin needs to see all unpaid / all paid at a glance |

### Payment Status Filter Options

| Filter Value | Shows |
|--------------|-------|
| All | All requests (default) |
| Unpaid | `payment_status` is null/not set |
| Payment Link Sent | `payment_status = payment_link_sent` |
| Paid | `payment_status = paid` |
| Waived | `payment_status = waived` |
| Failed/Expired | `payment_status = payment_failed` or `expired` |

### Payment Chips in List Rows

Small colored badges next to each request in the list:

| Status | Chip | Color |
|--------|------|-------|
| No payment needed | (none) | — |
| Payment link sent | "💳 Pending" | Amber |
| Paid | "✓ Paid" | Green |
| Failed | "✗ Failed" | Red |
| Waived | "— Waived" | Gray |

### Sorting

| Sort Option | Direction |
|-------------|-----------|
| Date (newest first) | Default |
| Payment status (unpaid first) | Useful for follow-up |
| Client name (A–Z) | Standard |
| Amount (high to low) | Useful for revenue view |

---

## 3. CareCard Payment Workflow Polish

### Current State Issues

| Issue | Improvement |
|-------|-------------|
| "Generate Payment Link" button could be unclear for first-time use | Add brief helper text: "Creates a Stripe Checkout link for this booking" |
| "Send Payment Email" purpose may be unclear | Add subtitle: "Emails the payment link directly to the client" |
| No visibility into send history | Show "Last emailed: {date} to {email}" and "Sent {count} time(s)" |
| Disabled states have no explanation | Add tooltip/helper: "Payment already received" or "Generate a link first" |
| Paid state could be more celebratory | Larger green badge with amount + date, maybe a ✓ icon |

### Proposed CareCard Payment Section States

**State: Unpaid (no link yet)**
```
━━━ Pricing & Payment ━━━
⚠️ Sandbox Mode

Amount: [$___.__] (input)
[Generate Payment Link]
  ↳ "Creates a secure Stripe Checkout link for this booking"
```

**State: Payment Link Sent**
```
━━━ Pricing & Payment ━━━
⚠️ Sandbox Mode

Status: 🟡 Payment Link Sent
Amount: $75.00
Link: [https://checkout.stripe.com/...] [Copy]

[Test Payment Page]  [Send Payment Email]
  ↳ "Emails the link to brearockwell@gmail.com"

Last emailed: Jun 17, 2026 at 7:51 PM (2 times)
```

**State: Paid**
```
━━━ Pricing & Payment ━━━

✅ Payment Received
Amount: $75.00
Paid: Jun 18, 2026 at 10:15 AM
Method: Stripe card payment

No further payment actions available.
```

---

## 4. Payment Workflow Operations Guide

### When to Generate a Payment Link

- After reviewing and approving a booking request
- After confirming the service amount with the client (if not fixed pricing)
- Before or after scheduling — payment doesn't gate scheduling in v1

### When to Send the Payment Email

- After generating the link, if the client expects email communication
- If you prefer, copy the link and send it manually via text/phone instead
- Do NOT resend more than 2–3 times without client contact first

### When to Follow Up

- If `payment_link_sent` for more than 48 hours with no payment
- Contact client to confirm they received the email and ask if they need help
- Offer to resend if the link expired

### When NOT to Resend

- If client has already paid (status will show Paid)
- If you just sent the email in the last few minutes (cooldown applies)
- If the client explicitly said they want to cancel the booking

### What to Do If Client Reports Payment Failed

1. Ask if they received an error message
2. Suggest trying a different card
3. Generate a new payment link (the old one may have expired)
4. If the issue persists, contact support

---

## 5. Customer-Facing UX Ideas

### Payment Success Page (`/payment/success`)

Currently this route may 404 or show a generic page. Proposed content:

```
✓ Payment Received!

Thank you for your payment. Your booking is confirmed.

What happens next:
- Your pet sitter will be assigned (if not already)
- You'll receive a confirmation email with visit details
- Contact us if you have questions

[Return to Home]
```

### Payment Cancel Page (`/payment/cancel`)

```
Payment Not Completed

Your booking is still active, but payment has not been received.
If you'd like to complete payment later, check your email for the payment link
or contact us to request a new one.

[Return to Home]  [Contact Support]
```

### Payment Email Wording Improvements

| Current | Proposed Improvement |
|---------|---------------------|
| "Pay Secure Now" button text | Consider "Complete Payment" or "Pay Now — $XX.XX" (shows amount on button) |
| Generic service description | Include pet name + date range for clarity |
| No footer contact info | Add: "Questions? Reply to this email or call [phone]" |

---

## 6. Risk/Priority Scoring

### Must-Have Before Live Payments

| Item | Reason |
|------|--------|
| Payment status filter in admin list | Admin needs to track unpaid bookings |
| Paid state read-only display in CareCard | Prevents confusion about generating duplicate links |
| Disabled-state explanations | Admin shouldn't guess why a button is grayed out |
| Success/cancel page content | Client shouldn't see a 404 after paying |

### Nice-to-Have After Live Launch

| Item | Reason |
|------|--------|
| Full search (name/email/ID) | Useful at scale, low urgency with few bookings |
| Send count / last-sent timestamp | Helpful but not blocking |
| Amount sorting | Low priority until volume grows |
| Email copy improvements | Can iterate post-launch |

---

## 7. Recommended Release Breakdown

| Release | Scope | Priority | EIN Required? |
|---------|-------|----------|---------------|
| **14B** | Admin search + payment status filter + list chips | High | ❌ No |
| **14C** | CareCard payment section copy/states/helper text polish | Medium | ❌ No |
| **14D** | Payment operations quick-reference guide (admin docs) | Medium | ❌ No |
| **14E** | Success/cancel page content + email copy refinement | High | ❌ No |

All of these are safe to implement in sandbox mode while waiting for EIN.

---

## 8. Implementation Notes

### Files Likely Affected

| Release | Files |
|---------|-------|
| 14B | `web/src/components/AdminDashboard.jsx` or `MasterScheduler.jsx` |
| 14C | `web/src/components/CareCard.jsx` |
| 14D | `docs/operations/payment-workflow-quick-reference.md` (new) |
| 14E | `web/src/components/PaymentSuccess.jsx` (new), `web/src/components/PaymentCancel.jsx` (new), email template updates |

### No Backend Changes Expected

All items are frontend-only or documentation. No API changes, no Terraform, no Lambda modifications needed.

---

## 9. What This Document Does NOT Authorize

- ❌ Writing code
- ❌ Deploying anything
- ❌ Stripe API calls or Dashboard changes
- ❌ AWS/Terraform changes
- ❌ DynamoDB writes
- ❌ Sending emails
- ❌ Cognito/Postmark/Google Calendar changes
- ❌ Mobile/EAS/TestFlight changes
- ❌ Committing secrets

This is a planning document only. Each follow-up release (14B–14E) requires separate approval.
