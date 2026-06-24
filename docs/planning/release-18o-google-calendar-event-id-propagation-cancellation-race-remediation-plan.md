# Release 18O: Google Calendar Event ID Propagation and Cancellation Cascade Race Condition Remediation Plan

**Status:** Planning
**Date:** 2026-06-23
**Priority:** Medium-High (orphaned calendar events degrade operational quality)
**Scope:** Design defensive fix for calendar event cleanup during booking cancellation

---

## 1. Observed Defect

### Where Discovered

Release 18N — Phase 2 Entitlement Controlled Validation Execution

### Symptom

- Admin created a normal (non-test) booking via admin offline flow
- Google Calendar event was created successfully (calendar is connected)
- Booking was later cancelled through normal admin cancellation
- The exempt (test) booking's calendar event was correctly deleted on cancellation
- The normal booking's calendar event was NOT automatically deleted
- Manual deletion of the orphaned Google Calendar event was required

### User Impact If Unresolved

- Orphaned calendar events remain on the sitter's Google Calendar after cancellations
- Ryan/staff see cancelled visits still showing on their calendar
- Requires manual Calendar cleanup by Matthew or Ryan
- Scales poorly with more bookings/tenants

---

## 2. Likely Technical Root Cause

### Flow Diagram (Problem Path)

```
1. Admin creates offline booking
     → intake_handler creates REQ# record
     → Step Function triggers job_handler
     → Calendar sync attempts event creation (async within review/approval path)

2. Job Lambda creates child JOB# records
     → At this point, REQ# may not yet have google_event_id
     → Child JOB# records inherit fields from parent BUT may miss google_event_id

3. Later: cancellation triggered
     → cancellation_handler looks for google_event_id on child JOB# record(s)
     → google_event_id is MISSING on child JOB (race: was set on parent after job creation)
     → Cancellation skips calendar event deletion
     → Event remains orphaned in Google Calendar
```

### Root Cause: Async Timing

- Calendar event creation and Job record creation happen concurrently or in indeterminate order
- The `google_event_id` is written to the parent REQ# record AFTER the calendar API responds
- Child JOB# records may be created BEFORE the parent has the event ID
- Cancellation cascade reads event ID from child records but parent's event ID is not checked as fallback

---

## 3. Remediation Options

| Option | Description | Safety | Effort | Recommendation |
|--------|-------------|--------|--------|----------------|
| **A** | Cancellation fallback: check parent REQ# for event ID if child JOB# lacks it | ✅ | Low | ✅ **MVP recommended** |
| **B** | After calendar sync, propagate event ID to all existing child JOBs | ✅ | Medium | ⚠️ Good but more complex |
| **C** | Make job creation wait/re-read parent after calendar sync | ⚠️ Adds latency | Medium | ❌ Coupling concerns |
| **D** | Cancellation collects ALL event IDs from parent + children, dedup, delete all | ✅ | Low-Medium | ✅ **Best defensive approach** |
| **E** | Combination: A + B (fallback now + propagation for future consistency) | ✅ | Medium | ⏳ Future enhancement |

### Recommended MVP Fix: Option D (Defensive Collection)

```python
# In cancellation_handler (or cascade logic):
def collect_calendar_event_ids(request_record, child_jobs):
    """Collect all google_event_ids from parent and children, deduplicated."""
    event_ids = set()
    
    # Check parent request
    parent_id = request_record.get('google_event_id')
    if parent_id:
        event_ids.add(parent_id)
    
    # Check all child jobs
    for job in child_jobs:
        job_id = job.get('google_event_id')
        if job_id:
            event_ids.add(job_id)
    
    return event_ids

def cancel_calendar_events(event_ids):
    """Attempt to delete/cancel each event. Tolerate missing/already-deleted."""
    for event_id in event_ids:
        try:
            delete_google_calendar_event(event_id)
        except EventNotFound:
            pass  # Already deleted or never existed — safe to ignore
        except Exception as e:
            print(f"CALENDAR_CLEANUP_WARNING: Failed to delete event {event_id}: {e}")
            # Non-blocking — cancellation still proceeds
```

### Why Option D Is Safest

