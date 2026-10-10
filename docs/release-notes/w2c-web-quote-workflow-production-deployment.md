# W2C — Web Canonical Quote Workflow Production Deployment (Gate D2 + D3)

Status: **DEPLOYED TO PRODUCTION / D3 NON-MUTATING VERIFICATION PASSED / COMPLETE.**
Matthew-approved Gate W2C-D2 deployed the already-reviewed D0 web artifact (source
`7c1a8f1f898233e37ee5c77e38bb92058deee3c7`) to the Togs & Dogs production web hosting
(S3 + CloudFront). No rollback was required. No backend/API change. No production
quote mutation (no PATCH/Send/Accept/Decline), no production test data, no M4.

Deployment date: 2026-10-08.

References:
- D0 local artifact prep: `PETCARE_HERO_W2C_D0_LOCAL_ARTIFACT_READY_FOR_D1`.
- D1 read-only precheck: `PETCARE_HERO_W2C_D1_READ_ONLY_PRECHECK_PASSED_D2_APPROVAL_REQUIRED`.
- Prior web production baseline: PTM0-S2BC coordinated deployment
  (`docs/release-notes/ptm0-s2bc-coordinated-production-deployment.md`), live JS
  `assets/index-D3a5IJFf.js`.
- Backend quote routes already live: OPS-3A.3
  (`docs/release-notes/ops3a3-production-deployment.md`).

---

## Deployed source and scope

- Source checkpoint: `main == origin/main == 7c1a8f1f898233e37ee5c77e38bb92058deee3c7`.
- Candidate scope (all undeployed web runtime work since the PTM-3D.1 web baseline
  `30e447b`), explicitly accepted by Matthew (`C092ED2_RIDEALONG_ACCEPTED=YES`):
  - **W2A** — web admin canonical quote API client foundation (`7c345c2`).
  - **W2B** — canonical admin quote editor (`ca12183`).
  - **W2C** — Send Quote / DRAFT → SENT (`7c1a8f1`).
  - **`c092ed2`** — LOW-risk Google Calendar unknown-status handling (display-only
    admin status-card hardening; accepted ride-along).
- Web-only runtime change. Backend/API unchanged.

## Production target (account `358604342897`)

- S3 hosting bucket: `togs-and-dogs-prod-toganddogs-hosting` (us-east-1).
- CloudFront distribution: `E35L00QPA2IRCY`, alias `toganddogs.usmissionhero.com`,
  origin `togs-and-dogs-prod-toganddogs-hosting.s3.us-east-1.amazonaws.com`.
- Profile: `usmissionhero-website-prod` (SSO AdministratorAccess assumed role).
- Production API (unchanged): REST API `a022yxuiue`, stage `prod`, deployment `hhryhc`.
- Backend package (unchanged): all 13 Lambdas on
  `CodeSha256 = gBjdlXDUn0+0gHHyF/W5aKv35NROe81lsQZbBf4YR6I=`.

## D0 artifact (deployed) hashes

| File | SHA256 |
|---|---|
| `index.html` | `cc453a6eae57fc8b913d32087b732de59928b7616dde5866e7b92de283b85a57` |
| `assets/index-DrAWpyW_.js` | `a3616d7e3ee70ff5dbc47e831167ec14697ef5894c2ef4be93439fb7e90d7563` |
| `assets/index-DEfFpwho.css` | `c2f06e9b2d384e663d0fe6e676bfe0f72d2c1188cf93afac9824e822673607c0` |

Build: `npm ci` + `vite build --mode production` in `web/` (deterministic;
`package.json`/`package-lock.json` unmodified). Artifact = 11 objects. Env resolution
verified: `VITE_API_URL`→`a022yxuiue/prod`, region `us-east-1`, production Cognito
pool/client; no dev/sandbox/org-migration endpoint in the bundle.

## Pre-deployment rollback snapshot (MANDATORY — versioning disabled)

`S3_VERSIONING_STATUS=Disabled/NotConfigured`, so the entire current production object
set was downloaded to a local rollback snapshot before `aws s3 sync --delete`.
`PREDEPLOY_ROLLBACK_SNAPSHOT_COMPLETE=YES` — 11 objects, baseline hashes verified
identical to the D1 live baseline:

| File | SHA256 |
|---|---|
| `index.html` | `7546b2ccc8b7903ca0d4f7487803f8a69df57e49f6591a84381a235c3f5a73a7` |
| `assets/index-D3a5IJFf.js` | `9184a29016e912d983abc988b7bce100d96eedc265298456911e4d1a3e1cc7ea` |
| `assets/index-BroXJAxV.css` | `69a7d7bc6dd6a334a1d4304545ed9c844cac637004264ecd5b8127c15e616990` |

## Deployment operations

1. Pre-deploy gates: checkpoint `7c1a8f1` clean; D0 hashes re-verified; AWS identity
   reconfirmed `358604342897`; CloudFront `Deployed`; admin Lambda on `gBjdlXDUn0…`.
2. Full 11-object rollback snapshot captured and verified.
3. `aws s3 sync web/dist/ s3://togs-and-dogs-prod-toganddogs-hosting --delete --profile usmissionhero-website-prod`:
   - DELETED: `assets/index-D3a5IJFf.js`, `assets/index-BroXJAxV.css` (retired baseline bundles).
   - UPLOADED: `index.html`, `assets/index-DrAWpyW_.js`, `assets/index-DEfFpwho.css`,
     `manifest.webmanifest`, `sw.js`, `icons.svg`, `assets/usmh-logo-CrRnxp7-.png`.
   - No errors; no unexpected deletions outside the reviewed artifact set.
4. Post-sync S3 verification: bucket = exactly the 11 D0 objects; no stale hashed
   bundles; `POSTSYNC_S3_ARTIFACT_MATCH=YES` (downloaded index/JS/CSS == D0 hashes).
5. `aws cloudfront create-invalidation --distribution-id E35L00QPA2IRCY --paths "/*"`
   → invalidation `I85ZQJRXKOEC91ICRF7Y18BMNV`; `CLOUDFRONT_INVALIDATION_COMPLETED=YES`
   (waiter confirmed); distribution remained `Deployed`.

## D3 non-mutating verification

Scope note: D3 verified the deployed **static artifact at the edge** and the
backend/API-unchanged facts. It did **not** perform an interactive authenticated
browser smoke. The two are reported separately and must not be conflated:

- `D3_STATIC_EDGE_VERIFICATION=PASS`
- `D3_INTERACTIVE_BROWSER_SMOKE=NOT_PERFORMED` (optional/future; owner-verifiable; must
  not access real customer data merely to prove the UI)

### `D3_STATIC_EDGE_VERIFICATION=PASS`

- **Edge artifact match** (`EDGE_ARTIFACT_MATCH=YES`) — fetched from
  `https://toganddogs.usmissionhero.com/`:
  - index.html SHA256 `cc453a6e…b85a57` == D0.
  - `/assets/index-DrAWpyW_.js` SHA256 `a3616d7e…0d7563` == D0.
  - `/assets/index-DEfFpwho.css` SHA256 `c2f06e9b…3607c0` == D0.
  - Edge index.html references the new bundles `/assets/index-DrAWpyW_.js` +
    `/assets/index-DEfFpwho.css`; retired `index-D3a5IJFf.js` no longer served.
- **Static bundle inspection (non-mutating)** — the edge-served JS bundle statically
  contains the W2C quote-editor UI marker (`admin-quote-editor`) and the Send
  confirmation copy ("Send this quote to the client"), and resolves to the production
  API `a022yxuiue/prod`. This is static text inspection of the served bundle, not a
  rendered-DOM assertion.
- **Backend/API unchanged** — `BACKEND_CHANGED_BY_D2=NO` (admin Lambda still
  `gBjdlXDUn0…`), `API_CHANGED_BY_D2=NO` (stage `prod` still deployment `hhryhc`).

### `D3_INTERACTIVE_BROWSER_SMOKE=NOT_PERFORMED`

The following were **not** performed in D2/D3 and remain optional/future owner
verification (none require accessing real customer records to prove the UI):

- interactive authenticated browser login flow;
- admin portal DOM render verification;
- CareCard quoting-tab quote-editor render against a real request;
- browser-console inspection during authenticated portal use.

## Notification safety

`QUOTE_SEND_EXTERNAL_NOTIFICATION_SIDE_EFFECT=NONE`. The deployed `POST
/admin/requests/{requestId}/quote/send` performs a state transition + audit entry only
(no `notify_event`, no email/SMS/push, no DynamoDB stream, no EventBridge consumer).
"Send Quote" makes a quote canonical `SENT`/client-visible; it does not proactively
message the client. The web Send UI calls only `sendAdminRequestQuote(requestId)`.

## Boundaries honored (NOT performed)

No production quote creation/update/Send/Accept/Decline, no production test data, no
direct application-API functional invocation, no M4, no backend/Lambda/API Gateway/
Terraform/Cognito/Stripe change, no mobile build/distribution, no Ryan testing, no
second tenant, no tenant-resolution change, no GAP-1/GAP-2/GAP-3 or W4/W1/W3 work.

- `M4_PRODUCTION_MUTATION_TEST_AUTHORIZED=PAUSED_FOR_WORKFLOW_RECONCILIATION`
- `FUNCTIONAL_PRODUCTION_TEST_AUTHORIZED=NO`
- `RYAN_TESTING_AUTHORIZED=NO`
- `MOBILE_PUBLIC_DISTRIBUTION_AUTHORIZED=NO`
- Stripe remains sandbox-only.

## Rollback readiness

- `W2C_WEB_ROLLBACK_READY=YES`. Method
  `REBUILD_OR_PRESERVED_OBJECT_RESYNC_PLUS_CLOUDFRONT_INVALIDATION` (S3 versioning is
  Disabled/NotConfigured — **S3 version-restore is NOT available**).
- Durable rollback evidence: the preserved 11-object pre-deploy production snapshot is
  stored outside the repo at
  `C:\USMISSIONHERO\release-evidence\petcare-hero\w2c-web-2026-10-10\predeploy-web-snapshot`
  (not committed, cannot be staged). Verified: 11 files; baseline hashes index.html
  `7546b2cc…`, `assets/index-D3a5IJFf.js` `9184a290…`, `assets/index-BroXJAxV.css`
  `69a7d7bc…`.
- Fallback rollback source: baseline commit `30e447b` (rebuildable web project).
- Rollback = restore the preserved prior objects (or rebuild `30e447b`) → `aws s3 sync
  … --delete` → CloudFront `/*` invalidation → edge re-verify the prior baseline hashes.
  Not required (deploy verified clean).

## Resume point

- Production web now serves the canonical owner/admin quote editor (W2B) and Send Quote
  (W2C), plus the W2A client foundation and the accepted `c092ed2` ride-along.
- Next separately gated step: **M4 readiness / execution** — owner/admin create+save a
  DRAFT (W2B) and Send (W2C) on a safe operator-controlled candidate, confirm client
  SENT visibility, then one Matthew-approved mobile Decline. M4 remains paused and
  requires fresh explicit Matthew approval (`M4_FRESH_EXECUTION_APPROVAL_REQUIRED=YES`).

Disposition: **`PETCARE_HERO_W2C_D2_DEPLOYED_D3_VERIFIED_DOCS_READY_FOR_REVIEW`**.
