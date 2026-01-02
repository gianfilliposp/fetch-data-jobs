# Dead Letter Queue for ai-message-creator
resource "aws_sqs_queue" "ai_message_creator_dlq" {
  name                      = "${var.project_name}-ai-message-creator-sqs-dlq-${var.environment}"
  message_retention_seconds = var.sqs_dlq_message_retention_seconds

  tags = {
    Environment = var.environment
    Name        = "${var.project_name}-ai-message-creator-sqs-dlq-${var.environment}"
  }
}

# Main ai-message-creator queue
resource "aws_sqs_queue" "ai_message_creator" {
  name                      = "${var.project_name}-ai-message-creator-sqs-${var.environment}"
  message_retention_seconds = var.sqs_message_retention_seconds
  visibility_timeout_seconds = 1800   # 30 minutes (6x Lambda timeout to prevent reprocessing)
  receive_wait_time_seconds  = 20     # Long polling (reduces empty responses)

  # Redrive policy to send failed messages to DLQ
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ai_message_creator_dlq.arn
    maxReceiveCount     = 3 # Number of times a message can be received before being sent to DLQ
  })

  tags = {
    Environment = var.environment
    Name        = "${var.project_name}-ai-message-creator-sqs-${var.environment}"
  }
}
