variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "eu-north-1"
}

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
  default     = "chatops"
}

variable "github_owner" {
  description = "GitHub repository owner/organization"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
}

variable "github_branch" {
  description = "GitHub branch for OIDC authentication"
  type        = string
  default     = "main"
}

variable "github_token" {
  description = "GitHub personal access token"
  type        = string
  sensitive   = true
}

variable "telegram_bot_token" {
  description = "Telegram bot token"
  type        = string
  sensitive   = true
}

variable "authorized_chat_id" {
  description = "Authorized Telegram chat ID"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN of S3 bucket for Terraform state"
  type        = string
}

variable "terraform_backend_bucket" {
  description = "S3 bucket name for Terraform backend (extracted from s3_bucket_arn)"
  type        = string
  default     = ""
}

variable "webhook_lambda_zip_path" {
  description = "Path to webhook handler Lambda ZIP file"
  type        = string
  default     = "lambda_function.zip"
}

variable "telegram_lambda_zip_path" {
  description = "Path to Telegram bot Lambda ZIP file"
  type        = string
  default     = "telegram-bot.zip"
}

variable "max_message_length" {
  description = "Maximum message length (simple truncation)"
  type        = number
  default     = 3500
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default = {
    Environment = "dev"
    ManagedBy   = "terraform"
    Project     = "chatops"
  }
}

variable "ai_processor_lambda_zip_path" {
  description = "Path to AI output processor Lambda ZIP file (required - 3rd Lambda)"
  type        = string
  default     = "../lambda/ai-output-processor/output_processor.zip"
}

variable "enable_ai_processing" {
  description = "Enable AI processing via AWS Bedrock (Lambda always exists, this controls Bedrock integration)"
  type        = bool
  default     = false
}

variable "ai_model_id" {
  description = "AI model ID for Bedrock"
  type        = string
  default     = "anthropic.claude-3-haiku-20240307-v1:0"
}

variable "ai_threshold" {
  description = "Minimum message length (characters) to trigger AI processing"
  type        = number
  default     = 1000
}

variable "ai_max_tokens" {
  description = "Maximum tokens for AI model response (cost control)"
  type        = number
  default     = 1000
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
}

variable "allowed_cors_origins" {
  description = "List of allowed CORS origins (default: empty, not needed for Telegram webhooks)"
  type        = list(string)
  default     = []
}

variable "resource_tag_key" {
  description = "Tag key used to identify resources managed by ChatOps (default: ChatOpsManaged)"
  type        = string
  default     = "ChatOpsManaged"
}

variable "resource_tag_value" {
  description = "Tag value for ChatOps-managed resources (default: true)"
  type        = string
  default     = "true"
}

variable "environment_tag_key" {
  description = "Tag key for environment (default: Environment)"
  type        = string
  default     = "Environment"
}

variable "environment_tag_value" {
  description = "Optional environment tag value to filter resources (null = any environment)"
  type        = string
  default     = null
}

variable "use_api_gateway" {
  description = "Whether to expose AI processor via API Gateway (default: true to preserve existing deployment, false uses direct Lambda invoke)"
  type        = bool
  default     = true
}
