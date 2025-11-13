#!/bin/bash

# Real-time email receiving test for h.kidox.ai
AWS_PROFILE="main"
BUCKET="email-to-webhook-emails-main-302835751737"
TEST_EMAIL="test@h.kidox.ai"

echo "=========================================="
echo "Real-Time Email Receiving Test"
echo "=========================================="
echo ""
echo "Send a test email to: $TEST_EMAIL"
echo ""
echo "Monitoring bucket for new emails..."
echo "Press Ctrl+C to stop"
echo ""

# Get initial count
INITIAL_COUNT=$(aws s3 ls "s3://$BUCKET" --profile "$AWS_PROFILE" --recursive | wc -l | tr -d ' ')
echo "Current email count: $INITIAL_COUNT"
echo ""

# Monitor for changes
while true; do
    CURRENT_COUNT=$(aws s3 ls "s3://$BUCKET" --profile "$AWS_PROFILE" --recursive | wc -l | tr -d ' ')
    
    if [ "$CURRENT_COUNT" -gt "$INITIAL_COUNT" ]; then
        echo ""
        echo "✅ NEW EMAIL DETECTED!"
        echo ""
        echo "Latest emails in bucket:"
        aws s3 ls "s3://$BUCKET" --profile "$AWS_PROFILE" --recursive --human-readable | tail -5
        echo ""
        
        # Show the newest email
        NEWEST_EMAIL=$(aws s3 ls "s3://$BUCKET" --profile "$AWS_PROFILE" --recursive | sort -k1,2 | tail -1 | awk '{print $4}')
        echo "Downloading newest email: $NEWEST_EMAIL"
        echo ""
        aws s3 cp "s3://$BUCKET/$NEWEST_EMAIL" - --profile "$AWS_PROFILE" | head -30
        
        break
    fi
    
    echo -n "."
    sleep 2
done

echo ""
echo "Test complete!"

