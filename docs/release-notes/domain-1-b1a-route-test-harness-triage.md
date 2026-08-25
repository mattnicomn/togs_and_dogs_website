# DOMAIN-1 / B1A-ROUTE Test-Harness Triage

**Date:** 2026-08-25

**Status:** TEST-HARNESS FIX READY FOR DOMAIN-1 V3 RC REBUILD

## Scope and controls

This was a local-only comparison and test-harness correction. No AWS access,
package generation, Terraform plan, deployment, Web change, Mobile change, or
backend runtime change occurred.

The comparison used:

- authoritative main `ccdb3c2cc42097ee87b8664cfdc1342970b7b079`;
- DOMAIN-1 v2 RC `3583b15b7b5907445db8e47dda54baa961895473`;
- deployed E3A backend baseline `732e48b930f6fd9aac958351c4ac7823c14cf3e0`;
- Python 3.13.3 with `PYTHONPATH=src/backend` and AWS instance-metadata
  discovery disabled for both candidate and baseline runs.

## Baseline comparison

Each test was run individually on the exact v2 RC and then under the identical
local environment on the deployed E3A baseline.

| Test | DOMAIN-1 v2 RC | Deployed E3A baseline | Classification |
| --- | --- | --- | --- |
| `test_review_handler_same_tenant_approved` | 403 `TenantDisabled` | 403 `TenantDisabled` | A — fails identically on deployed baseline |
| `test_admin_handler_export_filters_by_company` | 500; `fromisoformat` received a non-string | 500; `fromisoformat` received a non-string | A — fails identically on deployed baseline |
| `test_pet_handler_get_same_tenant_succeeds` | 403 `TenantDisabled` | 403 `TenantDisabled` | A — fails identically on deployed baseline |

No test classified B, so the evidence does not indicate a DOMAIN-1 runtime
regression.

## Root causes and bounded correction

The review and pet success tests patched `common.db.get_item` with a single
domain-record return value. `require_active_tenant` calls that same function
first with `TENANT#tog_and_dogs` / `METADATA`. Consequently, the entitlement
builder interpreted a request or pet record as tenant metadata; the absent
`subscription_status` correctly defaulted to `disabled`.

The export test patched `common.db.table` but did not define the table's
`get_item` result. The entitlement lookup therefore received a truthy
`MagicMock` instead of tenant metadata. Its synthetic `admin_override_until`
was also truthy, so deployed `TenantEntitlement._is_override_active`
legitimately attempted to parse it as an ISO timestamp and raised the observed
`fromisoformat` type error. No export-domain record timestamp was missing; the
missing fixture was the tenant metadata lookup itself. The corrected fixture
explicitly models an active professional tenant with no temporary override
(`admin_override_until=None`).

Only `tests/backend/test_r11e_tenant_enforcement.py` changed. It now provides a
small active-tenant metadata builder and key-aware mock dispatch so entitlement
lookups and request/pet lookups receive the correct records. Production
disabled/inactive enforcement was not weakened.

## Validation

- exact corrected tests: 3/3 passed;
- tenant-isolation selection: 51/51 passed;
- DOMAIN-1 tenant-route suite: 14/14 passed;
- deployed E3A compatibility suite: 24/24 passed;
- disabled-tenant plus Platform Admin suites: 26/26 passed;
- explicit negative boundary selection: 11/11 passed, covering disabled,
  inactive, missing, wrong-tenant, strict-multi fail-closed, and Platform Admin
  no-route-authority cases;
- shared token validator: 9/9 passed;
- shared constants validator: 18/18 passed;
- shared adapter validator: 7/7 passed in a generator-normalized temporary
  copy. The first direct Windows run exposed only committed CRLF versus
  generator LF raw-text comparison; validator-created Web/Mobile changes were
  discarded and no Web/Mobile diff remains;
- production API semantic manifest validator passed at 50 resources, 52
  methods, 52 integrations, 44 CORS resources, and 2 gateway responses;
- Python backend compilation passed;
- `git diff --check` passed.

The source diff from the v2 RC contains zero files under `src/backend`, `web`,
`mobile`, `infra`, or `modules`. Packaging and planning remain prohibited until
a fresh DOMAIN-1 v3 RC rebuild is separately performed and reviewed.
