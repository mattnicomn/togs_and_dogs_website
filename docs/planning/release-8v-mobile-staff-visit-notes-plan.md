# Release 8V: Mobile Staff Visit Notes

**Status:** Planning
**Priority:** Medium (operational value — staff can record care activity)
**Risk to Production:** Low (small backend addition + mobile UI)
**Terraform Required:** No
**Backend Changes:** Yes — minimal (add `visit_notes` field passthrough in review handler)
**Scope:** Mobile note input on Mark Completed + backend field persistence

---

## 1. Purpose

Allow staff to add a short completion note when marking a visit as done. Ryan/admin can then see what happened during each visit from the web dashboard or mobile admin view. This is the simplest form of visit logging before photos or structured check-in/check-out flows.

---

## 2. Current State

### What Exists

- Staff can mark visits as COMPLETED via `POST /admin/review` with `status: "COMPLETED"` (Release 8T)
- The `body.get('reason')` field is stored in the **audit log** entry but NOT as a top-level searchable/visible field
- The web CareCard detail view shows `pet_info`, `details`, and `timing_notes` but has no "visit notes" or "completion notes" section
- DynamoDB records can store arbitrary additional fields (schema-less)

### What's Missing

- The review handler does NOT persist arbitrary body fields to the record (only `status`, `worker_id`, `updated_at`, `audit_log`)
- No `visit_notes` or `completed_notes` field is currently stored
- No `completed_at` or `completed_by` field is set on completion (only `updated_at` and `updated_by`)
- The mobile app has no text input in the Mark Completed flow

---

## 3. Data Model

### Proposed Fields on REQ Record (parent)

| Field | Type | Set By | Set When |
|-------|------|--------|----------|
| `visit_notes` | String (max 500 chars) | Staff (mobile) | On Mark Completed |
| `completed_at` | ISO 8601 string | Backend | On status → COMPLETED |
| `completed_by` | Email string | Backend | On status → COMPLETED |

### Where Notes Live

**On the parent REQ# record.** Reasons:
- The REQ is what admin views in the web dashboard
- Staff marks the parent complete (cascades to child JOBs)
- For multi-day bookings, each completion action overwrites the parent's notes — this is acceptable because each "Mark Completed" is for the whole booking, not individual days
- Per-day notes would require a different approach (JOB-level notes) — defer to future

### For Multi-Day Bookings (Future Consideration)

If per-day notes are needed later, they'd go on individual JOB# records. For 8V MVP, notes go on the parent REQ and apply to the overall booking.

---

## 4. Backend Changes Required (Minimal)

### Change: Add `visit_notes`, `completed_at`, `completed_by` to Review Handler

**File:** `src/backend/handlers/review_handler.py`

In the section where the update expression is built (after line ~213):

```python
# SPECIAL CASE: Completion metadata
if new_status == 'COMPLETED':
    update_expr += ", completed_at = :cat, completed_by = :cby"
    expr_attr_vals[":cat"] = now
    expr_attr_vals[":cby"] = updated_by
    
    # Optional visit notes from staff
    visit_notes = body.get('visit_notes', '').strip()
    if visit_notes:
        # Truncate to 500 chars for safety
        visit_notes = visit_notes[:500]
        update_expr += ", visit_notes = :vn"
        expr_attr_vals[":vn"] = visit_notes
```

### What This Does

- When status transitions to COMPLETED, stores `completed_at` and `completed_by` on the record
- If `visit_notes` is included in the request body, stores it on the record (max 500 chars)
- If `visit_notes` is empty or missing, field is not set (backward compatible)
- No new endpoint needed — enhances existing `POST /admin/review`

### What This Does NOT Change

- No new API route
- No DynamoDB schema change (schema-less — new fields stored automatically)
- No Terraform change
- No notification side effects
- No calendar side effects
- Backward compatible — existing calls without `visit_notes` work identically

---

## 5. Mobile UX Flow

### Staff Booking Detail → Mark Completed

```
┌─────────────────────────────────────┐
│ [Booking detail content]            │
├─────────────────────────────────────┤
│ Visit Notes (optional)              │
│ ┌─────────────────────────────────┐ │
│ │ Fed Buddy, walked 30 min. He   │ │
│ │ pulled toward the park. All     │ │
│ │ good! Gate latched on exit.     │ │
│ └─────────────────────────────────┘ │
│ 127/500 characters                  │
│                                     │
│        [✓ Mark Completed]           │
└─────────────────────────────────────┘
```

### Flow

1. Staff views ASSIGNED visit detail
2. Optional: types notes in text area (max 500 chars, counter shown)
3. Taps "Mark Completed"
4. Confirmation modal: "Mark this visit as completed? Notes will be saved."
5. On confirm: calls `POST /admin/review` with `{ request_id, client_id, status: "COMPLETED", visit_notes: "..." }`
6. Success: toast + navigate back to schedule
7. Notes are now visible to admin in web dashboard

