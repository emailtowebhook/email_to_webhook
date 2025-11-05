# SES Receipt Rule Set (shared across all environments)
# Note: Only ONE receipt rule set can be active per AWS account/region
# Individual environment-specific receipt rules are created in each environment's main.tf
resource "aws_ses_receipt_rule_set" "default_rule_set" {
  rule_set_name = "default-rule-set"

  lifecycle {
    prevent_destroy = false
  }
}

# Activate the Rule Set (only one can be active per AWS account)
resource "aws_ses_active_receipt_rule_set" "activate_rule_set" {
  rule_set_name = aws_ses_receipt_rule_set.default_rule_set.rule_set_name
}

