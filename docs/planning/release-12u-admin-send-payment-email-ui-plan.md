# Release 12U: Admin Send Payment Email UI Plan

**Status:** Planning
**Priority:** Medium (completes payment notification workflow)
**Risk to Production:** Low (frontend-only, button is inert until clicked)
**Terraform Required:** No
**Code Changes:** None (planning only)
**Scope:** Plan the frontend "Send Payment Email" button and confirmation modal in CareCard

---

## 1. Prerequisites

| Prerequisite | Status |
|-------------|--------|
| 12T backend endpoint deployed: POST /admin/requests/{requestId}/send-payment-email | ✅ `777d383` |
| 12R/12R.2 CareCard payment section live | ✅ |
| Payment link generation works in production | ✅ |
| No real emails sent yet | ✅ |

---

## 2. Button Visibility Conditions

The "Send Payment Email" button should be visible ONLY when ALL of the following are true:

| Condition | Source |
|-----------|--------|
| `payment_status === 'payment_link_sent'` | `pet._originItem.payment_status` |
| `stripe_payment_url` exists and is non-empty | `pet._originItem.stripe_payment_url` |
| Client email exists on the request record | `pet._originItem.client_email` or `pet.client_email` |
| User role is `owner` or `admin` | `userRole` prop |

The button should be HIDDEN when:
- `payment_status` is `paid`, `refunded`, or `waived`
- No payment link has been generated yet (`payment_status` is null/not set)
- No client email exists

---

## 3. Button Placement in CareCard

Inside the existing "Pricing & Payment (Stripe Sandbox)" section, in the `payment_link_sent` branch — add after the existing "Copy Link" and "Test Payment Page" controls:

```
┌─────────────────────────────────────────────────┐
│ Pricing & Payment (Stripe Sandbox)              │
│                                                 │
│ ⚠️ SANDBOX: Do not send to real clients yet    │
│                                                 │
│ Stripe Payment Status: [Link Sent]              │
│ Payment Amount: $75.00                          │
│                                                 │
│ Payment Link:                                   │
│ ┌───────────────────────────────────────────┐   │
│ │ https://checkout.stripe.com/c/pay/cs...   │   │
│ │                              [Copy Link]  │   │
│ └───────────────────────────────────────────┘   │
│                                                 │
│ [Test Payment Page]  [Retrieve Existing Link]   │
│                                                 │
│ ────────────────────────────────────────────    │
│                                                 │
│ 📧 Email Payment Link to Client                │
│ Recipient: brearockwell@gmail.com               │
│ [Send Payment Email]                            │
│                                                 │
│ {success/error banner here if applicable}       │
│                                                 │
│ {Last sent: Jul 1, 2025 10:00 AM — if exists}  │
└─────────────────────────────────────────────────┘
```

### Visual Separation

Add a light horizontal divider (`<hr>` or border-top) between the existing link copy/test controls and the email send section to clearly distinguish "link management" from "email delivery."

---

## 4. Confirmation Modal

When admin clicks "Send Payment Email", show a confirmation modal BEFORE calling the backend:

```
┌──────────────────────────────────────────────────┐
│ 📧 Send Payment Email                            │
│                                                  │
│ This will email a payment link to the client.    │
│                                                  │
│ ┌──────────────────────────────────────────────┐ │
│ │ Recipient: brearockwell@gmail.com            │ │
│ │ Amount:    $75.00                            │ │
│ │ Service:   Dog Walking                       │ │
│ │ Client:    Brea Rockwell                     │ │
│ │ Pet(s):    Luna                              │ │
│ └──────────────────────────────────────────────┘ │
│                                                  │
│ ⚠️ SANDBOX MODE                                 │
│ This is a test email. Do not send to real        │
│ clients. Use Matthew-controlled addresses only.  │
│                                                  │
│         [Cancel]    [Send Email]                  │
└──────────────────────────────────────────────────┘
```

### Modal Data Sources

| Field | Source |
|-------|--------|
| Recipient | `pet._originItem.client_email` or `pet.client_email` |
| Amount | `pet._originItem.payment_amount_cents / 100` formatted as `$XX.XX` |
| Service | `pet._originItem.service_type` (formatted display name) |
| Client | `pet._originItem.client_name` or `pet.client_name` |
| Pet(s) | `pet._originItem.pet_names` or `pet.pet_name` or `pet.name` |

---

## 5. UI States

### Default (Ready to Send)

- Button: "Send Payment Email" (enabled, blue/primary style)
- Shows recipient email below button label
- Shows "Last sent: {date}" if `payment_email_sent_at` exists

### Loading (Sending)

- Button: "Sending..." (disabled, spinner/loading indicator)
- Modal closes or shows loading state
- Prevent double-click

### Success

- Banner: "✓ Payment email sent to brearockwell@gmail.com" (green, auto-dismiss after 5s)
- Button returns to default state
- "Last sent" timestamp updates
- Refresh parent data to reflect `payment_email_sent_at`

### Error — Backend Failure

- Banner: "✗ Failed to send email: {error message}" (red, persistent until dismissed)
- Button returns to enabled state (admin can retry)

### Error — Rate Limited

- Banner: "⚠️ Too many sends. Please wait before sending again." (amber)
- Button disabled for 60 seconds, then re-enables

### Disabled — No Client Email

- Button: "Send Payment Email" (disabled, grayed out)
- Tooltip or helper text: "No client email on file"

