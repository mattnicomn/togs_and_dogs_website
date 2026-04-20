variable "name_prefix" {
  type        = string
  description = "Prefix for resource naming"
}

variable "domain_name" {
  type        = string
  description = "Base domain name (e.g., toganddogs.com)"
}

variable "subdomain" {
  type        = string
  description = "Subdomain for the app (e.g., app)"
  default     = "app"
}

variable "tags" {
  type        = map(string)
  description = "Standard tags for all resources"
  default     = {}
}
