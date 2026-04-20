variable "name_prefix" {
  type        = string
  description = "Prefix for resource naming"
}

variable "sfn_role_arn" {
  type        = string
  description = "ARN of the IAM role for Step Functions"
}

variable "job_handler_arn" {
  type        = string
  description = "ARN of the job creation Lambda handler"
}

variable "notification_topic_arn" {
  type        = string
  description = "ARN of the SNS topic for notifications"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to resources"
  default     = {}
}
