# ------------------------------------------------------------------------------
# Preview-Only V1: Platform Admin Tenant-Onboarding Orchestrator
# Dedicated Preview Lambda + API Gateway Routes
#
# This Lambda is intentionally separate from the main `platform` Lambda to:
#   1. Use the dedicated read-only IAM role (platform_preview_exec)
#   2. Provide explicit no-write isolation at the deployment layer
#   3. Expose only POST /platform/onboarding/validate and /preview — no
#      /apply, /approve, /create, or /requests routes exist
#
# Gate status: APPROVED FOR DEPLOYMENT ONLY AFTER EXPLICIT MATTHEW APPROVAL
# Production deployment of this Terraform file is separately gated.
# ------------------------------------------------------------------------------

resource "aws_lambda_function" "platform_preview" {
  filename         = data.archive_file.backend_zip.output_path
  function_name    = "${local.name_prefix}-platform-preview"
  role             = aws_iam_role.platform_preview_exec.arn
  handler          = "handlers.platform_onboarding_handler.handler"
  source_code_hash = data.archive_file.backend_zip.output_base64sha256
  runtime          = "python3.11"
  memory_size      = 256
  timeout          = 30

  environment {
    variables = {
      DATA_TABLE_NAME        = module.data.table_name
      DEFAULT_COMPANY_ID     = "tog_and_dogs"
      TENANT_RESOLUTION_MODE = "multi"
    }
  }

  tags = merge(local.common_tags, {
    Purpose = "platform-onboarding-preview-readonly"
  })
}

resource "aws_lambda_permission" "api_platform_preview_validate" {
  statement_id  = "AllowAPIGatewayInvokePlatformPreviewValidate"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.platform_preview.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${module.api.execution_arn}/*/POST/platform/onboarding/validate"
}

resource "aws_lambda_permission" "api_platform_preview_preview" {
  statement_id  = "AllowAPIGatewayInvokePlatformPreviewPreview"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.platform_preview.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${module.api.execution_arn}/*/POST/platform/onboarding/preview"
}
