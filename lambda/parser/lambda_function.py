# MIT License
# Copyright (c) 2023 [Your Name or Organization]
# See LICENSE file for details

import json
import boto3
import email
from email import policy
from email.parser import BytesParser
import requests  # For HTTP POST requests
import uuid
import os
import re
from datetime import datetime
import pystache  # Python implementation of Mustache.js
import ipaddress
from urllib.parse import urlparse
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# Initialize clients
s3_client = boto3.client('s3')

# MongoDB connection
mongodb_uri = os.environ.get('MONGODB_URI', '')
environment = os.environ.get('ENVIRONMENT', 'main')
mongo_client = None
db = None

if mongodb_uri:
    try:
        mongo_client = MongoClient(mongodb_uri)
        # Use environment-specific database name
        db_name = f"email_webhooks_{environment.replace('/', '_')}"  # Replace / in branch names
        db = mongo_client[db_name]
        print(f"MongoDB connection initialized successfully, using database: {db.name}")
    except Exception as e:
        print(f"Failed to initialize MongoDB connection: {e}")

attachments_bucket_name = os.environ.get('ATTACHMENTS_BUCKET_NAME', 'email-attachments-bucket-3rfrd')


def validate_webhook_url(url):
    """
    Strictly validate the webhook URL to prevent SSRF attacks.
    - Only allow http(s) schemes.
    - Block localhost and private/internal IPs.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.hostname
        if not host:
            return False
        # Block localhost
        if host in ("localhost", "127.0.0.1", "0.0.0.0"):
            return False
        # Block internal IPs
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        except ValueError:
            # Not an IP, might be a domain
            pass
        # Optionally, enforce HTTPS only:
        # if parsed.scheme != "https":
        #     return False
        return True
    except Exception:
        return False


def process_template(template, data):
    """
    Process a mustache-style template string using pystache (Mustache.js for Python).
    
    Args:
        template (str): Template string with {{variable}} placeholders
        data (dict): Dictionary containing values to replace placeholders
        
    Returns:
        str: Processed string with variables replaced by their values
    """
    if not template or "{{" not in template:
        return template
    
    return pystache.render(template, data)

def save_email_to_mongodb(email_data, webhook_url=None, webhook_response=None, webhook_status_code=None):
    """
    Save parsed email to MongoDB database if MONGODB_URI environment variable exists
    
    Args:
        email_data (dict): Dictionary containing:
            - domain: The domain part of the recipient address
            - local_part: The local part of the recipient address
            - email_id: Full email address identifier
            - attachments: Array of attachment metadata
            - All other parsed email fields
        webhook_url (str, optional): The webhook URL to send the email data to
        webhook_response (str, optional): The response from the webhook
        webhook_status_code (int, optional): The status code from the webhook
    """
    if db is None or not mongodb_uri:
        print("MongoDB connection not available, skipping database save")
        return
    
    try:
        # Prepare document for MongoDB
        email_document = {
            "_id": f"email_{str(uuid.uuid4())}",
            "email_id": email_data['email_id'],
            "domain": email_data['domain'],
            "local_part": email_data['local_part'],
            "sender": email_data.get('sender'),
            "recipient": email_data.get('recipient'),
            "subject": email_data.get('subject'),
            "date": email_data.get('date'),
            "message_id": email_data.get('message_id'),
            "cc": email_data.get('cc'),
            "bcc": email_data.get('bcc'),
            "reply_to": email_data.get('reply_to'),
            "references": email_data.get('references'),
            "in_reply_to": email_data.get('in_reply_to'),
            "importance": email_data.get('importance'),
            "custom_headers": email_data.get('custom_headers', {}),
            "body": email_data.get('body'),
            "html_body": email_data.get('html_body'),
            "attachments": email_data.get('attachments', []),
            "email_data": email_data,  # Store complete email data
            "is_webhook_sent": True,
            "webhook_url": webhook_url,
            "webhook_response": webhook_response,
            "webhook_status_code": webhook_status_code,
            "created_at": datetime.utcnow()
        }
        
        # Insert into parsed_emails collection
        collection = db['parsed_emails']
        result = collection.insert_one(email_document)
        
        print(f"Email {email_data['email_id']} saved to MongoDB successfully with ID: {result.inserted_id}")
        
    except PyMongoError as e:
        print(f"Failed to save email to MongoDB: {e}")
    except Exception as e:
        print(f"Unexpected error saving email to MongoDB: {e}")

def lambda_handler(event, context):
    # Parse the S3 event
    for record in event['Records']:
        email_bucket_name = record['s3']['bucket']['name']
        email_object_key = record['s3']['object']['key']

        # Get the email object from S3
        response = s3_client.get_object(Bucket=email_bucket_name, Key=email_object_key)
        raw_email = response['Body'].read()

        print(f"Received email from {email_bucket_name}/{email_object_key}")
        print(f"Email content: {raw_email}")
        # Parse the email
        msg = BytesParser(policy=policy.default).parsebytes(raw_email)
       
        # Extract email headers first
        sender = msg.get('From', '')
        recipient = msg.get('To', '')
        
        # Retrieve webhook URL for the domain from the S3 bucket
        # Extract domain from recipient email using regex
        pattern = r"by ([\w\.-]+) with SMTP id ([\w\d]+).*?for ([\w@\.-]+);"
        received_header = msg.get('Received', '')
        match = re.search(pattern, received_header, re.DOTALL) if received_header else None
        kv_key = match.group(3).split('@')[1] if match else (recipient.split('@')[-1].strip('>') if recipient else '')
     
        received_from = match.group(3) if match else None
        subject = msg.get('Subject', '')
        date = msg.get('Date', '')  # Extract email date/timestamp
        message_id = msg.get('Message-ID', '')  # Extract unique message ID
        cc = msg.get('Cc', '')  # Extract CC recipients
        bcc = msg.get('Bcc', '')  # Extract BCC recipients
        reply_to = msg.get('Reply-To', '')  # Extract Reply-To header
        references = msg.get('References', '')  # Extract message references
        in_reply_to = msg.get('In-Reply-To', '')  # Extract In-Reply-To header
        importance = msg.get('Importance', '')  # Extract importance/priority
        
        # Extract custom headers if needed
        custom_headers = {}
        for header in msg.keys():
            if header.lower().startswith('x-'):  # Most custom headers start with X-
                custom_headers[header] = msg[header]
                
        body = ""
        html_body = ""  # Store HTML version separately
        attachments = []

        print(f"Sender: {sender}")
        print(f"Recipient: {recipient}")
       
        print(f"Webhook key: {kv_key}")
        
        # Retrieve webhook URL from MongoDB
        webhook_url = None
        try:
            if db is not None and mongodb_uri:
                # Query MongoDB for domain configuration
                domain_configs = db['domain_configs']
                domain_config = domain_configs.find_one({"domain": kv_key})
                
                if domain_config and 'webhook' in domain_config:
                    webhook_url = domain_config['webhook']
                    # SECURITY: Validate webhook URL strictly
                    if not validate_webhook_url(webhook_url):
                        print(f"Blocked unsafe webhook URL: {webhook_url}")
                        return {
                            'statusCode': 400,
                            'body': "Invalid or unsafe webhook URL."
                        }
                else:
                    print(f"No webhook configuration found for domain {kv_key}")
                    return {
                        'statusCode': 404,
                        'body': f"Webhook configuration for domain {kv_key} not found."
                    }
            else:
                print("MongoDB connection not available")
                return {
                    'statusCode': 500,
                    'body': "Database connection not available."
                }
        except PyMongoError as e:
            print(f"MongoDB error retrieving webhook for domain {kv_key}: {e}")
            return {
                'statusCode': 500,
                'body': "Error retrieving webhook configuration."
            }
        except Exception as e:
            print(f"Error retrieving webhook for domain {kv_key}: {e}")
            return {
                'statusCode': 500,
                'body': "Webhook for domain not found or error occurred."
            }

        # Extract email body and attachments
        if msg.is_multipart():
            for part in msg.iter_parts():
                content_type = part.get_content_type()
                content_disposition = str(part.get_content_disposition() or "").lower()
                is_inline = "inline" in content_disposition or part.get("Content-ID")

                # Process text/plain body parts
                if content_type == "text/plain" and not is_inline and "attachment" not in content_disposition:
                    body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
                
                # Process text/html body parts
                elif content_type == "text/html" and not is_inline and "attachment" not in content_disposition:
                    html_body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
                    if not body:  # Use HTML as fallback if plain text is unavailable
                        body = html_body
                
                # Process attachments and inline content in a single block
                elif "attachment" in content_disposition or is_inline:
                    attachment_data = part.get_payload(decode=True)
                    attachment_name = part.get_filename()
                    content_id = part.get("Content-ID", "").strip('<>')

                    if is_inline and not attachment_name:
                        attachment_name = f"inline_{content_id or uuid.uuid4().hex}.png"

                    attachment_key = f"{uuid.uuid4().hex}/{attachment_name}"
                    s3_client.put_object(
                        Bucket=attachments_bucket_name,
                        Key=attachment_key,
                        Body=attachment_data,
                        ContentType=content_type
                    )

                    s3_url = f"https://{attachments_bucket_name}.s3.amazonaws.com/{attachment_key}"
                    print(f"Processed {'inline' if is_inline else 'attachment'}: {attachment_name}, URL: {s3_url}")

                    attachments.append({
                        "filename": attachment_name,
                        "public_url": s3_url,
                        "content_type": content_type,
                        "inline": is_inline,
                        "content_id": content_id if is_inline else None
                    })

            # Replace cid: references in the HTML body with the public URLs after processing all parts
            if html_body:
                for attachment in attachments:
                    if attachment.get("inline") and attachment.get("content_id"):
                        html_body = html_body.replace(f"cid:{attachment['content_id']}", attachment['public_url'])
        else:
            content_type = msg.get_content_type()
            if content_type == "text/html":
                html_body = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8")
                body = html_body  # Use HTML as body if that's all we have
            else:
                body = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8")

        # Construct payload
        parsed_email = {
            "email_id": email_object_key,
            "domain": received_from.split('@')[1],
            "local_part": received_from.split('@')[0],
            "sender": sender,
            "recipient": recipient,
            "subject": subject,
            "date": date,
            "message_id": message_id,
            "cc": cc,
            "bcc": bcc,
            "reply_to": reply_to,
            "references": references,
            "in_reply_to": in_reply_to,
            "importance": importance,
            "custom_headers": custom_headers,
            "body": body,
            "html_body": html_body if html_body else None,  # Include HTML body if available
            "attachments": attachments
        }

        # Process webhook URL templates before sending
        webhook_url = process_template(webhook_url, parsed_email)

        # SECURITY: Outbound webhook call with strict timeout and no redirects
        try:
            response = requests.post(
                webhook_url,
                json=parsed_email,
                timeout=5,  # tighter timeout
                allow_redirects=False  # do not follow redirects
            )
            response.raise_for_status()
            print(f"Data sent to webhook {webhook_url} successfully.")
            # Call the updated function with successful webhook details
            save_email_to_mongodb(
                parsed_email,
                webhook_url=webhook_url,
                webhook_response=response.text,
                webhook_status_code=response.status_code
            )
        except Exception as e:
            # SECURITY: Log error internally, but do not leak details to response
            print(f"Error sending data to webhook {webhook_url}: {repr(e)}")
            save_email_to_mongodb(
                parsed_email,
                webhook_url=webhook_url,
                webhook_response="Webhook error",
                webhook_status_code=getattr(e, 'response', None).status_code if hasattr(e, 'response') and e.response else 0
            )
            # Continue processing, but do not expose details
            print("Continuing despite webhook error.")

    # Always return generic success, regardless of webhook outcome
    return {
        'statusCode': 200,
        'body': "Email processed successfully."
    }
