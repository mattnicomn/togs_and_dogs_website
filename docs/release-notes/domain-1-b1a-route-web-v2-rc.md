# DOMAIN-1 / B1A-ROUTE Web V2 Release Candidate

**Date:** 2026-08-25

**Status:** ROUTE-GATE-B REVIEW COMPLETE / READY FOR MATTHEW APPROVAL / NOT DEPLOYED

**Branch:** `release/domain1-b1a-route-web-v2-rc`

**Exact runtime/build source:** `440cab2eae409dc3aed85f0af5056f885877aa91`

**Deployed Web source baseline:** `4c7975d3bf9cd0ed84b0348015197034b9127dba`

ROUTE-GATE-A is complete: the DOMAIN-1 backend is deployed, Terraform state is
serial 513, API Gateway remains `prod -> atxpw3`, and all 13 backend Lambdas are
Active/Successful on common CodeSha256
`W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=`. This document records a fresh,
isolated Web review only. No Web deployment, authenticated login, or production
mutation occurred.

## Deployed baseline proof

The production CloudFront site was fetched independently and then compared with
a production build from exact commit `4c7975d`. The built and live entry point,
primary JavaScript, and CSS matched byte-for-byte:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `index.html` | 1,473 | `3792F6DC32CCF2C1A83069B729BE5836652215EE3C79459829A93C7141F1D07F` |
| `assets/index-BtB1oa0E.js` | 1,055,326 | `23F634AC141148A072FBE74561E2C437350343927128D42B5374C5F4D3C63D14` |
| `assets/index-BroXJAxV.css` | 84,786 | `69A7D7BC6DD6A334A1D4304545ED9C844CAC637004264ECD5B8127C15E616990` |

Read-only S3 metadata independently confirmed those object sizes and a
1,473-byte `index.html` ETag of `"1c3a4efdaf87c79409ed06686a9adb09"`.
Therefore `4c7975d` still represents the actual deployed Web application source.

## Prior RC and fresh composition

The prior, never-deployed RC `8d3c8ae2b6231ddcd638efba95380a05e6165c67`
has `4c7975d` as its direct parent. Its only application delta was the reviewed
DOMAIN-1 Web implementation plus its test and release note. The fresh v2 branch
was created from exact deployed baseline `4c7975d` and the reviewed patch was
replayed without reusing the old release commit. Additional changes in the new
test file only harden the required stale-state and negative bootstrap evidence.

The exact source/test delta from the deployed baseline is:

- `web/src/App.jsx`: `/t/:tenantSlug` redirect and refresh-safe admin route,
  tenant-key remount, tenant-route shell isolation, and suppression of global and
  Platform Admin navigation on the tenant plane.
- `web/src/api/client.js`: optional, URL-encoded `expectedTenantSlug` on the
  existing tenant-info request.
- `web/src/components/AdminDashboard.jsx`: one shared authenticated bootstrap
  boundary for existing-session, sign-in, and new-password flows; operational
  fetches are scheduled only inside the post-verification authorization callback.
- `web/src/utils/tenantContext.js`: bounded slug validation and fail-closed
  route/claim/server agreement using one generic tenant-access error.
- `web/tests/TenantScopedRouting.test.jsx`: 13 tenant-route, failure-boundary,
  Platform Admin navigation, refresh, and stale-state tests.

There are no backend, Mobile, Terraform, DNS, Cognito, Stripe, Calendar,
notification, onboarding-preview, Request List, E1/E2/O1, billing, or unrelated
authentication changes. The dependency lockfile is unchanged.

## Security, failure, and stale-state review

The route slug is presentation context only. The browser supplies it to the
deployed backend as `expectedTenantSlug`; the backend remains authoritative. The
Web permits the operational dashboard bootstrap only when the authenticated
session has a company claim and the server returns the same canonical company
with `is_access_allowed === true` and `is_blocked !== true`.

Malformed slugs and missing claims fail before resolution. Unknown tenants,
disabled/inactive tenants, wrong-tenant responses, backend 401/403 responses,
and network failures all collapse to the same generic error and never schedule
operational loading. Platform Admin navigation is absent from tenant routes,
and the dashboard's existing tenant-plane role allowlist does not treat
`platform_admin` as a tenant owner/admin/staff role.

The route component is keyed by tenant slug, so every A-to-B tenant change
unmounts the prior dashboard and begins with empty local state. Tests combine
that remount proof with explicit valid-A to inactive-B, wrong-tenant-B, and
unknown-B authorization failures. Tenant-to-compatibility navigation also
clears mounted operational state. A direct refresh of both tenant URL forms
lands on the tenant dashboard route, with the short form redirected to
`/t/<slug>/admin`.

## CloudFront deep-link evidence

Read-only distribution metadata confirms the enabled production distribution
uses the expected S3 origin, has `index.html` as its default root object, and
maps both origin 403 and 404 errors to `/index.html` with HTTP 200. Read-only
HTTPS requests to `/t/test-tenant-alpha` and
`/t/test-tenant-alpha/admin` each returned the exact deployed 1,473-byte index
body and ETag. No CloudFront, S3, or DNS mutation was needed.

## Backend contract compatibility

