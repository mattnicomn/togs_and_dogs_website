# B1A Real Web/API Write-Path Validation Plan

**Date:** 2026-09-02

**Status:** READY FOR MATTHEW APPROVAL / NOT APPROVED / NOT EXECUTED

**Recommended scope:** Option A — one successful authenticated Profile Only
staff creation for `test_tenant_alpha`, followed by exact-key cleanup under the
same later explicit approval.

## Planning boundary

This is a documentation-only approval package. It authorizes no production
request, AWS operation, Terraform operation, browser action, deployment, or
data mutation.

- Platform/operator: USMissionHero LLC.
- Primary customer tenant: `tog_and_dogs` (Togs & Dogs).
- Internal validation tenant: `test_tenant_alpha` only.
- Strict `TENANT_RESOLUTION_MODE=multi` remains active and must not change.
- No `tog_and_dogs` customer or business workflow data may be used.
- Matthew authenticates privately. Passwords, tokens, cookies, Authorization
  headers, JWTs, and raw session data must not be inspected or recorded.
- No new tenant, Cognito user, notification, Calendar event, deployment, or
  infrastructure change is part of this plan.

The source review used `main` at
`43bd0c774e5945dd90ab30848d264632dcfaaa59`. That commit contains the deployed
P1 Decimal-safe entitlement implementation and its production acceptance
record. The documented live baseline remains 13 Lambdas on `CodeSha256`
`K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=`, REST API `a022yxuiue` at
`prod -> atxpw3`, and Terraform state serial `516`, lineage
`7235fddd-c101-fe62-7669-7b7b3d858955`. These production facts must be
reconfirmed read-only immediately before any later execution; they were not
queried during this planning task.

## Exact remaining question

Completed evidence already proves:

- the B1A intake, Meet & Greet, approval, asynchronous job creation, and
  assignment business logic through direct Lambda invocation;
- tenant isolation during that backend workflow;
- the real Web -> API Gateway -> Cognito authorizer -> Lambda -> strict tenant
  resolution path through read-only tenant bootstrap;
- exact cleanup of the prior eight-item synthetic run and restoration of Alpha
  to its one-item metadata baseline; and
- the P1 Decimal entitlement fix through one real authenticated
  `POST /admin/staff` that intentionally returned 403 before persistence.

What remains unproven is a successful real authenticated request crossing the
deployed Web/API boundary and committing an item under the tenant resolved
from the Cognito claim:

`tenant Web UI -> HTTP -> API Gateway -> Cognito authorizer -> admin Lambda ->`
`active tenant -> custom:company_id in strict multi mode -> max_staff ->`
`DynamoDB persistence -> HTTP success`.

The P1 guarded 403 did not prove persistence. Conversely, repeating every
Gate-B transition would mostly repeat backend logic that is already proven.
The remaining risk category can be closed by one carefully bounded successful
write, provided the result is labelled narrowly.

## Candidate scope comparison

| Option | Real path proved | Records/mutations | Side effects and risk | Cleanup | Duplication / disposition |
| --- | --- | --- | --- | --- | --- |
| **A. Successful staff creation only** | Authenticated tenant Web UI, Cognito API method, strict claim resolution, active-tenant and `max_staff` entitlement checks, admin Lambda, one DynamoDB persistence, HTTP 200 | Exactly 1 `STAFF` item; no counter | No notification, Calendar, Cognito, or async call exists in the Profile Only route | One generated exact key, marker-linked and conditionally deletable | Minimal representative cross-layer write proof; **recommended** |
| **B. Successful public/client intake only** | Public `/requests` proves domain-mapped public intake but not Cognito; `/client/requests` proves Cognito only with a suitable linked client identity and has different `VISIT_BOOKING` semantics | At least 1 `REQUEST`; monthly counter changes unless test mode; notification ledger count is runtime/config dependent | Step Functions starts asynchronously; public intake calls `REQUEST_RECEIVED`; later Calendar/workflow effects are possible | Multi-system observation and at least request/counter/notification cleanup | Does not cleanly prove the intended authenticated owner path; reject |
| **C. Staff plus intake** | Option A plus an intake route | Option A's 1 staff item plus Option B's request/counter/possible notification records | Adds async and notification exposure without being necessary for the narrow remaining gap | Multiple keys and possible counter/ledger reconciliation | Duplicates already-proven intake logic; reject |
| **D. Full prior B1A workflow** | Real routes for intake, M&G, approval, async job, and assignment, plus staff creation | At least 5 core items (`STAFF`, `REQUEST`, `CLIENT`, `PET`, `JOB`) plus notification ledgers; the prior test-mode run created 8 total synthetic items | Current source exposes `REQUEST_RECEIVED`, `CUSTOMER_APPROVED`, `STAFF_ASSIGNED`, and `VISIT_SCHEDULED` notification calls; approval/assignment attempt Calendar; job creation is async | Exact dependency-ordered cleanup across all generated keys and ledgers | Materially repeats Gate-B backend behavior and has the largest blast radius; reject for this gate |

