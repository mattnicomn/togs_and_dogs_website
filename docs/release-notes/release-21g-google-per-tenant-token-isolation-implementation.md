# Release 21G — Google Per-Tenant Token Isolation Implementation

Release **21G** implements backend support for per-tenant Google Calendar token isolation. It scopes Google OAuth token reads and writes to dedicated tenant-specific secret paths while maintaining compatability fallback mode for the `tog_and_dogs` legacy global secret to ensure zero downtime or migration risk.

---

## Accomplishments

### 1. Per-Tenant Google Secret Path Resolver
- Created `resolve_google_token_secret_name(company_id)` in [google_calendar.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/common/google_calendar.py).
- Resolves token paths by checking:
  1. Explicit `calendar_secret_ref` configured in tenant metadata.
  2. Legacy global secret fallback (`GOOGLE_USER_TOKENS_NAME`) for the default tenant `tog_and_dogs` when no explicit reference is configured.
  3. Dynamic per-tenant secret path `{prefix}/calendar/{company_id}/tokens` for active tenants with Google Calendar integration enabled.
- Created `get_tenant_secret_path(company_id)` to parse the environment prefix (e.g. `togs-and-dogs-prod`) and return `{prefix}/calendar/{company_id}/tokens`.

### 2. Multi-Tenant Token Read/Write Helpers
- Updated `_get_stored_tokens`, `_save_tokens`, and `_mark_token_revoked` to utilize `resolve_google_token_secret_name` and accept `company_id`.
- Updated `sync_calendar_event` to skip calendar syncing gracefully if the tenant's secret cannot be resolved, ensuring no accidental sync errors or invalid connections.

### 3. Tenant-Scoped Google Auth Handlers
- **Token Helpers:** Updated `get_stored_tokens` and `save_tokens` in [google_auth_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/google_auth_handler.py) to accept `company_id` and resolve per-tenant token secret paths.
- **Connection status & health checks:** Updated `get_status` and `calendar_health_check` to resolve company context and pass it to token operations.
- **Google connection flows:** Gated `initiate_auth` and `handle_callback` using `resolve_google_token_secret_name` to reject requests from tenants that are not configured with Google integration.
- **OAuth callback:** Correctly parses the tenant context from the state record mapped in DynamoDB and writes exchanged tokens to the resolved per-tenant path.
- **Disconnect protection:** Updated `disconnect_auth` to only clear per-tenant secret paths and never delete or mutate the legacy global secret fallback `GOOGLE_USER_TOKENS_NAME` if used by `tog_and_dogs`.

### 4. Unit and Regression Testing
- Created a new test suite [test_r21g_google_token_isolation.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r21g_google_token_isolation.py) with 8 test cases verifying:
  - Default tenant `tog_and_dogs` legacy fallback.
  - Per-tenant secret path derivation.
  - Gated connection initiation/callback for non-configured tenants.
  - Scoped token writes and OAuth callback handling.
  - Safe disconnect behavior preserving legacy global secrets.
  - Gating of disabled tenant endpoints via `require_active_tenant`.
  - Non-exposure of raw tokens/secrets in API payloads.
- Verified that all 110 backend test cases pass successfully.

---

## Overall Status: ✅ PASS (Implementation Pre-Deploy Checkpoint Complete)

All backend implementation, secret routing helpers, security gating, and test suites have passed. Ready for deployment approval.
