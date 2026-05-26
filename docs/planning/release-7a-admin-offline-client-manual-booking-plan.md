# Release 7A: Admin Offline Client / Manual Booking Workflow — Plan

## Objective
Ensure the complete end-to-end workflow for managing offline/non-tech-savvy clients is fully operational, documented, and validated — from client profile creation through booking, assignment, scheduling, and completion.

---

## Current State: What Already Exists

### ✅ Already Implemented

| Capability | Release | Status |
|-----------|---------|--------|
| Create client profile WITHOUT Cognito | Pre-existing | `POST /admin/clients` creates profile with `cognito_status: "not_linked"`, `portal_enabled: false` |
| Create client profile WITH Cognito | Pre-existing | `POST /admin/clients/onboard` creates Cognito user + profile |
| Admin-created booking for existing client | Release 6F | `POST /requests` with `source: "admin_created"` — creates APPROVED VISIT_BOOKING |
| "+ New Visit" modal in Admin Dashboard | Release 6F | Client selector, pet selector, service/date fields |
| Admin pet listing for selected client | Release 6F | `GET /admin/pets?clientId={id}` |
| JOB creation on admin booking | Release 6F | Async Lambda invoke on APPROVED |
| Google Calendar sync on admin booking | Release 6F + 6G | All-day fallback, retry, health check |
| Notification sending for all events | Releases 6A-6B | REQUEST_RECEIVED skipped for admin-created; STAFF_ASSIGNED/VISIT_SCHEDULED fire on assignment |
| Notification ledger | Release 6I | Records all send outcomes |
| Webhook suppression | Release 6I | Auto-suppresses bounced/complained addresses |
| Protected admin accounts | Release 6H | Prevents accidental profile creation for admin emails |
| Filter integrity / safe delete | Release 6D | Trash guardrails, purge safety |

### ❓ Gaps / Questions to Resolve

| Gap | Description | Priority |
|-----|-------------|----------|
| Pet creation from New Visit modal | Modal shows existing pets but cannot create a new pet inline | Medium |
| Client creation from New Visit modal | Must select existing client — cannot create inline | Medium |
| Quote/approval flow for admin bookings | Currently skips to APPROVED — no quote step | Low (admin decides) |
| Offline client without email | Current profile creation requires email | Medium |
| Notification behavior for no-email clients | If client has no email, notifications skip silently | Low (by design) |
| Booking without pet | Modal blocks submission without pet — correct? | Confirmed correct |
| Admin-created booking audit visibility | `source: admin_created` is stored but not surfaced in UI | Low |

---

## Questions Answered

### 1. Can we already create offline client profiles without Cognito?
**YES.** `POST /admin/clients` creates a profile with:
- `cognito_status: "not_linked"`
- `portal_enabled: false`
- No Cognito user created
- Client can be managed entirely through Admin Dashboard

### 2. Can we already create bookings for those offline clients?
**YES.** Release 6F's `_handle_admin_created_booking()` in `intake_handler.py`:
- Requires existing `client_id` (from Client Management)
- Creates as `APPROVED` / `VISIT_BOOKING`
- Triggers JOB creation + Calendar sync
- Skips REQUEST_RECEIVED notification (admin already knows)
- Frontend "+ New Visit" modal provides the UI

### 3. Should admin-created bookings start as APPROVED, PENDING_REVIEW, or ADMIN_CREATED?
**Current: APPROVED.** This is correct for the offline client use case because:
- Admin is creating the booking — no review needed
- JOB record is created immediately
- Worker can be assigned immediately
- If a quote/review step is needed, admin can manually set status before creating

**Recommendation:** Keep APPROVED as default. Do NOT introduce a new status.

### 4. How should notifications behave for offline clients?
**Current behavior (correct):**
- If client has email → notifications send normally (VISIT_SCHEDULED, etc.)
- If client has no email → resolver returns empty recipients → notification skipped silently
- Admin always gets REQUEST_RECEIVED for public intakes (not admin-created)
- Staff gets STAFF_ASSIGNED when worker is assigned

**No change needed.** The system gracefully handles missing email.

### 5. How should Google Calendar behave for admin-created bookings?
**Current behavior (correct):**
- Calendar sync fires on booking creation (Release 6F)
- All-day event if no `scheduled_time` (Release 6G Phase 2)
- Retry on transient failures (Release 6G Phase 4)
- Health check validates token daily (Release 6G Phase 3)

**No change needed.**

### 6. What is the safest phased implementation path?
Since the core workflow already works, Release 7A should focus on **UX polish and gap closure**, not new backend architecture.

---

## Recommended Phases

### Phase 1: Validate Existing End-to-End Flow (~1-2 hours)
**Scope:** AG performs a complete production walkthrough of the offline client workflow.

