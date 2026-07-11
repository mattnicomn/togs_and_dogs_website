# Triage & Planning — Release 22T: Client Portal My Bookings Date and Visit Window Display Integrity Triage

**Date:** 2026-07-11
**Type:** Planning / Triage (Read-Only)
**Status:** ✅ **Triage Complete** — Root causes identified, fix planned.

---

## 🌟 Overview

Matthew observed that the customer portal (`/my-bookings`) displays incorrect dates and incomplete visit windows for care requests compared to the Admin Portal:
1. **Date Offset:** The client portal displays dates one day earlier than scheduled (e.g., displaying Sep 14 instead of Sep 15–23, and Dec 9 instead of Dec 10–13).
2. **Missing Date Ranges:** Multi-day bookings only show the starting day instead of the full range/occurrences.
3. **Visit Window Mismatch:** The client portal shows a single legacy window (e.g., `MORNING`) or raw text instead of the full list of preferred visit windows (e.g., Morning, Midday, Evening) selected by the client.
4. **Pending Review:** Pending review records lack clear multi-day range information and completion badges.

This document identifies the root causes and outlines the proposed remediation for a future release.

---

## 🔍 Root Cause Analysis

### 1. The Timezone / Date Parsing Bug (One-Day-Early Offset)
In `web/src/components/ClientPortal.jsx`, date parsing is implemented as:
```javascript
<div className="booking-date-weekday">
  {new Date(req.start_date).toLocaleDateString(undefined, { weekday: 'short' })}
</div>
```
When `new Date("YYYY-MM-DD")` receives an ISO date string without time/timezone offsets (e.g., `"2026-12-10"`), JavaScript parses it as UTC midnight (`2026-12-10T00:00:00Z`).
For users in negative timezone offsets (e.g. UTC-4 or UTC-5 in the Americas), this converts to `2026-12-09T20:00:00` local time, resulting in `.toLocaleDateString()` displaying **December 9** (one day early).

**Admin Dashboard Solution:**
The Admin Portal avoids this offset by explicitly splitting the date string by `-` and constructing a local date object:
```javascript
const parseDate = (d) => {
  if (!d) return new Date();
  const [year, month, day] = d.split('-');
  return new Date(year, month - 1, day);
};
```

### 2. Single-Day Display for Multi-Day Bookings
`ClientPortal.jsx` only references `req.start_date` inside its date rendering cards:
```javascript
new Date(req.start_date).toLocaleDateString(...)
```
It completely ignores the `selected_dates` array and `end_date` fields, showing only the first date of a multi-day booking instead of the range.

### 3. Singular Visit Window Display
`ClientPortal.jsx` only references the legacy `req.visit_window` string:
```javascript
{req.visit_window && <span>⏰ {req.visit_window}</span>}
```
It does not look at the modern `req.visit_windows` (plural) array field created in Release 2, and it does not map the values using a friendly label utility like `getVisitWindowLabel(w)`.

---

## 📋 Triage Questions & Answers

### 1. Are the admin and client portal looking at the same parent records?
**Yes.** Both query the same DynamoDB table (`togs-and-dogs-prod-data`) for items where `entity_type == "REQUEST"` (starting with `REQ#`).

### 2. Does `/my-bookings` use parent REQ records or child JOB records?
**Parent REQ records.** The API `/client/requests` only scans and returns items where `entity_type == "REQUEST"`.

### 3. Why does the customer portal show one day earlier?
JavaScript's `new Date("YYYY-MM-DD")` defaults to UTC, which localizes to the previous day in Western timezones.

### 4. Why does customer portal show only `MORNING` instead of all selected windows?
It only references the legacy `req.visit_window` string field instead of mapping and joining the `req.visit_windows` array.

### 5. What field does admin use for the displayed Sep 15–23 and Dec 10–13 ranges?
The admin uses `item.selected_dates` (if present) or `item.start_date` and `item.end_date` parsed locally via custom formatting logic (`formatVisitDates`).

### 6. What field does customer portal use for Sep 14 and Dec 9?
It uses `new Date(req.start_date)` parsed as UTC.

### 7. Is the underlying data wrong, or only the customer portal display logic?
The underlying database data is correct. The issue is entirely frontend rendering logic inside `ClientPortal.jsx`.

### 8. Are child JOB records generated correctly?
**Yes.** Multi-day requests correctly generate distinct child `JOB` records for each scheduled date, containing proper occurrence indices and total occurrence counts.

### 9. Does this affect approved bookings only, pending review only, overnight only, or all multi-day bookings?
It affects **all requests** shown in the client portal, across all services and statuses.

### 10. Should the customer portal show range, windows, completion count, and status?
**Yes.** It should display:
- Friendly date ranges for multi-day bookings (e.g. `Sep 15–23, 2026` and a "Multi-Day" badge).
- Selected visit windows mapped to readable text (e.g. `Morning, Midday, Evening`).
- Visit completion counts (e.g., `0/9 visits done`) to keep clients informed of active schedule progress.
- Status badges matching the admin portal (including `PENDING_REVIEW` / `NEEDS_ACTION` queues).

---

## 🛠️ Proposed Solution

We will update `web/src/components/ClientPortal.jsx` to:
1. **Port the Date Parser:** Implement the local timezone `parseDate` and friendly `formatVisitDates` helper functions from `AdminDashboard.jsx`.
2. **Implement Multi-Day Formatting:** Update the date-box and meta display to show ranges for multi-day requests.
3. **Map Visit Windows:** Implement `getVisitWindowLabel` and map `req.visit_windows` (falling back to `req.visit_window` or `ANYTIME`).
4. **Add Completion Badges:** Add the progress badge (`X/Y visits done`) for multi-day bookings.

---

## 🛡️ Guardrails Met
- Read-only investigation and planning only.
- No code modifications.
- No production deployment.
- No DynamoDB/Cognito/Stripe/Calendar changes.