### Disabled — Recently Sent (<2 min)

- Button: "Email Sent ✓" (disabled, green text)
- Shows "Sent just now" or timestamp
- Re-enables after 2 minutes

---

## 6. Frontend API Helper

### New Function in `web/src/api/client.js`

```javascript
// Release 12U: Send Payment Email to Client
export const sendPaymentEmail = (requestId) =>
  request(`/admin/requests/${requestId}/send-payment-email`, 'POST', {}, true);
```

### Response Handling

| Backend Status | Frontend Action |
|----------------|-----------------|
| 200 | Show success banner, update "last sent" |
| 400 "No payment link exists" | Show error: "Generate a payment link first" |
| 400 "Client has no email" | Show error: "No client email on file" |
| 403 | Show error: "Access denied" |
| 404 | Show error: "Request not found" |
| 409 "Payment already received" | Show error: "Payment already completed — no email needed" |
| 429 (rate limit) | Show rate-limit message, disable button |
| 500 | Show error: "Email delivery failed — try again" |

---

## 7. Parent Refresh Behavior

After a successful send:

1. Call `onPaymentSessionCreated` (or equivalent parent refresh callback) to reload request data
2. The refreshed data will include `payment_email_sent_at` and `payment_email_recipient`
3. CareCard re-renders with updated "Last sent" display
4. No full page reload needed

### "Last Sent" Display

If `pet._originItem.payment_email_sent_at` exists:

```
Last emailed: Jul 1, 2025 at 10:00 AM to brearockwell@gmail.com
```

Format using `toLocaleDateString` + `toLocaleTimeString` for user's timezone.

---

## 8. Pre-Validation Backend Check

Before the first real send test, AG should verify the API Gateway route is correctly wired:

```powershell
# Verify the route exists and has Cognito auth
aws apigateway get-resources --rest-api-id a022yxuiue --profile usmissionhero-website-prod --query "items[?path=='/admin/requests/{requestId}/send-payment-email']"
```

If the path uses a different structure (e.g., nested under existing `/admin/requests`), verify via:

```powershell
aws apigateway get-resources --rest-api-id a022yxuiue --profile usmissionhero-website-prod --output table
```

This confirms the route exists, method is POST, and authorization is COGNITO_USER_POOLS before attempting a frontend test.

---

## 9. Files to Change (Implementation)

| File | Change |
|------|--------|
| `web/src/api/client.js` | Add `sendPaymentEmail(requestId)` function |
| `web/src/components/CareCard.jsx` | Add email section in `payment_link_sent` branch, confirmation modal, state management |

### State Variables to Add in CareCard

```javascript
const [isSendingEmail, setIsSendingEmail] = useState(false);
const [emailSendError, setEmailSendError] = useState('');
const [emailSendSuccess, setEmailSendSuccess] = useState(false);
const [showEmailConfirmModal, setShowEmailConfirmModal] = useState(false);
```

---

## 10. Validation Plan

### Phase 1: UI Visibility Smoke (No Send)

1. Deploy frontend with "Send Payment Email" button
2. Matthew opens admin → clicks a request with `payment_link_sent` status
3. Verify button is visible
4. Verify button shows recipient email
5. Verify button is hidden for paid/unpaid requests
6. Do NOT click "Send Payment Email" yet

### Phase 2: Confirmation Modal Smoke (No Send)

1. Matthew clicks "Send Payment Email"
2. Verify confirmation modal appears with correct data
3. Click "Cancel" to dismiss
4. No email sent, no API call made

### Phase 3: First Real Send (Requires Approval)

1. Matthew explicitly approves first email test
2. Recipient MUST be Matthew-controlled (mattnicomn10@gmail.com or similar)
3. Matthew clicks "Send Email" in modal
4. Verify success banner
5. Verify email arrives in inbox
6. Verify link in email works

### Pre-Conditions for Phase 3

- AG verifies API Gateway route exists with correct auth
- AG verifies Postmark template is configured
- Matthew confirms recipient address is safe

---

## 11. Sandbox Safety

### While in Sandbox Mode

- Sandbox warning banner always visible in the Pricing & Payment section
- Confirmation modal includes explicit "SANDBOX MODE" warning
- No real client emails until Matthew explicitly approves live mode transition
- Rate limiting protects against accidental spam

### Transition to Live

When live mode is activated (future release):
- Remove sandbox banners
- Remove test-card references
- Keep confirmation modal (always good UX)
- Remove rate-limit relaxation only if needed

---

## 12. Phased Rollout

| Release | Scope |
|---------|-------|
| **12U** | Planning (this document) |
| **12V** | Frontend implementation: button + modal + API call + states |
| **12W** | Sandbox validation: UI smoke + first controlled send test |
| **Future** | SMS support, auto-send toggle, live mode |

---

## 13. What This Document Does NOT Authorize

- ❌ Writing code
- ❌ Modifying CareCard.jsx
- ❌ Adding API helpers
- ❌ Deploying frontend
- ❌ Sending emails
- ❌ Calling Postmark API
- ❌ Creating Checkout Sessions
- ❌ Making payments
- ❌ Writing to DynamoDB
- ❌ AWS/Terraform changes
- ❌ Cognito changes
- ❌ Mobile/EAS/TestFlight changes
- ❌ Committing secrets

This is a planning document only. Frontend implementation requires separate explicit approval (Release 12V).
