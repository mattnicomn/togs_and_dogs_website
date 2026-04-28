# IAM Roles for Lambdas
resource "aws_iam_role" "lambda_exec" {
  name = "${var.name_prefix}-lambda-exec"

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

  tags = var.tags
}

# DynamoDB Access
resource "aws_iam_policy" "dynamodb_access" {
  name        = "${var.name_prefix}-dynamodb-access"
  description = "Allows Lambda to read/write to the project DynamoDB table"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ]
      Effect = "Allow"
      Resource = [
        var.data_table_arn,
        "${var.data_table_arn}/index/*"
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_dynamodb" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.dynamodb_access.arn
}

# Step Functions StartExecution for Intake
resource "aws_iam_policy" "lambda_sfn_start" {
  name        = "${var.name_prefix}-lambda-sfn-start"
  description = "Allows Lambda to start the request lifecycle Step Function"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action   = "states:StartExecution"
      Effect   = "Allow"
      Resource = var.sfn_arn
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_sfn" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_sfn_start.arn
}

# Secrets Manager Access for Google
resource "aws_iam_policy" "google_secrets_access" {
  name        = "${var.name_prefix}-google-secrets"
  description = "Allows Lambda to read/write Google OAuth credentials"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = [
        "secretsmanager:GetSecretValue",
        "secretsmanager:PutSecretValue"
      ]
      Effect = "Allow"
      Resource = [
        var.google_client_creds_arn,
        var.google_user_tokens_arn
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_google_secrets" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.google_secrets_access.arn
}

# logging
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Step Functions Role
resource "aws_iam_role" "sfn_exec" {
  name = "${var.name_prefix}-sfn-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "states.amazonaws.com"
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_policy" "sfn_lambda_sns" {
  name = "${var.name_prefix}-sfn-lambda-sns"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = "lambda:InvokeFunction"
        Effect   = "Allow"
        Resource = "*" # Tighten in more detailed iteration
      },
      {
        Action   = "sns:Publish"
        Effect   = "Allow"
        Resource = var.sns_topic_arns
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "sfn_policy" {
  role       = aws_iam_role.sfn_exec.name
  policy_arn = aws_iam_policy.sfn_lambda_sns.arn
}
resource "aws_iam_policy" "lambda_invoke_access" {
  name        = "${var.name_prefix}-lambda-invoke"
  description = "Allows Lambda to invoke other functions in the project"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action   = "lambda:InvokeFunction"
      Effect   = "Allow"
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_invoke" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_invoke_access.arn
}

# SES Access for Notifications
resource "aws_iam_policy" "ses_access" {
  name        = "${var.name_prefix}-ses-access"
  description = "Allows Lambda to send emails via SES"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = [
        "ses:SendEmail",
        "ses:SendRawEmail"
      ]
      Effect   = "Allow"
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_ses" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.ses_access.arn
}

# Cognito Admin Access
resource "aws_iam_policy" "cognito_admin_access" {
  name        = "${var.name_prefix}-cognito-admin"
  description = "Allows Lambda to onboard and manage Cognito users"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = [
        "cognito-idp:AdminCreateUser",
        "cognito-idp:AdminAddUserToGroup",
        "cognito-idp:AdminGetUser",
        "cognito-idp:AdminUpdateUserAttributes",
        "cognito-idp:AdminDisableUser",
        "cognito-idp:AdminEnableUser",
        "cognito-idp:AdminResetUserPassword",
        "cognito-idp:ListUsers"
      ]
      Effect   = "Allow"
      Resource = var.user_pool_arn
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_cognito" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.cognito_admin_access.arn
}

