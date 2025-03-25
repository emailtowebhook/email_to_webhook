# This file contains resources to ensure proper destruction order
# for API Gateway routes and integrations

# Use a local-exec provisioner to manually delete the routes using AWS CLI
resource "null_resource" "delete_routes_before_integration" {
  # Only run this during destroy operations
  triggers = {
    # Use the integration ID as a trigger
    integration_id = aws_apigatewayv2_integration.cloudflare_worker_function_integration.id
    api_id = aws_apigatewayv2_api.lambda_api.id
  }

  # Delete routes before the integration
  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
      echo "Deleting routes referencing integration ${self.triggers.integration_id}..."
      
      # Get all routes for this API
      ROUTES=$(aws apigatewayv2 get-routes --api-id ${self.triggers.api_id} | jq -r '.Items[] | select(.Target | contains("${self.triggers.integration_id}")) | .RouteId')
      
      # Delete each route
      for ROUTE_ID in $ROUTES; do
        echo "Deleting route $ROUTE_ID..."
        aws apigatewayv2 delete-route --api-id ${self.triggers.api_id} --route-id "$ROUTE_ID"
      done
      
      echo "All routes deleted"
    EOT
    interpreter = ["/bin/bash", "-c"]
  }

  # This resource depends on all route resources to ensure they're created first
  depends_on = [
    aws_apigatewayv2_route.post_function_route,
    aws_apigatewayv2_route.get_function_route,
    aws_apigatewayv2_route.delete_function_route,
    aws_apigatewayv2_route.put_function_route
  ]
}

# Add explicit dependency to integration to ensure routes are deleted first
# We will modify the main.tf file to add a depends_on to the integration
# This is just a placeholder to track the dependency
resource "null_resource" "integration_dependency" {
  depends_on = [null_resource.delete_routes_before_integration]
  
  triggers = {
    integration_id = aws_apigatewayv2_integration.cloudflare_worker_function_integration.id
  }
} 