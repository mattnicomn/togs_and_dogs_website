# Release 21F: Google Per-Tenant Token Isolation Plan

**Status:** Planning
**Date:** 2026-06-28
**Priority:** High (required before second tenant can use Google Calendar)
**Scope:** Design per-tenant Google token isolation without reading/modifying tokens

---

## 1. Current Google Calendar Token Model

### High-Level Architecture (No Secret Values Documented)

| Component | Current Behavior |
|-----------|-----------------|
| Token storage | Single global Secrets Manager key (shared across all code paths) |
| Token retrieval | `google_auth_handler.py` reads from environment-referenced secret name |
| Calendar sync | `common/google_calendar.py` uses retrieved tokens for API calls |
| Health check | EventBridge daily check validates token via refresh attempt |
| Token write | OAuth callback stores new tokens to the same global secret |
| Scope | Implicitly belongs to tog_and_dogs (only tenant with calendar) |

### Backend Locations That Use Google Calendar Tokens

| File | Operation | Token Usage |
|------|-----------|-------------|
| `google_auth_handler.py` | OAuth initiate, callback, status, disconnect, health check | Read/write tokens |
| `common/google_calendar.py` | Create/update/delete calendar events | Read tokens |
| `review_handler.py` | Triggers calendar sync on approval | Calls google_calendar |
| `assignment_handler.py` | Updates calendar event on staff assign | Calls google_calendar |
| `cancellation_handler.py` | Deletes calendar event on cancel | Calls google_calendar |
| `job_handler.py` | Creates per-day events for multi-day bookings | Calls google_calendar |

### Current Tenant Reliance

- **tog_and_dogs:** Actively uses the Google Calendar connection
- **test_tenant_alpha:** No calendar configured; code returns "not configured" (19K/21B fixes)

---

## 2. Target Per-Tenant Google Token Model

### Design Principles

| Principle | Implementation |
|-----------|---------------|
| One secret per tenant | Each tenant gets its own Secrets Manager key |
| No shared global secret for multi-tenant use | Legacy global key remains for tog_and_dogs until migrated |
| Token read/write scoped by company_id | Handler resolves `calendar_secret_ref` from tenant metadata |
| Secret path stored in metadata, not token value | `calendar_secret_ref` = key name only |
| Tenants cannot access each other's tokens | Handler reads only the current tenant's secret |

### Proposed Secret Naming Pattern

```
Legacy (current):
  togs-and-dogs-prod/google/user-tokens

Per-tenant (target):
  togs-and-dogs-prod/calendar/tog_and_dogs/tokens
  togs-and-dogs-prod/calendar/test_tenant_alpha/tokens
  togs-and-dogs-prod/calendar/<company_id>/tokens
```

### Token Resolution Flow (After Migration)

```
Request → get_current_company_id(event) → company_id
  → get_tenant_calendar_config(company_id) → calendar_secret_ref
  → Secrets Manager read(calendar_secret_ref) → tokens
  → Use tokens for Google API call
```

### What Changes in Code

| Current | Target |
|---------|--------|
| Handler reads hardcoded env var for secret name | Handler reads `calendar_secret_ref` from tenant config |
| One global secret for all calendar operations | Per-tenant secret resolved dynamically |
| OAuth callback writes to global secret | OAuth callback writes to tenant-specific secret |
| Health check reads global secret | Health check iterates configured tenants |

---

## 3. Migration Strategy Options

| Option | Description | Risk | Disruption | Recommendation |
|--------|-------------|------|-----------|----------------|
| **A: Keep legacy for tog_and_dogs until explicit migration** | Code supports both old (global) and new (per-tenant) paths | Low | Zero | ✅ **Recommended** |
| **B: Copy global secret to per-tenant path** | Duplicate the existing secret to the new naming pattern | Low | Low | ⚠️ Acceptable after A is working |
| **C: Require reconnect under new path** | tog_and_dogs owner re-authenticates; new tokens stored in per-tenant key | Medium | Medium (reconnect required) | ❌ Avoid unless forced |

### Recommendation: Option A (Compatibility Mode First)

```python
def get_calendar_secret_name(company_id, tenant_config):
    """Resolve the correct secret name for this tenant's calendar tokens."""
    # If tenant has explicit per-tenant ref, use it
    if tenant_config.get('calendar_secret_ref'):
        return tenant_config['calendar_secret_ref']
    
    # Legacy fallback: tog_and_dogs uses global secret
    if company_id == 'tog_and_dogs':
        return os.environ.get('GOOGLE_USER_TOKENS_NAME')
    
    # No secret configured for this tenant
    return None
```

**Phase 1 (21G/21H):** Deploy code that supports both paths. tog_and_dogs continues using global secret via fallback.

**Phase 2 (21I):** Optionally copy/migrate tog_and_dogs secret to per-tenant path, update metadata `calendar_secret_ref`, remove global fallback.

---

## 4. Connect / Reconnect / Disconnect Behavior

### Connect (New Tenant)

