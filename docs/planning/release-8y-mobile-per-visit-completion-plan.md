# Release 8Y: Mobile Per-Visit / Per-Day Completion Workflow

**Status:** Planning
**Priority:** High (core operational gap for multi-day bookings)
**Risk to Production:** Medium (requires a new backend endpoint for per-JOB updates)
**Terraform Required:** Yes (new API route for JOB status update — minimal)
**Backend Changes:** Yes (new handler or new route in existing handler)
**Scope:** Per-day completion for multi-day bookings via child JOB records

---

## 1. Purpose

Allow staff to mark individual visit days as completed without completing the entire multi-day booking. Currently, "Mark Completed" on a 5-day booking marks ALL 5 days as done — even if only day 1 is finished.

---

## 2. Current Data Model

### Parent REQ Record

```
PK: REQ#<request_id>
SK: CLIENT#<client_id>
Fields:
  status: "ASSIGNED"
  job_id: "first-job-uuid"
  job_ids: ["job-1", "job-2", "job-3"]
  is_multi_day: true
  total_occurrences: 3
  selected_dates: ["2026-06-10", "2026-06-11", "2026-06-12"]
  worker_id: "mattnicomn10@yahoo.com"
  worker_name: "Test Staff"
```

### Child JOB Records (One Per Day)

```
PK: JOB#<job_id>
SK: REQ#<request_id>
Fields:
  status: "ASSIGNED"
  occurrence_date: "2026-06-10"
  occurrence_index: 1
  total_occurrences: 3
  is_multi_day: true
  scheduled_date: "2026-06-10"
  start_date: "2026-06-10"
  end_date: "2026-06-10"
  worker_id: "mattnicomn10@yahoo.com"
  service_type: "WALK_30MIN"
  client_name: "Jane Smith"
  pet_name: "Buddy"
  google_event_id: "gcal-xxx"
```

### Current Status Flow

```
POST /admin/review (status: COMPLETED)
  → Updates parent REQ to COMPLETED
  → cascade_status_to_job() updates ALL child JOBs to COMPLETED
  → All calendar events remain, all days marked done
```

**Problem:** No way to complete just one JOB independently.

---

## 3. Current Mobile Behavior

### ScheduleScreen

