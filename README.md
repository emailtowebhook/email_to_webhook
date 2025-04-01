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

## Deployment with GitHub Actions

1. Fork/clone this repository
2. Set required repository secrets:
   - `AWS_ACCESS_KEY_ID`: Your AWS access key
   - `AWS_SECRET_ACCESS_KEY`: Your AWS secret key
   - `AWS_ACCOUNT_ID`: Your AWS account ID
   - `DB_CONNECTION_STRING`: Optional - for external database (emails are stored in AWS by default)

Deployment runs automatically on pushes to main branch or can be triggered manually from Actions tab.

## Using the API

### Register Domain

```sh
curl -X POST '<api_gateway_url>/v1/domain/yourdomain.com' -H 'Content-Type: application/json' -d '{"webhook": "https://your-webhook-endpoint.com/path"}'
```

### Get Domain Status

```sh
curl -X GET '<api_gateway_url>/v1/domain/yourdomain.com'
```

### Update Domain

```sh
curl -X PUT '<api_gateway_url>/v1/domain/yourdomain.com' -H 'Content-Type: application/json' -d '{"webhook": "https://your-new-webhook-endpoint.com/path"}'
```

### Delete Domain

```sh
curl -X DELETE '<api_gateway_url>/v1/domain/yourdomain.com'
```

Once verified, emails to `anything@yourdomain.com` will be sent to your webhook as JSON with S3 attachment links.

## Connect

- **LinkedIn**: [Yakir Perlin](https://www.linkedin.com/in/yakirperlin/)
- **Twitter**: [@yakirbipbip](https://x.com/yakirbipbip)

Licensed under MIT. For issues or ideas, please use [GitHub Issues](https://github.com/emailtowebhook/emailtowebhook/issues)
