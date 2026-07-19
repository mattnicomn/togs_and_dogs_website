# Release Notes: Phase 1B.2A — ClientPetIndex GSI-Only Terraform Plan

## 1. Executive Summary

This document records the generation of the isolated `ClientPetIndex` global secondary index (GSI) production Terraform plan. 

The `ClientPetIndex` configuration block was fully restored to the HCL schema. A full, non-targeted Terraform plan was then generated against production, capturing only the GSI addition on the DynamoDB data table.

No Terraform apply, database modification, or index creation occurred. The GSI remains undeployed. The old combined plan (`phase-1b2a-client-pet-index.tfplan`) remains blocked and must never be applied.

---

## 2. Plan Identity

- **Restoration Commit Hash:** `757cabb`
- **Saved Plan Filename:** `phase-1b2a-client-pet-index-gsi-only.tfplan` (located under `infra/prod/`)
- **Saved Plan Checksum (SHA256):** `858986d96a673ba7256bb0c4b369216f69220fb6d3d5d4310664c51e5d7ef90a`
- **Plan Summary:** `0 to add, 1 to change, 0 to destroy.`
- **Target environment:** `production`

---

## 3. GSI Configuration Restored

The following GSI configuration block was restored in [modules/data/main.tf](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/modules/data/main.tf) matching the original design:

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

---

## 4. Production Plan Resource & Actions

The plan contains exactly one in-place update on the DynamoDB data table resource:

| Resource Address | Action | Description |
|------------------|--------|-------------|
| `module.data.aws_dynamodb_table.main` | `~ update in-place` | Add `client_id` and `pet_id` attributes, and add GSI `ClientPetIndex` |

- **No replacement** of the DynamoDB table is planned.
- **No destruction** of any resource is planned.
- **No Lambda function changes** or package hash changes are planned.
- **No API Gateway, IAM, Cognito, S3, or CloudFront changes** are present in the plan.
- **No unrelated drift** has been captured.

---

## 5. Rollout and Backfill Expectations

- **Online Update:** The index addition is planned as an in-place update to the active table. Existing database traffic will be unaffected during creation.
- **Automatic Backfill:** AWS DynamoDB automatically backfills the index with eligible records.
- **GSI Inclusion Criteria:** Only items containing both a scalar `client_id` (hash key) and `pet_id` (range key) will enter the index.
  - Estimated 68 legacy PET records will be indexed and defensible.
  - Estimated 13 legacy PET records will be indexed but must be excluded by tenant company_id filters.
  - Estimated 3 malformed legacy PET records lacking one or both keys will not enter the index.
- **ACTIVE Status:** The index status must be monitored until it reports `ACTIVE` before any backend query cutover is deployed.
- **Query cutover, remediation, and frontend pet inventory** remain deferred and are not part of this plan.

---

## 6. Status & Next Gate

- **Backend Deployment:** Deployed and validated in production (Release `f64cf7c`).
- **GSI Creation:** Pending Kiro plan review and Matthew approval.
- **Action Required:** Approve saved plan application (`phase-1b2a-client-pet-index-gsi-only.tfplan`).
