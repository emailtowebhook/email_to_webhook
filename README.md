# Email to Webhook Service

A serverless AWS solution that forwards incoming emails to webhooks. This service allows you to register domains and receive email content via webhook notifications, with support for attachments and inline images.

## Key Features

- **Domain Registration**: Register domains and associate them with webhook endpoints
- **Email Forwarding**: Automatically process incoming emails and forward content to registered webhooks
- **Attachment Handling**: Store email attachments in S3 and provide public URLs
- **DNS Configuration**: Automated DNS verification for SES domain setup
- **Serverless Architecture**: Built on AWS Lambda, API Gateway, S3, and SES

## Deployment Instructions

Run the deployment script from the root directory:

```
./deploy.sh
```

## Prerequisites

Before you begin, ensure you have the following tools installed:

1. **AWS CLI** - The AWS Command Line Interface is required for authentication and interaction with AWS services.

   ```
   # Install AWS CLI on Linux/macOS
   curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
   unzip awscliv2.zip
   sudo ./aws/install

   # Install AWS CLI on Windows
   # Download the installer from: https://awscli.amazonaws.com/AWSCLIV2.msi
   ```

   Configure AWS CLI with your credentials:

   ```
   aws configure
   ```

2. **Terraform** - Infrastructure as Code tool used to provision and manage AWS resources.

   ```
   # Install Terraform on Linux
   wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor | sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg
   echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
   sudo apt update && sudo apt install terraform

   # Install Terraform on macOS
   brew tap hashicorp/tap
   brew install hashicorp/tap/terraform

   # Install Terraform on Windows
   # Download from: https://developer.hashicorp.com/terraform/downloads
   ```

   Verify installation:

   ```
   terraform --version
   ```

3. **S3 Bucket for Terraform State** - Create an S3 bucket to store Terraform state files.

   ```
   # Create an S3 bucket for Terraform state
   aws s3 mb s3://my-terraform-state-bucket-name --region us-east-1
   ```

   Then configure your Terraform backend in `provider.tf`:

   ```hcl
   terraform {
     backend "s3" {
       bucket = "my-terraform-state-bucket-name"
       key    = "terraform.tfstate"
       region = "us-east-1"
     }
   }

   provider "aws" {
     region = var.aws_region
   }
   ```

   Make sure to replace `my-terraform-state-bucket-name` with your actual bucket name.

## Using the API

After deployment, you can use the API to register domains and their corresponding webhooks:

### Register a Domain with a Webhook

```bash
curl -X POST '<api_gateway_url>/v1/domain' \
-H 'Content-Type: application/json' \
-d '{
"domain": "yourdomain.com",
"webhook": "https://your-webhook-endpoint.com/path"
}'
```

## Contact

Feel free to connect with me:

- LinkedIn: [Yakir Perlin](https://www.linkedin.com/in/yakirperlin/)
- Twitter: [@yakirbipbip](https://x.com/yakirbipbip)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
