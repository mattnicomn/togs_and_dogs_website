# Phase 1B.2A: ClientPetIndex Query-Cutover Plan Review Closeout

**Date:** 2026-07-20
**Reviewer:** Kiro
**Status:** READY FOR QUERY CUTOVER APPLY APPROVAL

---

## Saved Plan Identity

| Field | Value |
|-------|-------|
| Saved plan file | `infra/prod/phase-1b2a-client-pet-index-query-cutover-backend.tfplan` |
| Plan SHA256 | `c8b0907824fa5da10a72a09c4fb5078d574175d7538e040afc46110ca0feaa73` |
| Backend archive | `infra/prod/backend.zip` |
| Archive SHA256 (hex) | `16f75c5ce888ac99281dc256c6a59474ed97358cd2df9e7ea629d13c95545dbc` |
| Archive SHA256 (Base64) | `FvdcXOiIrJkoHcJWxqWUdO2XNYzS355+pinRPJVUXbw=` |
| Plan summary | **0 to add, 13 to change, 0 to destroy** |

All checksums verified independently via `certutil -hashfile` and Python `hashlib`.

---

## Plan Summary

Exactly 13 Lambda functions updated in-place. Only fields changing:
- `source_code_hash`: `VW+goUeWfvYcY2P5ZVnk7tWqxGuj3/I0r6MmLAdPAIo=` → `FvdcXOiIrJkoHcJWxqWUdO2XNYzS355+pinRPJVUXbw=`
- `last_modified`: current timestamp → `(known after apply)`

No change to: handler, runtime, role, environment, memory, timeout, layers, architecture, reserved concurrency, tracing, VPC configuration, dead-letter configuration, or tags.

---

## Exact 13 Lambda Resources

| # | Resource Address | Lambda Name | Action |
|---|------------------|-------------|--------|
| 1 | `aws_lambda_function.admin` | `togs-and-dogs-prod-admin` | ~ update in-place |
| 2 | `aws_lambda_function.assign` | `togs-and-dogs-prod-assign` | ~ update in-place |
| 3 | `aws_lambda_function.cancellation` | `togs-and-dogs-prod-cancellation` | ~ update in-place |
| 4 | `aws_lambda_function.device` | `togs-and-dogs-prod-device` | ~ update in-place |
| 5 | `aws_lambda_function.google_auth` | `togs-and-dogs-prod-google-auth` | ~ update in-place |
| 6 | `aws_lambda_function.intake` | `togs-and-dogs-prod-intake` | ~ update in-place |
| 7 | `aws_lambda_function.job` | `togs-and-dogs-prod-job` | ~ update in-place |
| 8 | `aws_lambda_function.pet` | `togs-and-dogs-prod-pet` | ~ update in-place |
| 9 | `aws_lambda_function.platform` | `togs-and-dogs-prod-platform` | ~ update in-place |
| 10 | `aws_lambda_function.postmark_webhook` | `togs-and-dogs-prod-postmark-webhook` | ~ update in-place |
| 11 | `aws_lambda_function.review` | `togs-and-dogs-prod-review` | ~ update in-place |
| 12 | `aws_lambda_function.ses_feedback` | `togs-and-dogs-prod-ses-feedback` | ~ update in-place |
| 13 | `aws_lambda_function.stripe_webhook` | `togs-and-dogs-prod-stripe-webhook` | ~ update in-place |

---

## Verified Exclusions

- ❌ No DynamoDB table or index changes (ClientPetIndex already ACTIVE)
- ❌ No resource replacement
- ❌ No resource destruction
- ❌ No API Gateway changes
- ❌ No IAM role or policy changes
- ❌ No Cognito changes
- ❌ No S3 or CloudFront changes
- ❌ No Route 53 changes
- ❌ No unrelated changes

---

## Changed-Field Assessment: PACKAGE-ONLY

For all 13 Lambdas, the only meaningful change is `source_code_hash` transitioning from the previously deployed hash to the new archive hash. `last_modified` is provider-computed metadata. No configuration field changes.

---

## Source-Delta Assessment

- **Previously deployed baseline:** `ca73d93` — pet creation is_active hardening
- **New code commit:** `c372223` — ClientPetIndex query cutover implementation
- **Only commit touching src/backend in the range `ca73d93..e7b99f5`:** `c372223`
- **Only files changed:** `src/backend/handlers/pet_handler.py`, `src/backend/common/pet_profile.py`
- **No other handler or common module changed**
- **Tests and documentation are NOT packaged**

---

## Corrected Implementation Description

### pet_handler.py (commit c372223)

**GET /client/pets (client role):**
1. Derives trusted company_id and client identity from auth context
2. Validates canonical client ownership via `GetItem(PK=COMPANY#{company_id}, SK=CLIENT#{client_id})`
3. Returns `{"pets": []}` if client not found (no Query executed)
4. Queries `ClientPetIndex` by `client_id` with full pagination (ExclusiveStartKey loop)
5. Post-query Python filtering: `entity_type == 'PET'`, company_id present and matches, `is_active` not explicitly `False`
6. Sanitizes results with `sanitize_booking_for_role(item, 'client')`
7. Returns `{"pets": [...]}`

**GET /admin/pets?clientId (owner/admin role):**
1. Derives trusted company_id from auth context
2. Validates canonical client ownership via GetItem
3. Returns `{"pets": []}` if client not found (no Query executed)
4. Queries `ClientPetIndex` by `client_id` with full pagination
5. Post-query Python filtering: same as client path
6. Returns `{"pets": [...]}`

