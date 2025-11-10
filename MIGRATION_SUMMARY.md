# Multi-Account Migration Summary

## ✅ Migration Complete

Your infrastructure has been successfully migrated from a shared infrastructure model to a multi-account architecture.

## What Changed

### 🗑️ Deleted Files

The following shared infrastructure files were removed:
- `infra/shared/main.tf`
- `infra/shared/provider.tf`
- `infra/shared/variables.tf`
- `infra/shared/outputs.tf`
- `deploy-shared.sh`
- `destroy-shared.sh`
- `infra/destroy_routes.tf`
- `infra/route_cleanup.sh`

### 📝 Modified Files

#### Infrastructure Configuration

**`infra/main.tf`**
- Added per-environment SES receipt rule set (no longer shared)
- Added SES active receipt rule set activation
- Updated SES receipt rule to reference local rule set
- Removed dependency on shared infrastructure

**`infra/provider.tf`**
- Made Terraform backend fully configurable
- Removed hardcoded state bucket
- Backend now accepts bucket, key, and region via `-backend-config` flags
- Updated default tags to use environment variable

**`infra/variables.tf`**
- Improved documentation for all variables
- Added `state_bucket_name` variable
- Clarified that `aws_account_id` is required (no default)
- Updated `environment` description for multi-account context

#### Deployment Scripts

**`deploy.sh`**
- Complete rewrite for multi-account support
- Added `AWS_PROFILE` requirement and validation
- Added AWS credential verification
- Automatic account ID and region detection from profile
- Dynamic state bucket configuration per environment
- Removed shared infrastructure dependency checks
- Enhanced error messages and user guidance

**`destroy.sh`**
- Complete rewrite for multi-account support
- Added `AWS_PROFILE` requirement and validation
- Dynamic state bucket configuration
- Improved S3 bucket emptying logic
- Enhanced error handling

#### CI/CD

**`.github/workflows/deploy.yml`**
- Branch-to-environment mapping (main → main, preview → preview, dev → dev)
- Conditional AWS credential selection per branch
- Separate secrets for each environment:
  - `AWS_ACCESS_KEY_ID_MAIN/PREVIEW/DEV`
  - `AWS_SECRET_ACCESS_KEY_MAIN/PREVIEW/DEV`
  - `AWS_ACCOUNT_ID_MAIN/PREVIEW/DEV`
  - `AWS_REGION_MAIN/PREVIEW/DEV`
- Dynamic state bucket configuration
- Added Terraform plan step for visibility

#### Documentation

**`ENVIRONMENTS.md`**
- Complete rewrite for multi-account architecture
- Comprehensive AWS account setup guide
- AWS CLI profile configuration instructions
- Required IAM permissions documentation
- Terraform state bucket creation guide
- Local deployment examples
- GitHub Actions secrets configuration
- Security best practices
- Troubleshooting guide
- Cost management guidance

**`README.md`**
- Updated deployment section for multi-account architecture
- Updated prerequisites
- New GitHub Actions secrets list
- Clarified branch-based deployments

## Architecture Changes

### Before (Shared Infrastructure)
```
Single AWS Account
├── Shared SES Receipt Rule Set (all environments)
├── Environment: main
│   ├── Lambda Functions
│   ├── API Gateway
│   └── S3 Buckets
├── Environment: preview
│   ├── Lambda Functions
│   ├── API Gateway
│   └── S3 Buckets
└── Environment: dev
    ├── Lambda Functions
    ├── API Gateway
    └── S3 Buckets
```

### After (Multi-Account)
```
AWS Account 111111111111 (main)
├── SES Receipt Rule Set
├── Lambda Functions
├── API Gateway
├── S3 Buckets
└── Terraform State Bucket

AWS Account 222222222222 (preview)
├── SES Receipt Rule Set
├── Lambda Functions
├── API Gateway
├── S3 Buckets
└── Terraform State Bucket

AWS Account 333333333333 (dev)
├── SES Receipt Rule Set
├── Lambda Functions
├── API Gateway
├── S3 Buckets
└── Terraform State Bucket
```

### Terraform State Buckets

Terraform keeps remote state in a dedicated S3 bucket per account, using the pattern `terraform-state-${environment}-${account_id}`. For example:

```
terraform-state-main-111111111111
terraform-state-preview-222222222222
terraform-state-dev-333333333333
```

State files live at `s3://{bucket}/terraform.tfstate`.

## Next Steps

### 1. Set Up AWS Accounts

You need three separate AWS accounts (or one for testing). Options:

**Option A: AWS Organizations (Recommended)**
1. Create an AWS Organization
2. Create member accounts for main, preview, and dev
3. Note the account IDs

**Option B: Standalone Accounts**
1. Create three separate AWS accounts manually
2. Note the account IDs

