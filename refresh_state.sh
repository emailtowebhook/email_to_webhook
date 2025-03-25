#!/bin/bash

# This script will refresh the Terraform state after manual cleanup
# Run this after successfully running fix_routes.sh

echo "This script will refresh the Terraform state."
echo "It will run 'terraform state rm' commands to remove the problematic resources."
echo ""
echo "Please make sure you are in the same directory as your terraform files."
echo ""
read -p "Continue? (y/n) " CONTINUE

if [ "$CONTINUE" != "y" ]; then
  echo "Aborting."
  exit 1
fi

# Remove the integration from state
echo "Removing integration from Terraform state..."
terraform state rm aws_apigatewayv2_integration.cloudflare_worker_function_integration

# Now try to run terraform apply
echo ""
echo "State cleanup completed. Now you can run 'terraform apply' again." 