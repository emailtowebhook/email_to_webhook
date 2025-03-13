output "lambda_function_arn" {
  value = aws_lambda_function.email_parser_lambda.arn
}


output "s3_bucket_name" {
  value = aws_s3_bucket.lambda_bucket.id
}
