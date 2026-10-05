# Deferred: Platform-Preview / Tenant-Onboarding Orchestrator (Preview V1)

**Status: IMPLEMENTED but NOT DEPLOYED. Not part of the active `infra/prod` /
`modules/api` Terraform graph.**

## What this is
The Preview-Only V1 Platform Admin tenant-onboarding orchestrator: a dedicated
read-only Lambda (`platform_preview`) with a least-privilege IAM role
(`GetItem` + `Scan` only), two Lambda invoke permissions, and two API Gateway
routes — `POST /platform/onboarding/validate` and `POST /platform/onboarding/preview`.
It provides validation, conflict detection, metadata preview, and checklist
generation with no write/apply/create capability.

## Why it is deferred here
This infrastructure was committed but intentionally never deployed. Left active,
it contaminated unrelated production `terraform plan` output (it planned to
create the preview Lambda, its IAM role/policy/attachments, the invoke
permissions, and the onboarding API routes). The OPS-3A.1D production-root
hygiene correction removed it from the active graph so ordinary production plans
contain only approved, currently-deployed infrastructure. No infrastructure was
changed by this correction.

## Original active locations (before this correction)
- `infra/prod/platform_preview_lambda.tf` (this directory) — the preview Lambda
  and its two `aws_lambda_permission` resources.
- `infra/prod/platform_preview_iam.tf` (this directory) — the dedicated
  read-only IAM role, policy, and attachments.
- `infra/prod/main.tf` → `module "api"` input
  `platform_preview_handler_invoke_arn = aws_lambda_function.platform_preview.invoke_arn`
  (removed from the active root).
- `modules/api/main.tf` — the `platform_onboarding`, `platform_onboarding_validate`,
  and `platform_onboarding_preview` resources/methods/integrations, their three
  `cors_resources` entries, the two deployment `depends_on` entries, and the
  `platform_preview_handler_invoke_arn` entry in
  `local.api_integration_target_references` (all removed).
- `modules/api/variables.tf` → `variable "platform_preview_handler_invoke_arn"`
  (removed).
- `modules/api/deployment-semantics.tf.json` — the three platform_onboarding
  resources, two methods, two integrations, and three CORS resource keys
  (all removed, keeping the semantic fingerprint internally consistent).

## Preserved and unchanged
- The deployed main `platform` Lambda and its control-plane routes
  (`/platform/tenants`, `/platform/tenants/{company_id}`, `/platform/audit`) are
  unrelated to the preview feature and are untouched.
- The backend handler (`src/backend/handlers/platform_onboarding_handler.py`),
  shared commons, web UI, and tests remain on `main`.

## Activation (requires explicit Matthew approval)
Activation is a single, reviewed, plan-visible release that must atomically
restore ALL of the removed parts together:
1. Move `platform_preview_lambda.tf` + `platform_preview_iam.tf` back into
   `infra/prod/`.
2. Re-add the `module "api"` input `platform_preview_handler_invoke_arn`.
3. Re-introduce in `modules/api`: the three onboarding resources, two methods,
   two integrations, the three CORS keys, the two deployment `depends_on`
   entries, the `platform_preview_handler_invoke_arn` variable, and the local
   target-reference entry.
4. Re-add the matching entries to `deployment-semantics.tf.json` (resources,
   methods, integrations, CORS keys) so the fingerprint matches the live graph.
5. Produce a plan reviewed under the normal plan/apply (Gate A/Gate B) discipline.

Do not activate without explicit approval. Full source is preserved in Git; no
local-filesystem copying is required to reactivate.
