# Release 7D: Google Calendar Visit Scheduling Hardening

**Status:** Planning
**Priority:** Medium (UX improvement for Ryan's daily operations)
**Risk to Production:** Very Low (backend-only, non-breaking changes to `_build_event_body`)
**Terraform Required:** No
**Frontend Changes:** No

---

## 1. Objective

Improve Google Calendar event quality so that real visits appear with correct time blocks, service-type color coding, and informative titles/descriptions — reducing Ryan's reliance on the web dashboard for daily schedule awareness.

Currently, many bookings appear as all-day events even when usable time information exists on the record. This release narrows the all-day fallback to only fire when genuinely no time data is available.

---

## 2. Current Behavior Analysis

### How `_build_event_body()` Currently Works

```
1. Extract scheduled_time, scheduled_date (or start_date), scheduled_duration
2. If scheduled_time exists → create timed event (dateTime)
3. If scheduled_time is missing/empty → create all-day event (date)
4. If scheduled_date is missing → skip (no event created)
```

### Problem: Most Bookings Lack `scheduled_time`

The `scheduled_time` field is only populated when:
- An admin explicitly sets it during assignment (rare)
- The assignment handler passes it in the `body` merge

Most bookings have these time-related fields instead:
- `visit_window`: `"MORNING"` | `"MIDDAY"` | `"AFTERNOON"` | `"EVENING"` | `"ANYTIME"`
- `visit_windows`: `["MORNING", "AFTERNOON"]` (array, multi-select)
- `preferred_time`: Free-text field (e.g., "around 10am", "after school")
- `start_date`: Always present for valid bookings

**Result:** Nearly all bookings fall through to the all-day fallback, making the calendar unhelpful for daily scheduling.

### Data Fields Available on Records

| Field | Source | Example | Present On |
|-------|--------|---------|-----------|
| `start_date` | Intake form / Admin booking | `"2026-07-15"` | All bookings |
| `end_date` | Intake form (multi-day) | `"2026-07-17"` | Multi-day only |
| `scheduled_time` | Admin/assignment override | `"09:30"` | Rarely set |
| `scheduled_date` | Admin override | `"2026-07-15"` | Rarely set (alias for start_date) |
| `scheduled_duration` | Admin override | `60` | Rarely set |
| `visit_window` | Intake form (legacy) | `"MORNING"` | Most bookings |
| `visit_windows` | Intake form (array) | `["MIDDAY"]` | Most bookings |
| `preferred_time` | Intake form (free text) | `"around 10am"` | Some bookings |
| `service_type` | Intake form / Admin | `"WALK_30MIN"` | All bookings |
| `source` | System | `"admin_created"` | Admin bookings |

---

## 3. Proposed Time Resolution Logic

### New Priority Cascade in `_build_event_body()`

```
1. scheduled_time (explicit HH:MM) → Exact timed event
2. visit_window/visit_windows → Window-based timed event (use midpoint of window)
3. All-day fallback → Only when no window AND no scheduled_time
```

### Visit Window → Time Mapping

| Window | Start Time | End Time | Rationale |
|--------|-----------|----------|-----------|
| `MORNING` | 08:00 | 09:00* | Early morning slot |
| `MIDDAY` | 11:00 | 12:00* | Late morning / lunch |
| `AFTERNOON` | 14:00 | 15:00* | After lunch |
| `EVENING` | 17:00 | 18:00* | End of day |
| `ANYTIME` | — | — | Falls through to all-day |

*End time = start time + service_type duration (see below)

### Service Type → Default Duration Mapping

| Service Type | Duration (minutes) | Notes |
|-------------|-------------------|-------|
| `WALK_30MIN` | 30 | Short walk |
| `WALK_60MIN` | 60 | Long walk |
| `DROPIN_1HR` | 60 | Standard drop-in |
| `DROPIN_3HR` | 180 | Extended drop-in |
| `OVERNIGHT` | 720 (12 hours) | Evening to morning |
| `PET_SITTING` | 60 | Default assumption |
| `MEET_GREET` | 45 | Initial consultation |
| (unknown) | 60 | Safe default |

### Multi-Window Handling

When `visit_windows` contains multiple values (e.g., `["MORNING", "AFTERNOON"]`):
- Use the **first** window in the array as the calendar time
- Include all windows in the event description for context

### ANYTIME Handling

- `visit_window = "ANYTIME"` or `visit_windows = ["ANYTIME"]` → all-day fallback (no change)
- This preserves the current behavior for genuinely unscheduled bookings

### Overnight Special Case

For `OVERNIGHT` service type:
- If window is `EVENING`: start at 17:00, end next day at 05:00 (12-hour block)
- If no window: create all-day event spanning start_date to end_date (or start_date + 1 day)

---

## 4. Google Calendar Color Coding

Google Calendar supports `colorId` (string "1" through "11") on events:

| colorId | Google Color | Assigned Service Type |
|---------|-------------|----------------------|
| `"9"` | Blueberry (dark blue) | `WALK_30MIN`, `WALK_60MIN` |
| `"7"` | Peacock (teal) | `DROPIN_1HR`, `DROPIN_3HR` |
| `"6"` | Tangerine (orange) | `OVERNIGHT` |
| `"10"` | Basil (dark green) | `PET_SITTING` |
| `"3"` | Grape (purple) | `MEET_GREET` |
| `"8"` | Graphite (gray) | Unknown / fallback |

### Why These Colors?

- Walks = blue (active, outdoor)
- Drop-ins = teal (calm, indoor)
- Overnight = orange (attention, long duration)
- Pet sitting = green (standard care)
- Meet & greet = purple (special/one-time)

---

## 5. Event Title & Description Format

### Current Title Format
```
Tog and Dogs - {pet_names} / {client_name} - {service_type}
```

### Proposed Title Format
```
🐾 {pet_names} — {friendly_service_type} ({time_window_label})
```

Examples:
- `🐾 Buddy — 30-Min Walk (Morning)`
- `🐾 Fido, Max — Overnight Care (Evening)`
- `🐾 Luna — 1-Hour Drop-in (All Day)`

### Proposed Description Format
```
Client: {client_name}
Phone: {client_phone}
Pet(s): {pet_names}
Service: {friendly_service_type}
Window: {visit_window_label}
Staff: {assigned_worker}

Notes: {pet_info or timing_notes}

---
Request ID: {request_id}
Source: {source_label}
```

### Why Change the Title?

- Ryan views the calendar on his phone — shorter titles are more readable
- The emoji prefix makes Tog and Dogs events instantly distinguishable from personal events
- Service type in human-readable form (not `WALK_30MIN`)
- Time window in parentheses gives at-a-glance scheduling context
- Client name moves to description (less important for quick calendar scanning)

---

## 6. Implementation Scope

### Files Modified

| File | Change | Risk |
|------|--------|------|
| `src/backend/common/google_calendar.py` | Update `_build_event_body()` with new time resolution, color, title/description | Low |
| `tests/backend/test_r6g_calendar_all_day.py` | Update existing tests for new behavior | None |
| `tests/backend/test_r7d_calendar_hardening.py` | New test file for window-based timing, colors, title format | None |

### Files NOT Modified

- No frontend changes
- No Terraform changes
- No handler changes (data already flows correctly to `_build_event_body`)
- No DynamoDB schema changes

---

## 7. Detailed Code Changes

### `_build_event_body()` — New Logic

```python
def _build_event_body(item, assigned_worker=None):
    # ... existing field extraction ...

    # NEW: Service type → duration mapping
    SERVICE_DURATIONS = {
        'WALK_30MIN': 30,
        'WALK_60MIN': 60,
        'DROPIN_1HR': 60,
        'DROPIN_3HR': 180,
        'OVERNIGHT': 720,
        'PET_SITTING': 60,
        'MEET_GREET': 45,
    }

    # NEW: Visit window → start hour mapping
    WINDOW_START_HOURS = {
        'MORNING': 8,
        'MIDDAY': 11,
        'AFTERNOON': 14,
        'EVENING': 17,
    }

    # NEW: Service type → Google Calendar colorId
    SERVICE_COLORS = {
        'WALK_30MIN': '9',
        'WALK_60MIN': '9',
        'DROPIN_1HR': '7',
        'DROPIN_3HR': '7',
        'OVERNIGHT': '6',
        'PET_SITTING': '10',
        'MEET_GREET': '3',
    }

    duration_mins = int(item.get('scheduled_duration') or SERVICE_DURATIONS.get(service_type, 60))
    color_id = SERVICE_COLORS.get(service_type, '8')

    # Time resolution cascade:
    # 1. Explicit scheduled_time
    # 2. Visit window → inferred start time
    # 3. All-day fallback

    resolved_start_hour = None

    if not scheduled_time:
        # Try to resolve from visit_windows (array) or visit_window (string)
        windows = item.get('visit_windows') or []
        if not windows:
            single_window = item.get('visit_window', 'ANYTIME')
            windows = [single_window] if single_window else ['ANYTIME']

        # Use first non-ANYTIME window
        for w in windows:
            if w in WINDOW_START_HOURS:
                resolved_start_hour = WINDOW_START_HOURS[w]
                break

    # ... build title, description with new format ...
    # ... if scheduled_time: exact event (existing) ...
    # ... elif resolved_start_hour: window-based timed event (NEW) ...
    # ... else: all-day fallback (existing, narrowed) ...

    # Add colorId to event body
    body['colorId'] = color_id
```

---

## 8. Backward Compatibility & Safety

| Concern | Mitigation |
|---------|-----------|
| Existing all-day events on calendar | Not modified — only new/updated events get new format |
| Records with `ANYTIME` window | Still create all-day events (no change) |
| Records with no window data at all | Still create all-day events (no change) |
| `scheduled_time` still takes priority | Yes — explicit time always wins |
| Calendar sync failures | Still non-blocking (existing try/except pattern) |
| Overnight spanning midnight | Handled with end_date or +1 day logic |

---

## 9. Tests Required

### New Test File: `tests/backend/test_r7d_calendar_hardening.py`

| Test | Description |
|------|-------------|
| `test_window_morning_creates_timed_event` | `visit_windows: ["MORNING"]` → 08:00 start |
| `test_window_midday_creates_timed_event` | `visit_windows: ["MIDDAY"]` → 11:00 start |
| `test_window_afternoon_creates_timed_event` | `visit_windows: ["AFTERNOON"]` → 14:00 start |
| `test_window_evening_creates_timed_event` | `visit_windows: ["EVENING"]` → 17:00 start |
| `test_window_anytime_creates_all_day` | `visit_windows: ["ANYTIME"]` → all-day (unchanged) |
| `test_multi_window_uses_first` | `visit_windows: ["MORNING", "AFTERNOON"]` → 08:00 |
| `test_scheduled_time_overrides_window` | Both present → scheduled_time wins |
| `test_service_type_duration_walk_30` | WALK_30MIN → 30-minute event block |
| `test_service_type_duration_dropin_3hr` | DROPIN_3HR → 180-minute event block |
| `test_service_type_duration_overnight` | OVERNIGHT + EVENING → 12-hour block |
| `test_color_id_walk` | WALK_30MIN → colorId "9" |
| `test_color_id_dropin` | DROPIN_1HR → colorId "7" |
| `test_color_id_overnight` | OVERNIGHT → colorId "6" |
| `test_title_format_with_emoji` | Title starts with 🐾 and uses friendly service name |
| `test_description_includes_client_phone` | Description contains phone if available |
| `test_description_includes_source_label` | Admin-created bookings show "Source: Admin Created" |
| `test_legacy_visit_window_string_fallback` | `visit_window: "MORNING"` (no array) → still resolves |
| `test_no_window_no_time_still_all_day` | Empty windows + no scheduled_time → all-day |
| `test_existing_tests_still_pass` | All Release 6G tests remain green |

### Updated Tests

- `test_r6g_calendar_all_day.py`: Update assertions for new title format (emoji prefix, friendly service name)

---

## 10. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Ryan confused by new event format | Low | Low | Improvement is clearly better; brief heads-up |
| Window-based times don't match actual visit | Low | Low | Description says "Estimated from booking window" |
| Existing calendar events look different from new ones | Medium | Very Low | Cosmetic only; old events remain unchanged |
| Color coding not visible on all calendar views | Low | None | Colors are additive; events still readable without them |
| Overnight events span midnight incorrectly | Low | Low | Explicit handling with end_date or +1 day |

---

## 11. Non-Goals (Deferred)

| Item | Reason |
|------|--------|
| Calendar event editing from web UI | Separate feature |
| Two-way sync (Google → app) | Complex, not needed yet |
| Per-staff calendar support | Currently single shared calendar |
| Recurring visit events | Not supported in booking model yet |
| Push notification for calendar changes | Release 7C scope |

---

## 12. Deployment Impact

- **No Terraform required** — only Python code changes
- **No frontend changes** — backend-only
- **Deploy via:** `terraform apply` (repackages Lambda zip) or manual Lambda update
- **Rollback:** Revert `google_calendar.py` to previous version
- **Validation:** Create a test booking with a visit window, verify calendar event has correct time block and color

---

## 13. AG Implementation Prompt

```
AG — implement Release 7D: Google Calendar Visit Scheduling Hardening.

Backend-only changes in src/backend/common/google_calendar.py.

1. Add constants at module level (inside or above _build_event_body):

   SERVICE_DURATIONS = {
       'WALK_30MIN': 30, 'WALK_60MIN': 60, 'DROPIN_1HR': 60,
       'DROPIN_3HR': 180, 'OVERNIGHT': 720, 'PET_SITTING': 60, 'MEET_GREET': 45,
   }

   WINDOW_START_HOURS = {
       'MORNING': 8, 'MIDDAY': 11, 'AFTERNOON': 14, 'EVENING': 17,
   }

   SERVICE_COLORS = {
       'WALK_30MIN': '9', 'WALK_60MIN': '9', 'DROPIN_1HR': '7',
       'DROPIN_3HR': '7', 'OVERNIGHT': '6', 'PET_SITTING': '10', 'MEET_GREET': '3',
   }

   FRIENDLY_SERVICE_NAMES = {
       'WALK_30MIN': '30-Min Walk', 'WALK_60MIN': '60-Min Walk',
       'DROPIN_1HR': '1-Hour Drop-in', 'DROPIN_3HR': '3-Hour Drop-in',
       'OVERNIGHT': 'Overnight Care', 'PET_SITTING': 'Pet Sitting', 'MEET_GREET': 'Meet & Greet',
   }

2. Update _build_event_body() time resolution:
   - After checking scheduled_time (existing), add window resolution:
   - Extract visit_windows (array) or visit_window (string) from item
   - Find first non-ANYTIME window and map to start hour
   - If resolved: create timed event using window start hour + service duration
   - If not resolved (ANYTIME or empty): fall through to existing all-day logic
   - scheduled_time still takes absolute priority (no change to existing path)

3. Update event title format:
   - New: "🐾 {pet_names} — {friendly_service_name} ({window_label})"
   - window_label = "Morning" / "Midday" / "Afternoon" / "Evening" / "All Day"
   - Keep title under ~60 chars for mobile readability

4. Update event description:
   - Include: Client name, phone, pet names, service type, window, staff, notes, request ID, source
   - Add "Source: Admin Created" for admin_created bookings
   - Add "⏰ Estimated from booking window" note when using window-based time

5. Add colorId to event body:
   - body['colorId'] = SERVICE_COLORS.get(service_type, '8')

6. Preserve all existing safety:
   - All-day fallback still works for ANYTIME / no window
   - scheduled_time still overrides everything
   - Missing fields still return skip reasons
   - Non-blocking behavior unchanged

7. Create tests: tests/backend/test_r7d_calendar_hardening.py
   - Test each window → time mapping
   - Test ANYTIME → all-day
   - Test multi-window uses first
   - Test scheduled_time overrides window
   - Test service durations
   - Test colorId assignment
   - Test new title format
   - Test description content

8. Update existing tests in test_r6g_calendar_all_day.py:
   - Update title assertions to match new emoji format
   - All existing behavior tests must still pass

9. Run: python -m pytest tests/backend/test_r7d_calendar_hardening.py tests/backend/test_r6g_calendar_all_day.py -v
10. Run: python -m py_compile src/backend/common/google_calendar.py

Do not modify frontend code or Terraform.
Do not change any handler files.
Do not deploy.
Return: files changed, test results, summary.
```

---

## 14. Commit Command

```bash
git add src/backend/common/google_calendar.py tests/backend/test_r7d_calendar_hardening.py tests/backend/test_r6g_calendar_all_day.py
git commit -m "feat: Release 7D — Google Calendar visit scheduling hardening with window-based timing and color coding"
```
