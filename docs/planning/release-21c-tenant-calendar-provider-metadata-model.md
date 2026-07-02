# Release 21C: Tenant Calendar Provider Metadata Model

**Status:** Planning
**Date:** 2026-06-28
**Priority:** Medium (foundation for per-tenant calendar support)
**Scope:** Define metadata fields, enums, defaults, secret reference pattern, and behaviors

---

## 1. Tenant Metadata Fields

### New Calendar Fields on `TENANT#{company_id} / METADATA`

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
    "read_events": false,
    "disconnect_supported": false
  }
}
```

### Field Specifications

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `calendar_provider` | String (enum) | Yes | Identifies which provider/adapter to use |
| `calendar_enabled` | Boolean | Yes | Whether tier allows calendar integration |
| `calendar_connection_status` | String (enum) | Yes | Current connection health |
| `calendar_connected_account_label` | String or null | No | Safe display label (no tokens/secrets) |
| `calendar_last_check_at` | ISO timestamp or null | No | Last automated health check time |
| `calendar_secret_ref` | String or null | No | Secrets Manager key path (NOT the secret value) |
| `calendar_capabilities` | Object | Yes | What operations the connected provider supports |

---

## 2. Enum Values

### `calendar_provider`

| Value | Meaning | When Used |
|-------|---------|-----------|
| `none` | No provider configured | Default for new tenants |
| `google` | Google Calendar (OAuth 2.0) | tog_and_dogs current; future tenants choosing Google |
| `microsoft` | Microsoft Outlook / 365 (Graph API) | Future |
| `caldav` | Generic CalDAV (Yahoo, iCloud, Nextcloud) | Future |
| `ics_feed` | Read-only ICS feed export | Future |

### `calendar_connection_status`

| Value | Meaning | Transition From |
|-------|---------|-----------------|
| `not_configured` | No provider selected or setup started | Initial state |
| `not_connected` | Provider selected but OAuth/auth not completed | After provider selection |
| `connected` | Active, healthy connection | After successful auth |
| `needs_reconnect` | Token expired/revoked; re-auth needed | Health check failure |
| `error` | Unexpected failure state | API errors |
| `disabled` | Calendar explicitly disabled by platform admin | Admin action |

### `calendar_capabilities` Flags

| Flag | Type | Purpose |
|------|------|---------|
| `create_events` | Boolean | Can create new calendar events |
| `update_events` | Boolean | Can modify existing events |
| `delete_events` | Boolean | Can remove events on cancellation |
| `read_events` | Boolean | Can read calendar events |
| `disconnect_supported` | Boolean | Can cleanly disconnect/revoke |

### Capability Defaults by Provider

| Provider | create | update | delete | read | disconnect |
|----------|--------|--------|--------|------|------------|
| `none` | false | false | false | false | false |
| `google` | true | true | true | true | true |
| `microsoft` | true | true | true | true | true |
| `caldav` | true | true | true | true | true |
| `ics_feed` | false | false | false | true | true |

---

## 3. Default Values

### tog_and_dogs (Existing Tenant — Backfill)

```json
{
  "calendar_provider": "google",
  "calendar_enabled": true,
  "calendar_connection_status": "connected",
  "calendar_connected_account_label": "Google Calendar (connected)",
  "calendar_last_check_at": "<last known health check>",
  "calendar_secret_ref": "togs-and-dogs-prod/google/user-tokens",
  "calendar_capabilities": {
    "create_events": true,
    "update_events": true,
    "delete_events": true,
    "read_events": true,
    "disconnect_supported": true
  }
}
```

**Note:** `calendar_secret_ref` points to the EXISTING global Secrets Manager key. This preserves current behavior without migration until per-tenant isolation is implemented (21F/21G).

### test_tenant_alpha (Current — No Calendar)

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
    "read_events": false,
    "disconnect_supported": false
  }
}
```

### Future New Tenants (Default)

Same as test_tenant_alpha above. Provider is `none`, status is `not_configured`, everything is disabled.

---

## 4. Migration / Backfill Strategy

### Approach: Code-Level Defaults + Optional DynamoDB Update

| Option | Description | Recommendation |
|--------|-------------|----------------|
| A: Backfill DynamoDB immediately | Write calendar fields to both tenant records | ⚠️ Requires DynamoDB write approval |
| B: Code defaults with graceful absence | If calendar fields missing, derive from existing behavior | ✅ **Recommended MVP** |
| C: Backfill on next Platform Admin edit | Fields populated when tenant is next modified | ✅ Acceptable supplement |

### Recommended: Option B (Code Defaults)

```python
def get_tenant_calendar_config(tenant_record):
    """Derive calendar config from tenant metadata, with safe defaults."""
    provider = tenant_record.get('calendar_provider')
    
    if provider:
        # New model: explicit fields
        return {
            'provider': provider,
            'enabled': tenant_record.get('calendar_enabled', False),
            'status': tenant_record.get('calendar_connection_status', 'not_configured'),
            'secret_ref': tenant_record.get('calendar_secret_ref'),
            'capabilities': tenant_record.get('calendar_capabilities', {}),
        }
    
    # Legacy fallback: tog_and_dogs without explicit calendar fields
    company_id = tenant_record.get('company_id')
    if company_id == 'tog_and_dogs':
        return {
            'provider': 'google',
            'enabled': True,
            'status': 'connected',  # Assume connected; health check confirms
            'secret_ref': 'togs-and-dogs-prod/google/user-tokens',
            'capabilities': {'create_events': True, 'update_events': True, 'delete_events': True, 'read_events': True, 'disconnect_supported': True},
        }
    
    # All other tenants: not configured
    return {
        'provider': 'none',
        'enabled': False,
        'status': 'not_configured',
        'secret_ref': None,
        'capabilities': {},
    }
```

