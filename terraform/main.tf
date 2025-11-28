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
  source  = "BarryPekerman/chatops/aws"
  version = "0.1.0"

  # Core configuration
  name_prefix              = var.name_prefix
  github_owner             = var.github_owner
  github_repo              = var.github_repo
  github_branch            = var.github_branch
  github_token             = var.github_token
  telegram_bot_token       = var.telegram_bot_token
  authorized_chat_id       = var.authorized_chat_id
  s3_bucket_arn = var.s3_bucket_arn

  webhook_lambda_zip_path      = var.webhook_lambda_zip_path
  telegram_lambda_zip_path     = var.telegram_lambda_zip_path
  ai_processor_lambda_zip_path = var.ai_processor_lambda_zip_path

  enable_ai_processing = var.enable_ai_processing
  ai_model_id          = var.ai_model_id
  ai_threshold         = var.ai_threshold
  ai_max_tokens        = var.ai_max_tokens

  # Optional configuration
  max_message_length = var.max_message_length
  log_retention_days = var.log_retention_days

  enable_security_alarms = false

  tags = merge(var.tags, {
    ChatOpsManaged = var.resource_tag_value # Required for tag-based IAM policy
  })
}
