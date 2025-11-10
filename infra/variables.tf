variable "aws_region" {
  description = "AWS region where resources will be deployed"
  default     = "us-east-1"
  type        = string
}

variable "aws_account_id" {
  description = "The AWS account ID for the target environment (required, no default)"
  type        = string
}


variable "verify_lambda_file_path" {
  description = "The path to the DNS lambda file"
  default = "../lambda_packages/check.zip"
  type = string
}

variable "parser_lambda_file_path" {
  description = "The path to the parser lambda file"
  default = "../lambda_packages/parser.zip"
  type = string
}

variable "database_bucket_name" {
  description = "The name of the S3 bucket for email webhooks, act as KV store (deprecated, kept for backward compatibility)"
  default     = "email-to-webhook-kv-database"
  type        = string
}

# Note: email_bucket_name is now managed in infra/shared/ as a shared resource

variable "attachments_bucket_name" {
  description = "The name of the S3 bucket for email attachments"
  default     = "email-to-webhook-attachments"
  type        = string
}

variable "mongodb_uri" {
  description = "The MongoDB connection URI for email and domain storage"
  default     = ""
  type        = string
  sensitive   = true
}

variable "environment" {
  description = "Environment name (main, preview, dev, etc.) - each environment deploys to its own AWS account"
  default     = "main"
  type        = string
}

variable "state_bucket_name" {
  description = "S3 bucket name for Terraform state storage in the target AWS account"
  type        = string
  default     = ""
}



 

 
 