#!/bin/bash
set -euo pipefail

# ChatOps Terraform Manager - Unified Installation Script
# Target: 15-minute setup from clone to working system

echo "🤖 ChatOps Terraform Manager - Quick Setup"
echo "========================================="
echo ""

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AWS_REGION="${AWS_REGION:-eu-north-1}"
SETUP_START_TIME=$(date +%s)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }
log_step() { echo -e "${PURPLE}🔄 $1${NC}"; }

# Progress tracking
TOTAL_STEPS=8
CURRENT_STEP=0

show_progress() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo ""
    echo "Progress: $CURRENT_STEP/$TOTAL_STEPS - $1"
    echo "----------------------------------------"
}

# Check if this is a fresh installation
check_fresh_installation() {
    log_info "Checking if this is a fresh installation..."

    # Check for existing GitHub secrets
    local existing_secrets=$(gh secret list 2>/dev/null | wc -l || echo "0")
    existing_secrets=$(echo "$existing_secrets" | tr -d ' \n')

    if [ "$existing_secrets" -eq 0 ]; then
        log_success "Fresh installation detected - no existing secrets found"
        FRESH_INSTALL=true
    else
        log_warning "Existing secrets found - this may be an update installation"
        FRESH_INSTALL=false
    fi
}

# Template processing with envsubst
process_template() {
    local template_file="$1"
    local output_file="$2"

    if [ ! -f "$template_file" ]; then
        log_error "Template file not found: $template_file"
        return 1
    fi

    log_info "Processing template: $template_file -> $output_file"
    envsubst < "$template_file" > "$output_file"

    if [ $? -eq 0 ]; then
        log_success "Template processed successfully"
    else
        log_error "Failed to process template"
        return 1
    fi
}

# Check prerequisites
check_prerequisites() {
    show_progress "Checking prerequisites"

    local missing_tools=()
    command -v terraform >/dev/null 2>&1 || missing_tools+=("terraform")
    command -v aws >/dev/null 2>&1 || missing_tools+=("aws")
    command -v jq >/dev/null 2>&1 || missing_tools+=("jq")
    command -v curl >/dev/null 2>&1 || missing_tools+=("curl")
    command -v git >/dev/null 2>&1 || missing_tools+=("git")
    command -v openssl >/dev/null 2>&1 || missing_tools+=("openssl")
    command -v envsubst >/dev/null 2>&1 || missing_tools+=("envsubst")

    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        echo ""
        echo "Please install the missing tools:"
        echo "  Ubuntu/Debian: sudo apt-get install terraform awscli jq curl git"
        echo "  macOS: brew install terraform awscli jq curl git"
        echo "  Or visit: https://terraform.io, https://aws.amazon.com/cli/"
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        log_error "AWS credentials not configured"
        echo ""
        echo "Please configure AWS credentials:"
        echo "  aws configure"
        echo "  Or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
        exit 1
    fi

    # Check if we're in the right directory
    if [[ ! -f "README.md" ]] || [[ ! -d "lambda" ]]; then
        log_error "Please run this script from the project root directory"
        exit 1
    fi

    log_success "All prerequisites met"
}

# Load configuration from file if it exists
load_configuration() {
    local config_file="${PROJECT_DIR}/install.conf"

    if [[ -f "$config_file" ]]; then
        log_info "Loading configuration from install.conf..."
        source "$config_file"

        # Export only non-sensitive variables to child processes
        export GITHUB_OWNER GITHUB_REPO
        export S3_BUCKET_NAME S3_STATE_KEY S3_STATE_KEY_PREFIX
        export AUTHORIZED_CHAT_ID
        export AWS_REGION
        export ENABLE_AI_PROCESSING MAX_MESSAGE_LENGTH MAX_MESSAGES AI_THRESHOLD

        # Keep sensitive variables local (not exported)
        # GITHUB_TOKEN, TELEGRAM_BOT_TOKEN remain local to this function

        log_success "Configuration loaded from file"
        return 0
    else
        log_info "No install.conf found - will prompt for configuration"
        return 1
    fi
}

