# Release Notes: Phase 1B.2A — ClientPetIndex Terraform Plan

> **⚠️ CORRECTION (Kiro Review):** This plan is **NOT apply-ready**. It contains 13 unrelated Lambda code-package updates alongside the intended DynamoDB GSI change. See `phase-1b2a-client-pet-index-plan-scope-mismatch-review.md` for the full assessment. A separate backend deployment must occur first, followed by a new clean plan containing only the GSI change.

## 1. Executive Summary
This release implements the Terraform configuration for the `ClientPetIndex` Global Secondary Index (GSI) on the primary DynamoDB table. We generated a saved production plan (`phase-1b2a-client-pet-index.tfplan`), validated formatting and structure, and reviewed all changes.

No resource replacements or destructions appear in the plan. All changes are in-place. No `terraform apply` has occurred.

---

## 2. Infrastructure Context & Resource Address

- **AWS Account:** `358604342897`
- **AWS Profile:** `usmissionhero-website-prod`
- **Region:** `us-east-1`
- **Terraform Directory:** `infra/prod`
- **Terraform File Changed:** `modules/data/main.tf`
- **Target Resource Address:** `module.data.aws_dynamodb_table.main`
- **Production Table:** `togs-and-dogs-prod-data`
- **Billing Mode:** `PAY_PER_REQUEST` (On-Demand)

---

## 3. GSI Configuration Details

```terraform
# Added to module.data.aws_dynamodb_table.main in modules/data/main.tf
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

- **Projection Type:** `ALL` remains intentional as the existing client pets endpoint returns complete PET items, and future workflows access multiple fields.
- **Capacity:** No provisioned read/write capacity or autoscaling was added.

---

## 4. Plan Summary & Results

- **Saved Plan Filename:** `phase-1b2a-client-pet-index.tfplan`
- **Local Path:** `infra/prod/phase-1b2a-client-pet-index.tfplan`
- **Plan Checksum (SHA256):** `19322ADF7ACBA4F22AB66128E971B74F0F73AA370076FC08C58484D58971F5EF`
- **Plan Totals:** `0 to add, 14 to change, 0 to destroy`

### Resources in Plan
1. **`module.data.aws_dynamodb_table.main`** — In-place update to add key attributes and the `ClientPetIndex` GSI.
2. **13 Lambda Functions** (`aws_lambda_function.admin`, `aws_lambda_function.assign`, etc.) — In-place updates to `source_code_hash` due to the previous local commit (`ca73d93` — "fix(backend): default new pets to active") which modified the backend code folder.

### Excluded from Plan
- ❌ DynamoDB table replacement (confirmed in-place only)
- ❌ Deletion of existing indexes (`StatusIndex` and `WorkerIndex` are preserved)
- ❌ Cognito schema or group changes
- ❌ API Gateway method or route deployment modifications
- ❌ IAM role or policy changes
- ❌ S3, CloudFront, Stripe, or Google Calendar resources
- ❌ Tenant metadata modifications

---

## 5. Rollout & GSI Participation Characteristics

- **Online Update:** Creating the GSI is an in-place DynamoDB table update. No table downtime or replacement is required.
- **Backfill:** DynamoDB automatically backfills eligible records. Only items containing both a scalar `client_id` and `pet_id` enter the index.
- **Index Participation Expectations (derived from the aggregate dry run):**
  - **68 records** are expected to enter the index and be immediately defensible by company_id checks.
  - **13 records** (with client ownership missing company_id) will enter the index but will be excluded by backend tenant-isolation checks (post-query company_id validation).
  - **3 records** (missing one or both keys) will not participate in the index.
- **Consistency:** GSI queries are eventually consistent.
- **Scan Fallback:** In future backend updates, fallback Scans will be strictly forbidden.
- **No Query Operations:** No backend or application query can be made against the index until the GSI status reports `ACTIVE`.

---

## 6. Next Steps
- **Next Gate:** Kiro review of this saved plan.
- **Remediation apply:** Remains deferred.
- **Apply Action:** Requires separate, explicit approval from Matthew.
