# Release 9D: Daily Sitter Dispatch Export

**Status:** Planning
**Priority:** Medium (operational fallback tool for Ryan)
**Risk to Production:** Very Low (frontend-only sheet generation)
**Terraform Required:** No
**Backend Changes:** No (existing export endpoint returns all needed data)
**Scope:** Add a "Daily Dispatch" sheet to the existing Excel export

---

## 1. Purpose

Give Ryan a print-friendly daily sitter dispatch sheet he can print or save as an offline fallback — showing who goes where, when, for which pets, with what instructions. This complements Google Calendar (which requires internet) and the mobile app (which requires the phone).

---

## 2. Current Export Behavior

### Existing Export Button

- Location: Admin Dashboard header area (visible to owner/admin)
- Triggers: `GET /admin/export-data` → full DynamoDB scan
- Returns: `{ requests, clients, pets, staff, jobs }`
- Frontend generates: Excel workbook with 9 sheets

### Current Sheets

| Sheet | Content | Useful for Dispatch? |
|-------|---------|---------------------|
| Export Summary | Counts | ❌ No |
| All Requests | Parent REQ rows with flat fields | ⚠️ Partial — grouped by booking, not by date/staff |
| Active Requests | Filtered active subset | ⚠️ Same issue |
| Scheduled | ASSIGNED/SCHEDULED/BOOKED | ⚠️ Shows parent bookings, not per-day |
| Completed | COMPLETED bookings | ❌ Past |
| Clients | Client profiles | ❌ Reference only |
| Pets | Pet profiles | ❌ Reference only |
| Staff Assignments | JOB records | ✅ Has per-day data! But unsorted, no grouping |
| Cancelled-Archived-Trash | Terminal records | ❌ No |

### Key Finding: JOB Data Already Available

The export endpoint returns `data.jobs` which includes child JOB records with:
- `occurrence_date` / `start_date`
- `status` (ASSIGNED, COMPLETED, etc.)
- `worker_name`
- `client_name`
- `pet_name` / `pet_names`
- `service_type`
- `visit_notes`
- `completed_at` / `completed_by`

**No backend changes needed.** The frontend just needs to build a better-formatted sheet from existing data.

---

## 3. Options Analysis

### Option A: Add New Sheet to Existing Export Workbook (Recommended)

Add a "Daily Dispatch" sheet to the Excel file that groups visits by date then by staff.

**Pros:** Single action (existing Export button), no new UI controls, includes dispatch alongside backup
**Cons:** Always generates all sheets (minor — export is already full-scan)

### Option B: Separate "Daily Dispatch" Button with Date Picker

Add a new button with a date range selector that generates ONLY the dispatch sheet.

**Pros:** Focused output, user chooses date range
**Cons:** Additional UI complexity, new button placement, more frontend work

### Option C: Printable Web View

Add a "Print Dispatch" screen that renders a formatted HTML table for printing.

**Pros:** No Excel dependency, immediate visual preview
**Cons:** More frontend development, print CSS complexity, no offline file saved

### Recommendation: Option A (MVP)

Add the "Daily Dispatch" sheet as the FIRST sheet in the existing export workbook (before Export Summary). This is the lowest-risk approach — zero new buttons, zero new endpoints, just better data formatting in the existing export flow.

---

## 4. Daily Dispatch Sheet Design

### Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│ DAILY DISPATCH — Tog & Dogs                                         │
│ Generated: Jun 10, 2026 at 7:00 AM                                 │
│ Date Range: Jun 10 – Jun 16, 2026 (next 7 days)                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ ═══ TUESDAY, JUNE 10, 2026 ═══                                    │
│                                                                     │
│ Ryan (2 visits)                                                     │
│ ┌───────────┬──────────────┬──────────┬────────────┬──────────────┐│
│ │ Time      │ Client / Pet │ Service  │ Location   │ Notes        ││
│ ├───────────┼──────────────┼──────────┼────────────┼──────────────┤│
│ │ Morning   │ Jane Smith   │ 30-Min   │ 123 Oak Ln │ Gate code:   ││
│ │ (7-10 AM) │ 🐾 Buddy    │ Walk     │            │ 1234         ││
│ ├───────────┼──────────────┼──────────┼────────────┼──────────────┤│
│ │ Afternoon │ Mark Lee     │ 1-Hour   │ 45 Pine St │ Key under    ││
│ │ (2-5 PM)  │ 🐾 Luna     │ Drop-in  │            │ mat          ││
│ └───────────┴──────────────┴──────────┴────────────┴──────────────┘│
│                                                                     │
│ Sarah (1 visit)                                                     │
│ ┌───────────┬──────────────┬──────────┬────────────┬──────────────┐│
│ │ Morning   │ Tom Brown    │ 30-Min   │ 78 Elm Ave │              ││
│ │           │ 🐾 Max       │ Walk     │            │              ││
│ └───────────┴──────────────┴──────────┴────────────┴──────────────┘│
│                                                                     │
│ ═══ WEDNESDAY, JUNE 11, 2026 ═══                                   │
│ ...                                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Columns

