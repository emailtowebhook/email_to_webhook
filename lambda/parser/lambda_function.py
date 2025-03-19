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
# Initialize clients
s3_client = boto3.client('s3')

attachments_bucket_name = os.environ.get('ATTACHMENTS_BUCKET_NAME', 'email-attachments-bucket-3rfrd')
kv_database_bucket_name = os.environ.get('database_bucket_name', 'email-webhooks-bucket-3rfrd')

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
       
        # Retrieve webhook URL for the domain from the S3 bucket
        # Extract domain from recipient email using regex
        pattern = r"by ([\w\.-]+) with SMTP id ([\w\d]+).*?for ([\w@\.-]+);"
        match = re.search(pattern, msg['Received'], re.DOTALL)
        kv_key = match.group(3).split('@')[1] if match else recipient.split('@')[-1].strip('>')
     
        received_from = match.group(3) if match else None
        sender = msg['From']
        recipient = msg['To']
        subject = msg['Subject']
        date = msg['Date']  # Extract email date/timestamp
        message_id = msg['Message-ID']  # Extract unique message ID
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
        try:
            kv_response = s3_client.get_object(Bucket=kv_database_bucket_name, Key=kv_key)
            kv_data = json.loads(kv_response['Body'].read())
            webhook_url = kv_data['webhook']
        except Exception as e:
            print(f"Error retrieving webhook for domain {kv_key}: {e}")
            return {
                'statusCode': 500,
                'body': f"Webhook for domain {kv_key} not found or error occurred."
            }

        # Extract email body and attachments
        if msg.is_multipart():
            for part in msg.iter_parts():
                content_type = part.get_content_type()
                content_disposition = str(part.get_content_disposition() or "").lower()

                # Process text/plain body parts
                if content_type == "text/plain" and "attachment" not in content_disposition and "inline" not in content_disposition:
                    body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
                
                # Process text/html body parts
                elif content_type == "text/html" and "attachment" not in content_disposition and "inline" not in content_disposition:
                    html_body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
                    if not body:  # Use HTML as fallback if plain text is unavailable
                        body = html_body
                
                # Process attachments
                elif content_disposition and "attachment" in content_disposition:
                    # Process attachments (existing code)
                    attachment_data = part.get_payload(decode=True)
                    attachment_name = part.get_filename()

                    attachment_key= f"{uuid.uuid4().hex}/{attachment_name}"
                    s3_client.put_object(
                        Bucket=attachments_bucket_name,
                        Key=attachment_key,
                        Body=attachment_data
                    )
                    # Get regular S3 URL for the attachment
                    s3_url = f"https://{attachments_bucket_name}.s3.amazonaws.com/{attachment_key}"
                    print(f"S3 URL for attachment: {s3_url}")

                    attachments.append({
                        "filename": attachment_name,
                        "public_url": s3_url,
                        "content_type": content_type
                    })
                
                # Process inline images - separate condition to ensure both are processed
                if part.get("Content-ID") or ("inline" in content_disposition):
                    content_id = part.get("Content-ID", "").strip('<>') or f"inline_{uuid.uuid4().hex}"
                    inline_image_data = part.get_payload(decode=True)
                    inline_image_name = part.get_filename() or f"inline_{content_id}.png"

                    inline_image_key = f"{uuid.uuid4().hex}/{inline_image_name}"
                    s3_client.put_object(
                        Bucket=attachments_bucket_name,
                        Key=inline_image_key,
                        Body=inline_image_data,
                        ContentType=content_type
                    )

                    inline_image_url = f"https://{attachments_bucket_name}.s3.amazonaws.com/{inline_image_key}"
                    print(f"Processed inline image: {content_id}, URL: {inline_image_url}")

                    # Add to attachments list with inline flag
                    attachments.append({
                        "filename": inline_image_name,
                        "public_url": inline_image_url,
                        "content_type": content_type,
                        "inline": True,
                        "content_id": content_id
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

        # Send HTTP POST request to the webhook
        try:
            response = requests.post(webhook_url, json=parsed_email, timeout=10)
            response.raise_for_status()
            print(f"Data sent to webhook {webhook_url} successfully.")
        except requests.exceptions.RequestException as e:
            print(f"Error sending data to webhook {webhook_url}: {e}")
            return {
                'statusCode': 500,
                'body': f"Error sending data to webhook {webhook_url}: {str(e)}"
            }

    return {
        'statusCode': 200,
        'body': "Email processed and data sent to webhook successfully."
    }
