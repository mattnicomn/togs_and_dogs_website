# API Gateway Semantic Fingerprint Migration V2 Plan

**Date:** 2026-08-24

**Status:** INFRA-GATE-A ready for Matthew approval / saved plan not applied / DOMAIN-1 and B1A blocked

## Review and release boundary

Independent review returned `LINE-ENDING FIX APPROVED FOR MIGRATION-RC PLANNING`. Fresh branch `release/api-semantic-fingerprint-migration-v2-rc` was created from exact deployed infrastructure baseline `732e48b930f6fd9aac958351c4ac7823c14cf3e0`, the documented source for live API deployment `886zij`. It was not branched from development `main`.

Plan-source commit `6f130fb4ba6d07b457a0466d8ee1f301dd6ba2da` contains only:

- the reviewed provider-independent semantic fingerprint module;
- the production-scoped Terraform-native `deployment-semantics.tf.json`;
- the deployment trigger integration and complete dependency ordering;
- the safe `deployment_fingerprint` output;
- the static validator and ten semantic tests;
- the provider-free saved-plan line-ending stability regression; and
- the narrow manifest-only `.gitattributes` rule.

The exact baseline-to-plan-source diff is eight paths: `.gitattributes`, `modules/api/deployment-fingerprint/main.tf`, `modules/api/deployment-fingerprint/tests/fingerprint.tftest.hcl`, `modules/api/deployment-semantics.tf.json`, `modules/api/main.tf`, `modules/api/outputs.tf`, `scripts/test_api_deployment_manifest_plan_stability.ps1`, and `scripts/validate_api_deployment_fingerprint.py`.

There are zero differences under `src/`, `web/`, `mobile/`, or `shared/`. DOMAIN-1, `tenant_route.py`, expected-tenant handler changes, Web tenant routes, E1, E2, O1/W1, onboarding-preview APIs, and unrelated development-main work are excluded. The provider lockfile is unchanged at SHA-256 `4481E01E8C1DC7FCC5C0204A4EA19CBB8853C33152A65EBDB0D9C99A68009AA2`.

## Production manifest and local validation

The production manifest exactly covers 50 resources, 52 primary methods, 52 primary integrations, 44 CORS resources, one Cognito authorizer, and two gateway responses. It includes E3A authenticated `POST /admin/job/start` and exact-request `GET /admin/requests/{requestId}` and excludes later undeployed onboarding-preview topology.

- `terraform fmt -check -recursive`: pass;
- production-root `terraform validate`: pass;
- semantic fingerprint tests: 10/10;
- static validator: pass at 50/52/52/44/2 with E3A coverage;
- baseline backend/API regressions: 58/58;
- baseline shared/API validator: 18/18;
- Python compile and `git diff --check`: pass;
- provider-free Windows LF/CRLF/compact fingerprint: `3c33e8944154f9fd96e77cd53be92e3cb9f6613d` in all three cases;
- independent canonical parsed-manifest SHA-1: `3a1e00fda3d8ef6b3e0873d13d6bce6017487adf`;
- saved-plan regression confirms the native manifest is embedded and an earlier plan remains readable after working representation changes.

The state-backed production semantic trigger value is `b44b339a3a0a19872c6ca269f678da20a4683615`. It differs from the provider-free test fingerprint because the production fingerprint resolves real integration and authorizer references, while the provider-free test deliberately uses stable synthetic references.

## Sanitized AWS, state, and live baseline

- profile: `usmissionhero-website-prod`;
- account: `********2897`;
- region: `us-east-1`;
- workspace: `default`;
- backend: established encrypted S3 object `prod/terraform.tfstate` with the established lock table;
- state serial: `509`;
- lineage: `7235fddd...8955`;
- Terraform: `1.14.8` on `windows_amd64`;
- providers: AWS `5.100.0`, archive `2.7.1`.

