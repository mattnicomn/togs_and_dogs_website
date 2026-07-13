# Hotfix: Cognito Tenant Assignment — Production Deployment

**Date:** 2026-07-12
**Status:** ✅ PASS — Deployed to Production
**Type:** Backend Lambda code update (Terraform apply)
**Deployed Commit:** `cb35242`
**Previous Production Backend:** Last deployed 2026-07-10 (Release 22I baseline)

---

## 1. Deployment Summary

| Item | Value |
|------|-------|
| Deployed commit | `cb35242` |
| Terraform plan file | `infra/prod/hotfix-tenant-assignment.tfplan` |
| Terraform version | v1.14.8 |
| AWS profile | `usmissionhero-website-prod` |
| Apply result | **0 added, 13 changed, 0 destroyed** |

## 2. Lambda Functions Updated

All 13 production Lambdas received the updated `src/backend/` code package:

| # | Function Name | Status |
|---|--------------|--------|
| 1 | togs-and-dogs-prod-admin | ✅ Modifications complete |
| 2 | togs-and-dogs-prod-assign | ✅ Modifications complete |
| 3 | togs-and-dogs-prod-cancellation | ✅ Modifications complete |
| 4 | togs-and-dogs-prod-device | ✅ Modifications complete |
| 5 | togs-and-dogs-prod-google-auth | ✅ Modifications complete |
| 6 | togs-and-dogs-prod-intake | ✅ Modifications complete |
| 7 | togs-and-dogs-prod-job | ✅ Modifications complete |
| 8 | togs-and-dogs-prod-pet | ✅ Modifications complete |
| 9 | togs-and-dogs-prod-platform | ✅ Modifications complete |
| 10 | togs-and-dogs-prod-postmark-webhook | ✅ Modifications complete |
| 11 | togs-and-dogs-prod-review | ✅ Modifications complete |
| 12 | togs-and-dogs-prod-ses-feedback | ✅ Modifications complete |
| 13 | togs-and-dogs-prod-stripe-webhook | ✅ Modifications complete |

Only `source_code_hash` and `last_modified` changed. No environment variables, IAM, API Gateway, Cognito, DynamoDB, or configuration changes.

## 3. What Was Deployed

- `common/auth.py`: Added `build_tenant_user_attribute()` and `ensure_cognito_tenant_attribute()` helpers
- `handlers/admin_handler.py`: Staff/client onboarding includes `custom:company_id`; link-cognito validates tenant before group/profile mutation

## 4. Test Results (Pre-Deploy)

| Suite | Result |
|-------|--------|
| Focused hotfix tests | 29 passed |
| Relevant tenant/isolation suite | 94 passed |
| Python compile | ✅ Success |
| Full-suite baseline comparison | 578 passed, 55 pre-existing failures (identical at parent and candidate) |

## 5. What Was NOT Done

- ❌ Brea's Cognito account was NOT repaired (requires separate approval gate)
- ❌ No production user was created, onboarded, linked, or modified
- ❌ Public POST /requests tenant routing was NOT changed
- ❌ No frontend deployment
- ❌ No Cognito user pool schema changes
- ❌ No IAM policy changes
- ❌ No API Gateway changes
- ❌ No DynamoDB writes
- ❌ No Stripe changes
- ❌ No Google Calendar changes
- ❌ No mobile/TestFlight/App Store changes
- ❌ TENANT_RESOLUTION_MODE was NOT modified

## 6. Remaining Approval Gates

| Gate | Description | Status |
|------|-------------|--------|
| A | Backend deployment of cb35242 | ✅ Complete |
| B | Read-only Cognito check for Brea | ⏳ Awaiting approval |
| C | One-user Cognito repair (set custom:company_id) | ⏳ Awaiting approval |
| D | Public-intake tenant-routing design | ⏳ Unstarted |

## 7. Post-Repair Requirements

After Gate C (Brea repair) is approved and executed:
- Brea must fully log out and log back in
- A page refresh alone may not suffice (cached token may lack the new claim)
- After fresh login, authenticated requests should resolve `custom:company_id = tog_and_dogs`
