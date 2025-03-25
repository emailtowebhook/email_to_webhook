import time
import json
import os
import boto3
import requests
import base64
import uuid
from urllib.parse import parse_qs

# Constants
CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4"
CLOUDFLARE_API_KEY = os.environ.get("CLOUDFLARE_API_KEY")
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
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
            Key=domain
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
            Key=domain,
            Body=json.dumps(data),
            ContentType='application/json'
        )
    except Exception as e:
        print(f"Error saving domain data: {str(e)}")
        raise

def create_cloudflare_worker(worker_name, domain):
    """
    Create a new Cloudflare Worker
    """
    url = f"{CLOUDFLARE_API_BASE}/accounts/{CLOUDFLARE_ACCOUNT_ID}/workers/scripts/{worker_name}"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_KEY}",
        "Content-Type": "application/javascript"
    }
    
    # Default initial code
    default_code = 'export default { async fetch(req) { return new Response("Default function") } }'
    
    response = requests.put(url, data=default_code, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to create worker: {response.text}")
    
    return worker_name

def update_worker_script(worker_name, code):
    """
    Update a Cloudflare Worker script with provided code
    """
    url = f"{CLOUDFLARE_API_BASE}/accounts/{CLOUDFLARE_ACCOUNT_ID}/workers/scripts/{worker_name}"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_KEY}",
        "Content-Type": "application/javascript"
    }
    
    # Default code if none provided
    if not code:
        code = 'export default { async fetch(req) { return new Response("Default function") } }'
    
    response = requests.put(url, data=code, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to update worker script: {response.text}")
    
    return response.json()["result"]

def create_worker_deployment(worker_name, env="dev"):
    """
    Create a deployment for a Cloudflare Worker
    """
    url = f"{CLOUDFLARE_API_BASE}/accounts/{CLOUDFLARE_ACCOUNT_ID}/workers/scripts/{worker_name}/deployments"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "environment": env
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to create deployment: {response.text}")
    
    return response.json()["result"]

def get_worker_details(worker_name):
    """
    Get details for a Cloudflare Worker
    """
    url = f"{CLOUDFLARE_API_BASE}/accounts/{CLOUDFLARE_ACCOUNT_ID}/workers/scripts/{worker_name}"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_KEY}"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Warning: Failed to get worker details: {response.text}")
        return {}
    
    return response.json()["result"]

def get_worker_script(worker_name):
    """
    Get script content for a Cloudflare Worker
    """
    url = f"{CLOUDFLARE_API_BASE}/accounts/{CLOUDFLARE_ACCOUNT_ID}/workers/scripts/{worker_name}/content"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_KEY}"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Warning: Failed to get worker script: {response.text}")
        return ""
    
    return response.text

def add_custom_domain(worker_name, domain):
    """
    Add a custom domain to a Cloudflare Worker
    """
    # First, check if the domain belongs to a Cloudflare zone
    url = f"{CLOUDFLARE_API_BASE}/zones"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    params = {
        "name": ".".join(domain.split(".")[-2:])  # Get the root domain
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        zones = response.json().get("result", [])
        
        if not zones:
            print(f"Warning: No Cloudflare zone found for domain {domain}")
            return False
        
        zone_id = zones[0]["id"]
        
        # Now add the custom domain to the worker
        url = f"{CLOUDFLARE_API_BASE}/zones/{zone_id}/workers/routes"
        payload = {
            "pattern": f"{domain}/*",
            "script": worker_name
        }
        
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code not in [200, 201]:
            print(f"Warning: Failed to add custom domain route: {response.text}")
            return False
        
        # Also set up the DNS record if needed for custom domain
        check_dns_url = f"{CLOUDFLARE_API_BASE}/zones/{zone_id}/dns_records"
        params = {"name": domain}
        
        dns_response = requests.get(check_dns_url, headers=headers, params=params)
        dns_records = dns_response.json().get("result", [])
        
        if not dns_records:
            # Create DNS record for the custom domain
            dns_payload = {
                "type": "CNAME",
                "name": domain.split(".")[0] if domain.count(".") > 1 else "@",
                "content": f"{worker_name}.workers.dev",
                "ttl": 120,
                "proxied": True
            }
            
            dns_create_response = requests.post(check_dns_url, headers=headers, json=dns_payload)
            if dns_create_response.status_code not in [200, 201]:
                print(f"Warning: Failed to create DNS record: {dns_create_response.text}")
        
        return True
    except requests.RequestException as e:
        print(f"Error adding custom domain: {str(e)}")
        return False

def delete_worker(worker_name):
    """
    Delete a Cloudflare Worker
    """
    url = f"{CLOUDFLARE_API_BASE}/accounts/{CLOUDFLARE_ACCOUNT_ID}/workers/scripts/{worker_name}"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_KEY}"
    }
    
    response = requests.delete(url, headers=headers)
    if response.status_code != 200:
        print(f"Warning: Failed to delete worker {worker_name}: {response.text}")
        return False
    
    return True

