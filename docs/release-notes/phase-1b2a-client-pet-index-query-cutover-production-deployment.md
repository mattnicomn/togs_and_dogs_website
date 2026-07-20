# Release Notes: Phase 1B.2A — ClientPetIndex Query-Cutover Production Deployment

**Date:** 2026-07-20
**Status:** INFRASTRUCTURE DEPLOYMENT COMPLETE — AUTHENTICATED BROWSER SMOKE PENDING

---

## 1. Executive Summary

This document records the successful production deployment of the Phase 1B.2A
ClientPetIndex Query Cutover backend. The reviewed saved Terraform plan was applied
without deviation. All 13 shared Lambda functions were updated in-place to the new
package containing the Query-cutover implementation (`c372223`).

No replacements, destructions, DynamoDB changes, or unrelated infrastructure changes
occurred. The ClientPetIndex GSI remained unchanged (already ACTIVE from the preceding
Phase 1B.2A GSI deployment). No production data was modified.

The deployment window CloudWatch check found zero occurrences of all monitored error
signatures. Authenticated browser smoke validation remains pending (next gate: Matthew).

---

## 2. Repository and Artifact Identity

| Field | Value |
|-------|-------|
| **Deployment commit (HEAD)** | `2c92730` — `docs: review ClientPetIndex query-cutover Terraform plan` |
| **Implementation commit** | `c372223` — `feat(backend): implement local ClientPetIndex query cutover` |
| **Saved plan filename** | `phase-1b2a-client-pet-index-query-cutover-backend.tfplan` |
| **Saved plan SHA256** | `c8b0907824fa5da10a72a09c4fb5078d574175d7538e040afc46110ca0feaa73` |
| **Backend archive SHA256 (hex)** | `16f75c5ce888ac99281dc256c6a59474ed97358cd2df9e7ea629d13c95545dbc` |
| **Backend archive SHA256 (Base64)** | `FvdcXOiIrJkoHcJWxqWUdO2XNYzS355+pinRPJVUXbw=` |

Both checksums were independently verified before apply. No plan regeneration occurred.

---

## 3. AWS Target Verification

| Field | Verified Value |
|-------|---------------|
| **Profile** | `usmissionhero-website-prod` |
| **Account** | `358604342897` |
| **Region** | `us-east-1` |

Verified via `aws sts get-caller-identity` immediately before apply. Token was refreshed
via SSO login.

---

## 4. Terraform Apply Result

| Field | Expected | Actual |
|-------|----------|--------|
| Resources added | 0 | 0 ✅ |
| Resources changed | 13 | 13 ✅ |
| Resources destroyed | 0 | 0 ✅ |

```
Apply complete! Resources: 0 added, 13 changed, 0 destroyed.
```

No plan staleness error was reported. The saved plan was accepted and applied as-is.

### Warning Noted (Non-blocking)

```
Warning: Deprecated Parameter
The parameter "dynamodb_table" is deprecated. Use parameter "use_lockfile" instead.
```

This is a pre-existing Terraform backend configuration deprecation warning unrelated to
this deployment. It does not affect the apply result.

---

## 5. Lambda Deployment Verification

All 13 Lambda functions verified via read-only `get-function-configuration` after apply.

### Expected CodeSha256

`FvdcXOiIrJkoHcJWxqWUdO2XNYzS355+pinRPJVUXbw=`

### Results

