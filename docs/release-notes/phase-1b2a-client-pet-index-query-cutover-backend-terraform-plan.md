# Release Notes: Phase 1B.2A — ClientPetIndex Query-Cutover Backend Terraform Plan

## 1. Executive Summary

This release note documents the generation of the production Terraform plan for the
**Phase 1B.2A ClientPetIndex Query Cutover** backend deployment. The plan targets only
the 13 shared Lambda functions to propagate the Query-cutover application code
(`c372223` — `pet_handler.py` + `pet_profile.py`).

The plan is intentionally backend-only: `modules/data/main.tf` already contains the
live `ClientPetIndex` GSI (deployed and `ACTIVE`). No DynamoDB changes are required or
present. The plan was generated against the current production infrastructure state via
a clean `terraform plan -out` invocation.

No `terraform apply`, Lambda deployment, or DynamoDB modification has occurred.

---

## 2. Infrastructure Context

- **AWS Account:** `358604342897`
- **AWS Profile:** `usmissionhero-website-prod`
- **Region:** `us-east-1`
- **Terraform Directory:** `infra/prod`
- **Terraform Workspace:** default
- **Target Environment:** production

---

## 3. Core Plan Metrics

| Field | Value |
|-------|-------|
| **Saved Plan Filename** | `phase-1b2a-client-pet-index-query-cutover-backend.tfplan` |
| **Local Path** | `infra/prod/phase-1b2a-client-pet-index-query-cutover-backend.tfplan` |
| **Plan Checksum (SHA256)** | `c8b0907824fa5da10a72a09c4fb5078d574175d7538e040afc46110ca0feaa73` |
| **Plan Summary** | `0 to add, 13 to change, 0 to destroy` |
| **Backend Archive Checksum (SHA256-hex)** | `16f75c5ce888ac99281dc256c6a59474ed97358cd2df9e7ea629d13c95545dbc` |
| **Backend Archive Checksum (SHA256-Base64)** | `FvdcXOiIrJkoHcJWxqWUdO2XNYzS355+pinRPJVUXbw=` |

> The Base64 value matches the `source_code_hash` shown in the plan for all 13 Lambda
> function updates (transition from the previously deployed hash to this new hash).

---

## 4. Source Code Delta

- **Previously Deployed Baseline:** `ca73d93` — `fix(backend): default new pets to active`
  (`is_active` hardening — already live in production)
- **New Code Commit:** `c372223` — `feat(backend): implement local ClientPetIndex query
  cutover and fix listing test mocks`

### Files Modified in `src/backend` (commit `c372223`)

| File | Changes |
|------|---------|
| `src/backend/handlers/pet_handler.py` | Replaces both Scan-based client-pet listing paths (GET /client/pets, GET /admin/pets?clientId) with ClientPetIndex GSI Query; adds canonical client ownership GetItem validation before Query; adds full pagination with ExclusiveStartKey; adds post-query Python filtering for entity_type, company_id, and is_active |
| `src/backend/common/pet_profile.py` | Replaces `_get_client_pets()` Scan with ClientPetIndex GSI Query; adds `company_id` parameter to function signature; adds canonical client ownership validation; adds pagination and post-query tenant/status filtering; updates both internal callers to pass company_id |

No other `src/backend` file differs between `ca73d93` and `e7b99f5` (HEAD).

---

## 5. Deterministic Backend Archive Audit

| Metric | Value |
|--------|-------|
| Total ZIP entries | `39` |
| Tracked backend files (`git ls-files src/backend`) | `39` |
| Missing tracked files | `0` |
| Unexpected included files | `0` |
| `.pytest_cache/` entries | `0` |
| `__pycache__/` entries | `0` |
| `.pyc` / `.pyo` files | `0` |
| `.log` / `.tmp` files | `0` |

The archive contains exactly the 39 files tracked under `src/backend`, stored at the
relative paths `common/…` and `handlers/…` (no `src/backend/` prefix), which matches
the Lambda `PYTHONPATH` configuration.

---

## 6. Production Plan Resources & Actions

All 13 Lambda functions are updated **in-place** via `source_code_hash`. No
replacements or destructions exist in the plan.

