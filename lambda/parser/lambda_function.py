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
try:
    from ai_parser import AIParser
except ImportError:
    print("Could not import AIParser. AI features disabled.")
    AIParser = None

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

def extract_email_body(msg):
    """
    Recursively extract body content from an email message.
    Handles nested multipart structures and prefers the most complete parts.

    Returns:
        tuple: (body_text, html_body)
    """
    plain_candidates = []
    html_candidates = []

    def walk(part):
        try:
            if part.is_multipart():
                for sub in part.iter_parts():
                    walk(sub)
                return

            content_type = part.get_content_type()
            content_disposition = str(part.get_content_disposition() or "").lower()

            # Skip attachments
            if "attachment" in content_disposition:
                return

            payload = part.get_payload(decode=True)
            if not payload:
                return

            charset = part.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace").strip()

            if content_type == "text/plain":
                plain_candidates.append(text)
                print(f"Found text/plain candidate: {len(text)} chars")
            elif content_type == "text/html":
                html_candidates.append(text)
                print(f"Found text/html candidate: {len(text)} chars")
        except Exception as e:
            print(f"Error walking part: {e}")

    walk(msg)

    body_text = ""
    html_body = None

    if plain_candidates:
        # Choose the longest non-empty plain text candidate
        body_text = max(plain_candidates, key=len)
    if html_candidates:
        # Choose the longest non-empty html candidate
        html_body = max(html_candidates, key=len)

    # Use HTML as fallback if no plain text
    if not body_text and html_body:
        body_text = html_body

    return body_text, html_body

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
        html_body = None  # Store HTML version separately
        attachments = []

        print(f"Sender: {sender}")
        print(f"Recipient: {recipient}")
        print(f"Subject: {subject}")
        print(f"Webhook key: {kv_key}")
        print(f"Email is multipart: {msg.is_multipart()}")
        print(f"Email content type: {msg.get_content_type()}")
        
        # Debug: Print all parts structure for multipart emails
        if msg.is_multipart():
            print("=== Email Parts Structure ===")
            for i, part in enumerate(msg.iter_parts()):
                print(f"Part {i}:")
                print(f"  Content-Type: {part.get_content_type()}")
                print(f"  Content-Disposition: {part.get_content_disposition()}")
                print(f"  Has Content-ID: {part.get('Content-ID') is not None}")
                print(f"  Has filename: {part.get_filename()}")
                payload = part.get_payload(decode=True)
                print(f"  Payload length: {len(payload) if payload else 0} bytes")
        else:
            payload = msg.get_payload(decode=True)
            print(f"Non-multipart payload length: {len(payload) if payload else 0} bytes")
        
        # Retrieve webhook URL from MongoDB
        webhook_url = None
        ai_prompt = None
        try:
            if db is not None and mongodb_uri:
                # Query MongoDB for domain configuration
                domain_configs = db['domain_configs']
                domain_config = domain_configs.find_one({"domain": kv_key})
                
                if domain_config and 'webhook' in domain_config:
                    webhook_url = domain_config['webhook']
                    ai_prompt = domain_config.get('ai_analysis')
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

        # Extract email body using dedicated function
        print("=== Extracting Email Body ===")
        body, html_body = extract_email_body(msg)
        print(f"After extraction - body: '{body[:100]}...' (length: {len(body)})")
        print(f"After extraction - html_body: {html_body[:100] if html_body else 'None'}... (length: {len(html_body) if html_body else 0})")
        
        # Extract attachments
        print("=== Extracting Attachments ===")
        if msg.is_multipart():
            for part in msg.iter_parts():
                content_type = part.get_content_type()
                content_disposition = str(part.get_content_disposition() or "").lower()
                
                # Check if this is truly an inline image/attachment
                has_content_id = part.get("Content-ID") is not None
                is_inline_image = has_content_id and content_type not in ("text/plain", "text/html")
                is_attachment = "attachment" in content_disposition
                has_filename = part.get_filename() is not None
                
                # Skip text parts (already processed for body)
                if content_type in ("text/plain", "text/html") and not is_attachment:
                    continue

                # Process attachments and inline images
                if is_attachment or is_inline_image or has_filename:
                    try:
                        attachment_data = part.get_payload(decode=True)
                        if not attachment_data:
                            continue
                            
                        attachment_name = part.get_filename()
                        content_id = part.get("Content-ID", "").strip('<>')

                        if is_inline_image and not attachment_name:
                            # Generate a name for inline images without filenames
                            extension = content_type.split('/')[-1] if '/' in content_type else 'bin'
                            attachment_name = f"inline_{content_id or uuid.uuid4().hex}.{extension}"

                        if not attachment_name:
                            attachment_name = f"attachment_{uuid.uuid4().hex}.bin"

                        attachment_key = f"{uuid.uuid4().hex}/{attachment_name}"
                        s3_client.put_object(
                            Bucket=attachments_bucket_name,
                            Key=attachment_key,
                            Body=attachment_data,
                            ContentType=content_type
                        )

                        s3_url = f"https://{attachments_bucket_name}.s3.amazonaws.com/{attachment_key}"
                        print(f"Processed {'inline image' if is_inline_image else 'attachment'}: {attachment_name}, URL: {s3_url}")

                        attachments.append({
                            "filename": attachment_name,
                            "public_url": s3_url,
                            "content_type": content_type,
                            "inline": is_inline_image,
                            "content_id": content_id if is_inline_image else None
                        })
                    except Exception as e:
                        print(f"Error processing attachment: {e}")

            # Replace cid: references in the HTML body with the public URLs
            if html_body:
                for attachment in attachments:
                    if attachment.get("inline") and attachment.get("content_id"):
                        html_body = html_body.replace(f"cid:{attachment['content_id']}", attachment['public_url'])

        # Log final body extraction results
        print(f"Final body length: {len(body)} characters")
        print(f"Final html_body length: {len(html_body) if html_body else 0} characters")
        print(f"Number of attachments: {len(attachments)}")

        # Construct payload
        print("=== Constructing Payload ===")
        # Determine local_part and domain robustly
        domain_part = None
        local_part = None
        try:
            if received_from and '@' in received_from:
                local_part, domain_part = received_from.split('@', 1)
            else:
                from email.utils import getaddresses
                addresses = getaddresses([recipient]) if recipient else []
                email_addr = addresses[0][1] if addresses else ''
                if email_addr and '@' in email_addr:
                    local_part, domain_part = email_addr.split('@', 1)
                else:
                    # Fallbacks
                    domain_part = kv_key or ''
                    local_part = ''
        except Exception as e:
            print(f"Error determining local/domain parts: {e}")
            domain_part = kv_key or ''
            local_part = ''

        parsed_email = {
            "email_id": email_object_key,
            "domain": domain_part,
            "local_part": local_part,
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
            "html_body": html_body,  # Include HTML body if available (already None if empty)
            "attachments": attachments
        }

        # Integrate AI Parser
        if AIParser and ai_prompt:
            try:
                print("=== Starting AI Parsing ===")
                ai_parser = AIParser()
                ai_result = ai_parser.parse_email(parsed_email, prompt=ai_prompt)
                parsed_email['ai_analysis'] = ai_result
                print("AI Parsing completed.")
            except Exception as e:
                print(f"Error during AI parsing integration: {e}")
                parsed_email['ai_analysis'] = {"error": str(e)}
        elif not ai_prompt:
            print("Skipping AI parsing: No 'ai_analysis' prompt found in domain config.")
        else:
            print("Skipping AI parsing: AIParser not available.")

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