### Empty Notes Allowed

Notes are optional. Staff can mark complete without typing anything. The `visit_notes` field simply won't be set on the record.

---

## 6. Role Rules

| Role | Can Add Notes? | Can View Notes? | Can Edit Notes? |
|------|---------------|-----------------|-----------------|
| Staff | ✅ On Mark Completed | ✅ Own visits (detail view) | ❌ Not after submission |
| Admin/Owner | ❌ (different action set) | ✅ All visits | ❌ (view-only for now) |
| Client | ❌ | ❌ (deferred) | ❌ |

### Staff Ownership Enforcement

Staff can only add notes to visits they're assigned to (enforced by mobile UI scoping — only shows their own ASSIGNED visits).

---

## 7. Admin Visibility

### Web Dashboard (Existing CareCard/Detail View)

Once `visit_notes` is stored on the REQ record, it's automatically returned by `GET /admin/requests`. The web admin detail/CareCard will show it if the field exists — this may require a small frontend addition (display the field if present) but is NOT required for Release 8V.

### Mobile Admin View (RequestDetailScreen)

Similarly, `visit_notes` will be in the API response. The mobile detail screen can show it as a read-only section. This can be added in 8V or deferred.

**Recommendation:** Add display of `visit_notes` in the mobile detail screen (read-only for all roles) in this same release since it's 2-3 lines of JSX.

---

## 8. Notification/Calendar Side Effects

| Side Effect | Expected Behavior |
|-------------|-------------------|
| Email notification | ❌ None — no notification configured for COMPLETED |
| Google Calendar | ❌ No change — event stays on calendar |
| Cascade to child JOBs | ✅ Status cascades (existing behavior) — notes do NOT cascade |
| Audit log | ✅ `visit_notes` content included in audit entry reason |

---

## 9. Guardrails

| Guardrail | Implementation |
|-----------|---------------|
| Anti-double-tap | `isMutating` state disables button during API call |
| Character limit | 500 max enforced frontend + backend |
| No duplicate notifications | No notification fires on COMPLETED |
| No calendar updates | No calendar action on COMPLETED |
| No client emails | Client notification for completion is not configured |
| Notes immutable after submission | No edit endpoint provided — submit once |
| Backend truncation | `visit_notes[:500]` prevents oversized writes |

---

## 10. Files to Create/Modify

| File | Change | New? |
|------|--------|------|
| `src/backend/handlers/review_handler.py` | Add `completed_at`, `completed_by`, `visit_notes` on COMPLETED transition | Modified |
| `mobile/src/screens/RequestDetailScreen.tsx` | Add text area for notes before Mark Completed button; show notes read-only if present | Modified |
| `tests/backend/test_r8v_visit_notes.py` | Test: notes stored on COMPLETED, empty notes ok, truncation | ✅ New |

### Files NOT Changed

- No Terraform
- No web frontend (admin visibility is future follow-up)
- No API client changes (`reviewRequest()` already accepts arbitrary body fields — `visit_notes` passes through)
- No notification logic
- No calendar logic
- No DynamoDB schema change

---

## 11. Acceptance Criteria

- [ ] Staff sees optional text area above "Mark Completed" button (ASSIGNED visits only)
- [ ] Character counter shows current/500
- [ ] Mark Completed succeeds with notes → `visit_notes` stored on REQ record
- [ ] Mark Completed succeeds without notes → field not set (no error)
- [ ] `completed_at` and `completed_by` stored on REQ record
- [ ] Notes > 500 chars truncated server-side
- [ ] Admin can see `visit_notes` in API response (DynamoDB)
- [ ] Mobile detail screen shows notes read-only if present
- [ ] No notification fires
- [ ] No calendar update
- [ ] Anti-double-tap works
- [ ] TypeScript compiles
- [ ] Backend tests pass
- [ ] Expo Go app launches without crash

---

## 12. Validation Checklist

### Staff Account: `mattnicomn10@yahoo.com`

| # | Test | Expected |
|---|------|----------|
| 1 | Login as staff | Schedule with assigned visits |
| 2 | Tap ASSIGNED visit → detail | Note text area visible above Mark Completed |
| 3 | Type "Fed Buddy, walked 30 min" | Character counter updates |
| 4 | Tap Mark Completed | Confirmation modal shows note will be saved |
| 5 | Confirm | Success toast, back to schedule |
| 6 | Query DynamoDB for REQ record | `visit_notes`, `completed_at`, `completed_by` present |
| 7 | Mark Completed without notes | Succeeds, `visit_notes` field absent |
| 8 | Type 600 chars → complete | Only 500 stored (truncated) |
| 9 | Admin views visit (mobile or web) | Notes visible if implemented |

