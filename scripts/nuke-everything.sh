#!/bin/bash
set -euo pipefail

# ChatOps Complete Teardown Script - "Nuke Everything"
# This script aggressively destroys ALL ChatOps resources, including orphaned ones
# Use when you keep running into "resource already exists" errors

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"
ANSIBLE_DIR="$PROJECT_ROOT/ansible"

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

# Get AWS region from Terraform config or use default
get_aws_region() {
    local region="${AWS_REGION:-}"

    if [[ -z "$region" && -f "$TERRAFORM_DIR/terraform.tfvars" ]]; then
        region=$(grep -E '^\s*aws_region\s*=' "$TERRAFORM_DIR/terraform.tfvars" 2>/dev/null | cut -d'"' -f2 | head -1 || echo "")
    fi

    if [[ -z "$region" ]]; then
        region=$(aws configure get region 2>/dev/null || echo "eu-west-1")
    fi

    echo "${region:-eu-west-1}"
}

# Get name_prefix from Terraform config
get_name_prefix() {
    local prefix="chatops"

    if [[ -f "$TERRAFORM_DIR/terraform.tfvars" ]]; then
        prefix=$(grep -E '^\s*name_prefix\s*=' "$TERRAFORM_DIR/terraform.tfvars" 2>/dev/null | cut -d'"' -f2 | head -1 || echo "chatops")
    fi

    echo "${prefix}"
}

# Get GitHub info for deleting secrets
get_github_info() {
    local owner=""
    local repo=""

    if [[ -f "$TERRAFORM_DIR/terraform.tfvars" ]]; then
        owner=$(grep -E '^\s*github_owner\s*=' "$TERRAFORM_DIR/terraform.tfvars" 2>/dev/null | cut -d'"' -f2 | head -1 || echo "")
        repo=$(grep -E '^\s*github_repo\s*=' "$TERRAFORM_DIR/terraform.tfvars" 2>/dev/null | cut -d'"' -f2 | head -1 || echo "")
    fi

    # Try from environment
    owner="${owner:-${GITHUB_OWNER:-}}"
    repo="${repo:-${GITHUB_REPO:-}}"

    echo "$owner|$repo"
}

# Confirm destruction
confirm_destruction() {
    echo ""
    log_warning "⚠️  NUCLEAR DESTRUCTION WARNING ⚠️"
    echo "=========================================="
    echo ""
    echo "This script will DESTROY EVERYTHING related to ChatOps:"
    echo ""
    echo "AWS Resources (in region: $(get_aws_region)):"
    echo "  • Lambda functions (webhook, telegram-bot, ai-processor)"
    echo "  • API Gateway APIs and stages"
    echo "  • IAM roles and policies (ALL chatops-related)"
    echo "  • IAM OIDC provider (GitHub)"
    echo "  • Secrets Manager secrets"
    echo "  • CloudWatch log groups"
    echo "  • CloudWatch dashboards"
    echo "  • SQS Dead Letter Queues"
    echo "  • KMS keys (if any)"
    echo ""
    echo "GitHub Resources:"
    echo "  • GitHub Actions secrets (AWS_ROLE_TO_ASSUME, etc.)"
    echo ""
    echo "Local Files:"
    echo "  • Terraform state files"
    echo "  • Ansible vars files"
    echo ""
    echo "This action is IRREVERSIBLE!"
    echo ""
    read -p "Type 'NUKE' to confirm: " confirmation

    if [[ "$confirmation" != "NUKE" ]]; then
        log_info "Destruction cancelled by user"
        exit 0
    fi
}

# Step 1: Destroy Terraform infrastructure (if state exists)
destroy_terraform() {
    log_info "Step 1: Attempting Terraform destroy..."
    echo ""

    if [[ ! -d "$TERRAFORM_DIR" ]]; then
        log_warning "Terraform directory not found - skipping"
        return
    fi

    cd "$TERRAFORM_DIR"

    # Try to initialize and destroy
    if terraform init -upgrade &>/dev/null 2>&1; then
        if terraform state list &>/dev/null 2>&1; then
            log_info "Terraform state found - running destroy..."
            if terraform destroy -auto-approve 2>&1; then
                log_success "Terraform destroy completed"
            else
                log_warning "Terraform destroy had errors (continuing with cleanup)"
            fi
        else
            log_warning "No Terraform state found - skipping terraform destroy"
        fi
    else
        log_warning "Failed to initialize Terraform - skipping destroy"
    fi
}

