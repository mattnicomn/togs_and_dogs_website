output "table_name" {
  value       = aws_dynamodb_table.main.name
  description = "Name of the DynamoDB table"
}

output "table_arn" {
  value       = aws_dynamodb_table.main.arn
  description = "ARN of the DynamoDB table"
}