| Resource Address | Action | Handler |
|------------------|--------|---------|
| `aws_lambda_function.admin` | `~ update in-place` | `handlers.admin_handler.handler` |
| `aws_lambda_function.assign` | `~ update in-place` | `handlers.assignment_handler.handler` |
| `aws_lambda_function.cancellation` | `~ update in-place` | `handlers.cancellation_handler.handler` |
| `aws_lambda_function.device` | `~ update in-place` | `handlers.device_handler.handler` |
| `aws_lambda_function.google_auth` | `~ update in-place` | `handlers.google_auth_handler.handler` |
| `aws_lambda_function.intake` | `~ update in-place` | `handlers.intake_handler.handler` |
| `aws_lambda_function.job` | `~ update in-place` | `handlers.job_handler.handler` |
| `aws_lambda_function.pet` | `~ update in-place` | `handlers.pet_handler.handler` |
| `aws_lambda_function.platform` | `~ update in-place` | `handlers.platform_handler.handler` |
| `aws_lambda_function.postmark_webhook` | `~ update in-place` | `handlers.postmark_webhook_handler.handler` |
| `aws_lambda_function.review` | `~ update in-place` | `handlers.review_handler.handler` |
| `aws_lambda_function.ses_feedback` | `~ update in-place` | `handlers.notification_feedback_handler.handler` |
| `aws_lambda_function.stripe_webhook` | `~ update in-place` | `handlers.stripe_webhook_handler.handler` |

### Verified Exclusions

- No DynamoDB table or index changes (GSI is already ACTIVE in production)
- No resource replacements or destructions
- No Cognito schema or group changes
- No API Gateway method, route, or deployment modifications
- No IAM role or policy changes
- No S3, CloudFront, Stripe, or Google Calendar resources
- No tenant metadata modifications

---

## 7. GSI State at Plan Time

- **ClientPetIndex status:** `ACTIVE` (deployed by the preceding Phase 1B.2A GSI plan apply)
- **Query cutover status:** Not yet live — `c372223` is in the repository at HEAD but
  the deployed Lambda package still reflects the `ca73d93` baseline
- **`pet_handler.py` behaviour once deployed:**
  - GET /client/pets: validates canonical client ownership via GetItem, queries ClientPetIndex by client_id with full pagination, filters results in Python (entity_type=PET, company_id match, is_active not explicitly False), sanitizes for client role, returns `{"pets": [...]}`
  - GET /admin/pets?clientId: validates canonical client ownership via GetItem, queries ClientPetIndex with full pagination, applies same tenant/status filtering, returns `{"pets": [...]}`
  - No Scan fallback path remains in any pet-by-client read operation
- **`pet_profile.py` behaviour once deployed:**
  - `_get_client_pets(client_id, company_id)`: validates canonical client via GetItem, queries ClientPetIndex with full pagination, applies entity_type/company_id/is_active filtering, returns list
  - Callers: `create_or_link_pets_from_request` and `_rebuild_pet_summary`
- **Filtering:** Post-query Python filtering excludes records where `is_active` is explicitly `False`; records missing `is_active` are treated as active. No `is_active` FilterExpression is used on the GSI Query itself.

---

## 8. Terraform Validation Results

```
terraform fmt     -> exit 0, no format corrections required
terraform validate -> Success! The configuration is valid.
terraform plan    -> Plan: 0 to add, 13 to change, 0 to destroy.
```

---

## 9. Repository State at Plan Generation

- **Branch:** `main`
- **HEAD commit:** `e7b99f5` — `docs: review ClientPetIndex query test hardening`
- **Working tree:** clean
- **Stash list:** empty
- **origin/main:** contains HEAD (no unpushed commits)

---

## 10. Status & Next Gate

- **ClientPetIndex GSI:** Deployed and `ACTIVE`
- **Backend Archive:** Built, audited, and hash-verified
- **Terraform Plan:** Generated, checked, and documented
- **Terraform Apply:** Pending Kiro plan review and Matthew approval
- **Action Required:** Approve application of `phase-1b2a-client-pet-index-query-cutover-backend.tfplan`
