# Release 6A: Client Approval Email Template

## Overview
Implements the `CUSTOMER_APPROVED` email template for the Postmark notification system. This is the final missing piece that enables approval emails to be sent to clients when their pet care request is approved.

## Background
The notification infrastructure (Postmark client, resolver, config, suppression, service orchestration) was fully deployed in a prior release. The `review_handler.py` already calls `notify_event('CUSTOMER_APPROVED', request_item)` on approval. However, the `customer_approved()` template method was never implemented in `templates.py`, causing a silent `AttributeError` caught by the service's fail-safe try/except. No approval emails were actually being sent despite the infrastructure being live.

## Changes

### Primary: `customer_approved` Template
**File:** `src/backend/common/notifications/templates.py`

- Branded HTML email with:
  - Approval confirmation header
  - Booking details table (service type, pet names, date/time)
  - "What happens next" steps
  - Portal link button
  - Tog & Dogs footer
- Plain text fallback for email clients without HTML support
- All fields use safe `.get()` with defaults — handles missing pet names, service type, dates gracefully

### Secondary: Stub Templates for Other Event Types
The following methods were added as **functional placeholders** to prevent `AttributeError` crashes:

| Method | Event | Recipient | Status |
|--------|-------|-----------|--------|
| `request_received` | REQUEST_RECEIVED | Admin only | Placeholder — internal use only |
| `visit_scheduled` | VISIT_SCHEDULED | Client | **Placeholder — NOT final customer copy** |
| `staff_assigned` | STAFF_ASSIGNED | Staff | Placeholder — internal use only |
| `visit_cancelled` | VISIT_CANCELLED | Client + Staff + Admin | **Placeholder — NOT final customer copy** |
| `visit_time_changed` | VISIT_TIME_CHANGED | Client | Placeholder — no code path triggers this currently |

> **IMPORTANT:** The stub templates marked "NOT final customer copy" are factually accurate but minimal. They should be polished with full branded HTML before enabling live delivery to real clients. During the dry-run deployment phase, these will only log — not send.

### Terraform: Dry-Run Safety
**File:** `infra/prod/locals.tf`

- `NOTIFICATION_DRY_RUN` set to `"true"` for controlled deployment
- This ensures all notification events are logged but NOT delivered via Postmark
- Go-live requires changing to `"false"` after validation

## Deployment Strategy

### Phase 1: Dry-Run Validation (Current)
1. Deploy with `NOTIFICATION_DRY_RUN = "true"`
2. Approve a test request (client_email = `mbn@usmissionhero.com`)
3. Verify CloudWatch logs show `NOTIFICATION_DRY_RUN_LOG` with correct template data
4. Confirm no `NOTIFICATION_CRITICAL_FAILURE` errors
5. Validate template rendering (subject, recipient, context fields)

### Phase 2: Go-Live (CUSTOMER_APPROVED Only)
1. Set `NOTIFICATION_DRY_RUN = "false"` in `locals.tf`
2. Optionally set `NOTIFICATION_TEST_RECIPIENT_OVERRIDE = "mbn@usmissionhero.com"` for first live test
3. `terraform apply`
4. Approve a test request and verify email delivery
5. Remove override after validation

### Phase 3: Full Template Polish (Future)
- Polish `visit_scheduled`, `visit_cancelled` with full branded HTML
- Polish `staff_assigned` for internal team
- Consider gating individual event types via existing `NOTIFY_*` flags if needed

## Postmark Account Status
- **DNS/DKIM:** Verified
- **Sender Signature:** Verified (`support@usmissionhero.com`)
- **Account Approval:** PENDING (Test Mode — restricted to `@usmissionhero.com` recipients)
- **Secret:** Configured in AWS Secrets Manager

Until Postmark account is approved for production, emails can only be delivered to `@usmissionhero.com` addresses regardless of dry-run setting.

