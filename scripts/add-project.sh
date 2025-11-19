#!/bin/bash
# Script to add a project to the ChatOps project registry
# Usage: ./add-project.sh <project-name> <backend-bucket> <backend-key> <region> [workspace]

set -euo pipefail

PROJECT_NAME="${1:-}"
BACKEND_BUCKET="${2:-}"
BACKEND_KEY="${3:-}"
REGION="${4:-}"
WORKSPACE="${5:-default}"

if [[ -z "$PROJECT_NAME" || -z "$BACKEND_BUCKET" || -z "$BACKEND_KEY" || -z "$REGION" ]]; then
    echo "Usage: $0 <project-name> <backend-bucket> <backend-key> <region> [workspace]"
    echo ""
    echo "Example:"
    echo "  $0 my-project tf-state-bucket my-project/terraform.tfstate eu-west-1 default"
    echo ""
    echo "Arguments:"
    echo "  project-name    : Name of the project (used in /select menu)"
    echo "  backend-bucket  : S3 bucket name for Terraform state"
    echo "  backend-key     : S3 key path for Terraform state file"
    echo "  region          : AWS region where state bucket exists"
    echo "  workspace       : Terraform workspace name (default: 'default')"
    exit 1
fi

SECRET_NAME="chatops/project-registry"
AWS_REGION="${AWS_REGION:-eu-west-1}"

echo "📋 Adding project '$PROJECT_NAME' to registry..."
echo "   Bucket: $BACKEND_BUCKET"
echo "   Key: $BACKEND_KEY"
echo "   Region: $REGION"
echo "   Workspace: $WORKSPACE"
echo ""

# Get current registry
echo "📥 Fetching current registry..."
CURRENT_REGISTRY=$(aws secretsmanager get-secret-value \
    --secret-id "$SECRET_NAME" \
    --region "$AWS_REGION" \
    --query 'SecretString' \
    --output text)

# Parse and update
echo "✏️  Updating registry..."
UPDATED_REGISTRY=$(echo "$CURRENT_REGISTRY" | jq --arg name "$PROJECT_NAME" \
    --arg bucket "$BACKEND_BUCKET" \
    --arg key "$BACKEND_KEY" \
    --arg region "$REGION" \
    --arg workspace "$WORKSPACE" \
    '.projects[$name] = {
        enabled: true,
        backend_bucket: $bucket,
        backend_key: $key,
        region: $region,
        workspace: $workspace
    }')

# Update secret
echo "💾 Saving updated registry..."
aws secretsmanager put-secret-value \
    --secret-id "$SECRET_NAME" \
    --region "$AWS_REGION" \
    --secret-string "$UPDATED_REGISTRY" \
    > /dev/null

echo "✅ Project '$PROJECT_NAME' added successfully!"
echo ""
echo "Verify with:"
echo "  aws secretsmanager get-secret-value --secret-id $SECRET_NAME --region $AWS_REGION --query 'SecretString' --output text | jq '.projects.\"$PROJECT_NAME\"'"
