# Quick Start - Multi-Environment Setup

## First Time Setup

### Step 1: Deploy Shared Infrastructure (one-time)
```bash
./deploy-shared.sh
```

This creates the shared SES infrastructure used by all environments:
- SES receipt rule set
- Shared email S3 bucket
- SES email routing rules

### Step 2: Deploy Your First Environment
```bash
./deploy.sh
```

## Daily Usage

### Deploy
```bash
# Main (production)
./deploy.sh

# Other environments
ENVIRONMENT=preview ./deploy.sh
ENVIRONMENT=dev ./deploy.sh
```

### Destroy
```bash
# Main (production)
./destroy.sh

# Other environments
ENVIRONMENT=preview ./destroy.sh
ENVIRONMENT=dev ./destroy.sh
```

## Environment Names
- `main` - Production (default)
- `preview` - Staging/Preview
- `dev` - Development
- Any branch name for feature deployments

## Architecture

### Two-Tier Infrastructure
1. **Shared Infrastructure** (`infra/shared/`)
   - SES receipt rule set (account-level, only one can be active)
   - Shared email S3 bucket (all environments store emails here)
   - State file: `s3://terraform-tregfd/terraform/shared/state.tfstate`

2. **Per-Environment Infrastructure** (`infra/`)
   - Lambda functions (unique per environment)
   - API Gateway endpoints (unique per environment)
   - IAM roles and policies (namespaced per environment)
   - State files: `s3://terraform-tregfd/terraform/${ENVIRONMENT}/state.tfstate`

### What Changed?
- ✅ SES resources are now shared (avoiding conflicts)
- ✅ Email storage uses one shared bucket with prefix-based organization
- ✅ Each environment has isolated Lambda functions and API Gateway
- ✅ Separate state files for shared vs per-environment resources

## Need More Info?
See [ENVIRONMENTS.md](../ENVIRONMENTS.md) for complete documentation.

