# Dead Letter Queue for profile mapper
resource "aws_sqs_queue" "profile_mapper_dlq" {
  name                      = "${var.project_name}-profile-mapper-dlq-${var.environment}"
  message_retention_seconds = 1209600 # 14 days (maximum)

  tags = {
    Environment = var.environment
    Name        = "${var.project_name}-profile-mapper-dlq-${var.environment}"
  }
}

# Main profile mapper queue
resource "aws_sqs_queue" "profile_mapper" {
  name                      = "${var.project_name}-profile-mapper-${var.environment}"
  message_retention_seconds = 345600 # 4 days
  visibility_timeout_seconds = 30     # Adjust based on your processing time
  receive_wait_time_seconds  = 0      # Short polling (0) or long polling (1-20)

  # Redrive policy to send failed messages to DLQ
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.profile_mapper_dlq.arn
    maxReceiveCount     = 3 # Number of times a message can be received before being sent to DLQ
  })

  tags = {
    Environment = var.environment
    Name        = "${var.project_name}-profile-mapper-${var.environment}"
  }
}

# Outputs
output "profile_mapper_queue_url" {
  description = "URL of the profile mapper SQS queue"
  value       = aws_sqs_queue.profile_mapper.url
}

output "profile_mapper_queue_arn" {
  description = "ARN of the profile mapper SQS queue"
  value       = aws_sqs_queue.profile_mapper.arn
}

output "profile_mapper_dlq_url" {
  description = "URL of the profile mapper DLQ"
  value       = aws_sqs_queue.profile_mapper_dlq.url
}

output "profile_mapper_dlq_arn" {
  description = "ARN of the profile mapper DLQ"
  value       = aws_sqs_queue.profile_mapper_dlq.arn
}

