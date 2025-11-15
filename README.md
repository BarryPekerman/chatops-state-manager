# ChatOps Terraform Module v0.1.0

**⚠️ Early Development Version - Not Production Ready ⚠️**

A Terraform module for building ChatOps workflows on AWS. This module enables you to manage infrastructure through Telegram with secure GitHub Actions integration.

**Status**: This is an early development version (v0.1.0). The module is functional but may have breaking changes, incomplete features, or undocumented behavior. Use at your own risk and test thoroughly before deploying to production environments.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         ChatOps v0.1.0                          │
│                                                                 │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐         │
│  │    Core      │   │    CI/CD     │   │     Chat     │         │
│  │              │   │              │   │              │         │
│  │  • Secrets   │   │  • GitHub    │   │  • Telegram  │         │
│  │  • Webhook   │   │    OIDC      │   │              │         │
│  │    Handler   │   │  • IAM       │   │              │         │
│  └──────────────┘   └──────────────┘   └──────────────┘         │
│                                                                 │
│  ┌─────────────────────────────────────────────────────┐        │
│  │          Separate: AI Output Processor              │        │
│  │          (Bedrock integration for long outputs)     │        │
│  └─────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

## Features

- **Telegram Integration**: Full bot integration with chat authorization
- **Secure CI/CD Integration**: GitHub OIDC authentication with least-privilege IAM
- **Centralized Secret Management**: AWS Secrets Manager for all credentials
- **Separate AI Processing**: Optional AWS Bedrock integration for output summarization
- **Observability**: CloudWatch logging, X-Ray tracing, API throttling
- **Modular Architecture**: Core module + optional AI processor

**⚠️ Note**: This is v0.1.0 - not production ready. Features may be incomplete, APIs may change, and thorough testing is required before production use.

## Quick Start

### Basic Example (No AI)

```hcl
module "chatops" {
  source  = "BarryPekerman/chatops/aws"
  version = "0.1.0"

  name_prefix        = "my-chatops"
  github_owner       = "my-org"
  github_repo        = "my-repo"
  github_token       = var.github_token
  telegram_bot_token = var.telegram_bot_token
  authorized_chat_id = var.authorized_chat_id
  s3_bucket_arn      = "arn:aws:s3:::my-terraform-state"

  webhook_lambda_zip_path      = "lambda_function.zip"
  telegram_lambda_zip_path     = "telegram-bot.zip"
  ai_processor_lambda_zip_path = "ai-output-processor.zip"  # Required even if AI is disabled
}
```

### With AI Processing

```hcl
module "chatops" {
  source  = "BarryPekerman/chatops/aws"
  version = "0.1.0"

  name_prefix        = "my-chatops"
  github_owner       = "my-org"
  github_repo        = "my-repo"
  github_token       = var.github_token
  telegram_bot_token = var.telegram_bot_token
  authorized_chat_id = var.authorized_chat_id
  s3_bucket_arn      = "arn:aws:s3:::my-terraform-state"

  webhook_lambda_zip_path      = "webhook-handler.zip"
  telegram_lambda_zip_path     = "telegram-bot.zip"
  ai_processor_lambda_zip_path = "ai-output-processor.zip"

  # Enable AI processing via AWS Bedrock
  enable_ai_processing = true
  ai_model_id          = "anthropic.claude-3-haiku-20240307-v1:0"
  ai_threshold         = 1000
  ai_max_tokens        = 1000
}
```

## Module Structure