def delete_custom_domain(worker_name, domain):
    """
    Remove a custom domain from a Cloudflare Worker
    """
    url = f"{CLOUDFLARE_API_BASE}/accounts/{CLOUDFLARE_ACCOUNT_ID}/workers/scripts/{worker_name}/domains/{domain}"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_KEY}"
    }
    
    response = requests.delete(url, headers=headers)
    if response.status_code != 200:
        print(f"Warning: Failed to delete custom domain {domain}: {response.text}")
        return False
    
    return True

def delete_worker_routes(worker_name, domain):
    """
    Delete routes associated with a Cloudflare Worker
    """
    try:
        # First, get the zone ID for the domain
        zone_url = f"{CLOUDFLARE_API_BASE}/zones"
        headers = {
            "Authorization": f"Bearer {CLOUDFLARE_API_KEY}",
            "Content-Type": "application/json"
        }
        
        params = {
            "name": ".".join(domain.split(".")[-2:])  # Get the root domain
        }
        
        response = requests.get(zone_url, headers=headers, params=params)
        response.raise_for_status()
        zones = response.json().get("result", [])
        
        if not zones:
            print(f"Warning: No Cloudflare zone found for domain {domain}")
            return False
        
        zone_id = zones[0]["id"]
        
        # Get all routes for the zone
        routes_url = f"{CLOUDFLARE_API_BASE}/zones/{zone_id}/workers/routes"
        response = requests.get(routes_url, headers=headers)
        response.raise_for_status()
        
        routes = response.json().get("result", [])
        deleted_routes = 0
        
        # Delete routes associated with this worker and domain
        for route in routes:
            if worker_name in route.get("script", "") and domain in route.get("pattern", ""):
                route_id = route.get("id")
                delete_url = f"{CLOUDFLARE_API_BASE}/zones/{zone_id}/workers/routes/{route_id}"
                delete_response = requests.delete(delete_url, headers=headers)
                
                if delete_response.status_code == 200:
                    deleted_routes += 1
                    print(f"Deleted route {route.get('pattern')} for worker {worker_name}")
                else:
                    print(f"Failed to delete route {route.get('pattern')}: {delete_response.text}")
        
        print(f"Deleted {deleted_routes} routes for worker {worker_name}")
        return True
    except Exception as e:
        print(f"Error deleting worker routes: {str(e)}")
        return False

def delete_dns_records(domain):
    """
    Delete DNS records for a custom domain
    """
    try:
        # First, get the zone ID for the domain
        zone_url = f"{CLOUDFLARE_API_BASE}/zones"
        headers = {
            "Authorization": f"Bearer {CLOUDFLARE_API_KEY}",
            "Content-Type": "application/json"
        }
        
        params = {
            "name": ".".join(domain.split(".")[-2:])  # Get the root domain
        }
        
        response = requests.get(zone_url, headers=headers, params=params)
        response.raise_for_status()
        zones = response.json().get("result", [])
        
        if not zones:
            print(f"Warning: No Cloudflare zone found for domain {domain}")
            return False
        
        zone_id = zones[0]["id"]
        
        # Get DNS records for the domain
        dns_url = f"{CLOUDFLARE_API_BASE}/zones/{zone_id}/dns_records"
        params = {"name": domain}
        
        response = requests.get(dns_url, headers=headers, params=params)
        response.raise_for_status()
        
        records = response.json().get("result", [])
        deleted_records = 0
        
        # Delete DNS records for the domain
        for record in records:
            record_id = record.get("id")
            delete_url = f"{CLOUDFLARE_API_BASE}/zones/{zone_id}/dns_records/{record_id}"
            delete_response = requests.delete(delete_url, headers=headers)
            
            if delete_response.status_code == 200:
                deleted_records += 1
                print(f"Deleted DNS record for {domain} (type: {record.get('type')})")
            else:
                print(f"Failed to delete DNS record for {domain}: {delete_response.text}")
        
        print(f"Deleted {deleted_records} DNS records for domain {domain}")
        return True
    except Exception as e:
        print(f"Error deleting DNS records: {str(e)}")
        return False

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
        
        # Get worker details
        worker_name = domain_data["functions"]["worker_name"]
        custom_domain = domain_data["functions"].get("domain", domain)
        
        print(f"Deleting worker {worker_name} with custom domain {custom_domain}")
        
        # First delete routes and DNS records
        routes_deleted = delete_worker_routes(worker_name, custom_domain)
        if routes_deleted:
            print(f"Successfully deleted routes for worker {worker_name}")
        else:
            print(f"Warning: Failed to delete routes for worker {worker_name}")
        
        dns_deleted = delete_dns_records(custom_domain)
        if dns_deleted:
            print(f"Successfully deleted DNS records for domain {custom_domain}")
        else:
            print(f"Warning: Failed to delete DNS records for domain {custom_domain}")
        
        # Delete the worker
        success = delete_worker(worker_name)
        
        if success:
            print(f"Successfully deleted worker {worker_name}")
            # Remove function data from domain
            del domain_data["functions"]
            
            # Save updated domain data
            save_domain_data(domain, domain_data)
            
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "Function deleted successfully",
                    "details": {
                        "worker_deleted": True,
                        "routes_deleted": routes_deleted,
                        "dns_deleted": dns_deleted
                    }
                })
            }
        else:
            print(f"Failed to delete worker {worker_name}")
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "Failed to delete function",
                    "details": {
                        "worker_deleted": False,
                        "routes_deleted": routes_deleted,
                        "dns_deleted": dns_deleted
                    }
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

