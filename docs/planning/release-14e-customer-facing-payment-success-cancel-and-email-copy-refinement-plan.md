# Release 14E: Customer-Facing Payment Success, Cancel, and Email Copy Refinement Plan

**Status:** Planning
**Priority:** Medium (polish before live payments)
**Risk to Production:** None (planning only)
**Terraform Required:** No
**Code Changes:** None
**Scope:** Plan copy improvements for existing success/cancel pages and payment email template

---

## 1. Existing Routes Confirmed

| Route | Component | Status |
|-------|-----------|--------|
| `/booking/:requestId/success` | `web/src/components/PaymentSuccess.jsx` | ✅ Deployed (12Z) |
| `/booking/:requestId/cancel` | `web/src/components/PaymentCancel.jsx` | ✅ Deployed (12Z) |

These are the correct routes. No new routes are needed.

---

## 2. Payment Success Page — Current vs Proposed

### Current Content (PaymentSuccess.jsx)

- ✓ Green checkmark icon
- "Payment Received!"
- "Thank you! Your payment has been successfully processed and recorded."
- Request ID displayed in code block
- Status badge: "Paid"
- Next steps:
  - "Our team is preparing for your pet's visits."
  - "Your booking details are now being finalized with our staff."
  - "You will receive an email confirmation once scheduling is complete."
- Button: "Go to My Bookings"

### Assessment

The existing content is already good. Minor refinements recommended:

### Proposed Improvements

| Item | Current | Proposed | Rationale |
|------|---------|----------|-----------|
| Next step #3 | "You will receive an email confirmation once scheduling is complete" | "You'll receive updates as your visits are scheduled and staff is assigned." | More accurate — scheduling may already be done |
| Support contact | Not mentioned | Add: "Questions? Contact us at [support email]" | Clients need a way to reach out |
| Request ID visibility | Shows raw UUID | Consider hiding or shortening — clients don't use request IDs | Less technical appearance |
| Scheduling caveat | Implies payment guarantees scheduling | Add small note: "Payment confirms your booking. Scheduling is handled by our team." | Avoids implying scheduling is automatic |

### Proposed Success Page Copy (Final)

```
✓ Payment Received!

Thank you! Your payment has been successfully processed.

[Request reference info — consider showing only last 8 chars or hiding entirely]
Status: Paid ✓

What Happens Next:
• Our team is preparing for your pet's visits.
• You'll receive updates as your visits are scheduled and staff is assigned.
• A receipt has been sent to your email from Stripe.

Questions? Contact us at [billing/support email to be confirmed].

[Go to My Bookings]
```

---

## 3. Payment Cancel Page — Current vs Proposed

### Current Content (PaymentCancel.jsx)

- × Red icon
- "Payment Cancelled"
- "The payment process was not completed. No charges were made."
- Request ID displayed
- Status badge: "Unpaid"
- Help section: "If you experienced an issue with payment, you can try again from the My Bookings portal or contact us directly at support@toganddogs.com for assistance."
- Button: "Return to My Bookings"

### Assessment

Good structure. A few refinements needed:

### Proposed Improvements

| Item | Current | Proposed | Rationale |
|------|---------|----------|-----------|
| Heading | "Payment Cancelled" | "Payment Not Completed" | Less alarming; "cancelled" implies intentional action |
| Support email | Hardcoded `support@toganddogs.com` | `[PENDING MATTHEW — use confirmed support email]` | Must match confirmed business inbox |
| Retry guidance | "try again from the My Bookings portal" | "Check your email for the payment link, or contact us for a new one." | More actionable — My Bookings may not have a pay button yet |
| Reassurance | None | Add: "Your booking is still active — we're holding your spot." | Reduces client anxiety |

### Proposed Cancel Page Copy (Final)

```
× Payment Not Completed

No charges were made. Your booking is still active.

[Request reference — shortened or hidden]
Status: Unpaid

What To Do:
• Check your email for the payment link — it may still be active.
• If the link has expired, contact us and we'll send a new one.
• Your booking spot is being held while we await payment.

Need help? Contact us at [billing/support email to be confirmed].

[Return to My Bookings]
```

---

## 4. Payment Email Template — Current vs Proposed

### Current Template (templates.py `payment_link_email`)

- Subject: "Payment Link for {pet_names}'s Care — Tog & Dogs"
- Greeting: "Hi {client_name}"
- Context: service, pet, date, amount
- CTA button: "Pay Securely Now"
- Expiry note: "Stripe payment links expire in 24 hours"
- Support: "contact us at {business_email}"
- Sandbox warning: conditional on `is_sandbox` flag
- Footer: "© 2026 {business_name} Pet Sitting / Secure Online Payments via Stripe"

