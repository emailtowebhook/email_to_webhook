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
   - `DB_CONNECTION_STRING`: Optional - for external database

Deployment runs automatically on pushes to main branch or can be triggered manually from Actions tab.

## Using the API

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
