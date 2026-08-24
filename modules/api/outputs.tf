output "api_endpoint" {
  value       = aws_api_gateway_stage.main.invoke_url
  description = "The execution URL of the API Gateway stage"
}

output "execution_arn" {
  value       = aws_api_gateway_rest_api.main.execution_arn
  description = "Execution ARN used to scope Lambda invoke permissions"
}

output "deployment_fingerprint" {
  value       = module.deployment_fingerprint.sha1
  description = "Deterministic semantic fingerprint used to trigger API Gateway deployments"
}
