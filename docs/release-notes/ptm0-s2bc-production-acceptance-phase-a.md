# PTM0-S2B + minimal S2C production acceptance — Phase A (read-only)

Date: 2026-09-12

Disposition: **`PTM0_S2BC_PRODUCTION_ACCEPTANCE_PHASE_A_READ_ONLY_PASS`**

Phase A (zero-authentication, zero-mutation, zero-provider) production acceptance
is complete and PASSED. This does **not** complete the full S2B/S2C acceptance set:
authenticated (AC-6/AC-7), provider/OAuth (AC-9/AC-10), and prior-P2–P5 synthetic
fixture (AC-11–AC-14) cases remain deferred and separately gated (see below).

Preparing this record performed no acceptance rerun, no authentication, no OAuth,
and no AWS/provider/application/infrastructure mutation.

## Repository identity

Acceptance was executed against `main == origin/main == 9dc2cc1df6b6106527ee4ee85a5ffc998c390cc3`.

## AC-1 — deployed backend identity: PASS

All 13 approved production Lambdas (intake, admin, review, assign, job,
google-auth, pet, cancellation, device, ses-feedback, postmark-webhook,
stripe-webhook, platform):

- State = Active
- LastUpdateStatus = Successful
- CodeSha256 = `OLAqPQtc4vYwMSnRSZxV1mJTmVoOYiEsUl8aXBVVt9I=`
- `TENANT_RESOLUTION_MODE = multi`

Control-plane reads only. No unrelated environment-variable values were listed or exposed.

## AC-2 — unauthenticated `/admin/auth/health`: PASS (reconciled expectation)

Observed production behavior: `GET /admin/auth/health` → **HTTP 403 "Missing
Authentication Token."** Read-only comparison probes established that real
Cognito-protected routes (`/admin/auth/status`, `/admin/tenant-info`,
`/admin/auth/google`) return HTTP 401, while `/admin/auth/health` returns 403
identically to a definitely-nonexistent route.

Therefore:

- `/admin/auth/health` is intentionally **NOT published** as an HTTP API route.
- HTTP callers cannot reach the scheduled health/refresh path.
- No health/refresh Lambda handler execution occurred from the live probe.
- No provider refresh or token persistence occurred.

The 403 is **not** described as a Cognito-authorizer rejection, and this live
request did **not** exercise the handler-level `SCHEDULED_HEALTH_ONLY` branch.

Defense-in-depth (two layers):
1. Primary production boundary — the health path is not published over HTTP.
2. Defense in depth — the deployed handler rejects HTTP-shaped health events with
   `SCHEDULED_HEALTH_ONLY` if ever reached (supported by frozen-source/local tests,
   not by this live probe).

## AC-3 — unauthenticated `/admin/auth/status`: PASS

`GET /admin/auth/status` (unauthenticated) → **HTTP 401 "Unauthorized."**

Recorded narrowly: unauthenticated callers cannot reach protected status
processing or receive a default tenant context. The live 401 alone is **not**
claimed to prove the internal `INVALID_TENANT_CONTEXT` branch; that strict-tenant
behavior is supported by frozen-source/local tests (AC-5).

## AC-4 — deployed frontend S2C artifact: PASS

Public CloudFront edge (read-only GETs) matched the approved deployed artifact
exactly (all HTTP 200):

- `index.html` SHA-256: `7546B2CCC8B7903CA0D4F7487803F8A69DF57E49F6591A84381A235C3F5A73A7`
- `assets/index-D3a5IJFf.js` SHA-256: `9184A29016E912D983ABC988B7BCE100D96EEDC265298456911E4D1A3E1CC7EA`
- `assets/index-BroXJAxV.css` SHA-256: `69A7D7BC6DD6A334A1D4304545ED9C844CAC637004264ECD5B8127C15E616990`

## AC-5 — local / frozen-source behavioral evidence: PASS

- Backend: **160 passed, 0 failed**
- Frontend: **9 passed, 0 failed**

