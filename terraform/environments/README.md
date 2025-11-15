# Terraform Environments Directory

## Overview

This directory contains example configuration files for **dev** (shared testing) and **production** environments.

## Environments

### Dev (Shared Testing)
- **Purpose**: Shared testing environment for validating changes before production
- **Location**: `dev/terraform.tfvars.example`
- **Configuration**:
  - AI processing: **Disabled** (cost savings)
  - Name prefix: `chatops-dev`
  - Log retention: 7 days
  - Region: `us-east-1` (or your preference)

### Production
- **Purpose**: Live environment for actual usage
- **Location**: `production/terraform.tfvars.example`
- **Configuration**:
  - AI processing: **Enabled**
  - Name prefix: `chatops`
  - Log retention: 365 days
  - Region: `eu-north-1` (or your preference)

## Usage

### Setting Up an Environment

1. **Copy the example file**:
   ```bash
   cd terraform/environments/dev  # or production
   cp terraform.tfvars.example terraform.tfvars
   ```

2. **Edit `terraform.tfvars`** with your values:
   - GitHub credentials
   - Telegram bot token and chat ID
   - S3 bucket ARN
   - AWS region

3. **Initialize Terraform** (from the environment directory):
   ```bash
   terraform init
   ```

4. **Plan and Apply**:
   ```bash
   terraform plan
   terraform apply
   ```

### Important Notes

- **Paths are fixed**: Lambda ZIP paths use `../../terraform-zips/...` which is correct when running Terraform from these subdirectories
- **Separate State Files**: Each environment should use a different S3 state key to keep them isolated
  - Dev: `s3://bucket/dev/terraform.tfstate`
  - Production: `s3://bucket/production/terraform.tfstate`
- **Separate GitHub Secrets**: Use different GitHub secrets for each environment
  - Dev: `AWS_ROLE_TO_ASSUME_DEV`
  - Production: `AWS_ROLE_TO_ASSUME`

## Workflow

1. **Test in Dev**: Deploy changes to dev environment first
2. **Validate**: Test all functionality in dev
3. **Deploy to Production**: Once validated, deploy to production

## Alternative: Single Environment

If you don't need separate environments, you can use the main `terraform/terraform.tfvars.example` instead and deploy directly from the `terraform/` directory.
