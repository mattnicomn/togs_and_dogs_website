# Release 11F: Tenant Enforcement Production Deployment and Smoke Validation Plan

**Status:** Planning
**Priority:** High
**Risk to Production:** Medium (behavior changes to existing handler responses)
**Terraform Required:** No
**Backend Changes:** Lambda code update only (no infra changes)
**Frontend Changes:** None
**Scope:** Deploy 11E tenant enforcement hardening to production and validate

---

## 1. Deployment Objective

Deploy the Release 11E tenant enforcement hardening code (`44691ee`) to the production Lambda. This release adds `validate_tenant_ownership()` post-read checks to all direct-item-access handlers, parameterizes the notification quota key, and adds tenant-scoped filtering to the export endpoint.

**Key safety property:** For the current single-tenant system (`tog_and_dogs` only), all records have `company_id = "tog_and_dogs"` or default to it, and the caller's company is always `"tog_and_dogs"`. Therefore `validate_tenant_ownership()` will always pass for existing users. The hardening is invisible to Ryan's workflow.

---

## 2. Exact Code Commit to Deploy

| Field | Value |
|-------|-------|
| Commit | `44691ee` |
| Branch | `main` |
| Message | `Release 11E: Backend tenant enforcement boundary hardening and test suite` |
| Tests | 340/340 passed (`py -m pytest tests/backend/ -v`) |

---

## 3. Affected Backend Files (from 11E)

| File | Change Type |
|------|-------------|
| `src/backend/handlers/admin_handler.py` | Added `validate_tenant_ownership` post-read checks |
| `src/backend/handlers/assignment_handler.py` | Added `validate_tenant_ownership` post-read checks |
| `src/backend/handlers/cancellation_handler.py` | Added `validate_tenant_ownership` post-read checks |
| `src/backend/handlers/review_handler.py` | Added `validate_tenant_ownership` post-read checks |
| `src/backend/handlers/pet_handler.py` | Added indirect tenant validation (client ownership check) |
| `src/backend/common/notifications/service.py` | Parameterized `QUOTA#` key to use `company_id` from record |
| `tests/backend/test_r11e_tenant_enforcement.py` | New test file (enforcement boundary tests) |
| `tests/backend/test_r6j_quota_controls.py` | Updated for parameterized quota key |
| `tests/backend/test_rbac_and_purge_safety.py` | Updated for tenant validation behavior |
| `docs/release-notes/release-11e-tenant-enforcement-hardening-implementation.md` | Release notes |

---

## 4. Pre-Deployment Checks

AG must verify the following before deployment:

### 4.1 Code Verification

```powershell
# Confirm HEAD is the correct commit
git log --oneline -1
# Expected: 44691ee Release 11E: Backend tenant enforcement boundary hardening and test suite

# Confirm working tree is clean
git status --short
# Expected: nothing (or only untracked non-src files)
```

### 4.2 Test Suite Verification

```powershell
# Run full backend test suite
C:\Windows\py.exe -m pytest tests/backend/ -v
# Expected: 340/340 passed, 0 failed, 0 errors
```

### 4.3 Syntax/Import Verification

```powershell
# Compile-check all modified handler files
C:\Windows\py.exe -m py_compile src/backend/handlers/admin_handler.py
C:\Windows\py.exe -m py_compile src/backend/handlers/assignment_handler.py
C:\Windows\py.exe -m py_compile src/backend/handlers/cancellation_handler.py
C:\Windows\py.exe -m py_compile src/backend/handlers/review_handler.py
C:\Windows\py.exe -m py_compile src/backend/handlers/pet_handler.py
C:\Windows\py.exe -m py_compile src/backend/common/notifications/service.py
# Expected: no output (clean compile)
```

### 4.4 Package Verification

```powershell
# Confirm backend.zip can be built from current source
# (AG packages src/backend/ into backend.zip for Lambda deployment)
```

---

## 5. Deployment Steps (Backend/Lambda Only)

### Step 1: Package Backend

```powershell
# Create deployment package from src/backend/
# AG zips src/backend/ contents into backend.zip at repo root
```

### Step 2: Deploy via Terraform

```powershell
# Navigate to terraform directory and apply
C:\Users\mattn\AppData\Local\Microsoft\WinGet\Packages\Hashicorp.Terraform_Microsoft.Winget.Source_8wekyb3d8bbwe\terraform.exe plan
# Review plan output — should show only Lambda code update (source_code_hash change)
# No new resources, no destroyed resources, no IAM/DynamoDB/API Gateway changes expected

C:\Users\mattn\AppData\Local\Microsoft\WinGet\Packages\Hashicorp.Terraform_Microsoft.Winget.Source_8wekyb3d8bbwe\terraform.exe apply
# Requires Matthew's explicit approval
```

