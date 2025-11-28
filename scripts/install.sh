#!/bin/bash
set -euo pipefail

# ChatOps State Manager - Installation Script
# Quick setup guide for first-time users

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing=()
    command -v terraform >/dev/null 2>&1 || missing+=("terraform")
    command -v aws >/dev/null 2>&1 || missing+=("aws-cli")
    command -v python3 >/dev/null 2>&1 || missing+=("python3")
    command -v jq >/dev/null 2>&1 || missing+=("jq")
    command -v gh >/dev/null 2>&1 || missing+=("gh (GitHub CLI)")

    if [ ${#missing[@]} -ne 0 ]; then
        log_error "Missing required tools: ${missing[*]}"
        echo ""
        echo "Install missing tools:"
        echo "  Ubuntu/Debian: sudo apt-get install terraform awscli python3 jq"
        echo "  macOS: brew install terraform awscli python3 jq gh"
        exit 1
    fi

    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        log_error "AWS credentials not configured"
        echo "Run: aws configure"
        exit 1
    fi

    log_success "All prerequisites met"
}

# Guide user through Telegram bot setup
setup_telegram_bot() {
    echo ""
    log_info "🤖 Setting Up Telegram Bot"
    echo "============================"
    echo ""
    echo "Step 1: Create a bot"
    echo "  1. Open Telegram and message @BotFather"
    echo "  2. Send: /newbot"
    echo "  3. Follow the instructions to name your bot"
    echo "  4. Copy the bot token (format: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz)"
    echo ""
    read -p "Enter your Telegram Bot Token: " TELEGRAM_BOT_TOKEN

    echo ""
    echo "Step 2: Get your Chat ID"
    echo "  1. Send any message to your new bot"
    echo "  2. Run this command (press Enter when ready):"
    echo "     curl \"https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates\""
    echo ""
    read -p "Press Enter after running the curl command above..."

    echo ""
    echo "In the JSON response, find: \"chat\":{\"id\":123456789}"
    echo "The number after \"id\": is your chat ID"
    echo ""
    read -p "Enter your Chat ID: " AUTHORIZED_CHAT_ID

    export TELEGRAM_BOT_TOKEN
    export AUTHORIZED_CHAT_ID
    log_success "Telegram bot configured"
}

# Build Lambda functions
build_lambdas() {
    log_info "Building Lambda function ZIP files..."

    if [ ! -f "$PROJECT_ROOT/build_all_lambdas.py" ]; then
        log_error "build_all_lambdas.py not found"
        exit 1
    fi

    cd "$PROJECT_ROOT"
    python3 build_all_lambdas.py

    if [ ! -f "terraform-zips/webhook-handler.zip" ] || \
       [ ! -f "terraform-zips/telegram-bot.zip" ] || \
       [ ! -f "terraform-zips/ai-output-processor.zip" ]; then
        log_error "Lambda ZIP files not created"
        exit 1
    fi

    log_success "Lambda functions built"
}

# Configure Terraform
configure_terraform() {
    log_info "Configuring Terraform..."

    cd "$TERRAFORM_DIR"

    if [ ! -f "terraform.tfvars" ]; then
        if [ ! -f "terraform.tfvars.example" ]; then
            log_error "terraform.tfvars.example not found"
            exit 1
        fi
        cp terraform.tfvars.example terraform.tfvars
        log_info "Created terraform.tfvars from example"
    fi

    # Update terraform.tfvars with provided values
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
        # Use sed to update values (basic approach)
        log_info "Updating terraform.tfvars with provided values..."
        log_warning "Please manually verify terraform.tfvars contains:"
        echo "  - telegram_bot_token = \"${TELEGRAM_BOT_TOKEN}\""
        echo "  - authorized_chat_id = \"${AUTHORIZED_CHAT_ID}\""
        echo ""
        read -p "Press Enter to continue after verifying terraform.tfvars..."
    fi

    log_success "Terraform configured"
}

# Deploy infrastructure
deploy_infrastructure() {
    log_info "Deploying infrastructure..."

    cd "$TERRAFORM_DIR"

    terraform init
    terraform plan

    echo ""
    log_warning "Review the plan above. This will create AWS resources."
    read -p "Continue with terraform apply? (yes/no): " confirm

    if [[ "$confirm" != "yes" ]]; then
        log_warning "Deployment cancelled"
        exit 0
    fi

    terraform apply

    log_success "Infrastructure deployed"
}

# Set GitHub secrets
setup_github_secrets() {
    log_info "Setting up GitHub secrets..."

    if ! command -v gh >/dev/null 2>&1; then
        log_warning "GitHub CLI not found. Please set secrets manually:"
        cd "$TERRAFORM_DIR"
        echo ""
        echo "AWS_ROLE_TO_ASSUME:"
        terraform output -raw github_role_arn 2>/dev/null || echo "  (run: terraform output github_role_arn)"
        echo ""
        echo "CALLBACK_URL:"
        terraform output -raw webhook_url 2>/dev/null || echo "  (run: terraform output webhook_url)"
        echo ""
        echo "CALLBACK_KEY:"
        terraform output -raw webhook_api_key 2>/dev/null || echo "  (run: terraform output webhook_api_key)"
        return
    fi

    cd "$TERRAFORM_DIR"

    local role_arn=$(terraform output -raw github_role_arn 2>/dev/null || echo "")
    local webhook_url=$(terraform output -raw webhook_url 2>/dev/null || echo "")
    local api_key=$(terraform output -raw webhook_api_key 2>/dev/null || echo "")

    if [ -n "$role_arn" ]; then
        gh secret set AWS_ROLE_TO_ASSUME --body "$role_arn" && log_success "Set AWS_ROLE_TO_ASSUME"
    fi

    if [ -n "$webhook_url" ]; then
        gh secret set CALLBACK_URL --body "$webhook_url" && log_success "Set CALLBACK_URL"
    fi

    if [ -n "$api_key" ] && [ "$api_key" != "null" ]; then
        gh secret set CALLBACK_KEY --body "$api_key" && log_success "Set CALLBACK_KEY"
    fi

    log_success "GitHub secrets configured"
}

# Main execution
main() {
    echo "=========================================="
    echo "  ChatOps State Manager - Installation"
    echo "=========================================="
    echo ""

    check_prerequisites
    setup_telegram_bot
    build_lambdas
    configure_terraform
    deploy_infrastructure
    setup_github_secrets

    echo ""
    log_success "🎉 Installation complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Register your first project:"
    echo "     ./scripts/register-project-from-dir.sh /path/to/terraform/project"
    echo ""
    echo "  2. Test your bot:"
    echo "     Send /help to your Telegram bot"
    echo ""
    echo "  3. Try a command:"
    echo "     Send /select to choose a project and action"
}

main "$@"