- Handles ALL timing scenarios (event on parent, on child, on both, on neither)
- Deduplication prevents double-delete attempts
- Tolerates already-deleted events
- Non-blocking — cancellation always completes regardless of calendar outcome
- No changes to the creation/approval path (only cancellation logic)

---

## 4. Test Strategy for AG

### Unit Tests

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | Parent has event ID, child missing → event deleted | Parent: `evt_123`, child: None | `delete_google_calendar_event('evt_123')` called |
| 2 | Child has event ID, parent missing → event deleted | Parent: None, child: `evt_456` | `delete_google_calendar_event('evt_456')` called |
| 3 | Both have same ID → deleted once | Parent: `evt_789`, child: `evt_789` | Called once (deduplicated) |
| 4 | Parent and child have different IDs → both deleted | Parent: `evt_A`, child: `evt_B` | Both called |
| 5 | Neither has event ID → no deletion attempted | Both None | No calendar API calls |
| 6 | Event already deleted → tolerated | API raises NotFound | Cancellation completes, no error |
| 7 | Calendar API error → tolerated (non-blocking) | API raises generic error | Warning logged, cancellation completes |
| 8 | Multi-day: multiple child JOBs with different event IDs | 3 children with 3 IDs | All 3 attempted |

### Regression Tests

| # | Test | Expected |
|---|------|----------|
| 9 | Existing cancellation transitions request to CANCELLED | Status updated correctly |
| 10 | Existing cascade deletes child JOBs/updates status | Normal cascade behavior preserved |
| 11 | No notification sent if no client email | Zero notification calls |
| 12 | Single-day booking cancellation still works | Event deleted from parent or child |

---

## 5. Production Validation Strategy

### Primary Validation: Unit/Integration Tests

The fix should be validated primarily through mocked tests (no production bookings needed). The race condition is a timing issue that tests can simulate by controlling which records have `google_event_id` set.

### Optional Production Validation (If Matthew Approves Later)

If a production smoke is desired after deployment:
- Create one internal test booking (same pattern as 18N)
- Verify calendar event created
- Cancel booking
- Verify calendar event deleted
- This is OPTIONAL and requires separate approval

### No Production Validation During 18P Implementation

The fix is defensive (adds fallback checks) — it cannot make things worse. If the parent has the event ID and the child doesn't, the fix finds it. If both have it, dedup handles it. Safe to deploy without production booking test.

---

## 6. Observability / Runbook Updates

### New Structured Log Lines

```
CALENDAR_CLEANUP_COLLECTED: request_id=<id>, event_ids_found=2
CALENDAR_CLEANUP_DELETED: event_id=<id>
CALENDAR_CLEANUP_ALREADY_GONE: event_id=<id>
CALENDAR_CLEANUP_WARNING: event_id=<id>, error=<msg>
CALENDAR_CLEANUP_NONE: request_id=<id>, no event IDs found
```

### How to Detect Orphaned Events (Future)

Currently no automated orphan detection exists. If needed later:
- Scan DynamoDB for cancelled requests with `google_event_id` set
- Cross-reference with Google Calendar API (if accessible)
- Delete orphaned events in batch

### Monitoring Checklist Update

Add to Matthew's monitoring checklist:
- After any cancellation, spot-check Google Calendar to confirm event was removed
- If orphaned events accumulate, escalate to AG for bulk cleanup

---

## 7. Recommended Release Sequence

| Release | Scope | Owner |
|---------|-------|-------|
| **18O** | Remediation plan (this document) | ✅ Kiro (done) |
| **18P** | Calendar cancellation cascade defensive fix + tests | AG |
| **18Q** | Optional controlled production validation (if Matthew approves) | AG + Matthew |
| **18R** | Strict-mode final gate review (June 30 target) | Kiro + Matthew |

---

## 8. What This Document Does NOT Authorize

- ❌ Code changes
- ❌ Modifying cancellation handlers
- ❌ Creating/deleting calendar events
- ❌ Creating bookings/clients/jobs
- ❌ DynamoDB writes
- ❌ Lambda/frontend/mobile deployment
- ❌ Terraform/AWS changes
- ❌ Cognito changes
- ❌ Enabling strict mode
- ❌ Creating second tenant
- ❌ Stripe/Postmark/payment changes
- ❌ Ryan/tester changes

This is a planning document. Implementation (18P) requires separate approval.
