# Terraform Drift Reconciliation

## Current safety notice — 2026-08-24

The reviewed API semantic-fingerprint fix is integrated into `main` and isolated on a deployed-baseline migration branch. Fresh saved plan `infra/prod/api-semantic-fingerprint-migration-20260824.tfplan` (SHA-256 `9629B084680E0E519B9C7F0CEE153514F99F68BA89961DA9CBEBDA6C105D99FA`) shows exactly one create-before-destroy API deployment replacement plus only the stage `deployment_id` update: 1 add, 1 change, 1 destroy, with zero Lambda or API-topology changes. It has not been applied and requires Matthew approval.

ROUTE-GATE-A remains blocked. The prior DOMAIN-1 saved plan is permanently rejected and must never be applied. Stripe test credential rotation remains separately approval-gated. See `docs/release-notes/api-gateway-semantic-fingerprint-migration-plan.md`.

The historical material below is retained for context and is not authorization for current work.

---

# Historical: Google Calendar Disconnect

**Date**: May 27, 2026  
**Component**: API Gateway, Lambda (`togs-and-dogs-prod-google-auth`)  
**Context**: During the deployment of the Google Calendar Disconnect fix, the local Terraform binary was unavailable (`CommandNotFoundException`). To unblock production, manual AWS CLI commands were used to provision the required `DELETE` method for the `/admin/auth/google` API Gateway route and update the backend Lambda code.

## Current State (Drift)
- **API Gateway**: A `DELETE` method and `AWS_PROXY` integration were manually added to the `admin_auth_google` resource (`/admin/auth/google`) using the Cognito Authorizer `r0gk6r`.
- **Lambda**: The code for `togs-and-dogs-prod-google-auth` was updated via `aws lambda update-function-code` but its source code hash in Terraform state has not been reconciled.
- **Terraform Config**: The `modules/api/main.tf` file **was** updated with the correct `aws_api_gateway_method` and `aws_api_gateway_integration` blocks for the `DELETE` method, meaning the codebase is correct.

## Required Actions

Once the local Terraform CLI environment is restored, an engineer must execute the following reconciliation steps:

### 1. Verify Configuration
Ensure you are in the correct production infra directory:
```bash
cd infra/prod
```

### 2. Generate Plan
Run a plan to safely review the drift reconciliation:
```bash
terraform plan -out=drift-reconciliation.tfplan
```

### 3. Review Plan Safely
Carefully review the output. Terraform should indicate:
- **No destruction** of existing API Gateway resources.
- A "modify" or "update in-place" action for the API Gateway deployment to align with the manually added `DELETE` route.
- A "modify" action for the Lambda function's source code hash/version to align the state with the deployed code.

⚠️ **WARNING**: If the plan indicates that it will DESTROY and RECREATE the `admin_auth_google` resource or the `DELETE` method, you must run a `terraform import` to manually pull the existing AWS resource into the state file before applying.

### 4. Apply
If the plan is clean and purely aligns the state with the existing infrastructure, apply it:
```bash
terraform apply drift-reconciliation.tfplan
```

### 5. Verification
After applying, verify that the Disconnect button on the Admin Dashboard still functions perfectly and that no CORS errors (`Failed to fetch`) have regressed.
