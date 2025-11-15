# Telegram Bot Infrastructure

This directory contains the infrastructure and code for the Telegram bot component of the ChatOps system.

## 📁 Directory Structure

```
telegram-bot/
├── terraform/           # Terraform configuration for bot infrastructure
│   ├── main.tf         # Main Terraform configuration
│   ├── variables.tf    # Input variables
│   ├── outputs.tf      # Output values
│   ├── terraform.tfvars.example  # Example variables file
│   └── terraform.tfvars         # Actual variables file
├── src/                # Bot source code
│   ├── bot.py          # Lambda function code
│   └── requirements.txt # Python dependencies
├── build_bot.sh        # Build script for Lambda package
├── test_bot.sh         # Test script for bot Lambda
├── setup_webhook.sh    # Telegram webhook configuration
└── README.md           # This file
```

## 🏗️ Architecture

The Telegram bot is deployed as a **Lambda function** that:

1. **Receives Telegram webhooks** via API Gateway
2. **Validates authorized users** (chat ID check)
3. **Forwards commands** to the main webhook handler
4. **Handles Telegram-specific logic** (message parsing, authorization)

### Flow:
```
Telegram → Bot API Gateway → Bot Lambda → Main API Gateway → Webhook Lambda → GitHub Actions
```

## 🚀 Deployment

### Option 1: Complete Automated Setup (Recommended)

Use the complete automated setup script for a hands-off experience:

```bash
# Complete automated setup
./setup_chatops.sh
```

This script will:
- ✅ Check prerequisites
- ✅ Guide you through bot creation
- ✅ Automatically configure Terraform
- ✅ Deploy infrastructure
- ✅ Set up webhook
- ✅ Verify everything works

### Option 2: Simple Bot Setup

For just the bot component:

```bash
# Simple bot setup
./setup_simple.sh
```

### Option 3: Manual Setup

If you prefer manual control:

#### Prerequisites

1. **Main infrastructure deployed**: The webhook handler Lambda and API Gateway must be deployed first
2. **Get outputs**: You need the main API Gateway URL and API key
3. **Telegram bot token**: Create a bot via @BotFather on Telegram
4. **Authorized chat ID**: Get your Telegram chat ID

#### Step 1: Configure Variables

```bash
cd telegram-bot/terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:

```hcl
aws_region         = "eu-north-1"
project_name      = "chatops-terraform-manager"
environment       = "dev"

# Get these from lambda-infrastructure outputs
api_gateway_url   = "https://your-webhook-api-gateway-url"
api_gateway_key   = "your-webhook-api-gateway-key"

# Telegram configuration
telegram_bot_token = "YOUR_TELEGRAM_BOT_TOKEN"
authorized_chat_id = "YOUR_TELEGRAM_CHAT_ID"
```

#### Step 2: Deploy Infrastructure

```bash
cd telegram-bot/terraform
terraform init
terraform plan
terraform apply
```

#### Step 3: Configure Telegram Webhook

After deployment, get the bot webhook URL:

```bash
terraform output bot_webhook_url
```

Set the webhook URL in Telegram:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://your-bot-api-gateway-url/webhook"
```

## 🔧 Configuration

### Environment Variables

The bot Lambda receives these environment variables:

- `API_GATEWAY_URL`: URL of the main webhook API Gateway
- `API_GATEWAY_KEY`: API key for the main webhook
- `TELEGRAM_BOT_TOKEN`: Telegram bot token
- `AUTHORIZED_CHAT_ID`: Authorized Telegram chat ID

### Security

- **API Key Authentication**: Bot API Gateway uses API keys
- **Chat ID Validation**: Only authorized chat IDs can send commands
- **Rate Limiting**: API Gateway has throttling configured
- **Logging**: All requests are logged to CloudWatch

## 🔧 Available Scripts

This directory includes several scripts for different deployment scenarios:

### `build_bot.sh` - Lambda Package Builder
**Purpose**: Creates ZIP package for Lambda deployment

**What it does**:
- Copies source files to temporary directory
- Installs Python dependencies (`requests`, etc.)
- Creates `telegram-bot.zip` for Lambda deployment
- Cleans up temporary files

**Usage**:
```bash
# Called automatically during deployment
./build_bot.sh

# Manual usage (when you need to rebuild package)
cd telegram-bot
./build_bot.sh
```

**When to use**:
- ✅ **Automatic**: Called by main install script
- ✅ **Manual**: When you need to rebuild the Lambda package
- ✅ **Development**: After changing bot source code

