# Release Notes — Release 14C — CareCard Payment Copy and Action-State Polish

## Implementation Summary

This release polishes the Stripe sandbox payment controls inside the admin CareCard modal. These changes make the workflow extremely clear and operational for administrators by clarifying when to generate links, when to send payment emails, what the current payment status means, and why actions may be disabled.

All changes are frontend-only, with zero changes made to the backend APIs, DynamoDB schemas, or Cognito credentials/roles.

## Helper Texts Added

1. **Generate Payment Link Helper**:
   * Renders a clean notice block inside the unpaid view:
     > 💡 **Before generating:** Confirm the request amount is correct and final. Once generated, the payment link must be sent separately using the **Send Payment Email** action.
2. **Send Payment Email Helper**:
   * Renders an explanatory notice block inside the payment-link-sent view:
     > ✉️ **About this email:** This will send the active Stripe Checkout link to the client email on file. To avoid spam, please do not resend repeatedly unless the client specifically requests it or the prior email delivery failed.

## Disabled-State Explanations

1. **Generate Payment Link**:
   * **Already Paid**: Explicitly states `🚫 Generate Payment Link: Disabled (Request is already paid)` when the request is paid.
   * **Refunded / Waived**: Explicitly states `🚫 Generate Payment Link: Disabled (Request is refunded/waived)` when status is read-only.
   * **Payment Link Sent**: Explicitly states `🚫 Generate Payment Link: Disabled (A payment link already exists for this request...)` when a link already exists.
   * **Missing Required Amount**: Disables the generate button dynamically and displays `⚠️ Generate Disabled: A valid, positive charge amount (greater than $0.00) is required.` if the amount field is empty, negative, or invalid.
   * **Missing Client Email**: Disables the generate button dynamically and displays `❌ Generate Disabled: Client email address is missing.` if `clientEmail` is not set on the request.
2. **Send Payment Email**:
   * **No Payment Link Exists**: Displays `🚫 Send Payment Email: Disabled (No active payment link exists. Please generate a payment link first.)` in the unpaid fallback state.
   * **Already Paid / Waived / Refunded**: Displays `🚫 Send Payment Email: Disabled (Request is already paid/waived/refunded)` in those specific terminal states.
   * **Cooldown Active**: Disables the send button and displays `⏳ Send Disabled (Cooldown): Please wait {seconds} seconds before sending another payment email to prevent duplicates.` if the 120-second client-side resend timer is active.
   * **Missing Client Email**: Disables the send button and displays `❌ Send Disabled: A client email address is required to send the payment link.` if `clientEmail` is missing.

## Payment Status Presentation

* **Paid**: Remains clearly green (`backgroundColor: '#10b981'`).
* **Payment Link Sent**: Standardized the badge label to `Payment Link Sent` and displays `🔗 An active payment link exists for this request. The client may have been sent this link via email to complete their payment.`.
* **Unpaid / Not Set**: Displays a clear status badge and `❌ No payment has been completed for this request yet.`.
* **Waived / Refunded**: Renders a read-only badge and safe messaging: `🛡️ Safe Mode: This request has been marked as {status}. No further payments or charge links can be created or processed.`.

## Email History Visibility

The dashboard now exposes the email send history fields (if present on the request metadata) inside both the main status area and the send email sub-section:
* **Email Send Count** (`pet._originItem?.payment_email_send_count`)
* **Last Sent Email** (`pet._originItem?.payment_email_sent_at`)
* **Last Recipient** (`pet._originItem?.payment_email_last_recipient`)
* Formatting is kept simple, compact, and admin-friendly (e.g. `✉️ Sent 2 time(s) (Last: 6/17/2026)`), avoiding exposure of internal Stripe IDs.

## Build Results

* The frontend production build (`npm run build` executed inside the `web` folder) compiled successfully:
  ```bash
  vite v8.0.8 building client environment for production...
  transforming...✓ 96 modules transformed.
  rendering chunks...
  computing gzip size...
  dist/index.html                         1.47 kB │ gzip:   0.67 kB
  dist/assets/usmh-logo-CrRnxp7-.png  2,583.40 kB
  dist/assets/index-Dhj_nyZO.css         59.93 kB │ gzip:  11.05 kB
  dist/assets/index-CJ_i6wEy.js         897.27 kB │ gzip: 264.66 kB
  ✓ built in 336ms
  ```

## Browser/Manual Smoke Test Deferral

* **Reason**: Strict credential-safety guidelines prevent the extraction or replication of Cognito session cookies or user login tokens from the production portal to the localhost server.
* **Scope for Post-Deploy Manual Validation**:
  1. Open a request in **Unpaid** status. Verify the input field validation works, the Generate button is disabled dynamically for invalid amounts, and the unpaid safe message and helper text are displayed.
  2. Open a request in **Payment Link Sent** status. Verify the active link details, copy link action, and Send Payment Email helper text are rendered. Verify the send cooldown disabling triggers correctly when the email is sent.
  3. Open a **Paid** or **Waived/Refunded** request and verify that action buttons are hidden, showing only the safe read-only message and detailed disabled reason labels.

## Deployment Recommendation

Production deployment is recommended as the code is fully implemented, compile-verified, and meets all Release 14C specifications. No backend modifications are required.
