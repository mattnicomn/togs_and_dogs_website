# Hotfix: Public Intake Domain Routing — Production Deployment

**Date:** 2026-07-13
**Status:** ✅ PASS — Deployed to Production
**Type:** Backend Lambda code + intake-only environment configuration
**Deployed Commit:** `40da715`
**Saved Plan:** `infra/prod/public-intake-domain-routing.tfplan`

---

## 1. Deployment Summary

| Item | Value |
|------|-------|
| Deployed commit | `40da715` |
| Terraform plan | `public-intake-domain-routing.tfplan` (exact saved plan) |
| Apply result | **0 added, 13 changed, 0 destroyed** |
| All Lambdas | Modifications complete |

## 2. Lambda Functions Updated

All 13 production Lambdas received updated `src/backend/` code package. The intake Lambda additionally received `PUBLIC_INTAKE_DOMAIN_MAP`:

| # | Function | Code Update | Env Var Change |
|---|----------|:-:|:-:|
| 1 | togs-and-dogs-prod-intake | ✅ | ✅ PUBLIC_INTAKE_DOMAIN_MAP added |
| 2 | togs-and-dogs-prod-admin | ✅ | ❌ None |
| 3 | togs-and-dogs-prod-assign | ✅ | ❌ None |
| 4 | togs-and-dogs-prod-cancellation | ✅ | ❌ None |
| 5 | togs-and-dogs-prod-device | ✅ | ❌ None |
| 6 | togs-and-dogs-prod-google-auth | ✅ | ❌ None |
| 7 | togs-and-dogs-prod-job | ✅ | ❌ None |
| 8 | togs-and-dogs-prod-pet | ✅ | ❌ None |
| 9 | togs-and-dogs-prod-platform | ✅ | ❌ None |
| 10 | togs-and-dogs-prod-postmark-webhook | ✅ | ❌ None |
| 11 | togs-and-dogs-prod-review | ✅ | ❌ None |
| 12 | togs-and-dogs-prod-ses-feedback | ✅ | ❌ None |
| 13 | togs-and-dogs-prod-stripe-webhook | ✅ | ❌ None |

## 3. What Was Deployed

- `common/auth.py`: Domain-based `resolve_public_intake_tenant` with strict `_validate_tenant_active`
- `handlers/intake_handler.py`: Public routes use domain resolver; portal routes use strict authenticated resolver
- `PUBLIC_INTAKE_DOMAIN_MAP` env var on intake Lambda only:
  - Maps `a022yxuiue.execute-api.us-east-1.amazonaws.com` → `tog_and_dogs`
  - active: true, public_intake_enabled: true

## 4. Transitional Bridge Limitations

- The raw execute-api mapping is a temporary single-tenant bridge for Togs & Dogs only
- No second tenant may be enabled with this bridge
- True tenant-specific CloudFront/API routing is required before a second tenant
- Direct execute-api access works ONLY because it is explicitly mapped

## 5. What Was NOT Done During Deployment

- ❌ No anonymous production request was submitted
- ❌ No Cognito user was created, linked, or modified
- ❌ No production data was written or changed
- ❌ No frontend deployment
- ❌ No TENANT_RESOLUTION_MODE change
- ❌ No Cognito self-signup enabled
- ❌ No second tenant created or enabled
- ❌ No Stripe, Google Calendar, or mobile changes

## 6. Rollback Approach

If issues are discovered:
1. Remove `PUBLIC_INTAKE_DOMAIN_MAP` from intake Lambda env in `infra/prod/main.tf`
2. Run `terraform plan` → expect intake Lambda env-var removal
3. Apply with Matthew approval
4. Public intake will return to TENANT_RESOLUTION_FAILED (same as before this deployment)
5. Authenticated portal/admin operations are unaffected by this rollback

## 7. Next Manual Verification Gate

Matthew should verify:
1. Load `https://toganddogs.usmissionhero.com/book`
2. Submit a test care request through the public form
3. Confirm the request appears in the admin Needs Action queue
4. Confirm no error occurs during submission
5. Confirm no Cognito account was created for the submitter
