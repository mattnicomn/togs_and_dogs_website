# Release 8R: Mobile Staff Runtime Validation & Staff Account Readiness — Closeout

**Date:** June 4, 2026  
**Release Phase:** 8R  
**Status:** PASSED  
**Planning Commit:** `e5f1610` — docs: plan release 8r mobile staff runtime validation  
**Release Type:** Validation-Only (No code modifications)  

---

## 🔍 Validation Status Summary

The purpose of Release 8R was to perform physical runtime validation of the new mobile staff daily workflow (Today vs. Upcoming tabs, detail screens, and admin action restrictions) using a real Cognito account in the `staff` group.

All validation goals have successfully passed.

### Validation Results

| Check | Status | Notes |
|-------|--------|-------|
| Cognito login with Staff account | ✅ Pass | Tested with `mattnicomn10@yahoo.com` |
| Role-based layout changes | ✅ Pass | App correctly mounts the staff-specific navigator (Schedule screen only) |
| Today / Upcoming Tabs | ✅ Pass | Toggle switches instantly and filters visits appropriately |
| Assigned visit visibility | ✅ Pass | Visits only visible when `worker_id` matches the user's email |
| Booking Details access | ✅ Pass | Opens from schedule list and displays correct care/emergency fields |
| Admin mutation actions hidden | ✅ Pass | Approve, Assign Staff, and Change Staff actions are not rendered |
| Pull-to-refresh | ✅ Pass | Refreshing retrieved up-to-date schedule entries |
| Token refresh / session stability | ✅ Pass | Token refresh operations run silently in the background |
| Sensitive data redaction | ✅ Pass | Internal, admin, and pricing notes are completely hidden |
| Zero code changes | ✅ Pass | No workspace source code was modified during validation |

---

## 💡 Key Findings & Role Mechanics

1. **Cognito Role Routing**: The mobile app layout/navigator selection is governed strictly by the `cognito:groups` array claim inside the Cognito ID token, rather than the database Staff Management profile labels.
2. **Staff Group Requirement**: For any user to see the staff navigation workflow on their device, they must be registered in Cognito and added to the `staff` group.
3. **Database Scoping constraint**: Staff assigned-visit visibility depends on the DynamoDB `worker_id` (or `assigned_sitter_id`) field exactly matching the Cognito account's registered email address.

---

## ⚠️ Separate Web/Admin Issues Discovered (To Track Separately)

During staff validation setup, the following issues were observed on the **Web Admin Dashboard** (Staff Management section):
1. **Unlink Login Action**: Clicking "unlink login" reports success to the administrator but does not actually unlink the Cognito profile from the staff profile in DynamoDB.
2. **Set Password Action**: Setting a temporary or permanent password from the web dashboard staff action menu appears not to work.

*Note: These issues are web/admin-side dashboard bugs and do not affect the mobile client. They are documented here to be resolved in a separate future release and were not modified during Release 8R.*

---

## ⚡ Guardrails Checked & Confirmed

- **NO** workspace code changes were made.
- **NO** backend Lambda modifications occurred.
- **NO** AWS infrastructure modifications (Cognito, DynamoDB, etc.) occurred.
- **NO** web/PWA deployment was triggered.
- **NO** Terraform configurations were changed.

---

Release 8R is **ACCEPTED** and **CLOSED**.
