resource "aws_ses_configuration_set" "main" {
  name = "${var.name_prefix}-config-set"
}

resource "aws_sns_topic" "ses_feedback" {
  name = "${var.name_prefix}-ses-feedback"
  tags = var.tags
}

resource "aws_ses_event_destination" "sns" {
  name                   = "sns-feedback"
  configuration_set_name = aws_ses_configuration_set.main.name
  enabled                = true
  matching_types         = ["bounce", "complaint"]

  sns_destination {
    topic_arn = aws_sns_topic.ses_feedback.arn
  }
}
