variable "name_prefix" {
  type        = string
  description = "Prefix for resource naming"
}

variable "environment" {
  type        = string
  description = "Deployment environment"
}

variable "intake_handler_invoke_arn" {
  type        = string
  description = "Invoke ARN of the intake Lambda"
}

variable "admin_handler_invoke_arn" {
  type        = string
  description = "Invoke ARN of the admin Lambda"
}

variable "user_pool_arn" {
  type        = string
  description = "ARN of the Cognito User Pool for authorization"
}

variable "review_handler_invoke_arn" {
  type        = string
  description = "Invoke ARN of the review Lambda"
}

variable "assign_handler_invoke_arn" {
  description = "Invocation ARN for the assignment handler"
  type        = string
}

variable "google_auth_handler_invoke_arn" {
  description = "Invocation ARN for the Google Auth handler"
  type        = string
}

variable "pet_handler_invoke_arn" {
  description = "Invocation ARN for the pet handler"
  type        = string
}

variable "cancellation_handler_invoke_arn" {
  description = "Invocation ARN for the cancellation handler"
  type        = string
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to resources"
  default     = {}
}
