# Phase 1B.2A: Backend Manual Production Smoke Closeout

**Date:** 2026-07-18
**Status:** ✅ PASSED — Backend Deployment Validation Complete

---

## Manual Smoke Result

Matthew performed a bounded read-only production smoke on the deployed website:

- ✅ Normal production Cognito login succeeded
- ✅ Client Management page loaded
- ✅ Existing client detail drawer opened
- ✅ Existing pet list loaded within the drawer
- ✅ No records were created, edited, archived, or deleted
- ✅ No settings, users, calendar, payment, or tenant configuration changed

Visual evidence was provided and reviewed. Production customer information is not reproduced in repository documentation.

## Authentication-Path Resolution

The deployment review identified that AG's post-apply validation used direct Lambda invocation (bypassing Cognito/API Gateway). This manual web smoke resolves that gap by confirming the real authenticated end-to-end path:
- Cognito login → ID token → API Gateway authorizer → Lambda handler → response

## Deployment Validation: COMPLETE

| Check | Method | Result |
|-------|--------|--------|
| Lambda Active/Successful (all 13) | AWS CLI | ✅ |
| Package hash match | Terraform show + SHA256 | ✅ |
| API Gateway routing (unauthenticated rejection) | curl | ✅ |
| Handler execution (direct invocation) | Lambda invoke | ✅ |
| Authenticated web path (login → Client Mgmt → drawer) | Manual browser | ✅ |
| No production data writes | Policy enforcement | ✅ |

## Current Production State

- Latest deployed backend: **Phase 1B.2A** (PET is_active hardening, commit `ca73d93`)
- Latest deployed frontend: **Phase 1B.1** (Client Management, commit `51b78bf`)
- TENANT_RESOLUTION_MODE: `multi` (unchanged)
- ClientPetIndex: temporarily absent from Terraform config, not deployed
- Stripe: sandbox-only
- Google Calendar: unchanged
- Google Play / Apple: deferred
- Ryan testing: paused
- No rollback required

## Next Gate

**Matthew approves ClientPetIndex configuration restoration and GSI-only Terraform plan generation.**

AG sequence:
1. Restore the ClientPetIndex configuration block (from `cda722a`)
2. Run `terraform fmt -check` and `terraform validate`
3. Generate a normal full Terraform plan
4. Expected: 0 add, 1 change, 0 destroy (DynamoDB table only)
5. Save and document the plan for Kiro review
6. Matthew separately approves GSI apply