### Step 3: Verify Lambda Updated

```powershell
# Confirm Lambda function was updated
aws lambda get-function --function-name <lambda-function-name> --profile usmissionhero-website-prod --query "Configuration.LastModified"
```

### What This Deployment Does NOT Touch

- ❌ S3/CloudFront (no frontend changes)
- ❌ DynamoDB table structure
- ❌ Cognito user pool
- ❌ API Gateway routes
- ❌ IAM roles/policies
- ❌ Postmark/Google Calendar integrations
- ❌ EAS/TestFlight/App Store

---

## 6. Rollback Plan

### If Issues Are Detected Post-Deployment

**Option A: Revert Lambda to prior code (fastest)**

1. Re-deploy the previous `backend.zip` (pre-11E version) via Terraform
2. Or use AWS Console → Lambda → deploy previous version

**Option B: Targeted handler revert**

If only one handler is causing 403 false-positives:
1. Identify which handler's `validate_tenant_ownership` call is failing
2. Revert only that file to pre-11E state
3. Re-package and re-deploy

**Option C: Full git revert**

```powershell
git revert 44691ee
# Creates a new commit undoing all 11E changes
# Then re-deploy
```

### Key Rollback Safety

- The `DEFAULT_COMPANY_ID` fallback in `validate_tenant_ownership` means records without `company_id` are treated as `tog_and_dogs`
- The caller's company always resolves to `tog_and_dogs` in the current single-tenant system
- False-positive 403s should be impossible unless a record has a non-matching `company_id` value (which would indicate a data integrity issue, not a code bug)

---

## 7. Post-Deployment Smoke Test Checklist

### 7.1 Admin Workflows (mattnicomn10@gmail.com)

| # | Test | Method | Expected |
|---|------|--------|----------|
| 1 | Admin login via web | Browser → admin portal | ✅ Login succeeds, dashboard loads |
| 2 | Admin request list loads | GET /admin/requests | ✅ 200 with request list |
| 3 | Admin single request detail | Click any request | ✅ 200 with full request data |
| 4 | Admin export data | GET /admin/export-data | ✅ Returns only `tog_and_dogs` records |
| 5 | Admin pet list | GET /admin/pets | ✅ 200 with pet list |
| 6 | Admin pet detail | GET /admin/pets/{petId} | ✅ 200 with pet data |

### 7.2 Client Workflows (brearockwell@gmail.com)

| # | Test | Method | Expected |
|---|------|--------|----------|
| 7 | Client login | Browser → client portal | ✅ Login succeeds |
| 8 | Client visits/bookings visible | Client dashboard | ✅ Shows upcoming visits |
| 9 | Client can view request history | Client history page | ✅ Shows past bookings |

### 7.3 Staff Workflows (mattnicomn10@yahoo.com)

| # | Test | Method | Expected |
|---|------|--------|----------|
| 10 | Staff login via mobile | TestFlight app | ✅ Login succeeds |
| 11 | Staff upcoming visits visible | Staff schedule screen | ✅ Shows assigned visits |
| 12 | Staff mark complete | Complete a test visit | ✅ JOB status updated |

### 7.4 Admin Actions (Use Controlled Test Record Only)

| # | Test | Method | Expected |
|---|------|--------|----------|
| 13 | Request review/approve | POST /admin/review (test record) | ✅ 200 success |
| 14 | Staff assignment | POST /admin/assign (test record) | ✅ 200 success |
| 15 | Request cancellation | POST /client/cancel (test record) | ✅ 200 success |

### 7.5 Integration Health

| # | Test | Method | Expected |
|---|------|--------|----------|
| 16 | Google Calendar not regressed | Check calendar events after action | ✅ Events still syncing |
| 17 | Postmark not regressed | Check notification sends | ✅ Emails still sending |
| 18 | Notification quota scoped | Check QUOTA# record after send | ✅ Increments `QUOTA#tog_and_dogs` |

### 7.6 Negative Validation (Confirm Enforcement Active)

| # | Test | Method | Expected |
|---|------|--------|----------|
| 19 | No 403 errors for normal admin ops | Monitor CloudWatch logs | ✅ Zero 403s during smoke test |
| 20 | No "Cross-tenant access" log entries | Check Lambda logs | ✅ No SECURITY log lines |

---

## 8. Do Not Test Yet

| ❌ Item | Reason |
|---------|--------|
| Second tenant creation | Not authorized — single-tenant only |
| Cross-tenant real-data testing | Requires a second tenant to exist |
| Billing/entitlement changes | Future Release 12C |
| Self-service onboarding | Future roadmap |
| External TestFlight (Ryan) | Separate release track |
| Frontend code changes | None in this release |
| Mobile app rebuild | Not needed for backend-only change |

