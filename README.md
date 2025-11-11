# Email to Webhook Service

Transforms emails into webhook notifications with attachment handling via AWS.

## Cloud Version

A hosted version of this service is available at [emailtowebhook.com](https://emailtowebhook.com/dashboard).

## Features

- Domain registration with webhook endpoints
- Email forwarding to webhooks
- S3 attachment storage
- Automated DNS verification
- Serverless architecture

## Deployment

### Multi-Account Architecture

This project uses a **multi-account architecture** where each environment deploys to its own isolated AWS account:

- **main**: Production environment (dedicated AWS account)
- **preview**: Staging environment (dedicated AWS account)
- **dev**: Development environment (dedicated AWS account)

**Benefits:**
- Complete resource isolation between environments
- Enhanced security with account-level boundaries
- Independent cost tracking per environment
- No shared infrastructure dependencies

**Prerequisites:**
1. Three separate AWS accounts (or one account for testing)
2. AWS CLI configured with profiles for each account
3. Terraform installed
4. S3 bucket for Terraform state in each account

**Quick Start:**

```bash
# Deploy to main environment
AWS_PROFILE=main ENVIRONMENT=main ./deploy.sh

# Deploy to preview environment
AWS_PROFILE=preview ENVIRONMENT=preview ./deploy.sh

# Deploy to dev environment
AWS_PROFILE=dev ENVIRONMENT=dev ./deploy.sh
```

📖 **See [ENVIRONMENTS.md](ENVIRONMENTS.md)** for complete setup guide including:
- AWS account creation
- AWS CLI profile configuration
- Terraform state bucket setup
- IAM permissions required
- GitHub Actions configuration

### GitHub Actions

1. Fork/clone this repository
2. Set repository secrets for each environment:

**Main Environment (Production):**
   - `AWS_ACCESS_KEY_ID_MAIN`: AWS access key for main account
   - `AWS_SECRET_ACCESS_KEY_MAIN`: AWS secret key for main account
   - `AWS_ACCOUNT_ID_MAIN`: Main AWS account ID
   - `AWS_REGION_MAIN`: AWS region (e.g., `us-east-1`)

**Preview Environment (Staging):**
   - `AWS_ACCESS_KEY_ID_PREVIEW`: AWS access key for preview account
   - `AWS_SECRET_ACCESS_KEY_PREVIEW`: AWS secret key for preview account
   - `AWS_ACCOUNT_ID_PREVIEW`: Preview AWS account ID
   - `AWS_REGION_PREVIEW`: AWS region (e.g., `us-east-1`)

**Dev Environment:**
   - `AWS_ACCESS_KEY_ID_DEV`: AWS access key for dev account
   - `AWS_SECRET_ACCESS_KEY_DEV`: AWS secret key for dev account
   - `AWS_ACCOUNT_ID_DEV`: Dev AWS account ID
   - `AWS_REGION_DEV`: AWS region (e.g., `us-east-1`)

**Shared Secrets:**
   - `MONGODB_URI`: (optional) MongoDB connection string if using external database

Deployment runs automatically on pushes to `main`, `preview`, or `dev` branches. Each branch deploys to its dedicated AWS account.

## Using the API

After successful deployment, you will see the API Gateway URL:
![API Gateway URL Example](https://res.cloudinary.com/dhwxfvlrn/image/upload/f_auto,q_auto/9fd400e4-af82-4f0f-b0eb-ac9036dcede3.png)

### Register Domain

```
curl -X POST '<api_gateway_url>/v1/domain/yourdomain.com' -H 'Content-Type: application/json' -d '{"webhook": "https://your-webhook-endpoint.com/path"}'
```

### Get Domain Status

```
curl -X GET '<api_gateway_url>/v1/domain/yourdomain.com'
```

### Update Domain

```
curl -X PUT '<api_gateway_url>/v1/domain/yourdomain.com' -H 'Content-Type: application/json' -d '{"webhook": "https://your-new-webhook-endpoint.com/path"}'
```

### Delete Domain

```
curl -X DELETE '<api_gateway_url>/v1/domain/yourdomain.com'
```

Once verified, emails to `anything@yourdomain.com` will be sent to your webhook as JSON with S3 attachment links.

## Contributing and Support

### How to Contribute

1. Fork the repository
2. Create a new branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Commit your changes (`git commit -m 'Add some feature'`)
5. Push to the branch (`git push origin feature/your-feature`)
6. Open a Pull Request

### Getting Support

If you encounter issues or have questions:

1. Check existing [GitHub Issues](https://github.com/emailtowebhook/emailtowebhook/issues) first
2. Open a new Issue with:
   - Clear description of the problem
   - Steps to reproduce
   - Expected vs actual behavior
   - System information (AWS region, etc.)

For security concerns, please report them directly to maintainers rather than opening public issues.

## Connect

- **LinkedIn**: [Yakir Perlin](https://www.linkedin.com/in/yakirperlin/)
- **Twitter**: [@yakirbipbip](https://x.com/yakirbipbip)

Licensed under MIT.
