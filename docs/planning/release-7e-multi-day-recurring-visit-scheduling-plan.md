# Release 7E: Multi-Day & Recurring Visit Scheduling

**Status:** Planning
**Priority:** Medium (operational improvement, not blocking mobile)
**Risk to Production:** Requires careful phasing — see MVP vs Deferred section
**Terraform Required:** No (for MVP phase)
**Frontend Changes:** Yes (for MVP phase — New Visit modal enhancement)

---

## 1. Objective

Design and plan support for:
- Multi-day visits where the same service/window applies to each day in a date range
- Recurring weekly schedules (e.g., walks every Mon/Wed/Fri for 4 weeks)
- Clear staff assignment, cancellation, and completion tracking per occurrence

This document recommends what to build now (safe MVP) versus what to defer to a future advanced scheduler.

---

## 2. Current System Behavior

### How Bookings Work Today

```
1 REQ record (parent) → 1 JOB record (child)
   └── 1 Google Calendar event
   └── 1 staff assignment
   └── 1 status lifecycle (APPROVED → ASSIGNED → COMPLETED)
```

### Multi-Day Bookings Today

The system already accepts `start_date` + `end_date` on a request:
- Frontend: New Visit modal has both date fields
- Backend: `intake_handler.py` stores both on the REQ record
- JOB handler: Copies `end_date` to the JOB record
- Calendar: Creates a **single** event (either timed on start_date or all-day)
- Display: Request List shows "2026-07-01 to 2026-07-05"

**Problem:** A 5-day booking creates 1 JOB and 1 calendar event. Ryan can't track which days are done, reassign individual days, or mark partial completion.

### Recurring Bookings Today

**Not supported.** If a client wants walks every Monday for a month, Ryan must create 4 separate bookings manually.

---

## 3. Design Options Analyzed

### Option A: Individual JOB Records Per Day (Recommended MVP)

```
1 REQ record (parent)
   ├── JOB#day1 (2026-07-01) → Calendar event 1
   ├── JOB#day2 (2026-07-02) → Calendar event 2
   ├── JOB#day3 (2026-07-03) → Calendar event 3
   └── JOB#day4 (2026-07-04) → Calendar event 4
```

**Pros:**
- Each day has independent status (can complete Mon, cancel Tue, reassign Wed)
- Each day gets its own calendar event with correct time
- Staff assignment can vary per day
- Cancellation of one day doesn't affect others
- Audit trail per occurrence
- Works with existing cascade logic (just multiple JOBs per REQ)
- Request List still shows 1 parent REQ row (no duplication)

**Cons:**
- More DynamoDB records (but trivial at this scale)
- JOB handler needs to create N records instead of 1
- Bulk operations (cancel all, reassign all) need UI support

### Option B: Google Calendar Recurrence Rules (RRULE)

```
1 REQ record → 1 JOB record → 1 recurring Calendar event (RRULE)
```

**Pros:**
- Single calendar event with recurrence (clean calendar view)
- Fewer DynamoDB records

**Cons:**
- Cannot track per-day completion/cancellation without breaking recurrence
- Cannot assign different staff to different days
- Modifying one occurrence in Google Calendar creates "exceptions" that are hard to sync
- Cancelling one day requires EXDATE manipulation
- No per-occurrence audit trail in DynamoDB
- Google Calendar API recurrence handling is complex and error-prone

### Option C: Schedule Template + Occurrence Generation (Future Advanced)

```
1 SCHEDULE record (template: Mon/Wed/Fri, 4 weeks, MORNING walk)
   └── Generates N REQ records on creation or rolling basis
       └── Each REQ → JOB → Calendar event
```

**Pros:**
- Cleanest long-term model for recurring clients
- Supports complex patterns (every other week, specific days, seasonal)
- Can auto-generate future occurrences

**Cons:**
- Significant new data model (SCHEDULE entity type)
- Requires schedule builder UI
- Overkill for current scale (< 20 active clients)
- Can be built later on top of Option A

### Recommendation: Option A (MVP) now, Option C (Advanced) later

Option A gives Ryan immediate value with minimal risk. Option C can be layered on top when the business grows.

---

## 4. MVP Design: Individual JOB Records Per Day

