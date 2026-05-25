# Release 6G: Staff Calendar Sync Reliability — Plan

## Objective
Improve reliability, observability, and user-facing clarity around Google Calendar sync during staff assignment and scheduling. Reduce silent failures and provide proactive monitoring.

---

## Phase 0: Critical Infrastructure Fix (REQUIRED FIRST)

### Missing Lambda Environment Variables

**Problem:** The `intake` and `admin` Lambda functions do NOT have `GOOGLE_CLIENT_CREDS_NAME` or `GOOGLE_USER_TOKENS_NAME` environment variables configured. This means:
- `intake_handler.py` (Release 6F admin-created bookings) calls `sync_calendar_event()` but the function cannot retrieve Google tokens → always fails silently
- `admin_handler.py` may also perform calendar sync paths during bulk status changes

**Fix:** Add these environment variables to the `intake` and `admin` Lambda definitions in `infra/prod/main.tf`:
```hcl
GOOGLE_CLIENT_CREDS_NAME = module.secrets.google_client_creds_arn
GOOGLE_USER_TOKENS_NAME  = module.secrets.google_user_tokens_arn
```

**Note:** The `review`, `assign`, `cancellation`, and `job` Lambdas already have these variables. Only `intake` and `admin` are missing them.

**Risk:** Low — adding env vars doesn't change runtime behavior for existing flows. Only enables calendar sync for the new admin-created booking path.

**Deployment:** Requires `terraform apply` (Lambda environment variable update).

---

## Phase 0B: Frontend Calendar Warning UX

### Problem
When a booking is created but calendar sync fails or is skipped (e.g., `calendar_failed`, `calendar_skipped_missing_scheduled_time`), the Admin Dashboard currently shows a full green success notification. The admin has no visibility that the calendar event was not created.

### Fix
Update `AdminDashboard.jsx` to inspect `calendar_result` in API responses:
- If `calendar_result.status === 'calendar_failed'` → show warning toast: "Booking created, but calendar sync failed. Event may not appear on Google Calendar."
- If `calendar_result.status` starts with `calendar_skipped` → show info toast: "Booking created. Calendar event skipped (no scheduled time set)."
- Only show full green success when `calendar_result` is null or has `event_id`

### Files
- `web/src/components/AdminDashboard.jsx` — notification logic after booking/assignment actions

---

## Phase 0C: Google Token Revocation Handling

### Problem
When Google revokes the refresh token (user removes app access, token expires after 6 months of non-use, or Google policy change), the refresh attempt returns `invalid_grant`. Currently this is logged as a generic error but the system doesn't update its connection status.

### Fix
1. In `google_calendar.py` `_refresh_access_token()`: detect `invalid_grant` error specifically
2. When detected: update the stored tokens to mark status as `revoked` or clear the access_token
3. Optionally: update a DynamoDB config record or flag that the admin dashboard's `/admin/auth/status` endpoint can read
4. The `/admin/auth/status` endpoint should return `VALIDATION_FAILED` when the stored token is marked as revoked
5. Admin Dashboard already shows connection status — this ensures it reflects reality after revocation

### Files
- `src/backend/common/google_calendar.py` — detect `invalid_grant` in refresh response
- `src/backend/handlers/google_auth_handler.py` — `/admin/auth/status` should check for revoked state

---

## Current-State Findings

### Architecture
- **Token storage:** AWS Secrets Manager (two secrets: client creds + user tokens)
- **Token refresh:** Automatic on use — checks expiry with 5-minute buffer, refreshes via Google OAuth
- **Sync pattern:** Fire-once, non-blocking — all calendar operations are wrapped in try/except
- **Event lifecycle:** Created on approval/assignment → updated on re-assignment → deleted on cancellation
- **Event ID persistence:** Stored on both REQ# and JOB# records as `google_event_id`

### Where Calendar Sync Fires

| Handler | Trigger | Action |
|---------|---------|--------|
| `review_handler.py` | APPROVED/ASSIGNED/BOOKED/SCHEDULED | `sync_calendar_event()` (create/update) |
| `review_handler.py` | CANCELLED/ARCHIVED/DELETED | `delete_event()` + REMOVE google_event_id |
| `assignment_handler.py` | Worker assigned | `sync_calendar_event()` with worker_name |
| `cancellation_handler.py` | Admin approves cancellation | `delete_event()` + REMOVE google_event_id |
| `intake_handler.py` | Admin-created booking (6F) | `sync_calendar_event()` immediately |

### Token Refresh Flow
```
_get_valid_token()
  → Read tokens from Secrets Manager
  → Check if access_token is still valid (updated_at + expires_in - 300s buffer)
  → If valid: return cached token
  → If expired: call _refresh_access_token()
    → Use refresh_token to get new access_token from Google
    → Save merged tokens back to Secrets Manager
    → Return new access_token
  → If refresh fails: return None → caller gets "calendar_failed" status
```

