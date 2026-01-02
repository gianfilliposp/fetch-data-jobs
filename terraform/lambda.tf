locals {
  ai_message_creator_lambda = "ai-message-creator-lambda-function-${var.environment}"
}

# Start AI Message Creator Lambda Configuration
data "archive_file" "lambda_function_ai_message_creator" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/ai-message-creator/"
  output_path = "${path.module}/../lambda/ai-message-creator/lambda_function.zip"
}

resource "aws_lambda_function" "ai_message_creator_lambda_function" {
  function_name = local.ai_message_creator_lambda
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.10"
  role          = aws_iam_role.lambda_execution_role.arn
  filename      = data.archive_file.lambda_function_ai_message_creator.output_path

  source_code_hash = filebase64sha256(data.archive_file.lambda_function_ai_message_creator.output_path)

  # Configure memory and timeout
  memory_size = 256
  timeout     = 300 # 5 minutes in seconds

  environment {
    variables = {
      LOG_LEVEL   = "INFO"
      ENVIRONMENT = var.environment
      SQS_QUEUE_URL = aws_sqs_queue.ai_message_creator.url
    }
  }
}

resource "aws_cloudwatch_log_group" "ai_message_creator_lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.ai_message_creator_lambda_function.function_name}"
  retention_in_days = 7
}

# Event source mapping to trigger Lambda from SQS
resource "aws_lambda_event_source_mapping" "ai_message_creator_sqs_trigger" {
  event_source_arn = aws_sqs_queue.ai_message_creator.arn
  function_name    = aws_lambda_function.ai_message_creator_lambda_function.arn
  batch_size       = 10
  enabled          = true
}

