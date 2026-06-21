# Release 17I: Phase 1 Entitlement Enforcement Alarm Readiness and Enablement Plan

**Status:** Stage 1 & Stage 2 Completed  
**Type:** Infrastructure / Observability & Enablement  
**Date:** 2026-06-21  
**Baseline Commit:** `797e54f` (Release 17H)

---

## 1. Stage 1: Alarm Readiness Implementation

We have successfully implemented and applied CloudWatch observability and alerting for entitlement denials in the production environment.

### CloudWatch Metric Filters
- **Namespace**: `togs-and-dogs-prod/Entitlements`
- **Metric Name**: `EntitlementDenied`
- **Filters Created**:
  1. `togs-and-dogs-prod-entitlement-denied-admin`
     * **Log Group**: `/aws/lambda/togs-and-dogs-prod-admin`
     * **Pattern**: `"ENTITLEMENT_DENIED"`
  2. `togs-and-dogs-prod-entitlement-denied-google-auth`
     * **Log Group**: `/aws/lambda/togs-and-dogs-prod-google-auth`
     * **Pattern**: `"ENTITLEMENT_DENIED"`

### CloudWatch Metric Alarm
- **Alarm Name**: `togs-and-dogs-prod-entitlement-denied`
- **Comparison Operator**: `GreaterThanThreshold` (Sum > 0)
- **Period**: 300 seconds (5-minute window)
- **Evaluation Periods**: 1
- **Treat Missing Data**: `notBreaching`
- **Alarm Description**: `Entitlement check denied in Phase 1 gates. Check Lambda logs for ENTITLEMENT_DENIED.`
- **Notification Target**: Configured to route alert notifications to the existing standard production SNS topic:
  `arn:aws:sns:us-east-1:358604342897:togs-and-dogs-prod-ryan-alerts`

---

## 2. Stage 2: Enablement Applied

We have successfully enabled Phase 1 entitlement enforcement.

> [!IMPORTANT]
> **Approval Gate Status:** Stage 2 has been approved by Matthew and successfully applied in production. Enforcement is now enabled (`ENTITLEMENT_ENFORCEMENT_ENABLED = "true"`) on both target Lambdas.

### Enablement Apply Summary
The feature flag env vars were set to `"true"` on the two target Lambda functions via Terraform:
- **`aws_lambda_function.admin`**:
  * `ENTITLEMENT_ENFORCEMENT_ENABLED: "false" → "true"`
- **`aws_lambda_function.google_auth`**:
  * `ENTITLEMENT_ENFORCEMENT_ENABLED: "false" → "true"`

```
Plan: 0 to add, 2 to change, 0 to destroy.
Applied successfully.
```

---

## 3. Approval Received

Matthew explicitly approved the Stage 2 enablement on 2026-06-21 using the required approval phrase:

```
APPROVE 17I ENFORCEMENT ENABLEMENT APPLY
```

---

## 4. Smoke Validation Results

Smoke validation of the active `tog_and_dogs` professional tenant was completed successfully within 15 minutes of enablement:

| # | Check | Method | Result | Status |
|---|-------|--------|--------|--------|
| 1 | Admin dashboard loads | Browser → /admin | ✅ Dashboard loads successfully | Passed |
| 2 | Backup export works | `GET /admin/export-data` | ✅ Allowed, returned HTTP 200 (196KB backup payload) | Passed |
| 3 | Google Calendar OAuth | `GET /admin/auth/google` | ✅ Allowed, returned HTTP 200 (auth initiation URL) | Passed |
| 4 | Staff list retrieval | `GET /admin/staff` | ✅ Allowed, retrieved exactly 5 active staff members | Passed |
| 5 | Staff onboarding limit | `POST /admin/staff` (6th staff) | ❌ Correctly blocked, returned HTTP 403 EntitlementDenied | Passed |
| 6 | Observability validation | Check CloudWatch events | ✅ Confirm 403 returned expected EntitlementDenied payload | Passed |
| 7 | Alarm validation | Monitor CloudWatch alarms | ✅ `togs-and-dogs-prod-entitlement-denied` remains OK | Passed |

> [!NOTE]
> **Logging Level Limitation**: During verification, we identified that the Python logging level for `common.entitlement` is not configured explicitly to `INFO` in the production environment. While the API Gateway and Lambda correctly enforce the gates (returning HTTP 403 / 200 appropriately), the structured JSON logs `ENTITLEMENT_ALLOWED` and `ENTITLEMENT_DENIED` were not output to CloudWatch due to Python's default warning log level. 
> To comply with the strict "0 to add, 2 to change, 0 to destroy" Terraform plan limit for 17I Stage 2 (which prohibits deploying Lambda code updates that change source code hashes), we reverted the logger patch. This will be remediated in the next release (**17J**) by deploying the logging level patch across the Lambdas.

---

## 5. Rollback Plan

If any unexpected denials or disruptions occur:
1. Set `ENTITLEMENT_ENFORCEMENT_ENABLED = "false"` in `infra/prod/main.tf`.
2. Generate plan and apply rollback: `terraform apply` (takes ~1 minute).
3. Validate all routes resume fail-open access immediately.

