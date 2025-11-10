# Multi-Account Environment Management Guide

This project uses a **multi-account architecture** where each environment (main, preview, dev) is deployed to its own isolated AWS account.

## Architecture Overview

### Multi-Account Model

Each environment runs in complete isolation within its own AWS account:

**Benefits:**
- **Complete Isolation**: No resource conflicts between environments
- **Security**: Blast radius is limited to a single account
- **Cost Tracking**: Easy to track costs per environment
- **Compliance**: Easier to meet security and compliance requirements
- **Flexibility**: Each environment can have different configurations, regions, and settings

**Environments:**
- **main**: Production environment (separate AWS account)
- **preview**: Staging/preview environment (separate AWS account)
- **dev**: Development environment (separate AWS account)

### Resources Per Environment

Each AWS account contains its complete infrastructure stack:

- **SES Configuration:**
  - Receipt rule set (unique per account)
  - Active rule set activation
  - Receipt rules for email routing
  - Domain verification

- **Compute:**
  - Lambda functions (check and parser)
  - Lambda execution roles and policies

- **Storage:**
  - Email S3 bucket for incoming emails
  - Attachments S3 bucket (publicly readable)
  - KV database S3 bucket
  - Terraform state S3 bucket

- **API:**
  - API Gateway HTTP API
  - Routes and integrations

- **IAM:**
  - Lambda execution roles
  - Service-specific policies

### State Management

Each AWS account has its own Terraform state bucket, suffixed by the account ID for global uniqueness:

```
Account 111111111111 (main):     terraform-state-main-111111111111
Account 222222222222 (preview):  terraform-state-preview-222222222222
Account 333333333333 (dev):      terraform-state-dev-333333333333
```

State files are stored at: `s3://{bucket}/terraform.tfstate`

---

## AWS Account Setup

### Step 1: Create AWS Accounts

You'll need three separate AWS accounts. The recommended approach is using **AWS Organizations**:

1. **Sign in to AWS Organizations** (or create a new organization)
2. **Create member accounts:**
   - Account name: `email-to-webhook-main` (for production)
   - Account name: `email-to-webhook-preview` (for staging)
   - Account name: `email-to-webhook-dev` (for development)
3. **Note the account IDs** - you'll need these for configuration

**Alternative:** You can use standalone AWS accounts if you don't want to use Organizations.

### Step 2: Create IAM Users or Roles

For each AWS account, create credentials for Terraform deployments:

#### Option A: IAM User (Simpler for getting started)

1. Sign in to each AWS account
2. Go to **IAM → Users → Create User**
3. User name: `terraform-deployer`
4. Enable **Access key - Programmatic access**
5. Attach policies (see Required IAM Permissions below)
6. **Save the Access Key ID and Secret Access Key** securely

#### Option B: IAM Role with Assume Role (Better for production)

1. Create a role in each member account
2. Configure trust relationship to allow assumption from your management account
3. Use AWS SSO or `aws sts assume-role` for authentication

### Step 3: Required IAM Permissions

The IAM user or role needs these AWS managed policies:
- `AdministratorAccess` (for initial setup)

Or create a custom policy with these permissions:
- SES: Full access
- S3: Full access
- Lambda: Full access
- API Gateway: Full access
- IAM: Full access (for creating Lambda execution roles)
- CloudWatch Logs: Full access

### Step 4: Configure AWS CLI Profiles

Configure AWS CLI profiles for each environment:

```bash
# Configure main environment
aws configure --profile main
# Enter Access Key ID for main account
# Enter Secret Access Key for main account
# Enter region: us-east-1 (or your preferred region)
# Enter output format: json

# Configure preview environment
aws configure --profile preview
# Enter Access Key ID for preview account
# Enter Secret Access Key for preview account
# Enter region: us-east-1
# Enter output format: json

# Configure dev environment
aws configure --profile dev
# Enter Access Key ID for dev account
# Enter Secret Access Key for dev account
# Enter region: us-east-1
# Enter output format: json
```

Verify your profiles:

```bash
aws sts get-caller-identity --profile main
aws sts get-caller-identity --profile preview
aws sts get-caller-identity --profile dev
```

### Step 5: Create Terraform State Buckets

For each AWS account, create an S3 bucket for Terraform state. The examples below automatically suffix the bucket name with the AWS account ID to ensure uniqueness:

