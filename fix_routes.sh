#!/bin/bash

# This script manually deletes the routes and integration mentioned in the error message.
# This should be run once to fix the current state, then your Terraform 
# configuration should handle future deployments correctly.

echo "This script will delete the following routes:"
echo "  - 15n2l5d"
echo "  - dzd4a2k"
echo "  - moplncr"
echo "  - olifg8v"
echo "And the integration: yk23ist"
echo ""
echo "Please make sure you are authenticated with AWS CLI and have the correct permissions."
echo ""
read -p "Enter the API ID: " API_ID

if [ -z "$API_ID" ]; then
  echo "API ID is required!"
  exit 1
fi

# Delete routes first
for ROUTE_ID in 15n2l5d dzd4a2k moplncr olifg8v; do
  echo "Deleting route $ROUTE_ID..."
  aws apigatewayv2 delete-route --api-id "$API_ID" --route-id "$ROUTE_ID"
  if [ $? -eq 0 ]; then
    echo "Route $ROUTE_ID deleted successfully"
  else
    echo "Error deleting route $ROUTE_ID"
  fi
done

# Delete the integration
echo "Deleting integration yk23ist..."
aws apigatewayv2 delete-integration --api-id "$API_ID" --integration-id "yk23ist"
if [ $? -eq 0 ]; then
  echo "Integration yk23ist deleted successfully"
else
  echo "Error deleting integration yk23ist. Check if all routes were properly deleted."
fi

echo ""
echo "Clean-up completed. Now you can run 'terraform apply' again." 