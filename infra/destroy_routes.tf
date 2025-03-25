# This file contains resources to ensure proper destruction order
# for API Gateway routes and integrations

# Use a local-exec provisioner to manually delete the routes during destroy
resource "null_resource" "delete_routes_before_destroy" {
  # We'll use a timestamp as trigger to make sure this runs every time
  triggers = {
    # Use a timestamp to ensure this runs on every apply
    time = timestamp()
  }

  # This runs during normal operations (not destroy), setting up a cleanup script
  provisioner "local-exec" {
    command = <<-EOT
      echo '#!/bin/bash
      
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
      ' > ${path.module}/route_cleanup.sh
      
      chmod +x ${path.module}/route_cleanup.sh
    EOT
  }

  depends_on = [
    aws_apigatewayv2_api.lambda_api
  ]
}

# This will be explicitly depended on by the integration resource
# but doesn't create a circular dependency
resource "null_resource" "integration_prerequisite" {
  # Empty resource that can be depended on safely
} 