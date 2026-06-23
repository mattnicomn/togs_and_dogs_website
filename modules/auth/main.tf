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

  schema {
    name                = "company_id"
    attribute_data_type = "String"
    mutable             = true
    required            = false

    string_attribute_constraints {
      min_length = 1
      max_length = 64
    }
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
  supported_identity_providers         = ["COGNITO"]

  read_attributes = [
    "email",
    "email_verified",
    "family_name",
    "given_name",
    "name",
    "phone_number",
    "phone_number_verified",
    "middle_name",
    "nickname",
    "preferred_username",
    "picture",
    "website",
    "gender",
    "locale",
    "zoneinfo",
    "updated_at",
    "custom:company_id"
  ]

  write_attributes = [
    "email",
    "family_name",
    "given_name",
    "name",
    "phone_number",
    "middle_name",
    "nickname",
    "preferred_username",
    "picture",
    "website",
    "gender",
    "locale",
    "zoneinfo",
    "updated_at"
  ]
}

resource "aws_cognito_user_pool_domain" "admin_domain" {
  domain       = "${var.name_prefix}-admin"
  user_pool_id = aws_cognito_user_pool.admin.id
}

resource "aws_cognito_user_group" "platform_admin" {
  name         = "platform_admin"
  user_pool_id = aws_cognito_user_pool.admin.id
  description  = "Platform Administrator group for global management console access"
}