| Step | Action |
|------|--------|
| 1 | Verify: tenant active + tier allows calendar + provider not already connected |
| 2 | Generate OAuth URL with tenant-identifying state parameter |
| 3 | User approves in Google → redirect to callback |
| 4 | Callback resolves tenant from state parameter (NOT from shared session) |
| 5 | Store tokens in `{prefix}/calendar/{company_id}/tokens` |
| 6 | Update tenant metadata: `calendar_connection_status=connected`, `calendar_secret_ref=<path>` |
| 7 | Audit: record connect action |

### Reconnect (Expired/Revoked Token)

| Step | Action |
|------|--------|
| 1 | Same as Connect (OAuth flow) |
| 2 | Overwrite existing secret at same path |
| 3 | Update metadata: `calendar_connection_status=connected`, `calendar_last_check_at=now` |
| 4 | Audit: record reconnect action |

### Disconnect

| Step | Action |
|------|--------|
| 1 | Verify: tenant active + currently connected |
| 2 | Delete or clear secret at `calendar_secret_ref` path |
| 3 | Update metadata: `calendar_connection_status=not_connected`, `calendar_secret_ref=null` |
| 4 | Audit: record disconnect action |
| 5 | Future calendar sync attempts for this tenant return early (no secret) |

### Disabled Tenant

- Cannot connect: blocked by `require_active_tenant()` (20E)
- Cannot reconnect: same block
- Cannot disconnect: same block
- Calendar sync: skipped (entitlement check fails before sync attempt)

---

## 5. Validation Requirements

| # | Requirement |
|---|-------------|
| 1 | tog_and_dogs Google Calendar connection remains fully functional during and after migration |
| 2 | test_tenant_alpha remains "not configured" (no calendar connection) |
| 3 | Connecting Google for test_tenant_alpha remains blocked unless Matthew explicitly approves |
| 4 | No cross-tenant calendar status leakage (already fixed in 19K) |
| 5 | No cross-tenant event creation/update/delete |
| 6 | No raw tokens/secrets appear in CloudWatch logs |
| 7 | No tokens/secrets in DynamoDB, docs, or chat |
| 8 | Health check only checks tenants with `calendar_connection_status=connected` |
| 9 | Disconnect for one tenant does not affect another tenant's connection |
| 10 | OAuth callback correctly identifies which tenant initiated the flow |

---

## 6. Metadata Updates (When Calendar Is Enabled for a Tenant)

When a tenant successfully connects Google Calendar, their metadata should be:

```json
{
  "calendar_provider": "google",
  "calendar_enabled": true,
  "calendar_connection_status": "connected",
  "calendar_connected_account_label": "Google Calendar (connected)",
  "calendar_last_check_at": "<timestamp>",
  "calendar_secret_ref": "togs-and-dogs-prod/calendar/<company_id>/tokens",
  "calendar_capabilities": {
    "create_events": true,
    "update_events": true,
    "delete_events": true,
    "read_events": true,
    "disconnect_supported": true
  }
}
```

---

## 7. Platform Admin Behavior

| Action | Allowed? | Visible Data |
|--------|----------|--------------|
| View tenant calendar provider/status | ✅ | Provider name, status badge, connected label |
| View `calendar_secret_ref` path | ✅ | Key NAME only (never the token value) |
| Enable/disable calendar for tenant | ⏳ Future | Toggle calendar_enabled |
| Trigger disconnect | ⏳ Future | Platform admin can disconnect on behalf of tenant |
| View raw tokens | ❌ NEVER | Security boundary |
| Modify tokens directly | ❌ NEVER | Only OAuth flow writes tokens |

---

## 8. Tenant Owner Behavior

| Action | Allowed? |
|--------|----------|
| See "Connect Google Calendar" button (if tier allows) | ✅ |
| Complete OAuth flow → tokens stored per-tenant | ✅ |
| See connected status + account label | ✅ |
| Disconnect | ✅ |
| See raw tokens | ❌ Never |
| Access another tenant's calendar | ❌ Never (isolated by company_id) |

---

## 9. Recommended Release Sequence

| Release | Scope | Owner |
|---------|-------|-------|
| **21F** | Per-tenant token isolation plan (this document) | ✅ Kiro (done) |
| **21G** | Code implementation: per-tenant secret resolution + compatibility mode | AG |
| **21H** | Deployment + validation: tog_and_dogs still works, test_tenant_alpha stays not_configured | AG + Matthew |
| **21I** | Optional: migrate tog_and_dogs secret to per-tenant path (copy + update metadata) | AG + Matthew |
| **21J** | Controlled Google Calendar enablement for test_tenant_alpha (if Matthew approves) | AG + Matthew |
| **Future** | Microsoft Graph provider planning | Kiro |

---

## 10. What This Document Does NOT Authorize

- ❌ Code changes
- ❌ Reading, creating, modifying, deleting, or migrating calendar tokens/secrets
- ❌ Connecting Google Calendar for any tenant
- ❌ Modifying Secrets Manager
- ❌ Modifying tenant metadata
- ❌ DynamoDB writes
- ❌ Terraform/AWS changes
- ❌ Deployment
- ❌ Cognito changes
- ❌ Stripe changes
- ❌ Mobile/TestFlight/App Store changes
- ❌ Ryan/tester changes
- ❌ Microsoft/CalDAV/ICS implementation

This is a design document. Implementation (21G) requires separate approval.
