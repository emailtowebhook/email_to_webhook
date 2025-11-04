# Output the API Gateway endpoint
output "api_gateway_url" {
  value       = "${aws_apigatewayv2_api.lambda_api.api_endpoint}/prod/v1/domain"
  description = "API Gateway endpoint URL"
}

output "api_gateway_id" {
  value       = aws_apigatewayv2_api.lambda_api.id
  description = "API Gateway ID"
}

output "api_gateway_name" {
  value       = aws_apigatewayv2_api.lambda_api.name
  description = "API Gateway name (includes environment suffix)"
}

output "environment" {
  value       = var.environment
  description = "Current deployment environment"
}