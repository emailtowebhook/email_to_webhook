#!/bin/bash
# MIT License
# Copyright (c) 2023 [Your Name or Organization]
# See LICENSE file for details

# Define variables
TF_COMMAND="terraform"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "AWS CLI is not installed. Please install it before running this script."
    echo "Installation instructions: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

echo "AWS CLI is installed and configured properly."

# Check if Terraform is installed
if ! command -v terraform &> /dev/null; then
    echo "Terraform is not installed. Please install it before running this script."
    echo "Installation instructions: https://learn.hashicorp.com/tutorials/terraform/install-cli"
    exit 1
fi

# Verify Terraform version
TERRAFORM_VERSION=$(terraform version -json | jq -r '.terraform_version')
echo "Terraform version $TERRAFORM_VERSION is installed."

# Check if jq is installed (used above for parsing Terraform version)
if ! command -v jq &> /dev/null; then
    echo "Warning: jq is not installed. This script uses jq to parse Terraform version."
    echo "The script will continue, but for full functionality, please install jq."
fi


# Step 1: Package Lambda functions
echo "Packaging Lambda functions..."

mkdir -p lambda_packages

echo "Packaging Check Lambda function..."
(cd lambda/check && ./package.sh) || {
  echo "Check Lambda packaging failed."
  exit 1
}

echo "Packaging Parser Lambda function..."
(cd lambda/parser && ./package.sh) || {
  echo "Parser Lambda packaging failed."
  exit 1
}

# Change directory to the infa folder before running terraform commands
cd infra

# Run terraform commands
terraform init
terraform plan
terraform apply -auto-approve

echo "Deployment complete."

# Clean up zip files after deployment
echo "Cleaning up Lambda function zip files..."
cd ..
rm -rf lambda_packages

echo "Cleanup complete."
