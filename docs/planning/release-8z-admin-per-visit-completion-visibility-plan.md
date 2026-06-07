# Release 8Z: Admin Web Per-Visit Completion Visibility

**Status:** Planning
**Priority:** Medium-High (Ryan needs to see which days are done)
**Risk to Production:** Low (backend enrichment + frontend display)
**Terraform Required:** No (adds route handling within existing Lambda)
**Backend Changes:** Yes — add child-job summary to parent REQ response
**Scope:** Backend response enrichment + web admin display

---

## 1. Purpose

Give Ryan visibility into which individual days of a multi-day booking are completed vs still pending, who completed them, and what visit notes were recorded — all from the admin web dashboard.

---

## 2. Current Data Availability

### What the Admin Request List Returns

`GET /admin/requests?status=ALL` returns **only parent REQ# records**. Child JOB# records are explicitly filtered out:

```python
filter_expressions.append("contains(PK, :req_tag)")
expression_values[":req_tag"] = "REQ#"
```

### What the Parent REQ# Record Contains

| Field | Available? | Contains Per-Day Status? |
|-------|-----------|-------------------------|
| `job_ids` | ✅ Array of JOB UUIDs | ❌ No — just IDs |
| `is_multi_day` | ✅ Boolean | — |
| `total_occurrences` | ✅ Number | — |
| `selected_dates` | ✅ Array of date strings | ❌ No status per date |
| `status` | ✅ Parent aggregate status | Only one value for whole booking |
| `visit_notes` | ✅ From 8V (parent-level) | Only one note for whole booking |

### What Child JOB# Records Contain (After 8Y)

| Field | Available? |
|-------|-----------|
| `status` | ✅ (ASSIGNED, COMPLETED, CANCELLED) |
| `occurrence_date` | ✅ |
| `occurrence_index` | ✅ |
| `visit_notes` | ✅ (per-day, from 8Y) |
| `completed_at` | ✅ |
| `completed_by` | ✅ |
| `worker_id` / `worker_name` | ✅ |

### Gap: No Way to See Per-Day Status from the Web

The web admin has **no access to child JOB completion data** — it only sees the parent REQ status. A 3-day booking where 2 days are done still shows as "ASSIGNED" with no indication of progress.

---

## 3. Backend Options

### Option A: Enrich Parent REQ Response with Child Job Summaries (Recommended)

When returning a parent REQ record that has `job_ids`, inline a summary of child job statuses:

```json
{
  "request_id": "req-123",
  "status": "ASSIGNED",
  "is_multi_day": true,
  "job_ids": ["job-1", "job-2", "job-3"],
  "selected_dates": ["2026-06-10", "2026-06-11", "2026-06-12"],
  "job_completion_summary": {
    "total": 3,
    "completed": 2,
    "pending": 1,
    "jobs": [
      { "job_id": "job-1", "date": "2026-06-10", "status": "COMPLETED", "completed_at": "2026-06-10T18:30:00", "completed_by": "staff@example.com", "visit_notes": "Fed Buddy, 30 min walk" },
      { "job_id": "job-2", "date": "2026-06-11", "status": "COMPLETED", "completed_at": "2026-06-11T17:45:00", "completed_by": "staff@example.com", "visit_notes": "Walk done, gate latched" },
      { "job_id": "job-3", "date": "2026-06-12", "status": "ASSIGNED", "completed_at": null, "completed_by": null, "visit_notes": null }
    ]
  }
}
```

**Pros:**
- Single response — no additional API calls from the web frontend
- Summary counts (`2/3 completed`) available for the list row badge
- Full per-day detail available for the expanded/detail view
- No new endpoint or route needed

**Cons:**
- Adds DynamoDB queries to the list response (N queries per multi-day booking)
- Should ONLY enrich on detail fetch, not bulk list fetch (performance)

### Option B: New Admin Endpoint to Get Jobs by Request

`GET /admin/requests/{requestId}/jobs`

**Pros:** Clean separation, lazy-loaded only when detail is opened
**Cons:** New API route, Terraform change, extra request from frontend

### Option C: Client-Side Query (Not Possible)

