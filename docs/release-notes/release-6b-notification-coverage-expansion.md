# Release 6B: Notification Coverage Expansion

## Overview
Polishes the remaining stub notification templates into production-quality branded emails, matching the style established in Release 6A.

## Phase 1: `visit_scheduled` + `staff_assigned` — ✅ Accepted (2026-05-19)

## Changes

### `visit_scheduled` — Client Notification
**Recipient:** Client email (gated by `NOTIFY_CLIENT_ON_SCHEDULED`)
**Trigger:** Worker assigned to a VISIT_BOOKING request (review_handler ASSIGNED transition, assignment_handler)

- Branded HTML with blue accent (scheduling/confirmation tone)
- Visit details table: service type, pet names, date/time
- Sitter name row (conditional — only shown when assigned)
- "What to expect" steps
- "View in Portal" CTA button
- Professional plain-text fallback
- All fields null-safe

### `staff_assigned` — Staff Notification
**Recipient:** Staff email (gated by `NOTIFY_STAFF_ON_ASSIGNMENT`)
**Trigger:** Same as visit_scheduled (fires alongside it)

- Branded HTML with purple accent (matching staff portal branding)
- Assignment details table: client name, phone (conditional), pet names, service, date
- Care notes section (conditional — only shown when details provided)
- "View in Staff Portal" CTA button
- Professional plain-text fallback
- All fields null-safe

### Service Context Enhancement
**File:** `src/backend/common/notifications/service.py`

Added to the template context dict:
- `worker_id` — assigned worker identifier
- `worker_name` — assigned worker display name (from `worker_name` or `assigned_to_name`)
- `portal_url` — from `NotificationConfig.PORTAL_URL`

These fields are available to all templates (not just the new ones).

## Template Color Scheme

| Template | Accent Color | Audience |
|----------|-------------|----------|
| `customer_approved` | Green (#27ae60) | Client |
| `visit_scheduled` | Blue (#2980b9) | Client |
| `request_received` | Orange (#e67e22) | Admin |
| `staff_assigned` | Purple (#8e44ad) | Staff |
| `visit_cancelled` | (stub — future) | Multi |
| `visit_time_changed` | (stub — dormant) | Client |

## Files Changed
- `src/backend/common/notifications/templates.py` — Polished `visit_scheduled()` and `staff_assigned()`
- `src/backend/common/notifications/service.py` — Added `worker_id`, `worker_name`, `portal_url` to context
- `tests/backend/test_r6b_templates.py` — 9 new tests covering null-safety and rendering

## Deployment
- Requires `terraform apply` (Lambda code hash update only)
- No env var changes, no new resources, no infrastructure changes
- Both templates fire on the same trigger (worker assignment), so a single test action validates both

## Validation Checklist
- [ ] `py -m py_compile` passes for templates.py and service.py
- [ ] `py tests/backend/test_r6b_templates.py` — all 9 tests pass
- [ ] `terraform plan` shows only Lambda source_code_hash updates
- [ ] `terraform apply` succeeds
- [ ] Assign a worker to a test VISIT_BOOKING request
- [ ] Staff email receives branded "New Assignment" email
- [ ] Client email receives branded "Visit Confirmed" email
- [ ] No `NOTIFICATION_CRITICAL_FAILURE` in CloudWatch
- [ ] No None/NoneType values in email content
- [ ] Existing `customer_approved` and `request_received` still work

## Rollback (Phase 1)
If issues occur with Phase 1 templates:
- Set `NOTIFY_CLIENT_ON_SCHEDULED = "false"` and/or `NOTIFY_STAFF_ON_ASSIGNMENT = "false"` in `locals.tf`
- `terraform apply`
- This disables the specific events without affecting approval or request-received emails

---

## Phase 2: `visit_cancelled` — ✅ Accepted (2026-05-20)

### `visit_cancelled` — Multi-Recipient Cancellation Notification
**Recipients:** Client + Staff + Admin (each gated by `NOTIFY_*_ON_CANCELLED` flags)
**Triggers:** `review_handler` (admin direct cancel via Status & Lifecycle Actions), `cancellation_handler` (two-step client request → admin approval), `admin_handler` (bulk status change)

**Important routing clarification:**
| Admin Action | Lambda | Path |
|-------------|--------|------|
| Admin Dashboard → Status & Lifecycle → CANCELLED | `togs-and-dogs-prod-review` | `POST /admin/review` with `status: CANCELLED` |
| Client requests cancellation → Admin approves | `togs-and-dogs-prod-cancellation` | `PUT /admin/cancel/decision` |
| Admin bulk status change to CANCELLED | `togs-and-dogs-prod-admin` | Bulk action endpoint |

**Design note:** `VISIT_CANCELLED` only fires for `workflow_type = VISIT_BOOKING`. CUSTOMER_INTAKE cancellations intentionally do not trigger this notification (no visit was scheduled, no staff to notify).

- Branded HTML with red accent (#c0392b — cancellation tone)
- **Neutral shared-audience greeting** ("Hello,") — does NOT address recipient as the client since the same email goes to client, staff, and admin
- Cancelled visit details table: client name, pet names, service type
- Date row (conditional — only shown when date exists)
- Assigned sitter row (conditional — only shown when a real worker was assigned)
- Cancellation reason section (conditional — only shown when meaningful, skips "No reason provided.")
- "View in Portal" CTA button (muted gray)
- Professional plain-text fallback
- All fields null-safe via `_safe()` helper

### Service Context Enhancement (Phase 2)
Added `cancellation_reason` to the template context dict in `service.py` (+1 line).

### Template Color Scheme (Updated)
| Template | Accent Color | Audience |
|----------|-------------|----------|
| `customer_approved` | Green (#27ae60) | Client |
| `visit_scheduled` | Blue (#2980b9) | Client |
| `request_received` | Orange (#e67e22) | Admin |
| `staff_assigned` | Purple (#8e44ad) | Staff |
| `visit_cancelled` | Red (#c0392b) | Client + Staff + Admin |
| `visit_time_changed` | (stub — dormant) | Client |

### Tests Added (Phase 2)
| Test | Validates |
|------|-----------|
| `test_visit_cancelled_happy_path` | Full data with reason, staff, date |
| `test_visit_cancelled_all_none` | All None → no crash, no "None" |
| `test_visit_cancelled_no_reason` | Empty reason → section hidden |
| `test_visit_cancelled_no_staff` | No worker → sitter row hidden |
| `test_visit_cancelled_empty_strings` | Empty strings → no crash |
| `test_visit_cancelled_default_reason_skipped` | "No reason provided." not rendered |
| `test_visit_cancelled_no_client_greeting` | Neutral "Hello," not "Hi {client}" |

### Local Validation (Phase 2)
- `py -m py_compile templates.py` → ✅ EXIT:0
- `py -m py_compile service.py` → ✅ EXIT:0
- `py tests/backend/test_r6b_templates.py` → ✅ All 16 tests PASSED

### Deployment (Phase 2)
- Requires `terraform apply` (Lambda code hash update only)
- No env var changes, no new resources, no infrastructure changes
- May require deleting `infra/prod/backend.zip` to force Terraform to detect the code change

### Validation Checklist (Phase 2)
- [ ] Cancel a test request with `@usmissionhero.com` client + staff
- [ ] Client inbox: "Visit Cancelled: [Service] — [Client]" received
- [ ] Staff inbox: same email received
- [ ] Admin inbox: same email received
- [ ] Neutral greeting ("Hello,") — not "Hi [Client Name]"
- [ ] Cancellation reason shown (if provided)
- [ ] Sitter row shown (if worker was assigned)
- [ ] No None/NoneType
- [ ] No "Team Member" fake name
- [ ] CloudWatch: `NOTIFICATION_SUCCESS` for VISIT_CANCELLED

### Rollback (Phase 2)
- Set `NOTIFY_CLIENT_ON_CANCELLED = "false"` and/or `NOTIFY_STAFF_ON_CANCELLED = "false"` in `locals.tf`
- `terraform apply`

---

## Not In Scope
- `visit_time_changed` — remains as safe stub (dormant, no active trigger exists)
- Notification ledger, quota tracking, webhooks (deferred from original spec)
