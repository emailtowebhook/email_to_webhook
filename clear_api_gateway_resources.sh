#!/bin/bash

# This script cleans up API Gateway resources outside of Terraform to resolve circular dependencies

set -e

echo "===== Starting API Gateway Resource Cleanup ====="

# Get API ID
echo "Finding API Gateway ID..."
API_ID=$(aws apigatewayv2 get-apis | jq -r '.Items[] | select(.Name == "EmailParserAPI") | .ApiId' || echo "")

if [ -z "$API_ID" ]; then
  echo "API Gateway 'EmailParserAPI' not found. Nothing to clean up."
  exit 0
fi

echo "Found API Gateway with ID: $API_ID"

# Find and delete routes related to functions/code
echo "Finding and deleting routes related to /v1/functions/code/ ..."
ROUTES=$(aws apigatewayv2 get-routes --api-id "$API_ID" | jq -r '.Items[] | select(.RouteKey | contains("/v1/functions/code/")) | .RouteId' || echo "")

if [ -n "$ROUTES" ]; then
  for ROUTE_ID in $ROUTES; do
    echo "Deleting route $ROUTE_ID..."
    aws apigatewayv2 delete-route --api-id "$API_ID" --route-id "$ROUTE_ID" || echo "Failed to delete route $ROUTE_ID"
  done
else
  echo "No matching routes found"
fi

# Find and delete the Cloudflare Worker integration
echo "Finding and deleting Cloudflare Worker integration..."
INTEGRATIONS=$(aws apigatewayv2 get-integrations --api-id "$API_ID" | jq -r '.Items[] | .IntegrationId' || echo "")

if [ -n "$INTEGRATIONS" ]; then
  for INT_ID in $INTEGRATIONS; do
    # Get integration details
    INT_URI=$(aws apigatewayv2 get-integration --api-id "$API_ID" --integration-id "$INT_ID" | jq -r '.IntegrationUri // ""')
    
    if [[ "$INT_URI" == *"cloudflare-worker"* ]]; then
      echo "Deleting integration $INT_ID (Cloudflare Worker)..."
      aws apigatewayv2 delete-integration --api-id "$API_ID" --integration-id "$INT_ID" || echo "Failed to delete integration $INT_ID"
    fi
  done
else
  echo "No integrations found"
fi

# Clean up Terraform state
echo "Removing problematic resources from Terraform state..."
terraform -chdir=infra state rm \
  aws_apigatewayv2_route.put_function_route \
  aws_apigatewayv2_route.post_function_route \
  aws_apigatewayv2_route.get_function_route \
  aws_apigatewayv2_route.delete_function_route \
  aws_apigatewayv2_integration.cloudflare_worker_function_integration \
  null_resource.delete_routes_before_destroy \
  null_resource.integration_prerequisite 2>/dev/null || true

echo "===== API Gateway Resource Cleanup Complete ====="
echo "You can now run 'terraform apply' to recreate resources without cycles" 