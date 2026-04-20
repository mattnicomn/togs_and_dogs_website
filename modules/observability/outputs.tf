output "api_log_group_name" {
  value       = aws_cloudwatch_log_group.api.name
  description = "Name of the API log group"
}

output "workflow_log_group_name" {
  value       = aws_cloudwatch_log_group.workflow.name
  description = "Name of the workflow log group"
}
