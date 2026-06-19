# Release 15D: Fresh Internal TestFlight Build

**Status:** Triggered & Scheduled (Building on EAS)  
**Type:** EAS Build & TestFlight Distribution  
**Date:** 2026-06-19  
**Baseline Commit:** `efc06f4cd4a4828ec25dddea8c6a67f6fa301b91` (Release 15C implementation commit)  

---

## 1. Goal

The goal of this release was to compile and deploy a fresh React Native iOS build containing the new read-only payment status indicators and submit it to Apple TestFlight for internal validation by Matthew and Ernest.

---

## 2. Pre-Build Verification Results

Before triggering the remote EAS build, local environment and compilation checks were verified inside the `mobile` directory:
1.  **TypeScript Static Compilation:**
    *   *Command:* `npx tsc --noEmit`
    *   *Result:* 🟢 **Success.** Passed with zero compilation errors.
2.  **Expo Health Diagnostic:**
    *   *Command:* `npx expo-doctor`
    *   *Result:* 🟢 **Success.** 18/18 checks passed.

---

## 3. Build & Submission Configuration

*   **Build Profile Used:** `production` (from `eas.json`)
*   **Target Platform:** iOS (remote builder agent)
*   **Version / Build Number Decision:**
    *   *App Version:* `1.0.0`
    *   *Build Number:* Remote version source resolved the last build as `3` and auto-incremented to **`4`** (manifest version: `1.0.0 (4)`).
*   **EAS Build ID:** `ece9bce1-5aa4-4f25-a1c6-982be221fc3c`
*   **EAS Build URL:** [Build Details](https://expo.dev/accounts/mattnicomn/projects/tog-and-dogs/builds/ece9bce1-5aa4-4f25-a1c6-982be221fc3c)
*   **Auto-Submit Status:** Enabled (`--auto-submit`).
*   **EAS Submission URL:** [Submission Status](https://expo.dev/accounts/mattnicomn/projects/tog-and-dogs/submissions/b51ebe58-e500-43e1-bf28-a75f218372ac) (scheduled to upload the IPA to Apple App Store Connect immediately upon build success).

---

## 4. Next Validation Steps for Matthew / Ernest

Once the EAS build completes and the submission to Apple is processed (typically 10-20 minutes):
1.  **TestFlight Install:** Launch the Apple TestFlight app on the physical testing device, check for version `1.0.0 (4)`, and install/update.
2.  **Smoke-Test Payment Visibility:**
    *   Log in to the app as an **Admin** or **Staff member**.
    *   Navigate to the **Schedule** tab and confirm visits show the inline `Payment: Paid` or `Payment: Unpaid / Not Set` indicators.
    *   Tap a visit to check the **Booking Details screen** and confirm the `Payment Status` badge renders correctly at the bottom of the first card with distinct colors (e.g. green for Paid, yellow for Link Sent, gray for Unpaid).
    *   Verify the staff-facing badge clearly states `(Informational only)`.
    *   Confirm there are no interactive billing options, Stripe Checkout pages, or payment link generation buttons.
3.  **Ernest Tester Invitation:** Verify that Ernest is registered as an active tester in App Store Connect so he receives the TestFlight invite.

---

## 5. Security & Guardrails Compliance

*   No AWS resources, Cognito pools, or DynamoDB tables were modified.
*   No Terraform apply or infrastructure changes occurred.
*   No Stripe API calls were made, and live Stripe activation remains blocked pending usmissionhero LLC EIN.
*   No Postmark emails or SMS messages were sent outside Apple's automatic TestFlight notification system.
*   No external TestFlight groups (Ryan) or Apple Beta App Review submissions were triggered.
