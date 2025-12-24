# Simple HTTP API Gateway
resource "aws_apigatewayv2_api" "api" {
  name          = "${var.project_name}-api-${var.environment}"
  protocol_type = "HTTP"
  
  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers = ["*"]
  }
}

# API Gateway Deployment
resource "aws_apigatewayv2_deployment" "api" {
  api_id = aws_apigatewayv2_api.api.id

  # Add route dependencies here when you add routes
  # depends_on = [
  #   aws_apigatewayv2_route.example
  # ]
}

# API Gateway Stage
resource "aws_apigatewayv2_stage" "api" {
  api_id        = aws_apigatewayv2_api.api.id
  name          = var.environment
  deployment_id = aws_apigatewayv2_deployment.api.id
  auto_deploy   = true
}

# Example API Gateway Integration and Route
# Uncomment and modify when you have Lambda functions:

# resource "aws_apigatewayv2_integration" "example" {
#   api_id           = aws_apigatewayv2_api.api.id
#   integration_type = "AWS_PROXY"
#   integration_method = "POST"
#   integration_uri  = aws_lambda_function.example.invoke_arn
# }
# 
# resource "aws_apigatewayv2_route" "example" {
#   api_id    = aws_apigatewayv2_api.api.id
#   route_key = "GET /example"
#   target    = "integrations/${aws_apigatewayv2_integration.example.id}"
# }
# 
# resource "aws_lambda_permission" "api_gateway_invoke" {
#   statement_id  = "AllowAPIGatewayInvoke"
#   action        = "lambda:InvokeFunction"
#   function_name = aws_lambda_function.example.function_name
#   principal     = "apigateway.amazonaws.com"
#   source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
# }

# Output API Gateway URL
output "api_gateway_url" {
  value = aws_apigatewayv2_stage.api.invoke_url
}

