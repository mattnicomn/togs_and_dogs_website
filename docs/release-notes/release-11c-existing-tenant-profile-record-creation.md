# Release 11C — Existing Tenant Profile Record Creation

**Status:** ⏳ Gate A Validation Complete — Blocker Identified (Pending Decision)  
**Date:** 2026-06-12  
**Scope:** Read-only database check and verification of tenant record properties  

---

## Gate A — Read-Only Validation Results

### 1. Confirm Tenant Record Existence
*   **Command:**
    ```bash
    aws dynamodb get-item \
      --table-name togs-and-dogs-prod-data \
      --key '{"PK": {"S": "TENANT#tog_and_dogs"}, "SK": {"S": "METADATA"}}' \
      --profile usmissionhero-website-prod
    ```
*   **Result:** ✅ **Pass** (No existing record found; stdout was empty. Seeding this record will not overwrite any existing data.)

### 2. Confirm Existing Records consistently use `company_id = tog_and_dogs`
*   **Command:**
    ```bash
    aws dynamodb scan \
      --table-name togs-and-dogs-prod-data \
      --filter-expression "begins_with(PK, :prefix)" \
      --expression-attribute-values '{":prefix": {"S": "COMPANY#tog_and_dogs"}}' \
      --select COUNT \
      --profile usmissionhero-website-prod
    ```
*   **Result:** ✅ **Pass** (Found 6 existing staff and client records, all of which use `company_id: "tog_and_dogs"`.)

### 3. Verify Owner/Admin User Reference Consistency
*   **Command:**
    ```bash
    aws dynamodb scan \
      --table-name togs-and-dogs-prod-data \
      --filter-expression "begins_with(PK, :prefix)" \
      --expression-attribute-values '{":prefix": {"S": "COMPANY#tog_and_dogs"}}' \
      --profile usmissionhero-website-prod
    ```
*   **Result:** ❌ **Blocker Identified**
    
    A mismatch was found between the proposed owner fields and the actual user records stored in production DynamoDB:
    
    *   **Proposed Plan properties:**
        *   `owner_email`: `mattnicomn10@gmail.com`
        *   `owner_cognito_sub`: `74b86488-1011-7029-bb6d-dad984e1463c`
    *   **Production Database Truth:**
        *   The Cognito sub `74b86488-1011-7029-bb6d-dad984e1463c` belongs to **`admin@toganddogs.com`** (`Admin_Root`), which is the hardcoded system protected admin sub.
        *   The email **`mattnicomn10@gmail.com`** (`Matthew Nico` admin account) actually has Cognito sub **`b4a89428-9071-7063-dcad-983d4305dd8c`**.

#### Risk of Proceeding with Mismatch
If we seed the record with the mismatched combination, future tenant verification logic comparing a user's Cognito sub (e.g., Matthew Nico's `b4a89428-9071-7063-dcad-983d4305dd8c`) against the tenant owner's sub (`74b86488-1011-7029-bb6d-dad984e1463c`) will fail.

---

## Recommended Options for Gate B

Before Matthew approves Gate B (write), we must align on one of the following two options:

### Option 1: Set Matthew Nico as the Tenant Owner
*   **Owner Email:** `mattnicomn10@gmail.com`
*   **Owner Cognito Sub:** `b4a89428-9071-7063-dcad-983d4305dd8c`

### Option 2: Set Admin_Root as the Tenant Owner
*   **Owner Email:** `admin@toganddogs.com`
*   **Owner Cognito Sub:** `74b86488-1011-7029-bb6d-dad984e1463c`

---

## Guardrail Confirmations

| Guardrail | Status |
|-----------|--------|
| No DynamoDB writes performed | ✅ Confirmed |
| No app code changes made | ✅ Confirmed |
| No AWS/Terraform infrastructure changes made | ✅ Confirmed |
| No Cognito changes made | ✅ Confirmed |
| No Postmark/Google Calendar changes made | ✅ Confirmed |
| No EAS build/submit executed | ✅ Confirmed |
| No App Store Connect/TestFlight changes made | ✅ Confirmed |
| No production deployment executed | ✅ Confirmed |
