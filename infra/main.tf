# Create per-environment email bucket for SES to store incoming emails
resource "aws_s3_bucket" "emails_bucket" {
  bucket        = "email-to-webhook-emails-${var.environment}"
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

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "lambda_ses_dns_role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Service = "lambda.amazonaws.com"
        },
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_policy" "lambda_policy" {
  name        = "lambda_ses_policy-${var.environment}"
  description = "Policy to allow Lambda to access SES, S3, and CloudWatch"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "ses:VerifyDomainIdentity",
          "ses:VerifyDomainDkim",
          "ses:GetIdentityVerificationAttributes", # Add this action
          "ses:GetIdentityDkimAttributes"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_role_attachment" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

# Create the IAM Role for the Lambda Function
resource "aws_iam_role" "verify_domain_lambda_role" {
  name = "verify-domain-lambda-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Service = "lambda.amazonaws.com"
        },
        Action = "sts:AssumeRole"
      }
    ]
  })
}

# Attach a Policy to the Lambda Role
resource "aws_iam_policy" "verify_domain_lambda_policy" {
  name = "verify-domain-lambda-policy-${var.environment}"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "ses:VerifyDomainIdentity",
          "ses:VerifyDomainDkim",
          "ses:GetIdentityVerificationAttributes",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "s3:PutObject",
          "s3:DeleteObject",
          "ses:DescribeReceiptRule",
          "ses:UpdateReceiptRule",
          "ses:CreateReceiptRule",
          "ses:DeleteReceiptRule"
        ],
        Resource = "*"
      },
       # Existing S3 Permissions
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
          Resource = [
            "arn:aws:s3:::${var.database_bucket_name}",
            "arn:aws:s3:::${var.database_bucket_name}/*",
            "arn:aws:s3:::${var.attachments_bucket_name}/*"
          ]
      },
      # CloudWatch Logs Permissions
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      # SES Permissions
      {
        Effect = "Allow"
        Action = [
          "ses:VerifyDomainIdentity",
          "ses:GetIdentityVerificationAttributes",
          "ses:DeleteIdentity",
          "ses:GetIdentityDkimAttributes"
        ]
        Resource = "*"
      },
      # SMTP User Creation Permissions
      {
        Effect = "Allow"
        Action = [
          "iam:CreateUser",
          "iam:PutUserPolicy",
          "iam:CreateAccessKey",
          "ses:ListIdentities",
          "ses:GetIdentityVerificationAttributes",
          "iam:ListAccessKeys"
        ]
        Resource = [
          "arn:aws:iam::${var.aws_account_id}:user/smtp-*"
        ]
      },
      # Allow IAM policy attachment
      {
        Effect = "Allow"
        Action = [
          "iam:AttachUserPolicy",
          "iam:PutUserPolicy"
        ]
        Resource = "arn:aws:iam::${var.aws_account_id}:user/smtp-*"
      },
      # Allow IAM user management
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = "arn:aws:iam::${var.aws_account_id}:role/verify-domain-lambda-role"
      },
      # Allow IAM GetUser permission
      {
        Effect = "Allow"
        Action = [
          "iam:GetUser"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "verify_domain_lambda_role_attachment" {
  role       = aws_iam_role.verify_domain_lambda_role.name
  policy_arn = aws_iam_policy.verify_domain_lambda_policy.arn
}

# Lambda Function
locals {
  verify_lambda_hash = filebase64sha256(var.verify_lambda_file_path)
}

resource "aws_lambda_function" "verify_domain_lambda" {
  function_name = "verify-domain-lambda-${var.environment}"
  filename      = var.verify_lambda_file_path
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  role          = aws_iam_role.verify_domain_lambda_role.arn

  source_code_hash = local.verify_lambda_hash

  environment {
    variables = {
      DATABASE_BUCKET_NAME = var.database_bucket_name
      MONGODB_URI = var.mongodb_uri
      ENVIRONMENT = var.environment
      CODE_VERSION = local.verify_lambda_hash
      RECEIPT_RULE_SET = "default-rule-set"  # Reference to shared rule set
    }
  }

  timeout = 20
  
  # Prevent Lambda replacement unless specific attributes change
  lifecycle {
    ignore_changes = [
      # Ignore changes to tags and other metadata that don't affect functionality
      tags,
      description
    ]
  }
}

# API Gateway
resource "aws_apigatewayv2_api" "lambda_api" {
  name          = "EmailParserAPI-${var.environment}"
  protocol_type = "HTTP"
  
  lifecycle {
    prevent_destroy = false
  }
}

# API Gateway Integration with Lambda
resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id           = aws_apigatewayv2_api.lambda_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.verify_domain_lambda.arn
  payload_format_version = "2.0"
}
 

# API Gateway Stage (per environment/branch)
resource "aws_apigatewayv2_stage" "env_stage" {
  api_id      = aws_apigatewayv2_api.lambda_api.id
  name        = "prod"
  auto_deploy = true
}

###########
# API Gateway Integration with Lambda
resource "aws_apigatewayv2_integration" "verify_lambda_integration" {
  api_id           = aws_apigatewayv2_api.lambda_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.verify_domain_lambda.arn
  payload_format_version = "2.0"
}

# API Gateway Route
resource "aws_apigatewayv2_route" "verify_lambda_route" {
  api_id    = aws_apigatewayv2_api.lambda_api.id
  route_key = "POST /v1/domain/{domain}"
  target    = "integrations/${aws_apigatewayv2_integration. verify_lambda_integration.id}"
}

# API Gateway DELETE Route for domain removal
resource "aws_apigatewayv2_route" "delete_domain_route" {
  api_id    = aws_apigatewayv2_api.lambda_api.id
  route_key = "DELETE /v1/domain/{domain}"
  target    = "integrations/${aws_apigatewayv2_integration.verify_lambda_integration.id}"
}

# API Gateway PUT Route for updating domain data
resource "aws_apigatewayv2_route" "update_domain_route" {
  api_id    = aws_apigatewayv2_api.lambda_api.id
  route_key = "PUT /v1/domain/{domain}"
  target    = "integrations/${aws_apigatewayv2_integration.verify_lambda_integration.id}"
}

# API Gateway GET Route for retrieving domain status and data
resource "aws_apigatewayv2_route" "get_domain_route" {
  api_id    = aws_apigatewayv2_api.lambda_api.id
  route_key = "GET /v1/domain/{domain}"
  target    = "integrations/${aws_apigatewayv2_integration.verify_lambda_integration.id}"
}

# API Gateway POST Route for syncing domains to SES receipt rule
resource "aws_apigatewayv2_route" "sync_domains_route" {
  api_id    = aws_apigatewayv2_api.lambda_api.id
  route_key = "POST /v1/domains/sync"
  target    = "integrations/${aws_apigatewayv2_integration.verify_lambda_integration.id}"
}

# API Gateway GET Route for debugging receipt rule state
resource "aws_apigatewayv2_route" "debug_receipt_rule_route" {
  api_id    = aws_apigatewayv2_api.lambda_api.id
  route_key = "GET /v1/debug/receipt-rule"
  target    = "integrations/${aws_apigatewayv2_integration.verify_lambda_integration.id}"
}

# Lambda Permission for API Gateway
resource "aws_lambda_permission" "verify_api_gateway_permission" {
  statement_id  = "AllowAPIGatewayInvoke-${var.environment}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.verify_domain_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.lambda_api.execution_arn}/prod/*"
}

resource "aws_s3_bucket" "kv_database_bucket" {
  bucket = "${var.database_bucket_name}-${var.environment}"
  force_destroy = true
}

resource "aws_s3_bucket_ownership_controls" "kv_database_bucket_ownership" {
  bucket = aws_s3_bucket.kv_database_bucket.id
  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "kv_database_bucket_acl" {
  depends_on = [aws_s3_bucket_ownership_controls.kv_database_bucket_ownership]
  bucket = aws_s3_bucket.kv_database_bucket.id
  acl    = "private"
}

resource "aws_s3_bucket" "attachments_bucket" {
  bucket = "${var.attachments_bucket_name}-${var.environment}"
  force_destroy = true
}

# Configure public access block to allow public policies
resource "aws_s3_bucket_public_access_block" "public_access_block" {
  bucket                  = aws_s3_bucket.attachments_bucket.id
  block_public_acls       = false
  block_public_policy     = false  # Allow bucket policies to enable public access
  ignore_public_acls      = false
  restrict_public_buckets = false
}
# Add a bucket policy to allow public read access
resource "aws_s3_bucket_policy" "public_access_policy" {
  bucket = aws_s3_bucket.attachments_bucket.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.attachments_bucket.arn}/*"
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.public_access_block]
 }

####3 parse email lambda
locals {
  # Calculate hash once to ensure consistency and avoid unnecessary Lambda redeployments
  parser_lambda_hash = filebase64sha256(var.parser_lambda_file_path)
}

resource "aws_lambda_function" "parsing_lambda" {
  function_name = "email-parser-lambda-${var.environment}"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  filename      = var.parser_lambda_file_path # Directly reference the ZIP file

  # Use the pre-calculated hash from locals
  source_code_hash = local.parser_lambda_hash
  timeout = 20

  environment {
    variables = {
      DATABASE_BUCKET_NAME = var.database_bucket_name
      EMAILS_BUCKET_NAME = aws_s3_bucket.emails_bucket.id
      ATTACHMENTS_BUCKET_NAME = var.attachments_bucket_name
      MONGODB_URI = var.mongodb_uri
      ENVIRONMENT = var.environment
      # Add a marker to track deployments - only changes when code actually changes
      CODE_VERSION = local.parser_lambda_hash
    }
  }
  
  # Prevent Lambda replacement unless specific attributes change
  lifecycle {
    ignore_changes = [
      # Ignore changes to tags and other metadata that don't affect functionality
      tags,
      description
    ]
  }
}

resource "aws_iam_role" "lambda_exec" {
  name = "lambda_exec_role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}
resource "aws_iam_role_policy" "lambda_ses_smtp_policy" {
  name = "lambda_ses_smtp_policy-${var.environment}"
  role = aws_iam_role.lambda_exec.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Existing S3 Permissions
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "arn:aws:s3:::${var.database_bucket_name}",
          "arn:aws:s3:::${var.database_bucket_name}/*",
          "arn:aws:s3:::${var.attachments_bucket_name}/*"
        ]
      },
      # CloudWatch Logs Permissions
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      # SES Permissions
      {
        Effect = "Allow"
        Action = [
          "ses:VerifyDomainIdentity",
          "ses:GetIdentityVerificationAttributes",
          "ses:DeleteIdentity",
          "ses:GetIdentityDkimAttributes"
        ]
        Resource = "*"
      },
      # SMTP User Creation Permissions
      {
        Effect = "Allow"
        Action = [
          "iam:CreateUser",
          "iam:PutUserPolicy",
          "iam:CreateAccessKey",
          "ses:ListIdentities",
          "ses:GetIdentityVerificationAttributes",
          "iam:ListAccessKeys"
        ]
        Resource = [
          "arn:aws:iam::${var.aws_account_id}:user/smtp-*"
        ]
      },
      # Allow IAM policy attachment
      {
        Effect = "Allow"
        Action = [
          "iam:AttachUserPolicy",
          "iam:PutUserPolicy"
        ]
        Resource = "arn:aws:iam::${var.aws_account_id}:user/smtp-*"
      },
      # Allow IAM user management
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = "arn:aws:iam::${var.aws_account_id}:role/verify-domain-lambda-role"
      },
      # Allow IAM GetUser permission
      {
        Effect = "Allow"
        Action = [
          "iam:GetUser"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy_attachment" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = aws_s3_bucket.emails_bucket.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.parsing_lambda.arn
    events              = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_lambda_permission.allow_s3_to_invoke]
}

resource "aws_lambda_permission" "allow_s3_to_invoke" {
  statement_id  = "AllowS3Invoke-${var.environment}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.parsing_lambda.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.emails_bucket.arn
}

# Add this new resource to attach S3 read permissions to the role
resource "aws_iam_role_policy" "lambda_s3_policy" {
  name   = "lambda_s3_policy-${var.environment}"
  role   = aws_iam_role.lambda_exec.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ],
        Effect   = "Allow",
        Resource = [
          "${aws_s3_bucket.emails_bucket.arn}",
          "${aws_s3_bucket.emails_bucket.arn}/*"
        ]
      }
    ]
  })
}

# SES Receipt Rule - catch emails for this environment and store in per-environment S3 bucket
# Note: The rule set "default-rule-set" must exist (created in infra/shared/)
resource "aws_ses_receipt_rule" "env_catch_rule" {
  rule_set_name = "default-rule-set"  # Reference to shared rule set
  name          = "catch-emails-${var.environment}"
  enabled       = true
  
  # Note: Rule positioning is handled by the order of rule creation
  # Rules are evaluated in the order they appear in the rule set
  # Each environment's rule filters by domain recipients
  # This ensures proper isolation without requiring specific rule order

  # Match all recipients (empty list means all verified domains)
  # This will be dynamically updated by the Lambda function when domains are registered
  recipients = []

  # Actions for the receipt rule
  s3_action {
    bucket_name = aws_s3_bucket.emails_bucket.id
    position    = 1
  }

  # Enable email scanning for spam/viruses
  scan_enabled = true

  depends_on = [aws_s3_bucket_policy.email_storage_policy, aws_s3_bucket.emails_bucket]
  
  # Lifecycle rule to prevent positioning conflicts
  lifecycle {
    ignore_changes = [after]
  }
}
