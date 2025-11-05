output "ses_receipt_rule_set_name" {
  description = "The name of the SES receipt rule set"
  value       = aws_ses_receipt_rule_set.default_rule_set.rule_set_name
}

