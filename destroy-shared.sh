#!/bin/bash
# MIT License
# Copyright (c) 2023 [Your Name or Organization]
# See LICENSE file for details

set -e

echo "⚠️  WARNING: DESTRUCTIVE OPERATION ⚠️"
echo ""
echo "This will destroy shared SES infrastructure used by ALL environments!"
echo "This includes:"
echo "  - SES receipt rule set (all email routing)"
echo ""
echo "Make sure you have destroyed all per-environment resources first."
echo "Note: Per-environment email buckets are destroyed with each environment."
echo ""
read -p "Are you absolutely sure you want to continue? (type 'yes' to confirm): " confirm

if [ "$confirm" != "yes" ]; then
  echo "Aborted."
  exit 0
fi

echo ""
echo "🧹 Starting shared infrastructure cleanup..."

# Change to the shared infrastructure directory
cd infra/shared

# Initialize Terraform (in case it hasn't been)
terraform init

# Deactivate the receipt rule set first
echo "📧 Deactivating SES receipt rule set..."
aws ses set-active-receipt-rule-set --region us-east-1 2>/dev/null || echo "⚠️  No active rule set to deactivate"

# Run terraform destroy
echo "💥 Running terraform destroy..."
terraform destroy -auto-approve

echo ""
echo "✅ Shared infrastructure destroyed successfully!"
echo ""
echo "📌 All SES email routing has been removed."

