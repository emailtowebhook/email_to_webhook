variable "aws_region" {
  default = "us-east-1"
}

variable "aws_account_id" {
  description = "The AWS account ID"
  default = "302835751737"
}


variable "verify_lambda_file_path" {
  description = "The path to the DNS lambda file"
  default = "../lambda_packages/check.zip"
}

variable "parser_lambda_file_path" {
  description = "The path to the parser lambda file"
  default = "../lambda_packages/parser.zip"
}


variable "webhooks_bucket_name" {
  description = "The name of the S3 bucket for email webhooks"
  default     = "email-webhooks-bucket-3rfrd"
  type        = string
}

variable "s3_bucket" {
  description = "The name of s3 bucket for lambda deployment"
  default = "my-lambda-deploy-bucket-4sdsd6thgr"
}

variable "attachments_bucket_name" {
  description = "The name of the S3 bucket for email attachments"
  default     = "email-attachments-bucket-3rfrd"
  type        = string
}


 

 
 