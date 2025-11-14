#!/bin/bash
set -euo pipefail

# Build Lambda function ZIP package (webhook)
echo "Building webhook Lambda ZIP package..."

# Create temporary directory
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Copy source files
cp src/webhook_handler.py "$TEMP_DIR/"
cp src/requirements.txt "$TEMP_DIR/"

# Install dependencies into the package
cd "$TEMP_DIR"
rm -f ../lambda_function.zip
python3 -m pip install --upgrade pip >/dev/null 2>&1 || true
python3 -m pip install -r requirements.txt -t .

# Create ZIP package
zip -r "$OLDPWD/lambda_function.zip" . >/dev/null
cd "$OLDPWD"

echo "Lambda function ZIP package created: lambda_function.zip"
if [[ -f "lambda_function.zip" ]]; then
    ls -lh "lambda_function.zip" | awk '{print "Size:", $5}'
else
    echo "Warning: lambda_function.zip not found"
fi

# Build output processor
echo ""
echo "🔨 Building output processor Lambda..."
./build_output_processor.sh
