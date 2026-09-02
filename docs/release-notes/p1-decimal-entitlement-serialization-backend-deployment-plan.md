# P1 Decimal entitlement serialization backend deployment plan

Status: **EXACT PLAN APPLIED SUCCESSFULLY / DEPLOYMENT HEALTHY / PRODUCTION ACCEPTANCE PASS**

> **2026-09-01 disposition:** Matthew approved the exact saved plan documented
> here and it applied successfully with the reviewed `0 add / 13 change /
> 0 destroy` scope. State advanced from `513` to `516` on the unchanged
> lineage. All 13 Lambdas are `Active / Successful` on the approved package
> hash and API Gateway remains `prod -> atxpw3`. The planning-time no-apply
> statements below remain historical evidence of this document's original
> gate. Exact Decimal-backed decision-log execution subsequently passed; see
> `p1-decimal-entitlement-serialization-production-acceptance.md`.

This record covers generation and review of one brand-new, locked,
refresh-enabled production Terraform saved plan from the reconciled backend RC.
It does not authorize or record an apply.

## Release identity and hygiene

- RC branch: `release/p1-decimal-entitlement-backend-rc`
- RC HEAD at plan generation: `ec618b5734d4b271e7dd4b4aa9eecf318411323c`
- Runtime/test commit: `97cb6ebffe8b727e7a6833988107a40e65ba2105`
- Deployed backend baseline: `46ab28779cc3647ef3664f84ee793cf4a6e8539d`
- The isolated RC worktree and index were clean, and the stash was empty.
- The deployed-baseline-to-RC runtime diff contains exactly
  `src/backend/common/entitlement.py`. The semantic runtime change imports
  `DecimalEncoder` and passes `cls=DecimalEncoder` to the entitlement decision
  log serialization. The remaining RC changes are the focused tests and release
  documentation already committed in the RC.
- No Preview V1 or Ryan scheduling/workflow runtime source is present in the
  deployment delta.

## Rejected historical plan

The following historical plan remains permanently rejected and must not be
applied or reused:

- File: `infra/prod/p1-decimal-entitlement-backend-20260831-state513.tfplan`
- SHA-256: `156F2CCFD4F58815E018A64B647BC44627573E7ED2F5305A1A67C0EF74CBCAB3`

Its hash was reconfirmed before and after new-plan generation. It was not used
as input and was not overwritten.

## Production baseline at plan generation

- Terraform state serial: `513`
- Terraform state lineage: `7235fddd-c101-fe62-7669-7b7b3d858955`
- Managed Lambda resources: `13`
- Lambda health: `13/13` `Active` with `LastUpdateStatus=Successful`
- Deployed Lambda code SHA-256: all 13 reported
  `W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=`
- Production REST API: `a022yxuiue`
- Stage: `prod`
- Stage deployment: `atxpw3`

The production inspections were read-only. No state, Lambda, API, tenant, or
application data was mutated.

## Canonical reconciled package

Terraform packaging uses `data.archive_file.backend_zip` with locked provider
`hashicorp/archive` v2.7.1 and the committed backend cache/bytecode/log/temp
exclusions.

- Python entries: `40`
- Unexpected entries: `0`
- Package/source content mismatches: `0`
- `common/entitlement.py`: `18,784` bytes, `531` CRLF, `0` lone LF
- ZIP size: `139,513` bytes
- ZIP SHA-256: `2BF654E0FE7EB69DD1752410C2BA77D897655D28BD45E07FD822A7289A933925`
- Provider/source-code Base64 SHA-256:
  `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=`
- Sorted entry-content manifest SHA-256:
  `87B4215623916219D8DE115844EB38AE3CD27C44C50549F88590F8B91632B904`

These values matched both before and after the production plan. Container hash
stability is recorded as evidence for this run; the content manifest remains
the cross-environment canonical content identity.

## Terraform validation and saved-plan identity

- Terraform: `v1.14.8` (`windows_amd64`)
- Archive provider: `v2.7.1`
- `terraform fmt -check -recursive`: passed
- `terraform validate`: passed
- API/package semantic fingerprint tests: `10/10`
- Plan mode: new saved plan, input disabled, state locking enabled, refresh
  enabled, production var file passed by path without displaying its contents
- Saved plan:
  `infra/prod/p1-decimal-entitlement-backend-reconciled-20260901-state513.tfplan`
- Saved-plan size: `162,621` bytes
- Saved-plan SHA-256:
  `D20B01FD309DB72C1608E774FA71A1317DB0364A27588FD8CD6569FB2938C022`
- Summary: `0 to add, 13 to change, 0 to destroy`
- Replacements: `0`

The saved plan is ignored local evidence. It is not committed.

## Complete changed-resource review

All 13 non-no-op managed resource records are in-place updates to Lambda
functions that share `backend.zip`. For every row, the changed attributes are
exactly `last_modified` and `source_code_hash`. `last_modified` is provider
computed after the package update; `source_code_hash` changes from the deployed
package hash to the reconciled package hash. No row changes runtime
configuration.

