# Release Notes — Release 22P: Centralized Profile Editor MVP Production Deployment and Validation

**Release Date:** 2026-07-10
**Type:** Frontend Production Deployment
**Status:** ⚠️ **Deployed — Manual Validation PENDING** (drawer stability issue found; see Release 22Q for fix)

---

## 🌟 Overview

Release 22P deploys the previously paused **Release 22J Centralized Profile Editor MVP** to production. This intentionally supersedes the 22M hotfix bundle and resolves the production/main divergence that was introduced when Release 22M was deployed from a temporary hotfix branch (bypassing 22J).

Matthew explicitly approved this deployment after manually deleting/clearing the two pending cancellation records that were present in production.

**Production/main divergence is now resolved.** Production, `main`, and the hotfix branch are now aligned on the same codebase via this release.

---

## 📋 Pre-Deploy Checks

| Check | Result |
|-------|--------|
| Branch | `main` ✅ |
| Git status | Clean (`nothing to commit, working tree clean`) ✅ |
| Commit `691a995` (22J Profile Editor) present | ✅ |
| Commit `d3e864d` (22L cancellation visibility) present | ✅ |
| Docs through 22O present (`5f8ba23`) | ✅ |
| No `.tfplan`, logs, screenshots, credentials staged | ✅ |
| No backend code changes requiring Terraform | ✅ (frontend-only) |

---

## 🧪 Build & Test Results

### Backend Sanity Tests
Ran targeted backend test suites:
- `tests/backend/test_r22h_orphaned_identity.py` — **8/8 PASS**
- `tests/backend/test_r8s_login_controls.py` — **4/4 PASS**
- `tests/backend/test_r8u_staff_cleanup.py` — **10/10 PASS**
- **Total: 22/22 PASS** (2 deprecation warnings, no failures)

### Frontend Build
Ran `npm run build` from the `main` branch:
- **Result:** ✅ PASS — compiled in `339ms`
- **JS Bundle:** `dist/assets/index-knxaSOel.js` (940.82 kB, gzip: 272.91 kB)
- **CSS Bundle:** `dist/assets/index-Bm23ZtvS.css` (72.18 kB, gzip: 13.12 kB)
- No errors. One chunk-size advisory warning (cosmetic, not blocking).

> [!NOTE]
> No frontend test script exists in this project (Vite does not include a built-in test runner). Build success and backend tests are the verification gate.

---

## 📦 Deployment Summary

| Item | Value |
|------|-------|
| S3 Bucket | `s3://togs-and-dogs-prod-toganddogs-hosting` |
| AWS Profile | `usmissionhero-website-prod` |
| CloudFront Distribution | `E35L00QPA2IRCY` |
| Invalidation ID | `ICB4NN3TZRN3G5412WHPJNTOOY` |
| Invalidation Status | **Completed** |
| JS Bundle Live | `/assets/index-knxaSOel.js` ✅ |
| CSS Bundle Live | `/assets/index-Bm23ZtvS.css` ✅ |
| Previous 22M Hotfix Bundle | Deleted from S3 (`index-BU-WCL8y.js`, `index-fLn3j3dM.css`) ✅ |

**Production HTML bundle reference confirmed** via live HTTP fetch of `toganddogs.usmissionhero.com` with cache-bust query parameter.

---

## 🔬 Production Validation Results

> [!NOTE]
> Browser subagent was rate-limited during automated validation. Matthew should complete the manual validation checklist below and confirm results. The items marked below reflect expected behavior based on code review and pre-deploy testing.

### Manual Validation Checklist (for Matthew to confirm)

**Staff Management / Profile Editor MVP:**
- [ ] Navigate to `/admin` → Staff tab
- [ ] Confirm staff cards are **simplified** — no direct Unlink/Reset Password/Set Temp Password/Delete buttons visible on cards
- [ ] Confirm each staff card has a **Manage** button
- [ ] Click **Manage** on a normal valid staff profile (e.g. Ryan York)
- [ ] Confirm a **Profile Editor side drawer** opens
- [ ] Confirm the drawer contains sections: Profile Details, Login Identity, Tenant & Role, Account Security, Danger Zone
- [ ] Close the drawer

**Protected Platform Admin:**
- [ ] Click **Manage** on a protected admin profile (e.g. Matthew's account, look for a Protected badge)
- [ ] Confirm a **Protected badge/banner** appears in the drawer
- [ ] Confirm dangerous actions (Delete, Unlink) are **hidden or disabled** in the drawer
- [ ] Close the drawer. Do NOT execute any action.

**USmissionhero Orphaned Login:**
- [ ] Click **Manage** on the USmissionhero profile
- [ ] Confirm the drawer shows **Orphaned Login** state
- [ ] Confirm risky actions (Reset Password, Delete, Unlink) are **disabled or hidden**
- [ ] Close the drawer. Do NOT execute any action.

**Request List / Cancellation Visibility:**
- [ ] Navigate to Request List
- [ ] Confirm **Needs Action** queue is visible (expected: empty since Matthew manually cleared the 2 pending cancellation records)
- [ ] Confirm **Cancelled** tab shows only final cancelled records and loads without error
- [ ] Document actual queue counts

**Public Routes:**
- [ ] Confirm `/my-bookings` loads correctly
- [ ] Confirm `/book` loads correctly

---

## 🔄 22J Deployment Status

- Release 22J is now **live in production** as of this deployment.
- The production/main divergence introduced by the 22M hotfix is now **fully resolved**.
- `main` and production are aligned.

---

## 📋 Pending Cancellation Records

Matthew manually deleted/cleared the 2 pending cancellation records (`CANCELLATION_REQUESTED` status) that were present in production prior to this deployment. No AG-driven cancellation approval, denial, or deletion occurred.

The cancellation visibility infrastructure deployed in 22L/22M remains intact. If new cancellation requests are submitted by clients in the future, they will correctly appear in the Needs Action queue.

---

## 🛡️ Guardrails Confirmed

| Guardrail | Status |
|-----------|--------|
| Frontend deployment only | ✅ |
| No Terraform applied | ✅ |
| No backend deployment | ✅ |
| No DynamoDB writes | ✅ |
| No cancellation approval/rejection/delete | ✅ (Matthew manually cleared) |
| No Cognito/profile/login mutations | ✅ |
| No invite/password emails sent | ✅ |
| No Stripe changes | ✅ |
| No Google Calendar changes | ✅ |
| No mobile/TestFlight changes | ✅ |
| No Ryan/tester actions | ✅ |
