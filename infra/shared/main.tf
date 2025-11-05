# Shared S3 Bucket for Email Storage (used by all environments)
resource "aws_s3_bucket" "emails_bucket" {
  bucket        = var.email_bucket_name
  force_destroy = true
}

# S3 Bucket Policy to Allow SES Write Access
resource "aws_s3_bucket_policy" "email_storage_policy" {
  bucket = aws_s3_bucket.emails_bucket.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Service = "ses.amazonaws.com"
        },
        Action   = "s3:PutObject",
        Resource = "${aws_s3_bucket.emails_bucket.arn}/*"
      },
      {
        Effect = "Allow",
        Principal = {
          Service = "lambda.amazonaws.com"
        },
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ],
        Resource = [
          "${aws_s3_bucket.emails_bucket.arn}",
          "${aws_s3_bucket.emails_bucket.arn}/*"
        ]
      }
    ]
  })
}

# SES Receipt Rule Set (shared across all environments)
resource "aws_ses_receipt_rule_set" "default_rule_set" {
  rule_set_name = "default-rule-set"

  lifecycle {
    prevent_destroy = false
  }
}

# SES Receipt Rule - catch all emails and store in shared S3 bucket
resource "aws_ses_receipt_rule" "catch_all_rule" {
  rule_set_name = aws_ses_receipt_rule_set.default_rule_set.rule_set_name
  name          = "catch-all-to-s3"
  enabled       = true

  # Match all recipients (empty list means all verified domains)
  recipients = []

  # Actions for the receipt rule
  s3_action {
    bucket_name = aws_s3_bucket.emails_bucket.id
    position    = 1 # Position in the rule set
  }

  # Enable email scanning for spam/viruses
  scan_enabled = true

  depends_on = [aws_s3_bucket_policy.email_storage_policy, aws_s3_bucket.emails_bucket, aws_ses_receipt_rule_set.default_rule_set]
}

# Activate the Rule Set (only one can be active per AWS account)
resource "aws_ses_active_receipt_rule_set" "activate_rule_set" {
  rule_set_name = aws_ses_receipt_rule_set.default_rule_set.rule_set_name
}

