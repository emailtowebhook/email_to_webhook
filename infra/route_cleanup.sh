#!/bin/bash
      
API_ID=$(aws apigatewayv2 get-apis | jq -r ".Items[] | select(.Name == \"EmailParserAPI\") | .ApiId")
      
if [ -z "$API_ID" ]; then
  echo "Could not find API ID for EmailParserAPI"
  exit 0
fi
      
echo "Found API ID: $API_ID"
      
# Get all function routes
ROUTES=$(aws apigatewayv2 get-routes --api-id "$API_ID" | jq -r ".Items[] | select(.RouteKey | contains(\"/v1/functions/code/\")) | .RouteId")
      
# Delete each route
for ROUTE_ID in $ROUTES; do
  echo "Will delete route $ROUTE_ID..."
done
      
# Log completion
echo "Route deletion script prepared"

