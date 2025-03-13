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
webhook_bucket_name = os.environ.get('database_bucket_name', 'email-webhooks-bucket-3rfrd')

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

        # Extract email details
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
        # Retrieve webhook URL for the domain from the S3 bucket
        # Extract domain from recipient email using regex
        webhook_key = recipient.split('@')[-1].strip('>')
        print(f"Webhook key: {webhook_key}")
        try:
            webhook_response = s3_client.get_object(Bucket=webhook_bucket_name, Key=webhook_key)
            webhook_data = json.loads(webhook_response['Body'].read())
            webhook_url = webhook_data['webhook']
        except Exception as e:
            print(f"Error retrieving webhook for domain {webhook_key}: {e}")
            return {
                'statusCode': 500,
                'body': f"Webhook for domain {webhook_key} not found or error occurred."
            }

        # Extract email body and attachments
        if msg.is_multipart():
            for part in msg.iter_parts():
                content_type = part.get_content_type()
                content_disposition = part.get_content_disposition()

                if content_type == "text/plain":
                    body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
                elif content_type == "text/html":
                    html_body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
                    if not body:  # Use HTML as fallback if plain text is unavailable
                        body = html_body
                elif content_disposition and "attachment" in content_disposition:
                    # Process attachments
                    attachment_data = part.get_payload(decode=True)
                    attachment_name = part.get_filename()

                    # generate random guid and concatenate with attachment name

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
                elif "Content-ID" in part and not content_disposition:  # Process inline images
                    content_id = part['Content-ID'].strip('<>')
                    inline_image_data = part.get_payload(decode=True)
                    inline_image_name = part.get_filename() or f"inline_{content_id}.png"

                    inline_image_key = f"inline_images/{inline_image_name}"
                    s3_client.put_object(
                        Bucket=attachments_bucket_name,
                        Key=inline_image_key,
                        Body=inline_image_data
                    )

                    inline_image_url = f"https://{attachments_bucket_name}.s3.amazonaws.com/{inline_image_key}"

                    # Replace cid: references in the HTML body with the public URL
                    if html_body:
                        html_body = html_body.replace(f"cid:{content_id}", inline_image_url)
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
