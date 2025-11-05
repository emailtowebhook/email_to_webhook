# SES Receipt Rule Synchronization

## Overview
This document describes the dynamic domain-based SES receipt rule implementation that ensures emails are properly routed to environment-specific S3 buckets.

## How It Works

### Automatic Updates
When domains are registered or removed via the API, the SES receipt rules are automatically updated:

1. **Domain Registration (POST /v1/domain/{domain})**: 
   - Adds the domain to MongoDB
   - Updates the environment's SES receipt rule to include the domain in recipients list
   
2. **Domain Deletion (DELETE /v1/domain/{domain})**:
   - Removes the domain from MongoDB
   - Updates the SES receipt rule to remove the domain from recipients list

### Manual Synchronization
A sync endpoint is available to manually synchronize all domains from the database to the SES receipt rule.

#### Endpoint
```
POST /v1/domains/sync
```

#### When to Use
- After initial deployment
- After restoring from backup
- If automatic updates failed
- To ensure consistency between database and SES rules

#### Example Usage
```bash
curl -X POST https://your-api-endpoint/v1/domains/sync
```

#### Response
```json
{
  "message": "Successfully synced all domains to SES receipt rule",
  "domains_count": 5
}
```

## Environment Priority
Receipt rules are ordered by environment priority:
1. `main` (production) - Highest priority
2. `preview` - Second priority  
3. `dev` - Third priority
4. Other environments - Lower priority

This ensures that if a domain is registered in multiple environments, the highest priority environment receives the emails.

## Troubleshooting

### Emails Not Routing Correctly
1. Check if the domain is verified in SES
2. Verify the domain is registered in the correct environment's database
3. Run the sync endpoint to ensure receipt rules are up to date
4. Check CloudWatch logs for any errors

### Permission Errors
Ensure the Lambda function has the following IAM permissions:
- `ses:DescribeReceiptRule`
- `ses:PutReceiptRule`
- `ses:UpdateReceiptRule`

### Receipt Rule Not Found
Ensure the shared infrastructure is deployed first (`./deploy-shared.sh`), which creates the receipt rule set.