### 2. Create IAM Users/Roles

For each AWS account:
1. Create an IAM user named `terraform-deployer`
2. Attach `AdministratorAccess` policy (or custom policy with required permissions)
3. Create access keys
4. Save credentials securely

### 3. Configure AWS CLI Profiles

```bash
# Configure main environment
aws configure --profile main
# Enter access key, secret key, region (us-east-1), output format (json)

# Configure preview environment
aws configure --profile preview
# Enter access key, secret key, region (us-east-1), output format (json)

# Configure dev environment
aws configure --profile dev
# Enter access key, secret key, region (us-east-1), output format (json)
```

Verify:
```bash
aws sts get-caller-identity --profile main
aws sts get-caller-identity --profile preview
aws sts get-caller-identity --profile dev
```

### 4. Create Terraform State Buckets

For each account (bucket names automatically include the AWS account ID for uniqueness):

```bash
# Main environment
ACCOUNT_ID_MAIN=$(aws sts get-caller-identity --profile main --query Account --output text)
aws s3 mb s3://terraform-state-main-${ACCOUNT_ID_MAIN} --region us-east-1 --profile main
aws s3api put-bucket-versioning --bucket terraform-state-main-${ACCOUNT_ID_MAIN} \
  --versioning-configuration Status=Enabled --profile main

# Preview environment
ACCOUNT_ID_PREVIEW=$(aws sts get-caller-identity --profile preview --query Account --output text)
aws s3 mb s3://terraform-state-preview-${ACCOUNT_ID_PREVIEW} --region us-east-1 --profile preview
aws s3api put-bucket-versioning --bucket terraform-state-preview-${ACCOUNT_ID_PREVIEW} \
  --versioning-configuration Status=Enabled --profile preview

# Dev environment
ACCOUNT_ID_DEV=$(aws sts get-caller-identity --profile dev --query Account --output text)
aws s3 mb s3://terraform-state-dev-${ACCOUNT_ID_DEV} --region us-east-1 --profile dev
aws s3api put-bucket-versioning --bucket terraform-state-dev-${ACCOUNT_ID_DEV} \
  --versioning-configuration Status=Enabled --profile dev
```

### 5. Deploy Infrastructure

```bash
# Deploy to main
AWS_PROFILE=main ENVIRONMENT=main ./deploy.sh

# Deploy to preview
AWS_PROFILE=preview ENVIRONMENT=preview ./deploy.sh

# Deploy to dev
AWS_PROFILE=dev ENVIRONMENT=dev ./deploy.sh
```

### 6. Configure GitHub Actions Secrets

In your GitHub repository, go to Settings → Secrets and variables → Actions, and add:

**Main Environment:**
- `AWS_ACCESS_KEY_ID_MAIN`
- `AWS_SECRET_ACCESS_KEY_MAIN`
- `AWS_ACCOUNT_ID_MAIN`
- `AWS_REGION_MAIN` (e.g., `us-east-1`)

**Preview Environment:**
- `AWS_ACCESS_KEY_ID_PREVIEW`
- `AWS_SECRET_ACCESS_KEY_PREVIEW`
- `AWS_ACCOUNT_ID_PREVIEW`
- `AWS_REGION_PREVIEW` (e.g., `us-east-1`)

**Dev Environment:**
- `AWS_ACCESS_KEY_ID_DEV`
- `AWS_SECRET_ACCESS_KEY_DEV`
- `AWS_ACCOUNT_ID_DEV`
- `AWS_REGION_DEV` (e.g., `us-east-1`)

**Shared:**
- `MONGODB_URI` (optional)

### 7. Test Deployments

Push to each branch to trigger automatic deployments:
- Push to `main` branch → deploys to main AWS account
- Push to `preview` branch → deploys to preview AWS account
- Push to `dev` branch → deploys to dev AWS account

## Benefits of Multi-Account Architecture

✅ **Complete Isolation**: No resource conflicts between environments
✅ **Enhanced Security**: Account-level security boundaries
✅ **Independent Scaling**: Each environment can scale independently
✅ **Cost Tracking**: Clear cost separation per environment
✅ **Compliance**: Easier to meet security and compliance requirements
✅ **Blast Radius**: Issues in one environment don't affect others

## Support

For detailed setup instructions, see:
- `ENVIRONMENTS.md` - Complete multi-account setup guide
- `README.md` - Quick start and API usage

## Rollback (If Needed)

If you need to rollback to the old shared infrastructure model:

1. Checkout the previous commit: `git checkout <previous-commit>`
2. Redeploy shared infrastructure: `./deploy-shared.sh`
3. Redeploy environments: `./deploy.sh`

**Note**: The codebase has been updated and the old model is no longer recommended.

