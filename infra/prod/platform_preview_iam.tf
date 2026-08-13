# ------------------------------------------------------------------------------
# Preview-Only V1: Platform Admin Tenant-Onboarding Orchestrator
# Dedicated Read-Only IAM Role
#
# This role is intentionally limited to the minimum permissions required
# for the onboarding preview Lambda to perform read-only DynamoDB checks:
#   - dynamodb:GetItem   (tenant existence check)
#   - dynamodb:Scan      (display-name collision detection)
#
# EXPLICITLY EXCLUDED (none of these actions appear in any attached policy):
#   - dynamodb:PutItem
#   - dynamodb:UpdateItem
#   - dynamodb:DeleteItem
#   - dynamodb:TransactWriteItems
#   - cognito-idp:*
#   - secretsmanager:*
#   - ses:*
#   - lambda:InvokeFunction
#   - states:*
#   - sns:*
#
# This file is intentionally separate from modules/iam to make the scope
# boundary visible and prevent accidental policy attachment.
# ------------------------------------------------------------------------------

resource "aws_iam_role" "platform_preview_exec" {
  name = "${local.name_prefix}-platform-preview-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = merge(local.common_tags, {
    Purpose = "platform-onboarding-preview-readonly"
  })
}

# CloudWatch Logs only — no other AWS service access
resource "aws_iam_role_policy_attachment" "platform_preview_logs" {
  role       = aws_iam_role.platform_preview_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Dedicated read-only DynamoDB policy: GetItem and Scan only
resource "aws_iam_policy" "platform_preview_dynamodb_readonly" {
  name        = "${local.name_prefix}-platform-preview-dynamodb-readonly"
  description = "Allows the onboarding preview Lambda to read tenant data. No write actions. See platform_preview_iam.tf."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "OnboardingPreviewReadOnly"
      Effect = "Allow"
      Action = [
        "dynamodb:GetItem",
        "dynamodb:Scan"
      ]
      Resource = module.data.table_arn
    }]
  })

  tags = merge(local.common_tags, {
    Purpose = "platform-onboarding-preview-readonly"
  })
}

resource "aws_iam_role_policy_attachment" "platform_preview_dynamodb" {
  role       = aws_iam_role.platform_preview_exec.name
  policy_arn = aws_iam_policy.platform_preview_dynamodb_readonly.arn
}
