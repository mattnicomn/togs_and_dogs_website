# ADR DOMAIN-1: Tenant Access Routing and Control-Plane Separation

**Status:** Accepted

**Decision date:** 2026-08-24

**Implementation state:** B1A route bridge implemented and validated locally; not deployed

---

## Context

The platform uses one Cognito pool and strict `TENANT_RESOLUTION_MODE=multi`. The authenticated `custom:company_id` claim is authoritative for tenant membership. The active internal tenant `test_tenant_alpha` and its enabled owner identity exist, but production has no normal tenant-specific owner landing URL. The shared compatibility host also currently contains tenant and Platform Admin routes.

The internal canonical ID and browser-safe route/domain name are intentionally different:

- canonical `company_id`: `test_tenant_alpha`;
- DNS-safe tenant slug: `test-tenant-alpha`.

Replacing hyphens with underscores is not a registry and is prohibited as a resolution mechanism.

## Decision

The target architecture separates two trust surfaces:

| Plane | Canonical hostname | Purpose |
|-------|--------------------|---------|
| Control | `platform.toganddogs.usmissionhero.com` | Platform Admin, tenant registry, subscriptions, entitlements, support, and platform audit |
| Tenant | `<tenant-slug>.toganddogs.usmissionhero.com` | One tenant's owner/admin/staff/client application |

`toganddogs.usmissionhero.com` remains a temporary primary-tenant compatibility host during migration.

Before wildcard tenant DNS exists, `/t/:tenantSlug/...` may provide a bounded bridge on the compatibility host. The bridge and future host bootstrap use the same invariant: route or host context is an expected-tenant constraint, never authorization.

## Authorization invariant

For a tenant route or host, the system must:

1. resolve the slug through a server-controlled registry;
2. load the canonical tenant metadata record;
3. require the tenant to be active;
4. require an authenticated Cognito `custom:company_id` claim;
5. require the claim to equal the registered canonical `company_id`;
6. only then render or request operational tenant data.

Unknown, malformed, missing, inactive, lookup-failed, or mismatched context fails closed. It does not redirect to another tenant and never falls back to `DEFAULT_COMPANY_ID`. Browser bodies, query values, local storage, Origin, Referer, or arbitrary headers cannot grant tenant membership.

The expected slug may be carried as an encoded API constraint, but the API resolves it through its own registry and performs the comparison. Client-side checks are defense in depth only.

## Slug registry ownership

DOMAIN-1/B1A-ROUTE introduces one centralized server-side bridge registry for the pre-existing internal test tenant:

`test-tenant-alpha` → `test_tenant_alpha`

The current tenant metadata schema has no persisted `tenant_slug`. No production schema or record is mutated in this slice. DOMAIN-6 must add unique, reserved-name-aware, DNS-safe slug provisioning and authoritative persistence before general tenant onboarding. Arbitrary tenants must not be hard-coded across UI components.

## Active and inactive tenants

The bridge requires both `is_active=true` and an allowed subscription state (`active` or `trialing`). Disabled, paused, canceled, malformed, or missing tenant records are denied with the same generic response as other resolution failures.

## Platform Admin boundary

Platform Admin remains available on its existing compatibility-host routes until DOMAIN-5 is separately deployed. Tenant-scoped navigation does not expose Platform Admin. The `platform_admin` group is not a tenant-route exception, does not bypass claim agreement, and does not grant impersonation. The final control-plane hostname will own Platform Admin navigation and cross-tenant audited operations.

## Login, refresh, logout, and callbacks

The current Web sign-in uses the Cognito SDK directly rather than a hosted Cognito callback. The route stays in the browser during login and new-password completion. Page refresh reconstructs the expected tenant from the URL and revalidates before data. Logout clears the Cognito session and reloads the same tenant URL, returning to the tenant login state.

Production Cognito callback settings are unchanged. Google OAuth and any future hosted-auth callbacks remain DOMAIN-4 prerequisites: they must preserve a verified initiating tenant without open redirects or primary-tenant substitution.

## Migration to tenant hosts

1. Deploy and independently validate the bounded route bridge after separate approval.
2. Add wildcard Route53, ACM, and CloudFront support under DOMAIN-3.
3. Replace the route-derived expected slug with a server-verified host-derived slug while retaining the same resolver and claim agreement.
4. Move Platform Admin to the control hostname under DOMAIN-5.
5. Keep the compatibility route/host for a measured period, then retire it after links, callbacks, and monitoring prove canonical-host readiness.

## Custom domains

A future verified custom domain maps to exactly one canonical tenant slug. Domain ownership verification, certificate lifecycle, disable/rollback, abuse controls, and canonical redirects are required. Custom domains use the same registry/claim agreement and never create a separate authorization model.

## Consequences and approval gates

- B1A-ROUTE is safe to validate locally without DNS or production data.
- B1A remains blocked until the route is deployed under separate approval and login-only isolation passes.
- Wildcard DNS is not required for B1A but remains required for the canonical tenant plane.
- Backend and Web deployment, CloudFront deep-link verification, Cognito/callback changes, and any B1A data creation remain separately approval-gated.
- This ADR authorizes no deployment, DNS, Cognito, tenant-data, infrastructure, or Mobile action.