JOB# records are not returned by any existing endpoint accessible from the web frontend.

### Recommendation: Hybrid of A + B

- **For the list row badge** ("2/3 completed"): Use `job_ids.length` as total and add a `completed_count` field to the parent REQ during the job-complete endpoint's auto-rollup logic (8Y already touches the parent — add `completed_count` there)
- **For the detail view** (per-day breakdown): Add a lightweight query in the admin handler when a single request is fetched (`GET /admin/requests?requestId=X&clientId=Y`) — enrich with child job statuses

This avoids expensive enrichment on bulk list fetches while giving full detail when needed.

---

## 4. Implementation Plan

### Phase 1: Backend — Add `completed_count` on Parent During Job Completion

**In the 8Y `POST /admin/job/complete` handler (already deployed):**

After updating the JOB to COMPLETED, also update the parent REQ with an incremented `completed_count`:

```python
# After successful JOB completion:
table.update_item(
    Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
    UpdateExpression="SET completed_count = if_not_exists(completed_count, :zero) + :one, updated_at = :now",
    ExpressionAttributeValues={":zero": 0, ":one": 1, ":now": now}
)
```

This gives the list view a quick `completed_count / total_occurrences` summary without fetching child JOBs.

### Phase 2: Backend — Enrich Single-Request Detail with Child Jobs

**In the admin handler's single-request GET path** (when `requestId` and `clientId` are provided):

```python
if request_id and client_id:
    item = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")
    if item and item.get('job_ids'):
        # Enrich with child job summaries
        job_summaries = []
        for jid in item['job_ids']:
            job = get_item(f"JOB#{jid}", f"REQ#{request_id}")
            if job:
                job_summaries.append({
                    "job_id": jid,
                    "date": job.get('occurrence_date') or job.get('start_date'),
                    "status": job.get('status'),
                    "completed_at": job.get('completed_at'),
                    "completed_by": job.get('completed_by'),
                    "visit_notes": job.get('visit_notes'),
                    "worker_name": job.get('worker_name')
                })
        item['job_completion_summary'] = {
            "total": len(item['job_ids']),
            "completed": sum(1 for j in job_summaries if j['status'] == 'COMPLETED'),
            "pending": sum(1 for j in job_summaries if j['status'] != 'COMPLETED'),
            "jobs": sorted(job_summaries, key=lambda j: j.get('date') or '')
        }
    return success(item, event)
```

This runs ONLY for single-request fetches (CareCard detail view), not bulk list queries.

### Phase 3: Web Frontend — List Row Badge

In the Request List table row, show a completion progress indicator for multi-day bookings:

```jsx
{item.is_multi_day && item.total_occurrences > 1 && (
  <span className="badge-completion">
    {item.completed_count || 0}/{item.total_occurrences} visits done
  </span>
)}
```

### Phase 4: Web Frontend — CareCard Per-Day Breakdown

When the CareCard/detail view opens for a multi-day booking with `job_completion_summary`:

```
── Visit Schedule (2/3 completed) ─────────

✅ Jun 10, 2026 — Completed
   By: Test Staff • 6:30 PM
   Notes: "Fed Buddy, 30 min walk"

✅ Jun 11, 2026 — Completed
   By: Test Staff • 5:45 PM
   Notes: "Walk done, gate latched"

⏳ Jun 12, 2026 — Pending
   Assigned to: Test Staff
```

---

## 5. Visit Notes Display Model

### Per-Day Notes (from 8Y — on JOB records)

Displayed in the per-day breakdown section, attached to each individual date.

### Parent-Level Notes (from 8V — on REQ record)

Displayed in a separate "Booking Notes" section above or below the per-day breakdown. This covers single-day completions and any legacy notes.

### Display Priority

```
If multi-day AND job_completion_summary exists:
  → Show per-day breakdown with individual notes
  → Show parent visit_notes (if any) as "Overall Booking Notes" separately

If single-day OR no job_completion_summary:
  → Show parent visit_notes (existing 8V behavior)
```

---

## 6. Excel Export Considerations

### Current Export

The "Staff Assignments" sheet already exports JOB records from `data.jobs`. It includes `status`, `start_date`, `worker_name`.

