#!/bin/bash
set -euo pipefail

# Build script for Telegram bot Lambda function
# This script creates a ZIP package for the Lambda deployment

echo "🔨 Building Telegram bot Lambda package..."

# Save the starting directory
START_DIR=$(pwd)

# Create temporary directory
TEMP_DIR=$(mktemp -d)
echo "📁 Using temporary directory: $TEMP_DIR"

# Copy source files
echo "📋 Copying source files..."
cp -r src/* "$TEMP_DIR/"

# Install dependencies
echo "📦 Installing Python dependencies..."
cd "$TEMP_DIR"
pip install -r requirements.txt -t .

# Create ZIP package
echo "📦 Creating ZIP package..."
zip -r "$START_DIR/telegram-bot.zip" . -x "*.pyc" "__pycache__/*" "*.git*"

# Cleanup
echo "🧹 Cleaning up..."
cd "$START_DIR"
rm -rf "$TEMP_DIR"

echo "✅ Bot package created: telegram-bot.zip"
echo "📊 Package size: $(du -h telegram-bot.zip | cut -f1)"