| Column | Source Field | Notes |
|--------|-------------|-------|
| Date | `occurrence_date` or `start_date` | Section header |
| Staff | `worker_name` | Sub-group within date |
| Time Window | `visit_windows[0]` → friendly label | "Morning (7-10 AM)" |
| Client | `client_name` | |
| Pet(s) | `pet_name` or `pet_names` | |
| Service | `service_type` → friendly label | "30-Minute Walk" |
| Location | Address from parent REQ (cross-reference via `request_id`) | May need client lookup |
| Notes/Instructions | `pet_info` or `details` from parent REQ | Truncated for print |
| Status | `status` | ✅ Completed / ⏳ Pending |
| Visit Notes | `visit_notes` (if completed) | Staff completion note |

### Filtering

- **Date range:** Next 7 days from today (default)
- **Status filter:** Include ASSIGNED + JOB_CREATED (pending visits). Optionally include COMPLETED for that day's summary.
- **Exclude:** CANCELLED, ARCHIVED, DELETED jobs
- **Exclude:** Test bookings (if `is_test` flag exists from 9A)

### Sorting

1. Primary: Date ascending
2. Secondary: Staff name alphabetical
3. Tertiary: Time window order (Morning → Midday → Afternoon → Evening → Anytime)

---

## 5. Data Assembly Logic (Frontend)

```javascript
const buildDispatchSheet = (jobs, requests, clients) => {
  const today = new Date();
  const endDate = new Date(today);
  endDate.setDate(today.getDate() + 7);
  
  // 1. Filter to upcoming assigned/active visits
  const upcoming = jobs.filter(j => {
    const status = (j.status || '').toUpperCase();
    if (!['ASSIGNED', 'JOB_CREATED', 'COMPLETED'].includes(status)) return false;
    const date = j.occurrence_date || j.start_date;
    if (!date) return false;
    return date >= todayStr && date <= endDateStr;
  });
  
  // 2. Enrich with parent REQ data (address, pet_info, details)
  const enriched = upcoming.map(j => {
    const parent = requests.find(r => r.request_id === j.request_id);
    return {
      ...j,
      address: parent?.address || parent?.service_location || '',
      pet_info: parent?.pet_info || parent?.details || '',
      visit_windows: parent?.visit_windows || [j.visit_window || 'ANYTIME'],
    };
  });
  
  // 3. Sort by date → staff → time window
  enriched.sort((a, b) => {
    const dateCompare = (a.occurrence_date || a.start_date || '').localeCompare(b.occurrence_date || b.start_date || '');
    if (dateCompare !== 0) return dateCompare;
    const staffCompare = (a.worker_name || '').localeCompare(b.worker_name || '');
    if (staffCompare !== 0) return staffCompare;
    return windowOrder(a) - windowOrder(b);
  });
  
  // 4. Build sheet rows with date/staff headers
  return enriched.map(j => ({
    "Date": formatDate(j.occurrence_date || j.start_date),
    "Staff": j.worker_name || 'Unassigned',
    "Time Window": friendlyWindow(j.visit_windows?.[0]),
    "Client": j.client_name,
    "Pet(s)": j.pet_name || j.pet_names,
    "Service": friendlyService(j.service_type),
    "Location": j.address,
    "Instructions": (j.pet_info || '').substring(0, 100),
    "Status": j.status === 'COMPLETED' ? '✅ Done' : '⏳ Pending',
    "Visit Notes": j.visit_notes || ''
  }));
};
```

