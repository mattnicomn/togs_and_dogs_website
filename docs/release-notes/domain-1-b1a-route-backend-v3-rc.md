# DOMAIN-1 / B1A-ROUTE Backend V3 Release Candidate

**Date:** 2026-08-25

**Status:** ROUTE-GATE-A READY FOR MATTHEW APPROVAL / SAVED PLAN NOT APPLIED

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

## Package evidence

The repository-native `archive_file` process ran from the clean plan-source
checkpoint `46ab28779cc3647ef3664f84ee793cf4a6e8539d` and produced ignored artifact
`infra/prod/backend.zip`:

- SHA-256:
  `5BD46E19ACBA6AB418352517C19D4BF62BFEC7263B704136593F2B04369AC558`;
- Lambda Base64 SHA-256:
  `W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=`;
- size: 139,161 bytes;
- manifest: 40 files, exactly matching the 40 eligible files under
  `src/backend` byte-for-byte;
- `common/tenant_route.py` and `handlers/admin_handler.py` are present;
- no `.pytest_cache`, `__pycache__`, `.pyc`, `.pyo`, `.log`, or `.tmp` entry is
  present;
- all 13 `aws_lambda_function` resources reference this same archive path and
  Base64 hash.

The saved-plan stability regression and exact archive/source comparison prove
the package identity without generating a second production plan. Focused E3A
regressions prove the archive retains the deployed Start, request-detail,
occurrence-summary, idempotency, and Complete-compatible behavior.

## Read-only production baseline

SSO/STS was verified for workload account `********2897` and the separate DNS
account `********9673`; the plan used the workload profile in `us-east-1`.
Terraform used workspace `default`, the configured encrypted S3 remote backend,
and its production state lock. The refreshed plan embeds state serial `510`,
lineage `7235fddd-c101-fe62-7669-7b7b3d858955`, and 250 state resource blocks.

All 13 Lambdas were `Active` with `LastUpdateStatus=Successful`. Every function
had the currently deployed E3A code hash
`x+QHZkoXDKHCB3Ap5nUL3r5zbmSOUFZm3j3tCRxmY1o=`. Sanitized configuration
fingerprints were:

| Lambda | Configuration SHA-256 |
|---|---|
| intake | `956A10E4115834C834BF81C1BC27B2EB338688E6CD2CE1AD121893CFBBA7F805` |
| admin | `84B1A6156E5426764DC507B78B3A8DFCC7EE3365C26C155D55B657D77ADB5923` |
| review | `9F1A92CC09CA3DC242FB88AB80765D44DAA8DF1AC0578938F0B6A9269A1D28E2` |
| assign | `80195B58A9C245D56035152A2A1D98C2B6BAA14234F56C090DCD7046ED197601` |
| job | `1B37F2BF4E67C0BCD0E70318C69AA2AD85E05C8DED006D1F8C727BAF01EE93E8` |
| google-auth | `A38C688CB2184E8C49036B2DC06F8A3C453A80C88E0E101446EF8E053EB631F8` |
| pet | `3DD4A6DF214F516E8C4085CE88E97981E5450F734F438128776B272359841EA2` |
| cancellation | `117C27BE31C138CBE927B9C7A5FD75F378D1DDB9BA0EF3790427C6BCFBB321D6` |
| device | `C7227AD2FADC8AFEA319990C97502B69BFE43EB79D38892222E320B551BE9349` |
| ses-feedback | `3E5E4A80C34CE5C40C516C39D92FF213F10BC15A19850139EA5CA578388CE3F0` |
| postmark-webhook | `3FBAC666B15397EE545557DA06D6BE3A12890D04329306169B37F8A74598F841` |
| stripe-webhook | `6FB6567423C440468697F65BED0ABC55C5A0D5057EC39DEAB669296653C96C9D` |
| platform | `00E24095D211B3890B75DABD8BA8976D097144317FDE303A724052D268C37C30` |

The aggregate configuration fingerprint is
`E5AD4DA5585FC7BE1C187E4A82C9EEE1F8EDF002820469C57AF5F25642D74714`.

The live API remained deployment `atxpw3`, stage `prod`, with 51 live paths,
96 total methods, 96 integrations, one authorizer, and 48 authorizer
assignments. The sanitized live fingerprints captured by the current canonical
read-only collector were:

- topology:
  `D5EE951E7F18730BD27DED19018C31C6B4B0D117A6BDB10F96F68DD6D98B4046`;
- authorizer:
  `20A7CE4B7D07E031B6857CE12B3CD7196F5898BD48340435412D781D47FAA621`;
- stage excluding `deployment_id`:
  `640CD9632D16C679E4B76DF8287938AEF284FC67B5E964BE76B9705748ADD413`.