The deployed backend accepts `expectedTenantSlug` on the existing
`GET /admin/tenant-info` compatibility endpoint. When supplied, the server
resolves the registered active tenant against authenticated claims and returns
`company_id`, tenant display/subscription fields, `is_access_allowed`, and
`is_blocked`. When omitted, the established compatibility-host path remains in
place. Server denials use 403, the authorizer may return 401, and the Web maps
all resolver failures to its generic fail-closed tenant error.

## Validation

- Dependency restore: `npm ci` passed with no lockfile change.
- Focused tenant route/bootstrap/Platform boundary: **13/13 passed**.
- Legacy Web tests: **96/96 passed**.
- Vitest component suite: **159/159 passed across 14 files**.
- Total unique Web tests: **255/255 passed**.
- Production build: passed with Vite 8.0.8; 108 modules transformed.
- Changed test/utility/client lint: 0 errors and 0 warnings.
- Full repository lint: the exact deployed-baseline debt of 51 errors and 9
  warnings; no new candidate lint issue.
- Shared color tokens: **9/9 passed**.
- Shared constants/API contracts: **17/17 passed**.
- Generated adapters: **7/7 passed** after the established Windows line-ending
  normalization rerun; generated files were restored with zero diff.
- `git diff --check`: passed.

## Production artifact

Build verification timestamp: `2026-08-26T00:13:34Z`

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `assets/index-BpY_nxft.js` | 1,056,394 | `F0BEFB80ABF02B1072E6D8984EFF455DE25DCA8781739D044A8DF2313CAEB782` |
| `assets/index-BroXJAxV.css` | 84,786 | `69A7D7BC6DD6A334A1D4304545ED9C844CAC637004264ECD5B8127C15E616990` |
| `assets/usmh-logo-CrRnxp7-.png` | 2,583,401 | `9C528F7EA13B41888E24CA434FF972604E9E0558E44F74AD1F10EC102282BA65` |
| `favicon.svg` | 9,522 | `61BC9A161DE58248288E6905425D7180F0624C2865007B97D763FDAC12043A66` |
| `icon-192.png` | 47,200 | `6AF049248D9848006890C9E4B4DE52AAF9976AF456F78FCC26FB68EC7D3F14E7` |
| `icon-512.png` | 324,280 | `B069DACC9DB0CCF299F5674CDD6ADF19EF13382E3EBB685533C5DD23D7D586FC` |
| `icon-maskable-512.png` | 324,280 | `B069DACC9DB0CCF299F5674CDD6ADF19EF13382E3EBB685533C5DD23D7D586FC` |
| `icons.svg` | 5,031 | `B45FA506195CFCDEF406BA9F0C77B36DDC1A7C224040926EC70ABC2FDEA7B93A` |
| `index.html` | 1,473 | `398B785603E84637B7C115EE383D1214EB136E3326529032AEBE5831EFCC600D` |
| `manifest.webmanifest` | 695 | `2839A8915A522CB4D386241C4E4DCCE5D21DE7116B60FC06820CA0FFF04CB5E9` |
| `sw.js` | 931 | `C380BE95E881562FAFF0632C7081D4A6A19DA5C2730261538B846C36F69F4E57` |

Summary: **11 files / 4,437,993 bytes**. Compared with production, only
`index.html` and the primary JavaScript object change. CSS, logo, icons,
manifest, and service worker remain byte-identical. The superseded production
JS object is `assets/index-BtB1oa0E.js`.

## Future deployment plan — not executed

After separate Matthew approval only:

1. Reconfirm this exact RC and reproduce the recorded artifact hashes from
   `web/dist`.
2. Use the established static deployment from `web/` to sync `dist/` to
   `s3://togs-and-dogs-prod-toganddogs-hosting` with `--delete` and production
   profile `usmissionhero-website-prod`.
3. Expect upload of `index.html` and `assets/index-BpY_nxft.js`, deletion of
   superseded `assets/index-BtB1oa0E.js`, and no content change to the other nine
   files. Preserve all reviewed static/PWA assets by including the complete
   exact `dist` artifact.
4. Invalidate `/*` on CloudFront distribution `E35L00QPA2IRCY`, wait for
   completion, and perform only separately authorized non-write validation.

Rollback requires separate approval and restores only the exact deployed Web
artifact built from `4c7975d`, including `index-BtB1oa0E.js`, the baseline
`index.html`, and the nine unchanged files. It does not roll back the DOMAIN-1
backend, E3A, or semantic API fingerprint infrastructure.

## Gate boundary

No hard-stop condition was found. The deployed baseline is proven, composition
is unambiguous and bounded, the authorization model remains server-owned,
failure and stale-state behavior is fail-closed, direct deep links work, the
backend contract matches, all Web tests and the build pass, and the lockfile is
unchanged.

ROUTE-GATE-B still requires Matthew's explicit deployment approval.
ROUTE-GATE-C/B1A-LOGIN is not approved. B1A remains blocked pending Web
deployment and separately approved authenticated tenant-route validation;
B1B/B2/B3 remain not approved.

**ROUTE-GATE-B READY FOR MATTHEW APPROVAL.**

**DO NOT DEPLOY WEB.**
