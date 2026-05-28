# Release 7E Phase 2C: Public Intake Selected-Day Scheduling

**Status:** Planning
**Priority:** Medium
**Risk to Production:** Low (additive UI change to existing form)
**Terraform Required:** No
**Backend Changes:** None (Phase 2A already handles `selected_dates`)
**Scope:** Frontend-only — `IntakeForm.jsx` + reuse `DatePickerGrid.jsx`

---

## 1. Objective

Add selected-day scheduling to the public `/book` intake form so clients can request care on specific non-consecutive dates (e.g., "I need walks on July 1, 3, 5, 8, 10, 12") without forcing them to use a continuous date range.

The UX must be simpler and more guided than the admin version — clients are non-technical and may be on mobile.

---

## 2. Current Public Intake Form (Step 2: Schedule)

### Layout

```
┌─────────────────────────────────────────────┐
│ When do you need care?                       │
│                                              │
│ Service Type *    [dropdown]                 │
│                                              │
│ Start Date *      [date input]               │
│ End Date          [date input]               │
│                                              │
│ Preferred Visit Windows                      │
│ [Morning] [Midday] [Afternoon] [Evening]     │
│ [Anytime]                                    │
│                                              │
│ Preferred Sitter  [dropdown]                 │
│ Timing Notes      [text input]               │
│                                              │
│              [← Back] [Next: Pet Info →]      │
└─────────────────────────────────────────────┘
```

### Current State Shape (Step 2 fields)

```javascript
{
  service_type: 'PET_SITTING',
  start_date: '',
  end_date: '',
  visit_windows: ['ANYTIME'],
  visit_window: 'ANYTIME',
  preferred_time: '',
  timing_notes: '',
  preferred_sitter: '',
  preferred_sitter_name: ''
}
```

### Submission Paths

- **Public (unauthenticated):** `POST /requests` via `submitRequest(payload)`
- **Authenticated client:** `POST /client/requests` via `submitClientRequest(data)`

Both pass the full `formData` object. The backend `intake_handler.py` already accepts `selected_dates` from Phase 2A.

---

## 3. Proposed UX: Client-Friendly Date Selection

### Design Principle

Clients should not need to understand "modes." Instead, present a natural question flow:

```
"How many days do you need care?"
  ○ Just one day
  ○ Every day in a date range
  ○ Specific days I'll pick
```

### Proposed Layout (Step 2 — Updated)

```
┌─────────────────────────────────────────────┐
│ When do you need care?                       │
│                                              │
│ Service Type *    [dropdown]                 │
│                                              │
│ How many days? *                             │
│ ┌─────────────────────────────────────────┐  │
│ │ ○ Just one day                          │  │
│ │ ○ Every day in a date range             │  │
│ │ ○ Specific days I'll pick               │  │
│ └─────────────────────────────────────────┘  │
│                                              │
│ ── When "Just one day": ──                   │
│ Date *  [2026-07-15]                         │
│                                              │
│ ── When "Every day in a date range": ──      │
│ First Day * [2026-07-01]                     │
│ Last Day *  [2026-07-05]                     │
│ (We'll visit every day in this range)        │
│                                              │
│ ── When "Specific days I'll pick": ──        │
│ ┌─── July 2026 ──────── [<] [>] ──┐         │
│ │ Mo  Tu  We  Th  Fr  Sa  Su      │         │
│ │      ①   2   3  ④   5   6      │         │
│ │  7  ⑧   9  10  ⑪  12  13      │         │
│ │ 14  ⑮  16  17  ⑱  19  20      │         │
│ └──────────────────────────────────┘         │
│ ✓ 6 days selected (max 14)                  │
│ Jul 1, 4, 8, 11, 15, 18                     │
│                                              │
│ Preferred Visit Windows                      │
│ [Morning] [Midday] [Afternoon] [Evening]     │
│                                              │
│ Preferred Sitter  [dropdown]                 │
│ Timing Notes      [text input]               │
│                                              │
│              [← Back] [Next: Pet Info →]      │
└─────────────────────────────────────────────┘
```

