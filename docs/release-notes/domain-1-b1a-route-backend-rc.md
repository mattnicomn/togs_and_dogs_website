# DOMAIN-1 / B1A-ROUTE Backend Release Candidate

**Date:** 2026-08-24

**Status:** ISOLATED / VALIDATED / NOT DEPLOYED
**Deployed backend baseline:** `732e48b930f6fd9aac958351c4ac7823c14cf3e0`

This candidate starts from the exact E3A Gate-A release commit recorded as
deployed in production. It preserves the deployed child Start action and
occurrence-aware exact-request read, then adds only the fail-closed tenant-route
resolver, the bounded `expectedTenantSlug` tenant-info integration, and focused
tests.

## Runtime delta

- `src/backend/common/tenant_route.py`: server-owned route registry and strict
  route/active-tenant/Cognito-claim agreement.
- `src/backend/handlers/admin_handler.py`: only the `/admin/tenant-info` branch
  accepts and validates `expectedTenantSlug`; compatibility-host behavior is
  unchanged when the parameter is absent.

There is no API Gateway, Terraform, shared contract, Cognito, DNS, production
data, Mobile, or other backend runtime change in this candidate.

## Validation

- Focused route, E3A, disabled-tenant, and Platform Admin regressions: 64 passed.
- Legacy `test_r19k_tenant_isolation.py`: 3 passed / 6 unchanged local
  AWS-credential failures; all failures are in unmodified Google Calendar or
  compatibility tenant-info paths and reproduce the checkpoint environment.
- Shared constants/API validator: 18 passed.
- Generated adapter validator: 7 passed after the established Windows LF
  normalization run; generated files were restored with no candidate delta.
- Python compile and `git diff --check`: passed.

No deployment or external-system change occurred while preparing this RC.
