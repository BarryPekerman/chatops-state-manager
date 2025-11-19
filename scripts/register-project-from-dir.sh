#!/bin/bash
# Auto-detect and register a Terraform project from a working Terraform directory
# Usage: ./register-project-from-dir.sh <terraform-dir> <project-name> [workspace]

set -euo pipefail

TERRAFORM_DIR="${1:-}"
PROJECT_NAME="${2:-}"
WORKSPACE="${3:-}"

if [[ -z "$TERRAFORM_DIR" ]]; then
    echo "Usage: $0 <terraform-dir> [project-name] [workspace]"
    echo ""
    echo "Example:"
    echo "  $0 ./terraform-config"
    echo "  $0 ./terraform-config my-project"
    echo "  $0 ./terraform-config my-project dev"
    echo ""
    echo "This script will:"
    echo "  1. Parse Terraform backend configuration from the directory"
    echo "  2. Extract bucket, key, and region"
    echo "  3. Auto-detect available workspaces"
    echo "  4. Prompt for project name and workspace selection"
    echo "  5. Register the project in the ChatOps registry"
    exit 1
fi

if [[ ! -d "$TERRAFORM_DIR" ]]; then
    echo "❌ Error: Directory '$TERRAFORM_DIR' does not exist"
    exit 1
fi

# Get script directory before we change directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔍 Scanning Terraform directory: $TERRAFORM_DIR"
echo ""

# Check if terraform is initialized (has .terraform directory)
if [[ ! -d "$TERRAFORM_DIR/.terraform" ]]; then
    echo "⚠️  Warning: Terraform not initialized in this directory"
    echo "   Attempting to detect backend config from files..."
    echo ""
fi

# Try to get backend config from terraform (if initialized)
BACKEND_CONFIG=""
if command -v terraform &> /dev/null && [[ -d "$TERRAFORM_DIR/.terraform" ]]; then
    echo "📋 Reading Terraform backend configuration..."
    cd "$TERRAFORM_DIR"

    # Try to get backend config from terraform show
    BACKEND_CONFIG=$(terraform show -json 2>/dev/null | jq -r '.configuration.backend // empty' 2>/dev/null || echo "")

    # If that doesn't work, try terraform init -backend=false to parse config
    if [[ -z "$BACKEND_CONFIG" ]]; then
        BACKEND_CONFIG=$(terraform init -backend=false -input=false 2>&1 | grep -i backend || echo "")
    fi
fi

# Parse backend config from Terraform files
echo "📄 Parsing backend configuration from Terraform files..."

# Look for backend blocks in common files
BACKEND_FILES=(
    "$TERRAFORM_DIR/backend.tf"
    "$TERRAFORM_DIR/terraform.tf"
    "$TERRAFORM_DIR/main.tf"
    "$TERRAFORM_DIR/config.tf"
)

BACKEND_BUCKET=""
BACKEND_KEY=""
BACKEND_REGION=""

for file in "${BACKEND_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        echo "   Checking: $(basename "$file")"

        # Extract backend block (handles both HCL formats)
        # Match: backend "s3" { ... }
        BACKEND_BLOCK=$(awk '/backend\s+"s3"/,/^[[:space:]]*}/' "$file" 2>/dev/null || echo "")

        if [[ -n "$BACKEND_BLOCK" ]]; then
            # Extract bucket (handles both = and : separators, quotes, etc.)
            BACKEND_BUCKET=$(echo "$BACKEND_BLOCK" | grep -iE "bucket\s*[=:]" | head -1 | sed -E 's/.*bucket\s*[=:]\s*["'\'']?([^"'\'',}]+)["'\'',}]*.*/\1/' | sed 's/[[:space:]]*$//' || echo "")

            # Extract key
            BACKEND_KEY=$(echo "$BACKEND_BLOCK" | grep -iE "key\s*[=:]" | head -1 | sed -E 's/.*key\s*[=:]\s*["'\'']?([^"'\'',}]+)["'\'',}]*.*/\1/' | sed 's/[[:space:]]*$//' || echo "")

            # Extract region
            BACKEND_REGION=$(echo "$BACKEND_BLOCK" | grep -iE "region\s*[=:]" | head -1 | sed -E 's/.*region\s*[=:]\s*["'\'']?([^"'\'',}]+)["'\'',}]*.*/\1/' | sed 's/[[:space:]]*$//' || echo "")

            if [[ -n "$BACKEND_BUCKET" ]]; then
                echo "   ✅ Found backend configuration in $(basename "$file")"
                break
            fi
        fi
    fi
done

# If still not found, try parsing .terraform/terraform.tfstate (if exists)
if [[ -z "$BACKEND_BUCKET" && -f "$TERRAFORM_DIR/.terraform/terraform.tfstate" ]]; then
    echo "   Checking .terraform/terraform.tfstate..."
    BACKEND_BUCKET=$(jq -r '.backend.config.bucket // empty' "$TERRAFORM_DIR/.terraform/terraform.tfstate" 2>/dev/null || echo "")
    BACKEND_KEY=$(jq -r '.backend.config.key // empty' "$TERRAFORM_DIR/.terraform/terraform.tfstate" 2>/dev/null || echo "")
    BACKEND_REGION=$(jq -r '.backend.config.region // empty' "$TERRAFORM_DIR/.terraform/terraform.tfstate" 2>/dev/null || echo "")
fi

