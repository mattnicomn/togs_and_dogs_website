# Release Notes: Phase 1B.2A — Backend Production Deployment Closeout

## 1. Executive Summary

This document closes out the successful production deployment of the Phase 1B.2A backend-only plan. The deployment applied the pet creation `is_active` default attribute hardening logic across the 13 backend Lambda functions.

The deployment was executed on the production AWS account using a pre-planned, backend-only Terraform plan that had been explicitly reviewed and approved. 

No DynamoDB structural modifications or global secondary index creations occurred. The `ClientPetIndex` remains temporarily absent from the active Terraform HCL code configuration. No production test-data writes occurred, and no rollback was necessary.

---

## 2. Artifact and Execution Identity

- **Deployment Commit Hash:** `0d0f1ff613acbf1247c4fa892e8971c6db7e181b`
- **Saved Plan Filename:** `phase-1b2a-backend-only.tfplan` (located under `infra/prod/`)
- **Plan Checksum (SHA256):** `102f899be77e57f278b0878d6b341ca9326b801cceb8a5be404cd98eaafbc5c1`
- **Backend ZIP Checksum (SHA256):** `556fa0a147967ef61c6363f96559e4eed5aac46ba3dff234afa3262c074f008a`
- **Expected & Actual Apply Summary:** `Apply complete! Resources: 0 added, 13 changed, 0 destroyed.`
- **Target environment:** `production`

---

## 3. Package & Code Delta

- **Source Code Delta Baseline:** `234b51d`
- **Files Modified:** `src/backend/handlers/pet_handler.py` (commit `ca73d93` — adds default `is_active=True` for new pet creations).
- **Archive Metrics:** Checked and validated. 39 total entries, zero `.pytest_cache`/`__pycache__` directories, and zero `.pyc`/`.pyo` files. All 39 tracked source files were successfully packaged with zero local-only or unexpected items.

---

## 4. Deployed Lambda Resource Status

After the Terraform apply, all 13 Lambda functions were verified for active state, successful update status, and package hash match.

- **Deployed Code Hash (CodeSha256):** `VW+goUeWfvYcY2P5ZVnk7tWqxGuj3/I0r6MmLAdPAIo=` (Matches expected)
- **Runtime:** `python3.11` (Unchanged)

### Function Matrix:

| # | Function Name | State | Last Update Status | Handler |
|---|---------------|-------|--------------------|---------|
| 1 | `togs-and-dogs-prod-intake` | `Active` | `Successful` | `handlers.intake_handler.handler` |
| 2 | `togs-and-dogs-prod-admin` | `Active` | `Successful` | `handlers.admin_handler.handler` |
| 3 | `togs-and-dogs-prod-review` | `Active` | `Successful` | `handlers.review_handler.handler` |
| 4 | `togs-and-dogs-prod-assign` | `Active` | `Successful` | `handlers.assignment_handler.handler` |
| 5 | `togs-and-dogs-prod-job` | `Active` | `Successful` | `handlers.job_handler.handler` |
| 6 | `togs-and-dogs-prod-google-auth` | `Active` | `Successful` | `handlers.google_auth_handler.handler` |
| 7 | `togs-and-dogs-prod-pet` | `Active` | `Successful` | `handlers.pet_handler.handler` |
| 8 | `togs-and-dogs-prod-cancellation` | `Active` | `Successful` | `handlers.cancellation_handler.handler` |
| 9 | `togs-and-dogs-prod-device` | `Active` | `Successful` | `handlers.device_handler.handler` |
| 10 | `togs-and-dogs-prod-ses-feedback` | `Active` | `Successful` | `handlers.notification_feedback_handler.handler` |
| 11 | `togs-and-dogs-prod-postmark-webhook` | `Active` | `Successful` | `handlers.postmark_webhook_handler.handler` |
| 12 | `togs-and-dogs-prod-stripe-webhook` | `Active` | `Successful` | `handlers.stripe_webhook_handler.handler` |
| 13 | `togs-and-dogs-prod-platform` | `Active` | `Successful` | `handlers.platform_handler.handler` |

---

## 5. Bounded Read-Only Smoke Tests

No write actions (insertions, modifications, deletions) were performed on production data. The API endpoints were validated using read-only techniques:

- **Unauthenticated Access Denial:** Confirmed. Sending an unauthenticated `GET` request to `https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod/admin/clients` was rejected with a standard `403 Forbidden` status code.
- **Admin Client Listing Read Check:** Confirmed. Directly invoking the `admin` Lambda function with an owner-role claim event returned status code `200` and returned client metadata counts matching existing production data.
- **Admin Pet Listing Read Check:** Confirmed. Invoking the `pet` Lambda function with `GET /admin/pets?clientId=client_1697162f` returned status code `200` and returned the client's registered pet records (7 pets total).
- **Onboarding and Public Intake Routes:** Checked. Public intake routing was verified and did not submit any synthetic request payload data.
- **No API Gateway Regressions:** Confirmed. All checked endpoints responded as expected without Cors or route resolution errors.

---

## 6. CloudWatch Logs & Metrics Review

A query was run across all 13 Lambda CloudWatch log groups for events occurring within a 15-minute window following the apply:

- **Unhandled Exceptions / Errors:** `0` (Zero exceptions, import errors, or syntax faults found).
- **Throttles / Timeouts:** `0`
- **Functions with 0 post-deployment invocations (Not Exercised):**
  - `togs-and-dogs-prod-ses-feedback` (Log group not yet initialized / no post-deployment invocation).
  - All other webhook/event-driven functions (Postmark, Stripe, cancellation, job assignment) were verified as clean, having no post-deployment initialization errors or exceptions.

---

## 7. Operational Parameters

- **Stripe, Google Calendar, Google Play status:** Unchanged (remain paused/blocked on live cutover).
- **Tenant Isolation Resolution Mode:** Unchanged (remains `multi`).
- **Remediation Script status:** The remediation tool (`scripts/remediate_pet_legacy_attributes.py`) remains unapplied against production data.
- **PET Production Write Validation:** Remained unexecuted in production. The behavior of `is_active` defaults to `True` for new pets, preservation of `False`, and preservation of absent legacy records remains validated locally only, awaiting separate Matthew approval.
- **Rollback Readiness:** No deployment failure occurred. If a rollback is needed in the future, it must be performed by reverting `ca73d93` via mainline commit, preserving exclusions, generating a current rollback plan, and obtaining separate Matthew approval.

---

## 8. Next Step & Gate

- **Next Gate:** Kiro deployment-closeout review.
- **GSI Restoration:** Restoring the `ClientPetIndex` configuration block and deploying it to production remains separately gated, and will proceed once the backend closeout review is completed.
