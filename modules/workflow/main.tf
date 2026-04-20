resource "aws_sfn_state_machine" "request_lifecycle" {
  name     = "${var.name_prefix}-request-lifecycle"
  role_arn = var.sfn_role_arn

  definition = jsonencode({
    Comment = "Lifecycle for Pet Sitting Service Requests"
    StartAt = "WaitForReview"
    States = {
      WaitForReview = {
        Type    = "Wait"
        Seconds = 3600 # Placeholder for manual review cycle
        Next    = "CheckStatus"
      }
      CheckStatus = {
        Type = "Choice"
        Choices = [
          {
            Variable     = "$.status"
            StringEquals = "REQUEST_APPROVED"
            Next         = "CreateJob"
          },
          {
            Variable     = "$.status"
            StringEquals = "REQUEST_DECLINED"
            Next         = "NotifyDeclined"
          }
        ]
        Default = "WaitForReview"
      }
      CreateJob = {
        Type     = "Task"
        Resource = var.job_handler_arn
        Next     = "NotifyApproved"
      }
      NotifyApproved = {
        Type     = "Task"
        Resource = "arn:aws:states:::sns:publish"
        Parameters = {
          TopicArn = var.notification_topic_arn
          Message = {
            message    = "Your pet sitting request has been APPROVED."
            request_id = "$.request_id"
          }
        }
        End = true
      }
      NotifyDeclined = {
        Type     = "Task"
        Resource = "arn:aws:states:::sns:publish"
        Parameters = {
          TopicArn = var.notification_topic_arn
          Message = {
            message    = "Your pet sitting request was declined."
            request_id = "$.request_id"
          }
        }
        End = true
      }
    }
  })

  tags = var.tags
}
