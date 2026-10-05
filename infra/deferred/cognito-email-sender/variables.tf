# Feature-only variable relocated from infra/prod/variables.tf by the OPS-3A.1D
# production-root hygiene correction. It is consumed solely by
# cognito_email_sender.tf (the Cognito Custom Email Sender + Postmark feature),
# which is implemented but intentionally NOT deployed. See README.md in this
# directory. Reactivation (moving this feature back into infra/prod/) is a
# separate, Matthew-approved release.

variable "cognito_email_sender_package_path" {
  type        = string
  description = "Optional local path to the isolated Cognito Custom Email Sender Lambda zip. Build with scripts/build_cognito_email_sender_package.py before planning or applying."
  default     = null
  nullable    = true
}
