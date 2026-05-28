# Release 7E Phase 2B: Frontend Date Picker for Selected-Day Scheduling

**Status:** Planning
**Priority:** Medium
**Risk to Production:** Very Low (frontend-only, additive UI)
**Terraform Required:** No
**Backend Changes:** None (Phase 2A already deployed)
**Scope:** Frontend-only — `AdminDashboard.jsx` + new `DatePickerGrid.jsx` component

---

## 1. Objective

Add a "Pick Days" scheduling mode to the New Visit modal so Ryan can select specific non-consecutive dates (e.g., every Tuesday and Friday) for multi-visit bookings. The frontend sends `selected_dates` to the already-deployed Phase 2A backend.

---

## 2. Current Form Layout (New Visit Modal)

```
┌─────────────────────────────────────────────┐
│ + New Visit                            [✕]  │
│─────────────────────────────────────────────│
│ Client *          [dropdown]                 │
│ Pets *            [checkboxes]               │
│ Service Type *    [dropdown]                 │
│ Start Date *      [date input]               │
│ End Date          [date input]               │
│ Visit Window      [dropdown]                 │
│ Notes             [textarea]                 │
│ Preferred Sitter  [dropdown]                 │
│─────────────────────────────────────────────│
│                        [Cancel] [Create Visit]│
└─────────────────────────────────────────────┘
```

### Current State Shape

```javascript
{
  client_id: '', client_name: '', client_email: '', client_phone: '',
  pet_names: '', pet_ids: [], service_type: 'PET_SITTING',
  start_date: '', end_date: '', visit_windows: ['ANYTIME'],
  details: '', preferred_sitter: ''
}
```

---

## 3. Proposed UI Layout

### Schedule Mode Selector

Replace the current Start Date / End Date row with a mode selector + conditional date inputs:

```
┌─────────────────────────────────────────────┐
│ Schedule                                     │
│ [Single Day] [Date Range] [Pick Days]        │
│                                              │
│ ── When "Single Day" selected: ──            │
│ Date *  [2026-07-15]                         │
│                                              │
│ ── When "Date Range" selected: ──            │
│ Start * [2026-07-01]  End * [2026-07-05]     │
│                                              │
│ ── When "Pick Days" selected: ──             │
│ ┌─── July 2026 ──────── [<] [>] ──┐         │
│ │ Mo  Tu  We  Th  Fr  Sa  Su      │         │
│ │      ①   2   3  ④   5   6      │         │
│ │  7  ⑧   9  10  ⑪  12  13      │         │
│ │ 14  ⑮  16  17  ⑱  19  20      │         │
│ │ 21  22  23  24  25  26  27      │         │
│ │ 28  29  30  31                   │         │
│ └──────────────────────────────────┘         │
│ Selected: 6 days (max 14)                    │
│ Jul 1, 4, 8, 11, 15, 18                     │
└─────────────────────────────────────────────┘
```

### Mode Selector Styling

Use the same pill/toggle pattern as the existing `view-selector` in the admin header:

```css
/* Reuse existing .view-selector pattern */
background: var(--bg-muted);
padding: 4px;
border-radius: var(--radius-sm);
gap: 4px;
```

Active mode gets `background: var(--card-bg); color: var(--text-primary); box-shadow: var(--shadow-sm);`

---

## 4. DatePickerGrid Component

### File: `web/src/components/DatePickerGrid.jsx`

A self-contained, zero-dependency month calendar grid component.

### Props

```javascript
DatePickerGrid.propTypes = {
  selectedDates: PropTypes.arrayOf(PropTypes.string), // ["2026-07-01", ...]
  onDateToggle: PropTypes.func,                       // (dateStr) => void
  maxSelections: PropTypes.number,                    // 14
  minDate: PropTypes.string,                          // "2026-05-27" (today)
};
```

### Behavior

- Displays one month at a time with `<` / `>` navigation arrows
- Click a date to toggle selection (add/remove from array)
- Selected dates highlighted with `var(--primary)` background
- Past dates grayed out and non-clickable
- Today highlighted with a subtle ring
- When `maxSelections` reached, unselected dates become non-clickable with a tooltip/visual cue
- Month/year header shows current displayed month

### Internal State

