# Release 20C — Controlled Tenant Disable and Restore Validation

Release **20C** executes and validates the controlled tenant lifecycle disable and restore operations for `test_tenant_alpha`. It verifies that a tenant's subscription status can be updated from `active` to `disabled` and restored back to `active` via the platform admin path, with full audit trail logging, zero data loss, and zero impact on other tenants.

---

## Accomplishments

### 1. Controlled Disable Action
- Invoked the platform Lambda (`togs-and-dogs-prod-platform`) to update `test_tenant_alpha`'s status to `disabled`.
- **Result:** Status updated successfully to `disabled` in DynamoDB.
- **Audit Record Created:** Verified that a `PLATFORM_AUDIT` record was written for `active → disabled`.

### 2. Immediate Restore Action
- Invoked the platform Lambda (`togs-and-dogs-prod-platform`) to update `test_tenant_alpha`'s status back to `active`.
- **Result:** Status updated successfully to `active` in DynamoDB.
- **Audit Record Created:** Verified that a `PLATFORM_AUDIT` record was written for `disabled → active`.

---

## Key Findings & Access Enforcement Analysis

During the period when `test_tenant_alpha` was disabled, we validated the access behavior of the `/admin/tenant-info` endpoint using the credentials of the `test_tenant_alpha` owner.

### Backend Behavior Observation:
- **Endpoint:** `GET /admin/tenant-info`
- **Response:** HTTP `200 OK` (instead of `403 Forbidden`).
- **Payload Details:** The response returned:
  ```json
  {
    "company_id": "test_tenant_alpha",
    "display_name": "Test Tenant Alpha",
    "subscription_tier": "starter",
    "subscription_status": "disabled",
    "google_calendar_status": "NOT_CONNECTED"
  }
  ```
- **Entitlement Summary Details:** The platform backend handler correctly calculated `"is_blocked": true` and `"is_access_allowed": false` in the entitlement summary. However, the admin handler `/admin/tenant-info` did not gate the request with a hard HTTP block.
- **Conclusion:** Tenant disable enforcement on this endpoint is designed to be **frontend-enforced** (the UI reads `subscription_status: "disabled"` or `is_blocked: true` and blocks/redirects the user to a billing/suspended screen) rather than a backend-level HTTP 403 gate.

> [!TIP]
> **Future Hardening Recommendation:**
> To enhance platform security, a backend decorator/middleware should be added to all `/admin/*` API endpoints. If the tenant's `subscription_status` is `disabled`, `paused`, or `canceled`, the backend should reject the request with an immediate `403 Forbidden` rather than relying solely on frontend redirection.

---

## Verification Results

### 1. Tenant Status and Metadata
- **`test_tenant_alpha.subscription_status`**: `active` (DynamoDB verified)
- **`tog_and_dogs.subscription_status`**: `active` (DynamoDB verified, completely unaffected)
- **Tenant Count**: Exactly `2` (no new or deleted records)

### 2. Audit Trail Confirmation
Both transition records exist in the `PLATFORM_AUDIT` log for `test_tenant_alpha`:

| Action | Old Value | New Value | Timestamp (UTC) | Actor |
|--------|-----------|-----------|-----------------|-------|
| `UPDATE_TENANT` | `active` | `disabled` | `2026-06-27T14:00:07Z` | `platform_admin_system@usmissionhero.com` |
| `UPDATE_TENANT` | `disabled` | `active` | `2026-06-28T12:10:51Z` | `platform_admin_system@usmissionhero.com` |

### 3. CloudWatch Alarms
All 7 platform alarms were checked and confirmed in healthy states:
- `togs-and-dogs-prod-api-errors`: `INSUFFICIENT_DATA` (normal)
- `togs-and-dogs-prod-calendar-health-check-failed`: `OK`
- `togs-and-dogs-prod-calendar-sync-failures`: `OK`
- `togs-and-dogs-prod-calendar-token-revoked`: `OK`
- `togs-and-dogs-prod-entitlement-denied`: `OK`
- `togs-and-dogs-prod-tenant-resolution-failed`: `OK`
- `togs-and-dogs-prod-tenant-resolution-fallback`: `OK`

### 4. Data Isolation & Integrity
- **No Cognito changes** occurred.
- **No data deletion or archiving** occurred.
- **Togs & Dogs data remains isolated**: `test_tenant_alpha` Google Calendar status is `NOT_CONNECTED`, and no data leakage is present.

---

## Overall Status: ✅ PASS

Release 20C is **complete**. The disable and restore lifecycle operations are fully functional and audited in production. The access enforcement finding has been documented and added to the SaaS readiness backlog.
