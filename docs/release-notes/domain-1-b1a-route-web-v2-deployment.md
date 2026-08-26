# DOMAIN-1 / B1A-ROUTE Web V2 Production Deployment

**Date:** 2026-08-25

**Status:** ROUTE-GATE-B COMPLETE / WEB DEPLOYED / ROUTE-GATE-C NOT APPROVED

## Approval boundary

Matthew explicitly approved only the exact reviewed Web v2 release candidate:

- branch `release/domain1-b1a-route-web-v2-rc`;
- runtime/build source `440cab2eae409dc3aed85f0af5056f885877aa91`;
- evidence head `154731c0175593b960784ddc483b593b250f7a2b`;
- exact 11-file `web/dist` artifact;
- sync to `s3://togs-and-dogs-prod-toganddogs-hosting` with removal of the
  retired JavaScript object; and
- CloudFront invalidation `/*` on distribution `E35L00QPA2IRCY`.

The approval excluded backend, API Gateway, Cognito, DNS/Route53/ACM, tenant
data, authenticated `test_tenant_alpha` login, synthetic fixtures, staff,
clients, pets, requests, assignment, Start, Complete, Stripe, secrets,
Calendar, notifications, Mobile, E1/E2/O1, and B1A/B1B/B2/B3.

## Exact RC and artifact verification

Development `main` started clean and synchronized at
`5a2aaded124adcdf62836ce98ef3d51ef021f108`. The RC and origin both resolved to
exact evidence head `154731c`; approved runtime source `440cab2` was its direct
runtime/test ancestor, with only the RC evidence document after it. The
worktree, index, and stash were empty and the dependency lockfile was unchanged.

The build was regenerated from detached exact source `440cab2` using `npm ci`
and `npm run build`. Vite 8.0.8 transformed 108 modules. At
`2026-08-26T00:28:34Z`, the result matched the approved artifact exactly:

- 11 files;
- 4,437,993 total bytes;
- `assets/index-BpY_nxft.js`, 1,056,394 bytes, SHA-256
  `F0BEFB80ABF02B1072E6D8984EFF455DE25DCA8781739D044A8DF2313CAEB782`;
- `assets/index-BroXJAxV.css`, 84,786 bytes, SHA-256
  `69A7D7BC6DD6A334A1D4304545ED9C844CAC637004264ECD5B8127C15E616990`;
- `index.html`, 1,473 bytes, SHA-256
  `398B785603E84637B7C115EE383D1214EB136E3326529032AEBE5831EFCC600D`.

## Pre-deployment production evidence

The authenticated AWS identity was the expected production workload account
ending `2897`, in `us-east-1`. The bucket and CloudFront distribution were the
approved targets. CloudFront was enabled and Deployed on the expected S3 origin,
with `index.html` as the default root and existing 403/404-to-`/index.html` 200
SPA fallback behavior.

The live primary baseline still matched source `4c7975d` byte-for-byte:

- `index.html`: SHA-256
  `3792F6DC32CCF2C1A83069B729BE5836652215EE3C79459829A93C7141F1D07F`;
- `assets/index-BtB1oa0E.js`: SHA-256
  `23F634AC141148A072FBE74561E2C437350343927128D42B5374C5F4D3C63D14`;
- `assets/index-BroXJAxV.css`: SHA-256
  `69A7D7BC6DD6A334A1D4304545ED9C844CAC637004264ECD5B8127C15E616990`.

The bucket contained exactly 11 objects. Three reviewed text/PWA objects had
CRLF-sized deployed bytes while the approved build had LF bytes:
`icons.svg` (5,055 -> 5,031), `manifest.webmanifest` (727 -> 695), and `sw.js`
(957 -> 931). Read-only download and normalization proved their text content
was otherwise identical. All objects shared the same prior deployment window;
this was newline representation, not an intervening Web deployment. The
approval expressly covered syncing the exact reviewed 11-file artifact.

The native dry run contained only reviewed keys: seven uploads and one deletion.
It proposed the new JS and index, exact LF versions of the three text/PWA files,
byte-identical CSS and logo re-uploads, and deletion of the retired JS. No
unreviewed key appeared.

Before the Web write, API stage `prod` still referenced deployment `atxpw3`.
All 13 Lambdas were Active/Successful on common CodeSha256
`W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=`.

## Exact S3 deployment

The established sync ran exactly once:

- UTC start: `2026-08-26T00:31:06.9344841Z`;
- UTC end: `2026-08-26T00:31:09.6612340Z`;
- exit code: `0`.

Exact operations reported by S3 sync:

- uploaded `index.html`;
- uploaded `assets/index-BpY_nxft.js`;
- deleted `assets/index-BtB1oa0E.js`;
- uploaded reviewed `assets/index-BroXJAxV.css` and
  `assets/usmh-logo-CrRnxp7-.png` with byte-identical content;
- uploaded exact reviewed LF bytes for `icons.svg`, `manifest.webmanifest`, and
  `sw.js`;
- left `favicon.svg`, `icon-192.png`, `icon-512.png`, and
  `icon-maskable-512.png` unchanged.

Read-only post-sync download proved exactly 11 objects / 4,437,993 bytes and
matched every approved build SHA-256. The retired JS object was absent.

## CloudFront invalidation and public verification

CloudFront invalidation `I4G5JQMQZFA5GRB4L1Z3M3P17T` was created at
`2026-08-26T00:31:49.622Z` for exactly `/*`. The bounded waiter exited 0 and the
invalidation reached `Completed`. CloudFront configuration was not changed.

Public edge checks returned HTTP 200 with the exact deployed bytes:

- `index.html`: 1,473 bytes / `398B7856...600D`;
- `assets/index-BpY_nxft.js`: 1,056,394 bytes / `F0BEFB80...B782`;
- `assets/index-BroXJAxV.css`: 84,786 bytes / `69A7D7BC...6990`.

Direct unauthenticated requests to `/t/test-tenant-alpha` and
`/t/test-tenant-alpha/admin` returned the exact new SPA index. In a fresh
unauthenticated browser, the short route redirected to the admin route and both
the direct load and refresh displayed only the staff sign-in boundary plus the
generic tenant-access denial. No operational dashboard marker or browser error
was present.

Malformed `/t/BAD_slug%21/admin` and unknown
`/t/unknown-tenant/admin` routes displayed the same generic unauthenticated
boundary with no operational content. The normal `/about` application route
rendered successfully. No credential was entered and no authenticated request
was attempted.

## Backend/API no-change and health

After Web deployment, API stage `prod` remained on `atxpw3` with its unchanged
last-update timestamp. All 13 Lambdas remained Active/Successful on the exact
same common CodeSha256. No Terraform or backend/API action occurred.

The distribution remained enabled and Deployed. Available deployment-window
CloudFront datapoints at 00:33 and 00:34 UTC reported 0.0% average/maximum 4xx
and 0.0% average/maximum 5xx. All tested assets returned their correct content
types and hashes; the unauthenticated browser recorded no console error or
warning. No new-JS 404 or loading failure was observed.

## Final boundary

ROUTE-GATE-B is complete. ROUTE-GATE-C/B1A-LOGIN remains not approved. B1A is
still blocked pending separately approved authenticated tenant-route validation;
B1B/B2/B3 remain not approved.

No Cognito, DNS, data, login, Stripe, Calendar, notification, Mobile,
E1/E2/O1, assignment, Start, or Complete action occurred.

**ROUTE-GATE-B COMPLETE — READY FOR ROUTE-GATE-C REVIEW.**

**DO NOT CONTINUE TO AUTHENTICATED LOGIN.**
