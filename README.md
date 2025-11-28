# ChatOps State Manager

Manage your Terraform infrastructure through Telegram with secure GitHub Actions integration.

## Quick Setup (First-Time Users)

### Prerequisites

- AWS CLI configured with credentials
- Terraform >= 1.0 installed
- GitHub account with a repository
- Telegram account

### Step 1: Clone and Build Lambda Functions

```bash
git clone https://github.com/BarryPekerman/chatops-state-manager.git
cd chatops-state-manager

# Build Lambda ZIP files
python3 build_all_lambdas.py
```

### Step 2: Set Up Telegram Bot

1. **Create a bot:**
   - Open Telegram and message [@BotFather](https://t.me/botfather)
   - Send `/newbot` and follow the instructions
   - Copy the bot token (format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

2. **Get your Chat ID:**
   - Send a message to your new bot
   - Run: `curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates"`
   - Find your chat ID in the response: `"chat":{"id":123456789}`

### Step 3: Configure Terraform

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:
- `github_owner` - Your GitHub username/organization
- `github_repo` - Repository name
- `github_token` - GitHub Personal Access Token (create at https://github.com/settings/tokens)
- `telegram_bot_token` - Bot token from Step 2
- `authorized_chat_id` - Your chat ID from Step 2
- `s3_bucket_arn` - ARN of your Terraform state S3 bucket

### Step 4: Deploy Infrastructure

```bash
terraform init
terraform plan
terraform apply
```

### Step 5: Set Up GitHub Secrets

After deployment, set these GitHub secrets in your repository:

```bash
# Get values from Terraform outputs
terraform output -json | jq -r '.github_role_arn.value'  # AWS_ROLE_TO_ASSUME
terraform output -json | jq -r '.webhook_url.value'      # CALLBACK_URL
terraform output -json | jq -r '.webhook_api_key.value'   # CALLBACK_KEY (if enabled)

# Set secrets (requires GitHub CLI)
gh secret set AWS_ROLE_TO_ASSUME --body "<role-arn>"
gh secret set CALLBACK_URL --body "<webhook-url>"
gh secret set CALLBACK_KEY --body "<api-key>"  # Optional
```

### Step 6: Register Your First Project

```bash
# Register a Terraform project
./scripts/register-project-from-dir.sh /path/to/your/terraform/project

# Or manually add to project registry
./scripts/add-project.sh my-project s3-bucket-name state/key/path us-east-1
```

### Step 7: Test It

1. Send `/help` to your Telegram bot
2. Try `/select` to choose a project and action
3. Use `/list` to see all registered projects

**That's it!** Your ChatOps system is ready to use.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         ChatOps v0.1.3                          │
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

## Usage

### Telegram Commands

- `/select` - Select a project and action (Status or Destroy Plan)
- `/list` - List all registered projects with details
- `/help` - Show help message

### Workflow

1. Use `/select` to choose a project and action
2. Select a project from the list
3. Choose an action:
   - **Status**: Check Terraform state
   - **Destroy Plan**: Show destroy plan (review carefully!)
4. To confirm destruction, type: `/confirm_destroy <project-name>`

## Project Management

### Register a Project

```bash
# Auto-detect from Terraform directory
./scripts/register-project-from-dir.sh /path/to/terraform/project

# Manual registration
./scripts/add-project.sh project-name bucket-name state/key/path region
```

### List Projects

```bash
# Via Telegram
/list

# Via AWS CLI
aws secretsmanager get-secret-value \
  --secret-id chatops/project-registry \
  --query SecretString --output text | jq
```

## Configuration

### Terraform Variables

See `terraform/terraform.tfvars.example` for all available configuration options.

### Environment Variables

Lambda functions use environment variables configured via Terraform:
- `AUTHORIZED_CHAT_ID` - Authorized Telegram chat ID
- `GITHUB_OWNER` - GitHub repository owner
- `GITHUB_REPO` - GitHub repository name
- `PROJECT_REGISTRY_SECRET_ARN` - ARN of project registry secret

## Troubleshooting

### Bot Not Responding

1. Check CloudWatch logs: `aws logs tail /aws/lambda/chatops-webhook-handler --follow`
2. Verify Telegram webhook is set: Check API Gateway URL in Terraform outputs
3. Verify chat ID matches: Check `AUTHORIZED_CHAT_ID` environment variable

### GitHub Actions Not Triggering

1. Verify GitHub secrets are set: `gh secret list`
2. Check IAM role ARN matches: Compare `AWS_ROLE_TO_ASSUME` secret with Terraform output
3. Verify repository dispatch event is configured in workflow

### Project Not Found

1. Verify project is registered: `./scripts/check-secrets.sh`
2. Check project registry: `aws secretsmanager get-secret-value --secret-id chatops/project-registry`
3. Ensure project is enabled: Check `enabled: true` in registry

## Scripts

- `scripts/bootstrap.sh` - Automated setup (deploys infrastructure and configures secrets)
- `scripts/nuke-everything.sh` - Complete teardown (destroys all infrastructure)
- `scripts/add-project.sh` - Add a project to the registry
- `scripts/register-project-from-dir.sh` - Auto-register from Terraform directory
- `scripts/check-secrets.sh` - Verify secrets configuration

## Module Information

This project uses the `terraform-aws-chatops` module:

```hcl
module "chatops" {
  source  = "BarryPekerman/chatops/aws"
  version = "0.1.0"
  # ... configuration
}
```

See [terraform/README.md](terraform/README.md) for detailed module configuration.

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR.

## Support

For issues and questions, please use GitHub Issues.