Option B cannot be made equivalent to Option A merely by using the current
Alpha owner identity. Public `/requests` has `authorization = NONE`. On
`/client/requests`, a true linked client takes the client booking branch, while
an owner/admin identity takes a different `VISIT_BOOKING` branch. Alpha's
approved one-item baseline has no linked client or pet profile. Manufacturing
those prerequisites would expand the write scope before the target evidence
is obtained.

## Current production write contracts from source

### Option A: Profile Only staff

- HTTP/API: `POST /admin/staff`.
- API Gateway: `COGNITO_USER_POOLS`, the configured Cognito authorizer, and
  `AWS_PROXY` integration using integration method `POST` to the admin Lambda
  (`modules/api/main.tf:748-788`).
- Web: the tenant admin UI calls `createStaff()`, which requests
  `/admin/staff` with the current ID token; Profile Only selects this route and
  does not call `/admin/staff/onboard`
  (`web/src/api/client.js:1-30,89-94` and
  `web/src/components/AdminDashboard.jsx:1450-1501`).
- Tenant route gate: `/t/test-tenant-alpha/admin` bootstrap first calls the
  authenticated tenant-info resolver with the expected slug. Operational data
  loading is enabled only after server response, route slug, and
  `custom:company_id` agree (`web/src/utils/tenantContext.js` and
  `AdminDashboard.jsx:1180-1228`). The later POST does not trust or send the
  route slug as tenant authority.
- Lambda: `src/backend/handlers/admin_handler.py`.
- Tenant resolution: the shared active-tenant boundary runs first. The route
  then derives `company_id` from the Cognito `custom:company_id` claim.
  `get_current_company_id()` raises on a missing claim in strict multi mode; it
  does not fall back to `tog_and_dogs` (`common/auth.py:247-285`).
- Authorization/entitlement: active eligible tenant; effective role must be
  `owner` or `admin`; `display_name` must be non-empty and not `Unassigned`;
  active duplicate names are rejected; `check_limit(company_id,
  'max_staff', active_staff_count, context=event)` must allow the write; any
  supplied protected email is rejected.
- Persistence: exactly one unconditional `items_table.put_item` after all
  validation. There is no application-level transaction or compensating
  rollback. A lost/ambiguous client response can therefore follow a committed
  item and must never trigger an automatic retry.
- Generated item:
  - `PK = COMPANY#test_tenant_alpha`
  - `SK = STAFF#staff_<8 UUID characters>`
  - `company_id = test_tenant_alpha`
  - `staff_id = staff_<8 UUID characters>`
  - exact synthetic marker in both `display_name` and `notes`
  - `role = Staff`
  - `email = null`, `cognito_sub = null`, `phone = null`
  - `is_active = true`, explicitly submitted `is_assignable = false`
  - benign existing assignment-color default and server timestamps
- Async: none.
- Notifications/Postmark: none; this route contains no `notify_event` call.
- Calendar: none; this route contains no Calendar call.
- Cognito mutation: none in Profile Only mode.
- Expected success: HTTP 200 with the created profile in the Lambda-proxy
  response.

