# Release 18G: Matthew-Approved Google Calendar Reconnect Execution and Validation

**Status:** ✅ Completed  
**Type:** Operations / Google Calendar Reconnect / Validation  
**Date:** 2026-06-23  
**Baseline:** Release 18F (`f8ac19b`)

---

## 1. Context & Purpose

In Release 18F, we reviewed the degraded connection state of the production Google Calendar integration. The stored credentials in Secrets Manager had expired/revoked tokens, which degraded the sitter schedule synchronization.

In Release 18G, Matthew manually completed the Google OAuth consent flow in the browser via `/admin`, re-authenticating the application. This release documents the successful execution and read-only validation of the reconnection.

---

## 2. Files Created / Modified

| File | Action | Description |
|---|---|---|
| [docs/release-notes/release-18g-google-calendar-reconnect-execution-and-validation.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/release-notes/release-18g-google-calendar-reconnect-execution-and-validation.md) | 🆕 Created | This release notes/validation document. |
| [docs/release-notes/index.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/release-notes/index.md) | 📝 Modified | Registered Release 18G in the featured list and category section. |
| [docs/backlog/saas-maturity-and-multi-business-owner-readiness.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/backlog/saas-maturity-and-multi-business-owner-readiness.md) | 📝 Modified | Appended Release 18G history logs. |
| [docs/operations/matthew-monitoring-checklist.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/operations/matthew-monitoring-checklist.md) | 📝 Modified | Updated checklist with reconnection verification notes. |

---

## 3. Reconnect Execution & Validation Details

### 1. Manual OAuth Execution
- Matthew logged in, navigated to `/admin`, and clicked the Google Calendar reconnect link.
- Google consent was approved, and the callback completed successfully.
- **Secrets Manager Verification:**
  - Queried `togs-and-dogs-prod/google/user-tokens` metadata.
  - **LastChangedDate:** June 23, 2026, 2:03:20 PM EDT (`14:03:20`), confirming the credentials were successfully overwritten with fresh tokens.

### 2. Status & Health Check
- Invoked `GET /admin/auth/status` via Lambda:
  - **Result:** `"status": "CONNECTED"`
- Invoked daily EventBridge health check (`health_check` action):
  - **Result:** `"status": "CONNECTED", "message": "Google Calendar connection is healthy."`
- The admin calendar degraded warning banner is now cleared.

### 3. Safety & Secrets Guardrails
- Checked that **no access tokens, refresh tokens, auth codes, client secrets, or raw values** are exposed or printed in Lambda logs, console outputs, or UI configurations.
- verified that no automatic event backfills were triggered (sync is active for future scheduling events only).
- Verified that **no test bookings or test approvals** were executed.

### 4. Alarms & Platform Admin Check
- Checked `togs-and-dogs-prod-tenant-resolution-fallback` and `togs-and-dogs-prod-tenant-resolution-failed` alarms: **Both OK** (0 occurrences).
- Platform admin (`/platform-admin`) is verified stable and functional.

---

## 4. Operational Guardrails Verification

- **No AWS configuration changes** occurred.
- **No Cognito changes** occurred.
- **No Terraform apply** occurred.
- **No Lambda code deployment** occurred.
- **No code changes** (other than documentation) occurred.
- **No second tenant was created**.
- **No DynamoDB writes** occurred (except for standard OAuth token storage handled by the Lambda endpoint during Matthew's consent redirection).
- **No Stripe, Postmark, TestFlight, App Store Connect, Ryan/tester, or payment/email/SMS changes** occurred.
- **Strict mode remains disabled** (`TENANT_RESOLUTION_MODE` defaults to `single`).

---

## 5. Recommended Next Release

**Release 18H: Post-Reconnect Calendar Sync Validation**
- Under Matthew's explicit approval, create a safe test booking or perform a scheduling assignment to confirm that new calendar sync events are correctly written to the Google Calendar.
