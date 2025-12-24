# Example Lambda function - using default AWS networking (no VPC)
# You can duplicate this pattern for other Lambda functions
# 
# To use this, create a Lambda function zip file or use inline code.
# For example, create src/example/lambda_function.py and zip it.

# Example: Simple inline Lambda (for testing)
# Uncomment and modify as needed:

# data "archive_file" "example_lambda" {
#   type        = "zip"
#   source_dir  = "${path.module}/../lambda/example/"
#   output_path = "${path.module}/../lambda/example/lambda_function.zip"
# }

# resource "aws_lambda_function" "example" {
#   function_name = "${var.project_name}-example-${var.environment}"
#   handler       = "lambda_function.lambda_handler"
#   runtime       = "python3.10"
#   role          = aws_iam_role.lambda_execution_role.arn
#   filename      = data.archive_file.example_lambda.output_path
# 
#   # Default settings - no VPC, no custom memory/timeout
#   source_code_hash = filebase64sha256(data.archive_file.example_lambda.output_path)
# 
#   environment {
#     variables = {
#       ENVIRONMENT = var.environment
#     }
#   }
# }
# 
# resource "aws_cloudwatch_log_group" "example_lambda_logs" {
#   name              = "/aws/lambda/${aws_lambda_function.example.function_name}"
#   retention_in_days = 7
# }
# 
# output "example_lambda_arn" {
#   value = aws_lambda_function.example.arn
# }