| # | Lambda Name | State | LastUpdateStatus | CodeSha256 Matches |
|---|-------------|-------|-----------------|-------------------|
| 1 | `togs-and-dogs-prod-admin` | Active | Successful | ✅ |
| 2 | `togs-and-dogs-prod-assign` | Active | Successful | ✅ |
| 3 | `togs-and-dogs-prod-cancellation` | Active | Successful | ✅ |
| 4 | `togs-and-dogs-prod-device` | Active | Successful | ✅ |
| 5 | `togs-and-dogs-prod-google-auth` | Active | Successful | ✅ |
| 6 | `togs-and-dogs-prod-intake` | Active | Successful | ✅ |
| 7 | `togs-and-dogs-prod-job` | Active | Successful | ✅ |
| 8 | `togs-and-dogs-prod-pet` | Active | Successful | ✅ |
| 9 | `togs-and-dogs-prod-platform` | Active | Successful | ✅ |
| 10 | `togs-and-dogs-prod-postmark-webhook` | Active | Successful | ✅ |
| 11 | `togs-and-dogs-prod-review` | Active | Successful | ✅ |
| 12 | `togs-and-dogs-prod-ses-feedback` | Active | Successful | ✅ |
| 13 | `togs-and-dogs-prod-stripe-webhook` | Active | Successful | ✅ |

All 13: State=Active, LastUpdateStatus=Successful, CodeSha256 matches expected. ✅

---

## 6. Changed-Field Assessment

For all 13 Lambda functions, the only fields changed by this apply were:

- `source_code_hash`: `VW+goUeWfvYcY2P5ZVnk7tWqxGuj3/I0r6MmLAdPAIo=` → `FvdcXOiIrJkoHcJWxqWUdO2XNYzS355+pinRPJVUXbw=`
- `last_modified`: provider-computed metadata timestamp (expected side-effect of deploy)

No configuration fields changed: handler, runtime, role, environment variables, memory,
timeout, layers, architecture, reserved concurrency, tracing, VPC, dead-letter config,
or tags are all unchanged.

---

## 7. Verified Exclusions

- ✅ No DynamoDB table or index changes (ClientPetIndex remains ACTIVE and unchanged)
- ✅ No resource replacements
- ✅ No resource destructions
- ✅ No Cognito schema or group changes
- ✅ No API Gateway method, route, or deployment modifications
- ✅ No IAM role or policy changes
- ✅ No S3, CloudFront, Stripe, or Google Calendar resources touched
- ✅ No tenant metadata modifications
- ✅ No production data created, updated, or deleted
- ✅ No direct Lambda invocation
- ✅ No synthetic production API request
- ✅ No Cognito authentication validation
- ✅ No tenant isolation validation in production
- ✅ No remediation action taken
- ✅ No second-tenant creation
- ✅ No TENANT_RESOLUTION_MODE change
- ✅ No frontend deployment
- ✅ No mobile distribution change
- ✅ No Stripe, Google Calendar, Google Play, or Apple distribution change
- ✅ No Ryan-testing change

---

## 8. Aggregate CloudWatch Error-Signature Check

**Deployment window:** 2026-07-20T17:28:00Z – 2026-07-20T17:38:00Z

Checked log groups for the two primary changed-path Lambdas:
- `/aws/lambda/togs-and-dogs-prod-pet` — primary target (handler GET routes changed)
- `/aws/lambda/togs-and-dogs-prod-job` — secondary target (calls `create_or_link_pets_from_request`)

| Log Group | Error Signature | Count |
|-----------|----------------|-------|
| prod-pet | Runtime.ImportModuleError | 0 |
| prod-pet | Runtime.HandlerNotFound | 0 |
| prod-pet | INIT_REPORT failures | 0 |
| prod-pet | ValidationException | 0 |
| prod-pet | Task timed out | 0 |
| prod-pet | Unhandled | 0 |
| prod-job | Runtime.ImportModuleError | 0 |
| prod-job | Runtime.HandlerNotFound | 0 |
| prod-job | INIT_REPORT failures | 0 |
| prod-job | ValidationException | 0 |
| prod-job | Task timed out | 0 |
| prod-job | Unhandled | 0 |

**Assessment: CLEAN** — No deployment-window error signatures detected. No raw log
events were reproduced. Aggregate counts only.

Note: The functions that execute changed code paths (pet, job) were not necessarily
invoked during the deployment window. Absence of errors is expected and consistent
with a quiet deployment window.

