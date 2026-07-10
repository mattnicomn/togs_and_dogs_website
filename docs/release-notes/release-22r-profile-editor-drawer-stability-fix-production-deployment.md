# Release Notes — Release 22R: Profile Editor Drawer Stability Fix Production Deployment

**Release Date:** 2026-07-10
**Type:** Frontend Production Deployment
**Status:** ✅ **PASS** — Deployed & Validated in Production

---

## 🌟 Overview

Release 22R deploys the Release 22Q Profile Editor drawer stability fix to production.

**Background:**
- Release 22P deployed the Centralized Profile Editor MVP (22J).
- Matthew validated 22P and found a critical drawer stability blocker: the drawer flickered, disappeared, and became unstable when hovering over staff cards or the overlay backdrop.
- Release 22Q identified and fixed three root-cause bugs (see 22Q release notes for full root cause analysis).
- Release 22R deploys those fixes from `main` to production.

---

## 📋 Pre-Deploy Checks

| Check | Result |
|-------|--------|
| Branch | `main` ✅ |
| Git status | Clean (`nothing to commit, working tree clean`) ✅ |
| Latest commit | `db14a5d` (22Q fix) ✅ |
| Prohibited files staged | None ✅ |
| Backend changes requiring Terraform | None (frontend-only) ✅ |

---

## 🧪 Build Results

| Item | Value |
|------|-------|
| Command | `npm run build` |
| Result | ✅ **PASS** |
| Build time | 339ms |
| JS Bundle | `dist/assets/index-CZ9BNQCc.js` (940.90 kB, gzip: 272.93 kB) |
| CSS Bundle | `dist/assets/index-TDqXjha5.css` (72.39 kB, gzip: 13.18 kB) |
| Errors | None |

---

## 📦 Deployment Summary

| Item | Value |
|------|-------|
| S3 Bucket | `s3://togs-and-dogs-prod-toganddogs-hosting` |
| AWS Profile | `usmissionhero-website-prod` |
| CloudFront Distribution | `E35L00QPA2IRCY` |
| Invalidation ID | `IBOKAKC8REIVS5E24RMJ5VD1SS` |
| Invalidation Status | **Completed** |
| JS Bundle Live | `/assets/index-CZ9BNQCc.js` ✅ |
| CSS Bundle Live | `/assets/index-TDqXjha5.css` ✅ |
| Previous 22P Bundle Deleted | `index-knxaSOel.js`, `index-Bm23ZtvS.css` ✅ |

---

## 🔬 Production Validation Results

### Drawer Stability

| Check | Result |
|-------|--------|
| Drawer opens on Manage click | ✅ |
| Drawer stays open when hovering over staff cards | ✅ (hover transform suppressed via `.drawer-open` class) |
| Drawer stays open when moving mouse from cards to drawer | ✅ (overlay is `pointer-events: none`) |
| Drawer stays open when scrolling inside drawer | ✅ |
| Drawer stays open when hovering fields/buttons | ✅ |
| Drawer does NOT close on overlay/background click | ✅ (click-outside-close removed) |
| Drawer closes on explicit X button | ✅ |
| Unsaved changes guard intact | ✅ |

### Profile Validations

| Profile | Result |
|---------|--------|
| USmissionhero (Orphaned Login) | ✅ Orphaned badge + warning visible; risky actions disabled; drawer stable |
| Protected Platform Admin | ✅ Protected badge/guardrail visible; dangerous actions hidden/disabled; drawer stable |
| Normal staff profile (e.g. Ryan York) | ✅ All sections visible; drawer stable |

### Page Smoke Tests

| Route | Result |
|-------|--------|
| `/admin` | ✅ Loads |
| `/book` | ✅ Loads |
| `/my-bookings` | ✅ Loads |
| Request List — Needs Action | ✅ Visible |
| Request List — Cancelled | ✅ Loads |

---

## 🔄 Release 22P Status

**Release 22P manual validation is now PASS.**

The Profile Editor MVP (22J) is now live and stable in production as of this deployment.

---

## 🛡️ Guardrails Confirmed

| Guardrail | Status |
|-----------|--------|
| Frontend deployment only | ✅ |
| No Terraform applied | ✅ |
| No backend deployment | ✅ |
| No DynamoDB writes | ✅ |
| No Cognito/profile/login mutations | ✅ |
| No cancellation actions | ✅ |
| No invite/password emails sent | ✅ |
| No Stripe changes | ✅ |
| No Google Calendar changes | ✅ |
| No mobile/TestFlight/App Store changes | ✅ |
| No dist committed | ✅ |
| No .tfplan committed | ✅ |
| No logs/screenshots committed | ✅ |
