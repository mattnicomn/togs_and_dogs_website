output "ryan_alerts_topic_arn" {
  value       = aws_sns_topic.ryan_alerts.arn
  description = "ARN of the Ryan alerts SNS topic"
}

output "staff_coordination_topic_arn" {
  value       = aws_sns_topic.staff_coordination.arn
  description = "ARN of the staff coordination SNS topic"
}
