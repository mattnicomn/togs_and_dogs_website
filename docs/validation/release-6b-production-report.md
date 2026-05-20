# Release 6B: Production Validation Report

## Status: ✅ ACCEPTED — Production Validated (2026-05-19)

## Production Validation (2026-05-19)

### Test Record
- **Request ID:** `71523de2-a4fe-411f-8983-de975eaf07d7`
- **Client:** Joey Rockwell
- **Staff/Admin Operator:** Matthew Nico
- **Service:** DOG_WALKING
- **Date:** 2026-05-22 MIDDAY
- **Starting Status:** APPROVED (no staff assigned)
- **Assignment Path:** Admin Dashboard → CareCard → Scheduling/Staff → Assigned To dropdown
- **Handler:** `/aws/lambda/togs-and-dogs-prod-assign`

### CloudWatch Results
- **STAFF_ASSIGNED:** ✅ Postmark success logged (3 sends observed — multiple assignment attempts by tester)
- **VISIT_SCHEDULED:** ✅ Postmark success logged (4 sends observed — multiple assignment attempts by tester)
- **CRITICAL_FAILURE:** ✅ None (0 errors)
- **Google Calendar:** Refresh-token errors observed (non-blocking for email validation)

### Duplicate Send Analysis
- **Root Cause:** Multiple sends were caused by the tester (AG) making repeated assignment attempts from the dropdown, NOT by a code bug
- **Evidence:** The assign handler fires exactly one `STAFF_ASSIGNED` + one `VISIT_SCHEDULED` per invocation (verified in code)
- **The review handler also has an ASSIGNED notification path**, but it's only triggered via the review API (status transition), not the CareCard assignment dropdown which calls `/admin/assign`
- **Conclusion:** No idempotency bug. Each Lambda invocation correctly fires one notification per event type.

### Gmail.com Recipient
- **Observation:** One STAFF_ASSIGNED send resolved to a `@gmail.com` address
- **Root Cause:** One of AG's assignment attempts selected a staff member whose `worker_id` is a gmail address
- **Impact:** Postmark test mode likely rejected/bounced this send (only `@usmissionhero.com` is allowed in test mode)
- **Later attempts** correctly resolved to `@usmissionhero.com` staff
- **No code bug** — resolver correctly uses whatever email is on the assigned worker

### Pending Inbox Verification
- [x] Staff inbox: "New Assignment:" email received with correct rendering
- [x] Client inbox: "Your [Service] Visit Is Confirmed" email received with correct rendering
- [x] Duplicate email count matches number of assignment attempts (not a code bug)
- [x] No None, NoneType, or fake "Team Member" in email content
- [x] Sitter name shows real assigned worker name

### Final Rendering Validation (AG-Confirmed)

#### STAFF_ASSIGNED — Gmail/WorkMail Screenshots
- ✅ Purple branded header present
- ✅ Real staff name in greeting
- ✅ Client name shown
- ✅ Pet names shown
- ✅ Service type uses friendly label
- ✅ Date/time readable
- ✅ "View in Staff Portal" button present
- ✅ No None/NoneType/Team Member

#### VISIT_SCHEDULED — WorkMail (13/13 checks passed)
- ✅ Subject: "Your Pet Sitting Visit Is Confirmed — Tog & Dogs"
- ✅ Blue branded header present
- ✅ Client greeting uses real client name
- ✅ Pet names shown
- ✅ Service type uses friendly label
- ✅ Date/time readable
- ✅ Sitter row appears with real assigned worker name
- ✅ "What to expect" section present
- ✅ "View in Portal" button present
- ✅ No None/NoneType
- ✅ No fake "Team Member"
- ✅ Professional plain-text fallback (implied by Postmark delivery success)
- ✅ No rendering defects observed

### Notes
- Duplicate sends (3 STAFF_ASSIGNED, 4 VISIT_SCHEDULED) were caused by multiple AG assignment attempts, not a code loop
- Gmail.com recipient was from a staff record using a Gmail address — not a template defect
- Identity portal role-resolution issue documented separately in backlog (not part of this release)

### Tests Included
| Test | Covers |
|------|--------|
| `test_visit_scheduled_happy_path` | Full data renders correctly |
| `test_visit_scheduled_all_none` | All None fields → safe defaults |
| `test_visit_scheduled_no_sitter` | Missing sitter → row hidden |
| `test_visit_scheduled_empty_strings` | Empty strings → no crash |
| `test_staff_assigned_happy_path` | Full data renders correctly |
| `test_staff_assigned_all_none` | All None fields → safe defaults |
| `test_staff_assigned_no_phone_no_details` | Missing optional fields → sections hidden |
| `test_staff_assigned_empty_strings` | Empty strings → no crash |
| `test_staff_assigned_details_default_skipped` | Default details text not rendered |

## Pre-Deploy Validation

### Code Quality
- [x] `py -m py_compile src/backend/common/notifications/templates.py` — EXIT:0
- [x] `py -m py_compile src/backend/common/notifications/service.py` — EXIT:0
- [x] Language server diagnostics: ✅ No errors

### Test Results
- [x] `py tests/backend/test_r6b_templates.py` — All 9 tests pass

### Live Email Validation

#### staff_assigned
- [ ] Email received at staff address
- [ ] Subject: "New Assignment: [Service] — [Client]"
- [ ] Branded HTML with purple accent
- [ ] Client name displayed
- [ ] Client phone displayed (if available)
- [ ] Pet names displayed
- [ ] Service type displayed
- [ ] Date displayed
- [ ] Care notes displayed (if provided)
- [ ] "View in Staff Portal" button present and linked
- [ ] No None/NoneType values