# Get configuration from user
get_configuration() {
    show_progress "Gathering configuration"

    # Try to load from config file first
    if load_configuration; then
        log_info "Using configuration from install.conf"
        # Validate required variables are set
        local missing_vars=()
        [[ -z "${GITHUB_OWNER:-}" ]] && missing_vars+=("GITHUB_OWNER")
        [[ -z "${GITHUB_REPO:-}" ]] && missing_vars+=("GITHUB_REPO")
        [[ -z "${GITHUB_TOKEN:-}" ]] && missing_vars+=("GITHUB_TOKEN")
        [[ -z "${S3_BUCKET_NAME:-}" ]] && missing_vars+=("S3_BUCKET_NAME")
        [[ -z "${S3_STATE_KEY:-}" ]] && missing_vars+=("S3_STATE_KEY")
        [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]] && missing_vars+=("TELEGRAM_BOT_TOKEN")
        [[ -z "${AUTHORIZED_CHAT_ID:-}" ]] && missing_vars+=("AUTHORIZED_CHAT_ID")

        if [ ${#missing_vars[@]} -ne 0 ]; then
            log_error "Missing required variables in install.conf: ${missing_vars[*]}"
            echo "Please check your install.conf file and ensure all required variables are set."
            exit 1
        fi

        log_success "All required configuration loaded from file"
        return 0
    fi

    echo ""
    if [ "$FRESH_INSTALL" = true ]; then
        log_info "🎉 Fresh installation detected! Let's set up your ChatOps system from scratch..."
        echo ""
        echo "This will create:"
        echo "• AWS infrastructure (Lambda, API Gateway, IAM roles)"
        echo "• GitHub Actions integration"
        echo "• Telegram bot configuration"
        echo "• All necessary secrets and permissions"
        echo ""
    else
        log_info "Let's configure your ChatOps system..."
    fi
    echo ""

    # GitHub configuration
    if [[ -z "${GITHUB_OWNER:-}" ]]; then
        echo "📝 GitHub Configuration"
        echo "======================"
        read -p "GitHub username/organization: " GITHUB_OWNER
    fi

    if [[ -z "${GITHUB_REPO:-}" ]]; then
        read -p "GitHub repository name: " GITHUB_REPO
    fi

    if [[ -z "${GITHUB_TOKEN:-}" ]]; then
        echo ""
        echo "🔑 GitHub Token (for repository secrets)"
        echo "======================================"
        echo "Create a token at: https://github.com/settings/tokens"
        echo "Required scopes: repo, admin:org (if organization)"
        read -p "GitHub Token: " GITHUB_TOKEN
    fi

    # S3 backend configuration
    echo ""
    echo "🗄️  S3 Backend Configuration"
    echo "=========================="
    echo "Enter your existing S3 bucket for Terraform state:"
    if [[ -z "${S3_BUCKET_NAME:-}" ]]; then
        read -p "S3 Bucket Name: " S3_BUCKET_NAME
    fi

    if [[ -z "${S3_STATE_KEY:-}" ]]; then
        read -p "State file key (e.g., dev/terraform.tfstate): " S3_STATE_KEY
    fi

    # Telegram bot configuration
    echo ""
    echo "🤖 Telegram Bot Configuration"
    echo "============================"
    echo "1. Message @BotFather on Telegram"
    echo "2. Send /newbot"
    echo "3. Follow the instructions"
    echo "4. Copy the bot token"
    echo ""
    if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
        read -p "Telegram Bot Token: " TELEGRAM_BOT_TOKEN
    fi

    echo ""
    echo "To get your chat ID:"
    echo "1. Send a message to your bot"
    echo "2. Run: curl 'https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates'"
    echo "3. Look for 'chat':{'id':123456789} in the response"
    echo ""
    if [[ -z "${AUTHORIZED_CHAT_ID:-}" ]]; then
        read -p "Your Chat ID: " AUTHORIZED_CHAT_ID
    fi

    # Optional: AI-powered output processing
    echo ""
    echo "🧠 AI-Powered Output Processing (Optional)"
    echo "=========================================="
    echo "Enable smart summarization using AWS Bedrock? (adds ~$0.50/month)"
    read -p "Enable AI processing? (y/N): " ENABLE_AI_PROCESSING

    if [[ "${ENABLE_AI_PROCESSING:-n}" =~ ^[Yy]$ ]]; then
        export ENABLE_AI_PROCESSING="true"
        log_info "AI processing enabled - outputs will be intelligently summarized"
    else
        export ENABLE_AI_PROCESSING="false"
        log_info "AI processing disabled - using simple formatting"
    fi

    log_success "Configuration gathered"
}

# Create AWS Secrets Manager secrets
create_aws_secrets() {
    log_step "Creating AWS Secrets Manager secrets..."

    # Generate Telegram secret token (local variable, not exported)
    local TELEGRAM_SECRET_TOKEN="$(openssl rand -hex 16)"

    # Create GitHub token secret
    aws secretsmanager create-secret \
        --name "chatops/github-token" \
        --description "GitHub token for ChatOps Terraform Manager" \
        --secret-string "${GITHUB_TOKEN}" \
        --region "${AWS_REGION}" \
        --tags Key=Project,Value=chatops Key=Environment,Value=dev Key=ManagedBy,Value=terraform \
        >/dev/null 2>&1 || log_warning "GitHub token secret may already exist"

    # Create Telegram bot token secret
    aws secretsmanager create-secret \
        --name "chatops/telegram-bot-token" \
        --description "Telegram bot token for ChatOps" \
        --secret-string "${TELEGRAM_BOT_TOKEN}" \
        --region "${AWS_REGION}" \
        --tags Key=Project,Value=chatops Key=Environment,Value=dev Key=ManagedBy,Value=terraform \
        >/dev/null 2>&1 || log_warning "Telegram bot token secret may already exist"

    # Create Telegram secret token
    aws secretsmanager create-secret \
        --name "chatops/telegram-secret-token" \
        --description "Telegram webhook secret token" \
        --secret-string "${TELEGRAM_SECRET_TOKEN}" \
        --region "${AWS_REGION}" \
        --tags Key=Project,Value=chatops Key=Environment,Value=dev Key=ManagedBy,Value=terraform \
        >/dev/null 2>&1 || log_warning "Telegram secret token secret may already exist"

    log_success "AWS Secrets Manager secrets created"
}

# Deploy infrastructure
deploy_infrastructure() {
    show_progress "Deploying infrastructure"

    log_info "Deploying all infrastructure components..."

    # Create AWS secrets first
    create_aws_secrets

    # GitHub integration
    log_step "Setting up GitHub integration..."
    cd "${PROJECT_DIR}/github-integration"

    # Set template variables
    export S3_STATE_KEY_PREFIX="$(dirname "${S3_STATE_KEY}")"

    # Process template
    process_template "${PROJECT_DIR}/templates/github-integration.tfvars.template" "terraform.tfvars"

    terraform init -upgrade
    terraform plan
    terraform apply -auto-approve

    # Get outputs
    AWS_ROLE_TO_ASSUME=$(terraform output -json github_secrets | jq -r '.AWS_ROLE_TO_ASSUME')
    SECRET_NAME=$(terraform output -json github_secrets | jq -r '.SECRET_NAME')

    # Lambda infrastructure
    log_step "Setting up Lambda infrastructure..."
    cd "${PROJECT_DIR}/lambda-infrastructure"

    # Build Lambda function zip files
    log_info "Building Lambda function packages..."
    if [[ -f "build_lambda.sh" ]]; then
        ./build_lambda.sh
        log_success "Lambda function packages built"
    else
        log_error "build_lambda.sh not found in lambda-infrastructure directory"
        exit 1
    fi

    # Set template variables

    # Process template
    process_template "${PROJECT_DIR}/templates/lambda-infrastructure.tfvars.template" "terraform.tfvars"

    terraform init -upgrade
    terraform plan
    terraform apply -auto-approve

    # Get outputs
    API_GATEWAY_URL=$(terraform output -raw ai_processor_url)
    API_GATEWAY_KEY=$(terraform output -raw ai_processor_api_key)

    # Create API Gateway key secret
    aws secretsmanager create-secret \
        --name "chatops/api-gateway-key" \
        --description "API Gateway key for ChatOps" \
        --secret-string "${API_GATEWAY_KEY}" \
        --region "${AWS_REGION}" \
        --tags Key=Project,Value=chatops Key=Environment,Value=dev Key=ManagedBy,Value=terraform \
        >/dev/null 2>&1 || log_warning "API Gateway key secret may already exist"

    # Telegram bot
    log_step "Setting up Telegram bot..."
    cd "${PROJECT_DIR}/telegram-bot"

    # Build Telegram bot zip file
    log_info "Building Telegram bot package..."
    if [[ -f "build_bot.sh" ]]; then
        ./build_bot.sh
        log_success "Telegram bot package built"
    else
        log_error "build_bot.sh not found in telegram-bot directory"
        exit 1
    fi

    # Process template
    process_template "${PROJECT_DIR}/templates/telegram-bot.tfvars.template" "terraform/terraform.tfvars"

    cd terraform
    terraform init -upgrade
    terraform plan
    terraform apply -auto-approve

    # Get webhook URL from lambda-infrastructure (the main webhook handler)
    cd "${PROJECT_DIR}/lambda-infrastructure"
    BOT_WEBHOOK_URL=$(terraform output -raw webhook_url)
    cd "${PROJECT_DIR}/telegram-bot"

    log_success "Infrastructure deployed successfully"
}

# Configure services
configure_services() {
    show_progress "Configuring services"

    # Set Telegram webhook
    log_step "Configuring Telegram webhook..."
    curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
      -d "url=${BOT_WEBHOOK_URL}" \
      -H "Content-Type: application/x-www-form-urlencoded"

    # Set bot commands
    log_step "Setting up bot commands..."
    curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setMyCommands" \
      -H "Content-Type: application/json" \
      -d '{
        "commands": [
          {"command": "select", "description": "Select a project and action"},
          {"command": "list", "description": "List all registered projects"},
          {"command": "help", "description": "Show help message"}
        ]
      }'

    # Configure GitHub secrets
    log_step "Configuring GitHub secrets..."
    if command -v gh >/dev/null 2>&1; then
        gh secret set AWS_REGION --body "${AWS_REGION}"
        gh secret set AWS_ROLE_TO_ASSUME --body "${AWS_ROLE_TO_ASSUME}"
        gh secret set TELEGRAM_BOT_TOKEN --body "${TELEGRAM_BOT_TOKEN}"
        gh secret set TELEGRAM_CHAT_ID --body "${AUTHORIZED_CHAT_ID}"
        gh secret set CALLBACK_URL --body "${API_GATEWAY_URL}"
        gh secret set CALLBACK_KEY --body "${API_GATEWAY_KEY}"
        log_success "GitHub secrets configured"
    else
        log_warning "GitHub CLI not found - please set secrets manually:"
        echo "  AWS_REGION: ${AWS_REGION}"
        echo "  AWS_ROLE_TO_ASSUME: ${AWS_ROLE_TO_ASSUME}"
        echo "  TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}"
        echo "  TELEGRAM_CHAT_ID: ${AUTHORIZED_CHAT_ID}"
        echo "  CALLBACK_URL: ${API_GATEWAY_URL}"
        echo "  CALLBACK_KEY: ${API_GATEWAY_KEY}"
    fi

    log_success "Services configured"
}