### What Happens on Failure
- Calendar sync returns `{"status": "calendar_failed", "message": "..."}` 
- The business operation (approval, assignment, cancellation) **always succeeds** regardless
- CloudWatch logs: `CALENDAR_SYNC_WARNING`, `WARNING: Google Calendar sync failed`, `ERROR: Failed to refresh Google token`
- No retry mechanism exists
- No CloudWatch alarm exists
- No scheduled health check exists

### Event Body Fields
- Summary: `Tog and Dogs - {pet_names} / {client_name} - {service_type}`
- Description: client, pet, service, assigned staff, scheduled time, request ID, notes
- Start/End: dateTime with `America/New_York` timezone
- **Requires `scheduled_time` field** — if missing, sync is skipped with `missing_scheduled_time`

---

## Known Risks & Likely Failure Points

| Risk | Likelihood | Impact | Current Mitigation |
|------|-----------|--------|-------------------|
| Refresh token expires (unused >6 months) | Low (active use) | Calendar stops syncing until manual reauth | None — requires admin intervention |
| Refresh token revoked by Google | Very Low | Same as above | Manual reauth documented |
| Access token expired between Lambda cold starts | Medium | Single request fails, next succeeds | Auto-refresh on use |
| `scheduled_time` missing on record | High | Event not created (skipped silently) | None — many records lack this field |
| Google API rate limit | Very Low | Temporary 429 errors | None — no retry |
| Network timeout to Google API | Low | Single sync fails | None — no retry |
| Admin unaware calendar is disconnected | Medium | Events silently not created | Status shown in Admin Dashboard header |
| google_event_id lost (orphaned calendar events) | Low | Events remain on calendar after cancellation | Fallback lookup in assignment_handler |

### Critical Finding: `scheduled_time` Requirement
The `_build_event_body()` function **requires** `scheduled_time` to create a timed event. If only `start_date` is present (which is common for bookings without a specific time), the sync returns `"missing_scheduled_time"` and **no event is created**. This is likely the most common reason calendar events are missing.

---

## Recommended Scope for Release 6G

### Phase 1: Observability & Monitoring (~2 hours)
1. Add CloudWatch alarm on `CALENDAR_SYNC_WARNING` and `Failed to refresh Google token` patterns
2. Add structured logging with consistent prefix: `CALENDAR_SYNC_*` for all outcomes
3. Surface calendar sync status in the Admin Dashboard response (already partially done)

### Phase 2: All-Day Event Fallback (~2 hours)
1. When `scheduled_time` is missing but `start_date` exists, create an **all-day event** instead of skipping
2. This ensures every approved/assigned booking gets a calendar placeholder
3. When `scheduled_time` is later added (e.g., during assignment), update the event to a timed event

### Phase 3: Proactive Token Health Check (~2-3 hours)
1. Add a scheduled CloudWatch Events rule (daily or every 12 hours) that invokes a lightweight Lambda
2. The Lambda calls `_get_valid_token()` — if refresh fails, publish to SNS (admin alert)
3. This catches token expiry before it affects real bookings
4. Alternative: piggyback on the existing `/admin/auth/status` endpoint with a scheduled check

### Phase 4: Retry on Transient Failures (~1-2 hours)
1. Add a single retry with exponential backoff for Google API 5xx and timeout errors
2. Do NOT retry on 4xx (auth failures, invalid requests)
3. Keep the non-blocking pattern — retry once, then give up gracefully

---

## Backend Changes Likely Needed

### `src/backend/common/google_calendar.py`
- **Phase 2:** Modify `_build_event_body()` to create all-day events when `scheduled_time` is missing but `start_date` exists
- **Phase 4:** Add single-retry wrapper for `sync_calendar_event()` and `delete_event()`
- **Phase 1:** Standardize log prefixes to `CALENDAR_SYNC_SUCCESS`, `CALENDAR_SYNC_FAILED`, `CALENDAR_SYNC_SKIPPED`

### `infra/prod/` (Terraform)
- **Phase 1:** Add CloudWatch metric filter + alarm for calendar failure patterns
- **Phase 3:** Add scheduled EventBridge rule + lightweight health-check Lambda (or reuse google_auth Lambda)

### `src/backend/handlers/google_auth_handler.py`
- **Phase 3:** Add a `/admin/auth/health` endpoint or extend `/admin/auth/status` to be invokable by EventBridge

---

## Frontend/UI Changes Likely Needed

### Admin Dashboard
- **Phase 1:** If `calendar_result.status === 'calendar_failed'` in an API response, show a warning toast: "Calendar sync failed — event may not appear on Google Calendar"
- **Phase 1:** Consider showing a persistent banner when Google Calendar status is `VALIDATION_FAILED` or `NOT_CONNECTED`

### No Other Frontend Changes Expected
The calendar integration is entirely backend-driven. The frontend already shows Google Calendar connection status in the admin header.

---

## Test Plan

