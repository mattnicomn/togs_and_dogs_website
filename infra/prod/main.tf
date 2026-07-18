# ------------------------------------------------------------------------------
# 1. SECURITY & IDENTITY
# ------------------------------------------------------------------------------

module "auth" {
  source      = "../../modules/auth"
  name_prefix = local.name_prefix
  tags        = local.common_tags
}

module "secrets" {
  source      = "../../modules/secrets"
  name_prefix = local.name_prefix
  tags        = local.common_tags
}

module "iam" {
  source                  = "../../modules/iam"
  name_prefix             = local.name_prefix
  data_table_arn          = module.data.table_arn
  sns_topic_arns          = [module.notifications.ryan_alerts_topic_arn, module.notifications.staff_coordination_topic_arn]
  sfn_arn                 = module.workflow.sfn_arn
  google_client_creds_arn = module.secrets.google_client_creds_arn
  google_user_tokens_arn  = module.secrets.google_user_tokens_arn
  postmark_token_arn      = module.secrets.postmark_token_arn
  user_pool_arn           = module.auth.user_pool_arn
  tags                    = local.common_tags
}


# ------------------------------------------------------------------------------
# 2. DATA LAYER
# ------------------------------------------------------------------------------

module "data" {
  source      = "../../modules/data"
  name_prefix = local.name_prefix
  tags        = local.common_tags
}

# ------------------------------------------------------------------------------
# 3. NOTIFICATIONS & OBSERVABILITY
# ------------------------------------------------------------------------------

module "notifications" {
  source      = "../../modules/notifications"
  name_prefix = local.name_prefix
  tags        = local.common_tags
}

module "observability" {
  source              = "../../modules/observability"
  name_prefix         = local.name_prefix
  tags                = local.common_tags
  alarm_sns_topic_arn = module.notifications.ryan_alerts_topic_arn
}

# ------------------------------------------------------------------------------
# 4. LAMBDA LOGIC (Python Handlers)
# ------------------------------------------------------------------------------

# Archive code for Lambda
data "archive_file" "backend_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../src/backend"
  output_path = "${path.module}/backend.zip"
  excludes = [
    "**/.pytest_cache/**",
    "**/__pycache__/**",
    "**/*.pyc",
    "**/*.pyo",
    "**/*.log",
    "**/*.tmp"
  ]
}