---

## 6. Multi-Day Handling

| Scenario | Behavior |
|----------|----------|
| Multi-day booking with child JOBs | Each JOB appears as its own row on its occurrence date |
| Single-day booking with one JOB | One row on the start_date |
| Parent-only legacy booking (no child JOBs) | One row using parent's start_date |
| Completed days | Shown with ✅ status and visit notes |
| Pending days | Shown with ⏳ status |

The dispatch sheet operates on **JOB records** (one row per actual visit day), not parent REQ records. This naturally handles multi-day expansion.

---

## 7. Address/Location Enrichment

JOB records don't store the client's address — this lives on the parent REQ or the Client profile. The frontend enrichment step cross-references:

```javascript
const parent = requests.find(r => r.request_id === j.request_id);
const address = parent?.address || parent?.service_location || '';

// Optionally also check client profile:
const client = clients.find(c => c.client_id === j.client_id);
const fallbackAddress = client?.address || '';
```

This uses data already returned by `GET /admin/export-data`. No new endpoint needed.

---

## 8. Sensitive Data Guardrails

| Field | Include in Dispatch? | Reason |
|-------|---------------------|--------|
| Client name | ✅ Yes | Staff needs to know who |
| Client phone | ✅ Yes | Staff may need to call |
| Client email | ❌ No | Not needed for dispatch |
| Pet name/info | ✅ Yes | Care instructions |
| Address | ✅ Yes | Staff needs location |
| Internal admin notes | ❌ No | Not operational |
| Pricing/quotes | ❌ No | Not relevant to dispatch |
| Visit notes (completed) | ✅ Yes | Operational record |
| Emergency contact | ✅ Yes (optional column) | Safety |

---

## 9. Files to Modify

| File | Change | New? |
|------|--------|------|
| `web/src/components/AdminDashboard.jsx` | Add "Daily Dispatch" sheet generation in `handleExportData()` | Modified |

### Files NOT Changed

- No backend handlers (export endpoint already returns JOBs)
- No Terraform
- No mobile app
- No CSS (sheet is in Excel, not rendered on screen)
- No API client changes
- No new npm dependencies (uses existing XLSX library)

---

## 10. Acceptance Criteria

- [ ] Export Excel includes "Daily Dispatch" as the first sheet
- [ ] Dispatch shows next 7 days of visits grouped by date then staff
- [ ] Each row shows: date, staff, time window, client, pet, service, location, status
- [ ] Multi-day bookings show one row per JOB/date
- [ ] Completed visits show ✅ with notes
- [ ] Pending visits show ⏳
- [ ] Cancelled/archived visits excluded
- [ ] Test bookings excluded (if `is_test` flag available)
- [ ] Address/location enriched from parent REQ or client profile
- [ ] `npm run build` passes
- [ ] No backend changes needed
- [ ] Existing export sheets unchanged (backward compatible)

---

## 11. Validation Plan

### Build
```bash
cd web && npm run build
```

### Manual Testing

| # | Test | Expected |
|---|------|----------|
| 1 | Click Export with active assigned bookings | Excel downloads with "Daily Dispatch" as first sheet |
| 2 | Dispatch sheet shows today's visits | Correct date, staff, service |
| 3 | Multi-day booking shows multiple rows | One per occurrence date in range |
| 4 | Completed visit shows ✅ + notes | From child JOB completed_at/visit_notes |
| 5 | No cancelled/archived visits | Filtered out |
| 6 | Address appears from parent or client | Cross-referenced correctly |
| 7 | Staff grouping | Visits grouped under each sitter's name |
| 8 | Time window labels | "Morning (7-10 AM)" not "MORNING" |
| 9 | Existing sheets still present | All 9 original sheets unchanged |

---

## 12. Deployment

| Layer | Needed? |
|-------|---------|
| Backend Lambda | ❌ No |
| Web S3 + CloudFront | ✅ Yes (frontend change) |
| Mobile / EAS | ❌ No |
| Terraform | ❌ No |

---

## 13. Rollback

- Revert `AdminDashboard.jsx` export function changes
- Existing 9 sheets continue to generate (the dispatch sheet is additive)
- No data or backend impact

