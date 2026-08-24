# Terraform Drift and Deployment Trigger Reconciliation

## Current safety notice — 2026-08-24

ROUTE-GATE-A is **BLOCKED / NOT READY**. The saved plan `route-gate-a-b1a-route-20260824.tfplan` (SHA-256 `B127670C9229D694711CC428B86AE908FC2ADFB17EC563B4BD3F098F5310E7DF`) is permanently rejected and must never be applied.

The plan exposed a deterministic-trigger defect: `aws_api_gateway_deployment.main` hashed whole provider objects, so provider normalization of equivalent absent optional values (`null`, `[]`, `{}`, and `""`) caused an unnecessary deployment replacement and stage pointer update during a Lambda-only candidate. A dedicated local infrastructure prerequisite RC now replaces that design with an explicit, normalized semantic manifest and provider-independent fingerprint module. It is not deployed and still requires independent review. A fresh saved plan requires separate authorization after that review; no current plan is approved.

The remediation excludes provider IDs, deployment IDs, timestamps, Lambda package/hash/last-modified data, and unrelated Lambda configuration. Focused tests prove null/empty stability and positive changes for path, verb, authorization, integration target, request mapping, and CORS behavior. See `docs/release-notes/api-gateway-semantic-deployment-fingerprint-infrastructure-rc.md`.

A prior plan-inspection incident identified exposure of a Stripe test API credential and a Stripe test webhook-signing credential. Rotation was not performed and requires separate Matthew approval. Stripe remains sandbox/test-mode only. No secret value may be copied into commands, documentation, fixtures, diffs, or review output.

The May 2026 material below is retained as historical context only. Its plan/apply examples are not authorization for present work and must not be used for ROUTE-GATE-A.

---

# Historical: Google Calendar Disconnect Drift Reconciliation

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
