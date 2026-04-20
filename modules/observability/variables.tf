variable "name_prefix" {
  type        = string
  description = "Prefix for resource naming"
}

variable "log_retention_days" {
  type        = number
  description = "Number of days to retain logs"
  default     = 14
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to resources"
  default     = {}
}
