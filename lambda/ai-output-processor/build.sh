#!/bin/bash
set -euo pipefail

# Build script for output processor Lambda

echo "🔨 Building output processor Lambda..."

# Create build directory
BUILD_DIR="build_output_processor"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Copy source files
cp src/processor.py "$BUILD_DIR/"
cp src/requirements.txt "$BUILD_DIR/"

# Install dependencies
cd "$BUILD_DIR"
pip install -r requirements.txt -t .

# Create deployment package
zip -r ../output_processor.zip .

# Clean up
cd ..
rm -rf "$BUILD_DIR"

echo "✅ Output processor Lambda built successfully"
echo "📦 Package: output_processor.zip"
