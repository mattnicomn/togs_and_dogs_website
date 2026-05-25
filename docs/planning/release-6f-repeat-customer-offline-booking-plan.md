# Release 6F: Repeat Customer / Offline Client Booking Flow — Plan

## Status: ✅ DEPLOYED & PRODUCTION VALIDATED (2026-05-22)

**Key Commits:**
- `8fa35b3` — Planning doc
- `6415b7c` — Backend implementation
- `4b948b3` — Frontend + admin pet list fix
- `3934ef5` — Terraform GET /admin/pets route

**Deployment:** Backend (9 Lambdas) + Frontend (S3/CloudFront) + Terraform (new API Gateway route)
**Validation:** Direct Lambda smoke tests passed — role auth, tenant isolation, pet listing all confirmed

**Follow-up:** Verify `terraform plan` returns "No changes" to confirm full state alignment.

## Objective
Allow admin/owner to create visit bookings on behalf of existing clients directly from the Admin Dashboard, supporting offline/non-tech-savvy clients without requiring Cognito login or the public intake form.

## Current State (As Implemented)

### Request Creation Paths
| Path | Endpoint | Auth | Workflow Type | Who Uses It |
|------|----------|------|--------------|-------------|
| Public intake form | `POST /requests` | None | CUSTOMER_INTAKE | New clients via website |
| Client portal | `POST /client/requests` | Client role | VISIT_BOOKING | Returning clients with portal access |
| **Admin-created (NOT YET BUILT)** | — | Admin/Owner | VISIT_BOOKING | Staff booking for offline clients |

### Required Fields for Request Creation
- `client_name` (string, required)
- `client_email` (string, required)
- `start_date` (string, required)
- `pet_names` (string, required — or `pets[]` array)
- `client_id` (UUID — auto-generated or resolved from profile)
- `workflow_type` (set by code path, not user input)

### Client Profile Data Model
```
PK: COMPANY#{company_id}
SK: CLIENT#{client_id}
Fields: client_id, display_name, email, phone, address, emergency_contact,
        notes, is_active, portal_enabled, cognito_sub, cognito_status,
        intake_request_ids[], latest_request_id, request_count
```

### Pet Data Model
```
PK: PET#{pet_id}
SK: CLIENT#{client_id}
Fields: pet_id, client_id, name, breed, species, age, care_instructions,
        feeding_notes, medication_notes, behavior_notes, is_active,
        meet_and_greet_completed/required, quote_amount, payment_status
```

---

## Target: Admin-Created Booking Flow

### User Story
As an admin/owner, I want to create a visit booking for an existing client from the Admin Dashboard, so that I can serve offline/non-tech-savvy clients without requiring them to use the website.

### Workflow
1. Admin clicks "+ New Visit" in the Admin Dashboard
2. Admin selects an existing client from Client Management (searchable dropdown)
3. System auto-populates: client_name, client_email, client_phone, client_id
4. System shows the client's existing pets (selectable)
5. Admin fills in: service type, start date, end date (optional), visit window, notes
6. Admin submits → creates a VISIT_BOOKING request
7. Request enters the normal workflow at APPROVED status (admin is creating it, no review needed)
8. JOB record is created automatically (same as current approval flow)
9. Admin can immediately assign a worker from the request list
10. Notifications fire normally (STAFF_ASSIGNED, VISIT_SCHEDULED when assigned)

### Permission Model
| Role | Can Create Bookings? | Rationale |
|------|---------------------|-----------|
| Owner | ✅ Yes | Full operational control |
| Admin | ✅ Yes | Day-to-day booking management |
| Staff | ❌ No | Staff should not create bookings — only view/manage assigned visits |
| Client | ❌ No (use portal) | Clients use the client portal or public form |