# Step 2: Delete GitHub secrets
delete_github_secrets() {
    log_info "Step 2: Deleting GitHub secrets..."
    echo ""

    local github_info=$(get_github_info)
    local owner=$(echo "$github_info" | cut -d'|' -f1)
    local repo=$(echo "$github_info" | cut -d'|' -f2)

    if [[ -z "$owner" || -z "$repo" ]]; then
        log_warning "GitHub owner/repo not found - skipping GitHub secret deletion"
        log_info "You may need to delete secrets manually:"
        log_info "  Settings → Secrets and variables → Actions"
        return
    fi

    if [[ -z "${GITHUB_TOKEN:-}" ]]; then
        log_warning "GITHUB_TOKEN not set - skipping GitHub secret deletion"
        log_info "Set GITHUB_TOKEN environment variable to delete secrets automatically"
        return
    fi

    log_info "Deleting GitHub secrets for $owner/$repo..."

    # List of secrets to delete
    local secrets=(
        "AWS_ROLE_TO_ASSUME"
        "AWS_REGION"
        "TERRAFORM_STATE_BUCKET"
        "TELEGRAM_BOT_TOKEN"
        "TELEGRAM_CHAT_ID"
        "CALLBACK_URL"
        "CALLBACK_KEY"
    )

    for secret in "${secrets[@]}"; do
        log_info "  Deleting secret: $secret"
        if gh secret delete "$secret" --repo "$owner/$repo" 2>/dev/null; then
            log_success "    Deleted: $secret"
        else
            log_warning "    Failed or not found: $secret"
        fi
    done
}

# Step 3: Delete Lambda functions
delete_lambda_functions() {
    log_info "Step 3: Deleting Lambda functions..."
    echo ""

    local region=$(get_aws_region)
    local prefix=$(get_name_prefix)

    local functions=$(AWS_DEFAULT_REGION="$region" aws lambda list-functions \
        --query "Functions[?contains(FunctionName, \`$prefix\`)].FunctionName" \
        --output text 2>/dev/null || echo "")

    if [[ -n "$functions" && "$functions" != "None" ]]; then
        for func in $functions; do
            log_info "  Deleting Lambda: $func"
            if AWS_DEFAULT_REGION="$region" aws lambda delete-function \
                --function-name "$func" 2>/dev/null; then
                log_success "    Deleted: $func"
            else
                log_warning "    Failed to delete: $func"
            fi
        done
    else
        log_info "No Lambda functions found"
    fi
}

# Step 4: Delete API Gateways
delete_api_gateways() {
    log_info "Step 4: Deleting API Gateways..."
    echo ""

    local region=$(get_aws_region)
    local prefix=$(get_name_prefix)

    local apis=$(AWS_DEFAULT_REGION="$region" aws apigateway get-rest-apis \
        --query "items[?contains(name, \`$prefix\`) || contains(name, \`webhook\`) || contains(name, \`ai-processor\`)].{id:id, name:name}" \
        --output text 2>/dev/null || echo "")

    if [[ -n "$apis" && "$apis" != "None" ]]; then
        echo "$apis" | while read -r api_id api_name; do
            if [[ -n "$api_id" ]]; then
                log_info "  Deleting API Gateway: $api_name ($api_id)"
                if AWS_DEFAULT_REGION="$region" aws apigateway delete-rest-api \
                    --rest-api-id "$api_id" 2>/dev/null; then
                    log_success "    Deleted: $api_name"
                else
                    log_warning "    Failed to delete: $api_name"
                fi
            fi
        done
    else
        log_info "No API Gateways found"
    fi
}