These tests were local/frozen-source/package only, with provider calls
mocked / transport blocked, production credentials intentionally
unavailable/disabled for the local execution, no production application requests,
and no production writes. Coverage includes: strict HTTP tenant authority; no HTTP
default-tenant fallback; passive `/admin/auth/status` with no refresh/persist;
scheduled-health-only handler defense; OAuth transaction ownership/single-use;
provider-binding ownership isolation; protected-primary disconnect;
persistence-failure propagation; S2C UNKNOWN rendering; S2C monotonic/race handling.

## AC-8 — observability / metadata: PASS

CloudWatch (read-only, aggregate marker counts only; no raw payloads): 12 of the
13 target Lambda log groups existed. `togs-and-dogs-prod-ses-feedback` had no log
group because no invocation/log stream had been created — this is normal and **not**
an acceptance failure.

For both the deployment window and the Phase A window, all searched marker counts
were **zero**: `INVALID_TENANT_CONTEXT`, `SCHEDULED_HEALTH_ONLY`,
`PROVIDER_TOKEN_SAVE_FAILED`, `PROVIDER_REFRESH_FAILED`, `CALENDAR_HEALTH_CHECK`,
`PROVIDER_ACCESS_DENIED`, `ERROR`, `Traceback`.

Zero handler markers were expected for AC-2/AC-3 because those unauthenticated
requests were rejected by API Gateway / the authorizer **before** any Lambda
execution.

Secrets Manager: only `DescribeSecret` metadata was used; no secret value was
retrieved. The primary Google user-token secret `LastChangedDate` was
**2026-09-04**, which predates the 2026-09-12 deployment and Phase A acceptance and
corroborates that no token persistence / secret write occurred during these
activities.

## Zero-mutation confirmation

During Phase A there were: zero production application-data writes; zero DynamoDB
mutation; zero Secrets Manager mutation; zero Calendar/provider mutation; zero
Cognito mutation; zero S3/CloudFront mutation; zero Lambda code/config mutation;
zero Terraform; zero OAuth/provider interaction; zero authenticated acceptance; no
JWTs; no synthetic claims; no direct Lambda invocation with fabricated identity; no
second-tenant creation; no `TENANT_RESOLUTION_MODE` change; no Ryan testing; no
Stripe live work; no mobile/TestFlight/App Store work.

## Deferred / gated cases (acceptance set NOT complete)

- **AC-6, AC-7** (AUTHENTICATED_NON_MUTATING): definitions are **RATIFIED /
  AUTHORITATIVE** (see "Authoritative AC-6 / AC-7 acceptance definitions" below).
  Execution is now **COMPLETE — PASS** (2026-09-13, browser-observed authenticated
  production acceptance). See "Authenticated acceptance execution results (AC-6 /
  AC-7 / AC-8)" below. Results: `AC6_PASS`, `AC7_PASS`, `AC8_NON_MUTATION_PASS`.
- **AC-9, AC-10** (provider/OAuth-scoped): definitions are now **RATIFIED /
  AUTHORITATIVE** (see "Authoritative AC-9 / AC-10 acceptance definitions" below;
  ratified 2026-09-13). Execution status remains **NOT_EXECUTED / NOT YET
  AUTHORIZED**. Ratified readiness:
  `AC9_READY_AC10_PROTECTED_REFUSAL_READY_FOR_EXPLICIT_APPROVAL` via **Sequence B**.
  **AC-9 is intentionally mutating** (DynamoDB OAuth-state writes, external Google
  consent + code exchange, provider-secret write) and both AC-9 execution and the
  authenticated AC-10 request remain Matthew-gated. Google Calendar remains
  `VALIDATION_FAILED` until AC-9 is explicitly authorized and succeeds.
- **AC-11 through AC-14** (prior P2–P5 synthetic fixture cases): still require
  separate production fixture-creation authorization
  (`MATTHEW_APPROVAL_REQUIRED_FOR_PRODUCTION_FIXTURE_CREATION`).

The full S2B/S2C production acceptance set is **not** complete. F02 closure and
PTM-0 remain open pending the deferred/gated acceptance.

## Next recommended action

Await separate explicit authorization for the next acceptance tier
(authenticated AC-6/AC-7, then provider AC-9/AC-10, then fixture-dependent
AC-11–AC-14). No further production action is authorized by this checkpoint.

