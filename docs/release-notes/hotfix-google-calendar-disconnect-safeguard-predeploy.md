# Hotfix: Google Calendar Disconnect UI Safeguard (Pre-Deploy)

**Date:** 2026-07-12
**Status:** Pre-Deploy (undeployed unless separately authorized)
**Type:** Frontend-only UI safeguard
**Priority:** Urgent (Ryan demonstration readiness)
**Scope:** Prevent accidental disconnection of the shared business calendar

---

## 1. Problem

The Google Calendar connection is **tenant/business-scoped** — a single OAuth connection shared across all admin/staff accounts within the business. The existing "Disconnect" button in the Google Calendar integration card would disconnect the calendar for every user on the tenant, including the business owner. This poses a critical risk ahead of the Ryan demonstration.

## 2. Connection Scope Determination

| Finding | Evidence |
|---------|----------|
| Connection is tenant-scoped | Per-tenant token isolation (21F/21G/21H), secret path `togs-and-dogs-prod/calendar/{company_id}/tokens` |
| Status endpoint is tenant-scoped | `getGoogleStatus()` returns a single status for the tenant |
| Disconnect endpoint is tenant-scoped | `disconnectGoogle()` would clear the tenant's calendar secret |
| No user-level connection exists | No per-user OAuth token, no user-specific calendar selection |
| Connected Account label | Already shows "Business Account" (not a user email) |

## 3. Safeguard Implemented

| Before | After |
|--------|-------|
| "Disconnect" button visible when status is CONNECTED | Button removed entirely |
| Clicking Disconnect would call `disconnectGoogle()` API | No disconnect handler exists; no API call possible |
| No explanation of shared nature | Text: "Shared business calendar — individual calendar connections are not available yet." |

### Specific Changes

**`web/src/components/AdminDashboard.jsx`:**
- Removed `disconnectGoogle` from the API import
- Removed `handleDisconnectGoogle` function entirely
- Added comment explaining the intentional removal
- Replaced the Disconnect `<button>` with an informational `<p>` tag explaining the shared nature
- The Connect button remains available when status is NOT CONNECTED (for owner reconnect if needed)

### What Remains Visible
- "Connected" status badge (green)
- "Business Account" label (no private email or OAuth identity exposed)
- Last Checked timestamp
- Technical details (status, provider, scopes — no tokens or secrets)
- Shared-calendar explanation text

### What Is NOT Visible/Activatable
- No Disconnect button
- No keyboard-focusable disconnect control
- No way to invoke the disconnect API from the UI

## 4. Deferred Work: Per-User Calendar Connections

Implementing per-user calendar connections is intentionally deferred. It would require:
- User-scoped OAuth ownership model
- Multiple connection records per tenant
- User-specific calendar selection
- Authorization rules for connect/disconnect per user
- Scheduling/event ownership decisions
- Migration and compatibility planning with the existing shared model

## 5. Viewport Verification (Static Analysis)

| Width | Behavior |
|-------|----------|
| 375px | Calendar card renders in sidebar; shared-calendar text wraps within card width; no overflow |
| 768px | Calendar card visible in filter panel; text fits naturally |
| 1024px+ | Standard desktop sidebar layout; no regression |

The replacement `<p>` element is plain text with `fontSize: 0.8rem`, `text-align: center`, and `padding: 8px 0`. It has no fixed width and flows naturally within the `.integration-actions` container.

## 6. What Was NOT Changed

- ❌ OAuth authorization behavior
- ❌ OAuth tokens or calendar credentials
- ❌ Cognito or authentication
- ❌ Backend ownership models or API endpoints
- ❌ DynamoDB connection records
- ❌ Google Calendar event routing or scheduling
- ❌ Terraform or AWS infrastructure
- ❌ Tenant resolution mode
- ❌ Production data
- ❌ Stripe
- ❌ Mobile/Expo/TestFlight/App Store
- ❌ Backend disconnect endpoint (still exists, just not callable from UI)

## 7. Build & Lint Verification

| Check | Result |
|-------|--------|
| `npm run lint` | 47 problems (38 errors, 9 warnings) — baseline match |
| New lint findings | 0 |
| `npm run build` | ✅ Success (101 modules, 371ms) |

## 8. Deployment Status

This hotfix remains **undeployed** unless Matthew explicitly authorizes production deployment. The current production bundle (`index-CZXrWtrt.js` from Release 22V) still contains the Disconnect button.
