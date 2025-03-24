# MIT License
# Copyright (c) 2023 [Your Name or Organization]
# See LICENSE file for details

import requests
import boto3
import json
import secrets
import string
import re
import os
import uuid
import datetime

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
        bucket_name = os.environ.get('DATABASE_BUCKET_NAME', 'email-webhooks-bucket-3rfrd')
        
        # Try to delete from SES
        try:
            ses_client.delete_identity(
                Identity=domain
            )
        except Exception as ses_error:
            print(f"Error deleting domain from SES {domain}: {str(ses_error)}")
            # Continue with S3 deletion even if SES delete fails

        # Delete from Deno
        try:
            response = requests.delete(os.environ.get('FUNCTION_API_URL') + f"{domain}")
            print(response.json())
        except Exception as e:
            print(f"Error deleting domain from Deno {domain}: {str(e)}")

        # Delete from S3
        try:
            s3.delete_object(
                Bucket=bucket_name,
                Key=domain
            )
        except Exception as s3_error:
            print(f"Error deleting domain from S3 {domain}: {str(s3_error)}")
            # Continue even if S3 delete fails
        
        return True
    except Exception as e:
        print(f"Error in delete_domain operation for {domain}: {str(e)}")
        raise e

def get_dkim_tokens(domain):
    """Get DKIM tokens for the domain from SES."""
    try:
        # First verify DKIM for the domain
        ses_client.verify_domain_dkim(Domain=domain)
        
        # Then get the DKIM tokens
        response = ses_client.get_identity_dkim_attributes(
            Identities=[domain]
        )
        if domain in response['DkimAttributes']:
            return response['DkimAttributes'][domain]['DkimTokens']
    except Exception as e:
        print(f"Error getting DKIM tokens: {str(e)}")
    return []

def get_public_key(domain):
    """Get or generate public key for the domain."""
    try:
        response = ses_client.get_identity_mail_from_domain_attributes(
            Identities=[domain]
        )
        # For now return empty as we'll use custom key if provided
        return ""
    except Exception as e:
        print(f"Error getting public key: {str(e)}")
        return ""

def format_dns_records(domain, token, dkim_tokens, public_key=None):
    """Format DNS records in a structured way."""
    records = []
    
    # MX record
    records.append({
        "Type": "MX",
        "Name": domain,
        "Priority": 10,
        "Value": "inbound-smtp.us-east-1.amazonaws.com"
    })
    
    # SPF record
    records.append({
        "Type": "TXT",
        "Name": domain,
        "Priority": 0,
        "Value": "v=spf1 include:amazonses.com -all"
    })

    # DMARC record
    records.append({
        "Type": "TXT",
        "Name": f"_dmarc.{domain}",
        "Priority": 0,
        "Value": f"v=DMARC1; p=quarantine; rua=mailto:dmarc-reports@{domain}"
    })

    # Verification record
    if token:
        records.append({
            "Type": "TXT",
            "Name": f"_amazonses.{domain}",
            "Priority": 0,
            "Value": token
        })

    # DKIM records
    for dkim_token in dkim_tokens:
        records.append({
            "Type": "CNAME",
            "Name": f"{dkim_token}._domainkey.{domain}",
            "Priority": 0,
            "Value": f"{dkim_token}.dkim.amazonses.com"
        })

    # Custom DKIM if provided
    if public_key:
        records.append({
            "Type": "TXT",
            "Name": f"resend._domainkey.{domain}",
            "Priority": 0,
            "Value": public_key
        })

    return records

