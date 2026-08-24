# API Gateway Semantic Fingerprint Line-Ending Remediation

**Date:** 2026-08-24

**Status:** Locally validated / ready for independent review / not deployed / no production plan created

## Failed INFRA-GATE-A record

Matthew explicitly approved applying the dedicated migration artifact `infra/prod/api-semantic-fingerprint-migration-20260824.tfplan`, SHA-256 `9629B084680E0E519B9C7F0CEE153514F99F68BA89961DA9CBEBDA6C105D99FA`. Terraform stopped before any managed AWS resource changed. The exact plan is permanently invalid and must never be retried or applied.

Production remains on API Gateway deployment `886zij`, and stage `prod` still points to `886zij`. API topology, authorizer configuration, and all 13 Lambda code/configuration fingerprints are unchanged. Terraform state advanced from serial 508 to 509 with the same lineage. A canonical comparison of all 250 managed resources and all outputs found state 508 and 509 identical. Serial 509 is authoritative; it must not be decremented or manually edited, and any future production plan must start from serial 509.

ROUTE-GATE-A, DOMAIN-1, and B1A remain blocked. No retry or new production plan is authorized. A revised saved plan requires a newly reviewed dedicated release candidate and separate Matthew approval.

## Exact root cause

The failed release-candidate expression at `modules/api/main.tf:1335` was:

```hcl
api_deployment_semantics = jsondecode(file("${path.module}/deployment-semantics.json"))
```

The expression did not hash file bytes or validate a checksum. `file()` returned the manifest as a raw string; `jsondecode()` then parsed that string. Terraform saved the filesystem-function result during planning and checked it during apply. The plan source had LF bytes, while the Windows apply checkout supplied the equivalent file with CRLF bytes under repository-wide `core.autocrlf=true`. The raw `file()` result therefore differed even though `jsondecode()` produced the same object, and Terraform rejected the inconsistent function result before creating the replacement API deployment.

The complete deployment path was raw external file bytes → `file()` string → `jsondecode()` object → URI/authorizer reference resolution → typed canonical fingerprint module → `sha1(jsonencode(canonical semantics))` → `aws_api_gateway_deployment.main.triggers.redeployment`. The only production-path raw-byte dependency was the external `file()` call. No `filebase64`, `filesha1`, `filesha256`, `sha1(file(...))`, `sha256(file(...))`, or raw-manifest comparison controlled the deployment.

## LF/CRLF evidence

At authoritative starting commit `91115b3652d2931bc6d92d302e368f677f7f7b83`, Git stored the 1,000-line manifest as LF while the Windows checkout was CRLF. The committed Git blob was `a044096f3820d392d16e2523d42c7c78b4b4af96`, the equivalent unfiltered CRLF byte blob was `eea05f2bad06ea12e9360a2cb2c34d2f34080e5d`, and the Git-filtered Windows content matched the committed blob. Parsing the LF, CRLF, and compact-whitespace representations produced equal semantic objects; the new native configuration preserves the exact old object. Their independent canonical parsed-object SHA-1 was `9e2e0bcab8194597ba5a1000fb640ed641dd9888`.

## Remediation design

The semantic object is now declared directly in Terraform-native JSON configuration at `modules/api/deployment-semantics.tf.json`. Terraform loads that file as configuration and embeds it in saved plans; there is no external filesystem function result to re-evaluate at apply. The deployment fingerprint still depends only on the parsed object and the existing typed canonicalizer. `modules/api/main.tf` no longer calls `file()` for the manifest.

The narrow `.gitattributes` rule `modules/api/deployment-semantics.tf.json text eol=lf` provides defense in depth without rewriting unrelated repository files. Correctness does not depend on the rule: provider-free Windows plans created from LF, CRLF, and compact native JSON configuration all produced semantic fingerprint `29e700b0e44acb7dfb7b24b11116a74e91a2a110`.

## Regression coverage and validation

- Terraform semantic fingerprint tests: 10/10. The original eight normalization/change-detection cases remain, and LF plus CRLF/whitespace equivalence cases were added.
- Windows provider-free saved-plan regression: LF, CRLF, and compact configuration produced the same fingerprint; each plan embedded `deployment-semantics.tf.json`; the saved LF plan remained readable after the working configuration changed. No apply is used by this test.
- Static source/config validator: 53 resources, 54 methods, 54 integrations, 47 CORS resources, and two gateway responses; E3A coverage pass; no production-path raw manifest reader; LF/CRLF/whitespace equality pass.
- `terraform fmt -check -recursive`: pass.
- production-root `terraform validate`: pass without planning, refresh, or AWS access.
- tenant-route plus E3A backend regressions: 38/38.
- disabled-tenant and Platform Admin boundary regressions: 34/34.
- shared constants/API paths: 24/24.
- shared contract adapters: 9/9 in a temporary `core.autocrlf=false` clone. The known direct-Windows-checkout line-ending false negative remains unrelated and unchanged.
- Python compile and `git diff --check`: pass.

No production plan, apply, refresh, target, state edit, deployment, Cognito/DNS/data write, Start/Complete invocation, Mobile build/distribution, or secret operation occurred during remediation.

## Revised release composition

After independent review, compose a new dedicated migration RC from exact deployed infrastructure baseline `732e48b930f6fd9aac958351c4ac7823c14cf3e0`. Include the reviewed semantic fingerprint implementation, the production-baseline manifest, and this line-ending-stability remediation only. Exclude DOMAIN-1 runtime and unrelated `main` work. Generate a new saved production plan against authoritative state serial 509 only after that RC is reviewed; the plan then requires separate Matthew approval. The final RC and production plan were intentionally not created in this work.

## Security boundary

Sanitized continuity remains unchanged: exposure of a Stripe test API credential and a Stripe test webhook-signing credential was identified. No value was read, displayed, searched, reused, or recorded here. Rotation was not performed, remains separately approval-gated, and Stripe remains test-mode only.
