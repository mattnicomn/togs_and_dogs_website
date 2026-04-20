# Backend Bootstrap Guide

This guide explains how to initialize the AWS resources required for the Terraform remote backend.

## 1. Authentication
Before running the bootstrap script, you must ensure you have an active AWS SSO session for the production workload account.

```powershell
# Authenticate with SSO
aws sso login --profile usmissionhero-website-prod
```

## 2. Running the Bootstrap Script
We provide both PowerShell (recommended for Windows) and Bash scripts.

### PowerShell
```powershell
cd c:\Users\mattn\OneDrive\Desktop\togs_and_dogs_website
.\scripts\bootstrap-backend.ps1
```

### Bash
```bash
./scripts/bootstrap-backend.sh
```

## 3. What it Creates
The script performs the following actions in account `358604342897` (`us-east-1`):
1. **Verifies Identity**: Ensures the profile targets the correct account.
2. **S3 Bucket**: `togs-and-dogs-358604342897-us-east-1-tfstate`
    - Uses a unique naming pattern: `[project]-[account]-[region]-tfstate`.
    - Enables **Versioning** (protects from accidental deletion).
    - Enables **Encryption** (AES256).
    - Blocks **Public Access**.
3. **DynamoDB Table**: `togs-and-dogs-terraform-lock`
    - Creates a table with a `LockID` partition key for state locking.

## 4. Verification
After the script completes, you can verify success by running:
```powershell
aws s3api head-bucket --bucket togs-and-dogs-358604342897-us-east-1-tfstate --profile usmissionhero-website-prod
aws dynamodb describe-table --table-name togs-and-dogs-terraform-lock --profile usmissionhero-website-prod
```

Once verified, you are ready to navigate to `infra/prod` and run `terraform init`.
