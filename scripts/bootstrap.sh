#!/bin/bash
set -euo pipefail

# Bootstrap script for ChatOps setup
# This script automates the initial setup:
# 1. Deploy Terraform (creates OIDC role)
# 2. Extract role ARN from Terraform output
# 3. Set GitHub secrets using Ansible

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"
ANSIBLE_DIR="$PROJECT_ROOT/ansible"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_step() {
    echo -e "${GREEN}==>${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_step "Checking prerequisites..."

    local missing=0

    if ! command -v terraform &> /dev/null; then
        print_error "Terraform not found. Please install Terraform."
        missing=1
    fi

    if ! command -v ansible-playbook &> /dev/null; then
        print_error "Ansible not found. Please install Ansible."
        missing=1
    fi

    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 not found. Please install Python 3."
        missing=1
    fi

    if [ -z "${GITHUB_TOKEN:-}" ]; then
        print_error "GITHUB_TOKEN environment variable not set."
        print_warning "Set it with: export GITHUB_TOKEN=your_token"
        missing=1
    fi

    if [ -z "${AWS_REGION:-}" ]; then
        print_warning "AWS_REGION not set. Defaulting to eu-north-1"
        export AWS_REGION=eu-north-1
    fi

    if [ $missing -eq 1 ]; then
        exit 1
    fi

    print_success "All prerequisites met"
}

# Check if Terraform is initialized
check_terraform_init() {
    print_step "Checking Terraform initialization..."

    if [ ! -d "$TERRAFORM_DIR/.terraform" ]; then
        print_warning "Terraform not initialized. Running terraform init..."
        cd "$TERRAFORM_DIR"
        terraform init
        print_success "Terraform initialized"
    else
        print_success "Terraform already initialized"
    fi
}

# Deploy Terraform
deploy_terraform() {
    print_step "Deploying Terraform infrastructure..."

    cd "$TERRAFORM_DIR"

    # Check if terraform.tfvars exists
    if [ ! -f "terraform.tfvars" ]; then
        print_error "terraform.tfvars not found!"
        print_warning "Please create terraform.tfvars from terraform.tfvars.example"
        exit 1
    fi

    # Run terraform plan first
    print_step "Running terraform plan..."
    if ! terraform plan -out=tfplan; then
        print_error "Terraform plan failed"
        exit 1
    fi

    # Apply
    print_step "Applying Terraform changes..."
    if ! terraform apply tfplan; then
        print_error "Terraform apply failed"
        exit 1
    fi

    print_success "Terraform deployment complete"
}

# Extract Terraform outputs
extract_outputs() {
    print_step "Extracting Terraform outputs..."

    cd "$TERRAFORM_DIR"

    # Get outputs
    GITHUB_ROLE_ARN=$(terraform output -raw github_role_arn 2>/dev/null || echo "")
    WEBHOOK_URL=$(terraform output -raw webhook_url 2>/dev/null || echo "")
    AI_PROCESSOR_URL=$(terraform output -raw ai_processor_url 2>/dev/null || echo "")
    AI_PROCESSOR_API_KEY=$(terraform output -raw ai_processor_api_key 2>/dev/null || echo "")

    if [ -z "$GITHUB_ROLE_ARN" ]; then
        print_error "Failed to extract github_role_arn from Terraform output"
        exit 1
    fi

    print_success "Extracted outputs:"
    echo "  - GitHub Role ARN: $GITHUB_ROLE_ARN"
    echo "  - Webhook URL: ${WEBHOOK_URL:-not available}"
    echo "  - AI Processor URL: ${AI_PROCESSOR_URL:-not available}"

    # Export for Ansible
    export TF_OUTPUT_GITHUB_ROLE_ARN="$GITHUB_ROLE_ARN"
    export TF_OUTPUT_WEBHOOK_URL="$WEBHOOK_URL"
    export TF_OUTPUT_AI_PROCESSOR_URL="$AI_PROCESSOR_URL"
    export TF_OUTPUT_AI_PROCESSOR_API_KEY="$AI_PROCESSOR_API_KEY"
}

