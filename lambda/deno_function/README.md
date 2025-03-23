# Deno Function Lambda Handler

This Lambda function provides a CRUD API for managing Deno Subhosting functions. It allows you to create, read, update, and delete serverless functions that can be invoked by your email parser lambda.

## API Endpoints

The Lambda exposes the following API endpoints through API Gateway:

- `POST /v1/functions/code/{domain}` - Create or update a function
- `GET /v1/functions/code/{domain}` - Get function information
- `PUT /v1/functions/code/{domain}` - Update function settings (enable/disable)
- `DELETE /v1/functions/code/{domain}` - Delete a function

## Integrating with Email Parser Lambda

The email parser Lambda can execute functions after parsing by checking if a function exists for the domain and if it is enabled:

```python
import requests

def execute_deno_function(domain, data):
    # First, check if the function exists and is enabled
    response = requests.get(f"https://api.example.com/v1/functions/code/{domain}")

    if response.status_code != 200:
        print(f"No function found for domain {domain}")
        return None

    function_data = response.json().get("function", {})

    # Check if function is enabled
    if not function_data.get("enabled", False):
        print(f"Function for domain {domain} is disabled")
        return None

    # Use the production deployment URL
    prod_url = function_data.get("prod_deployment_url")

    if not prod_url:
        print(f"No production deployment URL found for domain {domain}")
        return None

    # Execute the function by calling the deployment URL
    function_response = requests.post(
        prod_url,
        json=data,
        headers={"Content-Type": "application/json"}
    )

    return function_response.json()
```

## Function Data Structure

The function data stored in S3 has the following structure:

```json
{
  "function": {
    "project_id": "project-id-from-deno",
    "dev_deployment_id": "dev-deployment-id",
    "dev_deployment_url": "https://function-domain-dev-deployment-id.deno.dev",
    "prod_deployment_id": "prod-deployment-id",
    "prod_deployment_url": "https://function-domain-prod-deployment-id.deno.dev",
    "enabled": true
  }
}
```

## Function Code Format

When creating or updating a function, the request body should include the code and environment:

```json
{
  "code": "export default { async fetch(req) { const data = await req.json(); return new Response(JSON.stringify({processed: true, data}), {headers: {'Content-Type': 'application/json'}}); } }",
  "env": "dev" // or "prod"
}
```

## Enabling/Disabling Functions

To enable or disable a function, send a PUT request:

```json
{
  "enabled": true // or false
}
```