### Duplicate Prevention Strategy
1. Admin selects from EXISTING client profiles — no new profile created
2. `client_id` comes from the selected CLIENT# record (not auto-generated)
3. `client_email` comes from the selected profile (not manually typed)
4. No `auto_create_or_link_client_profile` runs (that's only for CUSTOMER_INTAKE approval)
5. If the client doesn't have a profile yet, admin creates one first via Client Management

### How Pets/CareCards Should Be Handled
1. When admin selects a client, fetch their existing PET# records
2. Admin selects which pet(s) the booking is for (checkboxes)
3. Selected pet_ids are stored on the REQ record's `pet_ids[]` array
4. `pet_names` is auto-generated from selected pet names (same as intake form)
5. Admin can optionally add a new pet inline (reuses existing createPet API)
6. CareCard loads normally after booking is created

---

## Recommended API Design

### Option A: Reuse Intake Handler (Recommended)
Add a new code path to `intake_handler.py` for admin-created bookings:

```python
# Detect admin-created booking
if body.get('source') == 'admin_created' and role in ['owner', 'admin']:
    workflow_type = WorkflowType.VISIT_BOOKING
    # Skip validation that requires portal access
    # Use provided client_id directly (from selected profile)
    # Set initial status to APPROVED (no review needed)
```

**Endpoint:** `POST /requests` with `source: 'admin_created'` flag
**Advantages:** Reuses existing validation, notification, and record creation logic
**Auth:** Requires owner/admin role (checked via Cognito authorizer)

### Option B: New Dedicated Endpoint
Create `POST /admin/bookings` with a new handler.
**Disadvantage:** Duplicates record creation logic, more code to maintain.

**Recommendation:** Option A — minimal code, reuses existing infrastructure.

### Request Body (Admin-Created)
```json
{
  "source": "admin_created",
  "client_id": "client_abc123",
  "client_name": "Jane Smith",
  "client_email": "jane@example.com",
  "client_phone": "555-123-4567",
  "pet_names": "Buddy, Max",
  "pet_ids": ["pet_uuid1", "pet_uuid2"],
  "service_type": "WALK_30MIN",
  "start_date": "2026-06-15",
  "end_date": "2026-06-15",
  "visit_windows": ["MIDDAY"],
  "details": "Back gate code: 1234",
  "initial_status": "APPROVED"
}
```

### Response
Same as current intake handler response — returns the created request record.

---

## Frontend Changes

### New UI: "+ New Visit" Button
- Location: Admin Dashboard header or stat cards area (visible to owner/admin only)
- Opens a modal/drawer with the booking form

### Booking Form Fields
| Field | Source | Required |
|-------|--------|----------|
| Client | Searchable dropdown from clientList | ✅ |
| Pet(s) | Checkboxes from selected client's pets | ✅ (at least one) |
| Service Type | Dropdown (WALK_30MIN, DROPIN_1HR, etc.) | ✅ |
| Start Date | Date picker | ✅ |
| End Date | Date picker | Optional |
| Visit Window | Multi-select (MORNING, MIDDAY, etc.) | Optional |
| Notes/Details | Textarea | Optional |
| Preferred Sitter | Staff dropdown | Optional |

### Auto-Population
When admin selects a client:
- `client_name`, `client_email`, `client_phone` auto-fill from profile
- Pet list loads from that client's PET# records
- `client_id` is set from the profile's `client_id` field

---

## Backend Changes

### `src/backend/handlers/intake_handler.py`

**Admin-created booking path (triggered by `source: 'admin_created'`):**

1. **Authorization:** Verify `role in ['owner', 'admin']` — reject staff/client/unknown
2. **Source detection:** Check `body.get('source') == 'admin_created'`
3. **Tenant isolation:** Resolve `company_id` from authenticated admin's token via `get_current_company_id(event)`. Verify the selected `client_id` belongs to the same company (query CLIENT# record and compare `company_id`). Block cross-tenant booking creation.
4. **Client validation:** Require `client_id` from body (must be an existing CLIENT# profile). Do NOT auto-generate client_id.
5. **Pet validation:** Require `pet_ids` or `pet_names` from body. Pets must belong to the selected client.
6. **Skip portal checks:** Do not call `resolve_client_identity` or check `portal_enabled`
7. **Set workflow:** `workflow_type = VISIT_BOOKING`
8. **Set status:** `status = APPROVED` (admin is creating it, no review needed)
9. **Skip notification:** Do NOT trigger `REQUEST_RECEIVED` (admin already knows)
10. **Invoke JOB Lambda:** Call `JOB_FUNCTION_NAME` asynchronously (same pattern as `review_handler.py` approval path):
    ```python
    lambda_client = boto3.client('lambda')
    job_fn_name = os.environ.get('JOB_FUNCTION_NAME')
    if job_fn_name:
        lambda_client.invoke(
            FunctionName=job_fn_name,
            InvocationType='Event',
            Payload=json.dumps({"request_id": request_id, "client_id": client_id})
        )
    ```
11. **Google Calendar sync:** Invoke the same `sync_calendar_event` pattern used during approval to create a placeholder calendar event immediately:
    ```python
    from common.google_calendar import sync_calendar_event
    calendar_result = sync_calendar_event(item)
    if calendar_result and calendar_result.get('event_id'):
        # Persist google_event_id on the REQ record
        table.update_item(...)
    ```
12. **Audit trail:** Store `created_by`, `source: 'admin_created'`, `admin_created_at` fields on the REQ record

### Critical Integration Requirements (AG-Identified)

| Requirement | Rationale | Implementation |
|-------------|-----------|----------------|
| Manual JOB Lambda trigger | Admin-created APPROVED bookings bypass review_handler which normally triggers JOB creation | intake_handler must invoke JOB_FUNCTION_NAME directly |
| Google Calendar placeholder sync | Keeps Admin Scheduler and Google Calendar aligned from creation | intake_handler must call sync_calendar_event on creation |
| Tenant/company isolation | Prevent cross-tenant booking creation | Validate client_id belongs to admin's company_id |
| Pet requirement guardrail | Bookings without pets are invalid | Require at least one pet_id or pet_name |

### No Changes Needed
- `admin_handler.py` — no changes (client/pet CRUD already exists)
- `pet_handler.py` — no changes (pet CRUD already exists)
- `client_profile.py` — no changes (auto-profile only runs on CUSTOMER_INTAKE)
- Notification templates — no changes (existing templates work for assignment/scheduling)
- `review_handler.py` — no changes (admin-created bookings skip review)

---

## Frontend Changes

### UX Guardrails

**Client with no pets:**
- If the selected client has zero active PET# records, block form submission
- Show message: "This client has no pets on file. Please add a pet/CareCard first."
- Optionally provide a link/button to open the CareCard creation flow for that client

**Required field validation:**
- Client selection required
- At least one pet selected
- Service type required
- Start date required
- Block submit until all required fields are filled

---

## Complete Backend Scope Checklist (AG-Approved)

The admin-created booking path in `intake_handler.py` must implement ALL of the following:

- [ ] `source: "admin_created"` detection
- [ ] Owner/admin authorization (reject staff/client/unknown)
- [ ] Existing `client_id` required (from selected CLIENT# profile)
- [ ] Existing pet selection required (`pet_ids` or `pet_names`)
- [ ] `status = APPROVED`
- [ ] `workflow_type = VISIT_BOOKING`
- [ ] Skip `REQUEST_RECEIVED` notification
- [ ] Invoke `JOB_FUNCTION_NAME` asynchronously (Lambda invoke, same as review_handler)
- [ ] Invoke/sync Google Calendar placeholder (`sync_calendar_event`)
- [ ] Persist `google_event_id` on REQ record if calendar sync succeeds
- [ ] `created_by` + `source` + `admin_created_at` audit markers
- [ ] `company_id` validation (client must belong to admin's tenant)
- [ ] Non-blocking error handling for JOB Lambda and Calendar (fail-safe)

---

## Phased Implementation Plan

### Phase 1: Backend — Admin-Created Booking Path (~3-4 hours)
1. Add `source: 'admin_created'` detection to intake_handler
2. Verify owner/admin authorization
3. Validate tenant isolation (client belongs to admin's company)
4. Require existing client_id and pet selection
5. Set workflow_type = VISIT_BOOKING, status = APPROVED
6. Skip REQUEST_RECEIVED notification
7. Invoke JOB_FUNCTION_NAME asynchronously (mirror review_handler pattern)
8. Invoke Google Calendar sync_calendar_event (create placeholder)
9. Persist google_event_id on REQ record
10. Add `created_by`, `source`, `admin_created_at` audit fields
11. Add backend tests

### Phase 2: Frontend — New Visit Modal (~4-6 hours)
1. Add "+ New Visit" button (owner/admin only)
2. Create booking modal with searchable client selector
3. Load pets on client selection
4. Block submission if client has no pets (show clear message)
5. Service type, date, window, notes, preferred sitter fields
6. Required field validation before submit
7. Submit via `submitRequest` with `source: 'admin_created'`
8. Refresh request list after creation
9. Success notification

### Phase 3: Polish & Validation (~1-2 hours)
1. Preferred sitter pre-selection
2. Inline "Add Pet" if client has no pets
3. AG production validation
4. Release notes and docs

---

## AG Validation Plan

### Phase 1 (Backend)
1. Call `POST /requests` with `source: 'admin_created'` + admin auth token
2. Verify request created with `workflow_type: VISIT_BOOKING`, `status: APPROVED`
3. Verify JOB record created
4. Verify no REQUEST_RECEIVED notification sent
5. Verify `created_by` field set

### Phase 2 (Frontend)
1. Log in as admin → click "+ New Visit"
2. Select existing client → verify auto-population
3. Select pet(s) → verify pet_names generated
4. Fill service/date → submit
5. Verify request appears in Request List as "Approved / Ready to Schedule"
6. Assign worker → verify STAFF_ASSIGNED + VISIT_SCHEDULED emails fire

---

## Risks / Blockers

| Risk | Mitigation |
|------|-----------|
| Admin creates booking for wrong client | Client selector shows email + name for disambiguation |
| Duplicate bookings for same date | No automatic prevention — admin responsibility (same as current) |
| Client has no pets yet | Frontend blocks submission with clear "Add pet first" message |
| JOB creation Lambda timing | Same async pattern as current approval — may need brief delay before assignment |
| Google Calendar refresh token expired | Calendar sync is non-blocking (try/catch) — booking still created |
| Cross-tenant booking attempt | Backend validates client_id belongs to admin's company_id |
| JOB_FUNCTION_NAME env var missing | Graceful skip with warning log (same as review_handler) |

## What Should Remain Deferred
- Client-portal-initiated repeat bookings (requires identity resolution fix)
- Recurring/scheduled bookings (weekly walks, etc.)
- Booking templates/presets
- Client self-service rescheduling
- Payment/invoice integration with booking creation
- Staff-initiated bookings (keep admin/owner only for now)
