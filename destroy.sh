#!/bin/bash
# MIT License
# Copyright (c) 2023 [Your Name or Organization]
# See LICENSE file for details

set -e

# Multi-Account Destroy Script
# Each environment exists in its own AWS account

# Get environment name from ENV variable or default to "main"
ENVIRONMENT=${ENVIRONMENT:-main}
echo "🌍 Destroying environment: $ENVIRONMENT"
echo "🧹 Starting cleanup process..."
echo ""

# AWS Profile validation (required for multi-account setup)
if [ -z "$AWS_PROFILE" ]; then
  echo ""
  echo "❌ ERROR: AWS_PROFILE is not set!"
  echo ""
  echo "In multi-account setup, you must specify which AWS account to destroy from."
  echo "Set the AWS_PROFILE environment variable to target the correct account."
  echo ""
  echo "Examples:"
  echo "  AWS_PROFILE=main ENVIRONMENT=main ./destroy.sh"
  echo "  AWS_PROFILE=preview ENVIRONMENT=preview ./destroy.sh"
  echo "  AWS_PROFILE=dev ENVIRONMENT=dev ./destroy.sh"
  echo ""
  exit 1
fi

echo "📋 Using AWS Profile: $AWS_PROFILE"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please install it before running this script."
    exit 1
fi

# Verify AWS credentials
echo "🔐 Verifying AWS credentials for profile: $AWS_PROFILE..."
if ! aws sts get-caller-identity --profile "$AWS_PROFILE" &> /dev/null; then
  echo ""
  echo "❌ ERROR: Failed to authenticate with AWS using profile: $AWS_PROFILE"
  echo ""
  exit 1
fi

# Get AWS account ID and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query Account --output text)
AWS_REGION=$(aws configure get region --profile "$AWS_PROFILE" || echo "us-east-1")

echo "✅ Authenticated successfully"
echo "   Account ID: $AWS_ACCOUNT_ID"
echo "   Region: $AWS_REGION"
echo ""

# State bucket configuration
STATE_BUCKET="terraform-state-${ENVIRONMENT}-${AWS_ACCOUNT_ID}"
echo "📦 Terraform state bucket: $STATE_BUCKET"
echo ""

# Check if Terraform is installed
if ! command -v terraform &> /dev/null; then
    echo "❌ Terraform is not installed. Please install it before running this script."
    exit 1
fi

# Create placeholder Lambda packages for destroy
echo "📦 Creating placeholder Lambda packages for destroy operation..."
mkdir -p lambda_packages

if [ ! -f "lambda_packages/check.zip" ]; then
  echo "  Creating placeholder check.zip..."
  touch dummy_file
  zip -q lambda_packages/check.zip dummy_file
  rm dummy_file
fi

if [ ! -f "lambda_packages/parser.zip" ]; then
  echo "  Creating placeholder parser.zip..."
  touch dummy_file
  zip -q lambda_packages/parser.zip dummy_file
  rm dummy_file
fi

echo ""

# Change to the infrastructure directory
cd infra

# Initialize Terraform with account-specific backend
echo "🔧 Initializing Terraform..."
terraform init -reconfigure \
  -backend-config="bucket=$STATE_BUCKET" \
  -backend-config="key=terraform.tfstate" \
  -backend-config="region=$AWS_REGION"

echo ""

# Get bucket names from Terraform configuration
PARSER_BUCKET="email-to-webhook-kv-database-${ENVIRONMENT}-${AWS_ACCOUNT_ID}"
ATTACHMENTS_BUCKET="email-to-webhook-attachments-${ENVIRONMENT}-${AWS_ACCOUNT_ID}"
EMAIL_BUCKET="email-to-webhook-emails-${ENVIRONMENT}-${AWS_ACCOUNT_ID}"

# Function to empty an S3 bucket safely
empty_bucket() {
  local bucket_name=$1
  if [[ -z "$bucket_name" ]]; then
    echo "⚠️  Skipping bucket cleanup - no bucket name provided."
    return
  fi
  
  echo "🗑️  Emptying bucket: $bucket_name"
  if aws s3 ls "s3://$bucket_name" --profile "$AWS_PROFILE" 2>/dev/null; then
    aws s3 rm "s3://$bucket_name" --recursive --profile "$AWS_PROFILE" || echo "⚠️  Warning: Failed to empty bucket $bucket_name"
  else
    echo "   Bucket does not exist or already emptied."
  fi
}

# Empty buckets before destroying
echo "🗑️  Emptying S3 buckets..."
empty_bucket "$PARSER_BUCKET"
empty_bucket "$ATTACHMENTS_BUCKET"
empty_bucket "$EMAIL_BUCKET"

echo ""
echo "💥 Running terraform destroy for ${ENVIRONMENT}..."
echo ""

# Run terraform destroy
terraform destroy -auto-approve \
  -var="environment=$ENVIRONMENT" \
  -var="aws_account_id=$AWS_ACCOUNT_ID" \
  -var="aws_region=$AWS_REGION" \
  -var="state_bucket_name=$STATE_BUCKET"

echo ""
echo "🧹 Cleaning up placeholder files..."
cd ..
rm -rf lambda_packages

echo ""
echo "✅ Cleanup complete! All resources have been destroyed."
echo "🎉 Environment '$ENVIRONMENT' has been removed from AWS account $AWS_ACCOUNT_ID"
