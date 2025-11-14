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
from pymongo import MongoClient
from pymongo.errors import PyMongoError, DuplicateKeyError

ses_client = boto3.client('ses')
iam_client = boto3.client('iam')

# MongoDB connection
mongodb_uri = os.environ.get('MONGODB_URI', '')
environment = os.environ.get('ENVIRONMENT', 'main')
s3_bucket = os.environ.get('EMAIL_BUCKET', '')
mongo_client = None
db = None
receipt_rule_set = os.environ.get('RECEIPT_RULE_SET', 'default-rule-set')

if mongodb_uri:
    try:
        mongo_client = MongoClient(mongodb_uri)
        # Use environment-specific database name
        db_name = f"email_webhooks_{environment.replace('/', '_')}"  # Replace / in branch names
        db = mongo_client[db_name]
        # Create unique index on domain field
        db['domain_configs'].create_index("domain", unique=True)
        print(f"MongoDB connection initialized successfully, using database: {db.name}")
    except Exception as e:
        print(f"Failed to initialize MongoDB connection: {e}")


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
    """Delete domain from MongoDB and SES."""
    try:
        # Try to delete from SES
        try:
            ses_client.delete_identity(
                Identity=domain
            )
        except Exception as ses_error:
            print(f"Error deleting domain from SES {domain}: {str(ses_error)}")
            # Continue with MongoDB deletion even if SES delete fails

        # Delete from MongoDB
        if db is not None and mongodb_uri:
            try:
                domain_configs = db['domain_configs']
                result = domain_configs.delete_one({"domain": domain})
                if result.deleted_count == 0:
                    print(f"Domain {domain} not found in MongoDB")
                else:
                    print(f"Domain {domain} deleted from MongoDB successfully")
                        
            except PyMongoError as mongo_error:
                print(f"Error deleting domain from MongoDB {domain}: {str(mongo_error)}")
                raise mongo_error
        else:
            print("MongoDB connection not available")
            raise Exception("Database connection not available")
        
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

