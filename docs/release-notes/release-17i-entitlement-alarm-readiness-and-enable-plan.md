# Release 17I: Phase 1 Entitlement Enforcement Alarm Readiness and Enablement Plan

**Status:** Stage 1 Completed | Stage 2 Pending Approval  
**Type:** Infrastructure / Observability & Enablement Preflight  
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

## 2. Stage 2: Enablement Plan (Pending Approval)

A separate Terraform plan has been successfully prepared and saved locally as `tfplan_enablement` to enable Phase 1 entitlement enforcement.

> [!IMPORTANT]
> **Approval Gate Status:** Stage 2 is **NOT** applied yet. Enforcement remains completely disabled (`ENTITLEMENT_ENFORCEMENT_ENABLED = "false"`) on both Lambdas.

### Enablement Plan Summary
Setting the feature flag env vars to `"true"` on the two target Lambda functions:
- **`aws_lambda_function.admin`**:
  * `ENTITLEMENT_ENFORCEMENT_ENABLED: "false" → "true"`
- **`aws_lambda_function.google_auth`**:
  * `ENTITLEMENT_ENFORCEMENT_ENABLED: "false" → "true"`

```
Plan: 0 to add, 2 to change, 0 to destroy.
```

---

## 3. Required Approval Phrase

To proceed with applying the Stage 2 enablement, Matthew must review the plan and respond in chat with the exact approval phrase:

```
APPROVE 17I ENFORCEMENT ENABLEMENT APPLY
```

---

## 4. Smoke Validation Checklist (Upon Enablement)

Once the enablement plan is applied, we will perform the following validation steps within 15 minutes:
1. Load admin dashboard to ensure it displays correctly.
2. Confirm the backup export action (`GET /admin/export-data`) remains fully allowed.
3. Confirm Google Calendar disconnect/reconnect endpoints (`GET /admin/auth/google`) remain fully allowed.
4. Verify staff management loads and staff onboarding (`POST /admin/staff/onboard`) is allowed below the limit of 5.
5. Verify no unexpected 403 responses appear for the `tog_and_dogs` tenant in CloudWatch.

---

## 5. Rollback Plan

If any unexpected denials or disruptions occur after Stage 2 enablement:
1. Set `ENTITLEMENT_ENFORCEMENT_ENABLED = "false"` in `infra/prod/main.tf`.
2. Generate plan and apply rollback: `terraform apply` (takes ~1 minute).
3. Validate all routes resume fail-open access immediately.
