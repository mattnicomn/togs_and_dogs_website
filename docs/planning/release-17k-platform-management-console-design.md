# Release 17K: Platform Management Console Design

**Status:** Design Complete
**Date:** 2026-06-21
**Priority:** High (enables scalable tenant management without developer intervention)
**Scope:** Design a secure usmissionhero-only Platform Management Console for multi-tenant operations

---

## 1. User Roles and Access Model

### Role Hierarchy

| Role | Scope | Access To |
|------|-------|-----------|
| `platform_admin` | Platform-wide (usmissionhero operator) | All tenants, entitlements, billing config, platform settings |
| `business_owner` | Single tenant | Own business dashboard, staff, clients, bookings, payments |
| `staff` | Single tenant (limited) | Assigned visits, schedule, notes |
| `client` | Single tenant (limited) | Own bookings, pet details |

### Platform Admin vs Tenant Admin

| Dimension | Platform Admin | Tenant Admin (Business Owner) |
|-----------|----------------|-------------------------------|
| Who | Matthew / usmissionhero operators | Ryan / pet business owners |
| URL | `/platform-admin` (separate route/area) | `/admin` (existing dashboard) |
| Access method | Cognito group: `platform_admin` | Cognito group: `owner` or `admin` |
| Sees | All tenants, all tiers, all entitlements | Only own business data |
| Can modify | Tenant tier/status, limits, overrides | Own bookings, staff, clients |
| Cannot do | Edit raw DynamoDB, modify Cognito pools | See other tenants, change own tier |

### Authorization Model

```
Request → API Gateway → Cognito → Lambda
                                    ↓
                         get_effective_role(event)
                                    ↓
                    if role == 'platform_admin':
                        → allow platform management routes
                    else:
                        → standard tenant-scoped access
```

Platform admin routes MUST check for `platform_admin` role explicitly. Standard admin/owner role is NOT sufficient for platform management.

---

## 2. MVP Platform Management Console Features

### Tenant List View

| Feature | Priority | Notes |
|---------|----------|-------|
| List all tenants | ✅ MVP | Display name, tier, status, created date |
| Search/filter tenants | ✅ MVP | By name, tier, status |
| Tenant count badge | ✅ MVP | "3 tenants" |
| Quick status indicators | ✅ MVP | Green (active), yellow (past_due), red (canceled) |

### Tenant Detail View

| Feature | Priority | Notes |
|---------|----------|-------|
| Tenant profile (name, company_id, owner email) | ✅ MVP | Read-only in MVP |
| Subscription tier + status | ✅ MVP | Editable |
| Entitlement summary (limits + feature flags) | ✅ MVP | Derived from tier |
| Staff count / client count / booking count | ✅ MVP | Read-only usage metrics |
| Google Calendar connection status | ✅ MVP | Read-only |
| Payment/notification health | ⏳ Later | Nice-to-have |
| Recent entitlement denials (from logs) | ⏳ Later | After 17J logging works |

### Editable Fields (MVP)

| Field | Editable? | Validation |
|-------|-----------|------------|
| `display_name` | ✅ Yes | Non-empty string, max 100 chars |
| `subscription_tier` | ✅ Yes | One of: starter, professional, premium, enterprise |
| `subscription_status` | ✅ Yes | One of: active, trialing, past_due, canceled, paused, disabled |
| `admin_override_until` | ✅ Yes | ISO timestamp or null (courtesy extension) |
| Platform admin notes | ✅ Yes | Free text, internal only |

### NOT Editable in MVP

| Item | Reason |
|------|--------|
| TIER_LIMITS definitions | Code-level config; not safe for runtime editing |
| Stripe live keys / secrets | Security — never exposed in UI |
| Cognito user attributes | Separate admin flow |
| Raw DynamoDB records | Use structured APIs only |
| Client/staff private data | Privacy; use tenant admin for that |
| Tenant deletion | Destructive; defer to later with safeguards |
| `company_id` (immutable) | Primary key; never changes |

---

## 3. Backend/API Requirements

### New Routes (Platform Admin Only)

| Route | Method | Purpose | Auth |
|-------|--------|---------|------|
| `/platform/tenants` | GET | List all tenants | `platform_admin` only |
| `/platform/tenants/{company_id}` | GET | Get tenant detail + usage | `platform_admin` only |
| `/platform/tenants/{company_id}` | PATCH | Update tier/status/notes | `platform_admin` only |
| `/platform/audit` | GET | View platform audit log | `platform_admin` only |

### Authorization Enforcement

```python
def require_platform_admin(event):
    role = get_effective_role(event)
    if role != 'platform_admin':
        raise PermissionError("Platform admin access required")
```

This is separate from the existing `require_owner_or_admin` check — platform admin is a higher privilege level.

### Tenant Isolation Preservation

- Platform admin can READ any tenant's metadata
- Platform admin can UPDATE tier/status/override for any tenant
- Platform admin CANNOT impersonate a tenant's users
- Platform admin CANNOT access client/staff private data through this UI
- All platform admin actions write to a separate audit log

### Audit Requirements

Every PATCH to tenant metadata writes:

```json
{
  "PK": "PLATFORM_AUDIT",
  "SK": "ACTION#{timestamp}#{action_id}",
  "action": "tenant_tier_change",
  "actor": "platform_admin_sub",
  "target_company_id": "tog_and_dogs",
  "changes": {
    "subscription_tier": { "from": "starter", "to": "professional" }
  },
  "timestamp": "ISO"
}
```

### Validation Rules

| Change | Validation |
|--------|------------|
| Tier change | Must be one of TIER_LIMITS keys |
| Status change | Must be one of known statuses |
| Override extension | Must be future ISO timestamp |
| Display name | Non-empty, max 100 chars |

---

## 4. Frontend/UI Requirements

### Separate Platform Admin Area

| Aspect | Decision |
|--------|----------|
| URL path | `/platform-admin` |
| Navigation | Completely separate from `/admin` business dashboard |
| Access | Only visible/accessible if user has `platform_admin` Cognito group |
| Styling | Can reuse existing design system; add "Platform" badge/header |

### Pages

| Page | Components |
|------|------------|
| Tenant List | Table with search/filter, tier badge, status badge, row click → detail |
| Tenant Detail | Profile card, entitlement summary, usage stats, edit form |
| Edit Tenant | Modal or inline form for tier/status/override/notes, confirmation prompt |
| Audit Log | Read-only table of recent platform admin actions |

### UX Safety

| Rule | Implementation |
|------|---------------|
| Confirmation before tier/status change | Modal: "Change subscription_tier from Professional to Starter?" |
| Warning for downgrade | "Downgrading may restrict staff limit. Current staff count: 3/5 → new limit: 1." |
| Warning for status change to canceled/disabled | "This will block tenant login. Are you sure?" |
| No destructive delete action | Tenant deletion not available in MVP |

---

## 5. Data Model Impacts

### Current Tenant Metadata (Sufficient for MVP)

The existing `TENANT#{company_id} / METADATA` record already contains:
- `company_id`, `display_name`, `owner_email`
- `subscription_tier`, `subscription_status`
- `limits`, `feature_flags`
- `admin_override_until`
- `created_at`, `updated_at`

**No new DynamoDB record type needed for basic tenant management.** The existing metadata record is the source of truth.

### New: Platform Audit Log

```
PK: PLATFORM_AUDIT
SK: ACTION#{iso_timestamp}#{uuid}
```

New record type for tracking all platform admin changes. Does not exist yet — must be created in 17L.

### Usage Metrics (Read-Only Queries)

To display staff/client/booking counts per tenant:
- Staff count: `query(PK=COMPANY#{company_id}, SK begins_with STAFF#, Select=COUNT)`
- Client count: `query(PK=COMPANY#{company_id}, SK begins_with CLIENT#, Select=COUNT)`
- Booking count: `query with filter on company_id` (or index if available)

These are read-only queries — no new records needed.

### Feature Override (Deferred)

Per-tenant feature overrides (e.g., enable export for a specific starter tenant) could be implemented as:
```json
{
  "feature_overrides": {
    "export_enabled": true  // Override tier default
  }
}
```

**Deferred to later release.** MVP uses tier-derived limits only.

---

## 6. Security and Tenant Isolation Risks

| Risk | Mitigation |
|------|------------|
| Platform admin accidentally downgrades active tenant | Confirmation modal + audit log |
| Platform admin sees client private data | Platform routes return only tenant metadata, not client/staff details |
| Unauthorized access to platform routes | Strict `platform_admin` role check; 403 for all others |
| Tenant impersonation | Platform admin cannot log in as a tenant user |
| Audit log tampering | Audit records are append-only; no delete API |
| Tier change breaks active operations | Warning message shows current usage vs new limits |
| Status change to disabled blocks real users | Requires explicit confirmation + "Are you sure?" |

---

## 7. Cognito Group: `platform_admin`

### Requirements

- A new Cognito group `platform_admin` must exist
- Only Matthew's admin account should be in this group initially
- This group grants access to `/platform/*` routes
- Standard `owner`/`admin` groups do NOT have platform admin access
- Platform admin can also access standard admin routes (superset)

### Implementation

```python
def get_effective_role(event):
    groups = get_user_groups(event)
    if 'platform_admin' in groups:
        return 'platform_admin'
    if 'owner' in groups:
        return 'owner'
    # ... existing logic
```

---

## 8. Recommended Release Sequence

| Release | Scope | Owner | Effort |
|---------|-------|-------|--------|
| **17K** | Platform Management Console design (this document) | ✅ Kiro (done) | — |
| **17L** | Platform Admin backend APIs + Cognito group + audit log | AG | High |
| **17M** | Platform Management frontend UI MVP | AG | Medium |
| **17N** | Second-tenant creation through Platform Admin | AG | Medium |
| **17O** | Phase 2 entitlement gates (client limit, booking limit) | AG | Medium |
| **17P** | Business owner upgrade/limit messaging UI | AG | Low |

---

## 9. What This Document Does NOT Authorize

- ❌ Code changes
- ❌ Creating Cognito groups
- ❌ Creating API routes
- ❌ Building UI pages
- ❌ Modifying DynamoDB
- ❌ Terraform changes
- ❌ Stripe/Postmark/mobile changes
- ❌ Creating a second tenant
- ❌ Modifying tenant metadata
- ❌ Adding Ryan

This is a design document. Implementation begins with Release 17L (requires separate approval).
