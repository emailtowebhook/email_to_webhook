# S3 Bucket for Lambda Deployment Package
resource "aws_s3_bucket" "lambda_bucket" {
  bucket = var.s3_bucket
  force_destroy = true

  versioning {
    enabled = true
  }
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = var.lambda_role_name

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

# Lambda Function
resource "aws_lambda_function" "email_parser_lambda" {
  function_name = var.lambda_function_name
  filename      = var.parser_lambda_file_path
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.9"
  role          = aws_iam_role.lambda_role.arn

  # Detect changes in ZIP content
  source_code_hash = filebase64sha256(var.parser_lambda_file_path)

  environment {
    variables = {

    }
  }

  timeout = 10
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
          "s3:PutObject"
        ],
        Resource = "*"
      },
       # Existing S3 Permissions
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = [
          "arn:aws:s3:::email-webhooks-bucket-3rfrd",
          "arn:aws:s3:::email-webhooks-bucket-3rfrd/*",
          "arn:aws:s3:::email-attachments-bucket-3rfrd/*"
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
          "arn:aws:iam::302835751737:user/smtp-*"
        ]
      },
      # Allow IAM policy attachment
      {
        Effect = "Allow"
        Action = [
          "iam:AttachUserPolicy",
          "iam:PutUserPolicy"
        ]
        Resource = "arn:aws:iam::302835751737:user/smtp-*"
      },
      # Allow IAM user management
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = "arn:aws:iam::302835751737:role/verify-domain-lambda-role"
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
      BUCKET_NAME = var.webhooks_bucket_name
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
  integration_uri  = aws_lambda_function.email_parser_lambda.arn
  payload_format_version = "2.0"
}

