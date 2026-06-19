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
  ✓ built in 363ms
  ```

## Frontend Deployment Details

* **Deployment Method**: S3 sync deployment
* **Target S3 Bucket**: `s3://togs-and-dogs-prod-toganddogs-hosting`
* **AWS CLI Sync Results**: Successfully synced the 4 final assets to S3 and deleted the old asset bundles using AWS profile `usmissionhero-website-prod`.
* **CloudFront Invalidation ID**: `IBB99RNHM36UH2PQ8JW14ZYAXA` for distribution `E35L00QPA2IRCY`.

## Production Smoke Test Validation Results

A browser subagent completed a comprehensive verification directly on the live production URL `https://toganddogs.usmissionhero.com/admin` using the active authenticated admin portal session. All test targets passed successfully:
1. **Admin Dashboard Loads**: Verified page reload and initial list load on the live site.
2. **Search/Filter composition**: Search input and payment filter from Release 14B function correctly.
3. **Paid Request (`TestPet_ScenarioB`) CareCard**:
   * Opens CareCard normally.
   * Renders the Stripe Payment Status as a green, read-only **Paid** chip.
   * Displays the completed payment text: `✓ Payment completed via Stripe sandbox. No actions required.`.
   * Both **Generate Payment Link** and **Send Payment Email** actions are shown as disabled with explicit reason labels: `Disabled (Request is already paid)`.
4. **Payment Link Sent Request (`TestPet_ScenarioA`) CareCard**:
   * Renders the Stripe Payment Status as a blue **Payment Link Sent** chip.
   * Displays the active payment link and the **Copy Link** action.
   * Displays the new **Send Payment Email** helper text.
   * Correctly exposes the email send history: recipient email `brearockwell@gmail.com` and last sent details.
   * Shows **Generate Payment Link** as disabled: `Disabled (A payment link already exists...)`.
5. **Unpaid Request (`TestPet_ScenarioD`) CareCard**:
   * Renders the Stripe Payment Status as a grey **Unpaid / Not Set** chip with the safe message `❌ No payment has been completed for this request yet.`.
   * Displays the new **Generate Payment Link** helper text.
   * Renders disabled reasons next to the Generate button if validation fields are invalid (e.g. quote amount is `$0.00`).
   * Displays `🚫 Send Payment Email: Disabled (No active payment link exists...)` underneath.
   * Verified that no payment links were generated and no emails were sent during smoke testing.

## Final Git Status

The repository is clean and up to date with the remote tracking branch `origin/main`.

## Guardrails & Verification Confirmation

* No backend code, schemas, or API changes were made.
* No Terraform resource plans, configurations, or applies occurred.
* No Stripe Dashboard settings, API keys, or checkout sessions were modified or used.
* No Postmark email transmissions, SMS messages, DynamoDB writes, Cognito user pools/identities, mobile app/EAS packages, or second tenant configurations were changed.
