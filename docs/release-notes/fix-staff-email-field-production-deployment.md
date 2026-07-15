# Fix: Staff Management Email Field — Production Frontend Deployment

**Date:** 2026-07-15
**Status:** ✅ Corrective Deployment Complete — Awaiting Matthew Manual UI Validation
**Type:** Frontend-only production deployment (corrective)
**Deployed HEAD:** `9b196d1`
**Runtime Fix Commit:** `afc0a83` (first attempt, wrong section) → `9b196d1` (corrected)

---

## 1. Deployment History

| Attempt | Commit | Bundle | Result |
|---------|--------|--------|--------|
| First | `a1a38bb` | `index-CppE6ptc.js` | ❌ FAILED — email field absent (wrong JSX section) |
| Corrective | `9b196d1` | `index-Dvcmt57E.js` | ✅ Deployed — awaiting Matthew UI validation |

**Root cause of first failure:** Commit `afc0a83` modified the email field inside the "Login Identity" section, which is guarded by `{editingStaffId && ...}` and only renders when editing existing staff. The actual "Add New Staff" creation form is a separate earlier JSX section that had no email field.

**Corrective fix:** Commit `9b196d1` adds the email field to the actual creation form section, between Display Name and Phone, inside a `{!editingStaffId && ...}` guard so it appears only for new staff.

## 2. Corrective Deployment Summary

| Item | Value |
|------|-------|
| Deployed repository HEAD | `9b196d1` |
| Production JS bundle | `index-Dvcmt57E.js` |
| Production CSS bundle | `index-b59akteP.css` |
| S3 bucket | `togs-and-dogs-prod-toganddogs-hosting` |
| CloudFront distribution | `E35L00QPA2IRCY` |
| CloudFront invalidation ID | `I5Q7K3AWFKMW7GE89WOCDDX6J1` |
| Invalidation status | ✅ Completed |

## 3. Build and Lint

| Check | Result |
|-------|--------|
| `npm run build` | ✅ 101 modules, 532ms |
| `npm run lint` | 47 problems (38 errors, 9 warnings) — baseline match, 0 new |
| Bundle contains email-field strings | ✅ Verified ("login account" present) |

## 4. Read-Only Verification

| Check | Result |
|-------|--------|
| Production homepage HTTP 200 | ✅ |
| New bundle `index-Dvcmt57E.js` served | ✅ |
| Previous bundle `index-CppE6ptc.js` removed | ✅ |
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
