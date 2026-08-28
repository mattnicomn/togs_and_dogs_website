# B1A API Gateway Read-Only Validation

**Date:** 2026-08-28

**Repository checkpoint:** `main` at `477a42bcffc9a21911ed1b1d62068f922a71a22f`

**Disposition:** API layer verified; B1A Gate-C cleanup ready for separate Matthew approval; Gate C not executed

## Scope and safety

This handoff check was read-only. It made no DynamoDB write, mutating HTTP request, notification, Calendar call, deployment, AWS configuration change, Cognito change, DNS change, Mobile change, Stripe change, or cleanup action. Matthew entered application credentials privately. No password, token, cookie, Authorization header, JWT, or raw session material was inspected, captured, logged, retrieved, or recorded.

## Gate-B reconciliation

Gate B validated the deployed backend workflow and business logic but had three material execution qualifications:

1. `POST /admin/staff` failed with `Object of type Decimal is not JSON serializable`; the Alpha staff fixture was therefore created by a direct DynamoDB `put_item` under the approved Gate-B scope.
2. `VERIFY_MEET_GREET` / `MG_COMPLETED` preceded approval because the deployed approval validation requires completed Meet & Greet state.
3. Workflow actions were invoked directly against Lambda with constructed API Gateway-style events. Gate B therefore did not validate real API Gateway routing or Cognito-authorizer behavior.

The prior canonical state recorded the first two qualifications but omitted the third and did not enumerate the cleanup keys. This release note closes that documentation gap.

## Exact preserved Alpha inventory

Read-only scans before and after the authenticated HTTP check each returned exactly nine `company_id = test_tenant_alpha` items: one baseline tenant record and the exact eight synthetic B1A artifacts below. Missing keys: zero. Unexpected keys: zero.

Baseline to preserve permanently:

- `TENANT#test_tenant_alpha` / `METADATA`

Synthetic Gate-C cleanup manifest (preserve until separately approved cleanup):

1. `COMPANY#test_tenant_alpha` / `STAFF#staff_alpha01`
2. `REQ#3fba9817-ccb2-460e-9430-1a65edda79c4` / `CLIENT#750d5e1a-a4cb-4a2c-bf56-b8854d727326`
3. `CLIENT#750d5e1a-a4cb-4a2c-bf56-b8854d727326` / `METADATA`
4. `PET#3dc14dec-b15f-4790-880a-ad4c7975031d` / `CLIENT#750d5e1a-a4cb-4a2c-bf56-b8854d727326`
5. `JOB#43fa73ef-48ed-4309-9d79-c3fdae19c9f1` / `REQ#3fba9817-ccb2-460e-9430-1a65edda79c4`
6. `NOTIF#2e3345d7-e669-4ef2-8ef3-a25cc5f7d59f` / `REQUEST#3fba9817-ccb2-460e-9430-1a65edda79c4`
7. `NOTIF#209486c5-f4e5-4605-b6f4-d579f63e7ab3` / `REQUEST#3fba9817-ccb2-460e-9430-1a65edda79c4`
8. `NOTIF#9b3d4011-b014-4775-b38a-41d62b927919` / `REQUEST#3fba9817-ccb2-460e-9430-1a65edda79c4`

Narrow primary-tenant evidence returned zero `tog_and_dogs` items created or updated during the Alpha Gate-B execution window (`2026-08-27T19:52:59Z` through `19:56:29Z`) and zero primary-tenant items carrying the synthetic request, client, or job identifiers.

## Deployed API contract

| Field | Verified production value |
|---|---|
| REST API | `a022yxuiue` |
| Resource | `GET /admin/tenant-info` (`4dm5fv`) |
| Authorization | `COGNITO_USER_POOLS` |
| Authorizer | `CognitoAuthorizer` (`r0gk6r`) |
| Identity source | `method.request.header.Authorization` |
| Integration | `AWS_PROXY`; API Gateway integration method `POST` |
| Lambda | `togs-and-dogs-prod-admin` |
| Stage | `prod` |
| Deployment | `atxpw3` |

An unauthenticated real HTTP GET with `expectedTenantSlug=test-tenant-alpha` returned the expected `401`, proving the deployed authorizer rejects a missing identity. Matthew then authenticated privately on `/t/test-tenant-alpha/admin`. A fresh read-only reload rendered title `Test Tenant Alpha | Pet Care Portal`, heading `Test Tenant Alpha`, the Alpha-only staff option, and the single scheduled synthetic visit. The Web bootstrap can reach that state only after the protected `GET /admin/tenant-info?expectedTenantSlug=test-tenant-alpha` succeeds and returns the authoritative tenant context. No Platform Admin navigation or `tog_and_dogs` operational data was present.

Together with the deployed method/integration inspection, this verifies the real browser HTTP → API Gateway route → Cognito authorizer → Lambda proxy → expected-tenant resolution → read-only response path. This check does not claim that the Gate-B write workflow was driven through the Web UI.

## Staff-create defect

`common.billing._build_entitlement()` preserves numeric tenant limit overrides loaded from DynamoDB as `Decimal`. `common.entitlement.check_limit()` passes `max_allowed` to `_log_decision()`, whose plain `json.dumps(log_payload)` cannot serialize `Decimal`. The exception occurs before `POST /admin/staff` reaches `put_item`; the handler converts it to a 500. The response layer's `DecimalEncoder` does not help because the failure occurs earlier in structured logging.

Classification: P1/high production defect. It blocks normal staff creation and staff onboarding for affected tenants and shares a path with active-client and monthly-booking limit checks. A separate bounded backend workstream should make entitlement decision logs Decimal-safe, preserve enforcement semantics, and add realistic DynamoDB-Decimal coverage for every `check_limit` call-site category. No runtime fix is included here.

## B1A status and next gate

- Backend handler/business workflow: validated under Gate B, with documented deviations.
- Notifications: two controlled Gate-B deliveries were observed; no notification was sent in this read-only check.
- Calendar boundary: Gate B returned `calendar_skipped`; Alpha remains unconfigured and this check made no Calendar call.
- Tenant data isolation: passed in Gate B and reconfirmed by exact Alpha inventory plus narrow zero-count primary-tenant evidence.
- API Gateway routing and Cognito authorizer: verified read-only in this check.
- Web UI write workflow: not performed and not claimed.

B1A should not be described as full Web workflow validation. Gate C may remove exactly the eight synthetic items above only after separate Matthew approval and must preserve `TENANT#test_tenant_alpha / METADATA`. The exact inventory and API smoke prerequisites are satisfied. Gate C was not executed.
