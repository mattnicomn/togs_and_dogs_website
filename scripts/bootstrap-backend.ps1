<#
.SYNOPSIS
    Bootstrap Terraform backend resources (S3 & DynamoDB) for the Togs and Dogs project.
    
.DESCRIPTION
    This script verifies the AWS identity and profile before creating:
    - S3 Bucket for state storage with versioning, encryption, and public access blocks.
    - DynamoDB table for state locking.

.PARAMETER Profile
    The AWS CLI profile to use. Defaults to 'usmissionhero-website-prod'.

.PARAMETER TargetAccount
    The expected AWS Account ID. Defaults to '358604342897'.

.PARAMETER Region
    The AWS region for resources. Defaults to 'us-east-1'.
#>

param (
    [string]$Profile = "usmissionhero-website-prod",
    [string]$TargetAccount = "358604342897",
    [string]$Region = "us-east-1",
    [string]$BucketName = "togs-and-dogs-358604342897-us-east-1-tfstate",
    [string]$TableName = "togs-and-dogs-terraform-lock"
)

$ErrorActionPreference = "Stop"

Write-Host "--- Togs and Dogs Backend Bootstrap ---" -ForegroundColor Cyan

# 1. Verify Caller Identity
try {
    Write-Host "Verifying identity for profile '$Profile'..."
    $identityJson = aws sts get-caller-identity --profile $Profile --output json
    if ($LASTEXITCODE -ne 0) { throw "STS Check Failed" }
    $identity = $identityJson | ConvertFrom-Json
    
    if ($identity.Account -ne $TargetAccount) {
        Write-Error "CRITICAL: Current account $($identity.Account) does not match target account $TargetAccount. Aborting."
    }
    Write-Host "Success: Verified identity as $($identity.Arn)" -ForegroundColor Green
}
catch {
    Write-Error "Failed to verify identity. Please ensure you have run 'aws sso login --profile $Profile'."
}

# 2. Check/Create S3 Bucket
Write-Host "`nChecking S3 Bucket: $BucketName..."
$bucketExistsInAccount = $false

# Native commands don't trigger PowerShell try/catch by default, so we check $LASTEXITCODE
& aws s3api head-bucket --bucket $BucketName --profile $Profile --region $Region 2>$null
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    $bucketExistsInAccount = $true
    Write-Host "Bucket '$BucketName' already exists and is accessible." -ForegroundColor Yellow
}
elseif ($exitCode -eq 403) {
    Write-Error "CRITICAL: Bucket '$BucketName' exists but is NOT accessible (Forbidden). It likely belongs to another account. Please use a more unique bucket name."
}
else {
    # Exit code 254/255 usually indicates 404 for head-bucket
    Write-Host "Bucket '$BucketName' does not exist or is not in this account. Creating..."
    aws s3api create-bucket --bucket $BucketName --region $Region --profile $Profile
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create bucket." }
    $bucketExistsInAccount = $true
    Write-Host "Created bucket '$BucketName'." -ForegroundColor Green
}

# 3. Configure S3 Bucket (Versioning, Encryption, Public Access)
if ($bucketExistsInAccount) {
    Write-Host "Enforcing S3 versioning..."
    aws s3api put-bucket-versioning --bucket $BucketName --versioning-configuration Status=Enabled --profile $Profile --region $Region
    
    Write-Host "Enforcing S3 server-side encryption..."
    aws s3api put-bucket-encryption --bucket $BucketName --server-side-encryption-configuration '{
        "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
    }' --profile $Profile --region $Region
    
    Write-Host "Enforcing S3 Public Access Block..."
    aws s3api put-public-access-block --bucket $BucketName --public-access-block-configuration '{
        "BlockPublicAcls": true,
        "IgnorePublicAcls": true,
        "BlockPublicPolicy": true,
        "RestrictPublicBuckets": true
    }' --profile $Profile --region $Region
}

# 4. Check/Create DynamoDB Lock Table
Write-Host "`nChecking DynamoDB Table: $TableName..."
& aws dynamodb describe-table --table-name $TableName --profile $Profile --region $Region 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "Table '$TableName' already exists." -ForegroundColor Yellow
}
else {
    Write-Host "Table '$TableName' does not exist. Creating..."
    aws dynamodb create-table `
        --table-name $TableName `
        --attribute-definitions AttributeName=LockID,AttributeType=S `
        --key-schema AttributeName=LockID,KeyType=HASH `
        --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 `
        --region $Region `
        --profile $Profile
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create DynamoDB table." }
    Write-Host "Created table '$TableName'." -ForegroundColor Green
}

Write-Host "`n--- Bootstrap Complete ---" -ForegroundColor Cyan
Write-Host "You can now run 'terraform init' in the infra/prod directory."
