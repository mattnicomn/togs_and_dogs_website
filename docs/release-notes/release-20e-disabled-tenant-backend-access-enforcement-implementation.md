# Release 20E — Disabled Tenant Backend Access Enforcement Implementation

Release **20E** implements centralized backend disabled-tenant access enforcement. It ensures that tenant-scoped routes are consistently blocked with a `403 TenantDisabled` response when a tenant's subscription is inactive or disabled, while preserving the public routes, platform admin routes, and a minimal safe `/admin/tenant-info` endpoint.

---

## Accomplishments

### 1. Centralized Disabled-Tenant Enforcement Helper
- Created `require_active_tenant(event)` in [entitlement.py](file:///C:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/common/entitlement.py).
- The helper resolves the company context via `get_current_company_id(event)`, bypasses enforcement for `platform_admin` callers or root admin bypasses, loads the tenant's entitlement metadata from DynamoDB, and blocks disabled/inactive tenants with a consistent `403 TenantDisabled` response.

### 2. Special-Case `/admin/tenant-info` Endpoint
- Updated [admin_handler.py](file:///C:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/admin_handler.py) to handle `/admin/tenant-info` as a special case when a tenant is disabled.
- It returns `200 OK` with only safe fields (`company_id`, `display_name`, `subscription_status`, `is_access_allowed = False`, `is_blocked = True`) and skips the Google Calendar status check and any other operational data retrieval.

### 3. Handler Integration
Applied the `require_active_tenant(event)` check as the first post-auth check in the following tenant-scoped backend handlers:
- **`admin_handler.py`** (all routes except `/admin/tenant-info`)
- **`assignment_handler.py`**
- **`cancellation_handler.py`**
- **`device_handler.py`**
- **`google_auth_handler.py`** (excluding EventBridge/scheduled health checks)
- **`intake_handler.py`**
- **`pet_handler.py`**
- **`review_handler.py`**

### 4. Comprehensive Test Suite
- Created a new test file [test_r20e_disabled_tenant_enforcement.py](file:///C:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r20e_disabled_tenant_enforcement.py).
- Verified active tenant access, disabled tenant blocking, minimal status response on `/admin/tenant-info`, platform admin bypasses, and EventBridge scheduler bypasses.
- **Test Result**: `14 passed in 1.19s` ✅
- **Regression Result**: `51 passed in 1.66s` (including tenant isolation and entitlement tests) ✅

---

## Response Contract for Disabled Tenants
When a tenant is disabled, all protected endpoints return:
* **HTTP Status**: `403 Forbidden`
* **Response Body**:
  ```json
  {
    "error": "TenantDisabled",
    "message": "Tenant is disabled"
  }
  ```

---

## Guardrails & Safety Confirmed
- **No production deployment** occurred.
- **No Terraform apply** occurred.
- **No AWS changes** occurred.
- **No tenant was disabled** or modified in production.
- **No production database writes** occurred.
- **No Cognito, Stripe, or Google Calendar** changes occurred.