---

## 9. Application Validation Status

| Item | Status |
|------|--------|
| Infrastructure package deployment | ✅ Complete — all 13 Lambdas updated |
| Frontend deployment | ❌ Not performed (not in scope) |
| ClientPetIndex GSI change | ❌ Not performed (already ACTIVE, not in scope) |
| Production data modification | ❌ Not performed |
| Direct Lambda invocation | ❌ Not performed |
| Synthetic API request | ❌ Not performed |
| Cognito authentication validated in production | ❌ Pending (Matthew manual smoke) |
| Tenant isolation validated in production | ❌ Pending (Matthew manual smoke) |
| Client portal pet listing validated | ❌ Pending (Matthew manual smoke) |
| Admin pet listing validated | ❌ Pending (Matthew manual smoke) |
| Job workflow (offline booking) validated | ❌ Not exercised — event-driven path |
| CloudWatch deployment-window check | ✅ CLEAN — zero error signatures |

---

## 10. What Changes in Production Behavior

Once the new package is active ($LATEST), the following behavioral changes are live:

### GET /client/pets (client portal)
- **Before:** Full DynamoDB Scan with FilterExpression on client_id + entity_type
- **After:** GetItem canonical client ownership validation → ClientPetIndex GSI Query
  with full ExclusiveStartKey pagination → post-query Python filtering
  (entity_type, company_id, is_active)

### GET /admin/pets?clientId=... (admin)
- **Before:** Full DynamoDB Scan with FilterExpression on client_id + entity_type
- **After:** Same bounded Query pattern as client portal

### pet_profile._get_client_pets() (internal — called on request approval)
- **Before:** Full DynamoDB Scan
- **After:** Same bounded Query pattern; callers updated to pass company_id

**No Scan fallback path remains in any pet-by-client read operation.**

---

## 11. Deployment Timeline

| Event | Time (UTC) |
|-------|-----------|
| SSO token refreshed | 2026-07-20 ~17:24 |
| AWS identity verified (account 358604342897, us-east-1) | 2026-07-20 17:27:58 |
| `terraform apply` started | 2026-07-20 17:28:04 |
| First Lambda modification began | 2026-07-20 17:28 |
| Apply complete (0 added, 13 changed, 0 destroyed) | 2026-07-20 17:29:25 |
| Lambda verification (all 13 Active/Successful/hash match) | 2026-07-20 17:30:34 |
| CloudWatch error-signature check completed | 2026-07-20 17:38:23 |

---

## 12. Status and Next Gate

| Gate | Status |
|------|--------|
| ClientPetIndex GSI deployed and ACTIVE | ✅ Done (prior deployment) |
| Backend Lambda package deployed | ✅ Done (this deployment) |
| All 13 Lambdas Active/Successful/hash-verified | ✅ Done |
| CloudWatch deployment-window check | ✅ CLEAN |
| **Matthew authenticated browser smoke** | ⏳ **PENDING — next gate** |
| Kiro closeout review | ⏳ Pending (after smoke) |

### Matthew Manual Smoke Checklist (minimum)

1. Log in as admin at `toganddogs.usmissionhero.com`
2. Navigate to Client Management
3. Open a client detail drawer
4. Verify the pet inventory list loads correctly
5. Log in as a client (if applicable)
6. Navigate to client portal pet listing
7. Verify pets appear as expected
8. Report any errors, missing pets, or unexpected behavior

---

## 13. Commits in This Deployment Sequence

| Commit | Message |
|--------|---------|
| `c372223` | feat(backend): implement local ClientPetIndex query cutover |
| `18a3209` | test(backend): add focused unit tests for ClientPetIndex GSI query cutover |
| `e7b99f5` | docs: review ClientPetIndex query test hardening |
| `fbe5fc2` | docs: record Phase 1B.2A Query-cutover backend Terraform plan |
| `2c92730` | docs: review ClientPetIndex query-cutover Terraform plan |
