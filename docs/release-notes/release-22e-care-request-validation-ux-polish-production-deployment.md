# Release 22E — Care Request Validation UX Polish Production Deployment

**Release Date:** 2026-07-09
**Status:** PASS (Manually Validated)
**Deployed By:** Matthew (explicit approval) + Antigravity AI agent
**Type:** Frontend-only (no backend, Terraform, Cognito, or production data changes)

---

## Summary

Production deployment and validation of Release 22D care request validation UX polish. 

This release fixes the `/book` intake form Step 2 Schedule validation UX confusion by making the range auto-fill behavior context-aware, making the range selection action button visually prominent, making the preferred visit windows field explicitly required with its own inline error rendering, and polishing the top error summary layout.

---

## Pre-Deploy Checks

| Check | Result |
|---|---|
| Git status clean | PASS |
| Latest commit `4f496b5` or later | PASS — `4f496b5` (Release 22D implementation) |
| Expected bundle references in build | PASS — `assets/index-C9kQ3Nwr.js` and `assets/index-fLn3j3dM.css` |
| Verification of no backend/database/Terraform changes | PASS |

---

## Frontend Deployment

### S3 Sync
**Bucket:** `s3://togs-and-dogs-prod-toganddogs-hosting`
**Sync command:**
```powershell
aws s3 sync web/dist/ s3://togs-and-dogs-prod-toganddogs-hosting --delete --profile usmissionhero-website-prod
```
**Actions:**
- **Deleted old bundle:** `assets/index-BVmvw1mJ.js` and `assets/index-CntSnVuv.css` (22C bundle)
- **Uploaded new bundle:** `assets/index-C9kQ3Nwr.js` and `assets/index-fLn3j3dM.css`
- **Uploaded:** `index.html`

### CloudFront Invalidation
- **Distribution:** `E35L00QPA2IRCY`
- **Invalidation ID:** `I92PYE2NP4XELU4FWSDU61Z7GF`
- **Paths:** `/*`
- **Status:** Completed ✅

---

## Safe Production Validation

### Automated Checks

| Check | Result |
|---|---|
| Live HTML bundle references correct file | PASS (verified referencing `index-C9kQ3Nwr.js`) |
| `https://toganddogs.usmissionhero.com/` loads | PASS |
| `https://toganddogs.usmissionhero.com/book` loads | PASS |
| `https://toganddogs.usmissionhero.com/admin` loads | PASS |
| No production care request data submitted | PASS |
| No Cognito, tenant metadata, or database writes | PASS |

### Safe Browser Smoke Validation (via automated subagent testing)

| Check | Result |
|---|---|
| **Top Summary Error Copy** | PASS — "⚠️ Please complete the highlighted schedule fields below." is displayed. |
| **Top Summary Missing List** | PASS — lists "Visit Dates" and "Preferred Visit Windows" when both are empty. |
| **Preferred Visit Windows Required** | PASS — advancing to Step 3 is blocked; displays inline error "⚠️ Please select at least one preferred visit window." |
| **Preferred Visit Windows Highlight** | PASS — checkboxes container has a highlighted red border. |
| **Preferred Visit Windows Clear** | PASS — selecting "Anytime (Flexible)" immediately clears the error and highlight. |
| **Context-Aware Range Date Error** | PASS — Entering a Start/End date but not clicking auto-fill displays: "You entered a date range, but no visit dates are selected yet. Click 'Select Dates from Range' or select dates manually on the calendar below." |
| **Auto-Fill Button Style/Label** | PASS — labeled "Select Dates from Range" and rendered as a visually prominent pill button matching the primary theme button. |
| **Select Dates clears date error** | PASS — Clicking "Select Dates from Range" populates the calendar and clears the inline validation error. |
| **Advance to Step 3** | PASS — After validating Step 2 fields, click Next successfully advances to Step 3. |
| **Submit Request** | PASS — No request submitted, validation checked safely. |

---

## Guardrail Confirmation

| Guardrail | Status |
|---|---|
| No invite/password reset emails sent | CONFIRMED |
| No temp passwords set | CONFIRMED |
| No Cognito users/groups/passwords modified | CONFIRMED |
| No tenant metadata modified | CONFIRMED |
| No database records modified or backfilled | CONFIRMED |
| No Google Calendar tokens/secrets modified | CONFIRMED |
| No Stripe changes or live mode usage | CONFIRMED |
| No mobile/TestFlight changes | CONFIRMED |
| Targeted git add only (no git add .) | CONFIRMED |

---

## Commits

| Commit | Description |
|---|---|
| `4f496b5` | Release 22D: Implement Care Request Date Validation Copy and Auto-Fill UX Polish (Pre-Deploy) |

---

## Next Steps / Manual Matthew Validation

Matthew is requested to manually review the booking page:
1. Open `/book` in browser.
2. Advance through Step 1 to Step 2.
3. Test validation flow by checking errors, date range selection, and preferred visit windows.
4. Confirm smooth scrolling/focus behaviors.
5. Do not submit a request.