### `setup_simple.sh` - Interactive Bot Setup
**Purpose**: Step-by-step interactive setup for Telegram bot

**What it does**:
- Checks prerequisites (terraform, AWS credentials)
- Prompts for Telegram bot token
- Guides you through getting chat ID
- Deploys infrastructure with terraform
- Sets up webhook URL automatically
- Configures bot commands

**Usage**:
```bash
# Interactive setup with prompts
./setup_simple.sh
```

**When to use**:
- ✅ **Manual setup**: When you want step-by-step control
- ✅ **Troubleshooting**: When automated setup fails
- ✅ **Development**: When testing bot changes
- ✅ **Learning**: To understand the setup process

**Requirements**:
- Terraform installed
- AWS credentials configured
- Telegram bot token (will prompt if not set)

### `setup_webhook.sh` - Webhook Configuration Only
**Purpose**: Configure Telegram webhook URL only

**What it does**:
- Sets webhook URL for the bot
- Verifies webhook is working
- Shows webhook information
- Tests webhook connectivity

**Usage**:
```bash
# Set required environment variables
export TELEGRAM_BOT_TOKEN="your_bot_token"
export BOT_WEBHOOK_URL="https://your-api-gateway-url/webhook"

# Configure webhook
./setup_webhook.sh
```

**When to use**:
- ✅ **Webhook issues**: When webhook stops working
- ✅ **URL changes**: When API Gateway URL changes
- ✅ **Quick fix**: Just need to update webhook URL
- ✅ **Troubleshooting**: When bot doesn't receive messages

**Requirements**:
- `TELEGRAM_BOT_TOKEN` environment variable
- `BOT_WEBHOOK_URL` environment variable
- Infrastructure already deployed

## 🎯 Script Usage Guide

### Automated Setup (Recommended)
```bash
# Main install script handles everything automatically
./install.sh
```
This orchestrates all scripts in the correct order.

### Manual Setup Options

#### Option 1: Complete Interactive Setup
```bash
# Step-by-step setup with prompts
./setup_simple.sh
```

#### Option 2: Infrastructure + Webhook
```bash
# Build and deploy infrastructure
./build_bot.sh
cd terraform
terraform apply

# Configure webhook
export TELEGRAM_BOT_TOKEN="your_token"
export BOT_WEBHOOK_URL="your_webhook_url"
./setup_webhook.sh
```

#### Option 3: Webhook Only
```bash
# Just update webhook (infrastructure already exists)
export TELEGRAM_BOT_TOKEN="your_token"
export BOT_WEBHOOK_URL="your_webhook_url"
./setup_webhook.sh
```

#### Option 4: Package Rebuild
```bash
# Rebuild Lambda package (after code changes)
./build_bot.sh
cd terraform
terraform apply
```

## 🧪 Testing

### Test Bot Lambda Directly

```bash
# Test with sample Telegram webhook
aws lambda invoke \
  --function-name chatops-terraform-manager-telegram-bot \
  --payload '{"body":"{\"message\":{\"chat\":{\"id\":123456},\"text\":\"/status\"}}"}' \
  response.json
```

### Test Bot API Gateway

```bash
# Test webhook endpoint
curl -X POST "https://your-bot-api-gateway-url/webhook" \
  -H "Content-Type: application/json" \
  -d '{"message":{"chat":{"id":123456},"text":"/status"}}'
```

## 📊 Monitoring

### CloudWatch Logs

- **Log Group**: `/aws/lambda/chatops-terraform-manager-telegram-bot`
- **Retention**: 7 days
- **Log Level**: INFO

### Key Metrics

- **Invocations**: Number of webhook calls
- **Errors**: Failed webhook processing
- **Duration**: Processing time
- **Throttles**: Rate limiting events

## 🔄 Updates

### Update Bot Code

```bash
cd telegram-bot/terraform
terraform apply  # Rebuilds and deploys Lambda
```

### Update Configuration

```bash
# Edit terraform.tfvars
terraform plan
terraform apply
```

## 🗑️ Cleanup

```bash
cd telegram-bot/terraform
terraform destroy
```

## 🔗 Integration

The bot integrates with:

1. **Main Webhook Handler**: Forwards commands to main API Gateway
2. **GitHub Actions**: Triggers workflows via main webhook
3. **Telegram API**: Receives webhooks from Telegram

## 📝 Notes

- **Separation**: Bot infrastructure is separate from main webhook infrastructure for better organization
- **Scalability**: Lambda automatically scales with Telegram webhook volume
- **Serverless**: No server management required - fully serverless deployment
