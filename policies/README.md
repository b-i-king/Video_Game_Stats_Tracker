# IAM and Security Policies

AWS IAM and SQS policies for the Instagram poster.

## Files

### IAM Policies (for IAM user)
- **iam-s3-policy.json** - S3 bucket management permissions

### Lambda IAM Policies (for Lambda execution role)
- **trust-policy.json** - Lambda service trust policy
- **lambda-policy.json** - SQS, SNS, Secrets Manager, S3 access

### SQS Policies
- **sqs-policy.json** - Restrict queue to Lambda only (template)
- **sqs-policy-final.json** - Applied policy (gitignored, generated)

### S3 Configuration
- **encryption-config.json** - S3 bucket encryption settings
- **lifecycle-config.json** - S3 lifecycle rules (cleanup old versions)

## Usage

### Applying IAM User Policy
```powershell
aws iam put-user-policy `
  --user-name instagram-poster-deployer `
  --policy-name S3BucketAccess `
  --policy-document file://policies/iam-s3-policy.json
```

### Applying Lambda Role Policies
```powershell
# Trust policy
aws iam create-role `
  --role-name InstagramPosterLambdaRole `
  --assume-role-policy-document file://policies/trust-policy.json

# Custom policy
aws iam put-role-policy `
  --role-name InstagramPosterLambdaRole `
  --policy-name InstagramPosterPolicy `
  --policy-document file://policies/lambda-policy.json
```

### Applying SQS Policy
```powershell
# Replace YOUR-ACCOUNT-ID in sqs-policy.json first
$ACCOUNT_ID = (aws sts get-caller-identity --query 'Account' --output text)
$PolicyContent = Get-Content policies/sqs-policy.json -Raw
$PolicyContent = $PolicyContent -replace 'YOUR-ACCOUNT-ID', $ACCOUNT_ID
$PolicyContent | Out-File -FilePath policies/sqs-policy-final.json

# Apply
$PolicyJson = $PolicyContent | ConvertFrom-Json | ConvertTo-Json -Compress
aws sqs set-queue-attributes --queue-url $QUEUE_URL --attributes "{`"Policy`":$PolicyJson}"
```

## Security Notes

- Keep `sqs-policy-final.json` out of Git (has account ID)
- Review policies before applying
- Follow principle of least privilege
- All policies scoped to instagram-poster resources