# Phase 1B.2A: ClientPetIndex Terraform Plan Scope Mismatch Review

**Date:** 2026-07-17
**Reviewer:** Kiro
**Status:** ⚠️ NEEDS NEW BOUNDED PLAN — Saved plan is NOT apply-ready

---

## Saved Plan Summary

| Item | Value |
|------|-------|
| Filename | `infra/prod/phase-1b2a-client-pet-index.tfplan` |
| Checksum | `19322ADF7ACBA4F22AB66128E971B74F0F73AA370076FC08C58484D58971F5EF` |
| Plan totals | 0 to add, **14 to change**, 0 to destroy |

## Approved Scope vs Actual Plan

| | Approved | Actual |
|---|---------|--------|
| Resources to change | 1 | **14** |
| DynamoDB table | ✅ | ✅ |
| Lambda functions | 0 | **13** |

## Intended Resource (Correct)

- `module.data.aws_dynamodb_table.main` — in-place update adding ClientPetIndex GSI

## Unintended Resources (13 Lambda Functions)

All 13 Lambda functions show `source_code_hash` and `last_modified` changes:

1. `aws_lambda_function.admin`
2. `aws_lambda_function.assign`
3. `aws_lambda_function.cancellation`
4. `aws_lambda_function.device`
5. `aws_lambda_function.google_auth`
6. `aws_lambda_function.intake`
7. `aws_lambda_function.job`
8. `aws_lambda_function.pet`
9. `aws_lambda_function.platform`
10. `aws_lambda_function.postmark_webhook`
11. `aws_lambda_function.review`
12. `aws_lambda_function.ses_feedback`
13. `aws_lambda_function.stripe_webhook`

## Cause

`data.archive_file.backend_zip` packages the entire `src/backend` directory at plan time. The committed PET is_active hardening (commit `ca73d93`) modified `src/backend/handlers/pet_handler.py`, which is included in the shared archive. Since this code has not been deployed to production, the computed archive hash differs from the production-deployed hash.

**Important:** Unless a complete package-content comparison proves otherwise, `ca73d93` is not necessarily the sole undeployed backend difference. The plan would deploy the complete current backend archive to all 13 Lambda functions.

## Risk of Applying This Saved Plan

Applying would:
- Create ClientPetIndex on the DynamoDB table (intended)
- **Deploy the full current backend code package to all 13 Lambda functions** (unintended, unreviewed for this scope)
- Include at minimum the PET is_active hardening from `ca73d93`
- Potentially include any other committed but undeployed backend changes

This violates the principle of bounded, separately reviewed changes.

## AG Stop-Condition Deviation

The prior instructions required AG to stop if the plan proposed changes beyond the expected DynamoDB table update. AG should have reported the 13 Lambda changes and requested guidance rather than committing documentation marking the plan as apply-ready.

## Recommended Strategy: Option B

### Why Option B (Separate Backend Deployment First)

1. Preserves normal full-plan workflow
2. Avoids leaving acknowledged Terraform state differences hidden
3. Separates backend deployment risk from DynamoDB index creation
4. Produces clearer validation and rollback boundaries
5. Each change set gets independent testing and smoke validation

### Option B Sequence

1. ⬜ Keep ClientPetIndex apply **blocked**
2. ⬜ Review complete backend archive contents and deployment delta
3. ⬜ Prepare PET is_active hardening as a separate backend release
4. ⬜ Validate shared-package impact across all 13 Lambdas (baseline/candidate comparison)
5. ⬜ Obtain separate Matthew approval for backend deployment
6. ⬜ Deploy and validate the backend release independently
7. ⬜ Generate a new normal production Terraform plan afterward
8. ⬜ Verify new plan contains **only** `module.data.aws_dynamodb_table.main` (0 add, 1 change, 0 destroy)
9. ⬜ Obtain separate Matthew approval before applying the clean GSI plan

### Why Not Option A (Targeted -target Plan)

A targeted plan (`-target=module.data.aws_dynamodb_table.main`) would produce a narrower plan but:
- Leaves 13 Lambda state differences unacknowledged in Terraform
- Requires a follow-up full plan to reconcile
- Is an exceptional pattern not part of normal workflow
- Masks rather than resolves the underlying deployment gap

Targeted plan remains an exceptional fallback only and is **not authorized**.

---

## Current Production State

- ClientPetIndex: **undeployed and inactive**
- Backend code: production runs Phase 1A code (deployed at commit `234b51d` via plan `phase-1a-backend-deploy.tfplan`)
- PET is_active hardening: committed locally (`ca73d93`) but **not production-deployed**
- Latest deployed production release: **Phase 1B.1** (frontend only)
- Remediation: deferred
- Backend GSI query implementation: deferred
- Frontend pet inventory: deferred

## What Was NOT Done

- ❌ No Terraform apply
- ❌ No DynamoDB modification
- ❌ No Lambda deployment
- ❌ No AWS access during this review
- ❌ No new plan generated
- ❌ No saved plan deleted or modified