### 4.1 When Multi-Day JOBs Are Created

**Trigger:** When a REQ record is approved and has `start_date` + `end_date` spanning multiple days.

**Logic in `job_handler.py`:**

```python
from datetime import datetime, timedelta

start = datetime.strptime(start_date, '%Y-%m-%d')
end = datetime.strptime(end_date, '%Y-%m-%d')
day_count = (end - start).days + 1  # Inclusive

if day_count > 1:
    # Create one JOB per day
    for i in range(day_count):
        occurrence_date = (start + timedelta(days=i)).strftime('%Y-%m-%d')
        create_job(request_item, occurrence_date, occurrence_index=i+1, total_occurrences=day_count)
else:
    # Single day — existing behavior
    create_job(request_item, start_date)
```

### 4.2 JOB Record Schema for Occurrences

```
PK: JOB#<job_uuid>
SK: REQ#<request_id>

Additional fields for multi-day:
  occurrence_date:    "2026-07-02"          (the specific day this JOB covers)
  occurrence_index:   2                     (1-based: day 2 of 5)
  total_occurrences:  5                     (total days in the range)
  parent_request_id:  "req-abc"             (same as request_id, for clarity)
  is_multi_day:       true                  (flag for UI/query filtering)
```

### 4.3 Google Calendar: One Event Per JOB

Each JOB creates its own calendar event using the `occurrence_date` as the scheduled date. This means:
- 5-day booking → 5 calendar events (each on the correct day with correct time window)
- Each event has its own `google_event_id` stored on the JOB record
- Cancelling one day deletes only that day's calendar event

### 4.4 Staff Assignment

**Default:** All JOBs in a multi-day set inherit the same `preferred_sitter` from the REQ.

**Override:** Admin can reassign individual JOBs to different staff via the existing assignment flow. Each JOB is independently assignable.

### 4.5 Status Lifecycle Per Occurrence

Each JOB has its own independent status:
```
JOB#day1: ASSIGNED → COMPLETED
JOB#day2: ASSIGNED → CANCELLED (rain day)
JOB#day3: ASSIGNED → COMPLETED
JOB#day4: ASSIGNED → IN_PROGRESS
JOB#day5: JOB_CREATED (not yet assigned)
```

### 4.6 Parent REQ Status

The parent REQ record's status reflects the **aggregate** state:
- All JOBs completed → REQ = COMPLETED
- Any JOB still active → REQ = ASSIGNED (or IN_PROGRESS)
- All JOBs cancelled → REQ = CANCELLED
- Mix of completed + cancelled → REQ = COMPLETED (partial completion is still completion)

**Implementation:** After any JOB status change, check sibling JOBs and update parent REQ if all are terminal.

### 4.7 Cascade Behavior

**REQ → JOB cascade (existing):**
- If admin cancels the entire REQ → all linked JOBs cascade to CANCELLED
- If admin archives the REQ → all linked JOBs cascade to ARCHIVED

**JOB → REQ rollup (new):**
- When the last active JOB in a set reaches a terminal state → update parent REQ
- This is a new "rollup" direction (JOB → REQ), but it's safe because it only fires on terminal states

### 4.8 Request List Display

