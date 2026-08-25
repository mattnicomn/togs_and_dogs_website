# DOMAIN-1 and B1A-ROUTE Local Implementation

**Date:** 2026-08-24

**Status:** Implemented and validated locally / committed and pushed / not deployed

## Summary

DOMAIN-1 is recorded in `docs/planning/adr-domain-1-tenant-access-routing.md`. The Web SPA now supports `/t/:tenantSlug` and `/t/:tenantSlug/admin`; the landing route resolves to the existing owner/admin operational dashboard.

The route slug is an expected context only. The protected existing `/admin/tenant-info` API accepts an encoded `expectedTenantSlug`, resolves it through one centralized server-owned bridge registry, requires strict multi mode and an active authoritative tenant, and compares the canonical tenant ID with the Cognito `custom:company_id` claim. Unknown, inactive, missing-claim, wrong-claim, and lookup-failure cases return the same fail-closed denial with no default-tenant fallback.

The dashboard schedules no staff, client, request, tenant, or Calendar-status loading until agreement succeeds. Tenant routes suppress ordinary global navigation, including Platform Admin, while compatibility-host Platform Admin behavior remains unchanged. The verified tenant display name identifies the active workspace after authorization.

The current schema has no persisted tenant slug, so this bounded bridge centralizes only `test-tenant-alpha` → `test_tenant_alpha`. DOMAIN-6 must persist and provision unique DNS-safe slugs before general tenant onboarding.

## Validation

Focused backend and Web security suites cover valid agreement, wrong claim, unknown slug, inactive tenant, missing claim, strict multi mode, no primary fallback, generic denials, navigation persistence, Platform Admin separation, and the no-data-load authorization boundary.

- focused tenant-route backend: 14/14;
- related route, disabled-tenant, Platform Admin, and existing second-tenant info regression: 41/41;
- focused tenant-route Web: 7/7;
- full Web Vitest: 317/317 across 24 files;
- legacy Web: 99/99;
- Vite build: pass, 112 modules transformed;
- shared validators: 24/24 constants, 7/7 token adapters, 9/9 contract adapters, and 9/9 color tokens;
- Python compile check: pass;
- full Web lint: pre-existing nonzero baseline remains at 50 errors / 9 warnings; the new tenant utility and test file add zero lint findings.

One broader legacy tenant-enforcement selection completed 86/89; its three failures are existing entitlement/mock drift in unrelated review, export, and pet cases. A broader Google Calendar/tenant selection likewise exposed six existing unmocked AWS-credential failures. Neither failure set exercises or fails the new route resolver.

## Deployment boundary

No Web/backend deployment, DNS, Route53, CloudFront, ACM, API Gateway, Cognito callback, environment-variable, tenant-data, notification, Calendar, Stripe, Mobile build, or distribution change occurred. B1A remains blocked pending separately approved deployment and independent login-only isolation validation. B1B/B2/B3 remain not approved.

## ROUTE-GATE-A follow-up

The first DOMAIN-1 backend release-candidate plan is permanently rejected. Its unexpected API Gateway deployment replacement was traced to whole-provider-object hashing in the deployment trigger, not to the backend package. The canonical semantic fingerprint fix was subsequently deployed successfully through INFRA-GATE-A v2. Production now uses the same API semantics at deployment `atxpw3`, state serial 510.

Fresh branch `release/domain1-b1a-route-backend-v2-rc` correctly composes the deployed E3A baseline, deployed semantic infrastructure, and bounded DOMAIN-1 backend delta. Required validation then hit the explicit failed-test hard stop: 14 DOMAIN-1, 24 E3A, and 26 boundary tests passed, while the tenant-isolation selection had 48 passes and three known legacy mock/fixture failures. No package or plan was generated. ROUTE-GATE-A remains not ready, and the rejected plan is never reusable. See `docs/release-notes/domain-1-b1a-route-backend-v2-rc.md`.
