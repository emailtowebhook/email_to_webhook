#!/bin/bash
set -e

# Get environment name from ENV variable or default to "main"
ENVIRONMENT=${ENVIRONMENT:-main}
echo "🌍 Destroying environment: $ENVIRONMENT"
echo "🧹 Starting cleanup process..."
echo ""
echo "⚠️  Note: This will NOT destroy shared SES infrastructure."
echo "   Shared SES receipt rule set will remain active."
echo "   To destroy shared infrastructure, run: ./destroy-shared.sh"
echo ""

# Change to the infrastructure directory
cd infra

# Create empty lambda package directories if they don't exist
echo "📦 Creating placeholder Lambda packages if needed..."
mkdir -p ../lambda_packages

# Create empty zip files if they don't exist
if [ ! -f "../lambda_packages/check.zip" ]; then
  echo "Creating placeholder check.zip file..."
  touch dummy_file
  zip -q ../lambda_packages/check.zip dummy_file
  rm dummy_file
fi

if [ ! -f "../lambda_packages/parser.zip" ]; then
  echo "Creating placeholder parser.zip file..."
  touch dummy_file
  zip -q ../lambda_packages/parser.zip dummy_file
  rm dummy_file
fi

# Initialize Terraform with environment-specific state
echo "🔧 Initializing Terraform with environment-specific state..."
terraform init -reconfigure \
  -backend-config="key=terraform/${ENVIRONMENT}/state.tfstate"

# Get bucket names from Terraform state safely (they include environment suffix)
echo "📋 Retrieving bucket information from variables.tf..."
PARSER_BUCKET=$(grep -A2 "database_bucket_name" variables.tf | grep "default" | awk -F'"' '{print $2}')-${ENVIRONMENT}
ATTACHMENTS_BUCKET=$(grep -A2 "attachments_bucket_name" variables.tf | grep "default" | awk -F'"' '{print $2}')-${ENVIRONMENT}
EMAIL_BUCKET="email-to-webhook-emails-${ENVIRONMENT}"

# Function to empty an S3 bucket safely
empty_bucket() {
  local bucket_name=$1
  if [[ "$bucket_name" == "NOT_FOUND" || -z "$bucket_name" ]]; then
    echo "⚠️  Skipping bucket cleanup. No bucket found in Terraform state."
  else
    echo "🗑️  Emptying bucket: $bucket_name"
    aws s3 rb s3://$bucket_name --force || echo "⚠️  Warning: Failed to empty bucket $bucket_name"
  fi
}

# Empty buckets if they exist
empty_bucket "$PARSER_BUCKET"
empty_bucket "$ATTACHMENTS_BUCKET"
empty_bucket "$EMAIL_BUCKET"

# Run terraform destroy with environment variable
echo "💥 Running terraform destroy for ${ENVIRONMENT}..."
terraform destroy -auto-approve -var="environment=${ENVIRONMENT}"

# Clean up the placeholder files
echo "🧹 Cleaning up placeholder files..."
rm -rf ../lambda_packages

echo "✅ Cleanup complete! All resources have been destroyed."
