resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${var.name_prefix}-api"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "workflow" {
  name              = "/aws/vendedlogs/states/${var.name_prefix}-workflow"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

# Placeholder for baseline alarms
resource "aws_cloudwatch_metric_alarm" "api_errors" {
  alarm_name          = "${var.name_prefix}-api-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "This metric monitors api lambda errors"

  dimensions = {
    FunctionName = "${var.name_prefix}-api"
  }

  tags = var.tags
}


# Release 6G Phase 1: Calendar Sync Observability
# Metric filters scan all calendar-enabled Lambda log groups for failure/revocation patterns.

# --- Metric Filters ---

resource "aws_cloudwatch_log_metric_filter" "calendar_sync_failed" {
  for_each = toset([
    "/aws/lambda/${var.name_prefix}-intake",
    "/aws/lambda/${var.name_prefix}-admin",
    "/aws/lambda/${var.name_prefix}-review",
    "/aws/lambda/${var.name_prefix}-assign",
    "/aws/lambda/${var.name_prefix}-cancellation",
  ])

  name           = "${var.name_prefix}-calendar-sync-failed-${replace(replace(each.value, "/aws/lambda/${var.name_prefix}-", ""), "/", "-")}"
  pattern        = "CALENDAR_SYNC_FAILED"
  log_group_name = each.value

  metric_transformation {
    name      = "CalendarSyncFailed"
    namespace = "${var.name_prefix}/Calendar"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "calendar_token_revoked" {
  for_each = toset([
    "/aws/lambda/${var.name_prefix}-intake",
    "/aws/lambda/${var.name_prefix}-admin",
    "/aws/lambda/${var.name_prefix}-review",
    "/aws/lambda/${var.name_prefix}-assign",
    "/aws/lambda/${var.name_prefix}-cancellation",
  ])

  name           = "${var.name_prefix}-calendar-token-revoked-${replace(replace(each.value, "/aws/lambda/${var.name_prefix}-", ""), "/", "-")}"
  pattern        = "CALENDAR_SYNC_TOKEN_REVOKED"
  log_group_name = each.value

  metric_transformation {
    name      = "CalendarTokenRevoked"
    namespace = "${var.name_prefix}/Calendar"
    value     = "1"
  }
}

# --- Alarms ---

resource "aws_cloudwatch_metric_alarm" "calendar_sync_failures" {
  alarm_name          = "${var.name_prefix}-calendar-sync-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "CalendarSyncFailed"
  namespace           = "${var.name_prefix}/Calendar"
  period              = "3600"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Google Calendar sync failed one or more times in the last hour. Check Lambda logs for CALENDAR_SYNC_FAILED."
  treat_missing_data  = "notBreaching"

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "calendar_token_revoked" {
  alarm_name          = "${var.name_prefix}-calendar-token-revoked"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "CalendarTokenRevoked"
  namespace           = "${var.name_prefix}/Calendar"
  period              = "3600"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Google Calendar token was revoked (invalid_grant). Admin must reconnect Google Calendar."
  treat_missing_data  = "notBreaching"

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  tags = var.tags
}


# Release 6G Phase 3: Calendar Health Check Metric Filters & Alarms

resource "aws_cloudwatch_log_metric_filter" "calendar_health_failed" {
  name           = "${var.name_prefix}-calendar-health-failed"
  pattern        = "CALENDAR_HEALTH_CHECK_FAILED"
  log_group_name = "/aws/lambda/${var.name_prefix}-google-auth"

  metric_transformation {
    name      = "CalendarHealthCheckFailed"
    namespace = "${var.name_prefix}/Calendar"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "calendar_health_revoked" {
  name           = "${var.name_prefix}-calendar-health-revoked"
  pattern        = "CALENDAR_HEALTH_CHECK_TOKEN_REVOKED"
  log_group_name = "/aws/lambda/${var.name_prefix}-google-auth"

  metric_transformation {
    name      = "CalendarHealthCheckRevoked"
    namespace = "${var.name_prefix}/Calendar"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "calendar_health_check_failed" {
  alarm_name          = "${var.name_prefix}-calendar-health-check-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "CalendarHealthCheckFailed"
  namespace           = "${var.name_prefix}/Calendar"
  period              = "86400"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Scheduled Google Calendar health check failed. Check /admin/auth/status or reconnect."
  treat_missing_data  = "notBreaching"

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  tags = var.tags
}
