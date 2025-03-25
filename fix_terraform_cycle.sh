#!/bin/bash

# This script fixes Terraform cycle dependency issues with API Gateway routes and integrations

# Set error handling
set -e

echo "====== Starting Terraform Cycle Fix ======"

# 1. Run the cleanup script to remove problematic resources
echo "Cleaning up API Gateway resources..."
./clear_api_gateway_resources.sh

# 2. Clear Terraform state for resources causing cycles
echo "Refreshing Terraform state..."
terraform -chdir=infra refresh

# 3. Apply Terraform with fixed configuration and without cycles
echo "Applying Terraform with fixed configuration..."
terraform -chdir=infra apply -auto-approve

echo "====== Terraform Cycle Fix Complete ======"
echo "Your infrastructure should now be properly deployed without cycles." 