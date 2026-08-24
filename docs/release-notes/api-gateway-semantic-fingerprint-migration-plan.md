# API Gateway Semantic Fingerprint Migration Plan

**Date:** 2026-08-24

**Status:** Saved plan prepared / not applied / ready for Matthew approval

## Controlled release boundary

The semantic-fingerprint implementation reviewed at `8d6e38b4488cf8eb4a39d8f4b069aa0d5367875d` is integrated into `main` at `b6e988b`. Production was not built from `main`. The dedicated branch `release/api-semantic-fingerprint-migration-rc` starts from deployed E3A infrastructure baseline `732e48b930f6fd9aac958351c4ac7823c14cf3e0`; release evidence identifies that commit as the source of live API deployment `886zij`, and its `modules/api` and `infra/prod` trees are byte-identical to the later Lambda-only DOMAIN-1 candidate.

Plan-source commit `cf243a2311a7e188f2346c344a771d07ef903046` contains only:

- the reviewed canonical fingerprint module and eight focused tests;
- a production-baseline semantic manifest;
- the API deployment trigger replacement and complete dependency ordering;
- the safe fingerprint output; and
- the reviewed static validator.

The module, tests, and validator are blob-identical to the reviewed commit. The production-baseline manifest intentionally covers 50 resources, 52 non-CORS methods, 52 integrations, 44 CORS resources, one Cognito authorizer, and two gateway responses. It excludes the three resources, two methods, two integrations, and three CORS resources belonging to the later undeployed onboarding-preview work on `main`.

No backend runtime, Lambda package, Web, Mobile, shared contract, onboarding, Cognito, IAM, DynamoDB, budget, DNS, Stripe, Calendar, notification, tenant, or unrelated Terraform configuration is included.

## Validation

- Terraform 1.15.8 recursive format check: pass;
- production-root `terraform validate`: pass;
- provider-independent fingerprint tests: 8/8;
- static source/manifest validator: pass at 50 resources, 52 methods, 52 integrations, 44 CORS resources, and two gateway responses, including E3A coverage;
- representative baseline backend regressions: 58/58;
- baseline shared/API validator: 18/18;
- Python compile and `git diff --check`: pass;
- provider lockfile SHA-256 remained `4481E01E8C1DC7FCC5C0204A4EA19CBB8853C33152A65EBDB0D9C99A68009AA2`.

## Sanitized AWS and state evidence

- profile: `usmissionhero-website-prod`;
- account: `********2897`;
- region: `us-east-1`;
- backend: encrypted S3 object `prod/terraform.tfstate` in the established production state bucket, using the established lock table;
- workspace: `default`;
- state serial at plan generation: `508`;
- lineage: `7235fddd...8955`;
- providers: AWS 5.100.0 and archive 2.7.1.

## Saved plan

- path: `infra/prod/api-semantic-fingerprint-migration-20260824.tfplan`;
- SHA-256: `9629B084680E0E519B9C7F0CEE153514F99F68BA89961DA9CBEBDA6C105D99FA`;
- Terraform plan timestamp: `2026-08-24T20:27:11Z`;
- saved-artifact timestamp: `2026-08-24T20:27:39Z`;
- refresh: enabled;
- state lock: enabled;
- summary: exactly **1 add, 1 change, 1 destroy**.

| Address | Action | Sanitized evidence |
|---------|--------|--------------------|
| `module.api.aws_api_gateway_deployment.main` | replace, create before destroy | `replace_paths` is exactly `triggers`; REST API ID is unchanged; the legacy and semantic values are distinct SHA-1 digests. Replacement-only computed fields become unknown, and the prior empty deployment description normalizes to absent; neither is an additional action or replacement cause. |
| `module.api.aws_api_gateway_stage.main` | in-place update | The only changed top-level field is `deployment_id`. Stage name, REST API ID, variables, access logging, cache settings, tracing, and method settings are unchanged. |

There are zero Lambda changes and zero API resource, method, integration, authorizer, method-response, integration-response, gateway-response, or method-settings changes. No IAM, DynamoDB, Cognito, environment, budget, DNS, CDN/certificate, Stripe, Calendar, notification, tenant, or other drift appears.

## Read-only live API baseline

The live stage remains `prod` on documented deployment `886zij`: 51 paths including root, 101 declared methods, 96 integrations, one Cognito authorizer, 48 authorizer assignments, zero stage variables, cache disabled, and tracing disabled. The existing deterministic pre-deployment comparison fingerprints are:

- topology: `FF60E97C8ABF6F0E80484C5C9800590C302C75D77B1BD0462191B9182AAB3BCF`;
- authorizer: `FEB3878440E613AB8F0508B4C6F042592096722567726856E4A57BCD0DE661B6`;
- stage configuration excluding `deployment_id`: `18981B28BCE3526D61C2F12F425D2739D6B07F04B2F8964A554D80C8ADA6E5D3`.

Post-deployment verification, if separately approved, must recapture those three canonical comparisons and require equality. No API Gateway modification occurred during this capture.

## Approval, rollback, and remaining blocks

This plan has not been applied. Matthew's separate approval is required before any production action. ROUTE-GATE-A and B1A remain blocked until this migration is approved, applied, and verified. The prior DOMAIN-1 plan `route-gate-a-b1a-route-20260824.tfplan` is permanently rejected and must never be applied.

Rollback is a separately reviewed forward Terraform deployment restoring the prior trigger implementation only if post-deployment verification requires it. Manual state edits, `state rm`, import, targeting, and direct API deployment manipulation are not rollback mechanisms.

A Stripe test API credential and test webhook-signing credential exposure remain recorded without values. Rotation was not performed and remains separately approval-gated; Stripe remains sandbox/test only.
