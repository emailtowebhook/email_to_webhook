import json
import os
import boto3
import requests
import base64
import uuid
from urllib.parse import parse_qs

# Constants
DENO_API_BASE = "https://api.deno.com/v1"
DENO_API_KEY = os.environ.get("DENO_API_KEY")
DENO_ORG_ID = os.environ.get("DENO_ORG_ID")
DATABASE_BUCKET_NAME = os.environ.get("DATABASE_BUCKET_NAME")

# S3 client
s3_client = boto3.client('s3')

def get_domain_data(domain):
    """
    Fetch domain data from the S3 bucket
    """
    try:
        response = s3_client.get_object(
            Bucket=DATABASE_BUCKET_NAME,
            Key=f"{domain}"
        )
        data = json.loads(response['Body'].read().decode('utf-8'))
        return data
    except s3_client.exceptions.NoSuchKey:
        # If the file doesn't exist, return an empty dict
        return {}
    except Exception as e:
        print(f"Error fetching domain data: {str(e)}")
        raise

def save_domain_data(domain, data):
    """
    Save domain data to the S3 bucket
    """
    try:
        s3_client.put_object(
            Bucket=DATABASE_BUCKET_NAME,
            Key=f"{domain}",
            Body=json.dumps(data),
            ContentType='application/json'
        )
    except Exception as e:
        print(f"Error saving domain data: {str(e)}")
        raise

def create_deno_project(domain):
    """
    Create a new Deno project
    """
    url = f"{DENO_API_BASE}/organizations/{DENO_ORG_ID}/projects"
    headers = {
        "Authorization": f"Bearer {DENO_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "name": f"fn-{domain.replace('.', '-')}"[:26],
        "description": f"Email processing function for {domain}"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 201 and response.status_code != 200:
        raise Exception(f"Failed to create project: {response.text}")
    
    return response.json()["id"]

def create_deno_deployment(project_id, code, env="dev"):
    """
    Create a new Deno deployment with the provided code
    """
    url = f"{DENO_API_BASE}/projects/{project_id}/deployments"
    headers = {
        "Authorization": f"Bearer {DENO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Default code if none provided
    if not code:
        code = 'export default { async fetch(req) { return new Response("Default function") } }'
    
    payload = {
        "entryPointUrl": "main.ts",
        "assets": {
            "main.ts": {
                "kind": "file",
                "content": code,
                "encoding": "utf-8"
            }
        },
        "envVars": {},
        "description": f"{env.upper()} environment for {project_id}"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 201 and response.status_code != 200:
        raise Exception(f"Failed to create deployment: {response.text}")
    
    # Get the initial deployment data
    deployment_data = response.json()
    deployment_id = deployment_data["id"]
    
    # Get full deployment details including domain information
    deployment_details = get_deployment_details(deployment_id)
      
    return deployment_details;

def get_deployment_details(deployment_id):
    """
    Get complete details for a deployment including domains
    """
    url = f"{DENO_API_BASE}/deployments/{deployment_id}"
    headers = {
        "Authorization": f"Bearer {DENO_API_KEY}"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Warning: Failed to get deployment details: {response.text}")
        return {}
    
    return response.json()

def get_deployment_code(project_id, deployment_id):
    """
    Retrieve the code from a deployment
    """
    url = f"{DENO_API_BASE}/projects/{project_id}/deployments/{deployment_id}"
    headers = {
        "Authorization": f"Bearer {DENO_API_KEY}"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to get deployment details: {response.text}")
    
    deployment_data = response.json()
    # In a real scenario, we'd need to get the file content
    # This is simplified as the API doesn't directly provide the code
    # You'd typically need to download the assets
    
    # For simplicity, returning a placeholder
    return "// Code for this function is not directly accessible via API"

def handle_post_request(domain, body):
    """
    Handle POST request to create or update a function
    """
    try:
        # Get existing domain data
        domain_data = get_domain_data(domain)
        
        # Check if function data exists
        if "functions" not in domain_data:
            # Create new project and deployments
            project_id = create_deno_project(domain)
            
            # Create dev deployment
            dev_deployment = create_deno_deployment(project_id, code, "dev")
            
            # Create prod deployment with same code initially
            prod_deployment = create_deno_deployment(project_id, code, "prod")
            
            # Update domain data with new structure
            domain_data["functions"] = {
                "project_id": project_id,
                "enabled": False, 
                "dev": dev_deployment,
                "prod": prod_deployment
            }
            
            save_domain_data(domain, domain_data)
            
            return {
                "statusCode": 201,
                "body": json.dumps({
                    "message": "Function created successfully",
                    "functions": domain_data["functions"]
                })
            }
        else:
        # Extract code and environment from request body
            code = body.get("code", "")
            env = body.get("env", "dev").lower()  # Default to dev environment

            # Validate that code is provided
            if not code:
                return {
                    "statusCode": 400,
                    "body": json.dumps({
                        "error": "Function code is required"
                    })
                }
            # Update existing function
            function_data = domain_data["functions"]
            project_id = function_data["project_id"]
            
            # Create new deployment for the specified environment
            if env == "dev" or env == "prod":
                deployment = create_deno_deployment(project_id, code, env)
                # Update with full deployment details
                function_data[env] = get_deployment_details(deployment["id"])
            else:
                return {
                    "statusCode": 400,
                    "body": json.dumps({
                        "error": "Invalid environment. Must be 'dev' or 'prod'."
                    })
                }
            
            # Save updated domain data
            save_domain_data(domain, domain_data)
            
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps({
                    "message": f"Function {env} environment updated successfully",
                    "functions": domain_data["functions"]
                })
            }
    except Exception as e:
        print(f"Error in POST request: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "error": str(e)
            })
        }

def handle_get_request(domain):
    """
    Handle GET request to retrieve function details
    """
    try:
        # Get domain data
        domain_data = get_domain_data(domain)
        
        # Check if function exists
        if "functions" not in domain_data:
            return {
                "statusCode": 404,
                "body": json.dumps({
                    "error": "Function not found"
                })
            }
        
        # Return function data
        return {
            "statusCode": 200,
            "body": json.dumps({
                "functions": domain_data["functions"]
            })
        }
    except Exception as e:
        print(f"Error in GET request: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e)
            })
        }

