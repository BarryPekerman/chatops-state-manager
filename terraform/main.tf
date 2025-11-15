terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

module "chatops" {
  source = "../../terraform-aws-chatops"

  # Core configuration
  name_prefix              = var.name_prefix
  github_owner             = var.github_owner
  github_repo              = var.github_repo
  github_branch            = var.github_branch
  github_token             = var.github_token
  telegram_bot_token       = var.telegram_bot_token
  authorized_chat_id       = var.authorized_chat_id
  s3_bucket_arn = var.s3_bucket_arn

  # Lambda ZIP paths (3 Lambdas: webhook handler, telegram bot, AI processor)
  webhook_lambda_zip_path      = var.webhook_lambda_zip_path
  telegram_lambda_zip_path     = var.telegram_lambda_zip_path
  ai_processor_lambda_zip_path = var.ai_processor_lambda_zip_path

  # AI Processing Configuration
  # Note: AI processor Lambda always exists, but Bedrock AI is optional
  enable_ai_processing = var.enable_ai_processing
  ai_model_id          = var.ai_model_id
  ai_threshold         = var.ai_threshold
  ai_max_tokens        = var.ai_max_tokens

  # Optional configuration
  max_message_length = var.max_message_length
  log_retention_days = var.log_retention_days

  # Security features (basic setup - no added security alarms)
  # Mandatory features always enabled:
  # - AWS managed keys for Lambda env vars and CloudWatch logs (KMS wildcards removed)
  # - Dead Letter Queues for all Lambda functions
  # - X-Ray tracing for Lambda and API Gateway
  # - API Gateway access logging
  enable_security_alarms = false

  tags = merge(var.tags, {
    ChatOpsManaged = var.resource_tag_value # Required for tag-based IAM policy
  })
}
