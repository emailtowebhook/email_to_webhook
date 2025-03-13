# Output the API Gateway endpoint
output "api_gateway_url" {
  value       = "${aws_apigatewayv2_api.lambda_api.api_endpoint}/prod/v1/domain"
  description = "API Gateway endpoint URL"
}