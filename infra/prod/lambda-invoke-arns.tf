# ------------------------------------------------------------------------------
# W3-C2 isolation: decoupled Lambda API-Gateway invoke ARNs
# ------------------------------------------------------------------------------
# The API module integrations historically received each Lambda's invoke ARN as
# `aws_lambda_function.<fn>.invoke_arn`. That created a Terraform dependency edge
# from every API integration (and therefore from aws_api_gateway_deployment.main
# and aws_api_gateway_stage.main) to all 12 API-wired Lambda resources. As a
# result, a `-target` plan on the W3-C2 route / deployment / stage pulled in all
# 12 Lambdas and showed them as code updates (shared backend.zip source hash),
# which would activate W1 on an otherwise admin-only release.
#
# These locals reconstruct the EXACT same invoke ARN strings from region /
# account / partition / function name, with NO reference to the Lambda resources,
# severing the dependency edge. The value is byte-identical to
# aws_lambda_function.<fn>.invoke_arn:
#   arn:<partition>:apigateway:<region>:lambda:path/2015-03-31/functions/
#     arn:<partition>:lambda:<region>:<account>:function:<name_prefix>-<fn>/invocations
# (unqualified $LATEST — no alias, no version qualifier — matching the attribute).
#
# AWS_PROXY integrations only store the URI string; they do not require the target
# Lambda to pre-exist at create time. Invoke permission is still granted by the
# aws_lambda_permission.api_* resources (unchanged), which retain their own
# dependency on the Lambda functions. API deployment ordering is preserved by the
# aws_api_gateway_deployment.main depends_on list (methods/integrations), unchanged.

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

data "aws_region" "current" {}

locals {
  # Lambda logical name -> deployed function name suffix (matches
  # aws_lambda_function.<fn>.function_name = "${local.name_prefix}-<suffix>").
  lambda_function_names = {
    intake           = "${local.name_prefix}-intake"
    admin            = "${local.name_prefix}-admin"
    review           = "${local.name_prefix}-review"
    assign           = "${local.name_prefix}-assign"
    google_auth      = "${local.name_prefix}-google-auth"
    pet              = "${local.name_prefix}-pet"
    cancellation     = "${local.name_prefix}-cancellation"
    postmark_webhook = "${local.name_prefix}-postmark-webhook"
    stripe_webhook   = "${local.name_prefix}-stripe-webhook"
    device           = "${local.name_prefix}-device"
    platform         = "${local.name_prefix}-platform"
  }

  # Byte-identical reconstruction of aws_lambda_function.<fn>.invoke_arn, with no
  # reference to the Lambda resources (breaks the API -> Lambda dependency edge).
  lambda_invoke_arns = {
    for key, fn in local.lambda_function_names :
    key => format(
      "arn:%s:apigateway:%s:lambda:path/2015-03-31/functions/arn:%s:lambda:%s:%s:function:%s/invocations",
      data.aws_partition.current.partition,
      data.aws_region.current.name,
      data.aws_partition.current.partition,
      data.aws_region.current.name,
      data.aws_caller_identity.current.account_id,
      fn,
    )
  }
}
