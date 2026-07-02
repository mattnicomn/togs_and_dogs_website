# Release 21A: Multi-Provider Calendar Integration Strategy

**Status:** Planning
**Date:** 2026-06-28
**Priority:** Medium (operational UX improvement; not a security blocker)
**Scope:** Define calendar provider model, priority, metadata, and future release sequence

---

## 1. Calendar Provider Model

### Supported Provider Types

| Provider | Code | Auth Method | Sync Capability | Priority |
|----------|------|-------------|-----------------|----------|
| None (unconfigured) | `none` | N/A | N/A | ✅ Default for new tenants |
| Google Calendar | `google` | OAuth 2.0 | Full CRUD (create/update/delete events) | ✅ First-class (existing) |
| Microsoft Outlook / 365 | `microsoft` | Microsoft Graph OAuth | Full CRUD | ⏳ Second priority |
| CalDAV (generic) | `caldav` | Username + app-specific password | Basic CRUD | ⏳ Third (covers Yahoo, iCloud, others) |
| ICS Feed (read-only) | `ics_feed` | Public/private URL | Read-only (export schedule) | ⏳ Fallback option |

### Provider State Machine (Per Tenant)

```
none → google / microsoft / caldav / ics_feed
  ↕ (can switch provider with disconnect-then-reconnect)
connected → disconnected (revoked/expired)
  ↕
disconnected → connected (reconnect)
```

---

## 2. Provider Priority Recommendation

| Priority | Provider | Rationale |
|----------|----------|-----------|
| **1 (Now)** | Google Calendar | Already partially implemented; widest adoption among small businesses |
| **2 (Next)** | Microsoft Outlook / 365 | Large market share; Microsoft Graph API is well-documented; needed for business owners on Microsoft ecosystem |
| **3 (Later)** | CalDAV (generic) | Covers Yahoo, iCloud, and self-hosted calendars through one protocol |
| **4 (Deferred)** | ICS Feed | Read-only; low value for scheduling; useful only as "view my schedule" export |
| **5 (Not planned)** | Apple iCloud (native API) | No public API; CalDAV is the only path; app-specific passwords add friction |

### Recommendation

- Make Google Calendar fully tenant-scoped before enabling for second tenants (21D)
- Plan Microsoft Graph as the second first-class provider (21F)
- CalDAV/Yahoo/Apple can be addressed through a single generic CalDAV adapter later
- ICS feed is trivial and can be added as a "lite" option anytime

---

## 3. Tenant Metadata Requirements

### New/Extended Fields on TENANT Metadata

```json
{
  "calendar_provider": "none",
  "calendar_enabled": false,
  "calendar_connection_status": "not_configured",
  "calendar_connected_account_label": null,
  "calendar_last_check_at": null,
  "calendar_secret_ref": null,
  "calendar_capabilities": {
    "create_events": false,
    "update_events": false,
    "delete_events": false,
    "read_events": false
  }
}
```

### Field Definitions

| Field | Type | Purpose |
|-------|------|---------|
| `calendar_provider` | String enum | `none`, `google`, `microsoft`, `caldav`, `ics_feed` |
| `calendar_enabled` | Boolean | Whether calendar feature is available for this tier |
| `calendar_connection_status` | String | `not_configured`, `connected`, `disconnected`, `revoked`, `error` |
| `calendar_connected_account_label` | String or null | Display-safe label (e.g., "user@gmail.com calendar" — no tokens) |
| `calendar_last_check_at` | ISO timestamp | Last health check |
| `calendar_secret_ref` | String or null | Secrets Manager key path for this tenant's tokens (NOT the raw token) |
| `calendar_capabilities` | Object | What sync operations are supported for the connected provider |

### Entitlement Interaction

| Tier | `calendar_enabled` | `google_calendar_enabled` (existing) |
|------|--------------------|-----------------------------------------|
| Starter | false | false |
| Professional | true | true |
| Premium | true | true |
| Enterprise | true | true |

The existing `google_calendar_enabled` flag in TIER_LIMITS serves the same purpose as `calendar_enabled`. For MVP, keep using the existing flag. Add the full `calendar_provider` model when Microsoft/CalDAV is implemented.

---

## 4. Secrets/Storage Model

### Per-Tenant Token Isolation

| Current (Single-Tenant) | Future (Per-Tenant) |
|--------------------------|---------------------|
| `{prefix}/google/user-tokens` (one global key) | `{prefix}/calendar/{company_id}/tokens` |

### Rules

- ❌ No shared token secrets across tenants
- ❌ No raw tokens stored in DynamoDB
- ❌ No tokens/passwords/credentials in docs, logs, or chat
- ✅ Each tenant gets its own Secrets Manager key (or null if unconfigured)
- ✅ Disconnect clears/revokes the tenant's secret only
- ✅ Revocation marks status as `disconnected` without exposing token data

### Migration Path (Existing tog_and_dogs)