```javascript
const [displayMonth, setDisplayMonth] = useState(() => {
  // Start on current month
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() };
});
```

### Rendering Logic

```javascript
// Generate days grid for the displayed month
const firstDay = new Date(year, month, 1);
const lastDay = new Date(year, month + 1, 0);
const startDayOfWeek = firstDay.getDay(); // 0=Sun, adjust for Mon start
const totalDays = lastDay.getDate();

// Render 6 rows × 7 columns grid
// Each cell: empty (padding), past (disabled), available (clickable), selected (highlighted)
```

### CSS (inline styles or Admin.css additions)

```css
.date-picker-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
  padding: 12px;
  background: var(--card-bg);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
}

.date-picker-cell {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.date-picker-cell:hover:not(.disabled):not(.selected) {
  background: var(--bg-muted);
}

.date-picker-cell.selected {
  background: var(--primary);
  color: white;
  font-weight: 700;
}

.date-picker-cell.today:not(.selected) {
  border: 2px solid var(--primary);
}

.date-picker-cell.disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.date-picker-cell.max-reached:not(.selected) {
  opacity: 0.4;
  cursor: not-allowed;
}
```

---

## 5. Updated Form State

```javascript
const [newVisitForm, setNewVisitForm] = useState({
  client_id: '', client_name: '', client_email: '', client_phone: '',
  pet_names: '', pet_ids: [], service_type: 'PET_SITTING',
  start_date: '', end_date: '',
  selected_dates: [],          // NEW
  schedule_mode: 'single',     // NEW: 'single' | 'range' | 'pick_days'
  visit_windows: ['ANYTIME'],
  details: '', preferred_sitter: ''
});
```

### Reset on Modal Close

```javascript
const handleCloseNewVisitModal = () => {
  setNewVisitModal(false);
  setNewVisitForm({
    client_id: '', client_name: '', client_email: '', client_phone: '',
    pet_names: '', pet_ids: [], service_type: 'PET_SITTING',
    start_date: '', end_date: '',
    selected_dates: [],
    schedule_mode: 'single',
    visit_windows: ['ANYTIME'],
    details: '', preferred_sitter: ''
  });
  // ... existing cleanup ...
};
```

---

## 6. Payload Mapping

### handleNewVisitSubmit — Updated Logic

```javascript
const handleNewVisitSubmit = async () => {
  // Validation
  if (!newVisitForm.client_id) { showNotification("Please select a client.", "error"); return; }
  if (!newVisitForm.pet_names && newVisitForm.pet_ids.length === 0) { ... return; }

  // Mode-specific validation
  if (newVisitForm.schedule_mode === 'single' && !newVisitForm.start_date) {
    showNotification("Start date is required.", "error"); return;
  }
  if (newVisitForm.schedule_mode === 'range' && (!newVisitForm.start_date || !newVisitForm.end_date)) {
    showNotification("Start and end dates are required for date range.", "error"); return;
  }
  if (newVisitForm.schedule_mode === 'pick_days' && newVisitForm.selected_dates.length === 0) {
    showNotification("Please select at least one date.", "error"); return;
  }

  // Build payload based on mode
  const payload = {
    client_id: newVisitForm.client_id,
    client_name: newVisitForm.client_name,
    client_email: newVisitForm.client_email,
    client_phone: newVisitForm.client_phone,
    pet_names: newVisitForm.pet_names,
    pet_ids: newVisitForm.pet_ids,
    service_type: newVisitForm.service_type,
    visit_windows: newVisitForm.visit_windows,
    details: newVisitForm.details || undefined,
    preferred_sitter: newVisitForm.preferred_sitter || undefined,
  };

  if (newVisitForm.schedule_mode === 'single') {
    payload.start_date = newVisitForm.start_date;
  } else if (newVisitForm.schedule_mode === 'range') {
    payload.start_date = newVisitForm.start_date;
    payload.end_date = newVisitForm.end_date;
  } else if (newVisitForm.schedule_mode === 'pick_days') {
    const sorted = [...newVisitForm.selected_dates].sort();
    payload.selected_dates = sorted;
    payload.start_date = sorted[0]; // Backend requires start_date
  }

  setIsCreatingVisit(true);
  try {
    const resp = await createAdminBooking(payload);
    // ... existing success handling ...
  } catch (err) { ... }
};
```