### Recommended Addition

Add `completed_at`, `completed_by`, and `visit_notes` to the "Staff Assignments" export columns:

```javascript
{
  "Job ID": j.job_id || j.PK,
  "Request ID": j.request_id,
  "Status": j.status,
  "Date": j.occurrence_date || j.start_date,
  "Worker": j.worker_name || j.worker_id,
  "Completed At": j.completed_at || '',
  "Completed By": j.completed_by || '',
  "Visit Notes": j.visit_notes || ''
}
```

This does NOT explode parent bookings into multiple rows in the "All Requests" sheet — JOB-level detail only appears in the "Staff Assignments" sheet.

---

## 7. Visibility Guardrails

| Role | Can See Per-Day Notes? | Can See Completion Details? |
|------|------------------------|---------------------------|
| Admin/Owner | ✅ All visits, all notes | ✅ Full per-day breakdown |
| Staff | ✅ Own assigned visits only | ✅ Own completed visits |
| Client | ❌ Not exposed | ❌ Not exposed |

The backend `sanitize_booking_for_role(item, role)` already redacts sensitive fields for non-admin roles. The `job_completion_summary` is safe to include because it only contains operational data (status, date, notes) — no pricing or internal admin notes.

---

## 8. Backward Compatibility

| Scenario | Behavior |
|----------|----------|
| Existing completed parent REQs (pre-8Y) | No `job_completion_summary` → display as before |
| Existing parent-level `visit_notes` (8V) | Still shown in "Booking Notes" section |
| Single-day bookings | No `job_ids` array or `is_multi_day` → standard display |
| Old bookings without `completed_count` | Show "—" or "0/N" in list badge |

No destructive migration. All changes are additive.

---

## 9. Files to Create/Modify

| File | Change | New? |
|------|--------|------|
| `src/backend/handlers/admin_handler.py` | Enrich single-request GET with child job summaries; handle `completed_count` increment | Modified |
| `web/src/components/AdminDashboard.jsx` | Add completion badge on list rows for multi-day | Modified |
| `web/src/components/CareCard.jsx` | Add per-day breakdown section when `job_completion_summary` exists | Modified |
| `tests/backend/test_r8z_admin_per_visit_visibility.py` | Test enrichment logic, completed_count, summary shape | ✅ New |

### Files NOT Changed

- No Terraform (uses existing admin Lambda + routes)
- No mobile app changes
- No notification logic
- No Google Calendar logic
- No DynamoDB schema (additive fields only)

---

## 10. Deployment Requirements

| Layer | Needed? | Action |
|-------|---------|--------|
| Backend Lambda | ✅ Yes | `terraform apply` (repackages Lambda zip with enrichment logic) |
| Web Frontend | ✅ Yes | `aws s3 sync` + CloudFront invalidation |
| Mobile / EAS | ❌ No | Mobile already handles per-day completion (8Y) |
| Terraform resources | ❌ No | No new routes or infrastructure |

---

## 11. Acceptance Criteria

- [ ] Multi-day booking rows in Request List show "X/N visits done" badge
- [ ] CareCard detail for multi-day booking shows per-day breakdown
- [ ] Each completed day shows: date, completed_by, completed_at, visit_notes
- [ ] Pending days show as "Pending" with assigned worker
- [ ] Single-day bookings display unchanged (no regression)
- [ ] Parent-level `visit_notes` (8V) still displayed separately
- [ ] Legacy bookings without child job data display normally
- [ ] Export includes completed_at/completed_by/visit_notes columns in Staff Assignments
- [ ] `npm run build` passes
- [ ] Backend tests pass
- [ ] No Terraform resource changes needed

---

## 12. Validation Checklist

| # | Test | Expected |
|---|------|----------|
| 1 | Create 3-day booking, complete 2 days via mobile | Parent shows "2/3 visits done" badge |
| 2 | Open CareCard for partially-completed multi-day | Per-day breakdown shows 2 completed, 1 pending |
| 3 | Each completed day shows notes + timestamp + staff | Correct data |
| 4 | Complete final day | Badge updates to "3/3", parent auto-completes |
| 5 | Single-day booking | No "X/N" badge, standard display |
| 6 | Legacy booking (no job_ids) | Standard display, no crash |
| 7 | Export includes per-day completion columns | Staff Assignments sheet has new columns |
| 8 | Staff-role web login (if applicable) | Can see own visit notes only |

