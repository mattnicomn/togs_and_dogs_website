# Release 21D — Tenant Calendar Provider Metadata Defaults Implementation

Release **21D** implements code-level tenant calendar provider metadata defaults and safe metadata response fields. It enables the system to reason about tenant calendar providers, statuses, and capabilities without requiring immediate DynamoDB backfills or Secrets Manager modifications.

---

## Accomplishments

### 1. Backend Calendar Metadata Helper
- Created [calendar_metadata.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/common/calendar_metadata.py) containing `get_tenant_calendar_config`.
- Derives the following metadata fields and enums safely:
  - `calendar_provider`: `"google"`, `"microsoft"`, `"caldav"`, `"ics_feed"`, or `"none"`
  - `calendar_enabled`: `True` / `False`
  - `calendar_connection_status`: `"not_configured"`, `"not_connected"`, `"connected"`, `"needs_reconnect"`, `"error"`, or `"disabled"`
  - `calendar_connected_account_label`: Displays safe provider labels without exposing secrets.
  - `calendar_secret_ref`: Naming path references (e.g. `"togs-and-dogs-prod/google/user-tokens"`).
  - `calendar_capabilities`: Provider-specific capability flags (`create_events`, `update_events`, `delete_events`, `read_events`, `disconnect_supported`).
- Fallback Defaults:
  - If missing calendar metadata fields, `tog_and_dogs` derives Google provider defaults and maps existing Google health-check connection status.
  - Non-default tenants (such as `test_tenant_alpha`) default to provider `"none"`, status `"not_configured"`, and all capabilities as `False`.

### 2. Tenant Info & Platform Admin API Hardening
- **`/admin/tenant-info`:** Updated `src/backend/handlers/admin_handler.py` to merge the derived calendar config into successful active tenant info payloads. Checked that disabled tenants continue to get the minimal safe response with no calendar fields exposed.
- **Platform Admin Tenant Detail:** Updated `src/backend/handlers/platform_handler.py` to include the calendar metadata defaults under the tenant's `profile` object, exposing only safe metadata fields.

### 3. Frontend UI Updates
- **Platform Tenant Detail View:** Updated [PlatformTenantDetail.jsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/PlatformTenantDetail.jsx) to display Calendar Provider, Status, Connected Account, and Secret Reference safely in the Metadata list.
- **Admin Dashboard Calendar card:** Updated [AdminDashboard.jsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/AdminDashboard.jsx) to use `tenantInfo.calendar_provider === 'google'` metadata checks instead of the hardcoded `company_id === 'tog_and_dogs'` checks. This ensures that non-default tenants with provider `"none"` (or future providers) are automatically shown the calm provider-neutral unconfigured status card and cannot trigger Google OAuth flows.

### 4. Verification and Regression Testing
- Created a new test suite [test_r21d_calendar_metadata_defaults.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r21d_calendar_metadata_defaults.py) with 7 test cases covering derivation, overrides, disabled tenant gating, API payload safety, and preservation.
- Ran all new and existing tests:
  - `test_r21d_calendar_metadata_defaults.py`: 7 passed
  - `test_r20e_disabled_tenant_enforcement.py`: 14 passed
  - `test_r19k_tenant_isolation.py`: 9 passed
  - `test_r17b_entitlement_enforcement.py`: 9 passed
  - `test_r6g_calendar_health.py`: 8 passed
- Verified that the Vite production build compiles successfully target `dist/assets/index-BJ8CeT-X.js`.

---

## Overall Status: ✅ PASS (Implementation Pre-Deploy Checkpoint Complete)

All implementation, compile checks, and regression tests have passed. Ready for deployment approval.