# Step 5: Delete IAM policies
delete_iam_policies() {
    log_info "Step 5: Deleting IAM policies..."
    echo ""

    local prefix=$(get_name_prefix)

    local policies=$(aws iam list-policies --scope Local \
        --query "Policies[?contains(PolicyName, \`$prefix\`)].Arn" \
        --output text 2>/dev/null || echo "")

    if [[ -n "$policies" && "$policies" != "None" ]]; then
        for policy_arn in $policies; do
            log_info "  Deleting policy: $policy_arn"
            # First, delete all versions except default
            local versions=$(aws iam list-policy-versions \
                --policy-arn "$policy_arn" \
                --query 'Versions[?IsDefaultVersion==\`false\`].VersionId' \
                --output text 2>/dev/null || echo "")

            if [[ -n "$versions" && "$versions" != "None" ]]; then
                for version in $versions; do
                    aws iam delete-policy-version \
                        --policy-arn "$policy_arn" \
                        --version-id "$version" 2>/dev/null || true
                done
            fi

            # Then delete the policy
            if aws iam delete-policy --policy-arn "$policy_arn" 2>/dev/null; then
                log_success "    Deleted: $policy_arn"
            else
                log_warning "    Failed to delete: $policy_arn (may be attached to roles)"
            fi
        done
    else
        log_info "No IAM policies found"
    fi
}

# Step 6: Delete IAM roles
delete_iam_roles() {
    log_info "Step 6: Deleting IAM roles..."
    echo ""

    local prefix=$(get_name_prefix)

    local roles=$(aws iam list-roles \
        --query "Roles[?contains(RoleName, \`$prefix\`) || contains(RoleName, \`github\`)].RoleName" \
        --output text 2>/dev/null || echo "")

    if [[ -n "$roles" && "$roles" != "None" ]]; then
        for role in $roles; do
            log_info "  Cleaning up role: $role"

            # Detach all managed policies
            local attached=$(aws iam list-attached-role-policies \
                --role-name "$role" \
                --query 'AttachedPolicies[].PolicyArn' \
                --output text 2>/dev/null || echo "")

            if [[ -n "$attached" && "$attached" != "None" ]]; then
                for policy_arn in $attached; do
                    aws iam detach-role-policy \
                        --role-name "$role" \
                        --policy-arn "$policy_arn" 2>/dev/null || true
                done
            fi

            # Delete inline policies
            local inline=$(aws iam list-role-policies \
                --role-name "$role" \
                --query 'PolicyNames' \
                --output text 2>/dev/null || echo "")

            if [[ -n "$inline" && "$inline" != "None" ]]; then
                for policy_name in $inline; do
                    aws iam delete-role-policy \
                        --role-name "$role" \
                        --policy-name "$policy_name" 2>/dev/null || true
                done
            fi

            # Delete the role
            if aws iam delete-role --role-name "$role" 2>/dev/null; then
                log_success "    Deleted: $role"
            else
                log_warning "    Failed to delete: $role"
            fi
        done
    else
        log_info "No IAM roles found"
    fi
}

# Step 7: Delete OIDC provider
delete_oidc_provider() {
    log_info "Step 7: Deleting OIDC provider..."
    echo ""

    local providers=$(aws iam list-open-id-connect-providers \
        --query 'OpenIDConnectProviderList[?contains(Arn, `token.actions.githubusercontent.com`)].Arn' \
        --output text 2>/dev/null || echo "")

    if [[ -n "$providers" && "$providers" != "None" ]]; then
        for provider_arn in $providers; do
            log_info "  Deleting OIDC provider: $provider_arn"
            if aws iam delete-open-id-connect-provider \
                --open-id-connect-provider-arn "$provider_arn" 2>/dev/null; then
                log_success "    Deleted: $provider_arn"
            else
                log_warning "    Failed to delete: $provider_arn"
            fi
        done
    else
        log_info "No OIDC providers found"
    fi
}

