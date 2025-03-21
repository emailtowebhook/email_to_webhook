# MIT License
# Copyright (c) 2023 [Your Name or Organization]
# See LICENSE file for details

import boto3
import json
import secrets
import string
import re
import os

ses_client = boto3.client('ses')
iam_client = boto3.client('iam')


def generate_password():
    """Generate a secure password for SMTP credentials."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|"
    return ''.join(secrets.choice(alphabet) for i in range(16))


def get_existing_smtp_user(domain):
    """Check if SMTP user already exists for the domain."""
    username = f"smtp-{domain.replace('.', '-')}"
    try:
        # Try to get the user
        iam_client.get_user(UserName=username)

        # If user exists, get their access keys
        response = iam_client.list_access_keys(UserName=username)

        if response['AccessKeyMetadata']:
            # Return existing access key if available
            access_key_id = response['AccessKeyMetadata'][0]['AccessKeyId']

            return {
                "username": access_key_id,
                "smtp_server": "email-smtp.us-east-1.amazonaws.com",
                "smtp_port": 587,
                "smtp_tls": True
            }
        return None
    except iam_client.exceptions.NoSuchEntityException:
        return None


def create_smtp_user(domain):
    """Create IAM user with SES SMTP permissions and generate SMTP credentials."""
    # First check if user already exists
    existing_user = get_existing_smtp_user(domain)
    if existing_user:
        return existing_user

    # Create unique username based on domain
    username = f"smtp-{domain.replace('.', '-')}"

    try:
        # Create IAM user
        iam_client.create_user(UserName=username)

        # Attach SES sending policy
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "ses:SendRawEmail",
                    "ses:SendEmail"
                ],
                "Resource": "*"
            }]
        }

        iam_client.put_user_policy(
            UserName=username,
            PolicyName=f"{username}-ses-policy",
            PolicyDocument=json.dumps(policy_document)
        )

        # Create SMTP credentials
        response = iam_client.create_access_key(UserName=username)

        smtp_credentials = {
            "username": response['AccessKey']['AccessKeyId'],
            "password": response['AccessKey']['SecretAccessKey'],
            "smtp_server": "email-smtp.us-east-1.amazonaws.com",
            "smtp_port": 587,
            "smtp_tls": True
        }

        return smtp_credentials

    except Exception as e:
        # If there's an error, attempt to clean up the IAM user
        try:
            iam_client.delete_user(UserName=username)
        except:
            pass
        raise e


def verify_domain(domain):
    """Initiate SES domain verification if not already verified."""
    status = check_verification_status(domain)

    # Only verify if not already verified or pending
    if status in ['NotStarted', 'Failed']:
        response = ses_client.verify_domain_identity(Domain=domain)
        return response['VerificationToken']

    # Get existing verification token
    response = ses_client.get_identity_verification_attributes(
        Identities=[domain]
    )
    return response['VerificationAttributes'][domain].get('VerificationToken', '')


def check_verification_status(domain):
    """Check SES domain verification status."""
    response = ses_client.get_identity_verification_attributes(
        Identities=[domain]
    )
    verification_status = response['VerificationAttributes'].get(domain, {}).get('VerificationStatus', 'NotStarted')
    return verification_status

def is_valid_domain(domain):
    """Check if the domain has a valid format."""
    # Basic domain validation pattern
    # Checks for valid characters, proper length, and correct format
    pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    return bool(re.match(pattern, domain))

def is_valid_webhook(webhook):
    """Check if the webhook URL has a valid format."""
    pattern = r'^https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?::\d+)?(?:/[-\w%!$&\'()*+,;=:@/~]+)*(?:\?[-\w%!$&\'()*+,;=:@/~]*)?(?:#[-\w%!$&\'()*+,;=:@/~]*)?$'
    return bool(re.match(pattern, webhook))

def delete_domain(domain):
    """Delete domain from S3 and SES."""
    # Initialize clients
    s3 = boto3.client('s3')
    
    try:
        # Delete from S3
        bucket_name = os.environ.get('BUCKET_NAME', 'email-webhooks-bucket-3rfrd')
         # Delete from SES
        ses_client.delete_identity(
            Identity=domain
        )
        
        s3.delete_object(
            Bucket=bucket_name,
            Key=domain
        )
        
        return True
    except Exception as e:
        print(f"Error deleting domain {domain}: {str(e)}")
        raise e

def lambda_handler(event, context):
    try:
        # Log the incoming event for debugging
        print("Received event:",event)
        
        http_method = event['requestContext']['http']['method']
        
        # Handle DELETE request
        if http_method == 'DELETE':
            # For DELETE requests, extract domain from request body
            body = json.loads(event['body'])
            domain = body.get('domain')
            
            if not domain:
                return {
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "statusCode": 400,
                    "body": json.dumps({"error": "Domain is required"})
                }
            
            # Delete domain from S3 and SES
            delete_domain(domain)
            
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps({
                    "message": f"Domain {domain} deleted successfully",
                    "domain": domain
                })
            }
        
        # Handle GET request
        elif http_method == 'GET':
            # Extract domain from path parameters
            domain = None
            
            # Check if path parameters are present
            path_params = event.get('pathParameters', {}) or {}
            if path_params and 'domain' in path_params:
                domain = path_params.get('domain')
            
            # If no domain in path parameters, try query parameters as fallback
            if not domain:
                query_params = event.get('queryStringParameters', {}) or {}
                domain = query_params.get('domain')
            
            if not domain:
                return {
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "statusCode": 400,
                    "body": json.dumps({"error": "Domain is required in the path"})
                }
            
            # Validate domain format
            if not is_valid_domain(domain):
                return {
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "statusCode": 400,
                    "body": json.dumps({"error": "Invalid domain format"})
                }
            
            # Initialize S3 client
            s3 = boto3.client('s3')
            bucket_name = os.environ.get('BUCKET_NAME', 'email-webhooks-bucket-3rfrd')
            
            # Get domain verification status from SES
            status = check_verification_status(domain)
            
            # Get domain data from S3
            try:
                s3_response = s3.get_object(
                    Bucket=bucket_name,
                    Key=domain
                )
                s3_data = json.loads(s3_response['Body'].read().decode('utf-8'))
            except s3.exceptions.NoSuchKey:
                s3_data = {"webhook": None}
            except Exception as e:
                return {
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "statusCode": 500,
                    "body": json.dumps({"error": f"Error fetching S3 data: {str(e)}"})
                }
            
            # Get verification token
            token = ""
            try:
                response = ses_client.get_identity_verification_attributes(
                    Identities=[domain]
                )
                verification_attrs = response['VerificationAttributes'].get(domain, {})
                token = verification_attrs.get('VerificationToken', '')
            except Exception as e:
                print(f"Error fetching verification token: {str(e)}")
            
            # Prepare DNS records information
            dns_records = {
                "MX": {
                    "Type": "MX",
                    "Name": domain,
                    "Priority": 10,
                    "Value": "inbound-smtp.us-east-1.amazonaws.com"
                }
            }
            
            if token:
                dns_records["Verification"] = {
                    "Type": "TXT",
                    "Name": f"_amazonses.{domain}",
                    "Value": token
                }
            
            response_data = {
                "domain": domain,
                "webhook": s3_data.get("webhook"),
                "status": status.lower(),
                "dns_records": dns_records,
                **s3_data
            }
            
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps(response_data, indent=4)
            }
            
        # Handle PUT request
        elif http_method == 'PUT':
            # Extract domain from path parameters
            path_params = event.get('pathParameters', {}) or {}
            domain = path_params.get('domain')
            
            # Extract data from request body
            body = json.loads(event['body'])
              
            if not domain:
                return {
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "statusCode": 400,
                    "body": json.dumps({"error": "Domain is required in the path"})
                }
            
            # Initialize S3 client
            s3 = boto3.client('s3')
            bucket_name = os.environ.get('BUCKET_NAME', 'email-webhooks-bucket-3rfrd')
            
            # First, read the existing object from S3
            try:
                s3_response = s3.get_object(
                    Bucket=bucket_name,
                    Key=domain
                )
                existing_data = json.loads(s3_response['Body'].read().decode('utf-8'))
            except s3.exceptions.NoSuchKey:
                # If the domain doesn't exist in S3, return an error
                return {
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "statusCode": 404,
                    "body": json.dumps({"error": f"Domain '{domain}' not found"})
                }
               
            except Exception as e:
                return {
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "statusCode": 500,
                    "body": json.dumps({"error": f"Error fetching existing data: {str(e)}"})
                }
            
            # Update the data with new values, but don't change the domain
            for key, value in body.items():
                if key != 'domain':
                    existing_data[key] = value
            
            # Write the updated data back to S3
            try:
                s3.put_object(
                    Bucket=bucket_name,
                    Key=domain,
                    Body=json.dumps(existing_data),
                    ContentType='application/json'
                )
            except Exception as e:
                return {
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "statusCode": 500,
                    "body": json.dumps({"error": f"Error updating data: {str(e)}"})
                }
            
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps({
                    **existing_data,
                })
            }
            
        # Handle POST request (existing functionality)
        else:  # POST request
            # Parse input for the domain name
            body = json.loads(event['body'])
            user_domain = body.get('domain')
            webhook = body.get('webhook')

            # Initialize S3 client
            s3 = boto3.client('s3')

            if not user_domain:
                return {
                    "headers": {
                    "Content-Type": "application/json"
                    },
                    "statusCode": 400,
                    "body": json.dumps({"error": "Domain is required"})
                }
            
            if not webhook:
                return {
                    "headers": {
                    "Content-Type": "application/json"
                    },
                    "statusCode": 400,
                    "body": json.dumps({"error": "Webhook is required"})
                }
            
            # Validate domain format
            if not is_valid_domain(user_domain):
                return {
                    "headers": {
                    "Content-Type": "application/json"
                    },
                    "statusCode": 400,
                    "body": json.dumps({"error": "Invalid domain format"})
                }
            
            # Validate webhook format
            if not is_valid_webhook(webhook):
                return {
                    "headers": {
                    "Content-Type": "application/json"
                     },
                    "statusCode": 400,
                    "body": json.dumps({"error": "Invalid webhook URL format"})
                }
        

            # Define the bucket name and key
            bucket_name = os.environ.get('BUCKET_NAME', 'email-webhooks-bucket-3rfrd')
            key = user_domain

            # Simply update the webhook as in original code
            data = {
                "webhook": webhook
            }
            json_data = json.dumps(data)

            # Upload the JSON string to S3
            s3.put_object(
                Bucket=bucket_name,
                Key=key,
                Body=json_data,
                ContentType='application/json'
            )

            # Check the current verification status
            status = check_verification_status(user_domain)

            # Get or create SMTP credentials
            # smtp_credentials = create_smtp_user(user_domain)

            # Get verification token (will only initiate new verification if needed)
            token = verify_domain(user_domain)

            dns_records = {
                "MX": {
                    "Type": "MX",
                    "Name": user_domain,
                    "Priority": 10,
                    "Value": "inbound-smtp.us-east-1.amazonaws.com"
                },
                "Verification": {
                    "Type": "TXT",
                    "Name": f"_amazonses.{user_domain}",
                    "Value": token
                }
            }

            response_data = {
                "domain": user_domain,
                "webhook": webhook,
                "dns_records": dns_records,
                "status": status.lower(),
                "message": "DNS records verified successfully" if status == "Success" else "Verification pending"
            }

            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps(response_data, indent=4)
            }

    except Exception as e:
        return {
            "headers": {
                "Content-Type": "application/json"
            },
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }