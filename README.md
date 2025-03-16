# Open-Source Email to Webhook Service

An open-source solution that seamlessly transforms incoming emails into webhook notifications. Perfect for automated workflows, real-time email processing, and integration with external services.

## ✨ Features

🔹 **Domain Registration** – Easily register domains and link them to webhook endpoints.  
🔹 **Email Forwarding** – Automatically process and forward incoming emails to registered webhooks.  
🔹 **Attachment Handling** – Store attachments in Amazon S3 and generate accessible public URLs.  
🔹 **DNS Configuration** – Automates DNS verification for SES domain setup.  
🔹 **Serverless Architecture** – Built for scale, security, and cost efficiency.

---

## 🚀 Quick Deployment

Deploy the service with a single command from the root directory:

```sh
./deploy.sh
```

---

## 🔧 Prerequisites

Before you start, ensure you have the following tools installed:

### 🛠 1. AWS CLI

Used for authentication and interaction with AWS services.

#### Install AWS CLI:

```sh
# Linux/macOS
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Windows
# Download the installer: https://awscli.amazonaws.com/AWSCLIV2.msi
```

#### Configure AWS CLI:

```sh
aws configure
```

---

### 🏗 2. Terraform

Infrastructure-as-Code tool for provisioning AWS resources.

#### Install Terraform:

```sh
# Linux
wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor | sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform

# macOS
brew tap hashicorp/tap
brew install hashicorp/tap/terraform

# Windows
# Download: https://developer.hashicorp.com/terraform/downloads
```

#### Verify installation:

```sh
terraform --version
```

---

### 📂 3. S3 Bucket for Terraform State

Terraform requires an S3 bucket to store state files.

#### Create an S3 bucket:

```sh
aws s3 mb s3://my-terraform-state-bucket --region us-east-1
```

#### Configure Terraform backend in `provider.tf`:

```hcl
terraform {
  backend "s3" {
    bucket = "my-terraform-state-bucket"
    key    = "terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}
```

Replace `my-terraform-state-bucket` with your actual bucket name.

---

## 🚀 Using the API

Once deployed, use the API to register domains and their corresponding webhooks.

### Register a Domain & Webhook

```sh
curl -X POST '<api_gateway_url>' \
  -H 'Content-Type: application/json' \
  -d '{
    "domain": "yourdomain.com",
    "webhook": "https://your-webhook-endpoint.com/path"
  }'
```

After registering, you will receive two DNS records that need to be set up in your DNS manager. Once configured, you can start sending emails to your registered domain.

---

## 👋 Connect with Me

💼 **LinkedIn**: [Yakir Perlin](https://www.linkedin.com/in/yakirperlin/)  
𝕏: [@yakirbipbip](https://x.com/yakirbipbip)

---

## 📜 License

Licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

💡 **Have questions or ideas?** Open an issue or start a discussion on [GitHub](https://github.com/emailtowebhook/emailtowebhook/issues)
