# Intake, Client Management, Scheduling & Record Recovery — Discovery Evaluation

**Date:** 2026-05-11  
**Status:** Discovery Only — No Implementation  
**Author:** Kiro (automated code inspection)

---

## 1. Current Intake Form Fields and Payload Structure

### Frontend (IntakeForm.jsx)

The intake form is a 3-step wizard:

| Step | Field | Type | Required |
|------|-------|------|----------|
| 1 - Contact | `client_name` | text | Yes |
| 1 - Contact | `client_email` | email | Yes |
| 2 - Schedule | `service_type` | select: PET_SITTING, DOG_WALKING, OVERNIGHT | Yes |
| 2 - Schedule | `start_date` | date | Yes |
| 2 - Schedule | `end_date` | date | No |
| 2 - Schedule | `visit_window` | select: MORNING, MIDDAY, AFTERNOON, EVENING, ANYTIME | No (defaults ANYTIME) |
| 3 - Pets | `pet_names` | text (free-form, comma-separated) | Yes |
| 3 - Pets | `pet_info` | textarea (care instructions) | No |

### Backend Payload (intake_handler.py)

The handler creates a single `REQ#<uuid>` record with:
- `PK`: `REQ#<request_id>`
- `SK`: `CLIENT#<client_id>`
- All form fields above plus: `request_id`, `client_id`, `company_id`, `status` (PENDING_REVIEW), `workflow_type` (CUSTOMER_INTAKE or VISIT_BOOKING), `created_at`, `entity_type` (REQUEST)

### Workflow Type Determination

- Public path `/requests` → `CUSTOMER_INTAKE`
- Authenticated client path `/client/requests` with approved profile → `VISIT_BOOKING`
- Approved = `is_active=True` AND `portal_enabled=True` on client profile

### Gaps Identified

1. **Visit Window is single-select only** — no multi-select for multiple visits per day
2. **No Preferred Sitter field** — no way to express staff preference
3. **Pet data is free-text** — no structured per-pet fields (breed, age, medications, etc.)
4. **No vet/emergency fields** on intake
5. **No quote/pricing fields** on intake

---

## 2. Current Request Record Schema

```
PK: REQ#<uuid>
SK: CLIENT#<client_id>
```

| Field | Source | Notes |
|-------|--------|-------|
| request_id | Generated UUID | |
| client_id | Generated or resolved from auth | |
| company_id | From auth context | |
| client_name | Form input | |
| client_email | Form input | |
| start_date | Form input | YYYY-MM-DD |
| end_date | Form input | YYYY-MM-DD, optional |
| visit_window | Form input | ANYTIME default |
| preferred_time | Form input | Currently unused in UI |
| timing_notes | Form input | Currently unused in UI |
| pet_names | Form input | Free text |
| pet_info | Form input | Free text |
| service_type | Form input | PET_SITTING default |
| status | System | PENDING_REVIEW initial |
| workflow_type | System | CUSTOMER_INTAKE or VISIT_BOOKING |
| created_at | System | ISO timestamp |
| entity_type | System | "REQUEST" |
| worker_id | Set on assignment | Staff email |
| worker_name | Set on assignment | Display name |
| job_id | Set on approval | Links to JOB record |
| pet_id | Set on approval | Links to PET record |
| google_event_id | Set on calendar sync | |
| audit_log | System | List of status change entries |
| cancellation_* | Set on cancel flow | reason, requested_at, decision_at, etc. |

---

## 3. Current Client Profile Schema

```
PK: COMPANY#<company_id>
SK: CLIENT#<client_id>
```

| Field | Notes |
|-------|-------|
| client_id | e.g. "client_abc12345" |
| company_id | Tenant scoping |
| display_name | |
| email | |
| phone | |
| address | |
| emergency_contact | Single text field |
| notes | |
| is_active | Boolean |
| portal_enabled | Boolean — gates client portal access |
| cognito_sub | Cognito user link |
| cognito_status | CONFIRMED, FORCE_CHANGE_PASSWORD, etc. |
| created_at, updated_at | |

### Client Profile Creation

Profiles are created **manually** by admin via:
- `POST /admin/clients` (profile only, no login)
- `POST /admin/clients/onboard` (profile + Cognito user + welcome email)

**There is NO automatic client profile creation from intake approval.** This is a manual step Ryan must perform.

---

## 4. Current Pet/Profile Handling Model

