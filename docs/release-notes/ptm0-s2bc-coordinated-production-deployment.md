# PTM0-S2B + minimal S2C coordinated production deployment

Date: 2026-09-12

Disposition: **`PTM0_S2BC_COORDINATED_PRODUCTION_DEPLOYMENT_COMPLETE_ACCEPTANCE_NOT_STARTED`**

DEPLOYED — ARTIFACT IDENTITY VERIFIED — **PRODUCTION ACCEPTANCE NOT STARTED / NOT AUTHORIZED**.

The approved coordinated deployment executed in the mandatory order (frontend S2C
first, verified, then backend S2B), with a hard stop before any acceptance testing.
No production acceptance, application/runtime, infrastructure, provider, or data
change occurred beyond the exact authorized artifact publication and 13-Lambda
code-only update.

---

## Repository / source identities

- Pre-deployment repository checkpoint (unchanged by the deployment):
  `cc55e21850adbd8fa0735424e8fc748185904172`
- Backend frozen source: `414312a1caf91b03dcce7bc093d3c0ae579c9888`
- Backend tree: `86602e6084748f49f3439a7498722bc218d9d7c7`
- Frontend frozen source: `709f7cf1e55bba4b3b176c10fc83861f9917559e`
- Frontend tree: `841f26625703da8efba45b962b183d91ebc3651f`

Isolated release branches `release/ptm0-s2bc-backend-reconcile` and
`release/ptm0-s2bc-web-reconcile` remain unpushed. `main` was not modified by the
deployment.

## Backend artifact (S2B)

- Backend ZIP SHA-256: `38B02A3D0B5CE2F6303129D1499C55D66253995A0E62212C525F1A5C1555B7D2`
- Expected and observed Lambda CodeSha256: `OLAqPQtc4vYwMSnRSZxV1mJTmVoOYiEsUl8aXBVVt9I=`
- Previous S2 RC1 CodeSha256 (pre-deployment baseline): `CElAcSjErchfDbW2pL63iijo8J6qYAtK0QxxZ9pCGVQ=`
- S2 RC1 rollback ZIP SHA-256: `0849407128C4ADC85F0DB5B6A4BEB78A28E8F09EAA600B4AD10C7167DA421954`

The exact retained approved S2B ZIP bytes were uploaded via boto3
`update_function_code` (`Publish=False`, per-function `RevisionId` optimistic lock).
The ZIP was **not rebuilt** and Terraform was **not** used to construct or deploy
the package. The observed Lambda `CodeSha256` equals `Base64(SHA256(exact approved
ZIP bytes))`.

## Frontend artifact (minimal S2C)

- Frontend build-manifest SHA-256: `2EF7F45902FF9DE2F865B3AF6EB217EFF42D9F25573B5E3F4887D181934CEBE6`
- Deployed `index.html` SHA-256: `7546B2CCC8B7903CA0D4F7487803F8A69DF57E49F6591A84381A235C3F5A73A7`
- Primary JS `assets/index-D3a5IJFf.js` SHA-256: `9184A29016E912D983ABC988B7BCE100D96EEDC265298456911E4D1A3E1CC7EA`
- Retained CSS `assets/index-BroXJAxV.css` SHA-256: `69A7D7BC6DD6A334A1D4304545ED9C844CAC637004264ECD5B8127C15E616990` (byte-identical to the deployed baseline)
- Retired prior JS asset (removed by this deployment): `assets/index-CdPio7XK.js`

## Frontend production verification

- S3 bucket: `togs-and-dogs-prod-toganddogs-hosting`
- S3 sync dry-run matched the approved publication scope exactly (11 uploads of the
  approved dist objects + 1 deletion of the retired `assets/index-CdPio7XK.js`; no
  unexpected keys).
- Actual S3 publication completed (`aws s3 sync ... --delete`).
- Resulting bucket inventory was exactly the 11 approved objects — zero missing,
  zero unexpected, zero hash mismatches — and the retired
  `assets/index-CdPio7XK.js` object was absent.
- CloudFront distribution: `E35L00QPA2IRCY`
- Invalidation: `I73981UKKDWC4PGQI6KMA4Y83V`, path `/*`, result **Completed**.
- Post-invalidation edge verification (via CloudFront domain
  `d2nr4rfm2afckd.cloudfront.net`, alias `toganddogs.usmissionhero.com`, distribution
  `Deployed`): `index.html`, `assets/index-D3a5IJFf.js`, and `assets/index-BroXJAxV.css`
  each served HTTP 200 with the exact approved bytes/hashes above.

### SPA fallback note (retired JS path)

Requesting the retired path `assets/index-CdPio7XK.js` through CloudFront returned
HTTP 200 because the distribution's existing SPA 403/404 custom-error behavior
returns `index.html`. This response was proven **not** to be the retired JavaScript
asset:

- served body size matched `index.html` (1,472 bytes);
- content type was `text/html`;
- served SHA-256 equalled the approved deployed `index.html`
  (`7546B2CCC8B7903CA0D4F7487803F8A69DF57E49F6591A84381A235C3F5A73A7`);
- S3 inventory independently proved the retired JS object was absent;
- CloudFront reported `X-Cache: Error from cloudfront` for the fallback.

The retired JS asset is **not** deployed.

## Backend production verification

All 13 approved production Lambdas were updated code-only and verified:

