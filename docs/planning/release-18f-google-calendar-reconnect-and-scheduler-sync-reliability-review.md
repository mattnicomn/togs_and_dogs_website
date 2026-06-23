# Release 18F: Google Calendar Reconnect and Scheduler Sync Reliability Review

**Status:** Planning / Review
**Date:** 2026-06-23
**Priority:** Medium (operational health; independent of strict-mode gate)
**Scope:** Document current state, risks, and validation checklist for Google Calendar integration

---

## 1. Current Google Calendar Integration State

### Admin Warning

Production `/admin` currently displays:

> "Google Calendar connection needs reconnect. Sitter schedule sync is degraded."

This indicates the stored Google OAuth refresh token is expired or revoked, and the system cannot create/update/delete calendar events until reconnected.

### Architecture Summary

| Component | Location | Purpose |
|-----------|----------|---------|
| OAuth initiation | `GET /admin/auth/google` → `google_auth_handler.py` | Starts OAuth flow, stores state in DynamoDB |
| OAuth callback | `GET /admin/auth/callback` → `google_auth_handler.py` | Exchanges code for tokens, stores in Secrets Manager |
| Token storage | AWS Secrets Manager (`google-user-tokens`) | Stores access + refresh tokens |
| Calendar sync | `common/google_calendar.py` | Creates/updates/deletes events on booking changes |
| Health check | EventBridge daily schedule → `google_auth_handler.py` | Validates token, marks revoked if expired |
| Connection status | `GET /admin/auth/status` | Returns connection health for admin banner |
| Disconnect | `DELETE /admin/auth/google` | Clears tokens from Secrets Manager |

### What Uses Calendar Sync

| Handler | Trigger | Calendar Action |
|---------|---------|-----------------|
| `review_handler.py` | Request approved | Create calendar event |
| `assignment_handler.py` | Staff assigned | Update event with staff info |
| `cancellation_handler.py` | Visit cancelled | Delete/update calendar event |
| `job_handler.py` | Multi-day job expansion | Create per-day events |

### Degraded State Behavior

When disconnected/revoked:
- Calendar sync calls are attempted but fail gracefully (non-blocking)
- Bookings, approvals, assignments, completions all continue working
- Schedule data is stored in DynamoDB regardless of calendar sync
- Admin sees warning banner but operations are not blocked
- Staff mobile schedule view is unaffected (reads from DynamoDB, not Calendar)

---

## 2. Current Risks

| # | Risk | Likelihood | Impact | Notes |
|---|------|-----------|--------|-------|
| 1 | Schedule events missing from Google Calendar | ✅ Active (degraded now) | Medium | Visits approved during disconnection have no Calendar event |
| 2 | Reconnect flow unclear to business owner | Medium | Low | Admin must click reconnect and complete OAuth |
| 3 | Stale/expired tokens in Secrets Manager | ✅ Active | Low | Health check marks as revoked; no operational harm |
| 4 | OAuth re-consent required (Google revoked app) | Low | Medium | Would need Google Cloud Console review |
| 5 | Second-tenant calendar isolation | Medium (future) | High | Current: single shared connection. Future: per-tenant required |
| 6 | Reconnect triggers unwanted external notifications | Low | Low | Calendar sync is downstream of approval; no email side effects |
| 7 | Token logged or exposed during reconnect | Low | High | Code uses Secrets Manager; tokens not printed to CloudWatch |
| 8 | Cross-tenant calendar event leak (future) | N/A (single tenant) | Critical | Must be addressed before second tenant |

---

## 3. Reconnect Flow

### Expected Admin Recovery Steps

1. Admin sees "Google Calendar connection needs reconnect" banner on `/admin`
2. Admin navigates to Settings or clicks reconnect action
3. System calls `GET /admin/auth/google` → generates OAuth URL
4. Admin is redirected to Google consent screen
5. Admin approves → Google redirects to callback URL
6. `GET /admin/auth/callback` exchanges code for new tokens
7. New refresh + access tokens stored in Secrets Manager
8. Next calendar sync attempt succeeds
9. Banner disappears (health check passes)

### Entitlement Gate

Phase 1 entitlement enforcement gates `GET /admin/auth/google` (calendar connect):
- Professional tier: ✅ Allowed (google_calendar_enabled = true)
- Starter tier: ❌ Blocked (would return 403)
- Current tog_and_dogs is Professional: reconnect is allowed

---

## 4. Validation Checklist (For AG/Matthew Reconnect Smoke)

