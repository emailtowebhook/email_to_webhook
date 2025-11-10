provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      Project     = "email-to-webhook"
      ManagedBy   = "terraform"
    }
  }
}

terraform {
  backend "s3" {
    # Backend configuration is set dynamically during terraform init
    # Use -backend-config flags to specify:
    #   - bucket: The S3 bucket in the target AWS account
    #   - key: The state file path (e.g., "terraform.tfstate" or "terraform/${environment}/state.tfstate")
    #   - region: The AWS region where the state bucket exists
    # Example: terraform init -backend-config="bucket=terraform-state-main" \
    #                         -backend-config="key=terraform.tfstate" \
    #                         -backend-config="region=us-east-1"
    encrypt = true
  }
}
 
