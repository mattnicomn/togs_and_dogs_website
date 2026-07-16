# Phase 1A: Terraform Plan Review — Pre-Apply

**Date:** 2026-07-16
**Status:** ✅ Plan Saved — Awaiting Matthew Approval to Apply
**Repository Commit:** `234b51d`
**Terraform Directory:** `infra/prod`

---

## Infrastructure Context

| Item | Value |
|------|-------|
| AWS Account | 358604342897 |
| AWS Profile | usmissionhero-website-prod |
| Region | us-east-1 |
| Terraform Version | 1.14.8 |
| Pre-checks | fmt ✅, validate ✅ |

## Saved Plan

| Item | Value |
|------|-------|
| Filename | `phase-1a-backend-deploy.tfplan` |
| Path | `infra/prod/phase-1a-backend-deploy.tfplan` |
| Gitignored | Yes (`.gitignore` excludes `*.tfplan`) |

## Plan Totals

| Metric | Count |
|--------|-------|
| Resources to add | 0 |
| Resources to change | 13 |
| Resources to destroy | 0 |

## Changed Resources (All In-Place)

| # | Resource Address | Update Type |
|---|-----------------|-------------|
| 1 | `aws_lambda_function.admin` | in-place |
| 2 | `aws_lambda_function.assign` | in-place |
| 3 | `aws_lambda_function.cancellation` | in-place |
| 4 | `aws_lambda_function.device` | in-place |
| 5 | `aws_lambda_function.google_auth` | in-place |
| 6 | `aws_lambda_function.intake` | in-place |
| 7 | `aws_lambda_function.job` | in-place |
| 8 | `aws_lambda_function.pet` | in-place |
| 9 | `aws_lambda_function.platform` | in-place |
| 10 | `aws_lambda_function.postmark_webhook` | in-place |
| 11 | `aws_lambda_function.review` | in-place |
| 12 | `aws_lambda_function.ses_feedback` | in-place |
| 13 | `aws_lambda_function.stripe_webhook` | in-place |

## Attributes Changed Per Lambda

- `source_code_hash` — updated (new backend code package)
- `last_modified` — provider-computed (known after apply)

## Attributes Confirmed Unchanged

- function_name
- handler
- runtime
- architectures
- role
- timeout
- memory_size
- environment variables (all values preserved)
- layers
- VPC configuration
- reserved concurrency
- dead-letter configuration
- tracing configuration
- ephemeral storage
- tags

## Unrelated Infrastructure Confirmed Unchanged

- ✅ API Gateway — no changes
- ✅ IAM — no changes
- ✅ Cognito — no changes
- ✅ DynamoDB — no changes
- ✅ S3 — no changes
- ✅ CloudFront — no changes
- ✅ Route 53 / DNS — no changes
- ✅ SES / Postmark — no changes
- ✅ Stripe configuration — no changes
- ✅ Google Calendar configuration — no changes
- ✅ Secrets Manager — no changes
- ✅ Tenant resolution mode — unchanged (remains multi)

## Why All 13 Lambdas Refresh

All 13 backend Lambda functions share a single deployment archive (`data.archive_file.backend_zip` which packages the entire `src/backend` directory). Any code change in `src/backend` produces a new `source_code_hash`, triggering an in-place update for all functions.

**Functional effect is limited to GET /admin/clients response normalization.** Other endpoints receive the same code package but their behavior is unchanged.

## Validation Reference

- Focused Phase 1A tests: 44 passed, 0 failed
- Full baseline (5c296e7): 685 collected, 614 passed, 71 failed
- Full candidate (ed0ca34): 712 collected, 641 passed, 71 failed
- Candidate-only failures: 0
- Production smoke checklist: `docs/release-notes/phase-1a-client-household-backend-validation-closeout.md`

## What Has NOT Occurred

- ❌ `terraform apply` has not been run
- ❌ No Lambda code has been deployed
- ❌ No production behavior has changed
- ❌ No Cognito, DynamoDB, Stripe, Google Calendar, or frontend changes

## Next Step

Matthew must separately and explicitly approve applying this saved plan to production. After apply, execute the production smoke checklist.
