# P1 Decimal Entitlement Serialization Production Acceptance

**Date:** 2026-09-02

**Status:** `P1_PRODUCTION_DECIMAL_ACCEPTANCE_PASS`

**Final P1 status:** DEPLOYED / PRODUCTION ACCEPTANCE PASS / COMPLETE

## Accepted production execution

Matthew authorized one guarded production execution through the real tenant
Web path. The validation started at `2026-09-02T16:17:56.138Z`; the response
was observed at `2026-09-02T16:18:06.941Z`.

- Web tenant path: `/t/test-tenant-alpha/admin`
- Production API path: `POST /admin/staff`
- Tenant: `test_tenant_alpha`
- Creation mode: Profile Only
- Attempts: exactly `1`; no retry
- HTTP result: expected `403 Forbidden`
- Response boundary: the permanent protected-account guard rejected the
  request after entitlement evaluation and before persistence
- Target entitlement event: exactly one `ENTITLEMENT_ALLOWED` limit event
- `check_type`: `limit`
- `limit_key`: `max_staff`
- `protected_admin_bypass`: `false`
- `current_count`: numeric `0`
- `max_allowed`: numeric `1`, sourced from a DynamoDB numeric value and
  deserialized by Python as `Decimal`
- Structured decision-log JSON: parse PASS
- `Object of type Decimal is not JSON serializable`: `0`
- Lambda `ERROR` / `Exception` / `Traceback` signals: `0`

`check_limit()` also emitted the expected subscription decision before the
single target limit decision. It was a distinct `check_type=subscription`
event, not a duplicate `max_staff` limit event.

## Persistence and side-effect proof

The consistent Alpha inventory before and after was exactly one item:

`TENANT#test_tenant_alpha / METADATA`

- Alpha staff count before: `0`
- Alpha staff count after: `0`
- Synthetic marker matches after: `0`
- Records created / updated / deleted: `0 / 0 / 0`
- Postmark activity attributable to the validation window: `0`
- Google Calendar activity attributable to the validation window: `0`
- Cognito mutations: `0`
- Cleanup required: none
- Primary `tog_and_dogs` workflow data used or modified: none

## Post-validation infrastructure health

- Lambdas: `13/13` `Active / Successful`
- Lambdas on approved `CodeSha256`: `13/13`
- Approved `CodeSha256`:
  `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=`
- `TENANT_RESOLUTION_MODE=multi`: `13/13`; unchanged
- REST API: `a022yxuiue`
- Stage/deployment: `prod -> atxpw3`; unchanged
- Terraform state serial: `516`; unchanged
- Terraform lineage:
  `7235fddd-c101-fe62-7669-7b7b3d858955`; unchanged

## Closeout boundary

The production request exercised the deployed handler, tenant resolution,
`check_limit(max_staff)`, `_log_decision()`, and `DecimalEncoder`. The
Decimal-backed limit serialized as a valid JSON number without an exception.
P1 is complete and is no longer an active production blocker.

B1A did not begin during this validation. Its backend workflow validation,
read-only real API Gateway/Cognito path, and synthetic cleanup are complete;
full real Web/API write-path validation remains outstanding and separately
approval-gated.

No second probe, deployment, Terraform plan/apply, infrastructure mutation,
tenant mutation, notification, Calendar write, Stripe action, Mobile action,
or cleanup was performed.