| # | Check | Expected | Approval Needed? |
|---|-------|----------|------------------|
| 1 | `/admin` displays degraded-state warning | ✅ Currently showing | No (already visible) |
| 2 | `GET /admin/auth/status` returns disconnected/revoked state | ✅ | No (read-only) |
| 3 | Reconnect button/link routes to `GET /admin/auth/google` | ✅ OAuth URL returned | No (read-only check) |
| 4 | OAuth consent page loads (Google) | ✅ | **Yes — Matthew must approve actual reconnect** |
| 5 | Callback stores new tokens in Secrets Manager | ✅ | **Yes — this is the actual reconnect** |
| 6 | Banner disappears after reconnect | ✅ | Follows from #5 |
| 7 | New booking creates calendar event | ✅ | Test with safe data only |
| 8 | No private token data logged in CloudWatch | ✅ | Code review confirms |
| 9 | Reconnect is tenant-scoped (tok_and_dogs only) | ✅ | Single tenant — no cross-tenant risk now |
| 10 | No unrelated notifications triggered by reconnect | ✅ | Calendar sync is silent |

### Go/No-Go for Reconnect

| Gate | Status | Required? |
|------|--------|-----------|
| Matthew approves reconnect attempt | ⏳ | **Yes** |
| Admin dashboard is functional | ✅ | Yes |
| Entitlement allows calendar connect (Professional tier) | ✅ | Yes |
| No second tenant exists (no cross-tenant risk) | ✅ | Yes |
| Google Cloud Console project is active | ⏳ Verify | Yes |
| OAuth credentials in Secrets Manager are correct | ⏳ Verify | Yes |

---

## 5. Future Second-Tenant Requirements

### Current State: Single Shared Connection

- One set of Google OAuth tokens in Secrets Manager
- One calendar connection for the entire platform
- All events go to one Google Calendar
- This is acceptable for single-tenant but MUST change for multi-tenant

### Required for Second Tenant

| Requirement | Status | Priority |
|-------------|--------|----------|
| Per-tenant token storage (separate Secrets Manager keys per company_id) | ❌ Not implemented | High |
| Per-tenant calendar_id configuration | ❌ Not implemented | High |
| Tenant-scoped `GET /admin/auth/status` | ⚠️ Partially (uses get_current_company_id for tenant context) | Medium |
| Platform admin can view connection health per tenant | ⚠️ Not in platform UI yet | Low |
| Second-tenant dry run verifies no cross-calendar event creation | ❌ Not tested | High |

### Isolation Strategy (Future)

```
Secrets Manager key pattern:
  {name_prefix}/google/user-tokens/{company_id}

Example:
  togs-and-dogs-prod/google/user-tokens/tog_and_dogs
  togs-and-dogs-prod/google/user-tokens/second_tenant
```

Each tenant connects their own Google account independently. Platform admin can see connection status but not tokens.

---

## 6. Safe AG Follow-Up Options

| Option | Scope | Risk | Requires Approval? |
|--------|-------|------|-------------------|
| Read-only code review of google_auth/calendar flow | Documentation | None | No |
| Operational runbook update for calendar reconnect | Documentation | None | No |
| UI copy improvement (clearer reconnect CTA) | Frontend polish | Low | Standard deploy approval |
| Actual OAuth reconnect | Live Google interaction | Low | **Yes — Matthew must approve** |
| Per-tenant calendar isolation design | Planning | None | No |
| Per-tenant token storage implementation | Code | Medium | Separate release approval |

---

## 7. Operational Notes

### When Calendar Is Disconnected

- All booking/scheduling operations continue normally
- Events are simply not synced to Google Calendar
- No data loss — DynamoDB records remain complete
- Staff mobile schedule is unaffected (reads from DynamoDB)
- Reconnecting later does NOT retroactively sync missed events

### When Calendar Is Reconnected

- New operations (approve, assign, cancel) will sync going forward
- Previously missed events stay missing unless manually created
- Admin may want to re-approve or re-assign to trigger sync for important upcoming visits

### Monitoring

- Daily EventBridge health check validates token
- `CALENDAR_HEALTH_CHECK_FAILED` alarm exists
- `calendar_token_revoked` metric filter exists
- CloudWatch logs show sync attempts and failures

---

## 8. Recommended Release Sequence

| Release | Scope | Owner |
|---------|-------|-------|
| **18F** | Google Calendar reconnect review (this document) | ✅ Kiro (done) |
| **18G** | Matthew-approved Google Calendar reconnect execution | Matthew + AG |
| **18H** | Post-reconnect calendar sync validation | AG |
| Future | Per-tenant calendar isolation design | Kiro |
| Future | Per-tenant token storage implementation | AG |

---

## 9. What This Document Does NOT Authorize

- ❌ Reconnecting Google Calendar
- ❌ Executing OAuth flow
- ❌ Inspecting/printing/copying tokens
- ❌ Code changes
- ❌ Terraform/AWS changes
- ❌ Modifying Secrets Manager
- ❌ DynamoDB writes
- ❌ Frontend/mobile deployment
- ❌ Stripe/Postmark changes
- ❌ Creating second tenant
- ❌ Enabling strict mode
- ❌ Ryan/tester changes

This is a review/planning document. Reconnect execution (18G) requires Matthew's explicit approval.
