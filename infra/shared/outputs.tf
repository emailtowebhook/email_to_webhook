output "shared_email_bucket_name" {
  description = "The name of the shared email bucket"
  value       = aws_s3_bucket.emails_bucket.id
}

output "shared_email_bucket_arn" {
  description = "The ARN of the shared email bucket"
  value       = aws_s3_bucket.emails_bucket.arn
}

output "ses_receipt_rule_set_name" {
  description = "The name of the SES receipt rule set"
  value       = aws_ses_receipt_rule_set.default_rule_set.rule_set_name
}

