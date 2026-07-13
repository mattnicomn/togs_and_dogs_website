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

**Resolution rules (corrected in d2913a4/6841da1):**
1. Domain mapping (`PUBLIC_INTAKE_DOMAIN_MAP`) is ALWAYS required on public routes
2. An unmapped or unknown `requestContext.domainName` fails closed — even if authenticated
3. If authenticated `custom:company_id` is present, it must MATCH the domain-mapped tenant
4. After domain resolution, the authoritative tenant record is validated (must exist and be active)
5. Missing, disabled, suspended, or malformed tenant records fail closed
6. No `DEFAULT_COMPANY_ID` fallback exists

**Never reads from:** request body, query string, Origin, Referer, browser headers, or client-controlled values.

**Configuration:** `PUBLIC_INTAKE_DOMAIN_MAP` is a JSON env var scoped to the intake Lambda only:
```json
{"a022yxuiue.execute-api.us-east-1.amazonaws.com": {"tenant_id": "tog_and_dogs", "active": true, "public_intake_enabled": true}}
```

**Transitional limitation:** The raw execute-api hostname mapping is a temporary single-tenant bridge for Togs & Dogs. It does NOT provide true multi-tenant hostname routing. A second tenant cannot be enabled until tenant-specific CloudFront/API routing exists.

The global `get_current_company_id()` strict resolver is NOT weakened. The public-intake resolver is a separate, route-scoped function used only by the intake handler for the public `/requests` and staff-options paths. Portal requests continue using the strict authenticated resolver.

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

## 5. Production Configuration Required

Deployment requires adding `PUBLIC_INTAKE_DOMAIN_MAP` to the intake Lambda environment only (scoped in `infra/prod/main.tf`, not the shared `notification_env_vars`). No other Lambda receives this variable.

## 6. Tests (35 public-intake + 4 corrected booking-limit)

**Public-intake routing tests:** 35 passed (domain mapping, fail-closed, body/query/header rejection, authenticated mismatch, tenant validation, no-persistence-on-failure, transitional guardrails)

**Corrected booking-limit tests:** 4 previously candidate-introduced failures now pass with proper domain context and active tenant records.

**Relevant suite:** 128 passed (combined intake, tenant, identity, isolation)

**Full-suite baseline comparison:**
- Baseline (9b0c5cc): 588 passed, 71 failed
- Candidate (6841da1): 597 passed, 71 failed
- **Zero new failing test names introduced**

## 7. Separate Deployment Approval Gate

Deployment requires a Terraform plan review and apply approval:
- `PUBLIC_INTAKE_DOMAIN_MAP` added to intake Lambda environment (intake-only, not shared)
- All 13 Lambdas receive updated code package (shared archive)
- Expected plan: 0 add, 13 change (code hash), 0 destroy + 1 env var on intake
- No IAM, API Gateway, Cognito, or other infrastructure changes

## 8. Transitional Architecture Limitations

**This implementation is a temporary single-tenant compatibility bridge:**

- The browser currently calls the raw API Gateway `execute-api` URL directly
- `requestContext.domainName` is identical for all requests under the current architecture
- The current mapping explicitly allows the single known execute-api hostname to resolve to `tog_and_dogs`
- This does NOT provide true multi-tenant hostname routing
- A second tenant CANNOT be enabled until tenant-specific CloudFront/API custom-domain routing exists
- The target architecture requires direct execute-api access to fail closed (unmapped)
- Future tenants will require per-tenant API custom domains or CloudFront distributions

**Commit 00338f2 (original DEFAULT_COMPANY_ID fallback) was superseded and never deployed.****Commit 00338f2 (original implementation) remains superseded by the domain-mapping approach. It was never deployed.**

## 9. What Was NOT Changed

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
