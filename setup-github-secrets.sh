#!/bin/bash
# Script to set up GitHub secrets for multi-account deployment
# Requires GitHub CLI (gh) to be installed and authenticated

set -e

echo "🔐 GitHub Secrets Setup Script"
echo "================================"
echo ""

# Check if GitHub CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is not installed."
    echo ""
    echo "Install it with:"
    echo "  macOS:   brew install gh"
    echo "  Linux:   See https://github.com/cli/cli/blob/trunk/docs/install_linux.md"
    echo "  Windows: See https://github.com/cli/cli#windows"
    echo ""
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated with GitHub CLI."
    echo ""
    echo "Run: gh auth login"
    echo ""
    exit 1
fi

echo "✅ GitHub CLI is installed and authenticated"
echo ""

# Prompt for AWS credentials
echo "📋 Enter AWS credentials for MAIN environment:"
read -p "AWS Access Key ID (MAIN): " AWS_ACCESS_KEY_ID_MAIN
read -sp "AWS Secret Access Key (MAIN): " AWS_SECRET_ACCESS_KEY_MAIN
echo ""
read -p "AWS Account ID (MAIN) [302835751737]: " AWS_ACCOUNT_ID_MAIN
AWS_ACCOUNT_ID_MAIN=${AWS_ACCOUNT_ID_MAIN:-302835751737}
read -p "AWS Region (MAIN) [us-east-1]: " AWS_REGION_MAIN
AWS_REGION_MAIN=${AWS_REGION_MAIN:-us-east-1}
echo ""

# Ask if using same credentials for all environments
read -p "Use same AWS account for preview and dev? (y/n) [y]: " USE_SAME
USE_SAME=${USE_SAME:-y}
echo ""

if [[ "$USE_SAME" =~ ^[Yy]$ ]]; then
    AWS_ACCESS_KEY_ID_PREVIEW="$AWS_ACCESS_KEY_ID_MAIN"
    AWS_SECRET_ACCESS_KEY_PREVIEW="$AWS_SECRET_ACCESS_KEY_MAIN"
    AWS_ACCOUNT_ID_PREVIEW="$AWS_ACCOUNT_ID_MAIN"
    AWS_REGION_PREVIEW="$AWS_REGION_MAIN"
    
    AWS_ACCESS_KEY_ID_DEV="$AWS_ACCESS_KEY_ID_MAIN"
    AWS_SECRET_ACCESS_KEY_DEV="$AWS_SECRET_ACCESS_KEY_MAIN"
    AWS_ACCOUNT_ID_DEV="$AWS_ACCOUNT_ID_MAIN"
    AWS_REGION_DEV="$AWS_REGION_MAIN"
else
    echo "📋 Enter AWS credentials for PREVIEW environment:"
    read -p "AWS Access Key ID (PREVIEW): " AWS_ACCESS_KEY_ID_PREVIEW
    read -sp "AWS Secret Access Key (PREVIEW): " AWS_SECRET_ACCESS_KEY_PREVIEW
    echo ""
    read -p "AWS Account ID (PREVIEW): " AWS_ACCOUNT_ID_PREVIEW
    read -p "AWS Region (PREVIEW) [us-east-1]: " AWS_REGION_PREVIEW
    AWS_REGION_PREVIEW=${AWS_REGION_PREVIEW:-us-east-1}
    echo ""
    
    echo "📋 Enter AWS credentials for DEV environment:"
    read -p "AWS Access Key ID (DEV): " AWS_ACCESS_KEY_ID_DEV
    read -sp "AWS Secret Access Key (DEV): " AWS_SECRET_ACCESS_KEY_DEV
    echo ""
    read -p "AWS Account ID (DEV): " AWS_ACCOUNT_ID_DEV
    read -p "AWS Region (DEV) [us-east-1]: " AWS_REGION_DEV
    AWS_REGION_DEV=${AWS_REGION_DEV:-us-east-1}
    echo ""
fi

# Optional MongoDB URI
read -p "Enter MongoDB URI (optional, press Enter to skip): " MONGODB_URI
echo ""

# Confirm before setting secrets
echo "🔍 Summary:"
echo "  Main Account ID: $AWS_ACCOUNT_ID_MAIN"
echo "  Main Region: $AWS_REGION_MAIN"
echo "  Preview Account ID: $AWS_ACCOUNT_ID_PREVIEW"
echo "  Preview Region: $AWS_REGION_PREVIEW"
echo "  Dev Account ID: $AWS_ACCOUNT_ID_DEV"
echo "  Dev Region: $AWS_REGION_DEV"
if [ -n "$MONGODB_URI" ]; then
    echo "  MongoDB URI: <provided>"
fi
echo ""

read -p "Create these secrets in GitHub? (y/n): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled"
    exit 0
fi

echo ""
echo "🚀 Creating GitHub secrets..."
echo ""

# Create secrets for MAIN environment
echo "  Creating MAIN environment secrets..."
echo "$AWS_ACCESS_KEY_ID_MAIN" | gh secret set AWS_ACCESS_KEY_ID_MAIN
echo "$AWS_SECRET_ACCESS_KEY_MAIN" | gh secret set AWS_SECRET_ACCESS_KEY_MAIN
echo "$AWS_ACCOUNT_ID_MAIN" | gh secret set AWS_ACCOUNT_ID_MAIN
echo "$AWS_REGION_MAIN" | gh secret set AWS_REGION_MAIN

# Create secrets for PREVIEW environment
echo "  Creating PREVIEW environment secrets..."
echo "$AWS_ACCESS_KEY_ID_PREVIEW" | gh secret set AWS_ACCESS_KEY_ID_PREVIEW
echo "$AWS_SECRET_ACCESS_KEY_PREVIEW" | gh secret set AWS_SECRET_ACCESS_KEY_PREVIEW
echo "$AWS_ACCOUNT_ID_PREVIEW" | gh secret set AWS_ACCOUNT_ID_PREVIEW
echo "$AWS_REGION_PREVIEW" | gh secret set AWS_REGION_PREVIEW

# Create secrets for DEV environment
echo "  Creating DEV environment secrets..."
echo "$AWS_ACCESS_KEY_ID_DEV" | gh secret set AWS_ACCESS_KEY_ID_DEV
echo "$AWS_SECRET_ACCESS_KEY_DEV" | gh secret set AWS_SECRET_ACCESS_KEY_DEV
echo "$AWS_ACCOUNT_ID_DEV" | gh secret set AWS_ACCOUNT_ID_DEV
echo "$AWS_REGION_DEV" | gh secret set AWS_REGION_DEV

# Create optional MongoDB URI
if [ -n "$MONGODB_URI" ]; then
    echo "  Creating MONGODB_URI secret..."
    echo "$MONGODB_URI" | gh secret set MONGODB_URI
fi

echo ""
echo "✅ All secrets created successfully!"
echo ""
echo "📋 View your secrets at:"
gh repo view --web
echo "   → Settings → Secrets and variables → Actions"
echo ""
echo "🎉 You can now push to main/preview/dev branches to trigger deployments!"

