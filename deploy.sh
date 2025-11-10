#!/bin/bash
# MIT License
# Copyright (c) 2023 [Your Name or Organization]
# See LICENSE file for details

set -e

# Multi-Account Deployment Script
# Each environment deploys to its own AWS account

# Get environment name from ENV variable or default to "main"
ENVIRONMENT=${ENVIRONMENT:-main}
echo "🌍 Deploying to environment: $ENVIRONMENT"

# AWS Profile validation (required for multi-account setup)
if [ -z "$AWS_PROFILE" ]; then
  echo ""
  echo "❌ ERROR: AWS_PROFILE is not set!"
  echo ""
  echo "In multi-account setup, you must specify which AWS account to deploy to."
  echo "Set the AWS_PROFILE environment variable to target the correct account."
  echo ""
  echo "Examples:"
  echo "  AWS_PROFILE=main ENVIRONMENT=main ./deploy.sh"
  echo "  AWS_PROFILE=preview ENVIRONMENT=preview ./deploy.sh"
  echo "  AWS_PROFILE=dev ENVIRONMENT=dev ./deploy.sh"
  echo ""
  echo "To configure AWS profiles, see: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-profiles.html"
  exit 1
fi

echo "📋 Using AWS Profile: $AWS_PROFILE"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please install it before running this script."
    echo "Installation instructions: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

echo "✅ AWS CLI is installed."

# Verify AWS credentials are valid for the selected profile
echo "🔐 Verifying AWS credentials for profile: $AWS_PROFILE..."
if ! aws sts get-caller-identity --profile "$AWS_PROFILE" &> /dev/null; then
  echo ""
  echo "❌ ERROR: Failed to authenticate with AWS using profile: $AWS_PROFILE"
  echo ""
  echo "Please ensure:"
  echo "  1. The profile exists in ~/.aws/credentials or ~/.aws/config"
  echo "  2. The credentials are valid and not expired"
  echo "  3. You have network connectivity to AWS"
  echo ""
  exit 1
fi

# Get AWS account ID and region from the profile
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query Account --output text)
AWS_REGION=$(aws configure get region --profile "$AWS_PROFILE" || echo "us-east-1")

echo "✅ Authenticated successfully"
echo "   Account ID: $AWS_ACCOUNT_ID"
echo "   Region: $AWS_REGION"
echo ""

# State bucket configuration
# Best practice: Each AWS account has its own state bucket
STATE_BUCKET="terraform-state-${ENVIRONMENT}-${AWS_ACCOUNT_ID}"
echo "📦 Terraform state bucket: $STATE_BUCKET"
echo ""

# Check if Terraform is installed
if ! command -v terraform &> /dev/null; then
    echo "❌ Terraform is not installed. Please install it before running this script."
    echo "Installation instructions: https://learn.hashicorp.com/tutorials/terraform/install-cli"
    exit 1
fi

# Verify Terraform version
TERRAFORM_VERSION=$(terraform version -json 2>/dev/null | jq -r '.terraform_version' 2>/dev/null || echo "unknown")
echo "✅ Terraform version $TERRAFORM_VERSION is installed."

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "⚠️  Warning: jq is not installed. This script uses jq for parsing JSON."
    echo "   The script will continue, but for full functionality, please install jq."
fi

echo ""
echo "📦 Packaging Lambda functions..."

mkdir -p lambda_packages

echo "  📦 Packaging Check Lambda..."
(cd lambda/check && ./package.sh) || {
  echo "❌ Check Lambda packaging failed."
  exit 1
}

echo "  📦 Packaging Parser Lambda..."
(cd lambda/parser && ./package.sh) || {
  echo "❌ Parser Lambda packaging failed."
  exit 1
}

echo "✅ Packaging complete."
echo ""

# Change directory to the infra folder
cd infra

# Initialize Terraform with account-specific backend
echo "🔧 Initializing Terraform..."
echo "   Backend bucket: $STATE_BUCKET"
echo "   Backend key: terraform.tfstate"
echo "   Backend region: $AWS_REGION"
echo ""

terraform init -reconfigure \
  -backend-config="bucket=$STATE_BUCKET" \
  -backend-config="key=terraform.tfstate" \
  -backend-config="region=$AWS_REGION"

echo ""
echo "🚀 Deploying infrastructure to $ENVIRONMENT environment..."
echo ""

# Apply Terraform configuration with environment-specific variables
terraform apply -auto-approve \
  -var="environment=$ENVIRONMENT" \
  -var="aws_account_id=$AWS_ACCOUNT_ID" \
  -var="aws_region=$AWS_REGION" \
  -var="state_bucket_name=$STATE_BUCKET"

echo ""
echo "✅ Deployment complete!"
echo ""

# Clean up zip files after deployment
echo "🧹 Cleaning up Lambda function zip files..."
cd ..
rm -rf lambda_packages

echo "✅ Cleanup complete."
echo ""
echo "🎉 Environment '$ENVIRONMENT' is now deployed to AWS account $AWS_ACCOUNT_ID"