### Phase 0 (Infrastructure)
- Verify `terraform plan` shows only env var additions to `intake` and `admin` Lambdas
- Verify `terraform apply` succeeds with no other changes
- After apply: invoke admin-created booking → verify calendar sync is attempted (not `Failed to retrieve Google client config`)
- Verify existing `review`, `assign`, `cancellation` Lambdas still have their Google env vars (no regression)

### Phase 0B (Frontend Warning)
- Create a booking without `scheduled_time` → verify warning toast appears (not green success)
- Create a booking with valid `scheduled_time` → verify green success
- Simulate `calendar_failed` response → verify warning toast

### Phase 0C (Token Revocation)
- Simulate `invalid_grant` error from Google token endpoint → verify system marks connection as failed
- After simulated revocation: verify `/admin/auth/status` returns `VALIDATION_FAILED`
- After reauthorization: verify status returns to `CONNECTED`

### Phase 1 (Observability)
- Verify CloudWatch alarm triggers on simulated `CALENDAR_SYNC_WARNING` log
- Verify structured logs appear correctly in CloudWatch

### Phase 2 (All-Day Fallback)
- Unit test: `_build_event_body()` with `start_date` but no `scheduled_time` → returns all-day event body
- Unit test: `_build_event_body()` with both `start_date` and `scheduled_time` → returns timed event (unchanged)
- Unit test: DST boundary — `start_date` on a DST transition day with `scheduled_time` → verify correct timezone handling
- Unit test: `start_date` at year boundary (Dec 31 / Jan 1) → verify no off-by-one
- Integration: Approve a booking without `scheduled_time` → verify all-day event appears on Google Calendar

### Phase 3 (Health Check)
- Verify scheduled Lambda invokes successfully
- Verify SNS alert fires when token refresh fails (mock the failure)
- Verify no alert when token is healthy

### Phase 4 (Retry)
- Unit test: First attempt 500 → retry succeeds → event created
- Unit test: First attempt 401 → no retry → returns failure
- Unit test: Both attempts fail → returns failure gracefully
- Unit test: `invalid_grant` on refresh → no retry of the calendar operation (token is revoked, not transient)

### Non-Blocking Invariant (ALL Phases)
- **Calendar failure must NEVER block:** booking creation, approval, assignment, cancellation, or any admin lifecycle action
- Every test that simulates a calendar failure must verify the business operation still returns 200/success

---

## Deployment/Validation Plan

### Phase 1
- Terraform: Add CloudWatch alarm (requires `terraform apply`)
- Backend: Log format changes (Lambda code update)
- AG validation: Trigger a calendar sync, verify new log format in CloudWatch

### Phase 2
- Backend only: Modify `_build_event_body()` (Lambda code update via `terraform apply`)
- AG validation: Approve a booking without `scheduled_time` → verify all-day event on Google Calendar
- AG validation: Assign with `scheduled_time` → verify event updates to timed

### Phase 3
- Terraform: Add EventBridge rule + health check Lambda/endpoint
- AG validation: Verify scheduled execution in CloudWatch, verify alert on simulated failure

### Phase 4
- Backend only: Add retry wrapper (Lambda code update)
- AG validation: Verify retry behavior via CloudWatch logs during normal operations

---

## Items Explicitly Deferred

| Item | Reason |
|------|--------|
| Multi-calendar support (per-staff calendars) | Architecture change, not needed for current single-calendar model |
| Two-way sync (Google → app) | Complex, not needed — app is source of truth |
| Calendar event attendees (invite staff via email) | Requires additional Google API scopes |
| Recurring events for weekly bookings | Requires recurring booking feature first |
| Calendar color coding by service type | Nice-to-have, not reliability-related |
| Automatic reauthorization without admin | Not possible with Google OAuth — requires user consent |
| Full calendar event audit trail | Low priority — current logging is sufficient |

---

## Estimated Effort

| Phase | Effort | Risk | Deployment |
|-------|--------|------|-----------|
| Phase 0: Env Vars Fix | ~30 min | Very Low | Terraform only |
| Phase 0B: Frontend Warning | ~1 hour | Low | Frontend only |
| Phase 0C: Token Revocation | ~1-2 hours | Low | Lambda only |
| Phase 1: Observability | ~2 hours | Low | Terraform + Lambda |
| Phase 2: All-Day Fallback | ~2 hours | Low | Lambda only |
| Phase 3: Health Check | ~2-3 hours | Low | Terraform + Lambda |
| Phase 4: Retry | ~1-2 hours | Low | Lambda only |
| **Total** | **~10-12 hours** | | |

## Recommended Priority Order
1. **Phase 0 first** — critical infrastructure fix (env vars for intake/admin Lambdas)
2. **Phase 0B** — frontend warning UX so admins know when calendar sync is skipped
3. **Phase 0C** — token revocation detection so admins know when to reconnect
4. **Phase 2 next** — fixes the most common silent failure (missing `scheduled_time` → all-day fallback)
5. **Phase 1** — adds visibility into remaining failures (CloudWatch alarms)
6. **Phase 3** — proactive token health monitoring
7. **Phase 4 last** — handles rare transient errors (retry)