### Key Rules

- ❌ No raw calendar tokens stored in DynamoDB
- ❌ No tokens/passwords in docs, logs, or chat
- ❌ No shared global secret for multiple tenants (future: per-tenant keys)
- ✅ `calendar_secret_ref` stores only the Secrets Manager key PATH (not the secret value)
- ✅ Existing tog_and_dogs Google connection continues working unchanged

---

## 5. Per-Tenant Secret Reference Pattern

### Naming Convention

```
Existing (legacy):
  togs-and-dogs-prod/google/user-tokens         ← tog_and_dogs only

Future (per-tenant):
  togs-and-dogs-prod/calendar/tog_and_dogs/tokens
  togs-and-dogs-prod/calendar/test_tenant_alpha/tokens
  togs-and-dogs-prod/calendar/<company_id>/tokens
```

### Behavior

| Action | Secret Effect |
|--------|--------------|
| Connect | Create/update secret at `calendar_secret_ref` path |
| Disconnect | Clear/delete secret at `calendar_secret_ref` path |
| Reconnect | Overwrite existing secret with new tokens |
| Health check | Read secret; if invalid, mark `needs_reconnect` |
| Revoke | Delete secret; set status to `not_connected` |

### Migration from Legacy to Per-Tenant (21F/21G)

1. tog_and_dogs continues using `togs-and-dogs-prod/google/user-tokens`
2. When per-tenant isolation is implemented, copy to `togs-and-dogs-prod/calendar/tog_and_dogs/tokens`
3. Update `calendar_secret_ref` on tog_and_dogs metadata
4. Remove global key reference from handler code
5. New tenants always use per-tenant path

---

## 6. Platform Admin Behavior

### View

| Field | Visible? | Notes |
|-------|----------|-------|
| `calendar_provider` | ✅ | Show provider name |
| `calendar_connection_status` | ✅ | Badge/label |
| `calendar_connected_account_label` | ✅ | Safe display string |
| `calendar_last_check_at` | ✅ | Timestamp |
| `calendar_secret_ref` | ⚠️ Show key name only | Never show secret value |
| `calendar_capabilities` | ✅ | Feature flags |
| Raw tokens/secrets | ❌ Never | Security boundary |

### Future Edit (Platform Admin)

- Set `calendar_enabled` (enable/disable calendar for tenant tier)
- Set `calendar_provider` (select provider)
- Trigger disconnect (clear secret_ref + set status)
- Cannot directly set tokens (only connect flow does this)

---

## 7. Tenant Owner/Admin Behavior

### When Calendar NOT Configured

- See "Calendar integration is not configured" card (21B — already done)
- If tier allows: see "Connect [Provider]" button
- If tier blocks: see "Upgrade required" message

### When Calendar IS Connected

- See provider name + connected label
- See "Disconnect" button
- See last sync status
- Cannot see raw tokens/secrets

### Connect Flow (Future)

1. Owner clicks "Connect Google Calendar" (or Microsoft, etc.)
2. Backend validates: tenant active + tier allows + provider supported
3. Redirect to provider OAuth
4. Callback stores tokens in per-tenant secret
5. Update metadata: status=connected, secret_ref=path, capabilities=provider defaults
6. Audit record created

---

## 8. Disabled-Tenant Behavior

| Action | Allowed? |
|--------|----------|
| View calendar status | ❌ (entire admin blocked by 20E enforcement) |
| Connect calendar | ❌ Blocked |
| Disconnect calendar | ❌ Blocked |
| Calendar sync (create/update/delete events) | ❌ Skipped |
| Health check | ⚠️ May run but result is informational only (tenant can't act) |

---

## 9. Recommended Release Sequence

| Release | Scope | Owner |
|---------|-------|-------|
| **21C** | Calendar metadata model design (this document) | ✅ Kiro (done) |
| **21D** | Calendar metadata implementation (code-level defaults, no DynamoDB writes) | AG |
| **21E** | Metadata deployment + validation (verify tog_and_dogs derives correct config, test_tenant_alpha shows not_configured) | AG + Matthew |
| **21F** | Google per-tenant token isolation plan | Kiro |
| **21G** | Google per-tenant token isolation implementation | AG |
| **21H** | Controlled Google Calendar enablement for test_tenant_alpha (if approved) | AG + Matthew |
| **Future** | Microsoft provider planning | Kiro |

---

## 10. What This Document Does NOT Authorize

- ❌ Code changes
- ❌ DynamoDB writes / metadata updates
- ❌ Secrets Manager changes
- ❌ Connecting any calendar for any tenant
- ❌ Creating/modifying tokens
- ❌ Terraform/AWS changes
- ❌ Deployment
- ❌ Cognito changes
- ❌ Stripe changes
- ❌ Mobile/TestFlight/App Store changes
- ❌ Ryan/tester changes
- ❌ Disabling or modifying tenants

This is a data model design document. Implementation (21D) requires separate approval.
