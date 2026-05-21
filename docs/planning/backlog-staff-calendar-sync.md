# Backlog: Staff Calendar Sync Reliability

## Priority: Medium
## Status: Planned

## Problem
Google Calendar sync errors (refresh token failures) are observed in CloudWatch during assignment and cancellation workflows. These are non-blocking (calendar sync is wrapped in try/except) but mean calendar events may not be created/updated/deleted reliably.

## Observed Symptoms
- `CALENDAR_SYNC_WARNING` in assign Lambda logs
- `WARNING: Google Calendar sync failed` in review Lambda logs
- Refresh token expiry after extended periods without use

## Root Cause
- Google OAuth refresh tokens can expire if not used within a certain period
- The token is stored in AWS Secrets Manager and refreshed on use
- If the stored token is stale, the refresh fails and calendar operations silently skip

## Proposed Fix
1. Add a health check endpoint or scheduled Lambda that refreshes the Google token periodically
2. Add CloudWatch alarm on `CALENDAR_SYNC_WARNING` pattern
3. Document the Google Calendar reauthorization procedure (already at `docs/operations/google-calendar-reauthorization.md`)

## Files Involved
- `src/backend/common/google_calendar.py` — sync/delete logic
- `src/backend/handlers/google_auth_handler.py` — OAuth flow
- `infra/prod/` — potential scheduled Lambda for token refresh

## Effort: 4-6 hours
## Non-Blocking: Calendar failures never block business workflows
