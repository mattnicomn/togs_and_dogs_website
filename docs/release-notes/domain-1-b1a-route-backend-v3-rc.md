# DOMAIN-1 / B1A-ROUTE Backend V3 Release Candidate

**Date:** 2026-08-25

**Status:** LOCAL VALIDATION COMPLETE / PACKAGE AND STATE-510 PLAN PENDING / NO APPLY AUTHORIZED

## Exact composition

Branch `release/domain1-b1a-route-backend-v3-rc` was cut from the reviewed v2
test-harness checkpoint `3a04476aeb51b9294cd74d2c2cd42a5cc217d0a5`.
Its ancestry composes:

- deployed E3A backend baseline
  `732e48b930f6fd9aac958351c4ac7823c14cf3e0`;
- deployed semantic-fingerprint infrastructure commits `044e19d` and
  `6f130fb4ba6d07b457a0466d8ee1f301dd6ba2da`;
- reviewed DOMAIN-1 backend replay `f3d48f15641b82f8f86b0157fb215ac31a489058`;
- blocked v2 evidence checkpoint
  `3583b15b7b5907445db8e47dda54baa961895473`;
- test-harness-only correction `3a04476aeb51b9294cd74d2c2cd42a5cc217d0a5`.

Relative to deployed E3A, the only `src/backend` differences are
`common/tenant_route.py` and bounded `expectedTenantSlug` handling in
`handlers/admin_handler.py`. Relative to deployed semantic source `6f130fb4`,
`modules/api` is identical at tree
`b91d28ef2670279ffe46061a52de1bfef75904c2` and `infra/prod` is identical at
tree `c5646d22d660098b1ec41e902ed84eb82391b3f9`.

The harness correction changes only
`tests/backend/test_r11e_tenant_enforcement.py`. It provides explicit active
professional tenant metadata, key-aware entitlement/domain-record mock
dispatch, and `admin_override_until=None`. Disabled/inactive tenant enforcement
remains unchanged.

## Completed local validation

- DOMAIN-1 route: 14/14 passed;
- deployed E3A behavior: 24/24 passed;
- tenant isolation: 51/51 passed;
- disabled tenant plus Platform Admin: 26/26 passed;
- explicit negative tenant boundaries: 11/11 passed;
- semantic fingerprint Terraform tests: 10/10 passed;
- production manifest: 50 resources / 52 methods / 52 integrations / 44 CORS
  resources / 2 gateway responses;
- LF, CRLF, and compact saved-plan fingerprints identical at
  `3c33e8944154f9fd96e77cd53be92e3cb9f6613d`; embedded-plan reread stable;
- shared tokens 9/9, constants/API contracts 18/18, generated adapters 7/7 in
  an isolated LF-neutral copy;
- Python backend compile, Terraform recursive format check, Terraform validate,
  and `git diff --check` passed;
- provider lockfile remained unchanged at SHA-256
  `4481E01E8C1DC7FCC5C0204A4EA19CBB8853C33152A65EBDB0D9C99A68009AA2`.

No package, production AWS baseline, saved state-backed plan, apply, deployment,
Web/Mobile change, login, data write, Start, Complete, Calendar, Stripe,
notification, Cognito, DNS, or tenant mutation has occurred at this checkpoint.
ROUTE-GATE-A remains blocked pending exact package and plan evidence and
Matthew's separate approval.
