# Multi-Environment Management Guide

This project uses a **two-tier infrastructure model** with shared SES resources and per-environment application resources.

## Architecture

### Two-Tier Infrastructure Model

#### 1. Shared Infrastructure (`infra/shared/`)

AWS SES has account-level limitations - only one receipt rule set can be active at a time. Therefore, the SES receipt rule set is deployed once and shared across all environments:

**Resources:**

- SES receipt rule set (account-level resource)
- SES active receipt rule set activation

**State File:**

```
S3: terraform-tregfd/terraform/shared/state.tfstate
```

#### 2. Per-Environment Infrastructure (`infra/`)

Each environment (main, preview, dev, etc.) gets its own isolated application resources:

**Resources:**

- Lambda functions (unique per environment)
- API Gateway endpoints (unique per environment)
- IAM roles and policies (namespaced by environment)
- Email S3 bucket for incoming emails (unique per environment)
- Attachments S3 bucket (unique per environment)
- KV database S3 bucket (unique per environment)
- SES receipt rule (routes emails to environment-specific bucket)

**State Files:**

```
S3 Bucket: terraform-tregfd
├── terraform/main/state.tfstate       (production)
├── terraform/preview/state.tfstate    (preview deployments)
├── terraform/dev/state.tfstate        (development)
└── terraform/<branch>/state.tfstate   (feature branches)
```

### Email Routing

Each environment has its own email S3 bucket (e.g., `email-to-webhook-emails-main`, `email-to-webhook-emails-dev`). Incoming emails are routed to the environment-specific bucket via SES receipt rules, and each environment's Lambda function is triggered by S3 events on its own bucket.

---

## Initial Setup

### Step 1: Deploy Shared Infrastructure (One-Time)

Before deploying any environment, you must deploy the shared SES infrastructure:

```bash
./deploy-shared.sh
```

Or via GitHub Actions: Run the "Deploy Shared Infrastructure" workflow manually.

**What this creates:**

- SES receipt rule set (shared container for all environment receipt rules)
- Activates the receipt rule set

**Important:** This only needs to be done once per AWS account.

---

## Daily Usage

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

### Destroying Environments

**Important:** Destroying an environment does NOT destroy shared SES infrastructure.

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

### Destroying Shared Infrastructure

**⚠️ WARNING: This affects ALL environments!**

Only destroy shared infrastructure when you're done with ALL environments:

```bash
./destroy-shared.sh
```

Or via GitHub Actions: Run the "Destroy Shared Infrastructure" workflow (requires typing "destroy-all" to confirm).

This will:

- Deactivate SES receipt rule set
- Remove the shared receipt rule set

**Note:** Per-environment email buckets and receipt rules are automatically destroyed when destroying each environment.

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

**Shared Resources (no namespacing):**

- SES receipt rule set: `default-rule-set`

**Per-Environment Resources (namespaced):**

- Email S3 bucket: `email-to-webhook-emails-${environment}`
- Attachments S3 bucket: `bucket-name-${environment}`
- Database S3 bucket: `bucket-name-${environment}`
- SES receipt rule: `catch-emails-${environment}`
- API Gateway: `EmailParserAPI-${environment}`
- Lambda functions: `function-name-${environment}`
- IAM roles/policies: `role-name-${environment}`

---

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Deploy to Environment
  env:
    ENVIRONMENT: ${{ github.ref_name }} # Uses branch name
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