### Assessment

Template is well-structured and professional. Minor refinements:

### Proposed Improvements

| Item | Current | Proposed | Rationale |
|------|---------|----------|-----------|
| Expiry note | "expire in 24 hours" | "expire 30 minutes after you open the link" | More accurate — Stripe sessions expire 30 min after opening, not 24h after creation |
| Button text | "Pay Securely Now" | Keep or change to "Complete Payment — {amount_display}" | Shows amount on button for clarity |
| Post-payment expectation | Not mentioned | Add brief line: "After payment, you'll see a confirmation page and receive a receipt via email." | Sets expectations |
| Footer year | Hardcoded "2026" | Consider dynamic or remove year | Future-proofing |
| Support email | `support@toganddogs.com` (hardcoded in some contexts) | Use `{business_email}` variable consistently | Single source of truth |
| Reply-to behavior | "reply to this email" | Clarify only if Postmark reply-to is configured | Don't promise reply-to if it's not monitored |

### Proposed Email Copy (Key Changes)

**Subject:** No change needed — "Payment Link for {pet_names}'s Care — Tog & Dogs" is clear.

**Body additions/changes:**
```
After paying:
- You'll see a confirmation page
- A receipt will be sent to your email from Stripe
- Our team will finalize your scheduling

Note: The payment link is active for 30 minutes after you open it.
If it expires, contact us and we'll send a fresh link.
```

**Sandbox warning:** Already conditional on `STRIPE_ENV`. No change needed — 13B behavior handles this correctly.

---

## 5. Support Contact Placeholder

All three surfaces (success page, cancel page, email) reference a support/billing email.

| Location | Current Value | Needed |
|----------|---------------|--------|
| PaymentCancel.jsx | `support@toganddogs.com` (hardcoded) | Confirm or update |
| PaymentSuccess.jsx | Not shown | Add with placeholder |
| Email template | `{business_email}` (variable, default: `support@toganddogs.com`) | Confirm actual inbox exists |

**Action for Matthew:** Confirm whether `support@toganddogs.com` is a real monitored inbox, or provide the correct address. If not configured yet, document as pending.

---

## 6. Policy Alignment

The success/cancel pages and email should align with the draft payment policy (13D.1/13D.2):

| Policy Point | Where to Reflect |
|-------------|------------------|
| 30-min link expiry | Email template (already mentions); cancel page (add "link may have expired") |
| No charges on cancel | Cancel page (already says "No charges were made") ✅ |
| Contact for refund | Cancel page + email footer |
| Receipt from Stripe | Success page (add mention) |

---

## 7. Files to Change in Implementation (14F)

| File | Changes |
|------|---------|
| `web/src/components/PaymentSuccess.jsx` | Update next-steps copy, add support contact, optionally shorten request ID display |
| `web/src/components/PaymentCancel.jsx` | Change heading, update help text, add reassurance, update support email |
| `src/backend/common/notifications/templates.py` | Update expiry note wording, optionally add post-payment expectation, verify support email variable |

### No New Files Needed

All changes are edits to existing components/templates.

---

## 8. Validation Plan

### After 14F Implementation

1. Build frontend (`npm run build`) — confirm no errors
2. Visual check: open `/booking/test-id/success` locally — verify new copy renders
3. Visual check: open `/booking/test-id/cancel` locally — verify new copy renders
4. Deploy frontend (S3 sync + CloudFront invalidation)
5. Matthew spot-checks both pages in production
6. For email: run one sandbox payment-email send to Matthew-controlled address and verify updated wording

### No Stripe/Payment Actions Needed

All validation is visual copy review — no actual payments or Checkout Sessions required.

---

## 9. Recommended Next Release

**14F — Payment Success/Cancel Page and Email Copy Implementation**

- Frontend: update PaymentSuccess.jsx + PaymentCancel.jsx
- Backend: update templates.py email copy (optional — could defer to separate release)
- Deploy frontend
- Verify visually
- No Stripe/Terraform/backend deployment needed unless email template changes

---

## 10. What This Document Does NOT Authorize

- ❌ Writing code
- ❌ Deploying anything
- ❌ Modifying templates
- ❌ Sending emails
- ❌ Stripe/AWS/Terraform changes
- ❌ DynamoDB writes
- ❌ Cognito/Postmark configuration changes
- ❌ Mobile/EAS/TestFlight changes
- ❌ Committing secrets

This is a planning document only. Implementation requires separate approval (Release 14F).