```
target-module/
├── main.tf                          # Root module orchestration
├── variables.tf                     # User-facing inputs
├── outputs.tf                       # Module outputs
├── versions.tf                      # Provider requirements
│
├── modules/
│   ├── core/
│   │   ├── secrets/                 # Centralized secret management
│   │   └── webhook-handler/         # Main webhook processor (no AI)
│   ├── cicd/
│   │   └── github/                  # GitHub OIDC + IAM
│   └── chat/
│       └── telegram/                # Telegram bot integration
│
├── modules-optional/
│   └── ai-output-processor/         # Optional AI processing (separate)
│
└── examples/
    ├── basic/                       # Telegram + GitHub (no AI)
    └── with-ai/                     # Telegram + GitHub + AI processor
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.0 |
| aws | ~> 6.0 |
| random | ~> 3.6 |

## Providers

| Name | Version |
|------|---------|
| aws | ~> 6.0 |
| random | ~> 3.6 |

## Inputs

### Required Variables

| Name                      | Description                             | Type     |
|---------------------------|-----------------------------------------|----------|
| name_prefix               | Prefix for resource names               | `string` |
| github_owner              | GitHub repository owner/organization    | `string` |
| github_repo               | GitHub repository name                  | `string` |
| github_token              | GitHub personal access token            | `string` |
| telegram_bot_token        | Telegram bot token                      | `string` |
| authorized_chat_id        | Authorized Telegram chat ID             | `string` |
| s3_bucket_arn             | ARN of S3 bucket for Terraform state    | `string` |
| webhook_lambda_zip_path   | Path to webhook handler Lambda ZIP file | `string` |
| telegram_lambda_zip_path  | Path to Telegram bot Lambda ZIP file    | `string` |

### Optional Variables

| Name                     | Description | Type | Default |
|--------------------------|-------------|------|---------|
| github_branch            | GitHub branch for OIDC authentication      | `string` | `"main"` |
| max_message_length       | Maximum message length (simple truncation) | `number` | `3500`   |
| api_gateway_stage        | API Gateway stage name                     | `string` | `"prod"` |
| log_retention_days       | CloudWatch log retention in days           | `number` | `7`      |
| enable_xray_tracing      | Enable X-Ray tracing for API Gateway       | `bool`   | `true`   |
| rate_limit                | API Gateway rate limit (requests/second)   | `number` | `100`    |
| burst_limit               | API Gateway burst limit                    | `number` | `200`    |
| quota_limit               | API Gateway quota limit                    | `number` | `10000`  |
| quota_period              | API Gateway quota period                   | `string` | `"DAY"`  |
| webhook_api_key_required | Whether webhook API requires API key       | `bool`   | `false`  |
| tags                      | Tags to apply to all resources             | `map(string)` | `{"ManagedBy": "terraform", "Project": "chatops"}` |

## Outputs

| Name                       | Description                         |
|----------------------------|-------------------------------------|
| secrets_manager_arn        | ARN of the Secrets Manager secret   |
| secrets_manager_name       | Name of the Secrets Manager secret  |
| webhook_url                | Webhook API Gateway URL             |
| webhook_api_key            | Webhook API key (if enabled)        |
| webhook_function_arn       | ARN of the webhook handler Lambda   |
| github_role_arn            | ARN of the GitHub Actions IAM role  |
| github_role_name           | Name of the GitHub Actions IAM role |
| oidc_provider_arn          | ARN of the GitHub OIDC provider     |
| telegram_bot_function_arn  | ARN of the Telegram bot Lambda      |
| telegram_bot_function_name | Name of the Telegram bot Lambda     |

## Platform Support

### Telegram (v0.1.0)

- ✅ Bot integration
- ✅ Webhook handler
- ✅ Chat ID authorization
- ✅ Message truncation
- ✅ API Gateway integration

## Security Features

- **GitHub OIDC**: No long-lived credentials, federated authentication
- **Secrets Manager**: Centralized secret storage with automatic rotation support
- **Least Privilege IAM**: Minimal permissions for each component
- **API Gateway Security**: Rate limiting, throttling, optional API keys
- **CloudWatch Logging**: Comprehensive audit trails
- **X-Ray Tracing**: Request tracing for debugging

## Examples

See the [examples](./examples/) directory for complete usage examples:

- [Basic](./examples/basic/) - Telegram + GitHub (no AI)
- [With AI](./examples/with-ai/) - Telegram + GitHub + AI processor

## Documentation

For detailed documentation, see the [`docs/`](./docs/) directory:

- **[Project Management](./docs/PROJECT_MANAGEMENT.md)** - Managing multiple Terraform projects, provider requirements, and project registry
- **[Workflow Strategy](./docs/WORKFLOW_STRATEGY.md)** - CI/CD workflow architecture and flow
- **[Deployment Guide](./docs/DEPLOYMENT.md)** - Manual deployment procedures
- **[CI/CD Guide](./docs/CI_CD.md)** - Continuous integration and deployment
- **[Testing Guide](./docs/TESTING.md)** - Testing strategies and procedures

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR.

## Support

For issues and questions, please use GitHub Issues.
