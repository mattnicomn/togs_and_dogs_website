resource "aws_cognito_user_pool" "admin" {
  name = "${var.name_prefix}-admin-pool"

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }

  tags = var.tags
}

resource "aws_cognito_user_pool_client" "admin_client" {
  name         = "${var.name_prefix}-admin-client"
  user_pool_id = aws_cognito_user_pool.admin.id

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH"
  ]

  callback_urls = [
    "http://localhost:5173/admin",
    "https://toganddogs.usmissionhero.com/admin"
  ]
  logout_urls = [
    "http://localhost:5173",
    "https://toganddogs.usmissionhero.com"
  ]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code", "implicit"]
  allowed_oauth_scopes                 = ["email", "openid", "profile"]
  supported_identity_providers        = ["COGNITO"]
}

resource "aws_cognito_user_pool_domain" "admin_domain" {
  domain       = "${var.name_prefix}-admin"
  user_pool_id = aws_cognito_user_pool.admin.id
}