# Test the setup
test_setup() {
    show_progress "Testing setup"

    log_info "Running system tests..."

    # Test Lambda function
    log_step "Testing Lambda function..."
    cd "${PROJECT_DIR}/lambda-infrastructure"
    if [[ -f "test_lambda_quick.sh" ]]; then
        if ./test_lambda_quick.sh; then
            log_success "Lambda function test passed"
        else
            log_warning "Lambda function test failed - check CloudWatch logs"
        fi
    fi

    # Test GitHub Actions workflow
    log_step "Testing GitHub Actions workflow..."
    if command -v gh >/dev/null 2>&1; then
        gh workflow run "Telegram ChatOps - Terraform Manager" -f command=status || log_warning "GitHub Actions test failed"
        log_info "GitHub Actions workflow triggered - check the Actions tab"
    fi

    log_success "Testing completed"
}

# Show completion summary
show_summary() {
    show_progress "Setup complete"

    local setup_time=$(( $(date +%s) - SETUP_START_TIME ))
    local minutes=$(( setup_time / 60 ))
    local seconds=$(( setup_time % 60 ))

    echo ""
    log_success "🎉 ChatOps Terraform Manager setup complete!"
    echo ""
    echo "⏱️  Setup time: ${minutes}m ${seconds}s"
    echo ""
    echo "📋 What was deployed:"
    echo "===================="
    echo "✅ GitHub integration (OIDC, IAM roles, Secrets Manager)"
    echo "✅ Lambda infrastructure (webhook handler, API Gateway)"
    echo "✅ Telegram bot (webhook, commands, authorization)"
    if [[ "${ENABLE_AI_PROCESSING}" == "true" ]]; then
        echo "✅ AI-powered output processing (Bedrock integration)"
    fi
    echo "✅ GitHub secrets configured"
    echo "✅ Telegram webhook configured"
    echo ""
    echo "🔗 Important URLs:"
    echo "=================="
    echo "Main API Gateway: ${API_GATEWAY_URL}"
    echo "Bot Webhook: ${BOT_WEBHOOK_URL}"
    echo "GitHub Actions: https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/actions"
    echo ""
    echo "🧪 Test your setup:"
    echo "==================="
    echo "1. Send a message to your Telegram bot"
    echo "2. Try: /status"
    echo "3. Try: /destroy"
    echo "4. Check GitHub Actions for workflow runs"
    echo ""
    echo "📚 Documentation:"
    echo "================="
    echo "- Main README: README.md"
    echo "- Setup Guide: SETUP.md"
    echo "- Bot README: telegram-bot/README.md"
    echo ""
    echo "🎯 Your ChatOps system is ready to use!"
    echo ""
    echo "💡 Pro tip: Check CloudWatch logs if you encounter issues:"
    echo "   aws logs tail /aws/lambda/chatops-telegram-webhook --follow"
}

# Main execution
main() {
    echo "Starting ChatOps Terraform Manager setup..."
    echo "Target: 15-minute setup from clone to working system"
    echo ""

    check_fresh_installation
    check_prerequisites
    get_configuration

    echo ""
    log_info "Starting deployment process..."
    echo "This may take 5-10 minutes depending on your AWS region..."
    echo ""

    deploy_infrastructure
    configure_services
    test_setup
    show_summary
}

# Handle script interruption
trap 'echo ""; log_error "Setup interrupted by user"; exit 1' INT TERM

# Run main function
main "$@"
