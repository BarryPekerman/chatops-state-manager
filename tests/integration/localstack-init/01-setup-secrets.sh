#!/bin/bash
# LocalStack initialization script - sets up secrets for testing
# This runs automatically when LocalStack starts

echo "Setting up secrets in LocalStack..."

# Create the secrets bundle
awslocal secretsmanager create-secret \
  --name chatops/secrets \
  --secret-string '{
    "github_token": "ghp_test_token_12345",
    "telegram_bot_token": "123456:ABC-DEF",
    "api_gateway_key": "test-api-key",
    "telegram_secret_token": "test-secret-token"
  }' \
  --region us-east-1

echo "✓ Secrets created successfully"

# Verify secrets
awslocal secretsmanager describe-secret \
  --secret-id chatops/secrets \
  --region us-east-1

echo "✓ LocalStack initialization complete"