```bash
# Create state bucket for main environment
ACCOUNT_ID_MAIN=$(aws sts get-caller-identity --profile main --query Account --output text)
aws s3 mb s3://terraform-state-main-${ACCOUNT_ID_MAIN} --region us-east-1 --profile main
aws s3api put-bucket-versioning \
  --bucket terraform-state-main-${ACCOUNT_ID_MAIN} \
  --versioning-configuration Status=Enabled \
  --profile main

# Create state bucket for preview environment
ACCOUNT_ID_PREVIEW=$(aws sts get-caller-identity --profile preview --query Account --output text)
aws s3 mb s3://terraform-state-preview-${ACCOUNT_ID_PREVIEW} --region us-east-1 --profile preview
aws s3api put-bucket-versioning \
  --bucket terraform-state-preview-${ACCOUNT_ID_PREVIEW} \
  --versioning-configuration Status=Enabled \
  --profile preview

# Create state bucket for dev environment
ACCOUNT_ID_DEV=$(aws sts get-caller-identity --profile dev --query Account --output text)
aws s3 mb s3://terraform-state-dev-${ACCOUNT_ID_DEV} --region us-east-1 --profile dev
aws s3api put-bucket-versioning \
  --bucket terraform-state-dev-${ACCOUNT_ID_DEV} \
  --versioning-configuration Status=Enabled \
  --profile dev
```

---

## Local Deployment

### Deploy to an Environment

Use the `AWS_PROFILE` environment variable to target the correct AWS account:

**Deploy to Main (Production):**

```bash
AWS_PROFILE=main ENVIRONMENT=main ./deploy.sh
```

**Deploy to Preview (Staging):**

```bash
AWS_PROFILE=preview ENVIRONMENT=preview ./deploy.sh
```

**Deploy to Dev (Development):**

```bash
AWS_PROFILE=dev ENVIRONMENT=dev ./deploy.sh
```

### Destroy an Environment

**Destroy Main Environment:**

```bash
AWS_PROFILE=main ENVIRONMENT=main ./destroy.sh
```

**Destroy Preview Environment:**

```bash
AWS_PROFILE=preview ENVIRONMENT=preview ./destroy.sh
```

**Destroy Dev Environment:**

```bash
AWS_PROFILE=dev ENVIRONMENT=dev ./destroy.sh
```

---

## CI/CD with GitHub Actions

### Required GitHub Secrets

Configure the following secrets in your GitHub repository:

#### Main Environment Secrets
- `AWS_ACCESS_KEY_ID_MAIN` - Access key for main AWS account
- `AWS_SECRET_ACCESS_KEY_MAIN` - Secret key for main AWS account
- `AWS_ACCOUNT_ID_MAIN` - Main AWS account ID
- `AWS_REGION_MAIN` - AWS region for main (e.g., `us-east-1`)

#### Preview Environment Secrets
- `AWS_ACCESS_KEY_ID_PREVIEW` - Access key for preview AWS account
- `AWS_SECRET_ACCESS_KEY_PREVIEW` - Secret key for preview AWS account
- `AWS_ACCOUNT_ID_PREVIEW` - Preview AWS account ID
- `AWS_REGION_PREVIEW` - AWS region for preview (e.g., `us-east-1`)

#### Dev Environment Secrets
- `AWS_ACCESS_KEY_ID_DEV` - Access key for dev AWS account
- `AWS_SECRET_ACCESS_KEY_DEV` - Secret key for dev AWS account
- `AWS_ACCOUNT_ID_DEV` - Dev AWS account ID
- `AWS_REGION_DEV` - AWS region for dev (e.g., `us-east-1`)

#### Shared Secrets
- `MONGODB_URI` - MongoDB connection string (can be shared or per-environment)

### Setting Secrets in GitHub

1. Go to your repository on GitHub
2. Navigate to **Settings → Secrets and variables → Actions**
3. Click **New repository secret**
4. Add each secret with the exact name listed above

### Automatic Deployments

The GitHub Actions workflow automatically deploys based on the branch:
- Push to `main` branch → deploys to main AWS account
- Push to `preview` branch → deploys to preview AWS account
- Push to `dev` branch → deploys to dev AWS account

---

## How It Works

### 1. Environment Variable

The `ENVIRONMENT` variable determines the environment name (used for resource naming):
- Defaults to `main` if not specified
- Used in resource names: `email-to-webhook-emails-${environment}`

### 2. AWS Profile

