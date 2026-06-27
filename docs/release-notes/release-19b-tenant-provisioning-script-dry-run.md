# Release 19B: Tenant Provisioning Script Dry Run

**Status:** Completed (Dry Run Only)  
**Type:** Verification & Backlog Readiness  
**Date:** 2026-06-26  

---

## 1. Goal

The goal of this release was to run the tenant provisioning script (`scripts/provision_tenant.py`) in dry-run/no-write mode using the approved test tenant pattern. This dry run verifies the CLI syntax, validation rules, proposed metadata shape, Cognito placeholder instructions, and rollback/disable guidance.

No second tenant was created, and no database or AWS writes occurred.

---

## 2. CLI Options & Verification

### A. CLI Syntax and Options
- **CLI Script:** `scripts/provision_tenant.py`
- **Options used:**
  - `--company-id test_tenant_alpha`: Sets the unique company identifier slug.
  - `--display-name "Test Tenant Alpha"`: Sets the human-readable business name.
  - `--tier starter`: Sets the subscription tier limits.
  - `--status active`: Sets the initial subscription status.
  - `--notes "Internal dry-run validation only. Do not create without Matthew approval."`: Seed notes.
- **Safety Guards Configured:**
  - Running without `--apply` and `--confirm-apply` defaults to a safe **DRY-RUN** mode. No AWS/boto3 queries are executed.
  - Added ASCII characters (`->` and `-`) to print statements in `scripts/provision_tenant.py` to prevent Windows encoding errors (`UnicodeEncodeError` on `\u2192` and em-dash) when executing in Windows console environments.

---

## 3. Dry-Run Outputs Analysis

### A. Proposed Tenant Metadata Record
```json
{
  "PK": "TENANT#test_tenant_alpha",
  "SK": "METADATA",
  "company_id": "test_tenant_alpha",
  "display_name": "Test Tenant Alpha",
  "entity_type": "TENANT",
  "subscription_tier": "starter",
  "subscription_status": "active",
  "limits": {
    "max_active_clients": 20,
    "max_staff": 1,
    "max_monthly_notifications": 100,
    "max_monthly_bookings": 50,
    "google_calendar_enabled": false,
    "export_enabled": false,
    "custom_branding_enabled": false,
    "video_evidence_enabled": false
  },
  "is_active": true,
  "notes": "Internal dry-run validation only. Do not create without Matthew approval.",
  "created_at": "2026-06-27T02:01:18Z",
  "updated_at": "2026-06-27T02:01:18Z",
  "created_by": "platform_admin:system",
  "updated_by": "platform_admin:system"
}
```

### B. Proposed Platform Audit Record
```json
{
  "PK": "PLATFORM_AUDIT",
  "SK": "ACTION#2026-06-27T02:01:18Z#16c7189d-4e3b-4d6b-91db-3a97aa2ca6f1",
  "entity_type": "PLATFORM_AUDIT",
  "action": "PROVISION_TENANT",
  "target_company_id": "test_tenant_alpha",
  "changed_fields": [
    "company_id",
    "display_name",
    "subscription_tier",
    "subscription_status",
    "limits",
    "notes"
  ],
  "old_values": {},
  "new_values": {
    "company_id": "test_tenant_alpha",
    "display_name": "Test Tenant Alpha",
    "subscription_tier": "starter",
    "subscription_status": "active"
  },
  "actor": "platform_admin:system",
  "timestamp": "2026-06-27T02:01:18Z"
}
```

### C. Cognito CLI Command Templates Generated
*   **Step 1:** Create owner Cognito user with `custom:company_id = test_tenant_alpha`.
*   **Step 2:** Add owner user to the `owner` group (grants full tenant-level access for `company_id = test_tenant_alpha`).
*   **Role Rule:** Clear warning that `platform_admin` group is reserved for operator accounts only and must not be assigned to tenant owners.

### D. Rollback / Disable Guidance
*   Preference is to set `subscription_status` to `"disabled"` or `"canceled"` in the platform admin interface instead of deleting database records to maintain a clean audit history.

---

## 4. Post-Execution Safety Verification

*   **Database Writes:** Confirmed **0 records** written. The tenant metadata record `TENANT#test_tenant_alpha` and audit records do not exist in the production DynamoDB table.
*   **Tenant Count:** Confirmed **1 tenant** remains in the database (`tog_and_dogs` only).
*   **Cognito Users:** Confirmed **0 new users** created. All 5 active Cognito users remain correctly scoped to the `tog_and_dogs` tenant.
*   **Integrations:** No Google Calendar, Stripe, Postmark, email, or mobile app changes occurred.

---

## 5. Next Release Recommendation

It is recommended to proceed with **Release 19C** (Second-Tenant Provisioning Execution) to provision the first test tenant in the production database (writes enabled) after obtaining Matthew's gate approval.