### Option B: intake

- Public path: `POST /requests`, `authorization = NONE`, `AWS_PROXY` to the
  intake Lambda; tenant resolution uses the server-owned public domain map and
  fails closed for missing/unknown/mismatched domains.
- Authenticated path: `POST /client/requests`, `COGNITO_USER_POOLS`,
  `AWS_PROXY` to the same intake Lambda; tenant resolution uses the strict
  authenticated claim.
- Entitlements: active tenant; new public customer emails check
  `max_active_clients`; non-test requests check `max_monthly_bookings`.
- Required customer-intake input includes nonblank client name/email, start
  date and pet names (or normalized pets), plus accepted terms/privacy and
  bounded version values. The client portal additionally requires an eligible
  linked client to represent the client booking branch.
- Persistence: one initial
  `REQ#<UUID> / CLIENT#<client UUID or linked client ID>` request. Non-test
  requests also update/create the monthly booking counter.
- Async: starts the configured Step Functions execution after persistence.
  Failure is logged and the saved request remains; there is no rollback.
- Notifications: `CUSTOMER_INTAKE` calls `REQUEST_RECEIVED`, which may send via
  Postmark and write notification-ledger state according to tenant recipient,
  suppression, and deduplication configuration. Exact sends/ledgers require
  runtime preflight and explicit approval.
- Calendar: not called synchronously by basic intake, but downstream review,
  job, and assignment paths can call it.

### Option D: review and assignment continuation

- `POST /admin/review` and `POST /admin/assign` are Cognito-authorized
  Lambda-proxy methods. Their handlers enforce active tenant, roles, and
  tenant ownership.
- `VERIFY_MEET_GREET` updates client metadata and the linked request to
  `MG_COMPLETED`. Approval is fail-closed when the M&G prerequisite is not
  satisfied.
- `APPROVED` updates the request, appends audit state, invokes job creation
  asynchronously, auto-creates/links customer profile and pets when needed,
  calls `CUSTOMER_APPROVED`, and attempts Calendar sync.
- Assignment updates job and request records, attempts Calendar sync, and
  calls `STAFF_ASSIGNED` and `VISIT_SCHEDULED`.
- The documented Alpha Calendar provider is `none / not_configured`, so an
  approved full workflow would require every Calendar result to be skip-only.
  This status must still be reconfirmed before execution; any event creation or
  other Calendar activity is a hard stop.
- These handlers make sequential writes with fail-safe downstream operations,
  not an atomic cross-handler transaction. Partial state is possible and
  cleanup is correspondingly complex.

## Recommended exact execution

After a new explicit Matthew approval, use the deployed tenant Web UI at
`/t/test-tenant-alpha/admin`, with Matthew privately authenticated as the
intended non-protected Alpha owner/admin.

1. Complete every read-only preflight below.
2. Finalize one run marker from the reserved form
   `SYNTHETIC_B1A_REAL_API_ALPHA_20260902_<RUN>`. `<RUN>` must be a short,
   unique, non-secret execution identifier fixed before the write; do not
   reuse `SYNTHETIC_B1A_ALPHA_20260827` or the P1 marker.
3. Open Add Staff and explicitly select **Create Profile Only**.
4. Submit exactly:
   - display name: the exact run marker;
   - notes: the exact same run marker;
   - role: `Staff`;
   - email: blank;
   - phone: blank;
   - assignable to jobs: unchecked (`false`);
   - no Cognito identity or protected address.
5. Submit once. Never retry, including on timeout, network failure, or
   ambiguous response.
6. Record only sanitized HTTP status, request/correlation identifier, returned
   Alpha company ID, generated staff ID/key, marker, and non-sensitive fields.
7. Perform read-only persistence/log/health checks.
8. Under the same explicit approval, execute only the exact-key cleanup below.
9. Perform read-only baseline and health verification.

This action proves a successful real authenticated persistence slice. It does
not exercise onboarding and therefore cannot create a Cognito account or send
an invite.