### Why Radio Buttons (Not Tabs/Pills)

- Radio buttons are universally understood by non-technical users
- They read as a natural question ("How many days?")
- They work perfectly on mobile without horizontal scrolling
- They don't look like a "mode switch" that might confuse older clients

---

## 4. Component Reuse

### DatePickerGrid.jsx — Already Built (Phase 2B)

The `DatePickerGrid` component from the admin portal can be reused directly:
- Same props: `selectedDates`, `onDateToggle`, `maxSelections`, `minDate`
- Same behavior: click to toggle, month navigation, past dates disabled
- Styling adapts via CSS variables (public form uses the same design system)

### Styling Adjustments for Public Form

The public form uses slightly larger touch targets and more spacing than the admin modal. The DatePickerGrid should:
- Use `width: 100%` (fills the form column)
- Cell size: 40px × 40px (slightly larger than admin's 36px for mobile friendliness)
- Font size: 0.9rem (matches public form body text)

These can be controlled via a `className` prop or wrapper div styling.

---

## 5. Updated Form State

```javascript
const [formData, setFormData] = useState({
  // ... existing fields ...
  start_date: '',
  end_date: '',
  selected_dates: [],           // NEW
  schedule_mode: 'single',      // NEW: 'single' | 'range' | 'pick_days'
  visit_windows: ['ANYTIME'],
  // ... rest unchanged ...
});
```

---

## 6. Payload Mapping

### On Submit — Mode-Specific Payload

```javascript
const payload = { ...formData };

if (formData.schedule_mode === 'single') {
  // Send start_date only, clear multi-day fields
  delete payload.end_date;
  delete payload.selected_dates;
} else if (formData.schedule_mode === 'range') {
  // Send start_date + end_date, clear selected_dates
  delete payload.selected_dates;
} else if (formData.schedule_mode === 'pick_days') {
  // Send selected_dates array + set start_date/end_date for display
  const sorted = [...formData.selected_dates].sort();
  payload.selected_dates = sorted;
  payload.start_date = sorted[0];
  payload.end_date = sorted[sorted.length - 1];
}

// Always clean up internal-only field
delete payload.schedule_mode;
```

### Backend Compatibility

The backend `intake_handler.py` (public intake path) already stores whatever fields are in the payload. The `job_handler.py` (Phase 2A) already checks for `selected_dates` first. No backend changes needed.

---

## 7. Validation Rules

### Step 2 Validation (`validateStep`)

```javascript
if (step === 2) {
  if (!formData.service_type) return false;
  
  if (formData.schedule_mode === 'single') {
    return !!formData.start_date;
  } else if (formData.schedule_mode === 'range') {
    return !!formData.start_date && !!formData.end_date;
  } else if (formData.schedule_mode === 'pick_days') {
    return formData.selected_dates.length > 0;
  }
  return false;
}
```

### Frontend Constraints

| Rule | Enforcement |
|------|-------------|
| At least 1 date (pick_days) | "Next" button disabled |
| Max 14 dates | Calendar cells non-clickable at 14 |
| No past dates | Calendar cells disabled |
| End date after start date (range) | Validation on "Next" click |
| Service type required | Existing validation |

---

## 8. Edge Cases

| Edge Case | Handling |
|-----------|---------|
| Client switches mode after selecting dates | Clear `selected_dates` when leaving pick_days; clear `end_date` when leaving range |
| Client on mobile (small screen) | Calendar grid cells at 40px fit in 320px viewport (7 × 40 + 6 × 4 gap = 304px) |
| Client selects 1 date in pick_days mode | Valid — creates single-day booking (backend handles gracefully) |
| Client navigates months and selects across months | Works — DatePickerGrid accumulates selections across months |
| Client goes back to Step 1 then returns to Step 2 | Selections preserved in formData state |
| Authenticated client vs public client | Same form, different submit endpoint — both pass same payload |
| Client doesn't understand "date range" | Helper text: "We'll visit every day in this range" |

---

## 9. Mobile Layout Considerations

The public intake form is the primary mobile-facing form. Key considerations:

| Concern | Solution |
|---------|----------|
| Calendar grid width | 7 columns × 40px + gaps = ~304px — fits 320px viewport |
| Radio button touch targets | Min 44px height per option (WCAG) |
| Month navigation arrows | Min 44px × 44px touch targets |
| Selected dates summary | Wraps naturally; shows "and N more" if > 5 dates |
| Form scrolling | Calendar adds ~280px height — acceptable within scrollable form |

---

## 10. Files to Modify

| File | Change | New? |
|------|--------|------|
| `web/src/components/IntakeForm.jsx` | Add schedule mode radio, wire DatePickerGrid, update validation/payload | Modified |
| `web/src/components/IntakeForm.css` | Add `.schedule-mode-radio`, `.date-summary-public` styles | Modified |
| `web/src/components/DatePickerGrid.jsx` | No changes needed (reuse as-is) | Unchanged |

### Files NOT Modified

- No backend changes
- No `AdminDashboard.jsx` changes
- No API client changes (payload passes through)
- No Terraform changes
- No `Admin.css` changes

---

## 11. Confirmation: Frontend-Only

- Backend already accepts `selected_dates` (Phase 2A)
- Both `submitRequest()` and `submitClientRequest()` pass the full payload object
- `intake_handler.py` stores all fields from the body
- `job_handler.py` checks `selected_dates` first in its date resolution
- No new API routes, no Terraform, no Lambda changes

---

## 12. Phased Implementation

### Phase 2C-1: Add Schedule Mode + Date Picker (~1 hour)

1. Add `schedule_mode` and `selected_dates` to formData state
2. Add radio button group ("How many days?") above the date inputs
3. Conditionally render: single date input / range inputs / DatePickerGrid
4. Add selected dates summary below calendar
5. Clear irrelevant fields on mode switch

### Phase 2C-2: Update Validation + Payload (~30 min)

1. Update `validateStep()` for step 2 to handle all three modes
2. Update `handleSubmit` payload construction (mode-specific)
3. Remove `schedule_mode` from submitted payload (internal-only)

### Phase 2C-3: Styling + Mobile Polish (~30 min)

1. Add CSS for radio group, calendar wrapper, summary chips
2. Test on narrow viewport (320px)
3. Verify touch targets meet 44px minimum

### Phase 2C-4: Build + Manual Test (~30 min)

1. `npm run build`
2. Test all three modes end-to-end
3. Verify backend creates correct JOBs for each mode

---

## 13. Test Plan

### Manual Testing Checklist

| # | Test | Expected |
|---|------|----------|
| 1 | Default mode is "Just one day" | Single date input shown |
| 2 | Select "Every day in a date range" | Start + End inputs shown |
| 3 | Select "Specific days I'll pick" | Calendar grid shown |
| 4 | Pick 3 dates on calendar | Summary shows "3/14 days selected" |
| 5 | Click "Next" with 0 dates in pick_days | Blocked — validation fails |
| 6 | Submit with 4 picked dates | Payload includes `selected_dates: [...]` |
| 7 | Submit single day | Payload has `start_date` only |
| 8 | Submit date range | Payload has `start_date` + `end_date` |
| 9 | Switch from pick_days to single | `selected_dates` cleared |
| 10 | Mobile viewport (375px) | Calendar fits, radio buttons stack, touch targets adequate |
| 11 | Navigate months in calendar | Selections persist across months |
| 12 | Select 14 dates | 15th click blocked |
| 13 | `npm run build` passes | No errors |
| 14 | Production: 3 picked dates → 3 JOBs + 3 calendar events | End-to-end |

---

## 14. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Existing single-day intake breaks | Very Low | High | Default mode is "Just one day" — identical to current behavior |
| Calendar confuses older clients | Low | Low | Clear label "Specific days I'll pick" + helper text |
| Mobile layout breaks | Low | Medium | Calendar grid fits 320px; test on real device |
| Backend rejects selected_dates from public path | None | — | Already tested in Phase 2A; both intake paths pass through |
| Client selects too many dates | None | — | 14-date cap enforced in UI + backend |

---

## 15. AG Implementation Prompt

```
AG — implement Release 7E Phase 2C: Public Intake Selected-Day Scheduling.

Frontend-only changes in web/src/components/IntakeForm.jsx and IntakeForm.css.
Reuse the existing DatePickerGrid.jsx component (no changes to it).

=== 1. web/src/components/IntakeForm.jsx ===

a) Add to formData initial state:
   selected_dates: [],
   schedule_mode: 'single',  // 'single' | 'range' | 'pick_days'

b) In Step 2, replace the current date inputs section with:

   i. A radio button group labeled "How many days? *":
      - "Just one day" (value: 'single') — DEFAULT
      - "Every day in a date range" (value: 'range')
      - "Specific days I'll pick" (value: 'pick_days')

   ii. Conditional content based on schedule_mode:
      - 'single': Single date input (label: "Date *")
      - 'range': Start Date + End Date inputs (existing layout)
        Helper text below: "We'll visit every day in this range."
      - 'pick_days': DatePickerGrid component + summary

   iii. When switching modes, clear the other mode's data:
      - TO single: clear end_date, selected_dates
      - TO range: clear selected_dates
      - TO pick_days: clear start_date, end_date

c) Below DatePickerGrid (in pick_days mode), show:
   "{N}/14 days selected"
   Comma-separated short date list (e.g., "Jul 1, Jul 4, Jul 8")
   If 0 selected: "Tap dates on the calendar above"

d) Update validateStep() for step 2:
   - single: requires start_date
   - range: requires start_date AND end_date
   - pick_days: requires selected_dates.length > 0

e) Update handleSubmit payload construction:
   - single: payload.start_date = formData.start_date; delete selected_dates, end_date
   - range: payload.start_date + payload.end_date; delete selected_dates
   - pick_days: sorted = [...selected_dates].sort();
     payload.selected_dates = sorted;
     payload.start_date = sorted[0];
     payload.end_date = sorted[sorted.length - 1];
   - Always delete schedule_mode from payload (internal-only)

f) Import DatePickerGrid at the top:
   import DatePickerGrid from './DatePickerGrid';

g) Pass to DatePickerGrid:
   selectedDates={formData.selected_dates}
   onDateToggle={(dateStr) => {
     setFormData(prev => {
       const dates = prev.selected_dates.includes(dateStr)
         ? prev.selected_dates.filter(d => d !== dateStr)
         : [...prev.selected_dates, dateStr];
       return { ...prev, selected_dates: dates };
     });
   }}
   maxSelections={14}
   minDate={new Date().toISOString().split('T')[0]}

=== 2. web/src/components/IntakeForm.css ===

Add styles for:
- .schedule-mode-group (radio button container)
- .schedule-mode-option (individual radio label — min 44px height)
- .schedule-mode-option.selected (highlighted state)
- .date-summary-public (selected dates counter + list)

Style the radio group to look like card-style options:
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  padding: 12px 16px;
  cursor: pointer;
  transition: border-color 0.2s;

Selected state:
  border-color: var(--primary);
  background: var(--accent-soft, rgba(74, 144, 217, 0.05));

=== 3. Do NOT modify ===
- DatePickerGrid.jsx (reuse as-is)
- AdminDashboard.jsx
- Backend files
- API client files
- Terraform

=== 4. Validation ===

Run: npm run build (in web/)
Confirm no errors.
Do NOT deploy yet.

Return:
- Files modified
- Build result
- Any warnings
```

---

## 16. Commit Command

```bash
git add web/src/components/IntakeForm.jsx web/src/components/IntakeForm.css
git commit -m "feat: Release 7E Phase 2C — public intake selected-day scheduling"
```
