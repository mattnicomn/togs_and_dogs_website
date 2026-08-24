# DOMAIN-1 / B1A-ROUTE Web Release Candidate

**Date:** 2026-08-24

**Status:** ISOLATED / VALIDATED / NOT DEPLOYED

**Deployed Web baseline:** `4c7975d3bf9cd0ed84b0348015197034b9127dba`

This candidate starts from the exact password-recovery V2 release recorded as
deployed to the production S3/CloudFront site. It retains that recovery flow and
adds only the bounded `/t/:tenantSlug/admin` route, fail-closed route/claim/server
agreement, tenant-route navigation suppression, and focused tests.

## Runtime delta

- `web/src/App.jsx`: route bridge, refresh-safe tenant admin route, no shell
  tenant-info prefetch, and Platform Admin/global navigation suppression on the
  tenant route.
- `web/src/api/client.js`: optional URL-encoded `expectedTenantSlug` query value
  on the existing tenant-info request.
- `web/src/components/AdminDashboard.jsx`: validates tenant agreement before
  scheduling operational data fetches across existing-session, password, and
  new-password authentication paths.
- `web/src/utils/tenantContext.js`: generic fail-closed agreement boundary.

No E1/E2 workflow actions, Request List modernization, onboarding change,
unrelated Platform Admin behavior, backend, infrastructure, Cognito, DNS,
production data, or Mobile change is included.

## Validation

- Focused route/auth/Platform Admin regressions: 33 passed, including 7 new
  tenant-route tests.
- Full Vitest: 153 passed across 14 files.
- Legacy Web tests: 96 passed.
- Vite production build: passed, 108 modules transformed.
- Shared constants/API validator: 17 passed.
- Generated adapter validator: 7 passed on the established Windows line-ending
  rerun; generated files were restored with no candidate delta.
- Full lint remains the deployed-baseline debt at 51 errors / 9 warnings.
  Changed-file review is unchanged at App 2 errors and AdminDashboard 18 errors /
  5 warnings; `client.js`, the new tenant utility, and the new test have zero.
- `git diff --check`: passed.

## Read-only deep-link evidence

The production CloudFront source maps both S3-origin 403 and 404 responses to
`/index.html` with HTTP 200. A read-only HTTPS check of
`/t/test-tenant-alpha/admin` returned HTTP 200, `text/html`, the same 1,473-byte
body and ETag as `/index.html`, and `X-Cache: Error from cloudfront`. No
CloudFront change is required for this route.

No deployment or external-system change occurred while preparing this RC.