---

## 9. AG Pre-Deployment Validation Commands

AG should run these commands and report results before Matthew approves deployment:

```powershell
# 1. Confirm commit
git log --oneline -1
# Expected: 44691ee Release 11E: Backend tenant enforcement boundary hardening and test suite

# 2. Confirm clean tree
git status --short

# 3. Run full test suite
C:\Windows\py.exe -m pytest tests/backend/ -v
# Expected: 340 passed

# 4. Compile-check all affected files
C:\Windows\py.exe -m py_compile src/backend/handlers/admin_handler.py
C:\Windows\py.exe -m py_compile src/backend/handlers/assignment_handler.py
C:\Windows\py.exe -m py_compile src/backend/handlers/cancellation_handler.py
C:\Windows\py.exe -m py_compile src/backend/handlers/review_handler.py
C:\Windows\py.exe -m py_compile src/backend/handlers/pet_handler.py
C:\Windows\py.exe -m py_compile src/backend/common/notifications/service.py

# 5. Verify validate_tenant_ownership is imported and called in each handler
C:\Windows\py.exe -c "import ast; [print(f) for f in ['src/backend/handlers/admin_handler.py','src/backend/handlers/assignment_handler.py','src/backend/handlers/cancellation_handler.py','src/backend/handlers/review_handler.py','src/backend/handlers/pet_handler.py'] if 'validate_tenant_ownership' not in open(f).read()]"
# Expected: no output (all handlers contain the function)
```

---

## 10. AG Deployment Prompt (DO NOT RUN UNTIL MATTHEW APPROVES)

```
DEPLOYMENT TASK: Release 11F — Deploy 11E tenant enforcement to production

COMMIT: 44691ee
BRANCH: main
PROFILE: usmissionhero-website-prod
TERRAFORM: C:\Users\mattn\AppData\Local\Microsoft\WinGet\Packages\Hashicorp.Terraform_Microsoft.Winget.Source_8wekyb3d8bbwe\terraform.exe

STEPS:
1. Run pre-deployment validation commands (Section 9 above)
2. Report validation results to Matthew
3. Package backend: zip src/backend/ contents into backend.zip
4. Run: terraform plan (in terraform directory)
5. Report plan output — confirm Lambda code update only
6. STOP and wait for Matthew's "terraform apply" approval
7. After approval: terraform apply
8. Verify Lambda updated (check LastModified timestamp)
9. Run post-deployment smoke tests (Section 7 above)
10. Report smoke test results

GUARDRAILS:
- Backend Lambda update ONLY
- No S3/CloudFront/frontend deployment
- No DynamoDB schema changes
- No Cognito changes
- No new AWS resources
- Stop and report if terraform plan shows unexpected changes
- Stop and report if any smoke test fails

ROLLBACK:
- If smoke tests fail: immediately redeploy previous backend.zip
- Report which tests failed and any error details
```

---

## 11. Deployment Recommendation

**Recommended approach:** Deploy during a low-traffic window (early morning or late evening). The change is additive and safe for single-tenant, but deploying during low traffic minimizes impact if an unforeseen issue arises.

**Confidence level:** High. The `validate_tenant_ownership` check is mathematically guaranteed to pass for all `tog_and_dogs` records (current tenant matches caller tenant). The only risk is records with an unexpected `company_id` value, which would indicate pre-existing data corruption rather than a code defect.

---

## 12. Success Criteria

Deployment is successful when:
1. ✅ Lambda function updated with commit `44691ee` code
2. ✅ All smoke tests in Section 7 pass
3. ✅ Zero 403 errors in CloudWatch for normal operations
4. ✅ Zero "SECURITY: Cross-tenant access" log entries
5. ✅ Export endpoint returns only `tog_and_dogs` data
6. ✅ Notification quota increments `QUOTA#tog_and_dogs` (not hardcoded)
7. ✅ Google Calendar and Postmark continue functioning

---

## 13. What This Document Authorizes

- ✅ Creating this planning document
- ✅ Committing and pushing this document

## 14. What This Document Does NOT Authorize

- ❌ Deploying to production
- ❌ Running `terraform apply`
- ❌ Updating Lambda functions
- ❌ Writing to DynamoDB
- ❌ Modifying Cognito
- ❌ Modifying any code
- ❌ Running builds (EAS or Terraform)
- ❌ Creating a second tenant
- ❌ Adding/removing testers
- ❌ S3/CloudFront deployment

This is a planning document only. Deployment requires Matthew's separate explicit approval.