```
PK: PET#<uuid>
SK: CLIENT#<client_id>
```

| Field | Notes |
|-------|-------|
| pet_id | UUID |
| client_id | Owner link |
| company_id | Tenant |
| name | From pet_names (often the full string) |
| breed | Editable via CareCard |
| age | Editable via CareCard |
| photo_url | S3 URL |
| care_instructions | From pet_info on intake |
| behavior | Editable via CareCard |
| logistics | Access codes, keys |
| health | Vet details |
| document_links | Map of URLs |
| meet_and_greet_completed | Boolean gate |
| meet_and_greet_required | Boolean |
| quote_amount | Decimal |
| deposit_required | Boolean |
| deposit_paid | Boolean |
| payment_status | "Not Quoted", "Accepted", "Deposit Paid", "Paid in Full" |
| quote_sent_date, quote_accepted_date | |
| quote_notes, internal_pricing_notes | |
| entity_type | "PET" |

### Pet Creation Flow

1. When a request is APPROVED, `review_handler.py` triggers `job_handler.py` via async Lambda invoke
2. `job_handler.py` checks if `pet_id` exists on the request
3. If not, it creates a new PET record with `name = pet_names` (the full free-text string)
4. Links `pet_id` back to the REQ record

### Gaps

- **One PET record per request** — no multi-pet support per booking
- Pet `name` is set to the entire `pet_names` string (e.g., "Joey, Kyle, Kevin")
- No structured breed/age/medication fields collected at intake
- No vet/emergency contact fields on intake

---

## 5. Current Quote/Payment Fields — Why They Are or Are Not Editable

### Where They Live

Quote and payment fields live on the **PET record**, not the REQ record:
- `quote_amount`, `deposit_required`, `deposit_paid`, `payment_status`
- `quote_sent_date`, `quote_accepted_date`, `quote_notes`, `internal_pricing_notes`

### Editability

The `pet_handler.py` defines these as editable fields in its `editable_fields` list. They ARE editable via `PUT /admin/pets/{petId}`.

**However**, the CareCard UI component is the only interface for editing pet records. Whether quote/payment fields are rendered as editable inputs in the CareCard depends on the frontend implementation of that component.

### Enforcement

The `review_handler.py` enforces a gate: if `quote_amount > 0` and `payment_status` not in `['Accepted', 'Deposit Paid', 'Paid in Full']`, the request cannot be moved to APPROVED.

### Gap

- Quote/payment fields are **not on the request record itself** — they're on the pet record
- If the CareCard doesn't expose editable quote fields, Ryan has no UI path to update them
- The Scheduling/Staff tab and the Request List view do not expose these fields inline

---

## 6. Current Scheduling/Staff Assignment Behavior

### Assignment Flow

1. Admin clicks "Assign" on a request in APPROVED status
2. Frontend calls `assignWorker(jobId, reqId, clientId, workerId, workerName)`
3. `assignment_handler.py` receives the call
4. Resolves the JOB record (handles race conditions where job_id might not be linked yet)
5. Updates **both** the JOB record AND the REQ record with:
   - `status = ASSIGNED`
   - `worker_id = <staff email>`
   - `worker_name = <display name>`
6. Syncs to Google Calendar
7. Triggers STAFF_ASSIGNED and VISIT_SCHEDULED notifications

### Race Condition Handling

The assignment handler has explicit code for when the JOB record exists but isn't linked back to the REQ yet:
- If `job_id == req_id` or starts with "REQ#", it attempts to resolve via the REQ record's `job_id` field
- If that fails, it does a **table scan** looking for JOB records with `SK = REQ#<req_id>`
- If multiple JOB records are found, it uses the first one and logs a warning

### Gap

- **Staff assignment is not editable from within the record** after initial assignment without using the "Change Worker" action
- The "Change Worker" action calls the same assignment handler (re-assignment)
- There is no inline staff picker on the Scheduling/Staff tab of the CareCard

---

## 7. Current Parent Request vs Child Visit Instance Behavior

### Critical Finding: There Is NO Child Visit Instance Pattern

The system does **not** expand overnight or multi-day bookings into per-day visit instances. A single REQ record with `start_date` and `end_date` represents the entire booking.

### What Creates the Appearance of Duplicates

**Both REQ# and JOB# records appear in the admin request list.** Here's why:

