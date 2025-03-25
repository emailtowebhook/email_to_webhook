# Cloudflare Workers Function Manager

This Lambda function provides a RESTful API for managing Cloudflare Workers with custom domains. It allows you to:

1. Create and deploy workers with custom domains
2. Update worker code
3. Enable/disable workers
4. Delete workers and their associated resources

## Environment Variables

The following environment variables are required:

- `CLOUDFLARE_API_KEY`: Your Cloudflare API token with Workers and DNS permissions
- `CLOUDFLARE_ACCOUNT_ID`: Your Cloudflare account ID
- `DATABASE_BUCKET_NAME`: The S3 bucket used for storing configuration data

## API Endpoints

The API supports the following endpoints:

### POST /{domain}

Creates a new worker or updates an existing one.

**Request Body:**

```json
{
  "code": "export default { async fetch(req) { return new Response('Hello, World!') } }",
  "enabled": true,
  "environment": "production",
  "custom_domain": "api.example.com"
}
```

**Query Parameters:**

- `worker_name` (optional): Specify a custom name for the worker

### GET /{domain}

Retrieves information about an existing worker.

### DELETE /{domain}

Deletes a worker and all associated resources (routes, DNS records).

### PUT /{domain}

Updates worker settings.

**Request Body:**

```json
{
  "enabled": true
}
```

## Examples

### Creating a New Worker

```bash
curl -X POST https://your-api-gateway.execute-api.region.amazonaws.com/prod/api.example.com \
  -H "Content-Type: application/json" \
  -d '{
    "code": "export default { async fetch(req) { return new Response(\"Hello from Cloudflare Workers!\") } }",
    "enabled": true,
    "custom_domain": "api.example.com"
  }'
```

### Updating Worker Code

```bash
curl -X POST https://your-api-gateway.execute-api.region.amazonaws.com/prod/api.example.com \
  -H "Content-Type: application/json" \
  -d '{
    "code": "export default { async fetch(req) { return new Response(\"Updated response!\") } }",
    "environment": "production"
  }'
```

### Retrieving Worker Information

```bash
curl -X GET https://your-api-gateway.execute-api.region.amazonaws.com/prod/api.example.com
```

### Deleting a Worker

```bash
curl -X DELETE https://your-api-gateway.execute-api.region.amazonaws.com/prod/api.example.com
```

## Worker Template

This project includes a template file (`template.js`) that you can use as a starting point for your Cloudflare Workers. The template demonstrates:

- Setting up API routes
- Handling different HTTP methods (GET, POST, PUT)
- Using Cloudflare KV storage (if configured)
- Implementing caching with Cache-Control headers
- Accessing Cloudflare-specific request information
- Error handling and logging

To use the template, simply include it as the `code` parameter in your POST request:

```bash
curl -X POST https://your-api-gateway.execute-api.region.amazonaws.com/prod/api.example.com \
  -H "Content-Type: application/json" \
  -d '{
    "code": "'"$(cat template.js)"'",
    "enabled": true,
    "custom_domain": "api.example.com"
  }'
```

## Implementation Details

This function:

1. Manages Cloudflare Workers through the Cloudflare API
2. Sets up custom domains by creating appropriate DNS records and Worker routes
3. Stores configuration data in S3
4. Handles deployments for different environments

## Cloudflare Workers vs Deno Deploy

This implementation replaces the previous Deno Deploy implementation with Cloudflare Workers. Key differences:

- Cloudflare Workers has a more comprehensive API for programmatic management
- Custom domains are handled differently, requiring both DNS records and Worker routes
- Deployment is managed through a single worker with environment settings rather than separate deployments for dev/prod
