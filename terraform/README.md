# Terraform Configuration

This directory contains the Terraform configuration for deploying the ChatOps infrastructure using the `terraform-aws-chatops` module.

## 📁 Files

- `main.tf` - Main configuration using the terraform-aws-chatops module
- `variables.tf` - Input variable definitions
- `outputs.tf` - Output value definitions
- `terraform.tfvars.example` - Example configuration (copy to `terraform.tfvars`)

## 🚀 Usage

### 1. Configure Variables

```bash
# Copy example file
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
nano terraform.tfvars
```

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Plan Deployment

```bash
terraform plan
```

### 4. Deploy Infrastructure

```bash
terraform apply
```

## 📦 Module Configuration

This configuration uses the `terraform-aws-chatops` module from the local path:
```hcl
source = "../../terraform-aws-chatops"
```

### 🔒 Built-in Security Features (Always Enabled)

The module now includes mandatory security features that cannot be disabled:
- **KMS Encryption** - All Lambda environment variables and CloudWatch logs are encrypted using AWS managed keys
- **Dead Letter Queues** - Failed Lambda invocations are captured for analysis
- **X-Ray Tracing** - Full distributed tracing for debugging and monitoring
- **365-Day Log Retention** - CloudWatch logs retained for compliance
- **API Gateway Logging** - Access logs for all API requests

### Module Inputs

**Required:**
- `name_prefix` - Prefix for all resource names
- `github_owner` - GitHub username/organization
- `github_repo` - GitHub repository name
- `github_token` - GitHub Personal Access Token
- `telegram_bot_token` - Telegram bot token from @BotFather
- `authorized_chat_id` - Your Telegram chat ID
- `s3_bucket_arn` - ARN of the S3 bucket for Terraform state

**Required Lambda ZIPs (3 total):**
- `webhook_lambda_zip_path` - Webhook handler Lambda ZIP
- `telegram_lambda_zip_path` - Telegram bot Lambda ZIP
- `ai_processor_lambda_zip_path` - AI output processor Lambda ZIP (always required)

**Optional:**
- `github_branch` - Branch for OIDC (default: `main`)
- `max_message_length` - Maximum Telegram message length (default: `3500`)

**AI Processing Configuration:**
- `enable_ai_processing` - Enable AI via AWS Bedrock (default: `false`, Lambda exists either way)
- `ai_model_id` - AWS Bedrock model ID (default: `anthropic.claude-3-haiku-20240307-v1:0`)
- `ai_threshold` - Minimum message length to trigger AI processing (default: `1000`)
- `ai_max_tokens` - Maximum tokens for AI response (cost control, default: `1000`)

**Logging & Monitoring:**
- `log_retention_days` - CloudWatch log retention in days (default: `7`)

> **Note**: The AI processor Lambda **always exists** as the 3rd Lambda. The `enable_ai_processing` flag only controls whether it uses AWS Bedrock for AI. You can implement custom processing logic in the Lambda without Bedrock.

### Security Features

**Basic Setup (Default)**:
- ✅ KMS encryption for Lambda environment variables and CloudWatch logs (using AWS managed keys)
- ✅ Dead Letter Queues for all Lambda functions
- ✅ X-Ray tracing for debugging and monitoring
- ✅ API Gateway access logging
- ✅ 7-day log retention

**Enhanced Security (Optional)**:
Set `enable_security_alarms = true` in your configuration to enable:
- CloudWatch alarms for Lambda errors, throttles, and concurrent executions
- Enhanced logging and monitoring
- Security event alerting

### Module Outputs

- `secrets_manager_arn` - ARN of the Secrets Manager secret
- `webhook_url` - API Gateway webhook URL (for Telegram)
- `github_role_arn` - IAM role ARN for GitHub Actions
- `oidc_provider_arn` - GitHub OIDC provider ARN
- `telegram_bot_function_arn` - Telegram bot Lambda ARN
- `ai_processor_url` - AI processor API Gateway URL
- `ai_processor_function_arn` - AI processor Lambda ARN
- `ai_processor_function_name` - AI processor Lambda function name

## 🔒 Security Notes

**⚠️ NEVER commit `terraform.tfvars`** - It contains sensitive secrets!

The `.gitignore` file is configured to prevent this, but always double-check:
```bash
# Verify terraform.tfvars is ignored
git status
```

All secrets should be:
- ✅ Stored in AWS Secrets Manager
- ✅ Passed via environment variables or Terraform input
- ✅ Never committed to version control

## 🛠️ Troubleshooting

### Module Not Found

If you get a "module not found" error, ensure the `terraform-aws-chatops` module exists at:
```
../../terraform-aws-chatops/
```

Adjust the `source` path in `main.tf` if your directory structure differs.

### Lambda ZIP Files Missing

The module expects Lambda ZIP files at:
```
../lambda/webhook-handler/lambda_function.zip
../lambda/telegram-bot/telegram-bot.zip
../lambda/ai-output-processor/output_processor.zip
```

Build them first:
```bash
cd ../lambda/webhook-handler && ./build.sh
cd ../lambda/telegram-bot && ./build.sh
cd ../lambda/ai-output-processor && ./build.sh
```

### State Lock Errors

If Terraform operations hang or fail with state lock errors:
```bash
# Force unlock (use carefully!)
terraform force-unlock <LOCK_ID>
```

## 📚 Additional Resources

- [Terraform AWS ChatOps Module Documentation](../../terraform-aws-chatops/README.md)
- [Main Project README](../README.md)
- [Deployment Guide](../docs/DEPLOYMENT.md)
