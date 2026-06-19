# Payment Workflow Quick Reference

> **Current Mode: SANDBOX** — Live payments are not active. Do not send payment links to real clients until live mode is approved.

---

## Payment Flow Overview

```
1. Request submitted by client or admin
2. Admin reviews and approves request
3. Admin confirms service amount
4. Admin generates payment link (CareCard → Pricing & Payment)
5. Admin sends payment email (or copies link manually)
6. Client receives email with secure payment link
7. Client pays via Stripe Checkout (card only)
8. Stripe webhook fires → backend updates request
9. Request status becomes PAID
10. CareCard shows paid/read-only state
```

---

## When to Generate a Payment Link

### Do This Before Clicking "Generate Payment Link"

- ✅ Request is approved and ready for payment collection
- ✅ Service amount is finalized (confirm with client if needed)
- ✅ Client and pet details are correct in the request record
- ✅ Client has an email address on file (required for email send)
- ✅ Request is not already paid, refunded, or waived

### When It's Safe to Generate

- After the request is reviewed and approved
- After you've confirmed the amount with the client (if variable pricing)
- Before or after scheduling — payment does not block staff assignment

### When NOT to Generate

- If the request is already marked Paid
- If the request is refunded or waived
- If you're unsure about the amount (confirm first, then generate)

---

## When to Send Payment Email

### Do This Before Clicking "Send Payment Email"

- ✅ A valid payment link already exists (you generated one)
- ✅ The client's email address is correct
- ✅ You haven't already sent the email recently (check "Last emailed" timestamp)
- ✅ The request is not already paid

### When Resend Is Appropriate

- Client says they didn't receive the email (check spam/junk)
- Payment link has expired (30-minute session timeout)
- Client requests a new link

### When NOT to Resend

- You just sent it a few minutes ago (wait for delivery)
- Client has already paid (Paid badge is showing)
- Client asked to cancel the booking (handle cancellation instead)
- You've already sent 3+ times — contact the client directly

---

## What NOT to Do

| ❌ Never Do This | Reason |
|------------------|--------|
| Send payment email repeatedly without waiting | Can confuse or annoy clients |
| Generate a new link for an already-paid request | System blocks this, but don't try |
| Ask clients to send card numbers directly | Security violation — all payments go through Stripe |
| Paste Stripe keys, secrets, or tokens anywhere | Security violation |
| Send live payment links (currently) | Live mode is not active yet |
| Process cash/check payments through the system | Not supported in current version |

---

## Payment Status Definitions

| Status | Meaning | What Admin Should Do |
|--------|---------|---------------------|
| **Unpaid / Not Set** | No payment has been requested yet | Generate a payment link when ready |
| **Payment Link Sent** | Link created, waiting for client payment | Follow up after 24–48 hours if not paid |
| **Paid** | Client completed payment | Nothing — booking is paid and confirmed |
| **Waived** | Admin waived payment requirement | No further payment action needed |
| **Refunded** | Payment was returned to client | No further payment action needed |
| **Failed / Expired** | Link expired or payment failed | Generate a new link if still needed |

---

## Troubleshooting

### Client says "I didn't get the email"

1. Confirm the client email address is correct in the request
2. Ask client to check spam/junk folder
3. Resend the payment email (click "Send Payment Email" again)
4. If still not arriving, copy the payment link and send via text/phone

### Client says "My card was declined"

1. Ask them to try a different card
2. Check that the link hasn't expired (30-minute window)
3. If expired, generate a new payment link and resend
4. If the issue persists, escalate to Matthew

### Admin does not see "Paid" after client says they paid

1. Wait 1–2 minutes — webhook processing may be slightly delayed
2. Refresh the request list or re-open the CareCard
3. If still not showing after 5 minutes, check Stripe Dashboard for the payment status
4. Escalate to Matthew if Stripe shows "Succeeded" but admin shows "Payment Link Sent"

### Payment link expired

- Links expire 30 minutes after opening in the browser
- Generate a new link and resend or provide the new link to the client
- The expired link cannot be reused

### Wrong amount entered

- If payment has NOT been completed: generate a new link with the correct amount
- If payment HAS been completed: contact Matthew to arrange a partial refund or adjustment via Stripe Dashboard

### No client email on file

- The "Send Payment Email" button will be unavailable
- Copy the payment link manually and deliver it via text, phone, or in person
- Consider adding the client's email to their profile for future use

---

## Admin UI Instructions

### Finding Requests by Payment Status

1. Open Admin Dashboard
2. Use the **Payment Status filter** dropdown:
   - "All" — shows everything
   - "Unpaid" — requests needing payment links
   - "Link Sent" — waiting for client payment
   - "Paid" — completed payments
3. Use the **search bar** to find a specific client by name or email

### Using the CareCard Payment Section

1. Click any request card to open the CareCard detail
2. Scroll to **"Pricing & Payment"** section
3. Read the current status and helper text
4. If a button is disabled/grayed out, read the explanation below it for why

---

## Sandbox / Live Mode Reminder

| Item | Current Status |
|------|---------------|
| Stripe mode | **Sandbox** (test only) |
| Real charges | ❌ Not active |
| Live mode blocker | usmissionhero LLC EIN pending |
| First real payment | ❌ Not approved yet |
| Test card for sandbox | `4242 4242 4242 4242` |

**Do not send payment links to real clients until Matthew confirms live mode is active.**

---

## Escalation Checklist

If you encounter a payment issue you cannot resolve, capture the following before contacting Matthew:

| Item | What to Record |
|------|----------------|
| Request ID | Copy from the CareCard or URL |
| Client name | Full name as shown in the request |
| Pet name | Pet associated with the booking |
| Payment status | Current status badge shown (Unpaid/Link Sent/Paid/etc.) |
| Approximate time | When the issue was noticed |
| What happened | Brief description of the problem |
| What you tried | Steps you already took |

### Do NOT capture or share:
- ❌ Client card numbers
- ❌ Stripe keys or secrets
- ❌ Full payment URLs (they contain session tokens)
- ❌ Screenshots of Stripe Dashboard (may contain sensitive data)
