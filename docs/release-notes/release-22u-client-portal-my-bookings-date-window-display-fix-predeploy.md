# Release Notes — Release 22U: Client Portal My Bookings Date and Visit Window Display Fix Pre-Deploy

**Release Date:** 2026-07-11
**Type:** Frontend Bug Fix (Pre-Deploy)
**Status:** ✅ **PASS (Pre-Deploy, deployed via 22V)** — Built successfully and deployed to production.

---

## 🌟 Overview

Release 22U implements a comprehensive fix for the customer-facing date, multi-day range, and visit window display integrity issues in the Client Portal (`/my-bookings`). Matthew observed these issues in production during Release 22T triage.

The fix resolves timezone offsets (displaying one day early), implements admin-parity date range formatting for multi-day bookings, lists all selected visit windows with friendly labels, and adds visit completion count badges.

---

## 🔍 Root Cause & Fix Details

### 1. Timezone Date Shifting (One-Day-Early Bug)
- **Problem:** `new Date(req.start_date)` parsed the ISO date (e.g. `"2026-12-10"`) in UTC. In US negative offset timezones (e.g. EST/CST), this shifted the date to the previous evening (e.g. Dec 9), displaying one day early.
- **Fix:** Implemented a local date parser `parseDate(d)` that splits `"YYYY-MM-DD"` strings and constructs a local date object using `new Date(year, month - 1, day)`. The date box and cancellation calculations now use this parser, preventing all timezone shifts.

### 2. Multi-Day Range Display
- **Problem:** Client portal only displayed `req.start_date` inside each card, failing to indicate that bookings were multi-day or show the end date.
- **Fix:** Ported `formatVisitDates` and `formatDate` from `AdminDashboard.jsx`. Booking cards now display the complete range (e.g., `Sep 15–23, 2026` or `Dec 10–13, 2026`) and append a visible `Multi-Day` badge.

### 3. Plural Visit Window Mapping
- **Problem:** Client portal only displayed the legacy single `req.visit_window` and printed raw enum strings (e.g. `MORNING`) instead of all selected visit windows.
- **Fix:** Added `getVisitWindowLabel(w)` and mapped `req.visit_windows` (falling back to legacy `visit_window` or `ANYTIME`), joining multiple selections with commas (e.g., `Morning (7–10 AM), Midday (10 AM–2 PM), Evening (5–8 PM)`).

### 4. Visit Completion Badge
- **Problem:** Clients could not see how many visits were completed.
- **Fix:** Added a completion badge matching the admin style (e.g. `0/9 visits done`, `0/4 visits done`), using `req.completed_count` and `req.selected_dates.length || req.total_occurrences`.

---

## 📋 Files Changed

| File | Change |
|------|--------|
| [`web/src/components/ClientPortal.jsx`](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/ClientPortal.jsx) | Added `parseDate`, `formatDate`, `getVisitWindowLabel`, and `formatVisitDates` helper functions; updated cancellation checks; updated card layout JSX with ranges, windows, completion count, and Multi-Day badges |

---

## 🧪 Build Results

| Item | Value |
|------|-------|
| Command | `npm run build` |
| Status | ✅ **PASS** |
| Build time | 407ms |
| JS Bundle | `dist/assets/index-CZXrWtrt.js` (944.46 kB) |
| CSS Bundle | `dist/assets/index-BHyXIxXF.css` (72.52 kB) |
| Errors | None |

> [!NOTE]
> Vite does not include a test runner in this repository. Build compilation success is the verification gate.

---

## 🔬 Local / Code Validation Checklist
- [x] UTC date parsing `new Date("YYYY-MM-DD")` removed from ClientPortal date displays and handleCancelRequest.
- [x] Date ranges format correctly (e.g., `Sep 15–23, 2026` and `Dec 10–13, 2026`).
- [x] Multiple visit windows array and legacy fallback supported.
- [x] Multi-day badges and completion counts display dynamically.
- [x] No backend or database changes made.

---

## 🛡️ Guardrails Confirmed

- Frontend code/docs only. No Terraform applied. No backend deployment.
- No DynamoDB writes. No Cognito/profile/login mutations.
- No cancellation actions. No emails sent. No Stripe/calendar/mobile changes.
- `web/dist` and scratch files not committed.

---

## 🔄 Deployment Status & Note
- **Current Branch:** `main` (clean)
- **Status:** **Pre-Deploy** (Not deployed yet)
- **Release 22S Status:** Pre-deploy on `main` (Not deployed yet)
- **Future Deployment Note:** A future S3 sync/CloudFront invalidation from `main` will deploy **both** Release 22S (drawer stability portal fix) and Release 22U (client portal date/window display fix) together, resolving both outstanding MVP blockers at once.
