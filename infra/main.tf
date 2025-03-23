# S3 Bucket for Lambda Deployment Package
resource "aws_s3_bucket" "emails_bucket" {
  bucket = var.email_bucket_name
  force_destroy = true
 
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "lambda_ses_dns_role"

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
  name        = "lambda_ses_policy"
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
  name = "verify-domain-lambda-role"

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
  name = "verify-domain-lambda-policy"

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
          "s3:DeleteObject"
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
          "ses:DeleteIdentity"
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
resource "aws_lambda_function" "verify_domain_lambda" {
  function_name = "verify-domain-lambda"
  filename      = var.verify_lambda_file_path
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.9"
  role          = aws_iam_role.verify_domain_lambda_role.arn

  source_code_hash = filebase64sha256(var.verify_lambda_file_path)

  environment {
    variables = {
      BUCKET_NAME = var.database_bucket_name
    }
  }

  timeout = 10
}

# API Gateway
resource "aws_apigatewayv2_api" "lambda_api" {
  name          = "EmailParserAPI"
  protocol_type = "HTTP"
}

# API Gateway Integration with Lambda
resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id           = aws_apigatewayv2_api.lambda_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.verify_domain_lambda.arn
  payload_format_version = "2.0"
}
 

# API Gateway Stage
resource "aws_apigatewayv2_stage" "prod_stage" {
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

# Lambda Permission for API Gateway
resource "aws_lambda_permission" "verify_api_gateway_permission" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.verify_domain_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.lambda_api.execution_arn}/prod/*"
}

 

resource "aws_ses_receipt_rule_set" "default_rule_set" {
  rule_set_name = "default-rule-set"
}

# S3 Bucket Policy to Allow SES Write Access
resource "aws_s3_bucket_policy" "email_storage_policy" {
  bucket = aws_s3_bucket.emails_bucket.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect    = "Allow",
        Principal = {
          Service = "ses.amazonaws.com"
        },
        Action    = "s3:PutObject",
        Resource  = "${aws_s3_bucket.emails_bucket.arn}/*",
        Condition = {
          StringEquals = {
            "aws:Referer": var.aws_account_id
          }
        }
      }
    ]
  })
}

# SES Receipt Rule
resource "aws_ses_receipt_rule" "catch_all_rule" {
  rule_set_name = aws_ses_receipt_rule_set.default_rule_set.rule_set_name
  name          = "catch-all-to-s3"
  enabled       = true

  # Match all recipients (empty list means all verified domains)
  recipients = []

  # Actions for the receipt rule
  s3_action {
    bucket_name      = aws_s3_bucket.emails_bucket.id
    position      = 1  # Position in the rule set
   }

  # Enable email scanning for spam/viruses
  scan_enabled = true

  depends_on = [aws_s3_bucket_policy.email_storage_policy, aws_s3_bucket.emails_bucket , aws_ses_receipt_rule_set.default_rule_set]
}

# Activate the Rule Set
resource "aws_ses_active_receipt_rule_set" "activate_rule_set" {
    rule_set_name = aws_ses_receipt_rule_set.default_rule_set.rule_set_name

}

resource "aws_s3_bucket" "kv_database_bucket" {
  bucket = var.database_bucket_name
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
  bucket = var.attachments_bucket_name
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

 }

####3 parse email lambda
resource "aws_lambda_function" "parsing_lambda" {
  function_name = "email-parser-lambda-function"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.9"
  filename      = var.parser_lambda_file_path # Directly reference the ZIP file

  # Detect changes in ZIP content
  source_code_hash = filebase64sha256(var.parser_lambda_file_path)
  timeout = 20

  environment {
    variables = {
      DATABASE_BUCKET_NAME = var.database_bucket_name
      ATTACHMENTS_BUCKET_NAME = var.attachments_bucket_name
      DB_CONNECTION_STRING = var.db_connection_string
      FUNCTION_API_URL = "${aws_apigatewayv2_api.lambda_api.api_endpoint}/prod/v1/functions/code/"
    }
  }
  depends_on = [aws_apigatewayv2_route.post_function_route]
}

resource "aws_iam_role" "lambda_exec" {
  name = "lambda_exec_role"

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
  name = "lambda_ses_smtp_policy"
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
          "ses:DeleteIdentity"
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
  bucket = aws_s3_bucket.emails_bucket.bucket

  lambda_function {
    lambda_function_arn = aws_lambda_function.parsing_lambda.arn
    events              = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_lambda_permission.allow_s3_to_invoke]
}

resource "aws_lambda_permission" "allow_s3_to_invoke" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.parsing_lambda.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.emails_bucket.arn
}

# Add this new resource to attach S3 read permissions to the role
resource "aws_iam_role_policy" "lambda_s3_policy" {
  name   = "lambda_s3_policy"
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

######### Deno Function Lambda #########
resource "aws_lambda_function" "deno_function_lambda" {
  function_name = "deno-function-handler"
  role          = aws_iam_role.deno_lambda_exec.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.9"
  filename      = var.deno_lambda_file_path # ZIP file path for the Deno lambda
  timeout       = 30

  # Detect changes in ZIP content
  source_code_hash = filebase64sha256(var.deno_lambda_file_path)

  environment {
    variables = {
      DATABASE_BUCKET_NAME = var.database_bucket_name
      ATTACHMENTS_BUCKET_NAME = var.attachments_bucket_name
      DENO_API_KEY = var.deno_api_key
      DENO_ORG_ID = var.deno_org_id
    }
  }
}

# IAM role for Deno Function Lambda
resource "aws_iam_role" "deno_lambda_exec" {
  name = "deno_lambda_exec_role"

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

# IAM policy for Deno Function Lambda
resource "aws_iam_role_policy" "deno_lambda_policy" {
  name = "deno_lambda_policy"
  role = aws_iam_role.deno_lambda_exec.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # S3 Permissions
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
      }
    ]
  })
}

# Basic execution role policy attachment
resource "aws_iam_role_policy_attachment" "deno_lambda_policy_attachment" {
  role       = aws_iam_role.deno_lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# API Gateway Integration with Deno Function Lambda
resource "aws_apigatewayv2_integration" "deno_function_integration" {
  api_id           = aws_apigatewayv2_api.lambda_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.deno_function_lambda.arn
  payload_format_version = "2.0"
}

# API Gateway Routes for CRUD operations on functions
# POST - Create/update function code
resource "aws_apigatewayv2_route" "post_function_route" {
  api_id    = aws_apigatewayv2_api.lambda_api.id
  route_key = "POST /v1/functions/code/{domain}"
  target    = "integrations/${aws_apigatewayv2_integration.deno_function_integration.id}"
}

# GET - Retrieve function code
resource "aws_apigatewayv2_route" "get_function_route" {
  api_id    = aws_apigatewayv2_api.lambda_api.id
  route_key = "GET /v1/functions/code/{domain}"
  target    = "integrations/${aws_apigatewayv2_integration.deno_function_integration.id}"
}

# DELETE - Remove function
resource "aws_apigatewayv2_route" "delete_function_route" {
  api_id    = aws_apigatewayv2_api.lambda_api.id
  route_key = "DELETE /v1/functions/code/{domain}"
  target    = "integrations/${aws_apigatewayv2_integration.deno_function_integration.id}"
}

# PUT - Update function settings (enable/disable)
resource "aws_apigatewayv2_route" "put_function_route" {
  api_id    = aws_apigatewayv2_api.lambda_api.id
  route_key = "PUT /v1/functions/code/{domain}"
  target    = "integrations/${aws_apigatewayv2_integration.deno_function_integration.id}" 
}

# Lambda Permission for API Gateway
resource "aws_lambda_permission" "deno_function_api_gateway_permission" {
  statement_id  = "AllowDenofunctionAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.deno_function_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.lambda_api.execution_arn}/prod/*"
}