# Step 8: Delete Secrets Manager secrets
delete_secrets() {
    log_info "Step 8: Deleting Secrets Manager secrets..."
    echo ""

    local region=$(get_aws_region)
    local prefix=$(get_name_prefix)

    local secrets=$(AWS_DEFAULT_REGION="$region" aws secretsmanager list-secrets \
        --query "SecretList[?contains(Name, \`$prefix\`)].Name" \
        --output text 2>/dev/null || echo "")

    if [[ -n "$secrets" && "$secrets" != "None" ]]; then
        for secret in $secrets; do
            log_info "  Force deleting secret: $secret"
            if AWS_DEFAULT_REGION="$region" aws secretsmanager delete-secret \
                --secret-id "$secret" \
                --force-delete-without-recovery 2>/dev/null; then
                log_success "    Deleted: $secret"
            else
                log_warning "    Failed to delete: $secret"
            fi
        done
    else
        log_info "No secrets found"
    fi
}

# Step 9: Delete CloudWatch log groups
delete_log_groups() {
    log_info "Step 9: Deleting CloudWatch log groups..."
    echo ""

    local region=$(get_aws_region)
    local prefix=$(get_name_prefix)

    # Get all log groups with chatops in name
    local log_groups=$(AWS_DEFAULT_REGION="$region" aws logs describe-log-groups \
        --query "logGroups[?contains(logGroupName, \`$prefix\`) || contains(logGroupName, \`webhook\`) || contains(logGroupName, \`telegram\`) || contains(logGroupName, \`ai-processor\`)].logGroupName" \
        --output text 2>/dev/null || echo "")

    if [[ -n "$log_groups" && "$log_groups" != "None" ]]; then
        for log_group in $log_groups; do
            log_info "  Deleting log group: $log_group"
            if AWS_DEFAULT_REGION="$region" aws logs delete-log-group \
                --log-group-name "$log_group" 2>/dev/null; then
                log_success "    Deleted: $log_group"
            else
                log_warning "    Failed to delete: $log_group"
            fi
        done
    else
        log_info "No log groups found"
    fi
}

# Step 10: Delete CloudWatch dashboards
delete_dashboards() {
    log_info "Step 10: Deleting CloudWatch dashboards..."
    echo ""

    local region=$(get_aws_region)
    local prefix=$(get_name_prefix)

    local dashboards=$(AWS_DEFAULT_REGION="$region" aws cloudwatch list-dashboards \
        --query "DashboardEntries[?contains(DashboardName, \`$prefix\`)].DashboardName" \
        --output text 2>/dev/null || echo "")

    if [[ -n "$dashboards" && "$dashboards" != "None" ]]; then
        for dashboard in $dashboards; do
            log_info "  Deleting dashboard: $dashboard"
            if AWS_DEFAULT_REGION="$region" aws cloudwatch delete-dashboards \
                --dashboard-names "$dashboard" 2>/dev/null; then
                log_success "    Deleted: $dashboard"
            else
                log_warning "    Failed to delete: $dashboard"
            fi
        done
    else
        log_info "No dashboards found"
    fi
}

# Step 11: Delete SQS queues (Dead Letter Queues)
delete_sqs_queues() {
    log_info "Step 11: Deleting SQS queues..."
    echo ""

    local region=$(get_aws_region)
    local prefix=$(get_name_prefix)

    local queues=$(AWS_DEFAULT_REGION="$region" aws sqs list-queues \
        --query "QueueUrls[?contains(@, \`$prefix\`) || contains(@, \`dlq\`) || contains(@, \`dead-letter\`)].@" \
        --output text 2>/dev/null || echo "")

    if [[ -n "$queues" && "$queues" != "None" ]]; then
        for queue_url in $queues; do
            log_info "  Deleting queue: $queue_url"
            if AWS_DEFAULT_REGION="$region" aws sqs delete-queue \
                --queue-url "$queue_url" 2>/dev/null; then
                log_success "    Deleted: $queue_url"
            else
                log_warning "    Failed to delete: $queue_url"
            fi
        done
    else
        log_info "No SQS queues found"
    fi
}

