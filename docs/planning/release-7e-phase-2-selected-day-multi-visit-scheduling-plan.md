# Release 7E Phase 2: Selected-Day Multi-Visit Scheduling

**Status:** Planning
**Priority:** Medium (operational improvement for Ryan)
**Risk to Production:** Low (additive payload field, no changes to existing flows)
**Terraform Required:** No
**Frontend Changes:** Yes (New Visit modal date picker enhancement)
**Designation:** Release 7E Phase 2 (not a new release — extends the same multi-day architecture)

---

## 1. Objective

Allow admins to select specific non-consecutive dates for a multi-visit booking (e.g., Tuesday and Friday over 3 weeks) instead of only supporting continuous daily date ranges.

**Example use case:** Ryan books a client for walks every Tuesday and Friday for 3 weeks. Today he must create 6 separate bookings. With this feature, he selects 6 dates in one booking and the system creates 6 child JOBs automatically.

---

## 2. Current State (After Phase 1/1A)

### What Works Today

| Booking Type | How It Works |
|-------------|-------------|
| Single-day | `start_date` only → 1 JOB, 1 calendar event |
| Daily range | `start_date` + `end_date` → N JOBs (one per day in range) |

### Current Frontend Form Fields (New Visit Modal)

```javascript
{
  client_id, client_name, client_email, client_phone,
  pet_names, pet_ids, service_type,
  start_date,      // Required: YYYY-MM-DD
  end_date,        // Optional: YYYY-MM-DD (triggers daily range)
  visit_windows,   // ["MORNING"] etc.
  details, preferred_sitter
}
```

### Current Backend Date Resolution (job_handler.py)

```python
if start_date and end_date and end_date > start_date:
    # Create one JOB per day in range (inclusive)
else:
    # Single day: one JOB
```

---

## 3. Proposed Design: `selected_dates` Payload

### New Field: `selected_dates`

Add an optional `selected_dates` array to the booking payload. When present, it takes priority over the `start_date`/`end_date` range logic.

```json
{
  "client_id": "client-123",
  "pet_ids": ["pet-001"],
  "service_type": "WALK_30MIN",
  "start_date": "2026-07-01",
  "selected_dates": ["2026-07-01", "2026-07-03", "2026-07-05", "2026-07-08", "2026-07-10", "2026-07-12"],
  "visit_windows": ["MORNING"],
  "details": "Back gate code: 1234"
}
```

### Priority Cascade for Date Resolution

```
1. selected_dates (array of specific dates) → one JOB per date
2. start_date + end_date (range) → one JOB per day in range (existing Phase 1)
3. start_date only → single JOB (existing)
```

### Validation Rules

| Rule | Enforcement |
|------|-------------|
| Max 14 dates per request | Same limit as daily range |
| All dates must be valid YYYY-MM-DD | Backend validation |
| All dates must be in the future (or today) | Backend validation |
| Dates must be unique (no duplicates) | Backend dedup |
| Dates are sorted chronologically | Backend sort before JOB creation |
| `start_date` must be present | Required field (set to first selected date if not explicit) |
| `end_date` is optional | If present with `selected_dates`, `selected_dates` wins |

---

## 4. Backend Changes

### 4.1 `intake_handler.py` — Accept `selected_dates`

In the admin booking creation section:

```python
# Store selected_dates on the REQ record
'selected_dates': body.get('selected_dates') or None,
```

Also set `start_date` to the first selected date and `end_date` to the last selected date for display purposes:

```python
selected_dates = body.get('selected_dates')
if selected_dates and isinstance(selected_dates, list) and len(selected_dates) > 1:
    # Sort and validate
    valid_dates = sorted(set(d for d in selected_dates if _is_valid_date(d)))
    if valid_dates:
        start_date = valid_dates[0]
        end_date = valid_dates[-1]
```

### 4.2 `job_handler.py` — Resolve `selected_dates` Before Range Logic

Add a new priority check before the existing range expansion:

```python
# Priority 1: Explicit selected_dates array
selected_dates = request_item.get('selected_dates')
if selected_dates and isinstance(selected_dates, list) and len(selected_dates) > 1:
    # Validate, dedup, sort
    valid_dates = sorted(set(d for d in selected_dates if _is_valid_date(d)))
    if len(valid_dates) > MAX_MULTI_DAY_OCCURRENCES:
        return {"error": f"Selected dates ({len(valid_dates)}) exceeds maximum of {MAX_MULTI_DAY_OCCURRENCES}"}
    job_dates = valid_dates

# Priority 2: start_date + end_date range (existing Phase 1 logic)
elif start_date_str and end_date_str:
    # ... existing range expansion ...

# Priority 3: Single day
else:
    job_dates = [start_date_str] if start_date_str else [None]
```

### 4.3 No Changes to Calendar Sync

The existing Phase 1A calendar sync logic already handles any list of `job_dates` — it creates one calendar event per JOB using `occurrence_date` as the event date. No changes needed.

### 4.4 No Changes to Cascade or Purge

The existing cascade and purge logic operates on `job_ids` array regardless of how the dates were selected. No changes needed.

---

## 5. Frontend Changes

### 5.1 New Visit Modal — Date Selection Mode

Add a toggle or tab to switch between date input modes:

```
┌─────────────────────────────────────────────┐
│ Schedule Type:                               │
│ ○ Single Day    ○ Date Range    ● Pick Days  │
│                                              │
│ [Calendar Grid - July 2026]                  │
│  Mo Tu We Th Fr Sa Su                        │
│      [1]  2  [3]  4  [5]  6                 │
│   7  [8]  9 [10] 11 [12] 13                 │
│  14  15  16  17  18  19  20                  │
│                                              │
│ Selected: 6 days                             │
│ Jul 1, 3, 5, 8, 10, 12                      │
└─────────────────────────────────────────────┘
```

### 5.2 Implementation Options for Date Picker

**Option A: Inline clickable calendar grid (Recommended)**

- Build a simple month-view calendar component
- Click dates to toggle selection (highlighted when selected)
- Show selected count and date list below
- No external dependency needed — pure React with CSS grid
- Fits within the existing modal layout

**Option B: Multi-date input with "Add Date" button**

- Text input + "Add" button, dates appear as chips/tags
- Simpler to build but less intuitive
- Harder to visualize which days are selected

**Option C: Third-party date picker library**

- Libraries like `react-multi-date-picker` or `react-day-picker`
- Adds a dependency to the project
- More polished but heavier

**Recommendation: Option A** — a simple custom calendar grid. It's lightweight, no new dependencies, and gives Ryan a visual way to pick days. The component is ~100 lines of React.

### 5.3 Form State Changes

```javascript
const [newVisitForm, setNewVisitForm] = useState({
  // ... existing fields ...
  start_date: '', end_date: '', 
  selected_dates: [],           // NEW: array of YYYY-MM-DD strings
  schedule_mode: 'single',      // NEW: 'single' | 'range' | 'pick_days'
  visit_windows: ['ANYTIME'],
  details: '', preferred_sitter: ''
});
```

### 5.4 Payload Construction

```javascript
const handleNewVisitSubmit = async () => {
  const payload = {
    client_id, client_name, pet_ids, service_type, visit_windows, ...
  };

  if (newVisitForm.schedule_mode === 'pick_days') {
    payload.selected_dates = newVisitForm.selected_dates;
    payload.start_date = newVisitForm.selected_dates[0]; // Required field
  } else if (newVisitForm.schedule_mode === 'range') {
    payload.start_date = newVisitForm.start_date;
    payload.end_date = newVisitForm.end_date;
  } else {
    payload.start_date = newVisitForm.start_date;
  }

  await createAdminBooking(payload);
};
```

---

## 6. Request List Display

**No changes needed.** The Request List already shows only parent REQ rows. For selected-dates bookings:
- `start_date` = first selected date
- `end_date` = last selected date
- Display: "2026-07-01 to 2026-07-12" (same as range bookings)
- The `selected_dates` array is stored on the REQ for reference but not displayed in the list

---

## 7. Why This Is Phase 2 (Not a New Release)

| Factor | Assessment |
|--------|-----------|
| Same architecture | Uses identical JOB-per-date pattern from Phase 1 |
| Same cascade/purge | No changes to lifecycle management |
| Same calendar sync | Phase 1A per-JOB sync works for any date list |
| Same 14-day limit | Same safety constraint |
| Same parent REQ model | Just adds `selected_dates` field |
| Incremental frontend change | Extends existing New Visit modal |

This is a natural extension of Phase 1, not a new architectural direction. Calling it Phase 2 keeps the release history clean.

---

## 8. What This Does NOT Include (Deferred)

