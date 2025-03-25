#!/bin/bash

# Get API ID
echo "Listing APIs to find API ID..."
API_ID=$(aws apigatewayv2 get-apis | jq -r '.Items[] | select(.Name == "EmailParserAPI") | .ApiId')

if [ -z "$API_ID" ]; then
  echo "Could not find API ID for 'EmailParserAPI'"
  exit 1
fi

echo "Found API ID: $API_ID"

# Delete routes
ROUTES=("15n2l5d" "dzd4a2k" "moplncr" "olifg8v")
for ROUTE_ID in "${ROUTES[@]}"; do
  echo "Deleting route $ROUTE_ID..."
  aws apigatewayv2 delete-route --api-id "$API_ID" --route-id "$ROUTE_ID"
  echo "Route $ROUTE_ID deleted."
done

# Delete integration
echo "Deleting integration yk23ist..."
aws apigatewayv2 delete-integration --api-id "$API_ID" --integration-id "yk23ist"
echo "Integration deleted."

echo "All routes and integration removed successfully." 