**No change to the Request List.** It already shows only parent REQ rows (JOB# records are filtered out by `isRequestLikeRecord()`). The REQ row shows the date range and aggregate status.

**CareCard / Detail View:** When an admin clicks a multi-day REQ, show the individual JOB occurrences with their per-day status. This is a future UI enhancement (not MVP).

---

## 5. Recurring Weekly Schedules (Deferred — Not MVP)

### Why Defer

- Requires a schedule builder UI (day-of-week picker, week count, exceptions)
- Requires a new SCHEDULE entity type or a "generate occurrences" flow
- Current volume doesn't justify the complexity
- Can be built on top of the multi-day MVP (generate N individual REQs from a template)

### Future Design Sketch

```
Admin creates a "Recurring Schedule":
  Client: Jane Smith
  Pet: Buddy
  Service: WALK_30MIN
  Days: Mon, Wed, Fri
  Window: MORNING
  Duration: 4 weeks (starting 2026-07-01)
  Staff: Ryan (default)

System generates:
  REQ#1 (2026-07-01, Mon) → JOB → Calendar
  REQ#2 (2026-07-03, Wed) → JOB → Calendar
  REQ#3 (2026-07-05, Fri) → JOB → Calendar
  ... (12 total)
```

Each generated REQ is independent — can be cancelled, reassigned, or completed individually. The schedule template is metadata only (not a live entity that controls the REQs after generation).

### Workaround for Now

Ryan can create recurring visits manually using the "+ New Visit" modal, one per day. With the multi-day MVP, he can at least create a date range and get individual JOBs per day automatically.

---

## 6. Different Times on Different Days

### Question: Should a single request support Mon=Morning, Wed=Afternoon?

**Answer: No (not in MVP).** A single REQ has one `visit_windows` array that applies uniformly to all days in the range.

**If different times are needed on different days:**
- Create separate requests (one per unique time pattern)
- Or wait for the future schedule builder which can specify per-day windows

**Rationale:**
- Keeps the data model simple (one window set per REQ)
- Avoids complex per-day override schemas
- Matches how Ryan currently thinks about bookings ("Buddy needs morning walks all week")

---

## 7. Safety Limits

### Maximum Days Per Request

To prevent accidental creation of hundreds of JOBs:

```python
MAX_MULTI_DAY_OCCURRENCES = 14  # 2 weeks max per single request
```

If `day_count > 14`:
- Return an error: "Date range exceeds 14 days. For longer schedules, create multiple requests."
- This protects against typos (e.g., end_date = 2027 instead of 2026)

### Calendar Event Limit

Google Calendar API has rate limits. Creating 14 events sequentially is fine, but add a small delay between calls if needed:

```python
import time
for job in jobs_to_create:
    sync_calendar_event(job)
    time.sleep(0.1)  # 100ms between calls
```

---

## 8. What to Build Now (MVP) vs Defer

### MVP (Release 7E Phase 1) — Safe to Implement

| Item | Description | Risk |
|------|-------------|------|
| Multi-day JOB expansion | `job_handler.py` creates N JOBs for date ranges | Low |
| Per-day calendar events | Each JOB gets its own calendar event | Low |
| 14-day safety limit | Reject ranges > 14 days | None |
| Parent REQ rollup | Update REQ status when all JOBs are terminal | Low |
| Bulk cancel cascade | Cancelling REQ cancels all child JOBs | Already works |
| Tests | Unit tests for multi-day expansion, rollup, limits | None |

### Deferred (Future Releases)

| Item | Reason | When |
|------|--------|------|
| Recurring schedule builder UI | Complex, not needed at current scale | After mobile launch |
| Per-day time overrides | Adds schema complexity | After recurring schedules |
| CareCard multi-day detail view | UI enhancement, not blocking | After MVP validation |
| Bulk reassign all days | UI convenience, not blocking | After MVP validation |
| Schedule template entity | New data model, overkill now | After 50+ active clients |
| Auto-generation of future weeks | Requires scheduler/cron | After recurring schedules |

---

## 9. Risks to Ryan's Live Testing

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Existing single-day bookings break | Very Low | High | Multi-day logic only fires when `end_date` is present AND different from `start_date` |
| Too many JOBs created accidentally | Low | Medium | 14-day safety limit + validation |
| Calendar rate limiting | Very Low | Low | 100ms delay between event creations |
| Parent REQ status gets stuck | Low | Low | Rollup only fires on terminal states; manual override always available |
| Request List shows duplicate rows | None | — | JOB# records already filtered out by `isRequestLikeRecord()` |
| Cascade breaks for multi-JOB sets | Low | Medium | Test cascade with 5+ JOBs; existing cascade is per-JOB already |

### Key Safety Guarantee

**Single-day bookings (no `end_date` or `end_date == start_date`) are completely unchanged.** The multi-day expansion only activates when a genuine date range exists.

---

## 10. Implementation Phases

### Phase 1: Multi-Day JOB Expansion (~1 day)

- Modify `job_handler.py` to detect date ranges and create N JOBs
- Add `occurrence_date`, `occurrence_index`, `total_occurrences`, `is_multi_day` fields
- Add 14-day safety limit
- Each JOB gets its own calendar event via `sync_calendar_event()`
- Write tests for: 1-day (unchanged), 3-day, 14-day, 15-day (rejected), missing end_date

### Phase 2: Parent REQ Rollup (~0.5 day)

- After any JOB status change to terminal state, check all sibling JOBs
- If all terminal → update parent REQ to COMPLETED (or CANCELLED if all cancelled)
- Add rollup logic to `cascade.py` or a new `rollup.py` module
- Write tests for: partial completion, full completion, full cancellation, mixed states

### Phase 3: Calendar Sync for Multi-Day (~0.5 day)

- Ensure each JOB's calendar event uses `occurrence_date` (not parent `start_date`)
- Ensure cancelling one JOB deletes only that day's calendar event
- Ensure reassigning one JOB updates only that day's calendar event
- Write tests for: per-day calendar creation, per-day deletion, per-day update

### Phase 4: Validation & Docs (~0.5 day)

- Production smoke test: create a 3-day booking, verify 3 calendar events
- Verify Request List still shows 1 row
- Verify cancel-all cascades correctly
- Update operational docs

---

## 11. Files Changed (MVP)

| File | Change |
|------|--------|
| `src/backend/handlers/job_handler.py` | Multi-day expansion logic |
| `src/backend/common/cascade.py` | Add rollup function (JOB terminal → check parent REQ) |
| `tests/backend/test_r7e_multi_day_jobs.py` | New test file |
| `docs/datamodel.md` | Document new JOB fields |

### Files NOT Changed

- No frontend changes for MVP (Request List already handles this correctly)
- No Terraform changes
- No notification changes
- No `google_calendar.py` changes (already handles per-item sync correctly)

---

## 12. AG Implementation Prompt (Phase 1)

```
AG — implement Release 7E Phase 1: Multi-Day JOB Expansion.

Backend-only changes in src/backend/handlers/job_handler.py.

1. After fetching the request_item, detect multi-day range:
   - Extract start_date and end_date from request_item
   - If end_date exists and end_date > start_date:
     - Calculate day_count = (end - start).days + 1
     - If day_count > 14: return {"error": "Date range exceeds 14 days maximum."}
     - Create one JOB record per day in the range
   - If single day or no end_date: existing behavior (1 JOB)

2. For each JOB in a multi-day set, add fields:
   - occurrence_date: the specific date for this JOB (YYYY-MM-DD)
   - occurrence_index: 1-based index (day 1, day 2, etc.)
   - total_occurrences: total days in the range
   - is_multi_day: true
   - scheduled_date: same as occurrence_date (for calendar sync)

3. For single-day JOBs (existing behavior):
   - Do NOT add is_multi_day or occurrence fields
   - Behavior is completely unchanged

4. Calendar sync for multi-day:
   - Each JOB calls sync_calendar_event() with its own occurrence_date as start_date
   - Each JOB stores its own google_event_id
   - Add 100ms sleep between calendar API calls to avoid rate limiting

5. Link all JOB IDs back to parent REQ:
   - Update REQ record with job_ids array (list of all created job_ids)
   - Keep existing job_id field pointing to the first JOB for backward compat

6. Write tests: tests/backend/test_r7e_multi_day_jobs.py
   - test_single_day_unchanged (no end_date → 1 JOB, no multi-day fields)
   - test_single_day_same_dates (start_date == end_date → 1 JOB)
   - test_three_day_range (3 JOBs created with correct occurrence fields)
   - test_fourteen_day_max (14 days → 14 JOBs, no error)
   - test_fifteen_day_rejected (15 days → error returned)
   - test_occurrence_dates_correct (each JOB has correct date)
   - test_calendar_sync_per_day (each JOB triggers sync_calendar_event)
   - test_job_ids_linked_to_req (REQ updated with job_ids array)

7. Run: python -m pytest tests/backend/test_r7e_multi_day_jobs.py -v
8. Run: python -m py_compile src/backend/handlers/job_handler.py

Do not modify frontend code or Terraform.
Do not modify google_calendar.py (it already handles per-item sync).
Do not deploy.
Return: files changed, test results, summary.
```

---

## 13. Commit Command

```bash
git add docs/planning/release-7e-multi-day-recurring-visit-scheduling-plan.md
git commit -m "docs: Release 7E multi-day and recurring visit scheduling plan"
```