## Read-only preflight

Every item is mandatory immediately before the one POST:

1. Repository/checkpoint is the execution-approved commit, clean, with
   `HEAD == origin/main`, empty index, and empty stash.
2. Terraform state is exactly serial `516`, lineage
   `7235fddd-c101-fe62-7669-7b7b3d858955`; do not run `terraform plan`.
3. API `a022yxuiue` is exactly `prod -> atxpw3`; the route remains Cognito
   authorized and Lambda proxy to the admin Lambda.
4. All 13 Lambdas are `Active / Successful`, all have exact `CodeSha256`
   `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=`, and relevant configuration
   is unchanged.
5. `TENANT_RESOLUTION_MODE=multi` remains active on all 13 Lambdas.
6. A consistent Alpha inventory is exactly one item and that item is
   `TENANT#test_tenant_alpha / METADATA`.
7. Sanitized Alpha metadata proves `is_active=true`, subscription/entitlement
   access eligible, numeric `max_staff >= 1`, and Calendar provider
   `none / not_configured`.
8. Alpha staff count is exactly zero and active staff count is zero.
9. No Alpha item contains the finalized marker and there is no residual prior
   B1A synthetic record.
10. Matthew privately confirms the browser is authenticated as the intended
    non-protected Alpha owner/admin at the exact tenant route. Do not inspect
    or capture session material.
11. The route bootstrap succeeds with `company_id=test_tenant_alpha`, access
    allowed, no Platform Admin surface, and no primary-tenant operational data.
12. Record a UTC validation start time. Confirm the selected profile-only
    route has no notification, Calendar, Cognito, async, or billing operation.

If any value differs, do not write.

## Expected result and evidence

- Exactly one browser-generated authenticated `POST /admin/staff`.
- HTTP 200 exactly; no retry.
- Response company is `test_tenant_alpha`.
- Response and consistent `GetItem` agree on the generated
  `COMPANY#test_tenant_alpha / STAFF#staff_<8>` key.
- The item matches the exact marker and approved field contract.
- Alpha inventory moves exactly from 1 to 2 items; staff count moves exactly
  from 0 to 1; no other record type or counter appears.
- Sanitized admin-Lambda evidence contains allowed, non-bypass
  `max_staff` entitlement behavior for `test_tenant_alpha` and no Decimal
  serialization failure.
- No `ERROR`, `Exception`, or `Traceback` attributable to the window.
- No Cognito mutation, Postmark send, notification ledger, Calendar action,
  Step Functions execution, job invocation, or other workflow side effect.
- API, Lambda, tenant-mode, and Terraform baselines remain unchanged.

An ambiguous HTTP result is not a retry condition. Query Alpha by the fixed
marker read-only. Zero matches or more than one match is a validation failure;
one exact match is preserved as evidence and may be cleaned up only under the
explicit cleanup authority.

## Exact cleanup design

Cleanup is a production write and must be explicitly authorized together with
the POST. It is not authorized by this document.

1. Use the returned `staff_id`/PK/SK. A tenant-partition marker query may only
   corroborate the key; it must not select deletion targets.
2. Consistently `GetItem` the exact key immediately before deletion.
3. Require exact agreement on PK, SK, `company_id`, `staff_id`, display-name
   marker, notes marker, `role=Staff`, `is_active=true`,
   `is_assignable=false`, and null email/Cognito linkage.
4. Require Alpha inventory to contain exactly the metadata item and this one
   synthetic staff item, with no request, client, pet, job, notification, or
   counter artifact.
5. Issue one key-specific conditional DynamoDB `DeleteItem`. The condition
   must bind the exact Alpha company, generated staff ID, both marker fields,
   role, active state, and non-assignable state. Request `ALL_OLD` and verify
   the returned item matches the pre-delete item.
6. Do not use wildcard, prefix, batch, scan-driven, or application soft-delete
   cleanup. The application delete flow first disables a profile and requires
   additional mutation for hard deletion; it is less bounded than one
   conditional exact-key delete.
