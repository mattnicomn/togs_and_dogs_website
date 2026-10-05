# Deferred: Cognito Custom Email Sender + Postmark

**Status: IMPLEMENTED but NOT DEPLOYED. Not part of the active `infra/prod` Terraform root.**

## What this is
A dedicated Cognito Custom Email Sender Lambda that routes Cognito-originated
password-recovery email through Postmark (approved architecture:
Cognito → Custom Email Sender Lambda → Postmark). The implementation includes a
dedicated Lambda, a customer-managed symmetric KMS key/alias, a least-privilege
IAM role/policy, a dedicated CloudWatch log group, and the Cognito user-pool
`custom_email_sender` wiring.

## Why it is deferred here
This infrastructure was committed to the repo but intentionally never deployed.
Left in the active `infra/prod` root, it contaminated unrelated production
`terraform plan` output (it planned to create the Lambda/KMS/IAM and to modify
the live Cognito user pool). The OPS-3A.1D production-root hygiene correction
relocated it here so ordinary production plans contain only approved,
currently-deployed infrastructure. No infrastructure was changed by the move.

## Original active locations (before relocation)
- `infra/prod/cognito_email_sender.tf` (this directory's `cognito_email_sender.tf`)
- `infra/prod/variables.tf` → `variable "cognito_email_sender_package_path"`
  (now in this directory's `variables.tf`)
- `infra/prod/main.tf` → `module "auth"` inputs
  `custom_email_sender_lambda_arn` and `custom_email_sender_kms_key_arn`
  (now set to `null` in the active root)

## Preserved and unchanged
- The reusable `modules/auth` capability (nullable
  `custom_email_sender_lambda_arn` / `custom_email_sender_kms_key_arn` variables
  and the `dynamic "lambda_config"` block) stays intact. With both inputs `null`,
  the module emits no custom-email config, so the currently-deployed generic
  Cognito email behavior is preserved.
- The application package source (`src/cognito_email_sender/`), its build script
  (`scripts/build_cognito_email_sender_package.py`), and its tests are unchanged
  and remain on `main`.

## Activation (requires explicit Matthew approval)
Activation is a separate, reviewed, plan-visible release that must:
1. Move `cognito_email_sender.tf` (and `variables.tf`) back into `infra/prod/`.
2. Restore the `module "auth"` inputs in `infra/prod/main.tf` to
   `aws_lambda_function.cognito_email_sender.arn` and
   `aws_kms_key.cognito_email_sender.arn`.
3. Build the isolated package before plan/apply.
4. Produce a plan reviewed under the normal plan/apply (Gate A/Gate B) discipline.

Do not activate without explicit approval. Full source is preserved in Git; no
local-filesystem copying is required to reactivate.
