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

- **AC-6, AC-7** (AUTHENTICATED_NON_MUTATING): status **NOT_DETERMINED / NOT YET
  AUTHORIZED**. Authenticated-session availability was not investigated; no session
  material was accessed.
- **AC-9, AC-10** (provider/OAuth-scoped): **separate Matthew authorization
  required** (OAuth initiate/callback token persistence; provider disconnect).
- **AC-11 through AC-14** (prior P2–P5 synthetic fixture cases): still require
  separate production fixture-creation authorization
  (`MATTHEW_APPROVAL_REQUIRED_FOR_PRODUCTION_FIXTURE_CREATION`).

The full S2B/S2C production acceptance set is **not** complete. F02 closure and
PTM-0 remain open pending the deferred/gated acceptance.

## Next recommended action

Await separate explicit authorization for the next acceptance tier
(authenticated AC-6/AC-7, then provider AC-9/AC-10, then fixture-dependent
AC-11–AC-14). No further production action is authorized by this checkpoint.
