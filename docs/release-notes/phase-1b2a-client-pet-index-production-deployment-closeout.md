# Release Notes: Phase 1B.2A — ClientPetIndex Production Deployment Closeout

## 1. Executive Summary

This document closes out the successful production deployment of the `ClientPetIndex` global secondary database index (GSI). 

The GSI addition was applied to the production table `togs-and-dogs-prod-data` in-place. The GSI was created and backfilled successfully by AWS DynamoDB, reaching the `ACTIVE` status without impacting active database traffic.

No replacements or destructions of DynamoDB resources occurred. No Lambda packages, API Gateway configs, or other infrastructure resources were modified. The application behavior remains unchanged, as backend query cutover is deferred.

---

## 2. Artifact and Execution Identity

- **Deployment Commit Hash:** `6f50bc47b58bd23ff5dab2ad5a14c0de4dadaa48`
- **Saved Plan Filename:** `phase-1b2a-client-pet-index-gsi-only.tfplan` (located under `infra/prod/`)
- **Saved Plan Checksum (SHA256):** `858986d96a673ba7256bb0c4b369216f69220fb6d3d5d4310664c51e5d7ef90a`
- **Expected & Actual Apply Summary:** `Apply complete! Resources: 0 added, 1 changed, 0 destroyed.`
- **Target environment:** `production`

---

## 3. Restored GSI Configuration

The DynamoDB table schema now includes the exact approved GSI definition:

- **Index Name:** `ClientPetIndex`
- **Hash Key:** `client_id` (Type: `S`)
- **Range Key:** `pet_id` (Type: `S`)
- **Projection Type:** `ALL`

---

## 4. DynamoDB Table and Index Verification

Read-only describe operations confirmed the successful creation and healthy state of the GSI:

- **Table Name:** `togs-and-dogs-prod-data` (Preserved)
- **Table Status:** `ACTIVE`
- **Billing Mode:** `PAY_PER_REQUEST` (Preserved)
- **Primary Key Schema:** HASH `PK`, RANGE `SK` (Preserved)
- **Existing Indexes Status:**
  - `StatusIndex` -> `ACTIVE` (Preserved)
  - `WorkerIndex` -> `ACTIVE` (Preserved)
- **New Index Status:**
  - `ClientPetIndex` -> `ACTIVE` (Successfully backfilled)
  - **Backfilling:** `None` (Backfill completed)

---

## 5. Rollout and Backfill Expectations

- **Eligible Items Backfill:** AWS DynamoDB completed the backfill. Only items containing both a scalar `client_id` and `pet_id` have entered the index.
  - 68 PET records are defensible and indexed.
  - 13 PET records are indexed but must be excluded by future backend company_id filters.
  - 3 PET records lack one or both keys and remain outside the index.
- **ClientPetIndex is Not Authorization:** The index is purely for retrieval. Tenant company_id validation must continue to be enforced by the backend handlers.
- **No Production Remediation:** No remediation script or write-testing has run against production data in this task.

---

## 6. Application Status & Next Step

- **Lambda / API Status:** Unchanged. The current backend Lambda functions do not yet query the new GSI.
- **Frontend Status:** Unchanged. The frontend pet inventory page remains undeployed.
- **Old Combined Plan:** Permanently blocked.
- **Next Gate:** Kiro deployment-closeout review. Backend query implementation and cutover will proceed under a separate approval gate.