**Steps:**
1. Create a new client profile (profile-only, no Cognito) via Client Management
2. Add a pet to that client via CareCard
3. Create a booking via "+ New Visit" modal
4. Verify booking appears as APPROVED in Request List
5. Assign a worker
6. Verify STAFF_ASSIGNED + VISIT_SCHEDULED notifications fire
7. Verify Google Calendar event created
8. Cancel the booking
9. Verify VISIT_CANCELLED notification fires
10. Clean up test data

**If this passes:** The offline client workflow is already complete. Remaining phases are UX polish.

### Phase 2: Inline Pet Creation from New Visit Modal (~2-3 hours)
**Scope:** Allow admin to create a new pet directly from the New Visit modal if the selected client has no pets.

**Implementation:**
- Add "Add Pet" button/section in the modal when `newVisitClientPets.length === 0`
- Reuse existing `createPet` API call
- After pet creation, refresh pet list and auto-select the new pet
- Frontend-only change (backend pet creation already exists)

### Phase 3: Optional Email for Offline Clients (~1-2 hours)
**Scope:** Allow client profile creation without email for truly offline clients.

**Current blocker:** `POST /admin/clients` requires email (`if not display_name or not email: return bad_request`)

**Implementation:**
- Make email optional in the profile-only creation path
- Generate a placeholder or leave blank
- Notifications gracefully skip when email is missing (already handled)
- Admin-created bookings use `client_name` from profile regardless of email

### Phase 4: Inline Client Creation from New Visit Modal (Deferred)
**Scope:** Allow admin to create a new client directly from the New Visit modal.

**Why deferred:** The current flow (create client in Client Management → then create booking) works. Inline creation adds complexity and potential for duplicate profiles.

---

## Data Model Impact
**None.** All existing data models support the offline client workflow:
- CLIENT# records with `cognito_status: "not_linked"` ✅
- REQ# records with `source: "admin_created"` ✅
- PET# records linked via `SK: CLIENT#{client_id}` ✅
- JOB# records created via async Lambda ✅
- Notification ledger records all outcomes ✅

---

## UX Flow (Current — Already Working)

```
Admin Dashboard
  → Client Management → "+ Create Profile" (profile-only, no Cognito)
  → Client created with display_name, email (optional in Phase 3), phone
  → CareCard → Add Pet for that client
  → "+ New Visit" button → Select client → Select pet(s)
  → Fill service type, date, window, notes
  → Submit → Booking created as APPROVED
  → Request List shows new booking
  → Assign worker → STAFF_ASSIGNED + VISIT_SCHEDULED emails fire
  → Google Calendar event created
  → Complete/Cancel as normal
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Duplicate client profiles | Low | Confusion | Email uniqueness check already exists |
| Booking without pet | None | Blocked by modal | Modal requires pet selection |
| Missing email → notification failure | None | Graceful skip | Resolver returns empty recipients |
| Calendar sync failure | Low | Non-blocking | Retry + health check (6G) |

---

## Test & Validation Strategy

### Phase 1 (AG Walkthrough)
- Complete end-to-end offline client workflow in production
- Verify all notifications, calendar, ledger entries
- Document any UX friction points

### Phase 2 (Inline Pet Creation)
- `npm run build` passes
- Create booking for client with no pets → "Add Pet" option appears
- After adding pet → pet appears in selector
- Booking creation succeeds with new pet

### Phase 3 (Optional Email)
- `py -m py_compile admin_handler.py`
- Create client without email → succeeds
- Create booking for no-email client → succeeds
- Notifications gracefully skip (no error)

---

## Rollback
No new infrastructure or data model changes. All phases are additive UX improvements. Rollback = revert the specific frontend/backend change.

---

## What AG Should Implement First
**Phase 1 validation only.** If the existing workflow passes end-to-end, the offline client feature is already complete and Release 7A becomes a documentation/polish release rather than a feature build.

---

## Files Likely Involved

| File | Phase | Change |
|------|-------|--------|
| `web/src/components/AdminDashboard.jsx` | 2 | Inline pet creation in New Visit modal |
| `src/backend/handlers/admin_handler.py` | 3 | Make email optional for profile-only creation |
| `docs/operations/` | All | Operational guide for offline client workflow |

---

## Items Explicitly Deferred

| Item | Reason |
|------|--------|
| Inline client creation from New Visit modal | Adds complexity; current flow works |
| Quote/approval step for admin bookings | Admin decides pricing offline |
| SMS notifications for offline clients | Different channel, different scope |
| Client portal access for offline clients | Contradicts "offline" use case |
| Recurring/scheduled bookings | Separate feature |
| Bulk booking creation | Low priority |