def lambda_handler(event, context):
    try:
        # Log the incoming event for debugging
        print("Received event:",event)
        
        http_method = event['requestContext']['http']['method']
        
        # Handle DELETE request
        if http_method == 'DELETE':
            # Extract domain from path parameters
            path_params = event.get('pathParameters', {}) or {}
            domain = path_params.get('domain')
            
            # If no domain in path, try to get it from body as fallback
            if not domain:
                body = json.loads(event.get('body') or '{}')
                domain = body.get('domain')
            
            if not domain:
                return {
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "statusCode": 400,
                    "body": json.dumps({"error": "Domain is required in the path"})
                }
            
            # Delete domain from S3 and SES
            delete_domain(domain)
            
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps({
                    "message": f"Domain {domain} deleted successfully"
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
            
            # Initialize S3 client
            s3 = boto3.client('s3')
            bucket_name = os.environ.get('DATABASE_BUCKET_NAME', 'email-webhooks-bucket-3rfrd')
            
            # Get domain data from S3
            try:
                s3_response = s3.get_object(
                    Bucket=bucket_name,
                    Key=domain
                )
                s3_data = json.loads(s3_response['Body'].read().decode('utf-8'))
            except s3.exceptions.NoSuchKey:
                return {
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "statusCode": 404,
                    "body": json.dumps({"error": f"Domain {domain} not found"})
                }
            except Exception as e:
                return {
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "statusCode": 500,
                    "body": json.dumps({"error": f"Error fetching S3 data: {str(e)}"})
                }
            
            # Get domain verification status from SES
            status = "unknown"
            token = ""
            
            # Check if we should ignore SES data
            query_params = event.get('queryStringParameters', {}) or {}
            ignoreSesData = query_params.get('ignoreSesData') == "true"
            
            if not ignoreSesData:
                try:
                    status = check_verification_status(domain)
                    
                    # Get verification token
                    response = ses_client.get_identity_verification_attributes(
                        Identities=[domain]
                    )
                    verification_attrs = response['VerificationAttributes'].get(domain, {})
                    token = verification_attrs.get('VerificationToken', '')
                except Exception as e:
                    print(f"Error fetching SES data: {str(e)}")
            
            # Prepare DNS records information
            dns_records = {
                "MX": {
                    "Type": "MX",
                    "Name": domain,
                    "Priority": 10,
                    "Value": "inbound-smtp.us-east-1.amazonaws.com"
                },
                "SPF": {
                    "Type": "TXT",
                    "Name": domain,
                    "Priority": 0,
                    "Value": "v=spf1 include:amazonses.com ~all"
                },
                "DMARC": {
                    "Type": "TXT",
                    "Name": f"_dmarc.{domain}",
                    "Priority": 0,
                    "Value": f"v=DMARC1; p=none; rua=mailto:dmarc-reports@{domain}"
                }
            }
            
            # Add public key if provided in the request
            body = json.loads(event['body']) if event['body'] else {}
            public_key = body.get('public_key') if body and isinstance(body, dict) else None
            if public_key:
                dns_records["PublicKey"] = {
                    "Type": "TXT",
                    "Name": domain,
                    "Priority": 0,
                    "Value": public_key
                }
            
            if token:
                dns_records["Verification"] = {
                    "Type": "TXT",
                    "Name": f"_amazonses.{domain}",
                    "Priority": 0,
                    "Value": token
                }
            
            # Add DKIM records
            dkim_tokens = get_dkim_tokens(domain)
            for i, dkim_token in enumerate(dkim_tokens):
                dns_records[f"DKIM_{i+1}"] = {
                    "Type": "CNAME",
                    "Name": f"{dkim_token}._domainkey.{domain}",
                    "Priority": 0,
                    "Value": f"{dkim_token}.dkim.amazonses.com"
                }
            
            # Include status in response only if SES data was queried
            response_data = {**s3_data}
            
            if not ignoreSesData:
                response_data["status"] = status.lower()
                response_data["dns_records"] = dns_records
            
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
            bucket_name = os.environ.get('DATABASE_BUCKET_NAME', 'email-webhooks-bucket-3rfrd')
            
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
            # Extract domain from path parameters
            path_params = event.get('pathParameters', {}) or {}
            user_domain = path_params.get('domain')
            
            # Parse input from the request body
            body = json.loads(event['body'])
            
            # If no domain in path, try to get it from body as fallback
            if not user_domain and 'domain' in body:
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
                    "body": json.dumps({"error": "Domain is required in the path"})
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
            bucket_name = os.environ.get('DATABASE_BUCKET_NAME', 'email-webhooks-bucket-3rfrd')
            key = user_domain

    
            # Check if key exists, exit if it does
            try:
                s3.get_object(Bucket=bucket_name, Key=key)
                return {
                    "statusCode": 200,
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "body": json.dumps({"message": "Domain already exists"})
                }
            except s3.exceptions.NoSuchKey as e:
                pass
            
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
            
            # Get DKIM tokens
            dkim_tokens = get_dkim_tokens(user_domain)
            
            # Get public key if provided
            public_key = body.get('public_key') if isinstance(body, dict) else None
            
            # Format DNS records
            records = format_dns_records(user_domain, token, dkim_tokens, public_key)
   
            response_data = {
                "object": "domain",
                "id": str(uuid.uuid4()),  # Generate a unique ID
                "name": user_domain,
                "status": status.lower(),
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "region": "us-east-1",
                "records": records,
                "webhook": webhook
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