---

## 13. Rollback

- **Backend:** Revert enrichment logic; responses return to pre-8Z shape (no `job_completion_summary`)
- **Frontend:** Revert badge + breakdown display; CareCard returns to parent-only view
- **Data:** `completed_count` on parent REQ is harmless if not displayed
- **No Terraform rollback needed**

---

## 14. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 8Z: Admin Web Per-Visit Completion Visibility.

Backend + web frontend changes. No Terraform resource changes. No mobile changes.

=== PHASE 1: Backend Enrichment ===

1. In src/backend/handlers/admin_handler.py, in the single-request GET path
   (where `request_id and client_id` resolves to a single item):

   After getting the item, if it has job_ids:
   - Query each child JOB record
   - Build job_completion_summary: { total, completed, pending, jobs: [...] }
   - Attach to the response item
   - Each job entry: { job_id, date, status, completed_at, completed_by, visit_notes, worker_name }
   - Sort jobs by date

2. In the 8Y job-complete handler (POST /admin/job/complete), after updating
   the JOB to COMPLETED, also increment parent REQ's completed_count:
   
   table.update_item(
     Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
     UpdateExpression="SET completed_count = if_not_exists(completed_count, :zero) + :one, updated_at = :now",
     ExpressionAttributeValues={":zero": 0, ":one": 1, ":now": now}
   )

=== PHASE 2: Web Frontend — List Badge ===

3. In web/src/components/AdminDashboard.jsx, in the request list table row
   (Dates/Window column), add after the Multi-Day badge:

   {item.is_multi_day && item.total_occurrences > 1 && (
     <span style={{ fontSize: '0.65rem', fontWeight: 700,
       background: (item.completed_count || 0) >= item.total_occurrences ? '#ecfdf5' : '#eff6ff',
       color: (item.completed_count || 0) >= item.total_occurrences ? '#065f46' : '#1e40af',
       padding: '1px 6px', borderRadius: '4px', marginTop: '2px', display: 'inline-block' }}>
       {item.completed_count || 0}/{item.total_occurrences} visits done
     </span>
   )}

=== PHASE 3: Web Frontend — CareCard Per-Day Breakdown ===

4. In web/src/components/CareCard.jsx (or wherever request detail renders),
   when the item has job_completion_summary:

   Show a "Visit Schedule" section with:
   - Header: "Visit Schedule ({completed}/{total} completed)"
   - For each job in jobs array:
     - ✅ icon + date if COMPLETED; ⏳ icon + date if pending
     - Completed: "By: {completed_by} • {formatted completed_at}"
     - Notes: "{visit_notes}" if present
     - Pending: "Assigned to: {worker_name}"

=== PHASE 4: Export Enhancement ===

5. In the export mapping (AdminDashboard.jsx, "Staff Assignments" sheet),
   add columns: "Completed At", "Completed By", "Visit Notes"

=== PHASE 5: Tests ===

6. Create tests/backend/test_r8z_admin_per_visit_visibility.py:
   - test_single_request_enriched_with_job_summary
   - test_single_request_no_jobs_no_summary
   - test_completed_count_incremented_on_job_complete
   - test_summary_sorted_by_date
   - test_single_day_no_enrichment

=== PHASE 6: Validation ===

Backend:
  py_compile all changed .py files
  pytest tests/backend/test_r8z_admin_per_visit_visibility.py -v
  pytest tests/backend/ -v

Frontend:
  npm run build (in web/)

Do NOT deploy without Matthew's explicit approval.
Do NOT modify Terraform resource definitions.
Do NOT modify mobile app.

Return: files changed, test results, build result.
```

---

## 15. Commit Command (Planning Doc Only)

```bash
git add docs/planning/release-8z-admin-per-visit-completion-visibility-plan.md
git commit -m "docs: plan release 8z admin per visit completion visibility"
```
