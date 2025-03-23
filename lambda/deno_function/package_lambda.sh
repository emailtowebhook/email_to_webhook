#!/bin/bash

# Create a temporary directory for packaging
mkdir -p package

# Install dependencies to the package directory
pip install -r requirements.txt --target ./package

# Copy the Lambda function to the package directory
cp lambda_function.py ./package/

# Create the ZIP file
cd package
zip -r ../deno_function.zip .
cd ..

# Move the ZIP file to the lambda_packages directory
mkdir -p ../../lambda_packages
mv deno_function.zip ../../lambda_packages/

echo "Packaging complete. Lambda ZIP file created at ../../lambda_packages/deno_function.zip"

# Clean up
rm -rf package 