---

## 14. Future Enhancements (Not in 9D)

| Enhancement | When |
|-------------|------|
| Date range picker for dispatch (not just next 7 days) | 9E+ |
| Separate "Print Dispatch" button (without full export) | 9E+ |
| Printable web view with print CSS | 9F+ |
| Staff-specific dispatch (filter to one sitter) | 9E+ |
| Include client phone number column | 9D can include if approved |
| Include emergency contact column | 9E+ |

---

## 15. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 9D: Daily Sitter Dispatch Export.

Frontend-only change in web/src/components/AdminDashboard.jsx.
No backend, Terraform, mobile, or infrastructure changes.

=== 1. Update handleExportData() in AdminDashboard.jsx ===

After the workbook is created and before the "Export Summary" sheet is added,
insert a new "Daily Dispatch" sheet as the FIRST sheet:

a) Define helper functions (inside handleExportData or above it):

   const WINDOW_ORDER = { 'MORNING': 1, 'MIDDAY': 2, 'AFTERNOON': 3, 'EVENING': 4, 'ANYTIME': 5 };
   const FRIENDLY_WINDOWS = { 'MORNING': 'Morning (7-10 AM)', 'MIDDAY': 'Midday (10 AM-2 PM)', 'AFTERNOON': 'Afternoon (2-5 PM)', 'EVENING': 'Evening (5-8 PM)', 'ANYTIME': 'Anytime' };
   const FRIENDLY_SERVICES = { 'WALK_30MIN': '30-Min Walk', 'WALK_60MIN': '60-Min Walk', 'DROPIN_1HR': '1-Hour Drop-in', 'DROPIN_3HR': '3-Hour Drop-in', 'OVERNIGHT': 'Overnight Care', 'PET_SITTING': 'Pet Sitting', 'MEET_GREET': 'Meet & Greet' };

b) Filter jobs to next 7 days:
   - Get today's date as YYYY-MM-DD
   - Get date 7 days from now as YYYY-MM-DD
   - Filter data.jobs where:
     - (occurrence_date || start_date) >= today
     - (occurrence_date || start_date) <= endDate
     - status in ['ASSIGNED', 'JOB_CREATED', 'COMPLETED'] (exclude CANCELLED/ARCHIVED/DELETED)

c) Enrich each job with parent data:
   - Find parent request by request_id
   - Get address: parent.address || parent.service_location || ''
   - Get pet_info: parent.pet_info || parent.details || ''
   - Get visit_windows: parent.visit_windows || [job.visit_window || 'ANYTIME']
   - Get client_phone: parent.client_phone || ''

d) Sort:
   - By date ascending
   - Then by worker_name alphabetically
   - Then by window order (MORNING < MIDDAY < AFTERNOON < EVENING < ANYTIME)

e) Map to dispatch rows:
   {
     "Date": formatted date (e.g., "Tue, Jun 10, 2026"),
     "Staff": worker_name || 'Unassigned',
     "Time": FRIENDLY_WINDOWS[visit_windows[0]] || visit_windows[0] || 'Anytime',
     "Client": client_name,
     "Pet(s)": pet_name || pet_names || '',
     "Service": FRIENDLY_SERVICES[service_type] || service_type,
     "Location": address (truncated to 50 chars),
     "Instructions": pet_info (truncated to 100 chars),
     "Status": status === 'COMPLETED' ? '✅ Done' : '⏳ Pending',
     "Visit Notes": visit_notes || ''
   }

f) Add the dispatch sheet FIRST (before Export Summary):
   if (dispatchRows.length > 0) {
     XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(dispatchRows), "Daily Dispatch");
   } else {
     XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet([
       ["No upcoming visits scheduled for the next 7 days."]
     ]), "Daily Dispatch");
   }

   Then continue with existing Export Summary and other sheets.

=== 2. Validation ===

Run: npm run build (in web/)
Confirm no errors.
Do NOT deploy without Matthew's approval.

Return: files changed, build result, description of the new sheet.
```

---

## 16. Commit Command (Planning Doc Only)

```bash
git add docs/planning/release-9d-daily-sitter-dispatch-export-plan.md
git commit -m "docs: plan release 9d daily sitter dispatch export"
```
