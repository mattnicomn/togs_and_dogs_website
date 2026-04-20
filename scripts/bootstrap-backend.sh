#!/bin/bash
# 
# Bootstrap Terraform backend resources (S3 & DynamoDB) for the Togs and Dogs project.
#

set -e

PROFILE="usmissionhero-website-prod"
TARGET_ACCOUNT="358604342897"
REGION="us-east-1"
BUCKET_NAME="togs-and-dogs-358604342897-us-east-1-tfstate"
TABLE_NAME="togs-and-dogs-terraform-lock"

echo "--- Togs and Dogs Backend Bootstrap ---"

# 1. Verify Caller Identity
echo "Verifying identity for profile '$PROFILE'..."
ACCOUNT_ID=$(aws sts get-caller-identity --profile "$PROFILE" --query "Account" --output text)

if [ "$ACCOUNT_ID" != "$TARGET_ACCOUNT" ]; then
    echo "CRITICAL: Current account $ACCOUNT_ID does not match target account $TARGET_ACCOUNT. Aborting."
    exit 1
fi
echo "Success: Verified identity for account $ACCOUNT_ID."

# 2. Check/Create S3 Bucket
echo -e "\nChecking S3 Bucket: $BUCKET_NAME..."
set +e
aws s3api head-bucket --bucket "$BUCKET_NAME" --profile "$PROFILE" --region "$REGION" 2>/dev/null
EXIT_CODE=$?
set -e

if [ $EXIT_CODE -eq 0 ]; then
    echo "Bucket '$BUCKET_NAME' already exists and is accessible."
elif [ $EXIT_CODE -eq 403 ]; then
    echo "CRITICAL: Bucket '$BUCKET_NAME' exists but is NOT accessible (Forbidden). It likely belongs to another account."
    exit 1
else
    echo "Bucket '$BUCKET_NAME' does not exist in this account. Creating..."
    aws s3api create-bucket --bucket "$BUCKET_NAME" --region "$REGION" --profile "$PROFILE"
    echo "Created bucket '$BUCKET_NAME'."
fi

# 3. Configure S3 Bucket
echo "Enforcing S3 versioning..."
aws s3api put-bucket-versioning --bucket "$BUCKET_NAME" --versioning-configuration Status=Enabled --profile "$PROFILE" --region "$REGION"

echo "Enforcing S3 server-side encryption..."
aws s3api put-bucket-encryption --bucket "$BUCKET_NAME" --server-side-encryption-configuration '{
    "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
}' --profile "$PROFILE" --region "$REGION"

echo "Enforcing S3 Public Access Block..."
aws s3api put-public-access-block --bucket "$BUCKET_NAME" --public-access-block-configuration '{
    "BlockPublicAcls": true,
    "IgnorePublicAcls": true,
    "BlockPublicPolicy": true,
    "RestrictPublicBuckets": true
}' --profile "$PROFILE" --region "$REGION"

# 4. Check/Create DynamoDB Lock Table
echo -e "\nChecking DynamoDB Table: $TABLE_NAME..."
set +e
aws dynamodb describe-table --table-name "$TABLE_NAME" --profile "$PROFILE" --region "$REGION" 2>/dev/null
EXIT_CODE=$?
set -e

if [ $EXIT_CODE -eq 0 ]; then
    echo "Table '$TABLE_NAME' already exists."
else
    echo "Table '$TABLE_NAME' does not exist. Creating..."
    aws dynamodb create-table \
        --table-name "$TABLE_NAME" \
        --attribute-definitions AttributeName=LockID,AttributeType=S \
        --key-schema AttributeName=LockID,KeyType=HASH \
        --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
        --region "$REGION" \
        --profile "$PROFILE"
    echo "Created table '$TABLE_NAME'."
fi

echo -e "\n--- Bootstrap Complete ---"
echo "You can now run 'terraform init' in the infra/prod directory."