resource "aws_lambda_function" "intake" {
  filename         = data.archive_file.backend_zip.output_path
  function_name    = "${local.name_prefix}-intake"
  role             = module.iam.lambda_role_arn
  handler          = "handlers.intake_handler.handler"
  source_code_hash = data.archive_file.backend_zip.output_base64sha256
  runtime          = "python3.11"
  memory_size      = 512
  timeout          = 60

  environment {
    variables = merge(
      {
        DATA_TABLE_NAME          = module.data.table_name
        STATE_MACHINE_ARN        = module.workflow.sfn_arn
        GOOGLE_CLIENT_CREDS_NAME = module.secrets.google_client_creds_arn
        GOOGLE_USER_TOKENS_NAME  = module.secrets.google_user_tokens_arn
        JOB_FUNCTION_NAME        = aws_lambda_function.job.function_name
        # Trusted domain-to-tenant mapping for public intake routing (temporary single-tenant bridge)
        PUBLIC_INTAKE_DOMAIN_MAP = jsonencode({
          "a022yxuiue.execute-api.us-east-1.amazonaws.com" = {
            tenant_id             = "tog_and_dogs"
            active                = true
            public_intake_enabled = true
          }
        })
      },
      local.notification_env_vars
    )
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "admin" {
  filename         = data.archive_file.backend_zip.output_path
  function_name    = "${local.name_prefix}-admin"
  role             = module.iam.lambda_role_arn
  handler          = "handlers.admin_handler.handler"
  source_code_hash = data.archive_file.backend_zip.output_base64sha256
  runtime          = "python3.11"
  memory_size      = 512
  timeout          = 60

  environment {
    variables = merge(
      {
        DATA_TABLE_NAME                   = module.data.table_name
        ADMIN_USER_POOL_ID                = module.auth.user_pool_id
        DEFAULT_COMPANY_ID                = "tog_and_dogs"
        GOOGLE_CLIENT_CREDS_NAME          = module.secrets.google_client_creds_arn
        GOOGLE_USER_TOKENS_NAME           = module.secrets.google_user_tokens_arn
        STRIPE_SECRET_KEY                 = var.stripe_secret_key
        STRIPE_ENVIRONMENT                = "sandbox"
        STRIPE_ENV                        = "sandbox"
        STRIPE_PRICE_STARTER_MONTHLY      = var.stripe_price_starter_monthly
        STRIPE_PRICE_PROFESSIONAL_MONTHLY = var.stripe_price_professional_monthly
        STRIPE_PRICE_PREMIUM_MONTHLY      = var.stripe_price_premium_monthly
        STRIPE_SUCCESS_URL_TEMPLATE       = var.stripe_success_url_template
        STRIPE_CANCEL_URL_TEMPLATE        = var.stripe_cancel_url_template
        ENTITLEMENT_ENFORCEMENT_ENABLED   = "true"
      },
      local.notification_env_vars
    )
  }


  tags = local.common_tags
}

resource "aws_lambda_function" "review" {
  filename         = data.archive_file.backend_zip.output_path
  function_name    = "${local.name_prefix}-review"
  role             = module.iam.lambda_role_arn
  handler          = "handlers.review_handler.handler"
  source_code_hash = data.archive_file.backend_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = 60
  memory_size      = 512

  environment {
    variables = merge(
      {
        DATA_TABLE_NAME          = module.data.table_name
        GOOGLE_CLIENT_CREDS_NAME = module.secrets.google_client_creds_arn
        GOOGLE_USER_TOKENS_NAME  = module.secrets.google_user_tokens_arn
        JOB_FUNCTION_NAME        = aws_lambda_function.job.function_name
      },
      local.notification_env_vars
    )
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "assign" {
  filename         = data.archive_file.backend_zip.output_path
  function_name    = "${local.name_prefix}-assign"
  role             = module.iam.lambda_role_arn
  handler          = "handlers.assignment_handler.handler"
  source_code_hash = data.archive_file.backend_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = 60
  memory_size      = 512

  environment {
    variables = merge(
      {
        DATA_TABLE_NAME          = module.data.table_name
        GOOGLE_CLIENT_CREDS_NAME = module.secrets.google_client_creds_arn
        GOOGLE_USER_TOKENS_NAME  = module.secrets.google_user_tokens_arn
      },
      local.notification_env_vars
    )
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "job" {
  filename         = data.archive_file.backend_zip.output_path
  function_name    = "${local.name_prefix}-job"
  role             = module.iam.lambda_role_arn
  handler          = "handlers.job_handler.handler"
  source_code_hash = data.archive_file.backend_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = 60
  memory_size      = 512

  environment {
    variables = {
      DATA_TABLE_NAME          = module.data.table_name
      GOOGLE_CLIENT_CREDS_NAME = module.secrets.google_client_creds_arn
      GOOGLE_USER_TOKENS_NAME  = module.secrets.google_user_tokens_arn
      TENANT_RESOLUTION_MODE   = "multi"
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "google_auth" {
  filename         = data.archive_file.backend_zip.output_path
  function_name    = "${local.name_prefix}-google-auth"
  role             = module.iam.lambda_role_arn
  handler          = "handlers.google_auth_handler.handler"
  source_code_hash = data.archive_file.backend_zip.output_base64sha256
  runtime          = "python3.11"
  memory_size      = 512
  timeout          = 60 # OAuth exchanges can be slow

  environment {
    variables = {
      DATA_TABLE_NAME                 = module.data.table_name
      GOOGLE_CLIENT_CREDS_NAME        = module.secrets.google_client_creds_arn
      GOOGLE_USER_TOKENS_NAME         = module.secrets.google_user_tokens_arn
      ENTITLEMENT_ENFORCEMENT_ENABLED = "true"
      TENANT_RESOLUTION_MODE          = "multi"
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "pet" {
  filename         = data.archive_file.backend_zip.output_path
  function_name    = "${local.name_prefix}-pet"
  role             = module.iam.lambda_role_arn
  handler          = "handlers.pet_handler.handler"
  source_code_hash = data.archive_file.backend_zip.output_base64sha256
  runtime          = "python3.11"
  memory_size      = 512
  timeout          = 60

  environment {
    variables = {
      DATA_TABLE_NAME        = module.data.table_name
      TENANT_RESOLUTION_MODE = "multi"
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "cancellation" {
  filename         = data.archive_file.backend_zip.output_path
  function_name    = "${local.name_prefix}-cancellation"
  role             = module.iam.lambda_role_arn
  handler          = "handlers.cancellation_handler.handler"
  source_code_hash = data.archive_file.backend_zip.output_base64sha256
  runtime          = "python3.11"
  memory_size      = 512
  timeout          = 60

  environment {
    variables = merge(
      {
        DATA_TABLE_NAME            = module.data.table_name
        GOOGLE_CLIENT_CREDS_NAME   = module.secrets.google_client_creds_arn
        GOOGLE_USER_TOKENS_NAME    = module.secrets.google_user_tokens_arn
        STAFF_COORDINATION_SNS_ARN = module.notifications.staff_coordination_topic_arn
      },
      local.notification_env_vars
    )
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "device" {
  filename         = data.archive_file.backend_zip.output_path
  function_name    = "${local.name_prefix}-device"
  role             = module.iam.lambda_role_arn
  handler          = "handlers.device_handler.handler"
  source_code_hash = data.archive_file.backend_zip.output_base64sha256
  runtime          = "python3.11"
  memory_size      = 512
  timeout          = 30

  environment {
    variables = {
      DATA_TABLE_NAME        = module.data.table_name
      TENANT_RESOLUTION_MODE = "multi"
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "ses_feedback" {
  filename         = data.archive_file.backend_zip.output_path
  function_name    = "${local.name_prefix}-ses-feedback"
  role             = module.iam.lambda_role_arn
  handler          = "handlers.notification_feedback_handler.handler"
  source_code_hash = data.archive_file.backend_zip.output_base64sha256
  runtime          = "python3.11"
  memory_size      = 256
  timeout          = 30

  environment {
    variables = {
      DATA_TABLE_NAME        = module.data.table_name
      TENANT_RESOLUTION_MODE = "multi"
    }
  }

  tags = local.common_tags
}

# SNS Trigger for SES Feedback
resource "aws_sns_topic_subscription" "ses_feedback_trigger" {
  topic_arn = module.notifications.ses_feedback_topic_arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.ses_feedback.arn
}

resource "aws_lambda_permission" "sns_ses_feedback" {
  statement_id  = "AllowSNSSESFeedbackInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ses_feedback.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = module.notifications.ses_feedback_topic_arn
}

# Release 6I Phase 1: Postmark Webhook Handler
resource "aws_lambda_function" "postmark_webhook" {
  filename         = data.archive_file.backend_zip.output_path
  function_name    = "${local.name_prefix}-postmark-webhook"
  role             = module.iam.lambda_role_arn
  handler          = "handlers.postmark_webhook_handler.handler"
  source_code_hash = data.archive_file.backend_zip.output_base64sha256
  runtime          = "python3.11"
  memory_size      = 256
  timeout          = 10

  environment {
    variables = {
      DATA_TABLE_NAME         = module.data.table_name
      POSTMARK_WEBHOOK_SECRET = var.postmark_webhook_secret
      TENANT_RESOLUTION_MODE  = "multi"
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_permission" "api_postmark_webhook" {
  statement_id  = "AllowAPIGatewayInvokePostmarkWebhook"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.postmark_webhook.function_name
  principal     = "apigateway.amazonaws.com"
}

# Release 12I: Stripe Webhook Handler Lambda
resource "aws_lambda_function" "stripe_webhook" {
  filename         = data.archive_file.backend_zip.output_path
  function_name    = "${local.name_prefix}-stripe-webhook"
  role             = module.iam.lambda_role_arn
  handler          = "handlers.stripe_webhook_handler.handler"
  source_code_hash = data.archive_file.backend_zip.output_base64sha256
  runtime          = "python3.11"
  memory_size      = 256
  timeout          = 30

  environment {
    variables = {
      DATA_TABLE_NAME                   = module.data.table_name
      STRIPE_WEBHOOK_SECRET             = var.stripe_webhook_secret
      STRIPE_ENVIRONMENT                = "sandbox"
      STRIPE_ENV                        = "sandbox"
      STRIPE_PRICE_STARTER_MONTHLY      = var.stripe_price_starter_monthly
      STRIPE_PRICE_PROFESSIONAL_MONTHLY = var.stripe_price_professional_monthly
      STRIPE_PRICE_PREMIUM_MONTHLY      = var.stripe_price_premium_monthly
      DEFAULT_COMPANY_ID                = "tog_and_dogs"
      TENANT_RESOLUTION_MODE            = "multi"
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_permission" "api_stripe_webhook" {
  statement_id  = "AllowAPIGatewayInvokeStripeWebhook"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.stripe_webhook.function_name
  principal     = "apigateway.amazonaws.com"
}

resource "aws_lambda_function" "platform" {
  filename         = data.archive_file.backend_zip.output_path
  function_name    = "${local.name_prefix}-platform"
  role             = module.iam.lambda_role_arn
  handler          = "handlers.platform_handler.handler"
  source_code_hash = data.archive_file.backend_zip.output_base64sha256
  runtime          = "python3.11"
  memory_size      = 512
  timeout          = 60

  environment {
    variables = {
      DATA_TABLE_NAME        = module.data.table_name
      DEFAULT_COMPANY_ID     = "tog_and_dogs"
      TENANT_RESOLUTION_MODE = "multi"
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_permission" "api_platform" {
  statement_id  = "AllowAPIGatewayInvokePlatform"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.platform.function_name
  principal     = "apigateway.amazonaws.com"
}



# API Permissions for Google Auth
resource "aws_lambda_permission" "api_google_auth" {
  statement_id  = "AllowAPIGatewayInvokeGoogleAuth"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.google_auth.function_name
  principal     = "apigateway.amazonaws.com"
}

# Release 6G Phase 3: Scheduled Calendar Health Check (daily)
resource "aws_cloudwatch_event_rule" "calendar_health_check" {
  name                = "${local.name_prefix}-calendar-health-check"
  description         = "Daily Google Calendar connection health check"
  schedule_expression = "rate(1 day)"
  tags                = local.common_tags
}

resource "aws_cloudwatch_event_target" "calendar_health_check" {
  rule      = aws_cloudwatch_event_rule.calendar_health_check.name
  target_id = "CalendarHealthCheckLambda"
  arn       = aws_lambda_function.google_auth.arn
  input     = jsonencode({ "action" = "health_check", "source" = "aws.events" })
}

resource "aws_lambda_permission" "eventbridge_calendar_health" {
  statement_id  = "AllowEventBridgeCalendarHealth"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.google_auth.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.calendar_health_check.arn
}

# API Permissions for Lambda
resource "aws_lambda_permission" "api_intake" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.intake.function_name
  principal     = "apigateway.amazonaws.com"
}

resource "aws_lambda_permission" "api_admin" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.admin.function_name
  principal     = "apigateway.amazonaws.com"
}

resource "aws_lambda_permission" "api_review" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.review.function_name
  principal     = "apigateway.amazonaws.com"
}

resource "aws_lambda_permission" "api_assign" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.assign.function_name
  principal     = "apigateway.amazonaws.com"
}

resource "aws_lambda_permission" "api_pet" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pet.function_name
  principal     = "apigateway.amazonaws.com"
}

resource "aws_lambda_permission" "api_cancellation" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cancellation.function_name
  principal     = "apigateway.amazonaws.com"
}

resource "aws_lambda_permission" "api_device" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.device.function_name
  principal     = "apigateway.amazonaws.com"
}

# ------------------------------------------------------------------------------
# 5. API GATEWAY
# ------------------------------------------------------------------------------

module "api" {
  source                              = "../../modules/api"
  name_prefix                         = local.name_prefix
  environment                         = var.environment
  user_pool_arn                       = module.auth.user_pool_arn
  intake_handler_invoke_arn           = aws_lambda_function.intake.invoke_arn
  admin_handler_invoke_arn            = aws_lambda_function.admin.invoke_arn
  review_handler_invoke_arn           = aws_lambda_function.review.invoke_arn
  assign_handler_invoke_arn           = aws_lambda_function.assign.invoke_arn
  google_auth_handler_invoke_arn      = aws_lambda_function.google_auth.invoke_arn
  pet_handler_invoke_arn              = aws_lambda_function.pet.invoke_arn
  cancellation_handler_invoke_arn     = aws_lambda_function.cancellation.invoke_arn
  postmark_webhook_handler_invoke_arn = aws_lambda_function.postmark_webhook.invoke_arn
  stripe_webhook_handler_invoke_arn   = aws_lambda_function.stripe_webhook.invoke_arn
  device_handler_invoke_arn           = aws_lambda_function.device.invoke_arn
  platform_handler_invoke_arn         = aws_lambda_function.platform.invoke_arn
  tags                                = local.common_tags
}

# ------------------------------------------------------------------------------
# 6. WORKFLOW (Step Functions)
# ------------------------------------------------------------------------------

module "workflow" {
  source                 = "../../modules/workflow"
  name_prefix            = local.name_prefix
  sfn_role_arn           = module.iam.sfn_role_arn
  job_handler_arn        = aws_lambda_function.job.arn
  notification_topic_arn = module.notifications.ryan_alerts_topic_arn
  tags                   = local.common_tags
}

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# 7. FRONTEND HOSTING
# ------------------------------------------------------------------------------

module "frontend_hosting" {
  source      = "../../modules/frontend-hosting"
  name_prefix = local.name_prefix
  domain_name = var.domain_name
  subdomain   = var.app_subdomain
  tags        = local.common_tags
}
