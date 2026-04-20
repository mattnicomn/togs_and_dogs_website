output "user_pool_id" {
  value       = aws_cognito_user_pool.admin.id
  description = "ID of the Cognito User Pool"
}

output "user_pool_arn" {
  value       = aws_cognito_user_pool.admin.arn
  description = "ARN of the Cognito User Pool"
}

output "client_id" {
  value       = aws_cognito_user_pool_client.admin_client.id
  description = "ID of the Cognito User Pool Client"
}