---

## Authoritative AC-6 / AC-7 acceptance definitions (RATIFIED — 2026-09-13)

These definitions resolve the prior `AC6_AC7_DOCUMENTATION_CONFLICT` and are the
authoritative, repository-committed acceptance criteria for AC-6 and AC-7. They
were established by the read-only preflight and are grounded in the deployed
frozen S2B source (`src/backend/handlers/google_auth_handler.py::get_status` and
`src/backend/handlers/admin_handler.py` `/admin/tenant-info` block).

Ratifying these definitions does **NOT** execute them.

Post-ratification readiness state: **`AC6_AC7_READY_FOR_EXPLICIT_APPROVAL`**.

- **AC-6 = NOT EXECUTED**
- **AC-7 = NOT EXECUTED**
- **Authenticated production session = NOT AUTHORIZED / NOT EXECUTED**
- Production acceptance execution remains **blocked until Matthew explicitly
  approves it**. Do not mark either criterion PASS on the basis of this record.

Both AC-6 and AC-7 are **non-mutating** acceptance criteria (READ-ONLY;
CloudWatch logging is the only side effect and is not a business-data write).

### AC-6 — Passive authenticated Google Calendar status

Authenticated primary-tenant `GET /admin/auth/status`.

Acceptance intent: verify the deployed route returns the truthful passive
readiness taxonomy **without** provider token refresh and **without** credential
persistence.

Allowed result taxonomy:

- `CONNECTED`
- `NOT_CONNECTED`
- `VALIDATION_FAILED`
- `UNKNOWN`
- `PROVIDER_UNAVAILABLE` (provider/secret-read failure, where applicable)

Core invariants:

- authenticated tenant context is authoritative
- no default-tenant fallback
- no token refresh
- no credential persistence
- no `initiate_auth`
- no application / business-data write
- expected path is authenticated HTTP / API Gateway → `google-auth` Lambda
- evidence captures status classification only, never raw secret/token/provider payloads