These live topology counts include API Gateway `OPTIONS` methods. The
source-controlled semantic manifest deliberately counts the primary topology
as 50 resources / 52 primary methods / 52 primary integrations / 44 CORS
resources / 2 gateway responses.

## Fresh locked state-510 plan

Exactly one successful refresh-enabled, locked, untargeted production plan was
saved from plan-source SHA `46ab28779cc3647ef3664f84ee793cf4a6e8539d`:

- ignored path:
  `infra/prod/domain1-b1a-route-backend-v3-20260825.tfplan`;
- creation timestamp recorded by Terraform: `2026-08-25T15:31:40Z`;
- saved file timestamp: `2026-08-25T15:32:25.1307263Z`;
- size: 161,302 bytes;
- SHA-256:
  `871EF0EA349BDAACA1C7330CC5A6B547DD788B99BA14828E38EA340D1A597D00`;
- Terraform `1.14.8`, AWS provider `5.100.0`, archive provider `2.7.1`;
- state serial `510`, established lineage
  `7235fddd-c101-fe62-7669-7b7b3d858955`;
- result: **0 add / 13 change / 0 destroy**.

The machine-readable saved-plan audit found 444 resource action records: 431
`no-op` and the following 13 in-place `update` records:

| Address | Action | Changed values |
|---|---|---|
| `aws_lambda_function.admin` | update | `source_code_hash`; computed `last_modified` |
| `aws_lambda_function.assign` | update | `source_code_hash`; computed `last_modified` |
| `aws_lambda_function.cancellation` | update | `source_code_hash`; computed `last_modified` |
| `aws_lambda_function.device` | update | `source_code_hash`; computed `last_modified` |
| `aws_lambda_function.google_auth` | update | `source_code_hash`; computed `last_modified` |
| `aws_lambda_function.intake` | update | `source_code_hash`; computed `last_modified` |
| `aws_lambda_function.job` | update | `source_code_hash`; computed `last_modified` |
| `aws_lambda_function.pet` | update | `source_code_hash`; computed `last_modified` |
| `aws_lambda_function.platform` | update | `source_code_hash`; computed `last_modified` |
| `aws_lambda_function.postmark_webhook` | update | `source_code_hash`; computed `last_modified` |
| `aws_lambda_function.review` | update | `source_code_hash`; computed `last_modified` |
| `aws_lambda_function.ses_feedback` | update | `source_code_hash`; computed `last_modified` |
| `aws_lambda_function.stripe_webhook` | update | `source_code_hash`; computed `last_modified` |

For every row, the code hash changes from the deployed E3A hash to the exact
new archive hash. Role, environment (including sensitive values), runtime,
handler, memory, timeout, VPC, layers, architecture, tracing, concurrency, tags,
ephemeral storage, and all other configuration compare equal. There are no
replacement paths and no non-Lambda non-no-op actions.

All 336 `module.api` action records are `no-op`, explicitly including
`module.api.aws_api_gateway_deployment.main` and
`module.api.aws_api_gateway_stage.main`. All seven Terraform outputs are also
`no-op`. There is no API, IAM, DynamoDB, Cognito, budget, environment, tenant,
Stripe, Calendar, notification, DNS, Route53, ACM, CloudFront, Web, Mobile, or
other drift in the saved plan. The provider lockfile hash is unchanged.

## Rollback and future verification

The rollback code baseline is the common deployed E3A CodeSha256 above. Any
rollback must preserve E3A behavior and the semantic deployment-fingerprint
infrastructure; it must not use a pre-E3A or pre-fingerprint source and requires
its own reviewed plan and Matthew approval.

After separate approval, apply only the exact saved plan and verify all 13
Lambdas return to `Active`/`Successful`, share the new CodeSha256, and retain
their configuration fingerprints. Confirm API deployment `atxpw3`, stage
`prod`, and all API fingerprints remain unchanged. Then execute only read-only
route checks: malformed/unknown `expectedTenantSlug` denied and compatibility
tenant-info preserved. Do not perform B1A login, production data writes,
Start/Complete, or notification/Calendar/Stripe writes.

## Gate decision

All hard-stop conditions were evaluated and none occurred. ROUTE-GATE-A is
ready for Matthew's review and explicit approval of this exact saved plan.
ROUTE-GATE-B remains waiting; B1A-LOGIN is not approved; B1A remains blocked;
Stripe test-secret rotation remains a separate workstream.

No Terraform apply, Lambda deployment, API deployment, Web/Mobile change,
login, production data write, Start, Complete, Calendar, Stripe, notification,
Cognito, DNS, or tenant mutation was performed.

**DO NOT APPLY.**
