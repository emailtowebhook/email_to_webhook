provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = "production"
      Project     = "email-to-webhook"
      ManagedBy   = "terraform"
    }
  }
}

terraform {
  backend "s3" {
    bucket         = "terraform-tregfd"
    # key is set dynamically during terraform init based on environment
    # key = "terraform/${environment}/state.tfstate"
    region         = "us-east-1"
    encrypt        = true
  }
}
 