# If still not found, try terraform.tfstate (if exists)
if [[ -z "$BACKEND_BUCKET" && -f "$TERRAFORM_DIR/terraform.tfstate" ]]; then
    echo "   Checking terraform.tfstate..."
    BACKEND_BUCKET=$(jq -r '.backend.config.bucket // empty' "$TERRAFORM_DIR/terraform.tfstate" 2>/dev/null || echo "")
    BACKEND_KEY=$(jq -r '.backend.config.key // empty' "$TERRAFORM_DIR/terraform.tfstate" 2>/dev/null || echo "")
    BACKEND_REGION=$(jq -r '.backend.config.region // empty' "$TERRAFORM_DIR/terraform.tfstate" 2>/dev/null || echo "")
fi

# Validate required fields
if [[ -z "$BACKEND_BUCKET" ]]; then
    echo ""
    echo "❌ Error: Could not detect backend bucket"
    echo ""
    echo "Please ensure one of the following:"
    echo "  1. Terraform is initialized (run 'terraform init')"
    echo "  2. Backend configuration exists in:"
    echo "     - backend.tf"
    echo "     - terraform.tf"
    echo "     - main.tf"
    echo "     - config.tf"
    echo ""
    echo "Or manually register with:"
    echo "  ./scripts/add-project.sh $PROJECT_NAME <bucket> <key> <region> $WORKSPACE"
    exit 1
fi

# Use AWS_REGION as fallback for region
if [[ -z "$BACKEND_REGION" ]]; then
    BACKEND_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-eu-west-1}}"
    echo "   ⚠️  Region not found, using: $BACKEND_REGION"
fi

# Use default key if not found
if [[ -z "$BACKEND_KEY" ]]; then
    # Try to infer from directory name if project name is set
    if [[ -n "$PROJECT_NAME" ]]; then
        BACKEND_KEY="$PROJECT_NAME/terraform.tfstate"
    else
        BACKEND_KEY="$(basename "$TERRAFORM_DIR")/terraform.tfstate"
    fi
    echo "   ⚠️  Key not found, using default: $BACKEND_KEY"
fi

echo ""
echo "📋 Detected Backend Configuration:"
echo "   Bucket:  $BACKEND_BUCKET"
echo "   Key:     $BACKEND_KEY"
echo "   Region:  $BACKEND_REGION"
echo ""

# Prompt for project name if not provided
if [[ -z "$PROJECT_NAME" ]]; then
    # Suggest a default based on directory name or key path
    SUGGESTED_NAME=$(basename "$TERRAFORM_DIR")
    if [[ "$BACKEND_KEY" == *"/"* ]]; then
        # Extract from key path if available
        SUGGESTED_NAME=$(echo "$BACKEND_KEY" | cut -d'/' -f1)
    fi

    echo "📝 Project Name:"
    read -p "   Enter project name [$SUGGESTED_NAME]: " PROJECT_NAME
    PROJECT_NAME="${PROJECT_NAME:-$SUGGESTED_NAME}"
    echo ""
fi

# Auto-detect workspaces if Terraform is initialized
if [[ -z "$WORKSPACE" ]] && [[ -d "$TERRAFORM_DIR/.terraform" ]]; then
    echo "🔍 Detecting available workspaces..."
    ORIGINAL_DIR=$(pwd)
    cd "$TERRAFORM_DIR"

    # List workspaces
    WORKSPACES=$(terraform workspace list 2>/dev/null | grep -E '^\s*\*?\s+\S+' | sed 's/^\s*\*\?\s*//' | sed 's/[[:space:]]*$//' || echo "")
    CURRENT_WORKSPACE=$(terraform workspace show 2>/dev/null || echo "")

    if [[ -n "$WORKSPACES" ]]; then
        echo ""
        echo "Available workspaces:"
        WORKSPACE_ARRAY=()
        INDEX=1
        while IFS= read -r ws; do
            if [[ -n "$ws" ]]; then
                MARKER=""
                if [[ "$ws" == "$CURRENT_WORKSPACE" ]]; then
                    MARKER=" (current)"
                fi
                echo "  $INDEX) $ws$MARKER"
                WORKSPACE_ARRAY+=("$ws")
                INDEX=$((INDEX + 1))
            fi
        done <<< "$WORKSPACES"

        echo ""
        read -p "Select workspace [1-${#WORKSPACE_ARRAY[@]}] or enter name [default: $CURRENT_WORKSPACE]: " SELECTION

        if [[ "$SELECTION" =~ ^[0-9]+$ ]] && [[ "$SELECTION" -ge 1 ]] && [[ "$SELECTION" -le ${#WORKSPACE_ARRAY[@]} ]]; then
            WORKSPACE="${WORKSPACE_ARRAY[$((SELECTION - 1))]}"
        elif [[ -n "$SELECTION" ]]; then
            # User entered a workspace name
            WORKSPACE="$SELECTION"
        else
            # Use current workspace as default
            WORKSPACE="${CURRENT_WORKSPACE:-default}"
        fi
    else
        # No workspaces found, use default
        WORKSPACE="${CURRENT_WORKSPACE:-default}"
        echo "   Using workspace: $WORKSPACE"
    fi
    cd "$ORIGINAL_DIR"
    echo ""
elif [[ -z "$WORKSPACE" ]]; then
    # Terraform not initialized, prompt for workspace
    read -p "📝 Workspace [default]: " WORKSPACE
    WORKSPACE="${WORKSPACE:-default}"
    echo ""
fi

echo "📋 Final Configuration:"
echo "   Project:   $PROJECT_NAME"
echo "   Bucket:    $BACKEND_BUCKET"
echo "   Key:       $BACKEND_KEY"
echo "   Region:    $BACKEND_REGION"
echo "   Workspace: $WORKSPACE"
echo ""

# Confirm
read -p "Register this project? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Call add-project.sh
"$SCRIPT_DIR/add-project.sh" "$PROJECT_NAME" "$BACKEND_BUCKET" "$BACKEND_KEY" "$BACKEND_REGION" "$WORKSPACE"
