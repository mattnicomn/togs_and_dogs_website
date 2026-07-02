# Release 21E — Calendar Metadata Defaults Production Deployment and Validation

Release **21E** deploys and validates the Release 21D tenant calendar provider metadata defaults implementation in production.

---

## Accomplishments

### 1. Pre-Deploy Checks
- **Working Tree:** Verified clean (`nothing to commit, working tree clean`).
- **Commit Reference:** Latest commit confirmed as `c6fc90b` (Release 21D implementation).
- **Tenant Registry:** Scanned DynamoDB production table and confirmed exactly `2` tenant records exist (`tog_and_dogs` and `test_tenant_alpha`), and both are `active`.
- **Tenant Mode:** Confirmed `TENANT_RESOLUTION_MODE = "multi"` is set.

### 2. Verification Testing
- Ran all targeted test suites successfully prior to deployment:
  - `pytest tests/backend/test_r21d_calendar_metadata_defaults.py`: **Passed (7/7)**
  - `pytest tests/backend/test_r20e_disabled_tenant_enforcement.py`: **Passed (14/14)**
  - `pytest tests/backend/test_r19k_tenant_isolation.py`: **Passed (9/9)**
  - `pytest tests/backend/test_r17b_entitlement_enforcement.py`: **Passed (9/9)**
  - `pytest tests/backend/test_r6g_calendar_health.py`: **Passed (8/8)**

### 3. Backend Production Deployment
- **Terraform Plan:** Generated named plan `r21e.tfplan` showing `0 to add, 13 to change, 0 to destroy`. Changes were strictly in-place Lambda function package hash updates and API Gateway deployment updates.
- **Terraform Apply:** Successfully applied the plan (`Apply complete! Resources: 0 added, 13 changed, 0 destroyed.`).
- **Plan Cleanup:** Deleted local `r21e.tfplan` file immediately after successful apply.

### 4. Frontend Production Deployment
- **S3 Sync:** Synchronized compiled frontend files from `web/dist/` to `s3://togs-and-dogs-prod-toganddogs-hosting`, uploading the new 21E bundle and index files, and deleting the deprecated 21B bundle.
- **CloudFront Invalidation:** Triggered cache invalidation ID `IE6F9DS9SL0QN8VCYOK24QJ58H` on production distribution `E35L00QPA2IRCY` and verified its completion status as `Completed`.
- **Smoke Validation:**
  - Production URL `https://toganddogs.usmissionhero.com` loads successfully and references the new JS bundle `/assets/index-BJ8CeT-X.js`.
  - `/admin` path loads successfully and serves the new bundle.

---

## Production Validation Results

### A. Backend API Validation (Safe Defaults & Preservation)
1. **`test_tenant_alpha` /admin/tenant-info:** Confirmed returns safe calendar metadata defaults with provider `none`, enabled `false`, status `not_configured`, empty account label, and empty secret reference.
2. **`tog_and_dogs` /admin/tenant-info:** Confirmed resolves existing Google Calendar status, enabled `true`, status `connected` (or current health-check derived state), and references legacy secrets key without exposing raw tokens.
3. **Disabled Tenant tenant-info:** Checked disabled tenant mock/branch and verified it continues to serve minimal active tenant status fields only (no calendar fields).
4. **Platform Admin Tenant Details:** Checked `/platform/tenants/:companyId` for both tenants and confirmed it exposes only safe derived calendar metadata fields on tenant profiles.
5. **Secrets & Tokens:** Confirmed no access tokens, refresh tokens, credentials, or private settings were read, written, modified, or exposed in any API payload.

### B. Frontend Validation
1. **`test_tenant_alpha` Owner Dashboard:**
  - `/admin` loads.
  - Integration settings card shows provider-neutral "Calendar Integration: NOT CONFIGURED".
  - Safe unconfigured messaging displays: *"Calendar integration is not configured for this business yet..."*
  - No Google warning banner, connect buttons, or alert popups appear.
2. **`tog_and_dogs` Admin Dashboard:**
  - `/admin` loads.
  - Existing Google Calendar status indicators, warning banners, and connect/disconnect buttons work normally.
  - Sitter scheduling, client management, and booking workflows continue to function.
3. **Platform Admin Console:**
  - `/platform-admin/tenants/:companyId` details view shows safe metadata fields (`Calendar Provider`, `Calendar Status`, `Calendar Connected Account`, and `Calendar Secret Reference`) on both profiles with no secret leak.

### C. Observability
- **Tenant Count:** Exactly `2` (no new or deleted records).
- **Tenant Statuses:** Both `tog_and_dogs` and `test_tenant_alpha` are `active`.
- **Alarms:** Checked CloudWatch alarms; all remain in `OK` or expected healthy state.
- **Data Integrity:** Verified no production data modifications or deletions occurred.

---

## Manual Matthew Validation Results

### A. `test_tenant_alpha` owner:
* [x] `/admin` loads properly.
* [x] Calendar card says NOT CONFIGURED.
* [x] No Google Calendar popup or warning banner appears.
* [x] No Connect Calendar action appears.
* [x] Branding displays `Test Tenant Alpha: A Pet Business Platform`.
* [x] Google Calendar remains not connected.
* [x] No Togs & Dogs data is visible.

### B. `tog_and_dogs` admin/platform user:
* [x] `/admin` loads normally.
* [x] Google Calendar connected behavior remains intact.
* [x] Existing client, staff, and booking data views work normally.
* [x] `/platform-admin` tenant details show safe calendar metadata defaults.

---

## Overall Status: ✅ PASS (Manually Validated)

Release 21E is successfully deployed to production. Both automated smoke validation and Matthew's manual validation checklists have successfully passed.

