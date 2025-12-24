# Example DynamoDB table with default settings
resource "aws_dynamodb_table" "example" {
  name         = "${var.project_name}-table-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"  # Default: on-demand pricing

  hash_key = "id"

  attribute {
    name = "id"
    type = "S"
  }

  tags = {
    Environment = var.environment
    Name        = "${var.project_name}-table-${var.environment}"
  }
}

# Output table name
output "dynamodb_table_name" {
  value = aws_dynamodb_table.example.name
}

