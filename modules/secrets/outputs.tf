output "google_client_creds_arn" {
  value       = aws_secretsmanager_secret.google_client_creds.arn
  description = "ARN of the Google Client credentials secret"
}

output "google_user_tokens_arn" {
  value       = aws_secretsmanager_secret.google_user_tokens.arn
  description = "ARN of the Google User tokens secret"
}

output "app_secrets_arn" {
  value       = aws_secretsmanager_secret.app_secrets.arn
  description = "ARN of the general application secret"
}
