# Core Secrets Outputs
output "secrets_manager_arn" {
  description = "ARN of the Secrets Manager secret"
  value       = module.chatops.secrets_manager_arn
}

output "secrets_manager_name" {
  description = "Name of the Secrets Manager secret"
  value       = module.chatops.secrets_manager_name
}

# Webhook Handler Outputs
output "webhook_url" {
  description = "Webhook API Gateway URL"
  value       = module.chatops.webhook_url
}

output "webhook_api_key" {
  description = "Webhook API key (if enabled)"
  value       = module.chatops.webhook_api_key
  sensitive   = true
}

output "webhook_function_arn" {
  description = "ARN of the webhook handler Lambda"
  value       = module.chatops.webhook_function_arn
}

# GitHub OIDC Outputs
output "github_role_arn" {
  description = "ARN of the GitHub Actions IAM role"
  value       = module.chatops.github_role_arn
}

output "github_role_name" {
  description = "Name of the GitHub Actions IAM role"
  value       = module.chatops.github_role_name
}

output "oidc_provider_arn" {
  description = "ARN of the GitHub OIDC provider"
  value       = module.chatops.oidc_provider_arn
}

# Telegram Bot Outputs
output "telegram_bot_function_arn" {
  description = "ARN of the Telegram bot Lambda"
  value       = module.chatops.telegram_bot_function_arn
}

output "telegram_bot_function_name" {
  description = "Name of the Telegram bot Lambda"
  value       = module.chatops.telegram_bot_function_name
}

# AI Output Processor Outputs
output "ai_processor_url" {
  description = "AI processor API URL"
  value       = module.chatops.ai_processor_url
}

output "ai_processor_function_arn" {
  description = "ARN of the AI processor Lambda"
  value       = module.chatops.ai_processor_function_arn
}

output "ai_processor_function_name" {
  description = "Name of the AI processor Lambda"
  value       = module.chatops.ai_processor_function_name
}

# output "ai_processor_api_key" {
#   description = "AI processor API key"
#   value       = module.chatops.ai_processor_api_key
#   sensitive   = true
# }
