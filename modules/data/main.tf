resource "aws_dynamodb_table" "main" {
  name         = "${var.name_prefix}-data"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  # GSI for Status tracking (find pending requests, jobs by status)
  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  global_secondary_index {
    name            = "StatusIndex"
    hash_key        = "status"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  # GSI for Worker assignments
  attribute {
    name = "worker_id"
    type = "S"
  }

  attribute {
    name = "assigned_at"
    type = "S"
  }

  global_secondary_index {
    name            = "WorkerIndex"
    hash_key        = "worker_id"
    range_key       = "assigned_at"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = var.tags
}