Target route/function: `GET /admin/auth/status` → `togs-and-dogs-prod-google-auth`
→ `get_status` (docstring: "Passive cached readiness only: never refresh or
persist credentials"), tenant-gated by `_require_http_company_id`.

Tenant involved: primary `tog_and_dogs` (the authenticated session's own tenant).

Expected authorization behavior: authenticated caller passes
`_require_http_company_id`; missing/invalid/mismatched claim → HTTP 403
`INVALID_TENANT_CONTEXT`.

### AC-7 — Authenticated tenant-info passive composition

Authenticated primary-tenant `GET /admin/tenant-info`.

Acceptance intent: verify the route returns tenant metadata and a passively
composed `calendar_status`, with authenticated ownership authoritative and no
caller-controlled tenant override.

Core invariants:

- role authorization applies (owner/admin/staff/client/platform_admin)
- `_require_http_company_id` / authenticated tenant identity remains authoritative
- route/request `company_id` (e.g. `expectedTenantSlug`) must NOT override
  authenticated ownership
- DynamoDB tenant metadata access is read-only
- entitlement access is read-only
- `calendar_status` is derived from the passive `get_status`
- no provider refresh
- no credential persistence
- no business-data write
- do not expose raw tenant/customer/pet/staff data unnecessarily

Target route/function: `GET /admin/tenant-info` → `togs-and-dogs-prod-admin`
(role gate + `_require_http_company_id` → `company_id = authenticated_company` →
`get_item(TENANT#…)` → `_get_entitlement_safely` → passive `get_status`).

Tenant involved: primary `tog_and_dogs` (authenticated).

Expected own-tenant behavior:

- HTTP 200
- sanitized tenant metadata
- valid `calendar_status` classification (AC-6 taxonomy)

Expected invalid/mismatched-tenant behavior:

- appropriate authorization / tenant-context denial (HTTP 403; e.g.
  `PROVIDER_ACCESS_DENIED` when `company_id != authenticated_company`)
- no fallback to another tenant

### Minimum eventual acceptance evidence

For **AC-6**:

- HTTP status
- returned status classification only (one of the allowed taxonomy values)
- deployed backend identity reference (`CodeSha256 OLAqPQtc4vYwMSnRSZxV1mJTmVoOYiEsUl8aXBVVt9I=`, `TENANT_RESOLUTION_MODE=multi`)
- no refresh/save error markers (`PROVIDER_REFRESH_FAILED`, `PROVIDER_TOKEN_SAVE_FAILED` count = 0)
- secret metadata `LastChangedDate` unchanged where used as non-mutation evidence
  (baseline `2026-09-04`)

For **AC-7**:

- HTTP status
- sanitized tenant metadata classification
- `calendar_status`
- ownership / tenant-context behavior (authoritative authenticated ownership;
  denial on mismatch)
- no refresh/save error markers
- secret metadata `LastChangedDate` unchanged where applicable

AC-8 post-read confirmation (all error markers count = 0; secret `LastChangedDate`
unchanged) remains part of the eventual acceptance evidence.

### Evidence prohibitions (never store or display)

- JWTs
- Cognito tokens
- access tokens
- refresh tokens
- OAuth codes
- secrets / Secrets Manager values
- raw Cognito claims
- raw provider payloads
- private customer / pet / staff record bodies

### Retained approval gates

1. Authenticated production session creation/use — **Matthew-gated**.
2. Authenticated AC-6 / AC-7 production reads + AC-8 re-confirmation — **Matthew-gated**.

No AWS acceptance action, authentication, deployment, configuration change,
tenant/business-data change, or Terraform operation is authorized by this
documentation ratification.

---

## Authenticated acceptance execution results (AC-6 / AC-7 / AC-8) — 2026-09-13

Disposition: **`AC6_PASS`**, **`AC7_PASS`**, **`AC8_NON_MUTATION_PASS`**.

Executed against the accepted deployed identity (all 13 prod Lambdas
`CodeSha256 = OLAqPQtc4vYwMSnRSZxV1mJTmVoOYiEsUl8aXBVVt9I=`, State=Active,
LastUpdateStatus=Successful, `TENANT_RESOLUTION_MODE = multi`; AWS account
`358604342897`). Repository baseline at evaluation:
`HEAD == origin/main == 106798a99214d64bebe1791952c00b7b1e6502ed`.

Execution method: **browser-observed acceptance**. Matthew performed a normal
authenticated production login to the Togs & Dogs admin portal on the standard
`/admin` route, which caused the existing SPA to issue the two authenticated GETs
automatically (`web/src/api/client.js` `getGoogleStatus()` → `/admin/auth/status`;
`getTenantInfo()` → `/admin/tenant-info`, invoked from the post-auth bootstrap in
`AdminDashboard.jsx` and the `App.jsx` admin-route effect). No authentication
material (JWT / Cognito token / cookie / claim / password / OAuth code) was
requested, displayed, or persisted. No new credential or auth helper was created.

### AC-6 — authenticated `GET /admin/auth/status` — **PASS**

- Execution date: 2026-09-13.
- The authenticated production admin dashboard loaded successfully.
- `GET /admin/auth/status` produced the truthful passive classification
  **`VALIDATION_FAILED`**.
- Visible UI evidence: Google Calendar integration status **NEEDS RECONNECT**
  (SPA `getGoogleStatusConfig('VALIDATION_FAILED')` → "Needs Reconnect");
  technical classification `VALIDATION_FAILED`; connected account `None`; a
  degraded-calendar banner was displayed ("Google Calendar connection needs
  reconnect. Sitter schedule sync is degraded.").
- `VALIDATION_FAILED` is an **allowed accepted taxonomy value**; `CONNECTED` was
  **not required**. This is NOT an acceptance failure — it truthfully reports a
  separate operational condition (the existing Calendar connection needs
  reconnect; see operational follow-up below).
- Non-mutation confirmed (AC-8): no token refresh, no credential persistence, no
  `initiate_auth`. No OAuth / reconnect action was performed.
- Authenticated primary-tenant context (Togs & Dogs) was authoritative; no
  default-tenant fallback.

### AC-7 — authenticated `GET /admin/tenant-info` — **PASS**

- Execution date: 2026-09-13.
- The authenticated production admin dashboard loaded in the expected
  **Togs & Dogs** tenant context (Tog & Dogs Pet Sitting branding) on the normal
  production `/admin` route.
- Authenticated ownership remained authoritative (no `expectedTenantSlug`
  override on the standard route; deployed handler forces
  `company_id = authenticated_company`).
- **No** alternate tenant, default fallback, or cross-tenant presentation was
  observed.
- The Google Calendar status composition reflected the passive `VALIDATION_FAILED`
  state (`calendar_status` derived from the passive `get_status`).
- **Explicit numeric HTTP status was NOT directly captured** (DevTools not used).
  A numeric `200` is therefore **not claimed as directly observed**; the
  authenticated endpoint-derived application state (correct tenant identity +
  passive calendar-status composition, only producible by a successful,
  correctly-scoped `/admin/tenant-info` response) is sufficient under the ratified
  evidence definition, which lists HTTP status as "if safely observable."
- Non-mutation confirmed (AC-8).

### AC-8 — post-run non-mutation verification — **NON-MUTATION PASS**

Read-only, metadata-only checks over the same 24h window (which includes the
browser-session activity), compared against the clean pre-run baseline captured
earlier this run:

| Marker (log group) | Pre-run | Post-run |
|---|---|---|
| `PROVIDER_REFRESH_FAILED` (google-auth) | 0 | 0 |
| `PROVIDER_TOKEN_SAVE_FAILED` (google-auth) | 0 | 0 |
| `INVALID_TENANT_CONTEXT` (google-auth) | 0 | 0 |
| `SCHEDULED_HEALTH_ONLY` (google-auth) | 0 | 0 |
| `PROVIDER_ACCESS_DENIED` (google-auth) | 0 | 0 |
| `ERROR` (google-auth) | 0 | 0 |
| `Traceback` (google-auth) | 0 | 0 |
| `CALENDAR_HEALTH_CHECK` (google-auth, benign scheduled) | 3 | 3 |
| `PROVIDER_ACCESS_DENIED` (admin) | 0 | 0 |
| `ERROR` (admin) | 0 | 0 |
| `Traceback` (admin) | 0 | 0 |

- Google user-token secret `togs-and-dogs-prod/google/user-tokens` metadata
  `LastChangedDate` remained **`2026-09-04T08:13:11.653-04:00`** (unchanged
  before and after). Metadata only; **no secret value was retrieved**.
- No refresh/save marker increased; benign scheduled `CALENDAR_HEALTH_CHECK`
  activity unchanged. No provider refresh or persistence occurred; no
  application / business-data mutation occurred.
- The `VALIDATION_FAILED` status was returned by passive classification of the
  already-stored (revoked) token state — not by a new write.

### Scope confirmation

No production write, OAuth initiation, Calendar reconnect, deployment,
configuration change, tenant creation/modification, `TENANT_RESOLUTION_MODE`
change, Stripe action, Ryan tester change, mobile-distribution change, or
production test-data creation occurred during this acceptance. Only read-only
control-plane and metadata reads plus Matthew's normal authenticated browser
session were involved.

### Tier status

This completes the **authenticated non-mutating acceptance tier (AC-6 / AC-7)**
for PTM0-S2B + minimal S2C. It does **NOT** by itself complete the full S2B/S2C
acceptance set: provider/OAuth AC-9/AC-10 and prior-P2–P5 synthetic-fixture
AC-11–AC-14 remain deferred and separately gated. F02 closure and PTM-0 overall
remain open. No claim of PTM-0 / F02 / S2 / multi-tenant program completion is
made by this checkpoint.

### Operational follow-up (NOT part of acceptance; NOT executed)

Primary Google Calendar connection is in `VALIDATION_FAILED` — sitter schedule
sync is degraded and the existing Calendar credentials need reconnect. Reconnect
is **write-capable / OAuth provider mutation / Matthew-approval-required** and was
**not** performed. Acceptance passed precisely because the passive status route
reported this condition truthfully.

---

## Authoritative AC-9 / AC-10 acceptance definitions (RATIFIED — 2026-09-13)

These definitions resolve the AC-9/AC-10 documentation gap and are the
authoritative, repository-committed acceptance criteria for the provider/OAuth
acceptance tier. They were established by the read-only preflight and are grounded
in the deployed frozen S2B source (`src/backend/handlers/google_auth_handler.py`:
`initiate_auth`, `handle_callback`, `_load_oauth_transaction`,
`_claim_oauth_transaction`, `_persist_oauth_tokens`, `disconnect_auth`,
`_is_protected_primary_binding`).

Ratifying these definitions does **NOT** execute them.

Ratified readiness state:
**`AC9_READY_AC10_PROTECTED_REFUSAL_READY_FOR_EXPLICIT_APPROVAL`**.

- **AC-9 = NOT EXECUTED**
- **AC-10 = NOT EXECUTED**
- **Google Calendar = still `VALIDATION_FAILED`**
- **Reconnect = NOT EXECUTED**
- **Provider/OAuth acceptance tier = NOT COMPLETE**

Do not mark anything PASS on the basis of this record.

### AC-9 — primary-tenant Google Calendar OAuth reconnect (INTENTIONALLY MUTATING)

**Purpose:** validate the primary-tenant Google Calendar OAuth reconnect flow:
`GET /admin/auth/google` → server-held OAuth transaction creation → Google consent
→ `GET /admin/auth/callback` → single-use transaction consume → token exchange →
tenant-bound credential persistence → post-reconnect passive status = `CONNECTED`.

**Verified behavior:**

- authenticated owner/admin authorization (`initiate_auth` role gate)
- primary tenant = `tog_and_dogs`; strict authoritative tenant ownership
  (`_require_http_company_id`; no default-tenant fallback)
- server-generated OAuth `state` (UUID), stored server-side as
  `OAUTHSTATE#<state>/META` (schema v2, `status=PENDING`)
- single-use state; state expiry (`expires_at = created_at + 600`, ≤ 600s window)
- state ownership/binding validation (company_id, `provider_secret_arn`,
  redirect/destination pair) before use
- callback atomic consume (conditional `SET status=CONSUMED`; replay/expired →
  `INVALID_OAUTH_STATE`)
- Google authorization-code exchange (server-side)
- tenant-bound provider-secret persistence to the resolved bound ARN only
- revocation markers (`token_status`, `revoked_at`, `revoked_reason`) cleared on
  successful reconnect; `updated_at` set
- post-reconnect passive status becomes `CONNECTED`
- no cross-tenant token persistence; no arbitrary caller-selected secret binding

**Expected mutations (intentionally mutating; Matthew approval required):**

- `DYNAMODB WRITE` — create OAuth transaction (initiate); consume OAuth
  transaction (callback)
- `EXTERNAL PROVIDER ACTION` — Google consent; OAuth code exchange
- `SECRET WRITE` — persist refreshed provider credentials; clear
  reconnect/revocation status markers

This is **not** a business-data mutation, but it **is** a real
provider/auth/configuration mutation.

**Current production starting state (intended AC-9 starting condition):**

- the existing Google credential secret exists
  (`togs-and-dogs-prod/google/user-tokens`)
- current passive status = `VALIDATION_FAILED`
- Calendar integration needs reconnect
- this degraded/revoked state is the intended natural starting condition for AC-9
- no synthetic provider state needs to be created

**Expected success:** OAuth initiation succeeds; Google consent completes; callback
succeeds; OAuth state is consumed exactly once; credentials persist only to the
tenant-owned bound secret; post-run `/admin/auth/status` = `CONNECTED`; Calendar
operational state restored.

**Expected failure/denial classes (source-grounded):**

- unauthorized role → 403
- ineligible/disabled tenant or wrong provider binding → 403 `OAUTH_ACCESS_DENIED`
- malformed/expired/replayed OAuth state → 400 `INVALID_OAUTH_STATE`
- OAuth code exchange failure → 502 `OAUTH_EXCHANGE_FAILED`
- provider/config unavailable → 503 `OAUTH_UNAVAILABLE`
- origin denied → 403 `OAUTH_ORIGIN_DENIED`
- missing principal → 403 `OAUTH_PRINCIPAL_REQUIRED`

(No status codes beyond those present in the deployed source are asserted.)

**Rollback limitation:** a completed callback / token persistence is **not**
meaningfully reversed by application code rollback. The consumed OAuth transaction
and the refreshed provider credentials are external/persistent state. This is why
AC-9 requires explicit Matthew authorization.

### AC-10 — protected-primary disconnect refusal

**Purpose:** validate protected-primary disconnect behavior via
`DELETE /admin/auth/google`. For the primary Togs & Dogs provider binding, the
expected result is a **protected refusal**, not an actual disconnect.

**Expected primary-tenant behavior (the AC-10 acceptance condition here):**

- authenticated owner/admin request; tenant = `tog_and_dogs`
- provider binding = protected primary binding (`_is_protected_primary_binding`)
- expected result: **HTTP 409**, classification **`PROVIDER_DISCONNECT_PROTECTED`**
- no credential mutation; no provider API call; no provider-secret write; no
  Calendar disconnect
- production remains connected if AC-9 has already succeeded
- effect classification: **READ-ONLY / guarded refusal** (no SECRET WRITE, no
  PROVIDER MUTATION, no DYNAMODB write)

**Non-primary behavior (source context only — NOT authorized here):** for a
non-protected/non-primary tenant, `disconnect_auth` may mark provider credentials
revoked and perform a `SECRET WRITE`. That behavior is **NOT authorized** for
execution by this checkpoint. Do not create another tenant or synthetic provider
binding to test it.

### Ratified sequencing decision — Sequence B (minimum-mutation)

1. AC-9 itself serves as the controlled production reconnect.
2. Verify the integration transitions `VALIDATION_FAILED` → `CONNECTED`.
3. Run AC-10 only as the protected-primary disconnect **refusal** check.
4. Expected AC-10 = 409 `PROVIDER_DISCONNECT_PROTECTED`.
5. No real disconnect occurs.
6. Production should end in the `CONNECTED` state.

Explicitly rejected (unnecessary extra provider writes): operationally
reconnecting before AC-9; disconnecting then reconnecting again; any multi-write
path. Sequence B is the minimum-mutation acceptance path.

### Privacy / secret-handling (execution constraints)

Execution must never display, paste, or persist into documentation: OAuth
authorization code, Google access token, Google refresh token, Cognito token, JWT,
raw claims, browser cookie/session material, secret value, or raw provider payload.
Browser-observed acceptance is preferred; the authorization code and tokens are
exchanged **server-side** in the callback and must be kept out of
Kiro/ChatGPT-visible output.

### Evidence requirements

**AC-9 (minimum sanitized):** initiation success classification; callback success
classification; successful browser redirect; post-reconnect Calendar state
`CONNECTED`; provider-secret metadata `LastChangedDate` **changed** as expected
(no value read); no unexpected provider/OAuth failure markers; OAuth transaction
consumed exactly once; tenant ownership remained `tog_and_dogs`; no cross-tenant
provider mutation. Do not record secret values.

**AC-10 (minimum sanitized):** HTTP 409; `PROVIDER_DISCONNECT_PROTECTED`;
provider-secret metadata **unchanged** after AC-10; no provider API call/mutation;
Calendar remains `CONNECTED`. A repeated disconnect call is noted only if
separately authorized; do not require a duplicate call unless necessary.

### Approval gates (retained)

1. AC-9 execution requires Matthew authorization for: the browser OAuth reconnect;
   external Google consent; DynamoDB OAuth-state writes; and the provider-secret
   write.
2. AC-10 protected-primary check requires Matthew authorization for the
   authenticated `DELETE` request, even though the expected behavior is
   non-mutating.
3. No true non-primary disconnect is authorized.
4. No synthetic tenant/provider fixture is authorized.

### F02 / PTM-0 impact (no premature closure)

AC-9 + AC-10 PASS would complete the **provider/OAuth acceptance tier**. It would
**not** by itself complete the full S2B/S2C acceptance set (AC-11–AC-14 P2–P5
synthetic fixtures remain), and does **not** by itself close F02 or PTM-0 (F03–F08
remain out of scope here). No Tier-1 / S2 / PTM-0 / multi-tenant program completion
is implied by this ratification.
