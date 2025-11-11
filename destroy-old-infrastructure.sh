#!/bin/bash
# Migration Script: Destroy Old Infrastructure
# This script destroys infrastructure from the OLD shared state file location
# Use this ONCE to clean up before deploying with the new multi-account setup

set -e

echo "🔄 Migration Cleanup Script"
echo "This will destroy infrastructure from the OLD state file location"
echo ""

# Get environment name from ENV variable or default to "main"
ENVIRONMENT=${ENVIRONMENT:-main}
echo "🌍 Destroying old environment: $ENVIRONMENT"
echo "🧹 Starting cleanup process..."
echo ""

# AWS Profile validation
if [ -z "$AWS_PROFILE" ]; then
  echo ""
  echo "❌ ERROR: AWS_PROFILE is not set!"
  echo ""
  echo "Examples:"
  echo "  AWS_PROFILE=main ENVIRONMENT=main ./destroy-old-infrastructure.sh"
  echo "  AWS_PROFILE=preview ENVIRONMENT=preview ./destroy-old-infrastructure.sh"
  echo "  AWS_PROFILE=dev ENVIRONMENT=dev ./destroy-old-infrastructure.sh"
  echo ""
  exit 1
fi

echo "📋 Using AWS Profile: $AWS_PROFILE"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed."
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

# OLD state bucket configuration (before migration)
OLD_STATE_BUCKET="terraform-tregfd"
OLD_STATE_KEY="terraform/${ENVIRONMENT}/state.tfstate"
echo "📦 OLD Terraform state location:"
echo "   Bucket: $OLD_STATE_BUCKET"
echo "   Key: $OLD_STATE_KEY"
echo ""

# Check if Terraform is installed
if ! command -v terraform &> /dev/null; then
    echo "❌ Terraform is not installed."
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

# Initialize Terraform with OLD state file location
echo "🔧 Initializing Terraform with OLD state file location..."
terraform init -reconfigure \
  -backend-config="bucket=$OLD_STATE_BUCKET" \
  -backend-config="key=$OLD_STATE_KEY" \
  -backend-config="region=us-east-1"

echo ""

# Get bucket names from Terraform configuration (OLD naming without account ID)
PARSER_BUCKET="email-to-webhook-kv-database-${ENVIRONMENT}"
ATTACHMENTS_BUCKET="email-to-webhook-attachments-${ENVIRONMENT}"
EMAIL_BUCKET="email-to-webhook-emails-${ENVIRONMENT}"

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
  -var="aws_region=$AWS_REGION"

echo ""
echo "🧹 Cleaning up placeholder files..."
cd ..
rm -rf lambda_packages

echo ""
echo "✅ Old infrastructure cleanup complete!"
echo ""
echo "📌 Next Steps:"
echo "   1. Create the new state bucket:"
echo "      aws s3 mb s3://terraform-state-${ENVIRONMENT}-${AWS_ACCOUNT_ID} --region $AWS_REGION --profile $AWS_PROFILE"
echo "      aws s3api put-bucket-versioning --bucket terraform-state-${ENVIRONMENT}-${AWS_ACCOUNT_ID} \\"
echo "        --versioning-configuration Status=Enabled --profile $AWS_PROFILE"
echo ""
echo "   2. Deploy with new multi-account setup:"
echo "      AWS_PROFILE=$AWS_PROFILE ENVIRONMENT=$ENVIRONMENT ./deploy.sh"
echo ""

