# API Gateway Semantic Fingerprint Migration Plan

**Date:** 2026-08-24

**Status:** Apply failed before managed-resource change / saved plan permanently invalid / superseded by line-ending remediation / no retry authorized

## Failed controlled release boundary

The semantic-fingerprint implementation reviewed at `8d6e38b4488cf8eb4a39d8f4b069aa0d5367875d` was integrated into `main`. Production was not built from `main`. The dedicated branch `release/api-semantic-fingerprint-migration-rc` started from deployed E3A infrastructure baseline `732e48b930f6fd9aac958351c4ac7823c14cf3e0`; release evidence identifies that commit as the source of live API deployment `886zij`, and its `modules/api` and `infra/prod` trees were byte-identical to the later Lambda-only DOMAIN-1 candidate.

Matthew explicitly approved applying the exact saved plan documented below. Terraform stopped before any managed AWS resource changed. The plan is now permanently invalid and must never be retried or applied.

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

## Permanently invalid saved plan

- path: `infra/prod/api-semantic-fingerprint-migration-20260824.tfplan`;
- SHA-256: `9629B084680E0E519B9C7F0CEE153514F99F68BA89961DA9CBEBDA6C105D99FA`;
- Terraform plan timestamp: `2026-08-24T20:27:11Z`;
- saved-artifact timestamp: `2026-08-24T20:27:39Z`;
- refresh: enabled;
- state lock: enabled;
- planned summary: exactly **1 add, 1 change, 1 destroy**; none of those managed-resource actions completed.

| Address | Action | Sanitized evidence |
|---------|--------|--------------------|
| `module.api.aws_api_gateway_deployment.main` | replace, create before destroy | `replace_paths` is exactly `triggers`; REST API ID is unchanged; the legacy and semantic values are distinct SHA-1 digests. Replacement-only computed fields become unknown, and the prior empty deployment description normalizes to absent; neither is an additional action or replacement cause. |
| `module.api.aws_api_gateway_stage.main` | in-place update | The only changed top-level field is `deployment_id`. Stage name, REST API ID, variables, access logging, cache settings, tracing, and method settings are unchanged. |

There are zero Lambda changes and zero API resource, method, integration, authorizer, method-response, integration-response, gateway-response, or method-settings changes. No IAM, DynamoDB, Cognito, environment, budget, DNS, CDN/certificate, Stripe, Calendar, notification, tenant, or other drift appears.

## Failed-apply result and state evidence

The exact failing expression on the release candidate was `api_deployment_semantics = jsondecode(file("${path.module}/deployment-semantics.json"))`. `file()` supplied a raw manifest string. Terraform recorded its LF value in the saved plan, then saw equivalent CRLF bytes in the Windows apply checkout. Although `jsondecode()` produced the same semantic object, the filesystem-function value was not byte-identical, so Terraform rejected the inconsistency before creating the replacement deployment.

Production remains unchanged:

- API Gateway deployment: `886zij`;
- stage `prod` → `886zij`;
- API topology and authorizer fingerprints unchanged;
- all 13 Lambda code/configuration fingerprints unchanged.

Terraform state advanced from serial 508 to 509 with unchanged lineage. Read-only canonical comparison found the same 250 managed resources and outputs in both state representations. State 509 is authoritative; no restoration, decrement, or manual edit is appropriate. Every future production plan must start from state 509.

## Read-only live API baseline

The live stage remains `prod` on documented deployment `886zij`: 51 paths including root, 101 declared methods, 96 integrations, one Cognito authorizer, 48 authorizer assignments, zero stage variables, cache disabled, and tracing disabled. The existing deterministic pre-deployment comparison fingerprints are:

- topology: `FF60E97C8ABF6F0E80484C5C9800590C302C75D77B1BD0462191B9182AAB3BCF`;
- authorizer: `FEB3878440E613AB8F0508B4C6F042592096722567726856E4A57BCD0DE661B6`;
- stage configuration excluding `deployment_id`: `18981B28BCE3526D61C2F12F425D2739D6B07F04B2F8964A554D80C8ADA6E5D3`.

Post-deployment verification, if separately approved, must recapture those three canonical comparisons and require equality. No API Gateway modification occurred during this capture.

## Supersession and remaining blocks

This plan was attempted under Matthew's explicit approval and failed safely before managed-resource change. It is permanently invalid. ROUTE-GATE-A, DOMAIN-1, and B1A remain blocked. The prior DOMAIN-1 plan `route-gate-a-b1a-route-20260824.tfplan` is also permanently rejected and must never be applied.

The line-ending remediation moves the manifest to native Terraform JSON configuration so saved plans embed parsed configuration instead of re-evaluating an external raw `file()` result. Independent review approved that correction for migration-RC planning. Fresh replacement branch `release/api-semantic-fingerprint-migration-v2-rc` starts from deployed baseline `732e48b`, excludes DOMAIN-1/unrelated `main`, and produced exact state-509 plan SHA-256 `519E3EE19BE40A9EE790D00736DD08857B312FE6B83EF7D5D6B265F3AAD86004`. The v2 plan remains unapplied and requires Matthew's separate approval. See `docs/release-notes/api-gateway-semantic-fingerprint-line-ending-remediation.md` and `docs/release-notes/api-gateway-semantic-fingerprint-migration-v2-plan.md`.

Rollback is a separately reviewed forward Terraform deployment restoring the prior trigger implementation only if post-deployment verification requires it. Manual state edits, `state rm`, import, targeting, and direct API deployment manipulation are not rollback mechanisms.

A Stripe test API credential and test webhook-signing credential exposure remain recorded without values. Rotation was not performed and remains separately approval-gated; Stripe remains sandbox/test only.
