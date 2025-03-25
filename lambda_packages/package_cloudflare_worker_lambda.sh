#!/bin/bash

# Set variables
SOURCE_DIR="../lambda/cloudflare_worker_function"
PACKAGE_DIR="./tmp"
OUTPUT_FILE="cloudflare_worker_function.zip"

# Create temporary directory if it doesn't exist
mkdir -p $PACKAGE_DIR

# Clean up any previous package
rm -f $OUTPUT_FILE

# Copy Python files and any dependencies
cp -r $SOURCE_DIR/*.py $PACKAGE_DIR/
cp -r $SOURCE_DIR/*.js $PACKAGE_DIR/

# Install any required dependencies into the package directory
# pip install -r $SOURCE_DIR/requirements.txt -t $PACKAGE_DIR/

# Create the zip file
echo "Creating Lambda package at $OUTPUT_FILE..."
cd $PACKAGE_DIR && zip -r ../$OUTPUT_FILE . && cd ..

# Clean up
rm -rf $PACKAGE_DIR

echo "Package created successfully at $OUTPUT_FILE" 