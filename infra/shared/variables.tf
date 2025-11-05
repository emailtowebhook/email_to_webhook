variable "aws_region" {
  default = "us-east-1"
  type    = string
}

variable "email_bucket_name" {
  description = "The name of the shared S3 bucket for all email storage"
  default     = "email-to-webhook-emails-shared"
  type        = string
}

