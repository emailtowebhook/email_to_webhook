#!/bin/bash
# MIT License
# Copyright (c) 2023 [Your Name or Organization]
# See LICENSE file for details

# Get the current directory name (function name)
FUNCTION_NAME=$(basename "$PWD")
ROOT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || echo "$(cd ../ && pwd)")
ZIP_FILE="${ROOT_DIR}/lambda_packages/${FUNCTION_NAME}.zip"
TEMP_DIR=$(mktemp -d)

echo "Packaging Lambda function: $FUNCTION_NAME"
echo "Root directory for zip: $ROOT_DIR"

# Step 1: Clean up old zip file
if [ -f "$ZIP_FILE" ]; then
  echo "Removing old package at $ZIP_FILE..."
  rm "$ZIP_FILE"
fi

# Step 2: Install dependencies in a temporary directory
if [ -f "requirements.txt" ]; then
  echo "Installing dependencies from requirements.txt..."
  pip install -r "requirements.txt" -t "$TEMP_DIR" || {
    echo "Error installing dependencies for $FUNCTION_NAME."
    rm -rf "$TEMP_DIR"
    exit 1
  }
else
  echo "No requirements.txt found. Skipping dependency installation."
fi

# Step 3: Copy Lambda function code into the temporary directory
echo "Copying Lambda function code..."
cp ./*.py "$TEMP_DIR/" || {
  echo "Error copying code for $FUNCTION_NAME."
  rm -rf "$TEMP_DIR"
  exit 1
}

# Step 4: Create the ZIP package in the root directory
echo "Creating ZIP package..."
cd "$TEMP_DIR" || { echo "Failed to change directory to $TEMP_DIR"; exit 1; }
zip -r "$ZIP_FILE" ./* || {
  echo "Error creating ZIP package for $FUNCTION_NAME."
  rm -rf "$TEMP_DIR"
  exit 1
}
cd - > /dev/null || exit

# Step 5: Clean up the temporary directory
rm -rf "$TEMP_DIR"

echo "Package created at $ZIP_FILE."