## Rollback
**Immediate halt:** Set `NOTIFICATION_DRY_RUN = "true"` → `terraform apply`
**Full disable:** Set `NOTIFICATIONS_ENABLED = "false"` → `terraform apply`
**Code revert:** `git checkout HEAD~1 -- src/backend/common/notifications/templates.py` → `terraform apply`

## Files Changed
- `src/backend/common/notifications/templates.py` — Added 6 template methods
- `infra/prod/locals.tf` — `NOTIFICATION_DRY_RUN` set to `"false"` (live)

## Hotfix 1: REQUEST_RECEIVED Polish (2026-05-18)

### Change
Replaced the minimal `request_received()` stub with a fully branded admin notification template.

### Additions
- Branded HTML with orange accent (distinct from green client-facing emails)
- Client information section: name, email (mailto link), phone
- Request details section: service type, pet names, date/time, request ID
- Conditional client notes section
- "Review in Dashboard" CTA button
- Professional plain-text fallback
- All fields null-safe via `_safe()` helper

### Service Context Enhancement
Added `client_email` and `client_phone` to the template context dict in `service.py` (2-line addition, no logic change) so the admin notification can display client contact information.

### Files Changed (Hotfix 1)
- `src/backend/common/notifications/templates.py` — Polished `request_received()`
- `src/backend/common/notifications/service.py` — Added `client_email`, `client_phone` to context
- `tests/backend/test_r6a_templates.py` — Added 3 new tests for request_received

## Validation Checklist
- [x] `py -m py_compile` passes
- [x] `terraform plan` shows only Lambda code updates + env var change
- [x] `terraform apply` succeeds
- [x] Test approval produces `NOTIFICATION_DRY_RUN_LOG` in CloudWatch
- [x] Log contains correct subject, recipient domain, event_key
- [x] No `NOTIFICATION_CRITICAL_FAILURE` in logs after hotfix deploy
- [x] Go-live: email received at test address
- [x] Go-live: HTML renders correctly
- [ ] Go-live: idempotency prevents duplicate on re-approval

## Validation History

### Dry-Run Attempt 1 (2026-05-17)
- **Result:** FAILED
- **Error:** `NOTIFICATION_CRITICAL_FAILURE: 'NoneType' object has no attribute 'replace'`
- **Root Cause:** `normalize_context()` used `context.get('service_type', 'PET_SITTING')` which returns `None` when the key exists with a `None` value. The `.replace()` call on `None` crashed.
- **Fix:** Added `_safe()` helper, changed to `context.get('service_type') or 'PET_SITTING'` pattern for all nullable fields.

### Dry-Run Attempt 2 (2026-05-18)
- **Result:** PASSED ✅
- **Status:** Dry-Run Validated — Ready for Controlled Live Send Test
- **Confirmed:**
  - `NOTIFICATION_DRY_RUN_LOG` appeared in CloudWatch
  - `provider = postmark`
  - `dry_run = true`
  - Recipient domain = `usmissionhero.com`
  - Approval subject preview rendered correctly
  - No `NOTIFICATION_CRITICAL_FAILURE` after hotfix deploy
  - No `AttributeError`
  - No `NOTIFICATION_MISSING_TEMPLATE`
- **Next Step:** Awaiting approval to set `NOTIFICATION_DRY_RUN = "false"` for controlled live send test

### Live Send Test (2026-05-18)
- **Result:** PASSED ✅
- **Action:** Set `NOTIFICATION_DRY_RUN = "false"`, deployed, approved test request
- **Confirmed:** Branded approval email delivered to `mbn@usmissionhero.com` via Postmark
- **Status:** CUSTOMER_APPROVED live delivery validated

### Hotfix 1: REQUEST_RECEIVED Polish (2026-05-18)
- **Result:** PASSED ✅
- **Action:** Polished `request_received()` admin notification template
- **Confirmed:**
  - Branded HTML email received at admin address
  - Client name, email, phone displayed correctly
  - Service type, pet names, date rendered
  - Request ID visible
  - "Review in Dashboard" CTA button present
  - No None/NoneType values in content
  - Client notes section rendered when provided
- **Status:** Live — Production Validated