| Resource address | Action | `last_modified` before -> after | `source_code_hash` before -> after | Effect |
| --- | --- | --- | --- | --- |
| `aws_lambda_function.admin` | in-place update | `2026-08-25T16:14:05.000+0000` -> known after apply | `W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=` -> `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=` | shared runtime package only |
| `aws_lambda_function.assign` | in-place update | `2026-08-25T16:13:59.000+0000` -> known after apply | `W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=` -> `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=` | shared runtime package only |
| `aws_lambda_function.cancellation` | in-place update | `2026-08-25T16:14:10.000+0000` -> known after apply | `W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=` -> `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=` | shared runtime package only |
| `aws_lambda_function.device` | in-place update | `2026-08-25T16:13:47.000+0000` -> known after apply | `W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=` -> `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=` | shared runtime package only |
| `aws_lambda_function.google_auth` | in-place update | `2026-08-25T16:13:41.000+0000` -> known after apply | `W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=` -> `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=` | shared runtime package only |
| `aws_lambda_function.intake` | in-place update | `2026-08-25T16:14:16.000+0000` -> known after apply | `W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=` -> `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=` | shared runtime package only |
| `aws_lambda_function.job` | in-place update | `2026-08-25T16:13:35.000+0000` -> known after apply | `W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=` -> `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=` | shared runtime package only |
| `aws_lambda_function.pet` | in-place update | `2026-08-25T16:13:11.000+0000` -> known after apply | `W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=` -> `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=` | shared runtime package only |
| `aws_lambda_function.platform` | in-place update | `2026-08-25T16:13:53.000+0000` -> known after apply | `W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=` -> `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=` | shared runtime package only |
| `aws_lambda_function.postmark_webhook` | in-place update | `2026-08-25T16:13:29.000+0000` -> known after apply | `W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=` -> `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=` | shared runtime package only |
| `aws_lambda_function.review` | in-place update | `2026-08-25T16:14:22.000+0000` -> known after apply | `W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=` -> `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=` | shared runtime package only |
| `aws_lambda_function.ses_feedback` | in-place update | `2026-08-25T16:13:17.000+0000` -> known after apply | `W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=` -> `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=` | shared runtime package only |
| `aws_lambda_function.stripe_webhook` | in-place update | `2026-08-25T16:13:23.000+0000` -> known after apply | `W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=` -> `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=` | shared runtime package only |

The complete JSON plan contained `444` managed resource-change records: `431`
no-op and the 13 updates above. There were no other non-no-op managed
resources.

## Explicitly unchanged scope

For every changed Lambda, the review compared 21 configuration attributes and
found zero differences: filename, handler, runtime, timeout, memory, environment,
role/IAM, layers, architectures, reserved concurrency, tags/tags_all, KMS source
and runtime keys, VPC configuration, tracing, dead-letter configuration,
ephemeral storage, package type, publish behavior, and image URI.

All `336` API Gateway records were no-op, including:

- REST API and all 50 resources
- all 96 methods and 96 integrations
- all 44 method responses and 44 integration responses
- authorizer and both gateway responses
- `module.api.aws_api_gateway_deployment.main`: no-op, ID `atxpw3` -> `atxpw3`
- `module.api.aws_api_gateway_stage.main`: no-op, `prod` deployment ID
  `atxpw3` -> `atxpw3`

The complete plan therefore contains zero changes to Cognito, DynamoDB, IAM,
Route53, ACM, CloudFront, S3 Web assets, Stripe configuration, KMS, Secrets
Manager, Google configuration, notifications, Mobile infrastructure, tenant
metadata, provisioning resources, API topology, `TENANT_RESOLUTION_MODE`, Lambda
environment variables, or Lambda layers.

Plan classification: **A. EXPECTED PACKAGE-ONLY LAMBDA UPDATE**.

## Regression evidence

- Focused P1: `5/5`
- Entitlement observability: `6/6`
- Entitlement wiring: `20/20`
- Core entitlement enforcement: `9/9`
- Relevant client/booking selection: `15/15` (`2` documented date-stale tests
  deselected)
- Tenant enforcement: `16/16`
- Disabled tenant / Platform Admin: `26/26`
- E3A: `24/24`
- Tenant route/public: `49/49`
- Backend compile/import: `40` files compiled; entitlement and
  `DecimalEncoder` imports passed

The suites emitted existing `datetime.utcnow()` deprecation warnings only; no
test failed. Tests were not changed during this planning task.

## Historical no-apply boundary and next gate

- Terraform apply: **NOT RUN**
- Direct Lambda update/upload: **NOT RUN**
- Production mutations: **ZERO**
- B1A write validation: **NOT RUN**
- Saved plan committed: **NO**
- `backend.zip` committed: **NO**

Matthew must review and explicitly approve the exact new saved-plan filename,
SHA-256, and package-only scope before any apply is permitted.