# Step 12: Clean up local files
cleanup_local_files() {
    log_info "Step 12: Cleaning up local files..."
    echo ""

    # Remove Terraform state files
    if [[ -f "$TERRAFORM_DIR/terraform.tfstate" ]]; then
        log_info "  Removing Terraform state files..."
        rm -f "$TERRAFORM_DIR"/terraform.tfstate* 2>/dev/null || true
        log_success "    Removed state files"
    fi

    # Remove .terraform directory
    if [[ -d "$TERRAFORM_DIR/.terraform" ]]; then
        log_info "  Removing .terraform directory..."
        rm -rf "$TERRAFORM_DIR/.terraform" 2>/dev/null || true
        log_success "    Removed .terraform"
    fi

    # Remove plan files
    if [[ -f "$TERRAFORM_DIR/tfplan" ]]; then
        log_info "  Removing plan files..."
        rm -f "$TERRAFORM_DIR"/tfplan* 2>/dev/null || true
        log_success "    Removed plan files"
    fi

    # Remove Ansible vars files (they contain secrets)
    if [[ -f "$ANSIBLE_DIR/vars/bootstrap-secrets.yml" ]]; then
        log_info "  Removing Ansible secrets file..."
        rm -f "$ANSIBLE_DIR/vars/bootstrap-secrets.yml" 2>/dev/null || true
        log_success "    Removed bootstrap-secrets.yml"
    fi
}

# Step 13: Final verification
verify_cleanup() {
    log_info "Step 13: Verifying cleanup..."
    echo ""

    local region=$(get_aws_region)
    local prefix=$(get_name_prefix)
    local found_any=false

    # Check Lambda functions
    local lambdas=$(AWS_DEFAULT_REGION="$region" aws lambda list-functions \
        --query "Functions[?contains(FunctionName, \`$prefix\`)].FunctionName" \
        --output text 2>/dev/null || echo "")
    if [[ -n "$lambdas" && "$lambdas" != "None" ]]; then
        log_warning "Remaining Lambda functions: $lambdas"
        found_any=true
    fi

    # Check IAM policies
    local policies=$(aws iam list-policies --scope Local \
        --query "Policies[?contains(PolicyName, \`$prefix\`)].PolicyName" \
        --output text 2>/dev/null || echo "")
    if [[ -n "$policies" && "$policies" != "None" ]]; then
        log_warning "Remaining IAM policies: $policies"
        found_any=true
    fi

    # Check secrets
    local secrets=$(AWS_DEFAULT_REGION="$region" aws secretsmanager list-secrets \
        --query "SecretList[?contains(Name, \`$prefix\`)].Name" \
        --output text 2>/dev/null || echo "")
    if [[ -n "$secrets" && "$secrets" != "None" ]]; then
        log_warning "Remaining secrets: $secrets"
        found_any=true
    fi

    if [[ "$found_any" == "true" ]]; then
        log_warning "Some resources may still exist - check manually"
    else
        log_success "No remaining ChatOps resources found!"
    fi
}

# Main execution
main() {
    echo "=========================================="
    echo "  ChatOps Complete Teardown - NUKE ALL"
    echo "=========================================="
    echo ""

    local region=$(get_aws_region)
    local prefix=$(get_name_prefix)

    log_info "Configuration:"
    log_info "  AWS Region: $region"
    log_info "  Name Prefix: $prefix"
    echo ""

    confirm_destruction

    echo ""
    log_info "Starting complete teardown..."
    echo ""

    # Run all cleanup steps
    destroy_terraform
    echo ""

    delete_github_secrets
    echo ""

    delete_lambda_functions
    echo ""

    delete_api_gateways
    echo ""

    delete_iam_policies
    echo ""

    delete_iam_roles
    echo ""

    delete_oidc_provider
    echo ""

    delete_secrets
    echo ""

    delete_log_groups
    echo ""

    delete_dashboards
    echo ""

    delete_sqs_queues
    echo ""

    cleanup_local_files
    echo ""

    verify_cleanup
    echo ""

    log_success "🎉 Complete teardown finished!"
    echo ""
    echo "All ChatOps resources should now be deleted."
    echo "If you see warnings above, some resources may need manual cleanup."
    echo ""
}

# Run main if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
