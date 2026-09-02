# P1 Decimal Entitlement Serialization Local Fix

**Date:** 2026-08-31

**Starting checkpoint:** `main` at `26693a52864cd8386d923f95a8f6482ae3efad1c`

**Status:** HISTORICAL LOCAL FIX / SUPERSEDED BY SUCCESSFUL DEPLOYMENT AND PRODUCTION ACCEPTANCE

**Independent review disposition:** `P1_DECIMAL_FIX_REVIEW_APPROVED`

> **2026-09-02 reconciliation:** This record preserves the original local-fix
> checkpoint. The exact reviewed correction was subsequently isolated,
> packaged, deployed to all 13 Lambdas, and accepted through one guarded real
> Web/Cognito/API Gateway execution. Final disposition:
> `P1_PRODUCTION_DECIMAL_ACCEPTANCE_PASS`. See
> `p1-decimal-entitlement-serialization-production-acceptance.md`.

## Defect and observed B1A impact

Tenant entitlement limit overrides loaded from DynamoDB retain Python `Decimal`
values. `common.billing._build_entitlement()` preserved those numeric values,
`common.entitlement.check_limit()` supplied `max_allowed` to the structured
decision log, and `_log_decision()` used plain `json.dumps(log_payload)`.
Standard JSON serialization rejected the `Decimal` before the handler reached
normal response serialization or persistence.

During controlled B1A Gate-B execution, `POST /admin/staff` returned HTTP 500
and did not persist the staff record. The approved Gate-B run used its separately
documented direct DynamoDB fallback. The shared risk also covered staff
onboarding, active-client creation, and monthly-booking limit checks.

## Exact local correction

`src/backend/common/entitlement.py` now imports the repository's existing
`DecimalEncoder` from `common.response` and changes only the structured log
serialization call to:

```python
json.dumps(log_payload, cls=DecimalEncoder)
```

The canonical encoder retains whole-number semantics by encoding whole
`Decimal` values as JSON integers. Fractional values are encoded as JSON
floating-point numbers and are not silently truncated. The entitlement object
is not mutated.

No handler logic, tenant resolution, tier definition, limit, comparison,
message, fail-open/fail-closed rule, protected-admin behavior, or
`EntitlementDenied` behavior changed.

## Exact implementation and test files

- `src/backend/common/entitlement.py`
- `tests/backend/test_r17g_entitlement_observability.py`
- `tests/backend/test_r17d_entitlement_wiring.py`
- `tests/backend/test_r18l_client_booking_limits.py`

The tests use real Python `Decimal` fixtures and cover parseable allowed and
denied structured logs, whole and fractional numeric semantics, continued
denial at the limit, realistic `max_staff` handler behavior,
`max_active_clients`, and `max_monthly_bookings`.

## Local validation

- focused Decimal regression selection: 5/5 passed after reproducing 5/5
  pre-fix failures with `Object of type Decimal is not JSON serializable`;
- entitlement observability: 6/6 passed;
- entitlement wiring, including realistic `max_staff`: 20/20 passed;
- core entitlement enforcement: 9/9 passed;
- relevant client/booking selection: 15/15 passed with only the two documented
  unrelated date-stale baseline tests excluded;
- disabled-tenant plus Platform Admin boundaries: 26/26 passed;
- tenant route and public-intake boundaries: 49/49 passed;
- Python compile passed for all four changed Python files;
- `git diff --check` passed.

## Known unrelated baseline failures

Two unchanged tests in `test_r18l_client_booking_limits.py` hard-code the June
2026 usage key while the unchanged production helper correctly derives the
current August 2026 key. Both failures reproduced identically from a temporary
archive of the exact starting SHA. They are date-stale assertions, not P1
regressions.

Three unchanged tests in `test_r11e_tenant_enforcement.py` also reproduced
identically at the starting SHA. Their legacy mocks return request/pet records
or an unconfigured `MagicMock` where active tenant metadata is now required,
causing the already-documented `TenantDisabled` and `fromisoformat` fixture
failures. This P1 change does not modify those tests or tenant enforcement.

## Release boundary and next action

No package, Terraform plan/apply, deployment, AWS mutation, production API
invocation, production data write, Cognito change, DNS/CloudFront change,
notification, Calendar call, Stripe action, Mobile build/distribution, or
tenant change occurred.

This local closeout does not claim the production defect is resolved, that
production staff creation was validated, that the real Web/API write path is
complete, or that production acceptance is complete. Production retains the
defect until a separately reviewed and explicitly approved backend deployment.

B1A real Web/API write-path validation remains outstanding and separately
approval-gated. The next recommended action is **isolated backend/Lambda release
candidate preparation — planning/review only**. That RC is not prepared here.
