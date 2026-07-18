# Release Notes: Phase 1B.2A — Backend-Only Terraform Plan

## 1. Executive Summary

This release note documents the generation of the clean, backend-only production Terraform plan. The plan targets only the 13 Lambda functions to apply the pet creation `is_active` hardening code. 

To achieve this, the undeployed `ClientPetIndex` global secondary index configuration was temporarily removed from the repository. This guarantees that the resulting plan contains no DynamoDB changes, replacements, or destructions, matching the approved release sequencing layout.

No Terraform apply, Lambda deployment, or DynamoDB modification occurred. The old contaminated plan remains blocked and must never be applied.

---

## 2. Core Plan Metrics

- **Saved Plan Filename:** `phase-1b2a-backend-only.tfplan` (located under `infra/prod/`)
- **Saved Plan Checksum (SHA256):** `102f899be77e57f278b0878d6b341ca9326b801cceb8a5be404cd98eaafbc5c1`
- **Plan Summary:** `0 to add, 13 to change, 0 to destroy.`
- **Target environment:** `production`

---

## 3. Temporary GSI Configuration Removal

- **Removal Commit Hash:** `f3b9a7927d353beec7784fb41c42289659b8eb61`
- **Rationale:** To isolate the deployment of application-hardening changes from structural database index creations. By removing the GSI block, we avoid planning errors and scope mismatches, ensuring a clean in-place update for Lambda code package hashes.
- **Exact Configuration Removed from [modules/data/main.tf](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/modules/data/main.tf):**
  ```terraform
  # GSI for Client-to-Pet relationships
  attribute {
    name = "client_id"
    type = "S"
  }

  attribute {
    name = "pet_id"
    type = "S"
  }

  global_secondary_index {
    name            = "ClientPetIndex"
    hash_key        = "client_id"
    range_key       = "pet_id"
    projection_type = "ALL"
  }
  ```
- **Preservation:** The index design remains approved and documented. The GSI config will be fully restored via commit revert immediately following the backend release deployment.

---

## 4. Deterministic Backend Archive Details

- **Packaging Exclusion Commit:** `2386a93`
- **Backend ZIP Checksum (SHA256):** `556fa0a147967ef61c6363f96559e4eed5aac46ba3dff234afa3262c074f008a`
- **Archive Metrics:**
  - Total ZIP entries: `39`
  - `.pytest_cache/` entries: `0`
  - `__pycache__/` entries: `0`
  - `.pyc`/`.pyo` files: `0`
  - Tracked backend files count: `39` (matching `git ls-files` exactly)
  - Missing tracked files: `0`
  - Unexpected included files: `0`

---

## 5. Production Plan Resources & Actions

All 13 Lambda functions are updated in-place via their `source_code_hash`:

| Resource Address | Action | Description / Handler |
|------------------|--------|-----------------------|
| `aws_lambda_function.admin` | `~ update in-place` | `handlers.admin_handler.handler` |
| `aws_lambda_function.assign` | `~ update in-place` | `handlers.assignment_handler.handler` |
| `aws_lambda_function.cancellation` | `~ update in-place` | `handlers.cancellation_handler.handler` |
| `aws_lambda_function.device` | `~ update in-place` | `handlers.device_handler.handler` |
| `aws_lambda_function.google_auth` | `~ update in-place` | `handlers.google_auth_handler.handler` |
| `aws_lambda_function.intake` | `~ update in-place` | `handlers.intake_handler.handler` |
| `aws_lambda_function.job` | `~ update in-place` | `handlers.job_handler.handler` |
| `aws_lambda_function.pet` | `~ update in-place` | `handlers.pet_handler.handler` |
| `aws_lambda_function.platform` | `~ update in-place` | `handlers.platform_handler.handler` |
| `aws_lambda_function.postmark_webhook` | `~ update in-place` | `handlers.postmark_webhook_handler.handler` |
| `aws_lambda_function.review` | `~ update in-place` | `handlers.review_handler.handler` |
| `aws_lambda_function.ses_feedback` | `~ update in-place` | `handlers.notification_feedback_handler.handler` |
| `aws_lambda_function.stripe_webhook` | `~ update in-place` | `handlers.stripe_webhook_handler.handler` |

- **No replacements or destructions** are present in the plan.
- **No DynamoDB Table or index changes** are present.
- **No unrelated drift** has been captured.

---

## 6. Packaged Source Delta Verification

- **Baseline Commit:** `234b51d`
- **Source Code Delta:** The only modified file inside `src/backend` is `src/backend/handlers/pet_handler.py`.
- **Change Description:** Adds default `is_active=True` handling for new pet creations.
- **Remediation Script status:** The remediation tools located in `scripts/` are excluded from the zip archive.

---

## 7. Status & Next Gate

- **Latest Deployed Release:** Phase 1B.1 (`51b78bf`)
- **Backend Deployment Status:** Pending Kiro plan review and Matthew approval.
- **GSI Deployment Status:** Pending backend release verification.
- **Action Required:** Approve S3 plan application (`phase-1b2a-backend-only.tfplan`).
