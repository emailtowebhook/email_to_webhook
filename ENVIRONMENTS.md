# Multi-Environment Management Guide

This project uses **separate Terraform state files per environment** to safely manage multiple deployments (main, preview, dev, etc.).

## Architecture

### State File Structure
```
S3 Bucket: terraform-tregfd
├── terraform/main/state.tfstate       (production)
├── terraform/preview/state.tfstate    (preview deployments)
├── terraform/dev/state.tfstate        (development)
└── terraform/<branch>/state.tfstate   (feature branches)
```

Each environment has its own isolated state file in S3.

---

## Usage

### Deploying Environments

**Deploy to Main (Production)**
```bash
./deploy.sh
# or explicitly:
ENVIRONMENT=main ./deploy.sh
```

**Deploy to Preview/Staging**
```bash
ENVIRONMENT=preview ./deploy.sh
```

**Deploy to Development**
```bash
ENVIRONMENT=dev ./deploy.sh
```

**Deploy to Feature Branch**
```bash
ENVIRONMENT=feature-xyz ./deploy.sh
```

---

### Destroying Environments

**Destroy Main Environment**
```bash
./destroy.sh
# or explicitly:
ENVIRONMENT=main ./destroy.sh
```

**Destroy Preview Environment**
```bash
ENVIRONMENT=preview ./destroy.sh
```

**Destroy Any Environment**
```bash
ENVIRONMENT=<env-name> ./destroy.sh
```

---

## How It Works

### 1. **Environment Variable**
The `ENVIRONMENT` variable determines which state file to use:
- Defaults to `main` if not specified
- Can be any valid identifier (alphanumeric, hyphens)

### 2. **State File Isolation**
Each environment gets its own state file:
- `terraform init` uses `-backend-config` to set the state path
- State path: `terraform/${ENVIRONMENT}/state.tfstate`

### 3. **Resource Namespacing**
Resources are namespaced by environment:
- S3 buckets: `bucket-name-${environment}`
- API Gateway: `EmailParserAPI-${environment}`
- Lambda functions: `function-name-${environment}`

---

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Deploy to Environment
  env:
    ENVIRONMENT: ${{ github.ref_name }}  # Uses branch name
    AWS_REGION: us-east-1
  run: ./deploy.sh
```

The environment is automatically set to the branch name, creating isolated deployments per branch.

---

## Best Practices

### ✅ DO
- Use descriptive environment names (`main`, `preview`, `dev`)
- Always specify `ENVIRONMENT` in CI/CD
- Keep `main` as your production environment
- Review `terraform plan` before applying changes

### ❌ DON'T
- Don't use special characters in environment names (stick to alphanumeric + hyphens)
- Don't manually edit state files
- Don't share state files between environments

---

## Troubleshooting

### State File Not Found
If you see "No state file found":
```bash
# Reinitialize with correct environment
cd infra
ENVIRONMENT=your-env terraform init -reconfigure \
  -backend-config="key=terraform/your-env/state.tfstate"
```

### Wrong Environment Deployed
State files are isolated, so you can safely:
```bash
# Destroy the wrong environment
ENVIRONMENT=wrong-env ./destroy.sh

# Deploy to the correct environment
ENVIRONMENT=correct-env ./deploy.sh
```

---

## Migrating Existing State

If you have an existing shared state file, migrate it:

```bash
# 1. Backup current state
cd infra
terraform state pull > state-backup.json

# 2. Initialize with new environment-specific backend
ENVIRONMENT=main terraform init -migrate-state \
  -backend-config="key=terraform/main/state.tfstate"

# 3. Verify migration
terraform state list
```

---

## Cost Considerations

### Multiple Environments
- Each environment creates separate AWS resources
- Costs scale linearly with number of active environments
- Remember to destroy unused environments to save costs

---

## Additional Resources

- [Terraform Backend Configuration](https://www.terraform.io/docs/language/settings/backends/s3.html)
- [Managing Multiple Environments](https://www.terraform.io/docs/cloud/guides/recommended-practices/part1.html)