1. Current: global `{prefix}/google/user-tokens` stores tog_and_dogs tokens
2. Future: rename/move to `{prefix}/calendar/tog_and_dogs/tokens`
3. New tenants: create `{prefix}/calendar/{company_id}/tokens` on first connect
4. Handler reads `tenant.calendar_secret_ref` to know which secret to use

---

## 5. UI Behavior Recommendations

### Unconfigured Tenant (No Provider Connected)

```
┌─────────────────────────────────────────────┐
│ 📅 Calendar Integration                     │
│                                             │
│ Calendar sync is not configured for your    │
│ business yet.                               │
│                                             │
│ Connect a calendar to automatically sync    │
│ your scheduled visits.                      │
│                                             │
│ [Connect Google Calendar]  (if enabled)     │
│ [Connect Outlook]          (future)         │
│                                             │
│ ℹ️ Available on Professional plan and above │
└─────────────────────────────────────────────┘
```

### Connected Tenant

```
┌─────────────────────────────────────────────┐
│ 📅 Calendar Integration                     │
│                                             │
│ ✅ Connected: Google Calendar               │
│ Last synced: Jun 28, 2026                   │
│                                             │
│ [Disconnect]                                │
└─────────────────────────────────────────────┘
```

### Disabled/Blocked Tenant

No calendar card shown (entire admin is blocked by disabled-tenant enforcement).

### Key UI Principles

- Do NOT show "Google Calendar" text when provider is `none`
- Do NOT show browser alert/popup for unsupported provider
- Show "not configured" as a calm informational state, not an error
- Provider selector only shows options enabled for the tenant's tier
- Starter tier: calendar card shows "upgrade required" or is hidden

---

## 6. Operational Behavior

| Scenario | Behavior |
|----------|----------|
| Disabled tenant tries to connect calendar | Blocked by `require_active_tenant()` (20E) |
| Disabled tenant calendar sync attempted | Skipped (no active access) |
| Platform admin views tenant calendar status | Shows provider + connection status |
| Tenant owner connects calendar | Allowed if tier permits + status is active |
| Tenant owner disconnects calendar | Clears/revokes token secret, sets status to disconnected |
| Health check for unconfigured tenant | Skipped (nothing to check) |
| Audit on connect/disconnect | PLATFORM_AUDIT record (or tenant-level audit) |

---

## 7. Provider-Specific Notes

### Google Calendar (Current — Partially Implemented)

- OAuth 2.0 with refresh token
- Full CRUD: create, update, delete events
- Requires per-tenant token isolation before second tenant can use it
- Existing implementation works for tog_and_dogs only
- 19K tactical fix returns "not configured" for non-tog_and_dogs tenants

### Microsoft Outlook / Microsoft 365

- Microsoft Graph API (OAuth 2.0 with delegated permissions)
- Full CRUD: create, update, delete events
- Requires Azure AD app registration
- Refresh token flow similar to Google
- Good fit for businesses using Microsoft ecosystem
- Likely second provider to implement

### CalDAV (Yahoo, iCloud, Self-Hosted)

- Standard protocol (RFC 4791)
- Works with Yahoo Calendar, iCloud, Nextcloud, etc.
- Auth: username + app-specific password (less user-friendly than OAuth)
- Support burden higher (many server implementations, varied compliance)
- Good "catch-all" for non-Google/non-Microsoft users

### ICS Feed (Read-Only)

- Simple: generate an ICS URL that external calendars can subscribe to
- Read-only: external calendar polls for updates, cannot write back
- Lowest effort to implement
- Useful as "view my schedule in any calendar app" fallback
- Does NOT sync new events from the calendar back to the platform

---

## 8. Recommended Release Sequence

| Release | Scope | Priority |
|---------|-------|----------|
| **21A** | Multi-provider calendar strategy (this document) | ✅ Done |
| **21B** | Calendar UI unconfigured-state cleanup (remove popup, show calm "not configured" card) | Medium |
| **21C** | Tenant calendar provider metadata model (add fields to TENANT record) | Medium |
| **21D** | Google Calendar per-tenant token isolation (migrate tog_and_dogs, enable for new tenants) | High (before second tenant uses calendar) |
| **21E** | Google Calendar enablement for test_tenant_alpha (sandbox validation) | Medium |
| **21F** | Microsoft Outlook / Graph provider planning | Low (future demand) |
| **Future** | CalDAV generic adapter | Low |
| **Future** | ICS feed export | Low |

---

## 9. What This Document Does NOT Authorize

- ❌ Code changes
- ❌ Connecting calendars for any tenant
- ❌ Creating OAuth apps (Google, Microsoft, etc.)
- ❌ Modifying Secrets Manager
- ❌ Modifying tenant metadata
- ❌ DynamoDB writes
- ❌ Terraform/AWS changes
- ❌ Deployment
- ❌ Stripe/payment changes
- ❌ Cognito changes
- ❌ Mobile/TestFlight/App Store changes
- ❌ Ryan/tester changes

This is a strategy document. Implementation (21B+) requires separate approval.
