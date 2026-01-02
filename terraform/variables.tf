variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev/staging/prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "fetch-data-jobs"
}

variable "sqs_message_retention_seconds" {
  description = "Message retention period in seconds for the main SQS queue (default: 345600 = 4 days)"
  type        = number
  default     = 345600
}

variable "sqs_dlq_message_retention_seconds" {
  description = "Message retention period in seconds for the DLQ (default: 1209600 = 14 days, maximum)"
  type        = number
  default     = 1209600
}

