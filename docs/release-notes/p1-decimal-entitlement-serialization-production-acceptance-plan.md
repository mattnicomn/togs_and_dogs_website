# P1 Decimal Entitlement Serialization Production Acceptance Plan

**Date:** 2026-09-01

**Status:** EXECUTED ONCE AS APPROVED / PRODUCTION ACCEPTANCE PASS / HISTORICAL PLAN

**Authoritative production status:** P1 DEPLOYED / PRODUCTION ACCEPTANCE PASS / COMPLETE

> **2026-09-02 result:** Matthew approved and the guarded probe described in
> this plan executed exactly once. It returned the expected HTTP 403 after one
> non-bypass `ENTITLEMENT_ALLOWED` `max_staff` event with numeric
> `current_count=0` and Decimal-backed `max_allowed=1`. JSON parsed, the
> serialization/runtime error count was zero, Alpha remained at its exact
> metadata-only baseline, and Postmark/Calendar activity was zero. See
> `p1-decimal-entitlement-serialization-production-acceptance.md`.

## Scope and current evidence

The approved saved Terraform plan
`p1-decimal-entitlement-backend-reconciled-20260901-state513.tfplan`, SHA-256
`D20B01FD309DB72C1608E774FA71A1317DB0364A27588FD8CD6569FB2938C022`,
was applied with exactly `0 add / 13 change / 0 destroy`. The resulting
production evidence is:

- all 13 Lambdas are `Active` with `LastUpdateStatus=Successful`;
- all 13 report `CodeSha256`
  `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=`;
- REST API `a022yxuiue` remains `prod -> atxpw3`;
- Terraform state is serial `516`, lineage
  `7235fddd-c101-fe62-7669-7b7b3d858955`;
- unauthenticated `GET /prod/admin/clients` returns the accepted `401` Cognito
  authorizer response;
- a direct, statically read-only `GET /admin/clients` Lambda smoke returned
  invocation `200` and handler `200` with no function error;
- post-deployment logs contained zero `ERROR`, `Exception`, `Traceback`, or
  `Object of type Decimal is not JSON serializable` events.

At this planning checkpoint, no post-deployment `ENTITLEMENT_ALLOWED` or
`ENTITLEMENT_DENIED` event had occurred, so the corrected production
`_log_decision()` Decimal path was not yet execution-proven. The later result
linked above supersedes that historical planning state. This plan never
included B1A.

## Boundaries

- Platform/operator: USMissionHero LLC.
- Primary customer tenant: `tog_and_dogs` (Togs & Dogs, Ryan's business).
- Internal validation tenant: `test_tenant_alpha` only.
- Strict `TENANT_RESOLUTION_MODE=multi` remains active and unchanged.
- No `tog_and_dogs` customer data may be used, read as workflow data, or
  modified by this probe.
- Matthew authenticates privately. No password, token, cookie, Authorization
  header, JWT, or raw session material may be inspected or recorded.
- This P1 probe is not B1A real Web/API workflow validation.

## Candidate comparison

| Candidate | Entitlement decision | Persistence and side effects | Denial can be forced safely? | Disposition |
| --- | --- | --- | --- | --- |
| `POST /admin/staff`, Profile Only, permanent protected system address | `max_staff` before the protected-address guard | Expected zero records; no notification or Calendar call exists on this route | Capacity denial cannot be forced from request data, but the protected-address guard deterministically rejects after either allowed or denied decision | **Recommended** |
| `POST /admin/staff`, ordinary synthetic profile | `max_staff` before `put_item` | One `COMPANY#test_tenant_alpha / STAFF#<uuid>` record if allowed; no notification or Calendar | Only if current staff count is already at the limit; otherwise persists | Fallback only; not approved by this plan |
| `POST /admin/staff/onboard` | `max_staff` before Cognito work | If allowed: Cognito user, group membership, staff record, and welcome Postmark email | Not deterministically; protected-address guard occurs after the limit check but route has much higher rollback complexity if the guard is bypassed or changed | Reject |
| `POST /admin/clients`, Profile Only | `max_active_clients` | If allowed: one client record | Protected-address and duplicate guards occur before `check_limit`; they cannot prove the Decimal path | Reject |
| `POST /admin/clients/onboard` | `max_active_clients` | If allowed: Cognito user/group, client record, and welcome Postmark email | Protected-address guard occurs before the entitlement check | Reject |
| `POST /client/requests` with `source=admin_created` | `max_monthly_bookings` | Requires an existing Alpha client; then request, counter, asynchronous job/Calendar path | Alpha baseline has no client, and denial cannot be forced from request data | Reject |
| Public `POST /requests` or authenticated client request | `max_active_clients` and/or `max_monthly_bookings` | Request record, usage counter, Step Function, and possible notification if allowed | Denial depends on persisted counts and cannot be forced safely | Reject |
| Auto-profile creation in `common/client_profile.py` | `max_active_clients` | Runs only after an intake/request record already exists and writes request/audit state on denial | Not a standalone API probe and not zero-persistence | Reject |

No route exposes a request-controlled `current_value` or limit. A genuine
`ENTITLEMENT_DENIED` cannot be forced without first changing tenant metadata or
creating enough records to meet a limit. Those actions are not recommended.

### Candidate operational details

- Profile-only `POST /admin/staff` is handled by
  `src/backend/handlers/admin_handler.py:749-815`. It reaches
  `check_limit(..., 'max_staff', ...)` before its duplicate, protected-email,
  UUID, or write steps. The protected-address guard makes the recommended
  request zero-persistence when capacity is available; an already-full limit
  denies even earlier and still logs through `_log_decision()`. No Postmark or
  Calendar function is called in this route. Expected cleanup is none. An
  unexpected write would be one staff item and requires a separately approved,
  key-specific cleanup; it must never be auto-rolled back.
- Staff onboarding is handled by `admin_handler.py:818-951` and checks
  `max_staff` at line 854. A denial logs before persistence, but capacity cannot
  be safely forced. If allowed, later Cognito, staff-item, and welcome-email
  operations make cleanup multi-system and high complexity. The protected
  guard is later than the limit but is not selected because this route has
  avoidable side-effect exposure. It has no Calendar call.
- Client onboarding is handled by `admin_handler.py:1051-1169` and checks
  `max_active_clients` at line 1090. Protected/duplicate handling can return
  before the desired limit event, while an allowed request can mutate Cognito,
  write a client item, and send welcome email. Cleanup is multi-system and high
  complexity; no Calendar call occurs in this route.
- Profile-only `POST /admin/clients` is handled by
  `admin_handler.py:1985-2049` and checks `max_active_clients` at line 2025.
  Its safe protected/duplicate early returns occur before `check_limit()`, so
  they do not prove Decimal logging. An ordinary allowed request writes one
  client item. It sends no notification and calls no Calendar function, but
  would require a separately approved key-specific cleanup.
- Admin-created `POST /client/requests` is handled by
  `src/backend/handlers/intake_handler.py:145-304` and checks
  `max_monthly_bookings` at line 185. Alpha's one-metadata-item baseline lacks
  the required client; that early return prevents the target event. If allowed,
  the route writes request/counter state and can attempt Calendar sync. Cleanup
  is multi-record and high complexity.
- Public or client request creation is handled by
  `intake_handler.py:308-558`, with `max_active_clients` at line 450 and
  `max_monthly_bookings` at line 459. A successful path writes a request,
  starts downstream work, and can notify; request validation or identity checks
  can return before either target event. Capacity denial cannot be request-
  forced, and cleanup/rollback is high complexity.
- Auto-profile creation is handled by
  `src/backend/common/client_profile.py:145-247`, with
  `max_active_clients` at line 185 and a profile write at line 238. It is a
  nested helper reached after earlier workflow persistence, not an independent
  API route. Even an entitlement denial can accompany request/audit mutation,
  so it is not a zero-persistence probe and has high cleanup complexity.

## Recommended guarded probe

### Exact production path

Use the deployed Web UI at `/t/test-tenant-alpha/admin` with Matthew privately
authenticated as a non-protected Alpha owner/admin:

1. Open **Add New Staff Profile**.
2. Select **Profile Only** (not onboarding).
3. Submit exactly once through the existing UI, which calls authenticated
   `POST /admin/staff` through API Gateway.
4. Use synthetic marker
   `SYNTHETIC_P1_DECIMAL_ALPHA_20260901_GUARD` as both display name and notes.
5. Use the permanent protected system address `support@usmissionhero.com` in
   the profile email field. This is request data used only to reach the
   existing protected-account rejection; it is not the caller identity and no
   email is sent.
6. Role: `Staff`; assignable: `false`; creation mode: `profile_only`.

Do not use a direct Lambda invocation when the real browser/API Gateway path is
available. Do not extract a token to construct a separate HTTP client.

### Source-order proof

The deployed RC source establishes this ordering:

1. API Gateway declares `POST /admin/staff` as
   `COGNITO_USER_POOLS` and Lambda proxy integration
   (`modules/api/main.tf:718-733`).
2. The Web Profile Only path calls `createStaff()` and therefore
   `POST /admin/staff` (`web/src/components/AdminDashboard.jsx:1341-1345` and
   `web/src/api/client.js:85-90`).
3. The admin handler first applies the shared active-tenant boundary before
   ordinary routes (`src/backend/handlers/admin_handler.py:501-503`).
4. The route requires owner/admin, parses the body, validates a non-empty,
   non-reserved display name, and resolves company ID
   (`admin_handler.py:749-769`).
5. It queries only `COMPANY#<company_id>` staff records and computes the active
   staff count (`admin_handler.py:771-781`).
6. It calls
   `check_limit(company_id, 'max_staff', active_staff_count, context=event)`
   at `admin_handler.py:782`.
7. `check_limit()` loads the tenant entitlement, resolves `max_staff`, emits
   either `ENTITLEMENT_DENIED` before raising or `ENTITLEMENT_ALLOWED` before
   returning (`src/backend/common/entitlement.py:331-407`).
8. `_log_decision()` serializes the structured payload with
   `json.dumps(..., cls=DecimalEncoder)` at
   `src/backend/common/entitlement.py:52-86`.
9. Only after the entitlement call does the handler test duplicate display
   name and the protected profile email (`admin_handler.py:784-791`).
10. The permanent fallback protected address is always included by
    `src/backend/common/protected_accounts.py:17-43`.
11. UUID creation and the sole `put_item` occur later at
    `admin_handler.py:793-815`.

Therefore the expected path is:

`Cognito authorization -> strict tenant resolution -> active-tenant check ->`
`staff read/count -> check_limit(max_staff) -> _log_decision -> DecimalEncoder ->`
`protected-address rejection -> HTTP 403`, with no persistence.

The caller must not be a protected-admin bypass identity. A bypass event is not
acceptable evidence because it substitutes enterprise integer limits. The
accepted limit event must contain `protected_admin_bypass=false`.

### Expected result

- HTTP: `403 Forbidden`.
- If `current_count < max_allowed`: one `ENTITLEMENT_ALLOWED` limit event,
  followed by `Cannot create a standard profile using a protected account
  identity.`
- If `current_count >= max_allowed`: one `ENTITLEMENT_DENIED` limit event and
  the handler's entitlement `403`; the protected-address guard is not reached.
- In either case, the accepted event must be `check_type=limit`,
  `limit_key=max_staff`, `company_id=test_tenant_alpha`,
  `protected_admin_bypass=false`, and must contain numeric `current_count` and
  numeric Decimal-backed `max_allowed` in parseable JSON.
- Expected DynamoDB records created: **zero**.
- Expected Cognito mutations: **zero**.
- Expected Postmark/email activity: **zero**.
- Expected Google Calendar activity: **zero**.
- Cleanup requirement: **none** if the expected result occurs.

## Pre-validation checks

All checks are read-only and must pass before the single POST:

1. Main and RC Git hygiene remains known and clean; no runtime/source change is
   introduced by this planning record.
2. Production remains 13/13 `Active / Successful` on the approved code hash.
3. API remains `prod -> atxpw3`; Terraform state remains serial `516` on the
   documented lineage.
4. `TENANT_RESOLUTION_MODE=multi` remains unchanged.
5. `test_tenant_alpha` metadata is active/eligible and `limits.max_staff` is a
   DynamoDB numeric value that the Python SDK will deserialize as `Decimal`.
   Record only the sanitized numeric limit, not the full tenant item.
6. A consistent Alpha inventory is exactly one item:
   `TENANT#test_tenant_alpha / METADATA`; staff count is zero.
7. The browser shows the authenticated Alpha tenant surface. Do not inspect or
   record its token/session data.
8. Record UTC start timestamp immediately before the single submission.

If any precondition differs, do not submit the POST.

## CloudWatch evidence plan

Using the UTC start timestamp and the API/Lambda request correlation ID, return
only sanitized fields from the admin Lambda log:

- `event` is `ENTITLEMENT_ALLOWED` or `ENTITLEMENT_DENIED`;
- `company_id=test_tenant_alpha`;
- `check_type=limit`;
- `limit_key=max_staff`;
- `protected_admin_bypass=false`;
- numeric `current_count`;
- numeric `max_allowed`;
- the full line parses as JSON;
- no `Object of type Decimal is not JSON serializable`;
- no `ERROR`, `Exception`, or `Traceback` attributable to the window.

Do not display request bodies, private identity fields, tokens, cookies, or
unrelated application log messages.

## Post-validation checks

1. Confirm the response was exactly HTTP 403 and no retry occurred.
2. Consistently read the Alpha inventory and prove it remains exactly
   `TENANT#test_tenant_alpha / METADATA`.
3. Prove no `COMPANY#test_tenant_alpha / STAFF#*` record exists and the exact
   synthetic marker is absent from Alpha records.
4. Confirm no notification record or send attributable to the marker and no
   Calendar attempt.
5. Confirm all 13 Lambdas remain `Active / Successful` on the approved hash.
6. Confirm API remains `prod -> atxpw3` and Terraform state serial/lineage are
   unchanged.

Do not query `tog_and_dogs` customer records as workflow data. Isolation proof
comes from the authenticated Alpha route, the Alpha company ID in the accepted
decision log, and the Alpha-only pre/post inventory.

## PASS criteria

PASS requires every condition below:

- the real Web/API Gateway/Cognito/Lambda path was used exactly once;
- the resolved tenant and decision log are `test_tenant_alpha`;
- a non-bypass `max_staff` limit decision was emitted;
- the JSON log parses and `max_allowed` remains numeric;
- no Decimal serialization failure or other error occurred;
- HTTP 403 matched the planned denial boundary;
- Alpha persistence remained exactly the one metadata baseline item;
- no primary-tenant data was touched;
- no Cognito, notification, Postmark, Calendar, billing, or workflow side
  effect occurred;
- no cleanup was required;
- all 13 Lambdas and API deployment remained unchanged.

## Immediate STOP criteria

Stop without retry if any of the following occurs:

- preflight inventory or metadata differs from the required Alpha baseline;
- the caller resolves as a protected-admin bypass;
- the decision has the wrong tenant, check type, or limit key;
- the expected limit event is absent, duplicated, not parseable JSON, or lacks
  numeric `max_allowed`;
- HTTP is not 403;
- any Alpha record is created or changed;
- any Cognito, notification, Postmark, Calendar, counter, request, job, client,
  pet, or other workflow side effect occurs;
- any P1 Decimal error, `ERROR`, `Exception`, or `Traceback` occurs;
- Lambda health/hash, API deployment, state serial, lineage, or strict tenant
  configuration differs.

If an unexpected record is created, do not perform automatic cleanup. Preserve
the exact key and marker as sanitized evidence and request a separate,
key-specific cleanup approval.

## Approval boundary

This document authorizes nothing. The exact future action requiring Matthew's
approval is:

> Execute once, through the privately authenticated
> `/t/test-tenant-alpha/admin` Web UI and real API Gateway, the guarded Profile
> Only `POST /admin/staff` described above, together with only the stated
> read-only preflight, CloudWatch, Alpha-inventory, Lambda-health, API-stage,
> and Terraform-state checks. No retry, B1A expansion, record creation,
> notification, Calendar action, or automatic cleanup is authorized.