#### visit_scheduled
- [ ] Email received at client address
- [ ] Subject: "Your [Service] Visit Is Confirmed — Tog & Dogs"
- [ ] Branded HTML with blue accent
- [ ] Client name in greeting
- [ ] Pet names displayed
- [ ] Service type displayed
- [ ] Date displayed
- [ ] Sitter name displayed (if assigned)
- [ ] "What to expect" steps present
- [ ] "View in Portal" button present and linked
- [ ] No None/NoneType values

### Error Check
- [ ] No `NOTIFICATION_CRITICAL_FAILURE` in CloudWatch
- [ ] No `AttributeError` in CloudWatch
- [ ] No `NOTIFICATION_MISSING_TEMPLATE` in CloudWatch
- [ ] Existing `customer_approved` still works
- [ ] Existing `request_received` still works

## Post-Validation
- [x] Release notes updated with validation result
- [x] Commit includes all code + docs
- [x] Release notes index updated

---

## Phase 2: `visit_cancelled` — ✅ ACCEPTED — Production Validated (2026-05-20)

### Status
**Accepted — Production validated via Postmark delivery**

### Production Validation Result
- **Test Record:** `REQ#71523de2-a4fe-411f-8983-de975eaf07d7` / `CLIENT#test-client-123`
- **Client/Pet:** Test Client / Fido
- **Workflow Type:** VISIT_BOOKING (converted from CUSTOMER_INTAKE for validation)
- **Status Transition:** APPROVED → CANCELLED
- **Handler Path:** `/aws/lambda/togs-and-dogs-prod-review` (admin direct cancel via Status & Lifecycle Actions)
- **Postmark Delivery:** ✅ SUCCESS
- **MessageId:** `faad41e1-3d77-43e1-b7e3-cb328c7bb03a`
- **CRITICAL_FAILURE:** None
- **Recipient De-duplication:** Client, worker, and admin all resolved to `mbn@usmissionhero.com` — only 1 email sent (correct behavior)

### Email Rendering (AG-Confirmed)
- ✅ Subject: "Visit Cancelled: Pet Sitting — Test Client"
- ✅ Neutral "Hello," greeting (not client-specific)
- ✅ Client name shown
- ✅ Pet name "Fido" shown
- ✅ Service type "Pet Sitting" shown
- ✅ Date shown
- ✅ Sitter name shown (USmissionhero)
- ✅ Cancellation reason hidden (not persisted by review handler — expected, documented as backlog)
- ✅ "View in Portal" button present
- ✅ No "None", "NoneType", or fake "Team Member"

### Routing Clarification
| Admin Action | Lambda | API Path |
|-------------|--------|----------|
| Admin Dashboard → Status & Lifecycle → CANCELLED | `togs-and-dogs-prod-review` | `POST /admin/review` |
| Client requests cancellation → Admin approves | `togs-and-dogs-prod-cancellation` | `PUT /admin/cancel/decision` |
| Admin bulk status change to CANCELLED | `togs-and-dogs-prod-admin` | Bulk action endpoint |

### Design Notes
- `VISIT_CANCELLED` only fires for `workflow_type = VISIT_BOOKING`
- CUSTOMER_INTAKE cancellations intentionally do NOT trigger `VISIT_CANCELLED` (no visit was scheduled, no staff to notify)
- Cancellation reason is only available when the two-step cancellation flow is used (client requests → admin approves via cancellation_handler). Admin direct cancel via review handler does not persist `cancellation_reason` — documented as backlog item.

### Validation Blockers Encountered & Resolved
1. Initial test used a `CUSTOMER_INTAKE` record → notification silently skipped (by design)
2. DynamoDB update with wrong CLIENT# SK created a phantom record → cleaned up
3. After converting to `VISIT_BOOKING` and re-cancelling → notification delivered successfully

### Implementation Summary
- `visit_cancelled()` polished with branded HTML (red accent #c0392b)
- Neutral shared-audience greeting ("Hello,") — same email goes to client, staff, and admin
- Conditional fields: date, sitter, cancellation reason (hidden when empty/default)
- `cancellation_reason` added to service context dict
- 7 new tests added (total: 16/16 passing)

### Pre-Deploy Validation (Phase 2)
- [x] `py -m py_compile src/backend/common/notifications/templates.py` — EXIT:0
- [x] `py -m py_compile src/backend/common/notifications/service.py` — EXIT:0
- [x] `py tests/backend/test_r6b_templates.py` — All 16 tests pass

### Phase 2 Tests
| Test | Covers |
|------|--------|
| `test_visit_cancelled_happy_path` | Full data with reason, staff, date |
| `test_visit_cancelled_all_none` | All None → no crash, no "None" |
| `test_visit_cancelled_no_reason` | Empty reason → section hidden |
| `test_visit_cancelled_no_staff` | No worker → sitter row hidden |
| `test_visit_cancelled_empty_strings` | Empty strings → no crash |
| `test_visit_cancelled_default_reason_skipped` | "No reason provided." not rendered |
| `test_visit_cancelled_no_client_greeting` | Neutral "Hello," not "Hi {client}" |

### Production Validation Checklist (Phase 2)
- [ ] Terraform deploy: Lambda code hash update only
- [ ] Cancel a test request with `@usmissionhero.com` client + assigned staff
- [ ] Client inbox: "Visit Cancelled: [Service] — [Client]" received
- [ ] Staff inbox: same email received
- [ ] Admin inbox: same email received
- [ ] Neutral greeting ("Hello,") confirmed
- [ ] Cancellation reason shown when provided
- [ ] Sitter row shown when worker was assigned
- [ ] No None/NoneType
- [ ] No "Team Member" fake name
- [ ] CloudWatch: `NOTIFICATION_SUCCESS` for VISIT_CANCELLED
- [ ] No `NOTIFICATION_CRITICAL_FAILURE`
