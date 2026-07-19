# Phase 1B.2A: Backend-Only Plan Review Closeout

**Date:** 2026-07-18
**Reviewer:** Kiro
**Status:** ✅ READY FOR BACKEND APPLY APPROVAL

---

## Commits Reviewed

| Commit | Description |
|--------|-------------|
| `f3b9a79` | chore(infra): temporarily remove ClientPetIndex for backend release |
| `193750d` | docs: record backend-only Terraform plan |

## Plan Identity

| Item | Value |
|------|-------|
| Saved plan | `infra/prod/phase-1b2a-backend-only.tfplan` |
| Plan checksum (SHA256) | `102f899be77e57f278b0878d6b341ca9326b801cceb8a5be404cd98eaafbc5c1` |
| Plan summary | **0 to add, 13 to change, 0 to destroy** |

## Package Identity

| Item | Value |
|------|-------|
| Archive | `infra/prod/backend.zip` |
| ZIP checksum (SHA256) | `556fa0a147967ef61c6363f96559e4eed5aac46ba3dff234afa3262c074f008a` |
| Total entries | 39 (all tracked source files) |
| Cache/bytecode entries | 0 |

## Source-Code-Hash Reconciliation

- ZIP SHA256 hex: `556fa0a147967ef61c6363f96559e4eed5aac46ba3dff234afa3262c074f008a`
- Base64 encoding: `VW+goUeWfvYcY2P5ZVnk7tWqxGuj3/I0r6MmLAdPAIo=`
- Plan proposed hash: `VW+goUeWfvYcY2P5ZVnk7tWqxGuj3/I0r6MmLAdPAIo=`
- **Match: ✅**

## Exact 13 Resources (All In-Place)

| # | Resource | Changed Fields |
|---|----------|---------------|
| 1 | `aws_lambda_function.admin` | source_code_hash, last_modified |
| 2 | `aws_lambda_function.assign` | source_code_hash, last_modified |
| 3 | `aws_lambda_function.cancellation` | source_code_hash, last_modified |
| 4 | `aws_lambda_function.device` | source_code_hash, last_modified |
| 5 | `aws_lambda_function.google_auth` | source_code_hash, last_modified |
| 6 | `aws_lambda_function.intake` | source_code_hash, last_modified |
| 7 | `aws_lambda_function.job` | source_code_hash, last_modified |
| 8 | `aws_lambda_function.pet` | source_code_hash, last_modified |
| 9 | `aws_lambda_function.platform` | source_code_hash, last_modified |
| 10 | `aws_lambda_function.postmark_webhook` | source_code_hash, last_modified |
| 11 | `aws_lambda_function.review` | source_code_hash, last_modified |
| 12 | `aws_lambda_function.ses_feedback` | source_code_hash, last_modified |
| 13 | `aws_lambda_function.stripe_webhook` | source_code_hash, last_modified |

**Configuration unchanged:** handler, runtime, memory_size, timeout, role, architectures, environment variables, layers, VPC, reserved concurrency, dead-letter, tracing, ephemeral storage, tags.

**No replacement. No destruction. No DynamoDB, API Gateway, IAM, Cognito, S3, CloudFront, or Route 53 resources.**

## Packaged Source Delta

- Baseline: `234b51d` (BEST DOCUMENTED DEPLOYED BASELINE)
- Only change: `src/backend/handlers/pet_handler.py` — 5 inserted lines (commit `ca73d93`)
- No common module changed
- No other handler changed
- `scripts/remediate_pet_legacy_attributes.py` is outside `src/backend/` — not packaged

## PET Hardening Assessment: PASS

- New PET without is_active → defaults to True ✅
- Explicit is_active=True → True ✅
- Explicit is_active=False → False ✅
- Existing active PET update without is_active → True preserved ✅
- Existing archived PET update without is_active → False preserved ✅
- Legacy PET missing is_active updated without is_active → remains absent ✅
- Tenant verification unchanged ✅
- PET list/read behavior unchanged ✅
- Unknown caller-supplied petId upsert: pre-existing design risk, not a new regression

## Deployment Mechanics and Mixed-Version Risk

- All 13 Lambdas use the same archive ($LATEST, no versions/aliases)
- Only `pet_handler.py` has modified runtime behavior
- No other handler imports pet_handler
- No shared common module changed
- Terraform may update the 13 resources independently
- A partial apply failure could temporarily leave mixed package hashes
- Practical runtime risk is low (other handlers execute byte-identical supporting code) but is NOT zero

## Rollback Procedure

1. Revert only `ca73d93` in a reviewed current-mainline commit
2. Preserve archive exclusions and current infrastructure configuration
3. Generate a current-state rollback plan
4. Obtain separate Matthew approval
5. Apply the rollback plan

The currently deployed ZIP artifact was not empirically retrieved during this review. A rollback package would be rebuilt from the documented baseline source using the corrected archive exclusions.

**Do NOT apply Terraform from the old full repository state at `234b51d`.**

## Post-Apply Smoke-Test Requirements

### Read-only checks
- Authentication behavior
- Admin client list
- Admin pet list
- Intake endpoint health
- Staff/client onboarding endpoint health
- Lambda import and initialization checks
- CloudWatch error review for all 13 functions

### PET behavior checks (require separate production test-data approval)
- Create PET without is_active → confirm True
- Preserve True when omitted on update
- Explicit False
- Preserve False when omitted on update
- Tenant isolation

**Production PET creation or deletion requires separate explicit Matthew approval.** Backend apply approval alone does NOT authorize production test-data writes. Ryan testing remains paused.

## Status Summary

- Old combined GSI/Lambda plan: must NEVER be applied
- ClientPetIndex: temporarily absent from configuration; restoration is separately gated
- Latest deployed production release: Phase 1B.1
- No AWS access occurred during this review
- No apply or deployment occurred

---

## Next Approval Gate

**Matthew approves applying the saved backend-only plan:**
```
terraform -chdir=infra/prod apply phase-1b2a-backend-only.tfplan
```

This deploys the clean 39-file backend archive (with PET is_active hardening) to all 13 Lambda functions. No DynamoDB or other infrastructure changes.