---

## 7. Validation Rules (Frontend)

| Rule | Enforcement | UX |
|------|-------------|-----|
| At least 1 date selected (pick_days mode) | Submit button disabled | "Select at least one date" |
| Max 14 dates | Calendar cells become non-clickable at 14 | Counter shows "6/14 selected" |
| No past dates | Calendar cells for past dates are grayed/disabled | Visual only |
| Start date required (single/range) | Submit button disabled | Existing behavior |
| End date required (range mode) | Submit button disabled | Validation message |
| End date must be after start date (range) | Validation on submit | Error notification |

### Submit Button Disabled Logic

```javascript
disabled={
  isCreatingVisit ||
  !newVisitForm.client_id ||
  (!newVisitForm.pet_names && newVisitForm.pet_ids.length === 0) ||
  (newVisitForm.schedule_mode === 'single' && !newVisitForm.start_date) ||
  (newVisitForm.schedule_mode === 'range' && (!newVisitForm.start_date || !newVisitForm.end_date)) ||
  (newVisitForm.schedule_mode === 'pick_days' && newVisitForm.selected_dates.length === 0)
}
```

---

## 8. Edge Cases

| Edge Case | Handling |
|-----------|---------|
| User switches mode after selecting dates | Clear `selected_dates` when switching away from pick_days; clear `start_date`/`end_date` when switching away from range |
| User selects 14 dates then tries to add more | 15th click is no-op; visual indicator shows "Maximum reached" |
| User deselects all dates in pick_days mode | Submit button disabled; counter shows "0/14 selected" |
| User navigates to a past month | Past dates are disabled; can still navigate to see them |
| User selects dates across multiple months | Works naturally — navigate months, click dates, all accumulate in `selected_dates` |
| Modal reopened after previous booking | Form resets completely (existing behavior) |
| Very small screen (mobile web) | Calendar grid cells shrink; 7-column grid still fits at 36px cells = 252px + gaps |

---

## 9. Selected Dates Summary Display

Below the calendar grid, show a clear summary:

```
┌──────────────────────────────────────────┐
│ ✓ 6 days selected (max 14)              │
│ Jul 1, Jul 4, Jul 8, Jul 11, Jul 15, Jul 18 │
│                                          │
│ [Clear All]                              │
└──────────────────────────────────────────┘
```

- Shows count with max indicator
- Lists dates in short format (Mon DD)
- "Clear All" button to reset selection
- If > 7 dates, show first 5 + "and N more" with expand option

---

## 10. Files to Modify

| File | Change | New? |
|------|--------|------|
| `web/src/components/DatePickerGrid.jsx` | New calendar grid component | ✅ New |
| `web/src/components/AdminDashboard.jsx` | Add schedule mode selector, wire DatePickerGrid, update payload | Modified |
| `web/src/Admin.css` | Add `.date-picker-*` styles, `.schedule-mode-selector` styles | Modified |

### Files NOT Modified

- No backend changes
- No API client changes (`createAdminBooking` already passes through any payload fields)
- No Terraform changes
- No test file changes (manual frontend testing)

---

## 11. Confirmation: Frontend-Only

This is entirely frontend-only:
- The backend already accepts `selected_dates` (Phase 2A deployed)
- The API client (`web/src/api/client.js` → `createAdminBooking`) passes the full payload object to the backend — no changes needed
- No new API routes, no Terraform, no Lambda changes

---

## 12. Test Plan

### Manual Testing Checklist

| # | Test | Expected |
|---|------|----------|
| 1 | Open New Visit → default mode is "Single Day" | Single date input shown |
| 2 | Switch to "Date Range" | Start + End date inputs shown |
| 3 | Switch to "Pick Days" | Calendar grid shown |
| 4 | Click 3 dates on calendar | 3 dates highlighted, counter shows "3/14" |
| 5 | Click a selected date again | Deselected, counter decrements |
| 6 | Select 14 dates | 15th click is blocked, visual indicator |
| 7 | Navigate to next month | Calendar updates, selections persist |
| 8 | Navigate to previous month (past) | Past dates disabled |
| 9 | Click "Clear All" | All selections removed |
| 10 | Submit with 4 picked dates | API call includes `selected_dates: [...]` |
| 11 | Switch from "Pick Days" to "Single Day" | `selected_dates` cleared |
| 12 | Submit single-day booking | Payload has `start_date` only, no `selected_dates` |
| 13 | Submit date-range booking | Payload has `start_date` + `end_date`, no `selected_dates` |
| 14 | `npm run build` passes | No build errors |
| 15 | Verify production: 4 picked dates → 4 JOBs + 4 calendar events | End-to-end |

