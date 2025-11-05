#!/bin/bash
# MIT License
# Copyright (c) 2023 [Your Name or Organization]
# See LICENSE file for details

set -e

echo "🌍 Deploying shared SES infrastructure..."
echo "This infrastructure is shared across ALL environments."
echo ""

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

# Change to the shared infrastructure directory
cd infra/shared

# Initialize and apply Terraform
echo "🔧 Initializing Terraform..."
terraform init

echo "📋 Planning Terraform changes..."
terraform plan

echo "🚀 Applying Terraform configuration..."
terraform apply -auto-approve

echo ""
echo "✅ Shared infrastructure deployment complete!"
echo ""
echo "📌 Next steps:"
echo "   1. Run ./deploy.sh to deploy your first environment"
echo "   2. Use ENVIRONMENT=<name> ./deploy.sh for additional environments"

