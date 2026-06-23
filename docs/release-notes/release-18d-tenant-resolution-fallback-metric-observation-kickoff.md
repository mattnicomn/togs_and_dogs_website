# Release 18D: Tenant Resolution Fallback Metric Observation Period Kickoff

**Status:** ⏳ In Progress (Observation Phase)  
**Type:** Observability / Operations  
**Date:** 2026-06-23  
**Baseline:** Release 18C (`5e638aa`)

---

## 1. Context & Purpose

Release 18B successfully added the `custom:company_id` custom attribute schema field to the Cognito user pool. Release 18C completed the manual audit and backfill of all current Cognito users in production to assign them `custom:company_id = tog_and_dogs`.

Before strict `multi` tenant resolution mode can be safely enabled (`TENANT_RESOLUTION_MODE=multi`), we must verify that all active application pathways are correctly passing the company ID from the Cognito JWT token. If any pathway uses an unbackfilled user, or fails to pass the attribute, it will emit a fallback metric event.

Release 18D establishes a 7+ day read-only observation period to monitor these metrics under normal usage.

---

## 2. Observation Window Details

- **Start Date/Time:** June 23, 2026, 11:20 AM EDT (15:20 UTC)
- **Target Duration:** 7+ days (Minimum observation runs through June 30, 2026, 11:20 AM EDT)
- **Success Criteria:**
  - **Zero** `TENANT_RESOLUTION_FALLBACK` occurrences in CloudWatch metrics.
  - **Zero** `TENANT_RESOLUTION_FAILED` occurrences in CloudWatch metrics.
  - **Zero** user access or login regressions reported by Matthew.

---

## 3. Pre-Observation Read-Only Alarm Verification

Prior to the start of the observation period, a read-only check of the CloudWatch Alarms and metrics was performed:

- **Alarms Verified:**
  - `togs-and-dogs-prod-tenant-resolution-fallback` — **OK State**
  - `togs-and-dogs-prod-tenant-resolution-failed` — **OK State**
- **Recent Telemetry:**
  - Queried CloudWatch metrics for both `TenantResolutionFallback` and `TenantResolutionFailed` in the namespace `togs-and-dogs-prod/TenantResolution` over the past 40 hours.
  - **Result:** **0 occurrences** (no events logged since the backfill).

---

## 4. Guidelines During Observation Window

To maintain safety and ensure clean test conditions, the following guardrails must be strictly adhered to during this period:

- **Matthew:** Use the Operations Portal normally.
- **Do NOT:**
  - Do not toggle or enable `TENANT_RESOLUTION_MODE=multi`.
  - Do not create a second tenant.
  - Do not create new Cognito users or groups unless separately approved.
  - Do not modify or reset any user passwords, groups, or attributes.
  - Do not run `scripts/provision_tenant.py` in apply mode.
  - Do not manually write to DynamoDB tables.
  - Do not perform any Lambda or frontend/mobile deployments.
  - Do not change any Stripe/Postmark settings or credentials.

---

## 5. Daily Monitoring SOP (For Matthew / Support)

Monitor the status of tenant resolution daily during the quick-check routine:

1. **Verify Alarm States:** Confirm `togs-and-dogs-prod-tenant-resolution-fallback` remains in the **OK** state.
2. **Review Metrics / Logs:** Check CloudWatch logs for `/aws/lambda/togs-and-dogs-prod-*` for the string `TENANT_RESOLUTION_FALLBACK`.
3. **If a Fallback Occurs:**
   - Immediately pause the strict-mode roadmap.
   - Investigate the logs to locate the specific AWS request ID and Lambda function triggering the fallback.
   - Trace the user account or JWT claims associated with that request to find the unbackfilled flow.

---

## 6. Next Recommended Release

**Release 18E: Strict Mode Enablement Gate Review**
- Scheduled after June 30, 2026 (pending zero metric alerts).
- Confirm zero fallback events occurred during the 7-day period.
- Obtain explicit approval from Matthew to proceed to strict `multi` mode deployment.
