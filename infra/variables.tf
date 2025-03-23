variable "aws_region" {
  default = "us-east-1"
  type = string
}

variable "aws_account_id" {
  description = "The AWS account ID"
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

variable "deno_lambda_file_path" {
  description = "The path to the Deno function lambda file"
  default = "../lambda_packages/deno_function.zip"
  type = string
}


variable "database_bucket_name" {
  description = "The name of the S3 bucket for email webhooks, act as KV store"
  default     = "email-to-webhook-kv-database"
  type        = string
}

variable "email_bucket_name" {
  description = "The name of s3 bucket for lambda deployment"
  default = "email-to-webhook-emails"
  type = string
}

variable "attachments_bucket_name" {
  description = "The name of the S3 bucket for email attachments"
  default     = "email-to-webhook-attachments"
  type        = string
}

variable "db_connection_string" {
  description = "The PostgreSQL database connection string for email storage"
  default     = ""
  type        = string
}

variable "deno_org_id" {
  description = "The Deno organization ID for deployment"
  type        = string
  default     = ""
}

variable "deno_api_key" {
  description = "The Deno API key for authentication"
  type        = string
  default     = ""
}



 

 
 