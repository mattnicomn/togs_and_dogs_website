variable "aws_region" {
  type        = string
  description = "Primary AWS region for deployment."
  default     = "us-east-1"
}

variable "aws_profile_workload" {
  type        = string
  description = "SSO profile for the production workload account (358604342897)."
  default     = "usmissionhero-website-prod"
}

variable "aws_profile_dns" {
  type        = string
  description = "SSO profile for the DNS/Sandbox account (253881689673)."
  default     = "website-infra-sandbox"
}

variable "environment" {
  type        = string
  description = "Deployment environment name."
  default     = "prod"
}

variable "project_name" {
  type        = string
  description = "Project name used for resource naming."
  default     = "togs-and-dogs"
}

variable "domain_name" {
  type        = string
  description = "Primary domain for the pet sitting app."
  default     = "usmissionhero.com"
}

variable "app_subdomain" {
  type        = string
  description = "Subdomain for the app under domain_name."
  default     = "toganddogs"
}

# --- Budget & Cost Reporting ---

variable "budget_amount" {
  type        = string
  description = "Monthly budget limit in USD."
  default     = "20"
}

variable "budget_alert_email" {
  type        = string
  description = "Email address for budget threshold alerts."
  default     = "mbn@usmissionhero.com"
}

# --- Release 6I: Postmark Webhook ---

variable "postmark_webhook_secret" {
  type        = string
  description = "Shared secret for authenticating Postmark webhook requests. Set via terraform.tfvars or TF_VAR."
  sensitive   = true
  default     = ""
}

# --- Cognito Custom Email Sender + Postmark ---

variable "cognito_email_sender_package_path" {
  type        = string
  description = "Optional local path to the isolated Cognito Custom Email Sender Lambda zip. Build with scripts/build_cognito_email_sender_package.py before planning or applying."
  default     = null
  nullable    = true
}

# --- Release 12I: Stripe sandbox route and secret wiring ---

variable "stripe_secret_key" {
  type        = string
  description = "Stripe secret API key for creating Checkout Sessions. Set via terraform.tfvars or TF_VAR."
  sensitive   = true
  default     = ""
}

variable "stripe_webhook_secret" {
  type        = string
  description = "Stripe webhook signing secret for verifying webhook requests. Set via terraform.tfvars or TF_VAR."
  sensitive   = true
  default     = ""
}

variable "stripe_price_starter_monthly" {
  type        = string
  description = "Stripe Price ID for Starter Monthly plan."
  default     = ""
}

variable "stripe_price_professional_monthly" {
  type        = string
  description = "Stripe Price ID for Professional Monthly plan."
  default     = ""
}

variable "stripe_price_premium_monthly" {
  type        = string
  description = "Stripe Price ID for Premium Monthly plan."
  default     = ""
}

variable "stripe_success_url_template" {
  type        = string
  description = "Stripe Checkout Session success URL template."
  default     = "https://toganddogs.usmissionhero.com/booking/{request_id}/success?session_id={{CHECKOUT_SESSION_ID}}"
}

variable "stripe_cancel_url_template" {
  type        = string
  description = "Stripe Checkout Session cancel URL template."
  default     = "https://toganddogs.usmissionhero.com/booking/{request_id}/cancel"
}
