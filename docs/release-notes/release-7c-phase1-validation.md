# Release 7C Phase 1 Validation & Stabilization

**Commit:** `b304ffe` (feat: add Release 7C device token registration API)
**Date:** May 27, 2026

## Overview

Release 7C Phase 1 successfully introduces the Device Token Registration API (`/client/devices`) to support future push notification capabilities. This rollout was achieved safely with push systems strictly disabled, ensuring zero impact on active notification/email workflows or production testing environments.

## Terraform Drift Resolution

During the initial `terraform apply`, a `ConflictException: Method already exists for this resource` error was encountered for `module.api.aws_api_gateway_method.delete_google_auth`. 

**Cause:** The `DELETE /admin/auth/google` API Gateway method was previously created via a manual CLI action to fix a production bug, resulting in state drift between AWS and local Terraform state.
**Resolution:** The drifted resource was safely imported back into state using the specific resource ID discovered via `aws apigateway get-resources`:
```bash
terraform import module.api.aws_api_gateway_method.delete_google_auth a022yxuiue/7zta8o/DELETE
```
Following the import, the subsequent `terraform plan` and `apply` correctly restored parity and safely generated the missing `aws_api_gateway_integration` component without destroying the existing endpoints.

## Smoke Test Validation

Live production API Gateway smoke tests were run post-deployment. All tests correctly returned `401 Unauthorized` exactly as expected when missing valid Cognito/Authentication headers, proving that the endpoints exist, are correctly routed, and securely protected:

- **POST /client/devices**: `401 Unauthorized` (Secured via Cognito)
- **DELETE /client/devices/{device_id}**: `401 Unauthorized` (Secured via Cognito)
- **GET /admin/auth/google**: `401 Unauthorized` (Google Auth intact)
- **DELETE /admin/auth/google**: `401 Unauthorized` (Google Disconnect intact)
- **POST /webhooks/postmark**: `401 Unauthorized` (Webhook secret validation intact)

## Production Guardrails Confirmed

*   **Push Notifications Disabled:** Confirmed in `locals.tf` that `PUSH_ENABLED="false"`, `PUSH_DRY_RUN="true"`, and `PUSH_PROVIDER="expo"` are safely hardcoded for Phase 1.
*   **Zero Impact on Live Workflows:** No changes were made to Postmark configuration, email templates, or the underlying `service.py` booking logic. Ryan's production testing workflows and all existing client routing mechanisms remain entirely unaffected.
