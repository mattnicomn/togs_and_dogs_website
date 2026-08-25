# DOMAIN-1 / B1A-ROUTE Backend V2 Release Candidate

**Date:** 2026-08-24

**Status:** ROUTE-GATE-A NOT READY / required tenant-isolation regressions failed / no package or plan generated

## Rebuilt composition

Fresh branch `release/domain1-b1a-route-backend-v2-rc` was created from exact deployed semantic-infrastructure plan source `6f130fb4ba6d07b457a0466d8ee1f301dd6ba2da`. That source is based on deployed E3A backend baseline `732e48b930f6fd9aac958351c4ac7823c14cf3e0` and contains the production-scoped Terraform-native semantic API deployment fingerprint that produced the successfully applied INFRA-GATE-A v2 plan.

Reviewed DOMAIN-1 backend commit `5e8675ad25c92d05c60e94fa83894bd4ed7632b0` was replayed onto that source, producing initial rebuilt composition commit `f3d48f15641b82f8f86b0157fb215ac31a489058`. The pushed blocked-RC documentation checkpoint is `3583b15b7b5907445db8e47dda54baa961895473`.

The exact runtime delta from the deployed E3A baseline remains only:

- `src/backend/common/tenant_route.py`;
- the bounded `expectedTenantSlug` branch in `src/backend/handlers/admin_handler.py`.

The `modules/api` tree is byte-identical to `6f130fb4` at tree `b91d28ef2670279ffe46061a52de1bfef75904c2`. The `infra/prod` tree is also byte-identical at `c5646d22d660098b1ec41e902ed84eb82391b3f9`. No API resource, method, integration, authorizer, CORS, gateway-response, deployment trigger, stage configuration, or other Terraform semantic change was introduced by the DOMAIN-1 replay.

## Validation hard stop

The following required focused suites passed:

- DOMAIN-1 tenant-route security: 14/14;
- deployed E3A Start/occurrence/Complete compatibility: 24/24;
- disabled-tenant plus Platform Admin boundaries: 26/26.

The required tenant-isolation regression selection reported 48 passes and three failures:

- `test_review_handler_same_tenant_approved` returned the pre-existing `TenantDisabled` mock/entitlement result;
- `test_admin_handler_export_filters_by_company` hit the pre-existing incomplete export fixture timestamp error;
- `test_pet_handler_get_same_tenant_succeeds` returned the pre-existing `TenantDisabled` mock/entitlement result.

These same three legacy failure categories were already recorded by the original DOMAIN-1 local release evidence as unrelated entitlement/mock drift. The v2 candidate does not change `review_handler.py`, `pet_handler.py`, or the admin export path. They are nevertheless failures in a required run, and the current gate explicitly defines any failed test as `ROUTE-GATE-A NOT READY`.

## Stopped actions

The release process stopped before full fingerprint/Terraform validation, production AWS baseline capture, `backend.zip` generation, and saved-plan generation. No `.tfplan` was created, substituted, or reused. No apply, AWS mutation, Web deployment, login, fixture creation, Start, Complete, Calendar, Stripe, notification, Cognito, DNS, tenant, or production-data action occurred.

The prior DOMAIN-1 saved plan remains permanently rejected. INFRA-GATE-A v2 remains complete and must not be rolled back. ROUTE-GATE-B Web, ROUTE-GATE-C B1A-LOGIN, the B1A fixture, and B1B/B2/B3 remain unapproved.

## Required next decision

Matthew must decide whether a separately bounded test-harness correction/review is authorized or whether the gate should use a narrower pre-approved tenant-isolation selection. Until that decision and a completely passing required validation run, no DOMAIN-1 backend package or production plan should be created.
