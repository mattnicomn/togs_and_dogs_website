output "lambda_role_arn" {
  value       = aws_iam_role.lambda_exec.arn
  description = "ARN of the Lambda execution role"
}

output "sfn_role_arn" {
  value       = aws_iam_role.sfn_exec.arn
  description = "ARN of the Step Functions execution role"
}
