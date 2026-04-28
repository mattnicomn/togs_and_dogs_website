variable "name_prefix" {
  type        = string
  description = "Prefix for resource naming"
}

variable "data_table_arn" {
  type        = string
  description = "ARN of the DynamoDB table"
}

variable "sns_topic_arns" {
  type        = list(string)
  description = "List of SNS topic ARNs for Step Functions to publish to"
}

variable "sfn_arn" {
  description = "ARN of the Step Functions state machine"
  type        = string
}

variable "google_client_creds_arn" {
  description = "ARN of the Google Client credentials secret"
  type        = string
}

variable "google_user_tokens_arn" {
  description = "ARN of the Google User tokens secret"
  type        = string
}

variable "user_pool_arn" {
  type        = string
  description = "ARN of the Cognito User Pool"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to resources"
  default     = {}
}

