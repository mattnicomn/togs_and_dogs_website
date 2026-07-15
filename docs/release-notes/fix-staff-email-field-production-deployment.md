# Fix: Staff Management Email Field — Production Frontend Deployment

**Date:** 2026-07-15
**Status:** ❌ FAILED — Email field absent in production (corrected in follow-up commit)
**Type:** Frontend-only production deployment
**Deployed HEAD:** `a1a38bb`
**Runtime Fix Commit:** `afc0a83`

---

## 1. Deployment Summary

| Item | Value |
|------|-------|
| Previous frontend baseline | `11e2876` (bundle `index-DAx_msXw.js`) |
| Deployed repository HEAD | `a1a38bb` |
| Staff email fix commit | `afc0a83` |
| Included accessibility correction | `98fe16d` (22ZC sr-only labels) |
| Production JS bundle | `index-CppE6ptc.js` |
| Production CSS bundle | `index-b59akteP.css` |
| S3 bucket | `togs-and-dogs-prod-toganddogs-hosting` |
| CloudFront distribution | `E35L00QPA2IRCY` |
| CloudFront invalidation ID | `IEI9QHEOQNQIG21PB0HGZWO5UG` |
| Invalidation status | ✅ Completed |

## 2. Build and Lint

| Check | Result |
|-------|--------|
| `npm run build` | ✅ 101 modules, 586ms |
| `npm run lint` | 47 problems (38 errors, 9 warnings) — baseline match, 0 new |

## 3. S3 Deployment Scope

Dry-run confirmed, then applied:
- Upload: `index-CppE6ptc.js`, `index-b59akteP.css`, `usmh-logo-CrRnxp7-.png`, `index.html`
- Delete: `index-DAx_msXw.js`, `index-DdHmXCqb.css` (previous build)

## 4. Read-Only Verification

| Check | Result |
|-------|--------|
| Production homepage HTTP 200 | ✅ Confirmed |
| New bundle referenced | ✅ (assets load correctly) |
| Old bundle removed | ✅ (deleted from S3) |
| Site renders correctly | ✅ |

## 5. Authenticated UI Verification (Manual — Matthew)

The following checks require Matthew to log in and verify without submitting:

| # | Check | Status |
|---|-------|--------|
| 1 | Admin page loads | ⬜ |
| 2 | Open "Add New Staff" | ⬜ |
| 3 | "Create & Invite" mode selected by default | ⬜ |
| 4 | Email field is enabled and editable | ⬜ |
| 5 | Email shows as required (*) in onboard mode | ⬜ |
| 6 | Switch to "Create Profile Only" — email becomes "(Optional)" | ⬜ |
| 7 | Switch back — requirement returns | ⬜ |
| 8 | Cancel closes form without saving | ⬜ |
| 9 | Edit existing staff — email remains read-only | ⬜ |
| 10 | No staff profile or Cognito user was created | ⬜ |

## 6. What Was NOT Done

- ❌ No staff profile created
- ❌ No Cognito invitation sent
- ❌ No backend deployment
- ❌ No Terraform apply
- ❌ No production-data modification
- ❌ No tenant-mode change
- ❌ No Stripe, Google Calendar, or mobile changes
