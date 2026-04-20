resource "aws_sns_topic" "ryan_alerts" {
  name = "${var.name_prefix}-ryan-alerts"
  tags = var.tags
}

resource "aws_sns_topic" "staff_coordination" {
  name = "${var.name_prefix}-staff-coordination"
  tags = var.tags
}
