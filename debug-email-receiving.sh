#!/bin/bash

# Email Receiving Debug Script for h.kidox.ai
# This script checks all the components needed for email receiving to work

set -e

DOMAIN="h.kidox.ai"
ENVIRONMENT=${1:-"main"}
AWS_PROFILE="main"

echo "========================================"
echo "Debugging Email Receiving for $DOMAIN"
echo "Environment: $ENVIRONMENT"
echo "========================================"
echo ""

# Check AWS credentials
echo "1. Checking AWS Credentials..."
echo "   Using AWS Profile: $AWS_PROFILE"
if ! aws sts get-caller-identity --profile "$AWS_PROFILE" &> /dev/null; then
    echo "❌ AWS credentials not configured or invalid for profile '$AWS_PROFILE'"
    echo "   Run: aws configure --profile $AWS_PROFILE"
    exit 1
fi
ACCOUNT_ID=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query Account --output text)
echo "✅ AWS Account ID: $ACCOUNT_ID"
echo ""

# Get Terraform outputs
echo "2. Getting Infrastructure Details..."
cd infra
export AWS_PROFILE="$AWS_PROFILE"
EMAIL_BUCKET=$(terraform output -raw email_bucket_name 2>/dev/null || echo "")
RULE_SET_NAME="$ENVIRONMENT-rule-set"
if [ -z "$EMAIL_BUCKET" ]; then
    echo "❌ Could not get email bucket name from Terraform"
    echo "   Trying to construct bucket name from account ID..."
    EMAIL_BUCKET="email-to-webhook-emails-$ENVIRONMENT-$ACCOUNT_ID"
    echo "   Using: $EMAIL_BUCKET"
fi
echo "✅ Email Bucket: $EMAIL_BUCKET"
echo "✅ Rule Set: $RULE_SET_NAME"
cd ..
echo ""

# Check domain verification in SES
echo "3. Checking SES Domain Verification..."
VERIFICATION=$(aws ses get-identity-verification-attributes --profile "$AWS_PROFILE" --identities "$DOMAIN" --output json)
VERIFICATION_STATUS=$(echo "$VERIFICATION" | jq -r ".VerificationAttributes.\"$DOMAIN\".VerificationStatus // \"NotFound\"")
echo "   Domain Verification Status: $VERIFICATION_STATUS"
if [ "$VERIFICATION_STATUS" != "Success" ]; then
    echo "❌ Domain is not verified in SES!"
    echo "   Current status: $VERIFICATION_STATUS"
    echo ""
    echo "   To verify the domain, you need to:"
    echo "   1. POST to your API: /v1/domain/$DOMAIN"
    echo "   2. Wait for verification to complete"
else
    echo "✅ Domain is verified in SES"
fi
echo ""

# Check active receipt rule set
echo "4. Checking Active Receipt Rule Set..."
ACTIVE_RULE_SET=$(aws ses describe-active-receipt-rule-set --profile "$AWS_PROFILE" --output json 2>/dev/null || echo "{}")
ACTIVE_NAME=$(echo "$ACTIVE_RULE_SET" | jq -r '.Metadata.Name // "None"')
echo "   Active Rule Set: $ACTIVE_NAME"
if [ "$ACTIVE_NAME" != "$RULE_SET_NAME" ]; then
    echo "⚠️  Warning: Active rule set ($ACTIVE_NAME) doesn't match expected ($RULE_SET_NAME)"
else
    echo "✅ Correct rule set is active"
fi
echo ""

# Check receipt rules in the rule set
echo "5. Checking Receipt Rules..."
RECEIPT_RULE=$(aws ses describe-receipt-rule-set --profile "$AWS_PROFILE" --rule-set-name "$RULE_SET_NAME" --output json 2>/dev/null || echo "{}")
RULE_COUNT=$(echo "$RECEIPT_RULE" | jq '.Rules | length')
echo "   Number of rules: $RULE_COUNT"
if [ "$RULE_COUNT" -gt 0 ]; then
    echo "$RECEIPT_RULE" | jq -r '.Rules[] | "   - Rule: \(.Name) | Enabled: \(.Enabled) | Recipients: \(if .Recipients then (.Recipients | join(", ")) else "ALL" end)"'
    echo "✅ Receipt rules configured"
else
    echo "❌ No receipt rules found!"
fi
echo ""

# Check S3 bucket
echo "6. Checking S3 Email Bucket..."
if aws s3 ls "s3://$EMAIL_BUCKET" --profile "$AWS_PROFILE" &> /dev/null; then
    OBJECT_COUNT=$(aws s3 ls "s3://$EMAIL_BUCKET" --profile "$AWS_PROFILE" --recursive | wc -l | tr -d ' ')
    echo "✅ Bucket exists"
    echo "   Objects in bucket: $OBJECT_COUNT"
    if [ "$OBJECT_COUNT" -gt 0 ]; then
        echo ""
        echo "   Recent objects:"
        aws s3 ls "s3://$EMAIL_BUCKET" --profile "$AWS_PROFILE" --recursive | tail -5
    else
        echo "   ⚠️  Bucket is empty - no emails received yet"
    fi
else
    echo "❌ Cannot access bucket"
fi
echo ""

# Check S3 bucket policy
echo "7. Checking S3 Bucket Policy..."
BUCKET_POLICY=$(aws s3api get-bucket-policy --profile "$AWS_PROFILE" --bucket "$EMAIL_BUCKET" 2>/dev/null || echo "")
if [ -n "$BUCKET_POLICY" ]; then
    SES_PERMISSION=$(echo "$BUCKET_POLICY" | jq -r '.Policy | fromjson | .Statement[] | select(.Principal.Service == "ses.amazonaws.com") | .Action')
    if [ -n "$SES_PERMISSION" ] && [ "$SES_PERMISSION" != "null" ]; then
        echo "✅ SES has permission to write to bucket"
    else
        echo "❌ SES does not have PutObject permission on bucket"
    fi
else
    echo "❌ No bucket policy found"
fi
echo ""

# Check CloudWatch Logs for parsing lambda
echo "8. Checking Recent Lambda Logs..."
PARSER_LAMBDA_LOG_GROUP="/aws/lambda/email-parser-lambda-$ENVIRONMENT"
echo "   Log Group: $PARSER_LAMBDA_LOG_GROUP"
if aws logs describe-log-groups --profile "$AWS_PROFILE" --log-group-name-prefix "$PARSER_LAMBDA_LOG_GROUP" --output json | jq -e '.logGroups[0]' > /dev/null 2>&1; then
    echo "✅ Lambda log group exists"
    echo ""
    echo "   Recent log events (last 10 minutes):"
    aws logs tail "$PARSER_LAMBDA_LOG_GROUP" --profile "$AWS_PROFILE" --since 10m --format short 2>/dev/null || echo "   No recent logs"
else
    echo "⚠️  Lambda log group not found (Lambda may not have run yet)"
fi
echo ""

echo "========================================"
echo "Summary"
echo "========================================"
echo ""
echo "Test email receiving by sending an email to: test@$DOMAIN"
echo ""
echo "If emails still don't appear in S3:"
echo "1. Check if domain verification is 'Success'"
echo "2. Verify the receipt rule set is active"
echo "3. Ensure receipt rules exist and are enabled"
echo "4. Check S3 bucket policy allows SES to write"
echo "5. Try sending from a verified external email (Gmail, etc.)"
echo ""

