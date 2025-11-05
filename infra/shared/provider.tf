provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = "shared"
      Project     = "email-to-webhook"
      ManagedBy   = "terraform"
    }
  }
}

terraform {
  backend "s3" {
    bucket  = "terraform-tregfd"
    key     = "terraform/shared/state.tfstate"
    region  = "us-east-1"
    encrypt = true
  }
}

