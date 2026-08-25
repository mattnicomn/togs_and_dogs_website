# API Gateway Semantic Fingerprint Migration V2 Deployment

**Date:** 2026-08-24

**Status:** INFRA-GATE-A v2 COMPLETE / READY FOR DOMAIN-1 RC REBUILD PLANNING / DOMAIN-1 AND B1A NOT DEPLOYED

## Approval and exact artifact

Matthew explicitly approved only the verified INFRA-GATE-A v2 production Terraform plan. The apply used migration RC `release/api-semantic-fingerprint-migration-v2-rc` at `02e5bfda9310e7c80884b34f9c2d61ebf0d9b8bb`, whose plan-source is `6f130fb4ba6d07b457a0466d8ee1f301dd6ba2da`.

- saved plan: `infra/prod/api-semantic-fingerprint-migration-v2-20260824.tfplan`;
- saved-plan SHA-256: `519E3EE19BE40A9EE790D00736DD08857B312FE6B83EF7D5D6B265F3AAD86004`;
- Terraform: `1.14.8`;
- providers: AWS `5.100.0`, archive `2.7.1`;
- workspace: `default`;
- AWS account: `********2897` in `us-east-1`;
- state: serial `509` before apply, serial `510` after apply, unchanged lineage `7235fddd...8955`.

The saved plan was reconfirmed immediately before apply as exactly one create-before-destroy API deployment replacement caused only by `triggers`, plus one in-place stage update changing only `deployment_id`. It contained zero Lambda, API resource/method/integration/authorizer, IAM, data, Cognito, DNS, Web, Mobile, Stripe, Calendar, notification, or tenant changes.

## Apply result

The exact saved-plan apply ran once from `2026-08-25T00:27:41.3307060Z` through `2026-08-25T00:27:46.9727543Z` and exited `0`.

Terraform reported exactly:

> Apply complete! Resources: 1 added, 1 changed, 1 destroyed.

The new immutable API deployment is `atxpw3`. Stage `prod` now points to `atxpw3`; the previous deployment `886zij` was removed after the stage transition. This is the intended `create_before_destroy` lifecycle.

## Semantic and Lambda verification

The same live inventory used for approval remained 51 paths including root, 96 methods, 96 integrations, one authorizer, and 48 authorizer assignments. Canonical before/after evidence is equal:

- topology SHA-256: `B8EB844C189B2AA6B50595728E66C515EECCB188429082F4F968027BAF0FA31E`;
- authorizers plus assignments SHA-256: `59B9A6185D4ADA5AA10DB1B54897DD3932A4F6B1DF1131AEDE09E0CF70C95601`;
- stage configuration excluding `deployment_id` and timestamps SHA-256: `126AE7BE42BA0872D45F8158FA49172CABCDF5A0CB3DF3E05FED1EB605F8B951`.

Stage variables and method settings remain empty. Cache, tracing, and access logging remain disabled.

All 13 production Lambdas remain `Active` / `Successful`. Every `CodeSha256` and configuration fingerprint is exactly equal to the pre-apply baseline. The sanitized aggregate Lambda baseline SHA-256 remains `0240C7A1B37604AD9DDDF8BC65349992231A3D3D22E2EE49BCBEEA9210B011D4`.

## Non-write smoke and health review

- unauthenticated `GET /admin/requests/safe-nonexistent-id`: `401`, with no integration write;
- `OPTIONS /admin/job/start`: `200` with expected CORS headers;
- `OPTIONS /admin/requests/safe-nonexistent-id`: `200` with expected CORS headers.

No Start, Complete, assignment, request, staff, client, pet, Calendar, Stripe, or notification write was attempted.

The migration-window API metrics recorded three expected smoke requests, one expected 4xx authentication denial, and zero 5xx responses. No integration latency datapoint was expected because the probes were an authorizer denial and mock OPTIONS responses. Twelve existing Lambda log groups contained zero matching error, exception, timeout, or import/init events; `togs-and-dogs-prod-ses-feedback` has no CloudWatch log group. All 13 functions nevertheless remained `Active` / `Successful` with unchanged code and configuration fingerprints. API execution logging remains disabled, consistent with the unchanged stage configuration.

## Result and next boundary

The one-time, line-ending-safe Terraform-native semantic deployment trigger is now active in production. Both previous failed plans remain permanently invalid and must never be retried.

DOMAIN-1 still requires a rebuilt baseline-derived RC and a fresh separately reviewed production plan. The expected steady-state Terraform topology for that later release is `0 add / 13 change / 0 destroy`, with zero API deployment or stage churn; that expectation must be proven by the new plan. B1A remains blocked until separately approved DOMAIN-1 backend/Web deployment and independent login-only isolation validation. Stripe test-secret rotation remains a separate approval-gated action.
