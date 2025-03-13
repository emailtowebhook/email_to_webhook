variable "aws_region" {
  default = "us-east-1"
}

variable "lambda_function_name" {
  description = "The name of email parser lambda function"
  default = "email_parser_dns_lambda"
}

variable "lambda_role_name" {
  description = "The name of lambda role"
  default = "lambda_ses_dns_role"
}

variable "s3_bucket" {
  description = "The name of s3 bucket for lambda deployment"
  default = "my-lambda-deploy-bucket-4sdsd6thgr"
}


variable "verify_lambda_file_path" {
  description = "The path to the DNS lambda file"
  default = "../lambda_packages/check.zip"
}

variable "parser_lambda_file_path" {
  description = "The path to the parser lambda file"
  default = "../lambda_packages/parser.zip"
}

variable "aws_account_id" {
  description = "The AWS account ID"
  default = "302835751737"
}


variable "domain_name" {
  description = "The domain name for the service"
  default = "emailtowebhook.com"
  type        = string
}

variable "subdomain_name" {
  description = "The subdomain name for the service"
  default = "api"
  type    = string
}

variable "certificate_arn" {
  description = "The ARN of the certificate for the service"
  type        = string
  default = "arn:aws:acm:us-east-1:302835751737:certificate/3b5ce796-3a5c-4742-8d98-79d1a42191e9"
}

variable "route53_zone_id" {
  description = "The Route53 zone ID for the service"
  type = string
  default = "Z06253611H11TYVLSQ89V"
}

variable "webhooks_bucket_name" {
  description = "The name of the S3 bucket for email webhooks"
  default     = "email-webhooks-bucket-3rfrd"
  type        = string
}

variable "attachments_bucket_name" {
  description = "The name of the S3 bucket for email attachments"
  default     = "email-attachments-bucket-3rfrd"
  type        = string
}


 

 
 