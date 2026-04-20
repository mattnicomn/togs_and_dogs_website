resource "aws_secretsmanager_secret" "google_client_creds" {
  name        = "${var.name_prefix}/google/client-creds"
  description = "Google OAuth Client ID and Secret (Manual Setup)"
  tags        = var.tags
}

resource "aws_secretsmanager_secret" "google_user_tokens" {
  name        = "${var.name_prefix}/google/user-tokens"
  description = "Google OAuth Tokens (Refresh Token)"
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "google_user_tokens_init" {
  secret_id     = aws_secretsmanager_secret.google_user_tokens.id
  secret_string = "{}"

  # Ignore changes to secret_string because Lambda will update it externally
  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "app_secrets" {
  name        = "${var.name_prefix}/app-secrets"
  description = "General application secrets"
  tags        = var.tags
}
