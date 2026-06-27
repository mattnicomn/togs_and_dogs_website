# Release 19I: Second-Tenant Owner Login Isolation Defect Triage

**Status:** Completed (Triage & Diagnosis)  
**Type:** Defect Triage / Security Audit  
**Date:** 2026-06-27  

---

## 1. Goal

During the manual verification checklist for **Release 19H** (Cognito owner user login under strict `TENANT_RESOLUTION_MODE=multi`), several critical multi-tenant isolation defects were identified when logged in as the new `test_tenant_alpha` owner user:
1.  The **Google Calendar integration card** incorrectly displayed as `CONNECTED` and exposed the main `tog_and_dogs` business connection.
2.  The **Request List sidebar / staff quick view** and **Staff Management** displayed staff and owner records belonging to `tog_and_dogs`.
3.  **Client Management** displayed client profiles belonging to `tog_and_dogs`.
4.  The **profile/company label** on the dashboard displayed `Tog and Dogs` instead of `Test Tenant Alpha`.

The goal of this release (**Release 19I**) is to perform a comprehensive, read-only backend and frontend source-code triage to identify the root causes for these isolation failures, categorize them by feature area, and draft remediation recommendations.

---

## 2. Environment Status & Guardrail Check

*   **git status Check:** Confirmed working tree is clean.
*   **Tenant Resolution Mode:** Strict mode remains active (`TENANT_RESOLUTION_MODE=multi` on all 13 backend Lambdas).
*   **Tenant Registry:** DynamoDB tenant registry remains at exactly `2` tenants (`tog_and_dogs` and `test_tenant_alpha`).
*   **Cognito Attributes:** The owner user `mattnico10@yahoo.com` remains active in Cognito, correctly scoped to `custom:company_id = test_tenant_alpha` and assigned only to the `owner` group.
*   **Production Safety:** No production data was modified, no Cognito users or groups were changed, and no test bookings or Stripe credentials were set up.

---

## 3. Defect Diagnosis & Root Causes

### A. Google Calendar Integration Card (`CONNECTED` status)
*   **Observed Behavior:** The status card for `test_tenant_alpha` showed `CONNECTED` with `tog_and_dogs` calendar.
*   **File(s) Inspected:** 
    *   [google_auth_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/google_auth_handler.py#L279) (Line 279, function `get_status`)
    *   [google_calendar.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/common/google_calendar.py#L24) (Line 24, function `_get_stored_tokens`)
*   **Root Cause:** The Google Calendar integration uses a single AWS Secrets Manager secret configured via the environment variable `GOOGLE_USER_TOKENS_NAME` on the Lambda. When `get_status(event)` retrieves tokens using `get_stored_tokens()`, it queries this global secret containing `tog_and_dogs` tokens. There is no tenant-scoping logic (e.g. appending `-test_tenant_alpha` to the secret name, storing tokens in DynamoDB under the tenant's `METADATA` record, or indexing tokens by `company_id` inside a shared JSON secret).

### B. Staff Management & Request Sidebar Staff Quick View
*   **Observed Behavior:** Existing `tog_and_dogs` owners, admins, and staff appeared in the `test_tenant_alpha` staff views.
*   **File(s) Inspected:** 
    *   [admin_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/admin_handler.py#L295-L312) (Lines 295–312, routing `GET /admin/staff`)
*   **Root Cause:** To list staff, the backend queries the Cognito User Pool globally for all users belonging to the `Staff`, `owner`, or `Admin` groups. The backend **fails to filter** the returned users by checking if their `custom:company_id` attribute matches the caller's `company_id`. Instead, it automatically maps all returned Cognito users as virtual staff profiles under the caller's current `company_id` (e.g. `PK: COMPANY#test_tenant_alpha`), causing `tog_and_dogs` staff to leak into the `test_tenant_alpha` view.

### C. Client Management
*   **Observed Behavior:** Existing `tog_and_dogs` clients appeared in the `test_tenant_alpha` client list.
*   **File(s) Inspected:**
    *   [admin_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/admin_handler.py#L1467-L1484) (Lines 1467–1484, routing `GET /admin/clients`)
*   **Root Cause:** Identical to the staff listing issue. The backend fetches all Cognito users globally belonging to the `client` group and creates virtual client profiles for the current company without checking the user's `custom:company_id` attribute.

### D. Profile/Company Display Branding Label
*   **Observed Behavior:** Logo/brand label showed "Tog and Dogs" instead of "Test Tenant Alpha".
*   **File(s) Inspected:**
    *   [UserProfile.jsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/UserProfile.jsx#L100) (Line 100)
    *   [AdminDashboard.jsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/AdminDashboard.jsx#L3244) (Line 3244)
*   **Root Cause:** The branding labels, logo shells, and dashboard titles are hardcoded in the frontend components. There is no API route (e.g. `GET /admin/tenant/profile`) that allows the frontend to dynamically fetch the tenant's `display_name`, custom branding colors, and logo from the DynamoDB tenant `METADATA` record based on the authenticated user's `custom:company_id` token claims.

### E. Bookings, Requests, Jobs, and Pets Isolation
*   **Observed Behavior:** No booking/request data was leaked.
*   **Analysis:** The booking and request records are stored in DynamoDB under `COMPANY#<company_id>` partition keys or filtered by `company_id` attributes, which are correctly resolved and isolated. 
*   *Defensive Observation:* In `admin_handler.py` `/admin/requests` (Line 1924 and 1980), the filter expressions still contain fallback checks like `(company_id = :cid OR attribute_not_exists(company_id))`. In strict multi-tenant mode, the fallback check `attribute_not_exists(company_id)` should be removed or conditioned strictly on `TENANT_RESOLUTION_MODE=single` to prevent any untagged legacy data from potentially matching.

---

## 4. Remediation Recommendations (Release 19J Proposal)

To achieve true SaaS multi-tenant readiness, we recommend the following fixes in **Release 19J**:
1.  **Backend Token Scoping:** Update `google_auth_handler.py` and `google_calendar.py` to store Google tokens in a tenant-specific manner (e.g., scoping the secret name using the active `company_id` or storing them in DynamoDB).
2.  **Cognito User Filtering:** Update `admin_handler.py` staff/client listing endpoints to check if each Cognito user's `custom:company_id` matches the current `company_id` before adding them to the response.
3.  **Dynamic Frontend Branding:** Create a new `/admin/tenant/profile` API endpoint to return tenant metadata. Update the frontend (`UserProfile.jsx`, `AdminDashboard.jsx`, and `App.jsx`) to fetch and display this profile dynamically instead of using hardcoded "Tog and Dogs" text.
4.  **Remove Query Fallbacks:** Clean up the legacy DynamoDB filter fallbacks (`attribute_not_exists(company_id)`) to enforce strict `company_id = :cid` matching when multi-tenant mode is active.