1. The `GET /admin/requests?status=ALL` endpoint scans DynamoDB with filter:
   ```
   contains(PK, "REQ#") OR contains(PK, "JOB#")
   ```

2. When a request is APPROVED, a JOB record is created:
   - `PK: JOB#<job_uuid>`, `SK: REQ#<request_id>`
   - Contains: `client_name`, `pet_name`, `service_type`, `start_date`, `worker_id`, `status`

3. The assignment handler updates **both** records to `ASSIGNED` status with the same `worker_id`

4. The frontend `AdminDashboard.jsx` merges records by PK:
   ```javascript
   const index = combined.findIndex(ex => ex.PK === newItem.PK);
   if (index >= 0) combined[index] = newItem;
   else combined.push(newItem);
   ```
   Since REQ# and JOB# have different PKs, **both appear in the list**.

5. The `getFilterPredicate('ASSIGNED')` filter matches:
   ```javascript
   return stat === 'ASSIGNED' || stat === 'SCHEDULED' || stat === 'IN_PROGRESS';
   ```
   Both the REQ and JOB records have `status = ASSIGNED`, so both pass the filter.

### Why the Two Rows Look Different

- **Row 1 (REQ record)**: Has `start_date` AND `end_date` → displays as "2026-05-15 to 2026-05-17"
- **Row 2 (JOB record)**: Only has `start_date` (copied from request) → displays as "2026-05-15"
- Both show the same client_name, service_type, worker_id, and ANYTIME window

---

## 8. Current Status Transition Matrix and Recovery Limitations

### Request Status Transitions (from status.py)

| From Status | Allowed Transitions |
|-------------|-------------------|
| PENDING_REVIEW | MEET_GREET_REQUIRED, READY_FOR_APPROVAL, PROFILE_CREATED, QUOTE_NEEDED, QUOTE_SENT, QUOTED, APPROVED, DECLINED, CANCELLED, ARCHIVED, DELETED |
| PROFILE_CREATED | READY_FOR_APPROVAL, MEET_GREET_REQUIRED, QUOTE_NEEDED, QUOTE_SENT, APPROVED, DECLINED, CANCELLED, ARCHIVED |
| MEET_GREET_REQUIRED | MG_SCHEDULED, MG_COMPLETED, READY_FOR_APPROVAL, QUOTE_NEEDED, DECLINED, CANCELLED, ARCHIVED |
| MG_SCHEDULED | MG_COMPLETED, MEET_GREET_REQUIRED, CANCELLED, ARCHIVED |
| MG_COMPLETED | QUOTE_NEEDED, QUOTE_SENT, QUOTED, READY_FOR_APPROVAL, APPROVED, CANCELLED, ARCHIVED |
| QUOTE_NEEDED | QUOTE_SENT, QUOTED, APPROVED, READY_FOR_APPROVAL, DECLINED, CANCELLED, ARCHIVED |
| QUOTE_SENT | APPROVED, QUOTE_NEEDED, DECLINED, CANCELLED, ARCHIVED |
| READY_FOR_APPROVAL | APPROVED, QUOTE_NEEDED, QUOTE_SENT, QUOTED, DECLINED, ARCHIVED |
| QUOTED | APPROVED, READY_FOR_APPROVAL, DECLINED, CANCELLED, ARCHIVED, DELETED |
| APPROVED | ASSIGNED, CANCELLATION_REQUESTED, CANCELLATION_DENIED, ARCHIVED, CANCELLED |
| ASSIGNED | APPROVED (rollback), COMPLETED, ARCHIVED, CANCELLED, CANCELLATION_REQUESTED, CANCELLATION_DENIED |
| CANCELLATION_REQUESTED | CANCELLED, CANCELLATION_DENIED, ARCHIVED |
| CANCELLATION_DENIED | ARCHIVED, CANCELLED |
| DECLINED | ARCHIVED, QUOTED, PENDING_REVIEW |
| **CANCELLED** | **ARCHIVED, PENDING_REVIEW, QUOTED, APPROVED** |
| **COMPLETED** | **ARCHIVED, ASSIGNED, APPROVED** |
| **ARCHIVED** | **PENDING_REVIEW, DELETED** |
| **DELETED** | **PENDING_REVIEW** |

### Recovery IS Possible

