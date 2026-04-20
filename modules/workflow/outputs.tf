output "sfn_arn" {
  value       = aws_sfn_state_machine.request_lifecycle.arn
  description = "ARN of the request lifecycle Step Function"
}
