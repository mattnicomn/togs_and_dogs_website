# Release 17P-Fix1: Platform Admin UI CORS Preflight / Deployment Remediation

**Status:** ✅ Completed  
**Type:** Infrastructure Deployment / CORS Remediation  
**Date:** 2026-06-21  
**Baseline:** Release 17P completed and synced to production (`510fe2b`).

---

## 1. Context & Defect Report

During manual validation of Release 17P in production, the Platform Admin Console at `/platform-admin` failed to load any tenant data and instead displayed:
- **System Error**
- **Failed to fetch**

While unauthenticated API Gateway requests correctly returned `401 Unauthorized` and unauthenticated frontend console requests redirected back to `/admin`, authenticated data fetching by logged-in platform administrators failed at the network level.

---

## 2. Root Cause Analysis

Investigation confirmed the following:
1. **Frontend Correctness**: Web client API helpers (`web/src/api/platform.js`, `web/src/api/client.js`), router (`web/src/App.jsx`), and components (`PlatformAdmin.jsx`) were confirmed to use correct endpoints, attach the id token properly, and logging was clean (no tokens or credentials exposed).
2. **Infrastructure Drift**: The `platform`, `platform_tenants`, `platform_tenants_id`, and `platform_audit` paths had been added to the local `cors_resources` map in `modules/api/main.tf` to generate mock `OPTIONS` preflight handlers. However, a Terraform plan showed that the **API Gateway stage deployment (`aws_api_gateway_deployment.main`) had not been redeployed**.
3. **CORS Failure**: Because the deployment had not been applied, the `OPTIONS` preflight routes for the new `/platform/*` endpoints did not exist in the active production API Gateway stage. Browsers attempting to send the authenticated `GET` requests sent a preflight `OPTIONS` request, which failed at the Gateway level, resulting in the `TypeError: Failed to fetch` error.

---

## 3. Remediation Executed

1. **Terraform Apply**: Executed a targeted and safe deployment:
   ```bash
   terraform apply
   ```
   This recreated the `aws_api_gateway_deployment.main` resource (based on the updated triggers block containing the new `platform` OPTIONS methods) and updated the `prod` stage to point to the new deployment.
2. **Commit Changes**: Staged and committed the API Gateway configuration changes in `modules/api/main.tf`.

---

## 4. Post-Fix Verification

### Unauthenticated API Response
Sent an unauthenticated `OPTIONS` preflight request to `/platform/tenants`:
```bash
curl -X OPTIONS "https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod/platform/tenants?cb=124"
```
Response headers returned:
- `HTTP/1.1 200 OK`
- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: GET,POST,PUT,PATCH,DELETE,OPTIONS`
- `Access-Control-Allow-Headers: Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token`

Unauthenticated `GET /platform/tenants` remains protected:
- `HTTP/1.1 401 Unauthorized`
- `{"message":"Unauthorized"}`

### Browser Smoke Validation
A browser subagent verified unauthenticated website behavior:
- **Public Site**: Loads successfully ✅
- **Staff Portal (`/admin`)**: Loads successfully ✅
- **Console Access Guard**: Navigating to `/platform-admin` while unauthenticated correctly redirects the browser to `/admin` ✅

### Test Suite Execution
Ran the full backend Python test suite to verify zero regressions:
```bash
py -m pytest tests/
```
Result: **454/454 passed** ✅

---

## 5. Operational Guarantees

- **No mutations**: No tenant metadata was modified during the fix or validation.
- **No Cognito changes**: No Cognito group memberships or accounts were added or modified.
- **No third-party integrations**: No Stripe, Postmark, mobile, EAS, TestFlight, or live API key changes occurred.
- **Privacy enforcement**: No tokens, session data, or credentials were logged or exposed.

---

## 6. Files Changed

| File | Action | Description |
|---|---|---|
| [main.tf](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/modules/api/main.tf) | 📝 Modified | Committed CORS platform mappings in `local.cors_resources` |
| [release-17p-fix1-platform-admin-fetch-cors-remediation.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/release-notes/release-17p-fix1-platform-admin-fetch-cors-remediation.md) | 🆕 Created | This release note |
| [index.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/release-notes/index.md) | 📝 Modified | Updated release history index |

---

## 7. Recommended Next Step for Matthew

Matthew can now perform manual validation in the production browser:
1. Log in with a `platform_admin` user.
2. Navigate to `https://toganddogs.usmissionhero.com/platform-admin`.
3. Confirm that the tenant list successfully loads with no system errors.