The `AWS_PROFILE` variable determines which AWS account to deploy to:
- Must be set for all local deployments
- Corresponds to profiles in `~/.aws/credentials` or `~/.aws/config`

### 3. State File Isolation

Each AWS account has its own state bucket and state file:
- State bucket: `terraform-state-${environment}`
- State file: `terraform.tfstate`
- Complete isolation between environments

### 4. Resource Naming

All resources are namespaced by environment:
- Email S3 bucket: `email-to-webhook-emails-${environment}`
- Attachments S3 bucket: `email-to-webhook-attachments-${environment}`
- Database S3 bucket: `email-to-webhook-kv-database-${environment}`
- SES receipt rule set: `${environment}-rule-set`
- SES receipt rule: `catch-emails-${environment}`
- API Gateway: `EmailParserAPI-${environment}`
- Lambda functions: `function-name-${environment}`
- IAM roles/policies: `role-name-${environment}`

---

## Best Practices

### ✅ DO

- Use separate AWS accounts for each environment
- Configure AWS CLI profiles for easy switching
- Always specify both `AWS_PROFILE` and `ENVIRONMENT`
- Keep `main` as your production environment
- Review `terraform plan` before applying changes
- Enable MFA on all AWS accounts
- Use AWS Organizations for centralized account management
- Enable CloudTrail in each account for audit logging
- Set up budget alerts in each account

### ❌ DON'T

- Don't use the same AWS account for multiple environments
- Don't share credentials between environments
- Don't manually edit state files
- Don't deploy to production without testing in preview/dev first
- Don't use root account credentials for deployments

---

## Troubleshooting

### "AWS_PROFILE is not set" Error

Make sure you set the AWS_PROFILE environment variable:

```bash
export AWS_PROFILE=main
./deploy.sh
```

Or set it inline:

```bash
AWS_PROFILE=main ./deploy.sh
```

### "Failed to authenticate with AWS" Error

1. Verify your profile exists:
   ```bash
   aws configure list --profile main
   ```

2. Verify credentials are valid:
   ```bash
   aws sts get-caller-identity --profile main
   ```

3. Check that credentials haven't expired (if using temporary credentials)

### State Bucket Not Found

Create the state bucket in the target AWS account:

```bash
aws s3 mb s3://terraform-state-main --profile main
```

### Wrong Account Deployed

State files are isolated per account, so you can safely:

```bash
# Destroy from wrong account (if needed)
AWS_PROFILE=wrong ENVIRONMENT=wrong ./destroy.sh

# Deploy to correct account
AWS_PROFILE=correct ENVIRONMENT=correct ./deploy.sh
```

---

## Cost Management

### Multiple Accounts

- Each environment incurs separate AWS costs
- Use AWS Cost Explorer in each account to track spending
- Set up billing alerts in each account
- Consider AWS Organizations for consolidated billing
- Destroy unused environments to save costs

### Estimated Monthly Costs (per environment)

- Lambda: ~$5-20 (depends on usage)
- S3: ~$1-5 (depends on storage)
- API Gateway: ~$3.50 per million requests
- SES: $0.10 per 1,000 emails

---

## Migration from Shared Infrastructure

If you're migrating from the old shared infrastructure model:

1. **Backup current state** from the shared S3 bucket
2. **Destroy all old environments** using the old scripts
3. **Destroy shared infrastructure** using `./destroy-shared.sh`
4. **Set up new AWS accounts** as described above
5. **Deploy to new accounts** using the new scripts
6. **Update DNS records** and domain configurations as needed

---

## Security Considerations

### Account-Level Security

- Enable MFA on all AWS accounts
- Use AWS Organizations SCPs (Service Control Policies) for guardrails
- Enable AWS CloudTrail in all accounts
- Enable AWS Config for compliance monitoring
- Use IAM roles instead of IAM users where possible
- Rotate access keys regularly
- Use AWS Secrets Manager for sensitive data

### Network Security

- Consider VPC deployment for Lambda functions
- Use VPC endpoints for S3 access
- Enable S3 bucket encryption
- Use HTTPS for all API endpoints

---

## Additional Resources

- [AWS Organizations Documentation](https://docs.aws.amazon.com/organizations/)
- [AWS Multi-Account Strategy](https://aws.amazon.com/organizations/getting-started/best-practices/)
- [Terraform S3 Backend](https://www.terraform.io/docs/language/settings/backends/s3.html)
- [AWS CLI Configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
