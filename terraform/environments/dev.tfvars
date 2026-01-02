environment  = "dev"
aws_region   = "us-east-1"
project_name = "fetch-data-jobs"

# SQS Message Retention (in seconds)
sqs_message_retention_seconds      = 345600  # 4 days
sqs_dlq_message_retention_seconds  = 1209600 # 14 days (maximum)

