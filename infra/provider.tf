provider "aws" {
  region = var.aws_region
}

terraform {
  backend "s3" {
    bucket         = "terraform-tregfd"
    key            = "terraform/state.tfstate" # Path to the state file in the bucket
    region         = "us-east-1"
    encrypt        = true # Enable server-side encryption
  }
}
