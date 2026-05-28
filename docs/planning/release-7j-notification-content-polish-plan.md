# Release 7J: Client & Staff Notification Content Polish — Planning Document

**Status:** PLANNING — No code changes made.  
**Date:** 2026-05-28  
**Scope:** Backend notification template content polish only.  
**Files in scope:** `src/backend/common/notifications/templates.py`, `src/backend/common/notifications/service.py`

---

## Background

Release 7F added the deduplication guard and Phase B multi-day context (the `normalize_context` helper).
Release 7G fixed multi-job cascading assignment with a per-request batch notification guard.
Release 7H polished the Admin UI date display.

The notification templates are functionally correct but have several content clarity and polish opportunities identified below. **No architectural or behavioral changes are in scope.**

---

## Live Notification Events Inventory

| Event Type | Trigger Path | Recipient(s) | Current Subject |
|---|---|---|---|
| `REQUEST_RECEIVED` | `intake_handler.py:469` | Admin | `"New Request: {client_name} — {service_label}"` |
| `CUSTOMER_APPROVED` | `review_handler.py:23,34`, `admin_handler.py:1990` | Client | `"Your Tog & Dogs Request Has Been Approved!"` |
| `VISIT_SCHEDULED` | `review_handler.py:37`, `assignment_handler.py:164` | Client | `"Your {service_label} Visit Is Confirmed — Tog & Dogs"` |
| `STAFF_ASSIGNED` | `review_handler.py:36`, `assignment_handler.py:163` | Staff | `"New Assignment: {service_label} — {client_name}"` |
| `VISIT_CANCELLED` | `cancellation_handler.py:239`, `review_handler.py:39`, `admin_handler.py:1992` | Client + Staff + Admin | `"Visit Cancelled: {service_label} — {client_name}"` |
| `VISIT_TIME_CHANGED` | (stub, not wired to a handler) | Client | `"Visit Time Updated — {service_label} for {pet_names}"` |
| `WELCOME_INVITE_STAFF` | `admin_handler.py:705` | Staff | `"You're invited to the Tog & Dogs Staff Portal"` |
| `WELCOME_INVITE_CLIENT` | `admin_handler.py:497,1277` | Client | `"Your Tog & Dogs Client Portal Account Is Ready"` |

---

## Current Context / Date Rendering

The `normalize_context` method in `templates.py` already handles multi-day date logic:
- `selected_dates` list → detects consecutive/non-consecutive and builds `date_display` (e.g. "Jun 9–13, 2026")
- `start_date` + `end_date` → fallback range format
- `is_multi_visit`, `date_heading` ("Date:" / "Dates:"), `date_text` ("Visit Date" / "Visit Dates") are all set correctly

**Gap identified:** The `service.py` context builder (lines 356–371) does **not** pass `selected_dates` or `end_date` through to the template. This means the Phase B multi-day date logic in `normalize_context` silently falls back to `start_date` only for all booking events triggered via `service.py`. The templates receive the `date_display` computed correctly in `normalize_context` only if the data is available to it.

---

## Issues & Recommended Improvements

### Issue 1: `service.py` context builder drops `selected_dates` and `end_date`
**File:** `service.py` lines 356–371  
**Severity:** Medium — multi-day date formatting in emails still falls back to `start_date` only  
**Fix:** Add `selected_dates` and `end_date` to the context dict built in `notify_event`:
```python
"selected_dates": record.get('selected_dates') or [],
"end_date": record.get('end_date') or '',
```

### Issue 2: `VISIT_CANCELLED` — Generic greeting "Hello,"
**File:** `templates.py` `visit_cancelled` (line 593)  
**Current:** `"Hello,"` (neutral shared-audience tone — per docstring)  
**Recommendation:** Use `client_name` in the greeting since the email goes to client, staff, and admin. The current generic greeting is acceptable for a shared-audience email. However, the subject line says "Visit Cancelled: {service_label} — {client_name}" which is better suited for admin/staff. For the client copy, a subject like `"Your {service_label} Visit Has Been Cancelled"` would feel more personal.

**Proposed approach:** Keep the shared template body but improve the subject line to be audience-context-aware. Since we cannot currently send different subjects to different recipient groups from one template call, a simpler improvement is to soften the subject:
- **Current:** `"Visit Cancelled: {service_label} — {client_name}"`
- **Proposed:** `"Your {service_label} Visit Has Been Cancelled — Tog & Dogs"`

### Issue 3: `VISIT_SCHEDULED` — "a sitter has been assigned" always shown even when sitter name is blank
**File:** `templates.py` `visit_scheduled` (line 410)  
**Current HTML:** `"...has been confirmed and a sitter has been assigned."`  
**Issue:** This sentence is always rendered even when `staff_name` is empty (no sitter yet). The `sitter_row` in the table is correctly conditional, but the paragraph body is not.  
**Fix:** Make the sentence conditional:
```python
# If staff_name is known:
"...has been confirmed and {staff_name} will be your sitter."
# If staff_name is blank:
"...has been confirmed. A sitter will be assigned shortly."
```

