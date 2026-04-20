# Infrastructure Plan - Module Layout

Following the conventions in `website_infrastructure`, we use a modular approach with clear separation of concerns.

## Root Modules (`infra/prod`)
Main entry point for the production environment.
- `main.tf`: Coordinates module calls.
- `providers.tf`: Defines aliased providers (`aws.dns`, `aws.us_east_1`).
- `backend.tf`: S3/DynamoDB remote state config.
- `locals.tf`: Tagging standard and project-wide constants.

## Reusable Modules (`modules/`)

### 1. `data`
- **DynamoDB**: Simple table `TogAndDogsData`.
- Optimized for core workflows (Intake, Request, Job, Staff).

### 2. `auth`
- **Cognito User Pool**: For Ryan's backend access.

### 3. `api`
- **API Gateway (HTTP API)**: Routes and authorizers.
- **Lambdas (Python)**: Intake, Request Management, Admin API.

### 4. `workflow`
- **AWS Step Functions**: `ApprovalStateMachine`.

### 5. `frontend-hosting`
- **S3 Bucket**: Static assets.
- **CloudFront**: Distribution with SSL.

### 6. `notifications`
- **SNS/SES**: Ryan alerts and staff coordination.

### 7. `observability`
- **CloudWatch logs/alarms**: Tracking system health and audit trails.

### 8. `secrets`
- **Secrets Manager**: Centralized secret storage.

## Remote State Approach
- **Account**: `usmissionhero-website-prod` (358604342897).
- **S3 Bucket**: `togs-and-dogs-terraform-state` (to be created/confirmed).
- **DynamoDB Table**: `togs-and-dogs-terraform-lock` (to be created/confirmed).
- **Key**: `prod/terraform.tfstate`.