7. Consistently verify the exact key is absent, the marker has zero Alpha
   matches, and Alpha is exactly one metadata item again.

If the item or inventory differs, do not delete. Stop and request a new,
specific remediation approval. A hard stop forbids further workflow actions;
it does not broaden cleanup authority.

## PASS criteria

`B1A REAL WEB/API WRITE-PATH VALIDATION PASS` requires all of the following:

- every preflight condition passed;
- exactly one request traversed the deployed tenant Web, HTTP, API Gateway,
  Cognito authorizer, admin Lambda, strict tenant resolution, active-tenant and
  `max_staff` checks;
- HTTP was exactly 200 and the exact one staff item persisted only for Alpha;
- response, logs, and consistent reads agree on tenant, key, marker, and item;
- no protected-admin entitlement bypass occurred;
- no primary-tenant access/leakage or non-Alpha write occurred;
- no unexpected record, notification, Calendar, Cognito, async, counter,
  billing, or infrastructure side effect occurred;
- no Lambda/P1 Decimal error occurred;
- the one exact conditional cleanup succeeded; and
- Alpha returned to exactly `TENANT#test_tenant_alpha / METADATA`, while API,
  Lambda, state, and tenant-mode baselines remained unchanged.

## STOP criteria

Stop without retry or workflow expansion on:

- any preflight mismatch, unexpected Alpha item, existing marker, wrong route,
  wrong browser identity/role, or protected-admin bypass;
- any resolved tenant other than `test_tenant_alpha`, missing strict claim,
  primary-tenant data exposure, or tenant access disagreement;
- entitlement denial/failure, any HTTP status other than 200, malformed or
  unexpected response, timeout, or ambiguous response;
- zero, duplicate, wrong-key, wrong-tenant, wrong-field, or extra persistence;
- any notification/send/ledger, Calendar activity, Cognito mutation, async
  execution, counter change, or other unexpected side effect;
- any `ERROR`, `Exception`, `Traceback`, Decimal serialization recurrence,
  Lambda health/hash change, API change, state change, configuration drift, or
  cleanup-condition failure.

After a post-write stop, perform no retry and no additional workflow action.
Only the exact cleanup described above may proceed, and only if the later
Matthew approval explicitly includes it and every cleanup precondition passes.

## Isolation and completion semantics

No primary-tenant workflow read is needed. Isolation evidence comes from the
fail-closed route/claim agreement, Cognito-authorized Alpha request, strict
claim-derived `company_id`, Alpha-only DynamoDB key and inventory, sanitized
Alpha entitlement log, and zero non-Alpha writes. Do not query `tog_and_dogs`
customer records to establish this proof.

If the plan passes, use exactly:

`B1A REAL WEB/API WRITE-PATH VALIDATION PASS`

Do **not** use `B1A FULL END-TO-END VALIDATION COMPLETE`. Still unproven through
real external routes are public/client intake persistence, M&G transition,
approval, asynchronous job creation, assignment, and their notification and
Calendar boundaries. Those backend behaviors already have direct-Lambda
evidence, but this representative slice does not revalidate every route.

## Approval boundary

The later Matthew approval must explicitly authorize all and only:

1. the listed read-only Git, Terraform-state, API, Lambda, tenant metadata,
   Alpha inventory, browser-surface, and log checks;
2. one authenticated browser `POST /admin/staff` with the finalized unique
   marker and exact Profile Only payload;
3. no retry under any circumstance;
4. read-only inspection of the exact response, Alpha item/inventory, sanitized
   correlated logs, and unchanged infrastructure health;
5. one exact-key, marker/company/staff-bound conditional DynamoDB deletion of
   only the created staff item; and
6. read-only proof that Alpha returned to its one-item metadata baseline.

It must not authorize intake, client/pet/job creation, M&G, approval,
assignment, Start/Complete, notification, Calendar, Cognito, Terraform,
deployment, tenant, Stripe, Mobile, Ryan-testing, or primary-tenant actions.
