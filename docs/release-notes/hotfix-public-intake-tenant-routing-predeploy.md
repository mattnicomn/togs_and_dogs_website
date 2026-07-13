# Hotfix: Public Intake Trusted Tenant Routing (Pre-Deploy)

**Date:** 2026-07-12
**Status:** Pre-Deploy (awaiting separate deployment approval)
**Type:** Backend security fix
**Scope:** Resolve TENANT_RESOLUTION_FAILED for unauthenticated POST /requests

---

## 1. Root Cause

In strict multi-tenant mode (`TENANT_RESOLUTION_MODE=multi`), `get_current_company_id()` raises `PermissionError` when no authenticated `custom:company_id` claim is present. The public `/requests` intake form is unauthenticated by design — prospective customers submit care requests without an account. This broke after strict mode was enabled (Release 18T).

## 2. Trusted Mapping Design

Added `resolve_public_intake_tenant(event)` in `common/auth.py`:

**Resolution order:**
1. If authenticated claims contain `custom:company_id` → use it (trusted Cognito claim)
2. If unauthenticated → use `PUBLIC_INTAKE_TENANT_ID` env var (server-configured)
3. If that's empty → fall back to `DEFAULT_COMPANY_ID` env var (`tog_and_dogs`)
4. If nothing available → raise `PermissionError` (fail closed)

**Never reads from:** request body, query string, browser headers, or client-controlled values.

The global `get_current_company_id()` strict resolver is NOT weakened. The public-intake resolver is a separate, route-scoped function used only by the intake handler for the `/requests` path.

## 3. Hybrid Client-Account Model

| Path | Behavior |
|------|----------|
| Anonymous `/requests` | Creates intake snapshot; no Cognito user; no profile link |
| Admin onboards client later | Creates Cognito user with `custom:company_id`; links profile |
| Returning authenticated client | Uses `/client/requests` with strict claim-based resolution |

Anonymous intake does NOT:
- Create a Cognito user
- Automatically merge with an existing client by email
- Modify existing profiles or pet records

## 4. Security Boundaries

| Threat | Mitigation |
|--------|-----------|
| Body `company_id` injection | Ignored — resolver never reads body |
| Query-string tenant selection | Not accepted |
| Arbitrary `Host`/`Origin` header | Not trusted |
| Cross-tenant authenticated request | Authenticated claim takes precedence |
| Missing configuration | Fails closed with PermissionError |

## 5. Production Configuration Required (Later)

No Terraform or Lambda env-var change is required for the current branded deployment. The code falls back to `DEFAULT_COMPANY_ID = "tog_and_dogs"` which is already available in the environment.

For future multi-brand deployments, the `PUBLIC_INTAKE_TENANT_ID` env var can be set per-Lambda or per-API-route to direct different branded intake forms to different tenants.

## 6. Tests (11 new)

| Test | Validates |
|------|-----------|
| authenticated_claim_takes_precedence | Cognito claim wins over server config |
| unauthenticated_uses_public_intake_tenant_id | PUBLIC_INTAKE_TENANT_ID env var used |
| unauthenticated_falls_back_to_default_company_id | DEFAULT_COMPANY_ID fallback works |
| fails_closed_without_any_config | PermissionError when no config |
| request_body_company_id_ignored | Body value never used |
| authenticated_second_tenant_user_uses_own_claim | Second tenant user keeps own claim |
| anonymous_public_intake_succeeds | Full handler integration passes |
| anonymous_intake_fails_without_trusted_config | Handler returns 500 when unconfigured |
| body_company_id_cannot_select_tenant | Saved record uses server tenant |
| no_cognito_user_created_by_anonymous_intake | No Cognito calls made |
| staff_options_works_anonymously | Staff-options endpoint works unauthenticated |

All 11 pass. Combined with tenant-assignment and isolation tests: 104 passed, 0 failed.

## 7. Separate Deployment Approval Gate

This fix requires a backend Lambda deployment (Terraform apply) that will update all 13 Lambdas with the new `common/auth.py` and `handlers/intake_handler.py`. No env-var, IAM, API Gateway, or configuration changes are needed.

## 8. What Was NOT Changed

- ❌ No deployment
- ❌ No Terraform apply
- ❌ No TENANT_RESOLUTION_MODE change
- ❌ No Cognito configuration change
- ❌ No global tenant-resolver weakening
- ❌ No Cognito self-signup enabled
- ❌ No second tenant created
- ❌ No Brea account modification
- ❌ No Stripe, Google Calendar, or mobile changes
- ❌ No frontend deployment
- ❌ No Client Management or saved-pet implementation
