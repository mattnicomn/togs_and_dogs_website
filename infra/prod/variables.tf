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
