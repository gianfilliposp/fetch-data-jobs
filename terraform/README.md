# Default Terraform Configuration

This is a minimal Terraform configuration that uses AWS default settings without custom VPC, networking, or complex configurations.

## Features

- **No VPC Configuration**: Lambda functions run in AWS default networking
- **Simplified IAM**: Basic Lambda execution role with CloudWatch Logs
- **Default Settings**: Uses AWS defaults for most resources
- **Minimal Setup**: Easy to understand and extend

## Structure

- `main.tf`: Provider and backend configuration
- `variables.tf`: Input variables
- `iam.tf`: Basic IAM roles and policies
- `lambda.tf`: Example Lambda function (no VPC)
- `api-gateway.tf`: Simple HTTP API Gateway
- `dynamodb.tf`: Example DynamoDB table

## Usage

1. Initialize Terraform:
   ```bash
   cd terraform-default
   terraform init
   ```

2. Review the plan:
   ```bash
   terraform plan
   ```

3. Apply the configuration:
   ```bash
   terraform apply
   ```

## Customization

- Add more Lambda functions by duplicating the pattern in `lambda.tf`
- Add more API routes in `api-gateway.tf`
- Add more DynamoDB tables in `dynamodb.tf`
- Modify IAM policies in `iam.tf` as needed

## Differences from Full Configuration

- **No VPC**: Functions run in default AWS networking (no custom subnets, security groups, etc.)
- **No Lambda Layers**: Can be added if needed
- **Simplified IAM**: Basic permissions only
- **No S3**: Can be added if needed
- **Local State**: Uses local state by default (uncomment backend block for S3)

## Notes

- Lambda functions without VPC have faster cold starts
- Default networking is simpler but less secure for production
- Consider adding VPC configuration for production workloads

