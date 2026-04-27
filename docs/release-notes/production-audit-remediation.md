# Production Audit Remediation

**Date:** 2026-04-27
**Status:** FULLY DEPLOYED

## Summary of Issues
A production audit identified several critical and high-priority operational issues in the Tog and Dogs application.

1. **Critical:** `Cannot read properties of undefined (reading 'split')` error in `AdminDashboard.jsx` when approving certain records.
2. **High:** Approved visits were not consistently visible in the `MasterScheduler.jsx` due to strict status filtering and date matching issues.
3. **High:** Missing `QUOTED` status in admin workflow dropdowns, filters, and bulk actions.
4. **Medium:** Admin Dashboard table "flashing" or disappearing during data fetches.
5. **Branding:** Remaining `Tog&Dogs` references in the admin header.

## Files Changed
- [AdminDashboard.jsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/AdminDashboard.jsx)
- [MasterScheduler.jsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/MasterScheduler.jsx)
- [CareCard.jsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/CareCard.jsx)

## Fixes Applied
- **Defensive ID Resolution:** Updated `resolveIds` in `AdminDashboard.jsx` to stringify `PK`/`SK` and use safe string operations, preventing `.split()` errors on malformed or missing keys.
- **Workflow Expansion:** Integrated `QUOTED` status into:
    - `statusMap` for transitions.
    - `getWorkflowState` to allow "Quote" as an action for new requests.
    - Quick filters and status select dropdowns in both the List and Scheduler views.
    - `CareCard` status override.
- **Scheduler Visibility:**
    - Included `QUOTED` and `APPROVED` in the active workflow check.
    - Switched "Today" calculation to use the local timezone (`toLocaleDateString('sv-SE')`) for better alignment with business operations.
- **Table Stability:** Optimized `fetchAllData` to avoid clearing the `requests` state on every fetch unless it's a fresh load, significantly reducing UI "flicker".
- **Branding Correction:** Updated admin header text to "Tog and Dogs Admin".

## Validation Performed
- **Build:** `npm run build` completed successfully.
- **Secret Search:** No sensitive strings or tokens found in the codebase.
- **Browser Lifecycle (Local Code):**
    - Intake submission: SUCCESS.
    - ID Resolution: SUCCESS (no crashes on approval).
    - Scheduler Visibility: SUCCESS (Approved/Quoted visits visible).
    - Branding: SUCCESS (Corrected in Admin header).

## Infrastructure Status
- **Terraform:** No changes were made to infrastructure.
- **CloudFront Distribution:** `E35L00QPA2IRCY`
- **CloudFront Invalidation ID:** `I971EGFPV2RLCLM0O4VADQGY52`
- **CloudFront Invalidation Status:** Completed (2026-04-27 12:18 UTC)

## Deployment Details
- **Commit Hash:** `3332039`
- **S3 Sync Completion:** 2026-04-27 12:13 UTC
- **Deployment Status:** SUCCESSFUL

## Production Validation Results (Live Site)
- **Public Intake Page:** PASS (Loads and accepts submissions).
- **Admin Branding:** PASS (Header correctly displays "Tog and Dogs Admin").
- **ID Resolution & Approval:** PASS (Records approve without `.split()` errors).
- **Quoted Status:** PASS (Visible in filters and workflow buttons).
- **Scheduler Visibility:** PASS (Approved visits appear on the timeline).
- **Table Stability:** PASS (Table no longer clears/flashes during refreshes).
- **Console Errors:** PASS (No regressions or JS crashes detected).

## Production URLs
- **Public:** https://toganddogs.usmissionhero.com/
- **Admin:** https://toganddogs.usmissionhero.com/admin