The transition matrix **does allow recovery**:
- `CANCELLED → PENDING_REVIEW` (reopen)
- `CANCELLED → APPROVED` (direct re-approval)
- `ARCHIVED → PENDING_REVIEW` (reopen)
- `DELETED → PENDING_REVIEW` (reopen)
- `COMPLETED → ASSIGNED` or `APPROVED` (reopen)

### Additional Safety Valve

The `is_valid_transition()` function has a blanket override:
```python
if new_status in ['ARCHIVED', 'DELETED']:
    return True  # Always allowed from any state
```

### Where Recovery Is Enforced

- **Backend**: `review_handler.py` calls `is_valid_transition()` before any status change
- **Frontend**: `getWorkflowState()` in AdminDashboard.jsx determines which action buttons appear per status. For ARCHIVED records, only `REOPEN_PENDING` and `DELETE` are shown. For DELETED records, only `REOPEN_PENDING` and `PURGE_FOREVER`.
- The `performAdminAction` POST endpoint also accepts `PENDING_REVIEW` as a valid action for bulk transitions

---

## 9. Root Cause Hypothesis: Duplicate/Ambiguous Scheduled Records

### Primary Cause: REQ + JOB Both Rendered in List

**Confidence: HIGH**

When a request is approved and assigned:
1. A `REQ#<uuid>` record exists with `status=ASSIGNED`, `worker_id=ryanywork@gmail.com`
2. A `JOB#<uuid>` record exists with `status=ASSIGNED`, `worker_id=ryanywork@gmail.com`
3. The backend scan returns **both** because the filter is `contains(PK, "REQ#") OR contains(PK, "JOB#")`
4. The frontend deduplicates by PK, but since PKs differ, both appear
5. The `ASSIGNED` filter predicate matches both

### Why They Display Differently

- REQ record has both `start_date` and `end_date` → "2026-05-15 to 2026-05-17"
- JOB record only copies `start_date` from the request → "2026-05-15"
- Both share: client_name, service_type, worker_id, visit_window (ANYTIME)

### Secondary Cause: Race Condition in Job Creation

**Confidence: MEDIUM**

The assignment handler's race condition handling (table scan for orphaned JOB records) could theoretically create scenarios where multiple JOB records exist for the same request, though the code only uses the first found.

---

## 10. Root Cause Hypothesis: Cancel Action Affecting Related Records

### Primary Cause: Shared Status Mirroring

**Confidence: HIGH**

The `review_handler.py` explicitly updates **both** the REQ and JOB records when status changes:

```python
# Also update the Job record if it exists
job_id = request_item.get('job_id')
if job_id:
    table.update_item(
        Key={'PK': f"JOB#{job_id}", 'SK': f"REQ#{request_id}"},
        UpdateExpression="SET #stat = :s, ..."
    )
```