### Build Validation

```bash
cd web
npm run build
```

---

## 13. Deployment

```bash
# Frontend deploy (after build passes):
aws s3 sync web/dist/ s3://togs-and-dogs-prod-toganddogs-hosting --delete --profile usmissionhero-website-prod

# CloudFront invalidation:
aws cloudfront create-invalidation --distribution-id <DIST_ID> --paths "/*" --profile usmissionhero-website-prod
```

No Terraform apply needed.

---

## 14. AG Implementation Prompt

```
AG — implement Release 7E Phase 2B: Frontend Date Picker for Selected-Day Scheduling.

Frontend-only changes. No backend, Terraform, or API client modifications.

=== 1. Create web/src/components/DatePickerGrid.jsx ===

A self-contained month calendar grid component with these props:
- selectedDates: string[] (YYYY-MM-DD format)
- onDateToggle: (dateStr: string) => void
- maxSelections: number (default 14)
- minDate: string (YYYY-MM-DD, default today)

Behavior:
- Displays one month at a time with < > navigation arrows
- Week starts on Monday
- Click a date to toggle selection
- Selected dates: var(--primary) background, white text
- Today: 2px solid var(--primary) ring (when not selected)
- Past dates: opacity 0.3, cursor not-allowed
- Max reached (non-selected): opacity 0.4, cursor not-allowed
- Month/year header centered between nav arrows

Styling: Use inline styles matching existing modal patterns (var(--primary), var(--card-bg), var(--border-soft), var(--radius-md), var(--text-muted)).
Keep the component under 150 lines. No external dependencies.

=== 2. Modify web/src/components/AdminDashboard.jsx ===

a) Update newVisitForm initial state — add:
   selected_dates: [],
   schedule_mode: 'single',  // 'single' | 'range' | 'pick_days'

b) Update handleCloseNewVisitModal reset — add same new fields.

c) Replace the current Dates section (the flex row with Start Date / End Date inputs)
   with a schedule mode selector + conditional content:

   Schedule mode selector (pill toggle, same style as .view-selector):
   - "Single Day" | "Date Range" | "Pick Days"
   - Default: "Single Day"

   When "Single Day": Show single date input (label: "Date *")
   When "Date Range": Show start + end date inputs (existing layout)
   When "Pick Days": Show DatePickerGrid + summary below it

   When switching modes, clear the other mode's data:
   - Switching TO single: clear end_date, selected_dates
   - Switching TO range: clear selected_dates
   - Switching TO pick_days: clear start_date, end_date

d) Below DatePickerGrid, show a summary line:
   "{N}/14 days selected" + date chips (short format: "Jul 1, Jul 4, ...")
   + "Clear All" link/button

e) Update handleNewVisitSubmit:
   - Mode-specific validation (see plan section 6)
   - Mode-specific payload construction:
     * single: { start_date }
     * range: { start_date, end_date }
     * pick_days: { selected_dates: sorted, start_date: sorted[0] }

f) Update submit button disabled logic to account for all three modes.

g) Import DatePickerGrid at the top of the file.

=== 3. Add CSS to web/src/Admin.css ===

Add styles for:
- .schedule-mode-selector (reuse .view-selector pattern)
- .date-picker-summary (counter + date chips)
- .date-chip (small pill showing selected date)

Keep styles minimal — most styling is inline in the component.

=== 4. Validation ===

Run: npm run build (in web/)
Confirm no errors.
Do NOT deploy yet.

Return:
- Files created/modified
- Build result
- Screenshot description of the UI if possible
- Any warnings or issues found
```

---

## 15. Commit Command

```bash
git add web/src/components/DatePickerGrid.jsx web/src/components/AdminDashboard.jsx web/src/Admin.css
git commit -m "feat: Release 7E Phase 2B — date picker grid for selected-day multi-visit booking"
```