- Fetches parent REQ records via `GET /admin/requests?status=ALL`
- Expands `selected_dates` into individual date rows
- Each row shows one date from the parent's `selected_dates` array
- Tapping a row navigates to `RequestDetailScreen` with the **parent** request data
- No individual JOB status is shown (all inherit parent's status)

### Mark Completed (8V)

- Calls `POST /admin/review` with parent's `request_id` and `client_id`
- Transitions parent to COMPLETED → cascades to ALL child JOBs
- Multi-day warning shown before submission
- After completion, ALL dates disappear from schedule

---

## 4. Recommended Approach: Option C (Independent JOB Completion)

### Options Evaluated

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: Complete child JOB only** | Update JOB status without touching parent | Simple | Parent shows ASSIGNED even when all days done |
| **B: Auto-rollup** | Complete JOB, then check if all JOBs done → auto-complete parent | Clean | Complex rollup logic, new reverse cascade |
| **C: Independent JOB status + manual parent completion** | JOBs track per-day completion; parent stays ASSIGNED until admin/all-done | Clear separation, low risk | Requires new endpoint + mobile awareness of JOB status |

**Recommended: Option C** — with simple auto-rollup.

### How It Works

1. Staff completes a single day → updates that JOB to COMPLETED
2. Parent REQ stays ASSIGNED (still has active child JOBs)
3. When the LAST child JOB is completed → auto-rollup: parent transitions to COMPLETED
4. Admin can also force-complete the parent at any time (existing behavior unchanged)

---

## 5. Backend Requirement: New JOB Status Update Endpoint

### Proposed: `POST /admin/job/complete`

```json
{
  "job_id": "job-uuid",
  "request_id": "request-uuid",
  "visit_notes": "Fed Buddy, 30 min walk. All good.",
  "completed_by": "mattnicomn10@yahoo.com"
}
```

**Response:**
```json
{
  "message": "Visit completed successfully.",
  "job_id": "job-uuid",
  "status": "COMPLETED",
  "parent_status": "ASSIGNED",
  "remaining_active_jobs": 2
}
```

### Handler Logic (Smallest Safe Addition)

```python
# In admin_handler.py or new job_status_handler.py

def handle_job_complete(event, body):
    role = get_effective_role(event)
    if role not in ['owner', 'admin', 'staff']:
        return error(403, "Forbidden", event)
    
    job_id = body.get('job_id')
    request_id = body.get('request_id')
    visit_notes = (body.get('visit_notes') or '').strip()[:500]
    
    # 1. Get the JOB record
    job = get_item(f"JOB#{job_id}", f"REQ#{request_id}")
    if not job:
        return not_found("Job record not found", event)
    
    # 2. Staff ownership check
    if role == 'staff':
        claims = get_claims(event)
        user_email = claims.get('email', '').lower().strip()
        if job.get('worker_id') and job.get('worker_id').lower() != user_email:
            return error(403, "You can only complete visits assigned to you.", event)
    
    # 3. Validate current status (must be ASSIGNED or JOB_CREATED)
    current_status = job.get('status', '')
    if current_status == 'COMPLETED':
        return success({"message": "Already completed", "job_id": job_id, "status": "COMPLETED"}, event)
    if current_status not in ['ASSIGNED', 'JOB_CREATED', 'SCHEDULED']:
        return bad_request(f"Cannot complete job in status: {current_status}", event)
    
    # 4. Update JOB to COMPLETED
    now = datetime.now(timezone.utc).isoformat()
    update_expr = "SET #stat = :s, completed_at = :cat, completed_by = :cby, updated_at = :now"
    expr_vals = {":s": "COMPLETED", ":cat": now, ":cby": updated_by, ":now": now}
    
    if visit_notes:
        update_expr += ", visit_notes = :vn"
        expr_vals[":vn"] = visit_notes
    
    table.update_item(
        Key={'PK': f"JOB#{job_id}", 'SK': f"REQ#{request_id}"},
        UpdateExpression=update_expr,
        ExpressionAttributeNames={"#stat": "status"},
        ExpressionAttributeValues=expr_vals
    )
    
    # 5. Check if ALL sibling JOBs are now COMPLETED → auto-rollup parent
    parent_req = get_item(f"REQ#{request_id}", f"CLIENT#{job.get('client_id')}")
    all_job_ids = parent_req.get('job_ids') or [parent_req.get('job_id')]
    
    all_completed = True
    for jid in all_job_ids:
        if jid == job_id:
            continue  # This one is now completed
        sibling = get_item(f"JOB#{jid}", f"REQ#{request_id}")
        if sibling and sibling.get('status') != 'COMPLETED':
            all_completed = False
            break
    
    parent_status = parent_req.get('status')
    if all_completed and parent_status != 'COMPLETED':
        # Auto-rollup: complete parent
        table.update_item(
            Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{job.get('client_id')}"},
            UpdateExpression="SET #stat = :s, completed_at = :cat, updated_at = :now",
            ExpressionAttributeNames={"#stat": "status"},
            ExpressionAttributeValues={":s": "COMPLETED", ":cat": now, ":now": now}
        )
        parent_status = "COMPLETED"
    
    remaining = sum(1 for jid in all_job_ids if jid != job_id 
                    and get_item(f"JOB#{jid}", f"REQ#{request_id}") 
                    and get_item(f"JOB#{jid}", f"REQ#{request_id}").get('status') != 'COMPLETED')
    
    return success({
        "message": "Visit completed successfully.",
        "job_id": job_id,
        "status": "COMPLETED",
        "parent_status": parent_status,
        "remaining_active_jobs": remaining
    }, event)
```

### Terraform Addition

A new route: `POST /admin/job/complete` (or `POST /admin/jobs/{jobId}/complete`)
- Cognito authorizer (protected)
- Points to existing admin Lambda (or a new small Lambda)
- CORS OPTIONS method

---

## 6. Visit Notes Model

### Notes on Child JOB Records (Per-Day)

| Field | Location | When Set |
|-------|----------|----------|
| `visit_notes` | JOB# record | On per-day completion |
| `completed_at` | JOB# record | On per-day completion |
| `completed_by` | JOB# record | On per-day completion |

### Notes on Parent REQ Record (Summary)

| Field | Location | When Set |
|-------|----------|----------|
| `visit_notes` | REQ# record | Only on single-day completion (8V behavior) |
| `completed_at` | REQ# record | On auto-rollup or admin force-complete |

### Admin Visibility

Per-day notes live on JOB records. To display them:
- Web admin could show a "Completion Log" section with notes per day
- Mobile admin detail could show completed dates + their notes
- This is a display enhancement, not required for 8Y MVP

---

## 7. Mobile UX

### Staff Schedule → Per-Day Completion

```
┌─────────────────────────────────────┐
│ Today (Tue, Jun 10)                  │
│ ┌─────────────────────────────────┐ │
│ │ 🐾 Buddy — 30-Min Walk         │ │
│ │ Client: Jane Smith              │ │
│ │ 👤 Test Staff       Day 1 of 3 │ │
│ │ [Tap to view & complete]        │ │
│ └─────────────────────────────────┘ │
│                                      │
│ Upcoming                             │
│ ┌── Wed, Jun 11 ─────────────────┐ │
│ │ 🐾 Buddy — 30-Min Walk  2 of 3│ │
│ └─────────────────────────────────┘ │
│ ┌── Thu, Jun 12 ─────────────────┐ │
│ │ 🐾 Buddy — 30-Min Walk  3 of 3│ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

### Detail Screen for Specific Day

When staff taps a date card, the detail screen shows:
- **Which specific date** this visit is for (prominently displayed)
- Client/pet/care info (from parent REQ)
- Visit Notes text area
- "Mark This Visit Completed" button

The key difference from 8V: the completion call targets a specific `job_id`, not the parent `request_id`.

### Resolving Job ID from Date

The mobile app needs to know which `job_id` corresponds to which date. Options:

**Option A (Recommended):** Fetch individual JOB records from a new endpoint or include them in the ALL response.

**Option B (Simpler MVP):** Map `job_ids[index]` to `selected_dates[index]` — since JOBs are created in chronological order, `job_ids[0]` = first date, `job_ids[1]` = second date, etc.

**Option B is safe** because the job handler creates JOBs in sorted date order and the arrays are parallel. This avoids needing a new API endpoint just to list JOBs.

### Single-Day Bookings

For single-day bookings (`is_multi_day` is false):
- No change needed — existing 8V behavior works
- `POST /admin/review` with `status: COMPLETED` completes the single JOB
- OR the new `POST /admin/job/complete` can handle single-day too (uses `job_id`)

---

## 8. Guardrails

| Guardrail | Implementation |
|-----------|---------------|
| Staff ownership | Backend checks `worker_id` matches calling user's email |
| Prevent wrong date/JOB | Mobile maps `job_ids[index]` → `selected_dates[index]` |
| Anti-double-tap | `isMutating` state on mobile |
| Idempotency | If JOB already COMPLETED, return success (no error) |
| No notifications | COMPLETED event has no notification configured |
| No calendar updates | Calendar events remain unchanged on completion |
| Parent auto-rollup | Only fires when ALL siblings are COMPLETED |

---

## 9. Backward Compatibility

| Concern | Resolution |
|---------|-----------|
| Existing completed parent REQs | Unaffected — already in COMPLETED status |
| Existing `visit_notes` on parent REQ (from 8V) | Preserved — single-day completion via review handler still works identically |
| Single-day bookings | Can use either `POST /admin/review` (existing) or new JOB endpoint |
| Web admin "Mark Completed" | Still calls `POST /admin/review` → cascades to all JOBs (unchanged) |
| Mobile Mark Completed for single-day | Can keep using `POST /admin/review` (no regression) |

---

## 10. Files to Create/Modify

| File | Change | New? |
|------|--------|------|
| `src/backend/handlers/admin_handler.py` | Add `POST /admin/job/complete` route handling | Modified |
| `modules/api/main.tf` | Add API Gateway route for `/admin/job/complete` | Modified |
| `modules/api/variables.tf` | No change (uses existing admin Lambda) | — |
| `infra/prod/main.tf` | Add deployment trigger | Modified |
| `mobile/src/api/client.ts` | Add `completeJob()` function | Modified |
| `mobile/src/screens/ScheduleScreen.tsx` | Pass `job_ids` mapping to detail navigation | Modified |
| `mobile/src/screens/RequestDetailScreen.tsx` | Use `completeJob()` for multi-day, keep `reviewRequest()` for single-day | Modified |
| `tests/backend/test_r8y_per_visit_completion.py` | New test file | ✅ New |

---

## 11. Acceptance Criteria

- [ ] Staff can complete a single day of a multi-day booking without completing all days
- [ ] Completed day disappears from Today/Upcoming schedule
- [ ] Remaining days stay in schedule
- [ ] Visit notes stored on the individual JOB record
- [ ] When ALL days are completed, parent auto-transitions to COMPLETED
- [ ] Staff cannot complete a visit assigned to someone else (403)
- [ ] Single-day bookings still work via existing flow
- [ ] Admin web dashboard shows parent as ASSIGNED while individual days complete
- [ ] Anti-double-tap prevents duplicate calls
- [ ] Already-completed JOB returns success (idempotent)
- [ ] TypeScript compiles
- [ ] Backend tests pass
- [ ] Terraform validates

---

## 12. Validation Checklist

### Staff Account: `mattnicomn10@yahoo.com`

| # | Test | Expected |
|---|------|----------|
| 1 | Create a 3-day test booking assigned to test staff | 3 JOBs created |
| 2 | Staff opens Schedule → sees 3 date cards | All show as assigned |
| 3 | Tap Day 1 → add note "Day 1 done" → Mark Completed | Only Day 1 JOB → COMPLETED |
| 4 | Schedule refreshes → Day 1 gone, Days 2-3 remain | Correct filtering |
| 5 | Parent REQ status | Still ASSIGNED |
| 6 | Complete Day 2 | Day 2 JOB → COMPLETED, parent still ASSIGNED |
| 7 | Complete Day 3 (last) | Day 3 JOB → COMPLETED, parent auto-rolls to COMPLETED |
| 8 | All days gone from schedule | Correct |
| 9 | Admin web → view parent | Shows COMPLETED |
| 10 | Single-day booking → Mark Completed | Works as before (no regression) |

### Backend Tests

- `test_complete_single_job`
- `test_complete_job_stores_notes`
- `test_complete_job_staff_ownership_check`
- `test_complete_already_completed_idempotent`
- `test_auto_rollup_when_all_jobs_done`
- `test_no_rollup_when_siblings_still_active`
- `test_single_day_via_job_endpoint`

---

## 13. Rollback

- **Backend:** Remove the new route handler; single-day completion via `POST /admin/review` still works
- **Terraform:** Remove API Gateway route; redeploy
- **Mobile:** Revert to 8V behavior (parent-level completion with multi-day warning)
- **Data:** Any JOB-level `visit_notes`/`completed_at` fields are harmless extras

---

## 14. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 8Y: Per-Visit / Per-Day Completion.

Backend + Terraform + Mobile changes. This is a larger release requiring Matthew's
explicit approval for both backend deployment and mobile changes.

=== PHASE 1: Backend (requires terraform apply approval) ===

1. In src/backend/handlers/admin_handler.py, add a new route block:

   if http_method == 'POST' and '/admin/job/complete' in path:
       [implement per Section 5 of this planning document]
       - Role check: owner, admin, staff
       - Staff ownership check (worker_id must match calling email)
       - Get JOB record, validate status is ASSIGNED/JOB_CREATED
       - Update JOB to COMPLETED with completed_at, completed_by, optional visit_notes[:500]
       - Check all sibling JOBs — if all COMPLETED, auto-rollup parent REQ
       - Return job status + parent status + remaining count
       - Idempotent: if already COMPLETED, return success

2. In modules/api/main.tf, add:
   - Resource: /admin/job
   - Resource: /admin/job/complete
   - Method: POST with Cognito authorizer
   - Integration: admin Lambda
   - CORS OPTIONS
   - Add to deployment depends_on + triggers

3. Tests: tests/backend/test_r8y_per_visit_completion.py
   - 7 test cases per Section 12

4. Validation:
   - py_compile all changed .py files
   - pytest tests/backend/test_r8y_per_visit_completion.py -v
   - pytest tests/backend/ -v (full suite)
   - terraform fmt && terraform validate (in infra/prod/)

DO NOT run terraform apply without Matthew's explicit approval.

=== PHASE 2: Mobile (after backend is deployed) ===

5. mobile/src/api/client.ts — add:
   export const completeJob = (jobId, requestId, visitNotes = '') =>
     request('/admin/job/complete', 'POST', {
       job_id: jobId, request_id: requestId, visit_notes: visitNotes
     }, true);

6. mobile/src/screens/ScheduleScreen.tsx — pass job_ids mapping:
   When building ExpandedVisit rows, include the corresponding job_id:
   job_ids[index] maps to selected_dates[index] (parallel arrays)

7. mobile/src/screens/RequestDetailScreen.tsx — detect per-day:
   - If route params include a specific job_id + occurrence_date:
     Use completeJob() instead of reviewRequest()
   - If single-day (no is_multi_day): keep existing reviewRequest() flow
   - Show the specific date prominently on the detail screen

8. Mobile validation:
   - npx tsc --noEmit
   - npx expo start --port 8082
   - Test per-day completion flow with staff account

Return: files changed, test results, terraform validate output, mobile test observations.
```

---

## 15. Commit Command (Planning Doc Only)

```bash
git add docs/planning/release-8y-mobile-per-visit-completion-plan.md
git commit -m "docs: plan release 8y mobile per visit completion"
```
