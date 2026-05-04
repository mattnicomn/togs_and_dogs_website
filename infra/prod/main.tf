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
  source      = "../../modules/observability"
  name_prefix = local.name_prefix
  tags        = local.common_tags
}

# ------------------------------------------------------------------------------
# 4. LAMBDA LOGIC (Python Handlers)
# ------------------------------------------------------------------------------

# Archive code for Lambda
data "archive_file" "backend_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../src/backend"
  output_path = "${path.module}/backend.zip"
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
        DATA_TABLE_NAME   = module.data.table_name
        STATE_MACHINE_ARN = module.workflow.sfn_arn
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
        DATA_TABLE_NAME    = module.data.table_name
        ADMIN_USER_POOL_ID = module.auth.user_pool_id
        DEFAULT_COMPANY_ID = "tog_and_dogs"
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
    variables = {
      DATA_TABLE_NAME          = module.data.table_name
      GOOGLE_CLIENT_CREDS_NAME = module.secrets.google_client_creds_arn
      GOOGLE_USER_TOKENS_NAME  = module.secrets.google_user_tokens_arn
      JOB_FUNCTION_NAME        = aws_lambda_function.job.function_name
    }
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
      DATA_TABLE_NAME          = module.data.table_name
      GOOGLE_CLIENT_CREDS_NAME = module.secrets.google_client_creds_arn
      GOOGLE_USER_TOKENS_NAME  = module.secrets.google_user_tokens_arn
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
      DATA_TABLE_NAME = module.data.table_name
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

# API Permissions for Google Auth
resource "aws_lambda_permission" "api_google_auth" {
  statement_id  = "AllowAPIGatewayInvokeGoogleAuth"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.google_auth.function_name
  principal     = "apigateway.amazonaws.com"
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

# ------------------------------------------------------------------------------
# 5. API GATEWAY
# ------------------------------------------------------------------------------

module "api" {
  source                          = "../../modules/api"
  name_prefix                     = local.name_prefix
  environment                     = var.environment
  user_pool_arn                   = module.auth.user_pool_arn
  intake_handler_invoke_arn       = aws_lambda_function.intake.invoke_arn
  admin_handler_invoke_arn        = aws_lambda_function.admin.invoke_arn
  review_handler_invoke_arn       = aws_lambda_function.review.invoke_arn
  assign_handler_invoke_arn       = aws_lambda_function.assign.invoke_arn
  google_auth_handler_invoke_arn  = aws_lambda_function.google_auth.invoke_arn
  pet_handler_invoke_arn          = aws_lambda_function.pet.invoke_arn
  cancellation_handler_invoke_arn = aws_lambda_function.cancellation.invoke_arn
  tags                            = local.common_tags
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