def handle_delete_request(domain):
    """
    Handle DELETE request to remove a function
    """
    try:
        # Get domain data
        domain_data = get_domain_data(domain)
        
        # Check if function exists
        if "functions" not in domain_data:
            return {
                "statusCode": 404,
                "body": json.dumps({
                    "error": "Function not found"
                })
            }
        
        # Remove function data
        del domain_data["functions"]
        
        # Save updated domain data
        save_domain_data(domain, domain_data)
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Function deleted successfully"
            })
        }
    except Exception as e:
        print(f"Error in DELETE request: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e)
            })
        }

def handle_put_request(domain, body):
    """
    Handle PUT request to update function settings
    """
    try:
        # Get domain data
        domain_data = get_domain_data(domain)
        
        # Check if function exists
        if "functions" not in domain_data:
            return {
                "statusCode": 404,
                "body": json.dumps({
                    "error": "Function not found"
                })
            }
        
        # Extract settings from request body
        enabled = body.get("enabled")
        
        # Update function settings
        if enabled is not None:
            domain_data["functions"]["enabled"] = bool(enabled)
        
        # Save updated domain data
        save_domain_data(domain, domain_data)
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Function settings updated successfully",
                "functions": domain_data["functions"]
            })
        }
    except Exception as e:
        print(f"Error in PUT request: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e)
            })
        }

def lambda_handler(event, context):
    """
    Main Lambda handler function
    """
    try:
        # Extract HTTP method and path parameters
        http_method = event.get("requestContext", {}).get("http", {}).get("method", "")
        domain = event.get("pathParameters", {}).get("domain", "")
        
        # Ensure domain is provided
        if not domain:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Domain parameter is required"
                })
            }
        
        # Parse request body if present
        body = {}
        if "body" in event and event["body"]:
            body = json.loads(event["body"])
        
        # Handle request based on HTTP method
        if http_method == "POST":
            return handle_post_request(domain, body)
        elif http_method == "GET":
            return handle_get_request(domain)
        elif http_method == "DELETE":
            return handle_delete_request(domain)
        elif http_method == "PUT":
            return handle_put_request(domain, body)
        else:
            return {
                "statusCode": 405,
                "body": json.dumps({
                    "error": "Method not allowed"
                })
            }
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e)
            })
        } 