# Get GitHub repo info from Terraform
get_github_info() {
    print_step "Getting GitHub repository information..."

    cd "$TERRAFORM_DIR"

    # Try to get from terraform.tfvars or variables
    GITHUB_OWNER=$(grep -E '^\s*github_owner\s*=' terraform.tfvars 2>/dev/null | cut -d'"' -f2 | head -1 || echo "")
    GITHUB_REPO=$(grep -E '^\s*github_repo\s*=' terraform.tfvars 2>/dev/null | cut -d'"' -f2 | head -1 || echo "")

    if [ -z "$GITHUB_OWNER" ] || [ -z "$GITHUB_REPO" ]; then
        print_warning "Could not extract GitHub info from terraform.tfvars"
        print_warning "Please set GITHUB_OWNER and GITHUB_REPO environment variables"

        if [ -z "${GITHUB_OWNER:-}" ] || [ -z "${GITHUB_REPO:-}" ]; then
            print_error "GITHUB_OWNER and GITHUB_REPO must be set"
            exit 1
        fi
    else
        export GITHUB_OWNER
        export GITHUB_REPO
    fi

    print_success "GitHub repo: $GITHUB_OWNER/$GITHUB_REPO"
}

# Get other required secrets
get_secrets() {
    print_step "Collecting required secrets..."

    # Check for required environment variables or prompt
    if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
        print_warning "TELEGRAM_BOT_TOKEN not set in environment"
        read -p "Enter Telegram Bot Token: " TELEGRAM_BOT_TOKEN
        export TELEGRAM_BOT_TOKEN
    fi

    if [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
        print_warning "TELEGRAM_CHAT_ID not set in environment"
        read -p "Enter Telegram Chat ID: " TELEGRAM_CHAT_ID
        export TELEGRAM_CHAT_ID
    fi

    if [ -z "${TERRAFORM_STATE_BUCKET:-}" ]; then
        print_warning "TERRAFORM_STATE_BUCKET not set in environment"
        read -p "Enter Terraform State S3 Bucket: " TERRAFORM_STATE_BUCKET
        export TERRAFORM_STATE_BUCKET
    fi

    print_success "Secrets collected"
}

# Create Ansible vars file
create_ansible_vars() {
    print_step "Creating Ansible variables file..."

    local vars_file="$ANSIBLE_DIR/vars/bootstrap-secrets.yml"

    cat > "$vars_file" <<EOF
# Auto-generated by bootstrap.sh - DO NOT EDIT MANUALLY
github_owner: "${GITHUB_OWNER}"
github_repo: "${GITHUB_REPO}"

github_secrets:
  AWS_ROLE_TO_ASSUME: "${TF_OUTPUT_GITHUB_ROLE_ARN}"
  AWS_REGION: "${AWS_REGION:-eu-north-1}"
  TERRAFORM_STATE_BUCKET: "${TERRAFORM_STATE_BUCKET}"
  TELEGRAM_BOT_TOKEN: "${TELEGRAM_BOT_TOKEN}"
  TELEGRAM_CHAT_ID: "${TELEGRAM_CHAT_ID}"
EOF

    # Add optional secrets if available
    if [ -n "${TF_OUTPUT_AI_PROCESSOR_URL:-}" ]; then
        echo "  CALLBACK_URL: \"${TF_OUTPUT_AI_PROCESSOR_URL}\"" >> "$vars_file"
    fi

    if [ -n "${TF_OUTPUT_AI_PROCESSOR_API_KEY:-}" ]; then
        echo "  CALLBACK_KEY: \"${TF_OUTPUT_AI_PROCESSOR_API_KEY}\"" >> "$vars_file"
    fi

    print_success "Created $vars_file"
    print_warning "This file contains secrets - do not commit to git!"
}

# Run Ansible to set GitHub secrets
set_github_secrets() {
    print_step "Setting GitHub secrets via Ansible..."

    cd "$ANSIBLE_DIR"

    # Update playbook to use bootstrap vars
    if ! ansible-playbook playbook.yml \
        -e "@vars/bootstrap-secrets.yml" \
        --extra-vars "github_owner=${GITHUB_OWNER} github_repo=${GITHUB_REPO}"; then
        print_error "Failed to set GitHub secrets"
        exit 1
    fi

    print_success "GitHub secrets configured"
}

# Main execution
main() {
    echo "=========================================="
    echo "  ChatOps Bootstrap Script"
    echo "=========================================="
    echo ""

    check_prerequisites
    echo ""

    get_github_info
    echo ""

    get_secrets
    echo ""

    check_terraform_init
    echo ""

    deploy_terraform
    echo ""

    extract_outputs
    echo ""

    create_ansible_vars
    echo ""

    set_github_secrets
    echo ""

    print_success "Bootstrap complete! 🎉"
    echo ""
    echo "Next steps:"
    echo "  1. Verify secrets in GitHub: Settings → Secrets and variables → Actions"
    echo "  2. Test deployment: Push to dev/staging branch or trigger workflow manually"
    echo "  3. Set up Telegram webhook: Use the webhook URL from Terraform output"
    echo ""
}

# Run main if script is executed directly
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi
