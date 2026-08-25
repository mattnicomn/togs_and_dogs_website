# API Gateway Semantic Deployment Fingerprint Infrastructure RC

**Date:** 2026-08-24

**Status:** Semantic deployment fingerprint active in production through completed INFRA-GATE-A v2

> **Outcome:** Matthew approved the corrected exact v2 plan, which applied successfully on 2026-08-25 UTC. Production stage `prod` now points to `atxpw3` on state serial 510 with unchanged API semantics and all 13 Lambda fingerprints. DOMAIN-1 remains separately gated. See `api-gateway-semantic-fingerprint-migration-v2-deployment.md`.

## Release boundary

The reviewed implementation is commit `8d6e38b4488cf8eb4a39d8f4b069aa0d5367875d`, originally prepared on `codex/api-semantic-fingerprint-rc` from authoritative `main` commit `b0a687f086dd25b359992dd599f25e239269f691`. Independent review returned `TRIGGER-FIX APPROVED FOR RELEASE-PLANNING`, and the exact reviewed commit was fast-forwarded into `main`. It remains intentionally separate from `release/domain1-b1a-route-backend-rc` so the API deployment-control migration can be released and verified before a revised DOMAIN-1 production plan is created.

ROUTE-GATE-A remains **BLOCKED / NOT READY**. The existing `route-gate-a-b1a-route-20260824.tfplan` file, SHA-256 `B127670C9229D694711CC428B86AE908FC2ADFB17EC563B4BD3F098F5310E7DF`, is permanently rejected and must never be applied. A fresh saved plan requires successful independent review and separate Matthew approval.

Integration into `main` was not a deployment. A later explicitly approved Terraform apply attempt stopped before managed-resource change; no deployment, AWS resource modification, Cognito/DNS change, production-data write, Mobile build/distribution, or secret rotation occurred. Because Terraform state records the legacy trigger value, a future reviewed migration plan is still expected to contain one transitional API Gateway deployment replacement plus only the stage `deployment_id` update. That expectation is not approval to plan or apply.

## Defect and remediation

`aws_api_gateway_deployment.main.triggers.redeployment` previously hashed `jsonencode` of 81 whole API Gateway provider resource objects. Provider-state normalization of semantically absent optional values (`null` versus `[]`, `{}`, or `""`) therefore changed the SHA-1 and proposed an unnecessary API deployment replacement plus stage `deployment_id` update during a Lambda-package-only candidate.

The trigger now consumes only `module.deployment_fingerprint.sha1`. An explicit manifest records API behavior, and a provider-independent typed Terraform module canonicalizes it before `jsonencode` and SHA-1 calculation. The manifest covers:

- resource parent/path identity;
- authorizer type, identity source, provider reference, and result TTL;
- method resource, HTTP verb, authorization, authorizer reference, API-key requirement, scopes, operation name, request models/parameters, and request-validator reference;
- integration method, type, integration verb, target URI/reference, connection/credential references, request mappings/templates, passthrough, cache semantics, content handling, timeout, and TLS behavior;
- method and integration response status, models, parameters, templates, content handling, and selection pattern;
- the exact CORS resource set plus shared OPTIONS, MOCK integration, method-response, and integration-response behavior;
- gateway-response type, status, parameters, and templates.

Optional maps canonicalize to `{}`, optional sets/lists to sorted `[]`, optional strings to `""`, and booleans/numeric defaults to explicit values. Map keys and semantic component keys are encoded deterministically; unordered collections are sorted. The trigger excludes provider-generated IDs and whole objects, deployment/stage IDs, timestamps, descriptions, Lambda `source_code_hash`, backend ZIP hash, Lambda `last_modified`, and unrelated Lambda configuration.

The deployment retains `create_before_destroy = true`. Its explicit `depends_on` now covers all 54 non-CORS integrations plus the shared CORS integration response and both gateway responses, preserving complete graph ordering after provider-object references were removed.

## Change-detection evidence

The focused provider-free Terraform test suite proves:

- `null` and absent/empty map, set/list, string, boolean, number representations yield the same fingerprint;
- adding a path changes the fingerprint;
- changing an HTTP method changes it;
- changing authorization changes it;
- changing an integration target URI changes it;
- changing a request parameter mapping changes it;
- changing CORS response behavior changes it.

Static validation compares the manifest with every configured API resource, non-CORS method, integration, authorizer, CORS resource, and gateway response, fails closed on uncovered fields, verifies complete deployment dependencies, and confirms E3A semantic coverage for authenticated `POST /admin/job/start` and `GET /admin/requests/{requestId}` including CORS.

Historical E3A commit `e10a98e` added genuine API topology/behavior in `modules/api/main.tf`; the manifest changes for its Start resource/method/integration and exact-request method/integration, so the new fingerprint would have changed. Conversely, deployed baseline `732e48b930f6fd9aac958351c4ac7823c14cf3e0` and DOMAIN-1 backend RC `5e8675ad25c92d05c60e94fa83894bd4ed7632b0` have byte-identical `modules/api` tree `c21fe946c095f7d50372222c1344809b64cc1ad4` and `infra/prod` tree `c5646d22d660098b1ec41e902ed84eb82391b3f9`; backend package metadata is excluded, so that Lambda-only change does not alter the semantic fingerprint.

## Local validation

- semantic fingerprint Terraform tests: 10/10, including LF and CRLF/whitespace semantic equality;
- provider-free Windows saved-plan regression: LF, CRLF, and compact native configuration produced the same fingerprint, embedded the manifest, and preserved saved-plan readability after working bytes changed;
- source/manifest static validator: 53 resources, 54 methods, 54 integrations, 47 CORS resources, 2 gateway responses; E3A coverage pass;
- Terraform recursive format check: pass;
- Terraform production-root configuration validation: pass without plan or state refresh;
- tenant-route plus E3A backend tests: 38/38;
- disabled-tenant and Platform Admin boundary tests: 34/34;
- shared constants/API paths: 24/24;
- shared contract adapters: 9/9 in an isolated line-ending-neutral checkout;
- Python compile: pass;
- Git diff check: pass.

## Security incident boundary

A prior inspection identified exposure of a Stripe test API credential and a Stripe test webhook-signing credential. No credential value is recorded here or in this RC. Rotation was not performed; it requires separate Matthew approval. Stripe remains sandbox/test-mode only.

## Migration attempt and line-ending remediation

Dedicated branch `release/api-semantic-fingerprint-migration-rc` was composed from deployed E3A baseline `732e48b`; its plan-source commit was `cf243a2`. The production-baseline manifest excluded later undeployed onboarding-preview semantics and validated 50 resources, 52 methods, 52 integrations, 44 CORS resources, and two gateway responses. Saved plan `api-semantic-fingerprint-migration-20260824.tfplan`, SHA-256 `9629B084680E0E519B9C7F0CEE153514F99F68BA89961DA9CBEBDA6C105D99FA`, planned exactly one create-before-destroy deployment replacement caused only by `triggers` and one stage update changing only `deployment_id`: 1 add, 1 change, 1 destroy, with zero Lambda/API-topology changes.

Matthew explicitly approved the exact plan, but Terraform stopped before managed-resource change because `jsondecode(file(...))` had an LF raw-string result at plan time and semantically identical CRLF input at apply time. Production remains on API deployment/stage `886zij`; API, authorizer, and all 13 Lambda fingerprints are unchanged. State serial advanced 508 → 509 with unchanged lineage and no canonical managed-resource/output difference. The saved plan is permanently invalid and must never be retried.

Independent review approved the native-configuration correction for migration-RC planning. Fresh baseline-derived RC `release/api-semantic-fingerprint-migration-v2-rc` is pushed at `02e5bfda`; plan-source `6f130fb4` validates production scope 50/52/52/44/2 with zero runtime application delta. State-509 plan SHA-256 `519E3EE19BE40A9EE790D00736DD08857B312FE6B83EF7D5D6B265F3AAD86004` applied successfully after Matthew's explicit approval: exactly 1 add, 1 change, 1 destroy across deployment replacement (`triggers` only) and stage update (`deployment_id` only). Production is now `prod → atxpw3` on state serial 510. See `docs/release-notes/api-gateway-semantic-fingerprint-migration-v2-plan.md` and `docs/release-notes/api-gateway-semantic-fingerprint-migration-v2-deployment.md`.