### Backend Tests

```bash
cd tests/backend
pytest test_r8v_visit_notes.py -v
```

Tests:
- `test_completed_stores_visit_notes`
- `test_completed_without_notes_ok`
- `test_visit_notes_truncated_at_500`
- `test_completed_at_and_completed_by_set`
- `test_non_completed_transition_does_not_set_notes`

---

## 13. Rollback

- **Mobile:** Revert `RequestDetailScreen.tsx` — removes text area, staff falls back to note-less completion
- **Backend:** Revert review handler changes — `visit_notes` field simply not stored
- **Data:** Any `visit_notes` already stored are harmless (ignored by old code)
- **No production impact** — notes are additive, never block workflows

---

## 14. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 8V: Mobile Staff Visit Notes.

Backend + mobile changes. No Terraform, web, or infrastructure changes.

=== 1. Update src/backend/handlers/review_handler.py ===

After the update expression is built (around line 215, after the ASSIGNED→APPROVED
REMOVE worker_id special case), add a COMPLETED special case:

    # Release 8V: Completion metadata + optional visit notes
    if new_status == 'COMPLETED':
        update_expr += ", completed_at = :cat, completed_by = :cby"
        expr_attr_vals[":cat"] = now
        expr_attr_vals[":cby"] = updated_by
        
        visit_notes = (body.get('visit_notes') or '').strip()
        if visit_notes:
            visit_notes = visit_notes[:500]  # Safety truncation
            update_expr += ", visit_notes = :vn"
            expr_attr_vals[":vn"] = visit_notes

=== 2. Update mobile/src/screens/RequestDetailScreen.tsx ===

For staff users viewing ASSIGNED visits:

a) Add state:
   const [visitNotes, setVisitNotes] = useState('');

b) Above the "Mark Completed" button, add a TextInput:
   - Label: "Visit Notes (optional)"
   - Placeholder: "How did the visit go? Any observations..."
   - multiline, 3-4 lines height
   - maxLength: 500
   - Character counter: "{visitNotes.length}/500"
   - Only visible when status is ASSIGNED and role is staff

c) In the handleMarkCompleted function, include visit_notes:
   await reviewRequest(request.request_id, request.client_id, 'COMPLETED', visitNotes || '');
   
   Wait — reviewRequest signature is (requestId, clientId, status, reason).
   The 'reason' field goes to audit log. We need visit_notes as a separate field.
   
   CORRECTION: Update the mobile API client to pass visit_notes:
   
   In mobile/src/api/client.ts, update reviewRequest to accept optional extra fields:
   
   export const reviewRequest = (
     requestId: string, clientId: string, status: string, reason = "", visitNotes = ""
   ) => request('/admin/review', 'POST', {
     request_id: requestId,
     client_id: clientId,
     status,
     reason,
     ...(visitNotes ? { visit_notes: visitNotes } : {})
   }, true);

d) Show visit_notes read-only if present on the request (for any role viewing a COMPLETED visit):
   {request.visit_notes && (
     <View style={styles.section}>
       <Text style={styles.sectionLabel}>VISIT NOTES</Text>
       <Text style={styles.notesText}>{request.visit_notes}</Text>
       {request.completed_at && (
         <Text style={styles.metaText}>Completed {formatDate(request.completed_at)} by {request.completed_by}</Text>
       )}
     </View>
   )}

=== 3. Create tests/backend/test_r8v_visit_notes.py ===

Tests using unittest.mock patching review_handler:
- test_completed_stores_visit_notes: transition to COMPLETED with visit_notes → update includes visit_notes
- test_completed_without_notes_ok: transition to COMPLETED without visit_notes → succeeds, no visit_notes in update
- test_visit_notes_truncated_at_500: 600-char note → only 500 stored
- test_completed_at_and_completed_by_set: completed_at and completed_by in update expression
- test_non_completed_transition_ignores_notes: transition to APPROVED with visit_notes → notes NOT stored

=== 4. Validation ===

Backend:
  python -m py_compile src/backend/handlers/review_handler.py
  pytest tests/backend/test_r8v_visit_notes.py -v
  pytest tests/backend/ -v (full suite)

Mobile:
  cd mobile && npx tsc --noEmit
  npx expo start --port 8082
  Test: staff login → ASSIGNED visit → type note → Mark Completed → verify in DynamoDB

Do NOT modify Terraform, web frontend, or AWS resources.
Do NOT deploy to App Store.
Do NOT deploy backend (terraform apply) without Matthew's explicit approval.

Return: files changed, test results, TypeScript result, manual observations.
```

---

## 15. Commit Command (Planning Doc Only)

```bash
git add docs/planning/release-8v-mobile-staff-visit-notes-plan.md
git commit -m "docs: plan release 8v mobile staff visit notes"
```