### Issue 4: `STAFF_ASSIGNED` — Missing multi-day visit context clarity
**File:** `templates.py` `staff_assigned`  
**Current:** The email says "You've been assigned a new visit." for single and multi-day.  
**Proposed improvement:** When `is_multi_visit` is True, change to:
- `"You've been assigned a new {service_label} booking spanning multiple visits."`  
This makes it clear to the staff member that the booking contains more than one visit day, matching what the admin and client see.

### Issue 5: `VISIT_TIME_CHANGED` — Stub template lacks full HTML branding
**File:** `templates.py` `visit_time_changed` (line 683)  
**Current:** Uses a bare minimal HTML stub (`<h2>Visit Time Updated</h2>`) inconsistent with all other branded templates.  
**Status:** Not currently wired to any handler. Low risk to polish now for future readiness.  
**Proposed:** Upgrade to full branded template matching the style of `visit_scheduled`.

### Issue 6: `REQUEST_RECEIVED` — `contact_line` in plain text includes pipe separator that can look odd
**File:** `templates.py` line 244  
**Current:** `"Email: foo@bar.com | Phone: 555-1234"`  
**Proposed:** Use a newline separator in plain text: `"Email: foo@bar.com\nPhone: 555-1234"` (the HTML version already renders as separate rows and is fine).

### Issue 7: `CUSTOMER_APPROVED` — "What Happens Next" list is generic for multi-day bookings
**File:** `templates.py` `customer_approved` (lines 195–199)  
**Current Step 1:** "A team member will be assigned to your visit shortly."  
**Issue:** For multi-day bookings, "your visit" (singular) is slightly misleading.  
**Proposed:** When `is_multi_visit` is True:
- Step 1: "A team member will be assigned to your visits shortly."
- Step 3: "You can view your booking details anytime in the client portal."

---

## Dedup & Batch Guard Preservation Requirements

> [!IMPORTANT]
> All template-level changes are context/wording only. They do NOT touch:
> - `_is_recent_duplicate()` in `service.py`
> - The 5-minute dedup window logic
> - The `_write_ledger_entry()` paths
> - The `assignment_handler.py` `notification_sent` batch guard flag
> These remain completely unchanged.

---

## Multi-Day Display Requirements Summary

| Scenario | Current Behavior | Target Behavior |
|---|---|---|
| Single date | "Jun 9, 2026" ✅ | No change |
| Consecutive selected_dates | "Jun 9–13, 2026" ✅ (if passed) | Ensure `selected_dates` reaches context |
| Non-consecutive selected_dates | Fallback to `start_date` ⚠️ | Pass `selected_dates` via `service.py` |
| Legacy `start_date`/`end_date` only | Range format ✅ | No change |

---

## Proposed File Changes

### `src/backend/common/notifications/service.py`
#### [MODIFY] Context builder (~line 356–371)
Add `selected_dates` and `end_date` to the context dict.

### `src/backend/common/notifications/templates.py`
#### [MODIFY] `visit_scheduled` (lines 350–455)
- Make the sitter sentence body conditional on `staff_name`.
#### [MODIFY] `staff_assigned` (lines 457–563)
- Add multi-visit context sentence when `is_multi_visit` is True.
#### [MODIFY] `customer_approved` (lines 131–220)
- Pluralize "visit/visits" in "What Happens Next" list when `is_multi_visit` is True.
#### [MODIFY] `visit_cancelled` (lines 565–680)
- Soften the subject to be client-friendly.
#### [MODIFY] `request_received` (lines 222–348)
- Use newline separator instead of pipe in plain-text contact line.
#### [MODIFY] `visit_time_changed` (lines 682–707)
- Upgrade from stub to full branded template.

---

## Test Plan

### New Tests in `tests/backend/test_r7j_notification_content_polish.py`
1. `test_visit_scheduled_with_sitter` — verify sitter sentence includes name when `worker_name` is set.
2. `test_visit_scheduled_without_sitter` — verify sentence says "A sitter will be assigned shortly" when name is empty.
3. `test_staff_assigned_multi_day` — verify "spanning multiple visits" text when `is_multi_visit=True`.
4. `test_staff_assigned_single_day` — verify "a new visit" text unchanged for single-day.
5. `test_customer_approved_multi_day` — verify "visits" pluralization in "What Happens Next".
6. `test_visit_cancelled_subject` — verify softened subject line.
7. `test_request_received_contact_line` — verify newline separator in plain text.
8. `test_selected_dates_reaches_template_context` — verify `selected_dates` and `end_date` pass through `service.py` context builder.
9. `test_dedup_guard_unchanged` — confirm `_is_recent_duplicate` still blocks within 5-minute window.

### Regression Check
- Re-run `tests/backend/test_r7f_notification_dedup.py`
- Re-run `tests/backend/test_r7f_template_multiday.py`
- Re-run `tests/backend/test_r7g_assignment_multiday.py`

### Build Check
- `python -m py_compile src/backend/common/notifications/templates.py src/backend/common/notifications/service.py`

---

## Guardrails

- Do NOT modify Terraform, API clients, DynamoDB schemas, frontend, or deployment scripts.
- Do NOT modify the dedup ledger write paths or dedup logic.
- Do NOT modify the Release 7G batch guard flag in `assignment_handler.py`.
- Do NOT add new notification event types.
- Do NOT change who receives which notification event.
- Test all changes with `py_compile` and the existing test suites before committing.
