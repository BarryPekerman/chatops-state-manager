# Lambda Infrastructure

This directory contains Terraform configuration for the Lambda function and API Gateway that handle Telegram webhooks and trigger GitHub Actions workflows.

## Architecture

- **Lambda Function**: Receives Telegram webhooks, validates authorization, and triggers GitHub Actions
- **API Gateway**: Secure HTTPS endpoint with API key authentication, rate limiting, and CORS
- **IAM Role**: Permissions for Lambda to trigger GitHub Actions
- **CloudWatch Logs**: Managed log groups with 7-day retention for both Lambda and API Gateway
- **Security**: API key authentication, rate limiting, access logging, and Telegram webhook validation
- **ZIP Packaging**: Simple, fast deployment without container overhead

## Files

- `main.tf`: Main Terraform configuration with secure API Gateway
- `variables.tf`: Input variables including security settings
- `outputs.tf`: Output values including API key and usage plan
- `src/webhook_handler.py`: Lambda function with security validation
- `src/requirements.txt`: Python dependencies
- `build_lambda.sh`: Script to build the ZIP package
- `test_secure_webhook.sh`: Test script for secure API Gateway
- `setup_telegram_bot.py`: Telegram bot configuration script
- `demo_api_interaction.sh`: Interactive demo of API Gateway usage
- `SECURE_API_GATEWAY.md`: Comprehensive security documentation
- `API_GATEWAY_INTERACTION.md`: Complete interaction guide
- `API_GATEWAY_FLOW.md`: Flow diagrams and examples
- `QUICK_REFERENCE.md`: Quick reference card

## Usage

1. **Set up variables**:
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your values
   ```

2. **Deploy infrastructure**:
   ```bash
   terraform init
   terraform plan
   terraform apply
   ```

3. **Get webhook URL**:
   ```bash
   terraform output webhook_url
   ```

## Packaging

The Lambda function uses ZIP packaging for simplicity and performance:

- **Faster deployment**: No container registry needed
- **Lower costs**: No ECR storage fees
- **Simpler debugging**: Direct Python execution
- **Appropriate scale**: Perfect for simple HTTP handlers

Terraform automatically creates the ZIP package from the `src/` directory.

## Environment Variables

The Lambda function requires these environment variables:
- `GITHUB_TOKEN`: GitHub token with repo permissions
- `GITHUB_OWNER`: GitHub repository owner
- `GITHUB_REPO`: GitHub repository name
- `TELEGRAM_BOT_TOKEN`: Telegram bot token
- `AUTHORIZED_CHAT_ID`: Authorized Telegram chat ID

## Commands Supported

- `/status`: Check Terraform state
- `/destroy`: Create destroy plan with token
- `/confirm_destroy <token>`: Apply destroy plan

## Security

### Runtime Security
- **Authorization**: Only authorized chat IDs can trigger commands
- **Secrets management**: GitHub token stored as environment variable
- **HTTPS**: API Gateway uses HTTPS encryption
- **Least privilege**: Lambda function has minimal IAM permissions

### Deployment Security
- **Minimal dependencies**: Only `requests` library included
- **Clean builds**: No sensitive files in deployment package
- **Log retention**: 7-day automatic cleanup prevents log accumulation
- **Managed lifecycle**: Terraform handles log group creation and destruction
