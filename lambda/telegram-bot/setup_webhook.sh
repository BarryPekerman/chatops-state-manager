#!/bin/bash
set -euo pipefail

# Script to set up Telegram bot webhook URL
# This script configures the Telegram bot to send webhooks to our API Gateway

echo "🔗 Setting up Telegram bot webhook..."

# Check if required environment variables are set
if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
    echo "❌ Error: TELEGRAM_BOT_TOKEN environment variable not set"
    echo "Please set it with: export TELEGRAM_BOT_TOKEN='your_bot_token'"
    exit 1
fi

if [[ -z "${BOT_WEBHOOK_URL:-}" ]]; then
    echo "❌ Error: BOT_WEBHOOK_URL environment variable not set"
    echo "Please set it with: export BOT_WEBHOOK_URL='https://your-lambda-infrastructure-api-gateway-url/webhook'"
    echo "Get the URL from: cd lambda-infrastructure && terraform output webhook_url"
    exit 1
fi

echo "🤖 Bot Token: ${TELEGRAM_BOT_TOKEN:0:10}..."
echo "🔗 Webhook URL: $BOT_WEBHOOK_URL"

# Set webhook URL
echo "📡 Setting webhook URL..."
response=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=${BOT_WEBHOOK_URL}")

echo "📋 Response:"
echo "$response" | jq '.'

# Check if webhook was set successfully
if echo "$response" | jq -e '.ok' > /dev/null; then
    echo "✅ Webhook URL set successfully!"
else
    echo "❌ Failed to set webhook URL"
    echo "Error: $(echo "$response" | jq -r '.description // "Unknown error"')"
    exit 1
fi

# Get webhook info
echo "📊 Getting webhook info..."
webhook_info=$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo")
echo "📋 Webhook Info:"
echo "$webhook_info" | jq '.'

echo "🎉 Telegram bot webhook setup completed!"