# API Gateway Route
resource "aws_apigatewayv2_route" "lambda_route" {
  api_id    = aws_apigatewayv2_api.lambda_api.id
  route_key = "POST /domain11"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# API Gateway Stage
resource "aws_apigatewayv2_stage" "prod_stage" {
  api_id      = aws_apigatewayv2_api.lambda_api.id
  name        = "prod"
  auto_deploy = true
}

# Lambda Permission for API Gateway
resource "aws_lambda_permission" "api_gateway_permission" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.email_parser_lambda.arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.lambda_api.execution_arn}/prod/*"
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
  route_key = "POST /v1/domain"
  target    = "integrations/${aws_apigatewayv2_integration. verify_lambda_integration.id}"
}

# Lambda Permission for API Gateway
resource "aws_lambda_permission" "verify_api_gateway_permission" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.verify_domain_lambda.arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.lambda_api.execution_arn}/prod/*"
}

# Output the API Gateway endpoint
output "api_gateway_url" {
  value       = "${aws_apigatewayv2_api.lambda_api.api_endpoint}/prod"
  description = "API Gateway endpoint URL"
}

resource "aws_ses_receipt_rule_set" "default_rule_set" {
  rule_set_name = "default-rule-set"
}

# S3 Bucket Policy to Allow SES Write Access
resource "aws_s3_bucket_policy" "email_storage_policy" {
  bucket = aws_s3_bucket.lambda_bucket.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect    = "Allow",
        Principal = {
          Service = "ses.amazonaws.com"
        },
        Action    = "s3:PutObject",
        Resource  = "${aws_s3_bucket.lambda_bucket.arn}/*",
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
    bucket_name      = aws_s3_bucket.lambda_bucket.id
    object_key_prefix = "emails/"
    position      = 1  # Position in the rule set
  }

  # Enable email scanning for spam/viruses
  scan_enabled = true
}

# Activate the Rule Set
resource "aws_ses_active_receipt_rule_set" "activate_rule_set" {
    rule_set_name = aws_ses_receipt_rule_set.default_rule_set.rule_set_name

}

resource "aws_s3_bucket" "email_urls_bucket" {
  bucket = var.webhooks_bucket_name
  acl    = "private"
}

resource "aws_s3_bucket" "email_attachments_bucket" {
  bucket = var.attachments_bucket_name
}

# Configure public access block to allow public policies
resource "aws_s3_bucket_public_access_block" "public_access_block" {
  bucket                  = aws_s3_bucket.email_attachments_bucket.id
  block_public_acls       = false
  block_public_policy     = false  # Allow bucket policies to enable public access
  ignore_public_acls      = false
  restrict_public_buckets = false
}
# Add a bucket policy to allow public read access
resource "aws_s3_bucket_policy" "public_access_policy" {
  bucket = aws_s3_bucket.email_attachments_bucket.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.email_attachments_bucket.arn}/*"
      }
    ]
  })

 }

####3 parse email lambda

resource "aws_lambda_function" "my_lambda" {
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
      DOMAIN_NAME = var.domain_name
      WEBHOOKS_BUCKET_NAME = var.webhooks_bucket_name
      ATTACHMENTS_BUCKET_NAME = var.attachments_bucket_name
    }
  }
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
          "s3:PutObject"
        ]
        Resource = [
          "arn:aws:s3:::${var.webhooks_bucket_name}",
          "arn:aws:s3:::${var.webhooks_bucket_name}/*",
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
          "arn:aws:iam::302835751737:user/smtp-*"
        ]
      },
      # Allow IAM policy attachment
      {
        Effect = "Allow"
        Action = [
          "iam:AttachUserPolicy",
          "iam:PutUserPolicy"
        ]
        Resource = "arn:aws:iam::302835751737:user/smtp-*"
      },
      # Allow IAM user management
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = "arn:aws:iam::302835751737:role/verify-domain-lambda-role"
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

resource "aws_iam_policy_attachment" "lambda_policy_attachment" {
  name       = "lambda_policy_attachment"
  roles      = [aws_iam_role.lambda_exec.name]
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = aws_s3_bucket.lambda_bucket.bucket

  lambda_function {
    lambda_function_arn = aws_lambda_function.my_lambda.arn
    events              = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_lambda_permission.allow_s3_to_invoke]
}

resource "aws_lambda_permission" "allow_s3_to_invoke" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.my_lambda.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.lambda_bucket.arn
}

resource "aws_cloudfront_distribution" "api_distribution" {
  aliases = ["api.${var.domain_name}", "attachments.${var.domain_name}"]

  origin {
    domain_name = "${aws_apigatewayv2_api.lambda_api.id}.execute-api.us-east-1.amazonaws.com"
    origin_path = "/prod"
    origin_id   = "APIGatewayOrigin"
    custom_origin_config {
      origin_ssl_protocols      = ["TLSv1.2"]
      http_port            = 80
      https_port           = 443
      origin_protocol_policy = "https-only"
    }
  }

  # Add the S3 bucket origin
  origin {
    domain_name = "email-attachments-bucket-3rfrd.s3.amazonaws.com"
    origin_id   = "S3BucketOrigin"
    origin_path = "/attachments" # Map the origin to the attachments folder in the bucket

    s3_origin_config {
      origin_access_identity = "origin-access-identity/cloudfront/${aws_cloudfront_origin_access_identity.s3_access.id}"
    }
  }

  enabled             = true
  is_ipv6_enabled    = true
  default_root_object = "index.html"

  viewer_certificate {
    acm_certificate_arn = "arn:aws:acm:us-east-1:302835751737:certificate/3b5ce796-3a5c-4742-8d98-79d1a42191e9"
    ssl_support_method  = "sni-only"
    minimum_protocol_version       = "TLSv1.2_2021" # Ensure TLS 1.2 or later
  }

  default_cache_behavior {
    target_origin_id = "S3BucketOrigin"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]

    forwarded_values {
      query_string = false

      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  ordered_cache_behavior {
    target_origin_id = "APIGatewayOrigin"
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    path_pattern = "/v1/*"

    forwarded_values {
      query_string = true  # Change to true to pass all query parameters
      headers      = ["None"]

      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  depends_on = [aws_apigatewayv2_api.lambda_api, aws_cloudfront_origin_access_identity.s3_access]
}

# Create CloudFront Origin Access Identity for secure bucket access
resource "aws_cloudfront_origin_access_identity" "s3_access" {
  comment = "Access identity for S3 bucket origin"
}

output "origin_access_identity_arn" {
  value = "origin-access-identity/cloudfront/${aws_cloudfront_origin_access_identity.s3_access.id}"
  description = "The full ARN of the CloudFront Origin Access Identity"
}

# Create a Route 53 record for CloudFront
resource "aws_route53_record" "api" {
  zone_id = var.route53_zone_id
  name    = "api.${var.domain_name}"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.api_distribution.domain_name
    zone_id                = aws_cloudfront_distribution.api_distribution.hosted_zone_id
    evaluate_target_health = false
  }

  depends_on = [aws_cloudfront_distribution.api_distribution]
}

resource "aws_s3_bucket_policy" "attachments_policy" {
  bucket = var.attachments_bucket_name

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid       = "PublicReadGetObject",
        Effect    = "Allow",
        Principal = "*",
        Action    = "s3:GetObject",
        Resource  = "arn:aws:s3:::${var.attachments_bucket_name}/*"
      },
      {
        Sid       = "CloudFrontAccess",
        Effect    = "Allow",
        Principal = {
          AWS = "arn:aws:iam::cloudfront:user/CloudFront Origin Access Identity ${aws_cloudfront_origin_access_identity.s3_access.id}"
        },
        Action    = "s3:GetObject",
        Resource  = "arn:aws:s3:::${var.attachments_bucket_name}/attachments/*"
      }
    ]
  })

  depends_on = [aws_cloudfront_distribution.api_distribution]
}

resource "aws_route53_record" "attachments_alias" {
  zone_id = var.route53_zone_id
  name    = "attachments.${var.domain_name}"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.api_distribution.domain_name
    zone_id                = aws_cloudfront_distribution.api_distribution.hosted_zone_id
    evaluate_target_health = false
  }

  depends_on = [aws_cloudfront_distribution.api_distribution]
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
          "arn:aws:s3:::my-lambda-deploy-bucket-4sdsd6thgr",
          "arn:aws:s3:::my-lambda-deploy-bucket-4sdsd6thgr/*"
        ]
      }
    ]
  })
}