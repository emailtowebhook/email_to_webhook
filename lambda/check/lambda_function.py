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

def lambda_handler(event, context):
    try:
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