| Function | State | LastUpdateStatus | CodeSha256 |
|---|---|---|---|
| togs-and-dogs-prod-intake | Active | Successful | `OLAqPQtc4vYwMSnRSZxV1mJTmVoOYiEsUl8aXBVVt9I=` |
| togs-and-dogs-prod-admin | Active | Successful | `OLAqPQtc4vYwMSnRSZxV1mJTmVoOYiEsUl8aXBVVt9I=` |
| togs-and-dogs-prod-review | Active | Successful | `OLAqPQtc4vYwMSnRSZxV1mJTmVoOYiEsUl8aXBVVt9I=` |
| togs-and-dogs-prod-assign | Active | Successful | `OLAqPQtc4vYwMSnRSZxV1mJTmVoOYiEsUl8aXBVVt9I=` |
| togs-and-dogs-prod-job | Active | Successful | `OLAqPQtc4vYwMSnRSZxV1mJTmVoOYiEsUl8aXBVVt9I=` |
| togs-and-dogs-prod-google-auth | Active | Successful | `OLAqPQtc4vYwMSnRSZxV1mJTmVoOYiEsUl8aXBVVt9I=` |
| togs-and-dogs-prod-pet | Active | Successful | `OLAqPQtc4vYwMSnRSZxV1mJTmVoOYiEsUl8aXBVVt9I=` |
| togs-and-dogs-prod-cancellation | Active | Successful | `OLAqPQtc4vYwMSnRSZxV1mJTmVoOYiEsUl8aXBVVt9I=` |
| togs-and-dogs-prod-device | Active | Successful | `OLAqPQtc4vYwMSnRSZxV1mJTmVoOYiEsUl8aXBVVt9I=` |
| togs-and-dogs-prod-ses-feedback | Active | Successful | `OLAqPQtc4vYwMSnRSZxV1mJTmVoOYiEsUl8aXBVVt9I=` |
| togs-and-dogs-prod-postmark-webhook | Active | Successful | `OLAqPQtc4vYwMSnRSZxV1mJTmVoOYiEsUl8aXBVVt9I=` |
| togs-and-dogs-prod-stripe-webhook | Active | Successful | `OLAqPQtc4vYwMSnRSZxV1mJTmVoOYiEsUl8aXBVVt9I=` |
| togs-and-dogs-prod-platform | Active | Successful | `OLAqPQtc4vYwMSnRSZxV1mJTmVoOYiEsUl8aXBVVt9I=` |

- `Publish=False`; no numbered Lambda version was published.
- `togs-and-dogs-prod-platform-preview` was **not** changed.
- `togs-and-dogs-prod-cognito-email-sender` was **not** changed.
- Account `358604342897`, region `us-east-1`, profile `usmissionhero-website-prod`.

## TENANT_RESOLUTION_MODE

`TENANT_RESOLUTION_MODE=multi` was already the production value before this
deployment and remained unchanged on all 13 functions. This deployment did **not**
enable or change multi mode.

## Configuration verification note

The first updated Lambda (`togs-and-dogs-prod-intake`) initially triggered a
verification false-positive: the original configuration fingerprint included the
AWS-managed `RuntimeVersionConfig`, whose runtime-patch pointer AWS
re-resolved/normalized during the code update. This was investigated before
proceeding, and it was confirmed that **no operator-controlled configuration change
occurred**.

Final post-deployment verification compared the operator-controlled configuration
fields — Handler, Role, Runtime, MemorySize, Timeout, Architectures,
EphemeralStorage, Environment, TracingConfig, SnapStart, LoggingConfig, Layers,
VPC configuration, DLQ, File systems, KMS, PackageType, Description — and confirmed
they **remained unchanged** on all 13 functions. (This does **not** claim
`RuntimeVersionConfig` itself was unchanged; that AWS-managed field is expected to
re-resolve on a code update.)

## Scope / hard stop

Production acceptance was **NOT started**. None of the following occurred as part of
this deployment: authenticated production acceptance; manual functional acceptance;
OAuth/provider acceptance; Calendar mutation; synthetic application requests;
production application-data writes; second-tenant creation; `TENANT_RESOLUTION_MODE`
change; Ryan testing; Stripe live work; mobile/TestFlight/App Store work; Terraform
apply; IAM change; API Gateway change; Secrets Manager change; DynamoDB change;
Cognito change; Route 53 change.

## Status after this deployment

- S2B backend: DEPLOYED (all 13 Lambdas on `OLAqPQtc4vYwMSnRSZxV1mJTmVoOYiEsUl8aXBVVt9I=`).
- Minimal S2C frontend: DEPLOYED and edge-verified.
- Production acceptance: **NOT STARTED / NOT AUTHORIZED** (separate gate).
- F02: source/artifact remediation is now deployed, but F02 closure still depends on
  the separately authorized production acceptance; treat F02 as not closed until that
  gate completes.
- PTM-0: remains incomplete.

Rollback reference remains the S2 RC1 backend package
(`0849407128C4ADC85F0DB5B6A4BEB78A28E8F09EAA600B4AD10C7167DA421954`,
CodeSha256 `CElAcSjErchfDbW2pL63iijo8J6qYAtK0QxxZ9pCGVQ=`) and the prior web lineage
(`3025f2f1e3991f990d0d4adde79b910e955fd6d1` / `assets/index-CdPio7XK.js`). Backend
and frontend rollback boundaries remain separate; if backend rollback is ever
required while S2B is active, roll the backend first, then the frontend. Code
rollback does not reverse consumed OAuth transactions or provider-state writes.

## Next recommended action

Await separate explicit Matthew authorization for PTM0-S2BC production acceptance.
No further production action is authorized by this checkpoint.