When Ryan cancels one visible row (whether it's the REQ or JOB), the handler:
1. Updates the target record to CANCELLED
2. If it's the REQ record, also updates the linked JOB record
3. If it's the JOB record (via assignment_handler path), also updates the REQ record

**Result**: Both rows disappear from the "Scheduled with Staff" view simultaneously because both records transition to CANCELLED.

### The Cancellation Handler Also Cascades

The `cancellation_handler.py` (admin decision path) updates the REQ record and triggers:
- Google Calendar event deletion
- Worker SNS notification
- `VISIT_CANCELLED` notification

But it does NOT explicitly update the JOB record. This means:
- If admin cancels via the REQ record → JOB stays in ASSIGNED (orphaned)
- If admin cancels via review_handler → both update

This inconsistency could explain why one record later appears in Data Issues.

---

## 11. Root Cause Hypothesis: Valid Records Moving to Data Issues

### Primary Cause: ASSIGNED Status Without worker_id

**Confidence: HIGH**

The `isDataIssue()` function in AdminDashboard.jsx does NOT directly check for missing worker_id. However, `getWorkflowState()` does:

```javascript
const isInvalidAssigned = status === 'ASSIGNED' && !hasWorker;
if (isInvalidAssigned) {
    state.displayStatus = "Needs Assignment";
    state.statusClass = "status-chip status-chip--urgent";
}
```

And the `isDataIssue()` function catches records with:
- Missing or empty `status`
- Missing `pet_names` or `client_name`
- Unknown status values

### Scenario That Creates This

1. REQ record is in ASSIGNED status with `worker_id` set
2. Admin cancels the REQ via `review_handler` → status becomes CANCELLED, but the linked JOB record's `worker_id` removal depends on the transition path
3. If the rollback path (`ASSIGNED → APPROVED`) is triggered on the REQ, it explicitly does `REMOVE worker_id`
4. If the JOB record is then left in ASSIGNED without worker_id (due to inconsistent cascade), it becomes a "Data Issue"

### Alternative Scenario

The `review_handler.py` has this special case:
```python
# SPECIAL CASE: Rollback ASSIGNED -> APPROVED clears worker_id
if current_status == 'ASSIGNED' and new_status == 'APPROVED':
    update_expr += " REMOVE worker_id"
```

If this rollback is applied to the REQ but not the JOB (or vice versa), one record ends up in ASSIGNED without a worker_id → Data Issue.

---

## 12. Recommended Implementation Sequence

### Phase 1: Fix Duplicate Display (Low Risk, High Impact)

1. **Backend**: Filter JOB# records from the `GET /admin/requests?status=ALL` scan, OR add a `is_child_record` flag
2. **Frontend**: Deduplicate by `request_id` instead of by `PK`, preferring the REQ record
3. **Frontend**: If JOB records are shown, visually distinguish them (e.g., "Visit Instance" badge)

### Phase 2: Fix Cascade Consistency (Medium Risk)

1. Ensure ALL status transitions on REQ records cascade to linked JOB records
2. Ensure ALL status transitions on JOB records cascade back to REQ records
3. Add `end_date` to JOB record creation in `job_handler.py`
4. Add integration test for cancel → verify both records update

### Phase 3: Intake Form Enhancements (Low Risk)

1. Multi-select visit window
2. Optional preferred sitter field (display only, no auto-assignment)
3. Structured per-pet fields (name, breed, age, feeding, medication, behavior)
4. Vet & emergency contact fields

### Phase 4: Client Profile Automation (Medium Risk)

1. Auto-create client profile on intake approval (or offer one-click creation)
2. Allow existing clients to submit requests without manual profile creation
3. Link intake `client_email` to existing client profiles automatically

### Phase 5: Record Editability (Low Risk)

1. Make quote/payment fields editable inline from the request detail view
2. Make staff assignment editable from the Scheduling/Staff tab
3. Make payment status editable from the request detail view

### Phase 6: Client Management Enhancements (Medium Risk)

1. Search/filter/sort on client list
2. Export to CSV/Excel
3. Multi-pet per owner with structured data
4. Lightweight spreadsheet-like inline editing

### Phase 7: Status Recovery & Data Issues Cleanup (Low Risk)

1. Add "Recover" action to Data Issues view that routes to appropriate status
2. Add bulk recovery action
3. Add orphaned JOB record detection and cleanup utility

---

## 13. Risks and Rollback Considerations

### Phase 1 Risks
- **Risk**: Hiding JOB records may break the MasterScheduler which uses them for the timeline
- **Mitigation**: Keep JOB records in scheduler view, only hide from Request List
- **Rollback**: Revert filter change (no data modification)

### Phase 2 Risks
- **Risk**: Cascade changes could create infinite loops (REQ updates JOB, JOB updates REQ)
- **Mitigation**: Add `_cascade_source` flag to prevent re-entry
- **Rollback**: Revert handler code (no data modification)

### Phase 3 Risks
- **Risk**: Schema changes to intake payload could break existing records
- **Mitigation**: All new fields are optional, backward-compatible
- **Rollback**: Revert frontend form (backend ignores unknown fields)

### Phase 4 Risks
- **Risk**: Auto-creating Cognito users could create orphaned accounts if approval is reversed
- **Mitigation**: Create profile only (no Cognito) on approval; Cognito onboarding remains manual
- **Rollback**: Disable auto-creation flag

### Phase 5 Risks
- **Risk**: Inline editing could allow invalid state (e.g., payment marked "Paid" without quote)
- **Mitigation**: Enforce validation rules on save
- **Rollback**: Revert UI components (no data modification)

### Phase 6 Risks
- **Risk**: Multi-pet model changes the PET record cardinality
- **Mitigation**: Keep existing single-pet records valid; new records use array/linked model
- **Rollback**: Feature flag

### General Rollback Strategy
- All phases are additive (no destructive schema changes)
- Feature flags recommended for Phases 4 and 6
- No Terraform changes required for Phases 1-5
- Phase 6 may require a new GSI if search/filter needs server-side support

---

## 14. Specific Files/Functions That Would Need to Change

### Phase 1: Fix Duplicate Display

| File | Function/Section | Change |
|------|-----------------|--------|
| `src/backend/handlers/admin_handler.py` | GET /admin/requests (status=ALL scan) | Add filter to exclude JOB# records OR add `record_type` field |
| `web/src/components/AdminDashboard.jsx` | `fetchAllData()` / `visibleRecords` memo | Deduplicate by `request_id` or filter `entity_type !== 'JOB'` |
| `web/src/components/AdminDashboard.jsx` | `isRequestLikeRecord()` | Optionally exclude JOB# from request list view |

### Phase 2: Fix Cascade Consistency

| File | Function/Section | Change |
|------|-----------------|--------|
| `src/backend/handlers/review_handler.py` | Status update section | Ensure JOB cascade covers all transitions including CANCELLED |
| `src/backend/handlers/cancellation_handler.py` | `handle_admin_decision()` | Add JOB record update on CANCELLED decision |
| `src/backend/handlers/assignment_handler.py` | Worker assignment | Already cascades; verify rollback path |
| `src/backend/handlers/job_handler.py` | Job creation | Copy `end_date` from request |

### Phase 3: Intake Form Enhancements

| File | Function/Section | Change |
|------|-----------------|--------|
| `web/src/components/IntakeForm.jsx` | Step 2 (Schedule) | Multi-select visit_window, preferred_sitter dropdown |
| `web/src/components/IntakeForm.jsx` | Step 3 (Pets) | Structured per-pet fields with add/remove |
| `web/src/components/IntakeForm.jsx` | Step 3 (Pets) | Vet & emergency contact fields |
| `src/backend/handlers/intake_handler.py` | Record creation | Accept new fields, store as structured data |
| `web/src/components/IntakeForm.css` | Styling | New field layouts |

### Phase 4: Client Profile Automation

| File | Function/Section | Change |
|------|-----------------|--------|
| `src/backend/handlers/review_handler.py` | APPROVED transition | Auto-create client profile if not exists |
| `src/backend/handlers/intake_handler.py` | Client resolution | Match by email to existing profiles |
| `src/backend/handlers/admin_handler.py` | Client management | Add "Create from Intake" action |

### Phase 5: Record Editability

| File | Function/Section | Change |
|------|-----------------|--------|
| `web/src/components/CareCard.jsx` | Quote/Payment section | Add inline edit controls |
| `web/src/components/CareCard.jsx` | Scheduling/Staff tab | Add staff picker dropdown |
| `web/src/api/client.js` | API calls | May need new endpoints or use existing updatePet |

### Phase 6: Client Management Enhancements

| File | Function/Section | Change |
|------|-----------------|--------|
| `web/src/components/AdminDashboard.jsx` | Client Management view | Add search, filter, sort, export |
| `src/backend/handlers/admin_handler.py` | GET /admin/clients | Add query params for search/filter |
| `src/backend/handlers/pet_handler.py` | Pet CRUD | Support multiple pets per client with structured fields |
| `web/src/components/CareCard.jsx` | Pet display | Multi-pet selector/tabs |

### Phase 7: Status Recovery

| File | Function/Section | Change |
|------|-----------------|--------|
| `web/src/components/AdminDashboard.jsx` | Data Issues view actions | Add "Recover to Approved" / "Recover to Pending" buttons |
| `src/backend/handlers/admin_handler.py` | POST /admin/requests | Already supports PENDING_REVIEW/APPROVED as action targets |
| New utility script | Orphan detection | Scan for JOB records without valid REQ parent |

---

## Summary of Key Findings

1. **The duplicate rows are the REQ record and its child JOB record both appearing in the same list view.** This is not a data corruption issue — it's a display/filtering issue.

2. **Cancel affecting both records is by design** — the review_handler cascades status to linked JOB records. However, the cancellation_handler does NOT cascade, creating inconsistency.

3. **Records appearing in Data Issues** is caused by the ASSIGNED→APPROVED rollback removing `worker_id` from one record but not the other, leaving a JOB in ASSIGNED without a worker.

4. **Recovery from terminal states IS supported** by the transition matrix but the UI only exposes "Reopen to Pending Review" — not direct recovery to Approved/Booked.

5. **No child visit instances are created** — the system treats multi-day bookings as a single record. The appearance of "expansion" is actually the REQ+JOB dual-record pattern.