def format_dns_records(domain, token, dkim_tokens, public_key=None, return_all=True):
    """Format DNS records in a structured way."""
    records = {}
    
    # MX record
    records["MX"] = {
        "Type": "MX",
        "Name": domain,
        "Priority": 10,
        "Value": "inbound-smtp.us-east-1.amazonaws.com"
    }
    # Verification record
    if token:
        records["Verification"] = {
            "Type": "TXT",
            "Name": f"_amazonses.{domain}",
            "Priority": 0,
            "Value": token
        }

    # If return_all is False, only return the required records
    if not return_all:
        return records
    
     # SPF record
    records["SPF"] = {
        "Type": "TXT",
        "Name": domain,
        "Priority": 0,
        "Value": "v=spf1 include:amazonses.com -all"
    }

    # DMARC record
    records["DMARC"] = {
        "Type": "TXT",
        "Name": f"_dmarc.{domain}",
        "Priority": 0,
        "Value": f"v=DMARC1; p=quarantine; rua=mailto:dmarc-reports@{domain}"
    }

    # DKIM records
    for i, dkim_token in enumerate(dkim_tokens):
        records[f"DKIM_{i+1}"] = {
            "Type": "CNAME",
            "Name": f"{dkim_token}._domainkey.{domain}",
            "Priority": 0,
            "Value": f"{dkim_token}.dkim.amazonses.com"
        }

    # Custom DKIM if provided
    if public_key:
        records["CustomDKIM"] = {
            "Type": "TXT",
            "Name": f"resend._domainkey.{domain}",
            "Priority": 0,
            "Value": public_key
        }

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
            
            # Check MongoDB connection
            if db is None or not mongodb_uri:
                return {
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "statusCode": 500,
                    "body": json.dumps({"error": "Database connection not available"})
                }
            
            # Get domain data from MongoDB 
            try:
                domain_configs = db['domain_configs']
                mongo_data = domain_configs.find_one({"domain": domain})
                
                if not mongo_data:
                    return {
                        "headers": {
                            "Content-Type": "application/json"
                        },
                        "statusCode": 404,
                        "body": json.dumps({"error": f"Domain {domain} not found"})
                    }
                
                # Remove MongoDB _id field and convert datetime objects to strings
                if '_id' in mongo_data:
                    del mongo_data['_id']
                
                # Convert datetime objects to ISO format strings
                for key, value in mongo_data.items():
                    if isinstance(value, datetime.datetime):
                        mongo_data[key] = value.isoformat()
                    
            except PyMongoError as e:
                return {
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "statusCode": 500,
                    "body": json.dumps({"error": f"Error fetching MongoDB data: {str(e)}"})
                }
            except Exception as e:
                return {
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "statusCode": 500,
                    "body": json.dumps({"error": f"Error fetching data: {str(e)}"})
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
                    
                    # Update verification status in MongoDB
                    try:
                        domain_configs.update_one(
                            {"domain": domain},
                            {
                                "$set": {
                                    "verification_status": status,
                                    "verification_status_last_checked": datetime.datetime.utcnow()
                                }
                            }
                        )
                        print(f"Updated verification status for {domain}: {status}")
                    except PyMongoError as e:
                        print(f"Error updating verification status in MongoDB: {str(e)}")
                        # Continue even if MongoDB update fails
                        
                except Exception as e:
                    print(f"Error fetching SES data: {str(e)}")
            
            # Get DKIM tokens
            dkim_tokens = []
            if not ignoreSesData:
                dkim_tokens = get_dkim_tokens(domain)
            
            # Prepare DNS records information
            dns_records = format_dns_records(domain, token, dkim_tokens)
            
            # Include status in response only if SES data was queried
            response_data = {**mongo_data}
            
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
            
            # Check MongoDB connection
            if db is None or not mongodb_uri:
                return {
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "statusCode": 500,
                    "body": json.dumps({"error": "Database connection not available"})
                }
            
            # Update the domain configuration in MongoDB
            try:
                domain_configs = db['domain_configs']
                
                # Prepare update data (exclude domain field)
                update_data = {k: v for k, v in body.items() if k != 'domain'}
                update_data['updated_at'] = datetime.datetime.utcnow()
                
                # Update the document
                result = domain_configs.update_one(
                    {"domain": domain},
                    {"$set": update_data}
                )
                
                if result.matched_count == 0:
                    return {
                        "headers": {
                            "Content-Type": "application/json"
                        },
                        "statusCode": 404,
                        "body": json.dumps({"error": f"Domain '{domain}' not found"})
                    }
                
                # Fetch the updated document
                updated_data = domain_configs.find_one({"domain": domain})
                if '_id' in updated_data:
                    del updated_data['_id']
                
                # Convert datetime objects to ISO format strings
                for key, value in updated_data.items():
                    if isinstance(value, datetime.datetime):
                        updated_data[key] = value.isoformat()
                    
            except PyMongoError as e:
                return {
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "statusCode": 500,
                    "body": json.dumps({"error": f"Error updating data: {str(e)}"})
                }
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
                "body": json.dumps(updated_data)
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
            
            # Check MongoDB connection
            if db is None or not mongodb_uri:
                return {
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "statusCode": 500,
                    "body": json.dumps({"error": "Database connection not available"})
                }
            
            # Insert domain configuration into MongoDB
            try:
                domain_configs = db['domain_configs']
                
                # Prepare domain configuration document
                domain_config = {
                    "domain": user_domain,
                    "webhook": webhook,
                    "created_at": datetime.datetime.utcnow(),
                    "updated_at": datetime.datetime.utcnow()
                }
                
                # Try to insert, check for duplicate
                try:
                    domain_configs.insert_one(domain_config)
                        
                except DuplicateKeyError:
                    return {
                        "statusCode": 200,
                        "headers": {
                            "Content-Type": "application/json"
                        },
                        "body": json.dumps({"message": "Domain already exists"})
                    }
            except PyMongoError as e:
                return {
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "statusCode": 500,
                    "body": json.dumps({"error": f"Error saving domain configuration: {str(e)}"})
                }

            # Check the current verification status
            status = check_verification_status(user_domain)

            # Update verification status in MongoDB
            try:
                domain_configs.update_one(
                    {"domain": user_domain},
                    {
                        "$set": {
                            "verification_status": status,
                            "verification_status_last_checked": datetime.datetime.utcnow()
                        }
                    }
                )
                print(f"Saved initial verification status for {user_domain}: {status}")
            except PyMongoError as e:
                print(f"Error saving verification status to MongoDB: {str(e)}")
                # Continue even if MongoDB update fails

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
                "dns_records": records,
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