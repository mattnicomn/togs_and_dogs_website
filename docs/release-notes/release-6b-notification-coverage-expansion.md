# Release 6B: Notification Coverage Expansion (Phase 1)

## Overview
Polishes the `visit_scheduled` and `staff_assigned` notification templates from minimal stubs into production-quality branded emails, matching the style established in Release 6A.

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

## Rollback
If issues occur with the new templates:
- Set `NOTIFY_CLIENT_ON_SCHEDULED = "false"` and/or `NOTIFY_STAFF_ON_ASSIGNMENT = "false"` in `locals.tf`
- `terraform apply`
- This disables the specific events without affecting approval or request-received emails

## Not In Scope
- `visit_cancelled` — remains as safe stub (Phase 3, future release)
- `visit_time_changed` — remains as safe stub (dormant, no trigger exists)
- Notification ledger, quota tracking, webhooks (deferred)
