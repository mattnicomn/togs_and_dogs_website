# Release 6G: Staff Calendar Sync Reliability

## Overview
Comprehensive reliability, observability, and resilience improvements for the Google Calendar integration used during staff assignment and scheduling.

## Status: ✅ Deployed & Production Validated (2026-05-22)

## Deployment Summary
| Phase | Scope | Commit |
|-------|-------|--------|
| Phase 0 | Terraform env vars for intake/admin Lambdas | `b983dd5` |
| Phase 0B | Admin UI calendar warning toasts | `9b4774e` |
| Phase 0C | Revoked token / invalid_grant detection | `132ceb3` |
| Phase 2 | All-day event fallback (missing scheduled_time) | `65de586` |
| Phase 1 | CloudWatch metric filters + alarms | `d3da93c` |
| Phase 3 | Scheduled EventBridge daily health check | `b8b58e9` |
| Phase 4 | Retry mechanism for transient failures | `e3fe2f6` |

**Final state:** `terraform plan` returns "No changes." Infrastructure fully aligned.

## Changes

### Phase 0: Lambda Environment Variables
- Added `GOOGLE_CLIENT_CREDS_NAME`, `GOOGLE_USER_TOKENS_NAME`, `JOB_FUNCTION_NAME` to `intake` Lambda
- Added `GOOGLE_CLIENT_CREDS_NAME`, `GOOGLE_USER_TOKENS_NAME` to `admin` Lambda
- Enables calendar sync for admin-created bookings (Release 6F)

### Phase 0B: Frontend Calendar Warning UX
- Added `getCalendarNotificationType()` and `getCalendarWarningMessage()` helpers
- Admin Dashboard shows warning/info toasts when calendar sync fails or is skipped
- Applied to: approval, assignment, status changes, and new visit creation
- Business operations always show success — calendar issues are supplementary warnings

### Phase 0C: Token Revocation Handling
- Detects `invalid_grant` specifically during token refresh
- Marks stored token as `token_status: revoked` in Secrets Manager
- `_get_valid_token()` short-circuits when token is revoked (no repeated refresh attempts)
- `/admin/auth/status` returns `VALIDATION_FAILED` when token is revoked
- Reconnecting via OAuth clears the revoked flag automatically

### Phase 2: All-Day Event Fallback
- When `scheduled_time` is missing but `start_date` exists, creates an all-day Google Calendar event
- Uses Google Calendar `date` fields (not `dateTime`) with exclusive end date
- Handles DST boundaries and year boundaries correctly
- Invalid dates return graceful skip (not crash)

### Phase 1: CloudWatch Observability
- Standardized log markers: `CALENDAR_SYNC_SUCCESS`, `CALENDAR_SYNC_FAILED`, `CALENDAR_SYNC_SKIPPED`, `CALENDAR_SYNC_TOKEN_REVOKED`
- Metric filters on 5 Lambda log groups (intake, admin, review, assign, cancellation)
- CloudWatch alarms: calendar sync failures (1hr window), token revoked (1hr window)
- Alarms notify `ryan-alerts` SNS topic

### Phase 3: Scheduled Health Check
- Daily EventBridge rule invokes `google_auth` Lambda with health check action
- Verifies: credentials exist, refresh token exists, token not revoked, live refresh succeeds
- Log markers: `CALENDAR_HEALTH_CHECK_SUCCESS`, `CALENDAR_HEALTH_CHECK_FAILED`, `CALENDAR_HEALTH_CHECK_TOKEN_REVOKED`
- Metric filter + alarm for health check failures (24hr window)
- Detects `invalid_grant` during health check and marks token revoked

### Phase 4: Retry Mechanism
- Retries transient errors: HTTP 429, 500, 502, 503, 504, TimeoutError, OSError
- Does NOT retry: HTTP 400, 401, 403, validation skips, `invalid_grant`
- Max 2 retries with backoff (0.5s, 1.5s)
- Log markers: `CALENDAR_SYNC_RETRY_ATTEMPT`, `CALENDAR_SYNC_RETRY_SUCCESS`, `CALENDAR_SYNC_RETRY_EXHAUSTED`
- Existing `CALENDAR_SYNC_FAILED` alarm still catches final exhausted failures

## Production Validation Results

| Check | Result |
|-------|--------|
| Google Calendar health check | ✅ CONNECTED |
| Terraform state aligned | ✅ No changes |
| CloudWatch alarms created | ✅ calendar-sync-failures, calendar-token-revoked, calendar-health-check-failed |
| EventBridge daily schedule | ✅ Active |
| Metric filters active | ✅ 12 filters across 5 Lambdas + health check |
| All-day fallback | ✅ Creates events for bookings without scheduled_time |
| Token revocation detection | ✅ invalid_grant marks token revoked |
| Retry on transient errors | ✅ Retries 503/500/timeout, succeeds on recovery |
| Non-blocking behavior | ✅ Calendar failures never block business operations |
| Frontend warning UX | ✅ Admin sees calendar warnings without false failure |

## Non-Blocking Invariant
Calendar sync failures, skips, retries, and health check results **never block** booking creation, approval, assignment, cancellation, or any admin lifecycle action. This is preserved across all phases.

## Files Changed (Across All Phases)
- `src/backend/common/google_calendar.py`
- `src/backend/handlers/google_auth_handler.py`
- `web/src/components/AdminDashboard.jsx`
- `web/src/api/client.js`
- `infra/prod/main.tf`
- `modules/observability/main.tf`
- `modules/observability/variables.tf`
- `tests/backend/test_r6g_calendar_token.py`
- `tests/backend/test_r6g_calendar_all_day.py`
- `tests/backend/test_r6g_calendar_health.py`
- `tests/backend/test_r6g_calendar_retry.py`
