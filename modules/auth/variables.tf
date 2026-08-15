variable "name_prefix" {
  type        = string
  description = "Prefix for resource naming"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to resources"
  default     = {}
}

variable "custom_email_sender_lambda_arn" {
  type        = string
  description = "Optional dedicated Cognito Custom Email Sender Lambda ARN. Must be set with custom_email_sender_kms_key_arn."
  default     = null
  nullable    = true

  validation {
    condition     = var.custom_email_sender_lambda_arn == null || can(regex("^arn:[^:]+:lambda:[^:]+:[0-9]{12}:function:.+$", var.custom_email_sender_lambda_arn))
    error_message = "custom_email_sender_lambda_arn must be null or a Lambda function ARN."
  }
}

variable "custom_email_sender_kms_key_arn" {
  type        = string
  description = "Optional symmetric KMS key ARN for Cognito Custom Email Sender envelopes. Must be set with custom_email_sender_lambda_arn."
  default     = null
  nullable    = true

  validation {
    condition     = var.custom_email_sender_kms_key_arn == null || can(regex("^arn:[^:]+:kms:[^:]+:[0-9]{12}:key/.+$", var.custom_email_sender_kms_key_arn))
    error_message = "custom_email_sender_kms_key_arn must be null or a KMS key ARN."
  }
}