The read-only pre-plan live API capture found deployment `886zij`, stage `prod`, 51 paths including root, 96 declared methods, 96 integrations, one authorizer, and 48 authorizer assignments. The stage has zero variables, cache disabled, tracing disabled, no access-log configuration, and zero method settings. Canonical read-only SHA-256 evidence:

- topology: `B8EB844C189B2AA6B50595728E66C515EECCB188429082F4F968027BAF0FA31E`;
- authorizers plus assignments: `59B9A6185D4ADA5AA10DB1B54897DD3932A4F6B1DF1131AEDE09E0CF70C95601`;
- stage configuration excluding `deploymentId` and timestamps: `126AE7BE42BA0872D45F8158FA49172CABCDF5A0CB3DF3E05FED1EB605F8B951`.

## Fresh state-509 saved plan

- path: `infra/prod/api-semantic-fingerprint-migration-v2-20260824.tfplan`;
- SHA-256: `519E3EE19BE40A9EE790D00736DD08857B312FE6B83EF7D5D6B265F3AAD86004`;
- Terraform plan timestamp: `2026-08-25T00:11:22Z`;
- saved-artifact timestamp: `2026-08-25T00:12:19.867Z`;
- refresh: enabled;
- state lock: enabled;
- embedded state: serial `509`, lineage `7235fddd...8955`;
- summary: exactly **1 add, 1 change, 1 destroy**.

| Address | Action | Complete sanitized review |
|---------|--------|---------------------------|
| `module.api.aws_api_gateway_deployment.main` | replace, create before destroy | Actions are `create,delete`; `replace_paths` is exactly `triggers`; REST API ID is unchanged; legacy trigger `d0007011ffa0627126b2dc691fa93fcfb0eeda33` transitions to semantic trigger `b44b339a3a0a19872c6ca269f678da20a4683615`. Replacement-only computed fields become unknown. The prior empty description normalizes to absent; it is not a replacement cause. |
| `module.api.aws_api_gateway_stage.main` | update in place | The only changed top-level key is `deployment_id`, from live `886zij` to the new computed deployment ID. Stage name and REST API ID are unchanged; variables, access logging, cache, tracing, and method settings compare equal. |

The complete plan contains exactly those two meaningful resource changes. It contains zero Lambda, API resource/path, method, integration, authorizer, CORS, gateway-response, IAM, DynamoDB, Cognito, environment, budget, tenant, Stripe, Calendar, notification, DNS, Route53, ACM, CloudFront, Web, Mobile, or unrelated changes. Post-plan read-only checks reconfirmed state serial 509 and live stage `prod → 886zij`.

## Prior-failure prevention and hard-stop evaluation

The failed v1 design loaded an external manifest through `jsondecode(file(...))`. Terraform recorded the mutable raw filesystem-function result at plan time, then rejected semantically equivalent CRLF bytes at apply. V2 declares the object in Terraform-native JSON configuration. The saved plan archive contains `tfconfig/m-api/deployment-semantics.tf.json`; the semantic object is embedded configuration, not a mutable raw `file()` result. No `jsondecode(file(...))`, raw manifest hash, or deployment-path filesystem dependency exists.

Every enumerated hard-stop condition was evaluated and none is present. The RC is clean, manifest counts are exact, state/workspace/account/lineage are correct, the provider lockfile is unchanged, all tests pass, and only the exact two expected managed addresses change.

## Approval, rollback, and remaining blocks

This plan has not been applied. Matthew must review and explicitly approve this exact plan SHA-256 before any apply. Both previous plans—`api-semantic-fingerprint-migration-20260824.tfplan` and `route-gate-a-b1a-route-20260824.tfplan`—remain permanently invalid and must never be retried.

Rollback remains a separately reviewed and approved forward Terraform migration restoring prior trigger behavior only if required. State decrement, manual state editing, `state rm`, import, targeting, and direct API deployment manipulation are prohibited.

DOMAIN-1 and B1A remain blocked. The Stripe test API credential and test webhook-signing credential exposure remain recorded without values; rotation was not performed and remains separately approval-gated. No secret value was read, displayed, reused, or rotated during this planning work.
