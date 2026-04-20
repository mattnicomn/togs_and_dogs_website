output "api_endpoint" {
  value       = module.api.api_endpoint
  description = "The direct API Gateway endpoint"
}

output "frontend_cloudfront_domain" {
  value       = module.frontend_hosting.cloudfront_domain_name
  description = "The CloudFront domain name for the frontend"
}

output "frontend_s3_bucket" {
  value       = module.frontend_hosting.s3_bucket_name
  description = "The S3 bucket name for frontend assets"
}

output "acm_validation_options" {
  value       = module.frontend_hosting.acm_certificate_validation_options
  description = "DNS validation records required for the HTTPS certificate"
}

output "cognito_user_pool_id" {
  value = module.auth.user_pool_id
}

output "cognito_client_id" {
  value = module.auth.client_id
}

output "cognito_region" {
  value = var.aws_region
}
