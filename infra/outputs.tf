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

output "email_bucket_name" {
  value       = aws_s3_bucket.emails_bucket.id
  description = "Name of the per-environment email S3 bucket"
}

output "email_bucket_arn" {
  value       = aws_s3_bucket.emails_bucket.arn
  description = "ARN of the per-environment email S3 bucket"
}

output "parser_lambda_arn" {
  value       = aws_lambda_function.parsing_lambda.arn
  description = "ARN of the email parser Lambda function"
}

output "ses_receipt_rule_name" {
  value       = aws_ses_receipt_rule.env_catch_rule.name
  description = "Name of the SES receipt rule for this environment"
}