def handle_post_request(domain, body, worker_name=None):
    """
    Handle POST request to create or update a function
    """
    try:
        # Get existing domain data
        domain_data = get_domain_data(domain)
        
        code = body.get("code", "")
        enabled = body.get("enabled", False)
        environment = body.get("environment", "production").lower()  # Default to production instead of dev
        custom_domain = body.get("custom_domain", domain)

        # Check if function data exists
        if "functions" not in domain_data:
            # Create new worker
            if worker_name is None:
                # Generate a more unique name to avoid conflicts
                timestamp = int(time.time())
                worker_name = f"fn-{domain.replace('.', '-')}-{timestamp}"[:30]
            
            # Create worker
            try:
                create_cloudflare_worker(worker_name, domain)
                print(f"Created new Cloudflare Worker: {worker_name}")
            except Exception as e:
                print(f"Error creating worker: {str(e)}")
                return {
                    "statusCode": 500,
                    "body": json.dumps({
                        "error": f"Failed to create worker: {str(e)}"
                    })
                }
            
            # Update with provided code
            try:
                worker_details = update_worker_script(worker_name, code)
                print(f"Updated worker script for: {worker_name}")
            except Exception as e:
                print(f"Error updating worker script: {str(e)}")
                return {
                    "statusCode": 500,
                    "body": json.dumps({
                        "error": f"Failed to update worker script: {str(e)}"
                    })
                }
            
            # Add custom domain
            domain_success = add_custom_domain(worker_name, custom_domain)
            if domain_success:
                print(f"Successfully added custom domain {custom_domain} to worker {worker_name}")
            else:
                print(f"Warning: Failed to add custom domain {custom_domain} to worker {worker_name}")
            
            # Create deployment
            try:
                deployment = create_worker_deployment(worker_name, environment)
                print(f"Created deployment for worker {worker_name} in environment {environment}")
            except Exception as e:
                print(f"Error creating deployment: {str(e)}")
                return {
                    "statusCode": 500,
                    "body": json.dumps({
                        "error": f"Failed to create deployment: {str(e)}"
                    })
                }
            
            # Update domain data with new structure
            domain_data["functions"] = {
                "worker_name": worker_name,
                "enabled": enabled,
                "code": code,
                "domain": custom_domain,
                "environment": environment,
                "deployment": deployment,
                "domain_configured": domain_success,
                "created_at": time.time()
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
            function_data["enabled"] = enabled
            worker_name = function_data["worker_name"] if worker_name is None else worker_name
            
            # Update worker script
            try:
                worker_details = update_worker_script(worker_name, code)
                print(f"Updated script for worker: {worker_name}")
            except Exception as e:
                print(f"Error updating worker script: {str(e)}")
                return {
                    "statusCode": 500,
                    "body": json.dumps({
                        "error": f"Failed to update worker script: {str(e)}"
                    })
                }
            
            # Create new deployment
            try:
                deployment = create_worker_deployment(worker_name, environment)
                print(f"Created new deployment for worker {worker_name} in environment {environment}")
            except Exception as e:
                print(f"Error creating deployment: {str(e)}")
                return {
                    "statusCode": 500,
                    "body": json.dumps({
                        "error": f"Failed to create deployment: {str(e)}"
                    })
                }
            
            # Check if custom domain has changed
            if custom_domain != function_data.get("domain"):
                domain_success = add_custom_domain(worker_name, custom_domain)
                function_data["domain"] = custom_domain
                function_data["domain_configured"] = domain_success
                print(f"Updated custom domain to {custom_domain} for worker {worker_name}")
            
            # Update function data
            function_data["code"] = code
            function_data["environment"] = environment
            function_data["deployment"] = deployment
            function_data["updated_at"] = time.time()
            
            # Save updated domain data
            save_domain_data(domain, domain_data)
            
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps({
                    "message": f"Function {environment} environment updated successfully",
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
        
        # Get worker name
        worker_name = domain_data["functions"]["worker_name"]
        
        # Get latest worker details
        worker_details = get_worker_details(worker_name)
        
        # Get current script
        current_script = get_worker_script(worker_name)
        
        # Update function data with latest details
        domain_data["functions"]["code"] = current_script
        domain_data["functions"]["worker_details"] = worker_details
        
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
        # Extract worker_name from query parameters if present
        query_params = event.get("queryStringParameters", {}) or {}
        worker_name = query_params.get("worker_name")
        
        # Log extracted parameters for debugging
        print(f"HTTP Method: {http_method}, Domain: {domain}, Worker Name: {worker_name}")
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
            return handle_post_request(domain, body, worker_name)
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