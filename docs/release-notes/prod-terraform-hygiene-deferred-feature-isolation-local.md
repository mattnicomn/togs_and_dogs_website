# Production Terraform Hygiene — Deferred Feature Isolation (local)

Status: **SOURCE-ONLY CORRECTION — READY FOR REVIEW. NOT APPLIED. NOT DEPLOYED.**
No Terraform command (`init`/`fmt`/`validate`/`test`/`plan`/`apply`) was run, no
AWS call was made, no Terraform state was mutated, and no infrastructure changed.

Starting checkpoint: `main == origin/main == fcfdec2d6be3eea321a2ceb054c70b1f8886e07f`.
This correction is a prerequisite for constructing a clean OPS-3A.1 production RC.

## Why this was needed

Three infrastructure workstreams were committed to the active production Terraform
root but intentionally **never deployed**:
- Cognito Custom Email Sender + Postmark (`67f5639`)
- Platform-preview tenant-onboarding orchestrator (Preview V1) and its
  `/platform/onboarding` API routes (`55da71c`)

Because their declarations sat inside the active `infra/prod` and `modules/api`
graph, every ordinary production `terraform plan` tried to **create** them (and to
modify the live Cognito user pool), contaminating unrelated plans — most recently
the OPS-3A.1D quote-route plan, which showed 60 adds / 15 changes it should not have.

## What this correction does (source-only isolation)

The deferred features were **relocated/removed from the active graph** while their
full implementation is **preserved in Git** for a future, separately-approved
activation. No application/backend/web code was reverted.

### Relocated (git mv, history preserved) to `infra/deferred/`
- `infra/prod/cognito_email_sender.tf` → `infra/deferred/cognito-email-sender/cognito_email_sender.tf`
- `infra/prod/platform_preview_lambda.tf` → `infra/deferred/platform-preview/platform_preview_lambda.tf`
- `infra/prod/platform_preview_iam.tf` → `infra/deferred/platform-preview/platform_preview_iam.tf`
- The feature-only `variable "cognito_email_sender_package_path"` moved from
  `infra/prod/variables.tf` to `infra/deferred/cognito-email-sender/variables.tf`.
- Added `README.md` in each deferred directory documenting the feature, why it is
  deferred, its original active locations, and that activation requires explicit
  Matthew approval and restores the complete resource/wiring/fingerprint set.

### Active-root input cleanup (`infra/prod/main.tf`)
- `module "auth"` now receives `custom_email_sender_lambda_arn = null` and
  `custom_email_sender_kms_key_arn = null`. The reusable `modules/auth`
  null-gated `dynamic "lambda_config"` therefore emits nothing, preserving the
  **currently-deployed generic Cognito email behavior** (removes the spurious
  `aws_cognito_user_pool.admin` plan change).
- Removed the `module "api"` input
  `platform_preview_handler_invoke_arn = aws_lambda_function.platform_preview.invoke_arn`.

### platform_onboarding removed from the active API module (Option B)
- `modules/api/main.tf`: removed the `platform_onboarding`,
  `platform_onboarding_validate`, `platform_onboarding_preview` resources, their
  two POST methods and two AWS_PROXY integrations, their three `cors_resources`
  entries, the two `aws_api_gateway_deployment.main` `depends_on` entries, and the
  `platform_preview_handler_invoke_arn` entry in
  `local.api_integration_target_references`.
- `modules/api/variables.tf`: removed `variable "platform_preview_handler_invoke_arn"`.
- `modules/api/deployment-semantics.tf.json`: atomically removed the three
  platform_onboarding resources, two methods, two integrations, and three CORS
  resource keys so the semantic deployment fingerprint stays internally consistent.
- `modules/api/outputs.tf`: **no change** — it has no platform_onboarding-only
  output (only `api_endpoint`, `execution_arn`, `deployment_fingerprint`).

## What was explicitly preserved (unchanged)

- Reusable `modules/auth` capability (nullable custom-email variables + dynamic
  block) — intact.
- All application/backend/web code (`src/backend/**`, `src/cognito_email_sender/**`,
  `web/**`), scripts, and tests — untouched.
- The deployed **platform control plane** — the main `platform` Lambda, its invoke
  permission, and the `/platform/tenants`, `/platform/tenants/{company_id}`,
  `/platform/audit` routes — untouched.
- The **OPS-3A quote** code and routes — unchanged (all three quote methods remain
  in the manifest; quote mentions in `modules/api/main.tf` unchanged).
- The four **AC-9** Google-auth commits remain on `main` (not touched; they are
  excluded from the deployed artifact separately, not from history).
- No tenant-resolution change; no currently-managed production resource declaration
  removed. All three deferred workstreams were `+ create` only in the rejected plan
  (not in Terraform state), so removing their declarations cannot destroy a managed
  resource.

## Static verification (no Terraform executed)

- `deployment-semantics.tf.json` parses as valid JSON; manifest counts dropped from
  57/57/57/51 to **54 resources / 55 methods / 55 integrations / 48 CORS keys**
  (exactly −3/−2/−2/−3 = the platform_onboarding footprint); **zero** reference
  errors (all parent/resource/authorizer/method/CORS keys resolve); no
  `platform_onboarding` keys and no `platform_preview_handler_invoke_arn` target
  remain.
- No active `infra/prod` reference to `cognito_email_sender`; `module.auth` inputs
  are `null`; `modules/auth` capability present.
- No active `infra/prod` platform_preview Lambda/IAM/permission/input (only
  explanatory comments remain).
- No non-comment `platform_onboarding` lines remain in `modules/api/main.tf`.
- Quote routes intact (3 methods in manifest; 28 quote mentions in `modules/api/main.tf`).
- `git diff --check` (unstaged and staged): clean, rc 0.

## RC portability (for the future clean OPS-3A.1 RC)

- `infra/prod/main.tf`, `infra/prod/variables.tf`, and `modules/api/variables.tf`
  are byte-identical at `cc55e21` and `fcfdec2`, so these hygiene edits apply
  verbatim onto a `cc55e21`-based RC.
- `modules/api/main.tf` and `deployment-semantics.tf.json` differ (they carry the
  OPS-3A.1C quote routes), so the hygiene edits to those two must be applied **after**
  `fcfdec2` in the RC: baseline `cc55e21` → `d29d833` → `a025154` → `fcfdec2` →
  hygiene. The platform_onboarding content being removed exists identically at both
  commits, so the removal applies cleanly once `fcfdec2` is present.

## Expected effect once applied (informational; not applied here)

After this hygiene correction, a normal production plan no longer contains
cognito_email_sender, platform_preview, platform_onboarding, or any Cognito
user-pool change. Combined with the clean OPS-3A.1 RC, the plan reduces to the quote
routes + the shared backend package update across the 13 Lambdas + one API Gateway
deployment refresh.

## Out of scope / deferred

- Activation of any of the three deferred features — each is a separate,
  Matthew-approved release (procedures documented in the deferred READMEs).
- The OPS-3A.1 RC construction, Terraform validate/plan (Gate A), and apply (Gate B).
- No Stripe/payment, tenant-resolution, Ryan/store/OAuth, or OPS-3A.2/3A.3 work.

## Resume point

- Files changed: see the categorized diff (relocations + active-root cleanup +
  platform_onboarding removal + manifest cleanup + deferred docs). No commit made.
- Nothing deployed; no Terraform ran; no state mutated.
- Next: independent review of this hygiene patch; on approval, commit it to `main`,
  then construct the clean OPS-3A.1 RC per the RC portability note.