### pet_profile.py (commit c372223)

**`_get_client_pets(client_id, company_id)`:**
1. Validates canonical client via GetItem
2. Returns `[]` if client not found (no Query)
3. Queries `ClientPetIndex` by `client_id` with full pagination
4. Post-query filtering: entity_type, company_id, is_active
5. Returns filtered list
6. Exception handling: catches all, returns `[]`

**Callers (both updated to pass company_id):**
- `create_or_link_pets_from_request` — pet-profile auto-creation on request approval
- `_rebuild_pet_summary` — pet names/breeds summary rebuild on client profile

### Corrections from AG Plan Documentation

| Inaccurate Claim | Correction |
|------------------|------------|
| "Adds `client_id` write-through on pet creation/update" | WRONG. c372223 does NOT add client_id write-through. It replaces Scan with Query in read paths. |
| "All `list_client_pets` calls route through..." | WRONG. No `list_client_pets` function exists. The paths are GET handler routes and `_get_client_pets` helper. |
| "with an `is_active = :true` filter" | WRONG. No FilterExpression on the GSI Query. Filtering is post-query in Python: excludes only explicit `is_active is False`. |

---

## Importer and Shared-Package Risk Assessment

### pet_profile importers

Only one external importer: `handlers/job_handler.py` imports `create_or_link_pets_from_request`.

### Runtime impact per Lambda

| Lambda | Executes changed paths? | Risk |
|--------|------------------------|------|
| `pet` | ✅ Directly — both handler GET routes | Primary target |
| `job` | ✅ Indirectly — `create_or_link_pets_from_request` calls `_get_client_pets` | Secondary target |
| admin, assign, cancellation, device, google_auth, intake, platform, postmark_webhook, review, ses_feedback, stripe_webhook | ❌ Receive archive but do not import or execute changed paths | No runtime impact |

### Deployment characteristics

- Lambda aliases and versions are NOT used — deployment updates `$LATEST` directly
- All 13 Lambdas receive the same shared archive
- Partial apply failure could temporarily create mixed package hashes across Lambdas
- Risk is low: only pet and job Lambdas execute the changed code paths
- Rollback path: re-apply with previous archive

---

## Test Evidence (from prior review, not rerun)

**Focused tests:**
- 15 collected, 15 passed, 0 failed, 0 warnings
- All 26 reviewed requirements meaningfully covered

**Full backend suite:**
- 740 collected, 671 passed, 69 failed, 102 warnings
- Candidate-only failures: 0
- All 69 failures are pre-existing baseline issues unrelated to pet read paths

---

## Backend Archive Audit

| Metric | Value |
|--------|-------|
| Total ZIP entries | 39 |
| Tracked src/backend files | 39 |
| Missing tracked files | 0 |
| Unexpected files | 0 |
| .pytest_cache entries | 0 |
| __pycache__ entries | 0 |
| .pyc / .pyo files | 0 |
| .log / .tmp files | 0 |

---

## Documentation Corrections Applied

1. **Section 4 of plan doc:** Corrected pet_profile.py description from "adds client_id write-through" to "replaces Scan with ClientPetIndex Query and adds company_id parameter"
2. **Section 7 of plan doc:** Replaced non-existent `list_client_pets` reference with actual implementation paths; corrected `is_active = :true` filter claim to "post-query Python filtering"

---

## Restrictions Confirmed

- ❌ No AWS access
- ❌ No Terraform state refresh
- ❌ No new plan generated
- ❌ No Terraform apply
- ❌ No Lambda deployment
- ❌ No DynamoDB modification
- ❌ No ClientPetIndex change
- ❌ No production Query or Scan
- ❌ No remediation
- ❌ No production-data modification
- ❌ No Cognito write
- ❌ No tenant change or second-tenant creation
- ❌ No Google Play action
- ❌ No Stripe change
- ❌ No Google Calendar change
- ❌ No mobile-distribution change
- ❌ No Ryan-testing change

**Query cutover remains undeployed.** The saved plan exists but has not been applied.

---

## Recommendation: **READY FOR QUERY CUTOVER APPLY APPROVAL**

All criteria met:
- ✅ Plan checksum matches expected value
- ✅ Archive hash reconciles (hex → Base64 verified)
- ✅ Plan contains exactly 13 in-place Lambda package updates
- ✅ Only `source_code_hash` and `last_modified` change
- ✅ No replacement, destruction, DynamoDB, or unrelated change
- ✅ Documentation corrected and accurate
- ✅ Source delta is bounded to 2 files in 1 commit
- ✅ Archive is clean and complete (39/39 files, no artifacts)

---

## Next Matthew Approval Gate

**Matthew approves `terraform apply` of `infra/prod/phase-1b2a-client-pet-index-query-cutover-backend.tfplan`.**

Expected outcome: All 13 Lambda functions updated to the new package containing the ClientPetIndex Query cutover. After apply, Matthew performs authenticated manual smoke test (Client Management → drawer → pet list) to verify pet listing works correctly in production.

---

## Commits

| Item | Value |
|------|-------|
| Starting commit | `fbe5fc2` |
| Ending commit | (this review) |
| Plan generated at | `e7b99f5` |
| Implementation commit | `c372223` |
| Branch | main |
