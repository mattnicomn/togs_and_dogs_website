# ------------------------------------------------------------------------------
# Cognito Custom Email Sender + Postmark
#
# LOCAL IMPLEMENTATION ONLY / NOT DEPLOYED
#
# The package is intentionally outside src/backend and must be built separately:
#   python scripts/build_cognito_email_sender_package.py
# This prevents changes to the shared backend.zip and its existing Lambda fleet.
# ------------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

locals {
  cognito_email_sender_package_path = coalesce(
    var.cognito_email_sender_package_path,
    "${path.module}/../../artifacts/cognito-email-sender/cognito-email-sender.zip"
  )
}

resource "aws_iam_role" "cognito_email_sender" {
  name = "${local.name_prefix}-cognito-email-sender"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "LambdaAssumeRole"
      Effect = "Allow"
      Action = "sts:AssumeRole"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = merge(local.common_tags, {
    Purpose = "cognito-password-recovery-postmark"
  })
}

data "aws_iam_policy_document" "cognito_email_sender_kms" {
  statement {
    sid    = "EnableAccountKeyAdministration"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    actions   = ["kms:*"]
    resources = ["*"]
  }

  statement {
    sid    = "AllowSenderDecryptForCognitoContext"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = [aws_iam_role.cognito_email_sender.arn]
    }

    actions   = ["kms:Decrypt"]
    resources = ["*"]

    condition {
      test     = "StringLike"
      variable = "kms:EncryptionContext:userpool-id"
      values   = ["${var.aws_region}_*"]
    }
  }
}

resource "aws_kms_key" "cognito_email_sender" {
  description              = "Encrypts Cognito Custom Email Sender password-recovery codes"
  key_usage                = "ENCRYPT_DECRYPT"
  customer_master_key_spec = "SYMMETRIC_DEFAULT"
  enable_key_rotation      = true
  deletion_window_in_days  = 30
  policy                   = data.aws_iam_policy_document.cognito_email_sender_kms.json

  tags = merge(local.common_tags, {
    Purpose = "cognito-password-recovery-code-envelope"
  })
}

resource "aws_kms_alias" "cognito_email_sender" {
  name          = "alias/${local.name_prefix}-cognito-email-sender"
  target_key_id = aws_kms_key.cognito_email_sender.key_id
}

resource "aws_cloudwatch_log_group" "cognito_email_sender" {
  name              = "/aws/lambda/${local.name_prefix}-cognito-email-sender"
  retention_in_days = 30

  tags = merge(local.common_tags, {
    Purpose = "cognito-password-recovery-postmark"
  })
}

data "aws_iam_policy_document" "cognito_email_sender" {
  statement {
    sid    = "WriteDedicatedLambdaLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["${aws_cloudwatch_log_group.cognito_email_sender.arn}:*"]
  }

  statement {
    sid       = "ReadPostmarkServerToken"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [module.secrets.postmark_token_arn]
  }

  statement {
    sid       = "DecryptCognitoCodeEnvelope"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.cognito_email_sender.arn]

    condition {
      test     = "StringLike"
      variable = "kms:EncryptionContext:userpool-id"
      values   = ["${var.aws_region}_*"]
    }
  }
}

resource "aws_iam_role_policy" "cognito_email_sender" {
  name   = "${local.name_prefix}-cognito-email-sender"
  role   = aws_iam_role.cognito_email_sender.id
  policy = data.aws_iam_policy_document.cognito_email_sender.json
}

resource "aws_lambda_function" "cognito_email_sender" {
  filename         = local.cognito_email_sender_package_path
  function_name    = "${local.name_prefix}-cognito-email-sender"
  role             = aws_iam_role.cognito_email_sender.arn
  handler          = "cognito_email_sender_handler.handler"
  source_code_hash = try(filebase64sha256(local.cognito_email_sender_package_path), null)
  runtime          = "python3.11"
  architectures    = ["x86_64"]
  memory_size      = 256
  timeout          = 15

  environment {
    variables = {
      COGNITO_EMAIL_SENDER_KMS_KEY_ARN = aws_kms_key.cognito_email_sender.arn
      POSTMARK_SERVER_TOKEN_SECRET_ARN = module.secrets.postmark_token_arn
      POSTMARK_MESSAGE_STREAM          = "outbound"
    }
  }

  lifecycle {
    precondition {
      condition     = fileexists(local.cognito_email_sender_package_path)
      error_message = "Build the isolated Cognito email sender package before Terraform plan/apply."
    }
  }

  depends_on = [aws_iam_role_policy.cognito_email_sender]

  tags = merge(local.common_tags, {
    Purpose = "cognito-password-recovery-postmark"
  })
}

resource "aws_lambda_permission" "cognito_email_sender" {
  statement_id   = "AllowCognitoUserPoolInvoke"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.cognito_email_sender.function_name
  principal      = "cognito-idp.amazonaws.com"
  source_account = data.aws_caller_identity.current.account_id
  source_arn     = module.auth.user_pool_arn
}
