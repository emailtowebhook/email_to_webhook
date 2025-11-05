# Quick Start - Multi-Environment Setup

## First Time Setup

**Deploy to main environment**:
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

## What Changed?
- ✅ Each environment now has its own isolated state file
- ✅ State files are stored at: `s3://terraform-tregfd/terraform/${ENVIRONMENT}/state.tfstate`
- ✅ DynamoDB table prevents concurrent modifications
- ✅ Resources are namespaced by environment (e.g., `bucket-name-main`, `bucket-name-preview`)

## Need More Info?
See [ENVIRONMENTS.md](../ENVIRONMENTS.md) for complete documentation.

