# Release 17J: Entitlement Structured Logging Remediation — Closeout

**Status:** Completed  
**Type:** Observability / Hotfix  
**Date:** 2026-06-21  
**Baseline Commit:** `2aca1edce2b1b7f8f07a090c82e0fda119a472cc` (Release 17I Stage 2)

---

## 1. Summary of Changes

We resolved the logging level issue that was preventing entitlement structured log events from propagating to CloudWatch.

### Backend Changes
- **[entitlement.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/common/entitlement.py):**
  - Configured root logging level and module logging level to `INFO` for the AWS Lambda environment:
    ```python
    logging.getLogger().setLevel(logging.INFO)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    ```

### Infrastructure Changes (Terraform)
- **Lambda Code Deployment:** Ran `terraform apply` to package and upload the updated backend code containing the logging configuration to all 12 production Lambda functions. No infrastructure variables, roles, or environment settings were modified.

---

## 2. Smoke & Observability Validation

### Safe Allowed-Route Verifications
1. **Backup Export (`GET /admin/export-data`):**
   - **Status:** HTTP 200 OK.
   - **Logs:** Confirmed structured logs emitted:
     ```json
     {"event": "ENTITLEMENT_ALLOWED", "company_id": "tog_and_dogs", "check_type": "subscription", "subscription_tier": "professional", "subscription_status": "active", "enforcement_enabled": true, "allowed": true, "reason": "Subscription check allowed in sandbox mode", "protected_admin_bypass": false}
     {"event": "ENTITLEMENT_ALLOWED", "company_id": "tog_and_dogs", "check_type": "feature", "subscription_tier": "professional", "subscription_status": "active", "enforcement_enabled": true, "allowed": true, "reason": "Feature is enabled", "protected_admin_bypass": false, "feature_key": "export_enabled"}
     ```

2. **Google OAuth Initiation (`GET /admin/auth/google`):**
   - **Status:** HTTP 200 OK.
   - **Logs:** Confirmed structured logs emitted:
     ```json
     {"event": "ENTITLEMENT_ALLOWED", "company_id": "tog_and_dogs", "check_type": "subscription", "subscription_tier": "professional", "subscription_status": "active", "enforcement_enabled": true, "allowed": true, "reason": "Subscription check allowed in sandbox mode", "protected_admin_bypass": false}
     {"event": "ENTITLEMENT_ALLOWED", "company_id": "tog_and_dogs", "check_type": "feature", "subscription_tier": "professional", "subscription_status": "active", "enforcement_enabled": true, "allowed": true, "reason": "Feature is enabled", "protected_admin_bypass": false, "feature_key": "google_calendar_enabled"}
     ```

3. **Staff List (`GET /admin/staff`):**
   - **Status:** HTTP 200 OK. Confirmed exactly 5 active staff members exist.

### Intentional Denied-Route Verification
1. **Staff Onboarding Limit (`POST /admin/staff`):**
   - **Payload:** Attempted to onboard a 6th staff member to the professional tenant (limit is 5).
   - **Status:** HTTP 403 Forbidden with:
     ```json
     {"error": "EntitlementDenied", "message": "Limit reached (5/5). Upgrade for more capacity.", "limit": "max_staff", "upgrade_hint": "upgrade"}
     ```
   - **Verification:** Verified that no staff record was created in the database.
   - **Logs:** Confirmed structured denial log emitted:
     ```json
     {"event": "ENTITLEMENT_DENIED", "company_id": "tog_and_dogs", "check_type": "limit", "subscription_tier": "professional", "subscription_status": "active", "enforcement_enabled": true, "allowed": false, "reason": "Limit reached (5/5). Upgrade for more capacity.", "protected_admin_bypass": false, "limit_key": "max_staff", "current_count": 5, "max_allowed": 5}
     ```

---

## 3. Alarm Status
- Metric filter `togs-and-dogs-prod-entitlement-denied-admin` successfully matched the pattern `"ENTITLEMENT_DENIED"` from the intentional denial test.
- CloudWatch Alarm `togs-and-dogs-prod-entitlement-denied` transitioned correctly, verifying end-to-end alerting pipeline.

---

## 4. Next Release
- **Release 17K:** Second-tenant denied-path dry-run planning.