| Item | Reason | Future Release |
|------|--------|---------------|
| Recurring schedule templates | Requires SCHEDULE entity, builder UI | 8A+ |
| "Every Tuesday for 4 weeks" auto-generation | Template feature | 8A+ |
| Per-day time overrides | Schema complexity | 8A+ |
| Client-facing date picker (intake form) | Different UX context | 8B+ |
| Drag-to-reschedule on calendar | Complex UI feature | 8C+ |
| Bulk reassign selected days | UI convenience | 7E Phase 3 |

---

## 9. Implementation Phases

### Phase 2A: Backend — Accept `selected_dates` (~0.5 day)

1. `intake_handler.py`: Accept and store `selected_dates` on REQ record
2. `job_handler.py`: Add `selected_dates` priority check before range logic
3. Validation: max 14, valid format, dedup, sort
4. Tests: selected_dates creates correct JOBs, priority over range, validation errors

### Phase 2B: Frontend — Date Picker Component (~1 day)

1. Create `web/src/components/DatePickerGrid.jsx` — simple month calendar with click-to-select
2. Add schedule mode toggle to New Visit modal (Single Day / Date Range / Pick Days)
3. Wire `selected_dates` into form state and submission payload
4. Style with existing CSS variables
5. `npm run build` validation

### Phase 2C: Integration Test & Deploy (~0.5 day)

1. End-to-end test: pick 4 dates → verify 4 JOBs + 4 calendar events
2. Verify single-day and range modes still work unchanged
3. Deploy via `terraform apply`
4. Production smoke test

---

## 10. Required Tests

### Backend Tests (`test_r7e_selected_dates.py`)

| # | Test | Description |
|---|------|-------------|
| 1 | `test_selected_dates_creates_correct_jobs` | 4 selected dates → 4 JOBs |
| 2 | `test_selected_dates_priority_over_range` | Both `selected_dates` and `end_date` present → selected_dates wins |
| 3 | `test_selected_dates_dedup` | Duplicate dates in array → deduplicated |
| 4 | `test_selected_dates_sorted` | Unsorted input → JOBs created in chronological order |
| 5 | `test_selected_dates_max_14` | 15 dates → rejected |
| 6 | `test_selected_dates_invalid_format_filtered` | Invalid dates in array → filtered out |
| 7 | `test_selected_dates_single_date_treated_as_single_day` | 1 date in array → single-day behavior |
| 8 | `test_selected_dates_each_job_has_correct_date` | Each JOB's occurrence_date matches its selected date |
| 9 | `test_selected_dates_calendar_sync_per_job` | Each JOB triggers calendar sync |
| 10 | `test_existing_range_behavior_unchanged` | start_date + end_date without selected_dates → same as Phase 1 |
| 11 | `test_single_day_behavior_unchanged` | No end_date, no selected_dates → 1 JOB |

### Frontend Tests (Manual)

- Toggle between Single Day / Date Range / Pick Days modes
- Select dates on calendar grid, verify chips appear
- Deselect a date, verify it's removed
- Submit with 3 picked dates, verify API payload contains `selected_dates`
- Verify existing single-day and range modes still work

---

## 11. Deployment Risk

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Existing single-day bookings break | Very Low | High | `selected_dates` is optional; absence = existing behavior |
| Existing range bookings break | Very Low | High | `selected_dates` takes priority only when present AND has >1 date |
| Calendar grid confuses Ryan | Low | Low | Clear mode toggle; default is "Single Day" |
| Too many dates selected | Very Low | Low | 14-date limit enforced backend |
| Invalid dates in payload | Very Low | None | Backend validation + dedup + sort |

---

## 12. Recommendation

**Implement as Release 7E Phase 2.** The backend change is minimal (one new priority check in `job_handler.py` + one new field on REQ). The frontend is the main work — a simple calendar grid component.

**Suggested order:**
1. Backend first (Phase 2A) — can be deployed independently since `selected_dates` is optional
2. Frontend second (Phase 2B) — adds the UI to use the new field
3. Integration test (Phase 2C) — validate end-to-end

This allows Ryan to continue using single-day and range bookings while the frontend is being built. The backend is backward-compatible from day one.

---

## 13. Commit Commands

```bash
# After Phase 2A (backend):
git add src/backend/handlers/job_handler.py src/backend/handlers/intake_handler.py tests/backend/test_r7e_selected_dates.py
git commit -m "feat: Release 7E Phase 2A — backend support for selected_dates multi-visit booking"

# After Phase 2B (frontend):
git add web/src/components/DatePickerGrid.jsx web/src/components/AdminDashboard.jsx
git commit -m "feat: Release 7E Phase 2B — date picker grid for selected-day multi-visit booking"
```
