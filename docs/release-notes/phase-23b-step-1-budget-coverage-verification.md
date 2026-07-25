# Phase 23B Step 1: Budget Coverage and Cost-Allocation Verification

**Status:** ✅ READ-ONLY VERIFICATION COMPLETE
**Date:** 2026-07-25
**Starting HEAD:** `762fd34`
**Account access:** Management/payer account (default profile: `Terraform_User`)
**Workload account SSO:** Expired (resource-level tagging API unavailable)

---

## 1. Account Context

| Property | Finding |
|----------|---------|
| CLI identity | `Terraform_User` in management/payer account |
| Organization master account | Same as CLI identity account |
| Workload account (linked) | Confirmed member of organization |
| Workload SSO profile | `usmissionhero-website-prod` — token expired |
| Budget location | Workload account (not queryable from management account) |
| Cost Explorer access | ✅ Available from management account (organization-wide) |
| Cost-allocation tag access | ✅ Available from management account |
| Resource tagging API | ❌ Requires workload account SSO (expired) |

**Correction from Phase 23A:** Phase 23A reported the workload account could not access cost-allocation tags. This verification confirms the management/payer account CAN access them — the limitation was the CLI profile used, not an organizational restriction.

---

## 2. Cost-Allocation Tag Status (Authoritative)

### Active User-Defined Tags

| Tag Key | Status | Activated | Last Used |
|---------|--------|-----------|-----------|
| `Client` | ✅ Active | 2026-04-20 | 2026-07-01 |
| `Environment` | ✅ Active | 2026-04-17 | 2026-07-01 |
| `ManagedBy` | ✅ Active | 2026-04-17 | 2026-07-01 |
| `Repo` | ✅ Active | 2026-04-17 | 2026-07-01 |
| `Name` | ✅ Active | 2026-04-17 | 2026-07-01 |
| `Department` | ✅ Active | 2026-04-17 | N/A |
| `Usage` | ✅ Active | 2026-04-17 | 2025-10-01 |

### Active AWS-Generated Tags

| Tag Key | Status | Last Used |
|---------|--------|-----------|
| `aws:createdBy` | ✅ Active | 2026-07-01 |
| `aws:cloudformation:stack-name` | ✅ Active | 2024-12-01 |
| `aws:cloudformation:stack-id` | ✅ Active | 2024-12-01 |
| `aws:cloudformation:logical-id` | ✅ Active | 2024-12-01 |

### Inactive User-Defined Tags

| Tag Key | Status | Last Used |
|---------|--------|-----------|
| `Project` | ⚠️ **Inactive** | 2026-07-01 |
| `BillingModel` | ⚠️ **Inactive** | 2026-07-01 |
| `Application` | ⚠️ **Inactive** | 2026-07-01 |
| `CostCenter` | ⚠️ **Inactive** | 2026-07-01 |
| `Company` | ⚠️ **Inactive** | 2026-07-01 |

### Tags Not Present in Cost-Allocation System

| Tag Key | Status |
|---------|--------|
| `Component` | ❌ Does not exist (never applied to resources) |

### Key Finding

The Budget filter uses `Client=TogAndDogs` which IS active — this confirms the Budget is correctly filtering by an active cost-allocation tag. However, 5 of the 9 standard tag keys are **inactive**, meaning they cannot be used for Cost Explorer grouping or filtering until activated.

---

## 3. Current Month Cost Coverage Analysis

**Period:** 2026-07-01 through 2026-07-24 (estimated)

| Metric | Amount |
|--------|--------|
| Total workload account spend | $6.11 |
| Tagged spend (`Client=TogAndDogs`) | $5.65 |
| Untagged/excluded spend | $0.46 |
| **Coverage ratio** | **92.5%** |
| Full-month forecast (workload account) | ~$7.98 |

### Tagged Spend by Service

| Service | Tagged Cost |
|---------|------------|
| AWS Step Functions | $4.38 |
| AWS Secrets Manager | $1.24 |
| Amazon API Gateway | $0.016 |
| Amazon DynamoDB | $0.006 |
| Amazon S3 | $0.001 |
| Amazon CloudFront | ~$0.00 |
| AWS Lambda | $0.00 |
| Amazon Cognito | $0.00 |
| Amazon SNS | $0.00 |

### Untagged Spend by Service

| Service | Untagged Cost | Likely Source |
|---------|---------------|---------------|
| **AmazonCloudWatch** | **$0.45** | CloudWatch Alarm monitoring (AlarmMonitorUsage) |
| Amazon S3 | $0.008 | Terraform state bucket (untagged) |
| AWS Lambda | ~$0.00 | Negligible |
| AWS Secrets Manager | ~$0.00 | Negligible |
| Amazon CloudFront | ~$0.00 | Negligible |
| AWS Glue | $0.00 | Catalog (no active usage) |
| AWS KMS | $0.00 | Free-tier key usage |

### Critical Finding: CloudWatch Alarm Cost Attribution

The 7 Terraform-managed CloudWatch alarms **are tagged** with `Client=TogAndDogs` (confirmed in Phase 23A via Resource Groups Tagging API). However, their costs appear as **untagged** in Cost Explorer.

**Root cause hypothesis:** CloudWatch metric alarm costs may not propagate resource tags to billing line items in the same way that other services do. The `CW:AlarmMonitorUsage` usage type ($0.45/month) represents the per-alarm monitoring charge. This is a known AWS billing attribution limitation for some service/usage-type combinations — the resource is tagged but the billing dimension does not inherit the tag.

**Impact:** $0.45/month is excluded from the Budget's Client-filtered view despite the alarms being correctly tagged at the resource level. This is **not fixable by tagging** — it would require AWS to support tag-based billing for this usage type, or consolidation into the Budget via an unfiltered approach.

---

## 4. Trailing Month Trend

| Month | Total Account | Client-Tagged | Gap | Coverage |
|-------|---------------|---------------|-----|----------|
| 2026-04 | $1.16 | $0.98 | $0.18 | 84% |
| 2026-05 | $5.95 | $5.80 | $0.15 | 97% |
| 2026-06 | $7.35 | $6.89 | $0.46 | 94% |
| 2026-07 (partial) | $6.11 | $5.65 | $0.46 | 92% |

The gap is consistent at ~$0.46/month, dominated by CloudWatch alarm monitoring costs that don't propagate the resource tag to billing.

---

## 5. Known Untagged Resources Re-evaluation

| Resource | Still Exists | Has Tags | Current Month Cost | In Budget? | Tagging Supported | Remediation |
|----------|-------------|----------|-------------------|------------|-------------------|-------------|
| Terraform state S3 bucket | Yes (inferred from S3 untagged cost) | No | ~$0.008 | ❌ No | Yes (manual) | One-time `aws s3api put-bucket-tagging` |
| Terraform lock DynamoDB table | Yes (inferred) | No | $0.00 | N/A (zero cost) | Yes (manual) | One-time CLI; negligible benefit |
| Lambda-created CloudWatch log groups (12×) | Yes (inferred) | No | ~$0.00 | N/A (within free tier) | Yes (manual or import) | Low priority |
| SES configuration set (v1) | Yes | No | $0.00 | N/A (free) | No (provider limitation) | Accept — zero cost |
| CloudWatch alarms (7×) | Yes | Yes (tagged) | $0.45 | ❌ No (billing limitation) | Tagged but billing doesn't attribute | **Not fixable by tagging** |

**Note:** Resource-level verification (existence, exact tags) requires the workload account SSO session to be refreshed. The cost-level evidence above is authoritative from Cost Explorer.

---

## 6. Budget Coverage Classification

**Classification: SUBSTANTIALLY COMPLETE WITH DOCUMENTED EXCLUSIONS**

The `Client=TogAndDogs` Budget captures **92–97%** of workload-account costs month-over-month. The excluded ~$0.46/month consists of:

1. **CloudWatch alarm monitoring ($0.45)** — resources ARE tagged but AWS billing does not attribute this usage type to resource tags. Not fixable by tagging.
2. **Terraform state S3 bucket ($0.008)** — untagged bootstrap resource. Fixable with one-time manual tagging (requires Matthew approval).
3. **Miscellaneous negligible items** — Lambda invocations, CloudFront requests from untagged sources. Individually < $0.001.

The Budget does NOT include:
- Tax (currently $0.00 in the workload account)
- Credits or refunds (none present)
- AWS Support (not visible in workload-account cost data)
- Marketplace purchases (none present)
- Cross-account shared charges (none identified)

---

## 7. Proposed Cost Explorer Report Configuration

| Setting | Proposed Value |
|---------|---------------|
| Report name | `Togs-and-Dogs-Monthly-Cost-Overview` |
| Date range | Trailing 6 months + current month |
| Granularity | Monthly (with daily drill-down) |
| Metric | Unblended cost |
| Primary filter | Tag: `Client` = `TogAndDogs` |
| Secondary filter | Linked account (workload account) — for untagged comparison |
| Primary group-by | Service |
| Optional group-by | Usage type (for drill-down) |
| Forecast | Include forecast line |
| Unallocated comparison | Compare filtered vs. total account to show exclusion gap |
| Default view | Monthly bar chart grouped by Service |

**Note:** The `Project` tag is inactive and cannot be used as a filter until activated. The `Client` tag is the correct primary filter.

**Amortized vs. unblended:** At this scale (~$7/month), there is no meaningful difference between amortized and unblended cost. No reserved instances, savings plans, or upfront commitments exist. Unblended is the simpler and more appropriate metric.

---

## 8. Budget Design Review (Proposals Only)

| Current | Assessment | Proposal |
|---------|------------|----------|
| $20 monthly limit | Appropriate — spend is $6–8/month, provides 2.5× headroom | No change recommended |
| 80% actual alert ($16) | Very high threshold relative to spend — would only fire if costs doubled | Consider adding 150% alert (relative to prior month average, ~$10) |
| Forecasted-spend alert | Not configured | **Recommend adding** 80% forecasted alert — provides early warning |
| 100% actual alert | Not configured | **Recommend adding** — notifies when $20 limit is breached |
| Single project budget | Appropriate for current scale | No per-service budgets needed at $7/month |
| Alert channel | Email only | Sufficient for Matthew's workflow |

**All changes require explicit Matthew approval.**

---

## 9. Cost-Allocation Tag Activation Recommendations

Five of the nine standard tag keys are inactive. Recommended activation priority:

| Priority | Tag Key | Rationale |
|----------|---------|-----------|
| 1 | `Project` | Enables project-level Cost Explorer filtering (useful for multi-project payer account) |
| 2 | `CostCenter` | Enables billing-model grouping |
| 3 | `Company` | Enables company-level filtering if account hosts multiple companies |
| 4 | `Application` | Lower priority — single application currently |
| 5 | `BillingModel` | Lower priority — single billing model currently |

**Activation is a payer-account-only operation. It does NOT change resource tags, budgets, or costs. It only makes the tag keys available for Cost Explorer filtering and grouping. Once activated, historical data from the activation date forward becomes filterable.**

---

## 10. Payer-Account Manual Verification Checklist

For Matthew or the payer administrator to verify/activate cost-allocation tags:

### Steps

1. **Sign in** to the AWS Management Console using the management/payer account credentials
2. **Navigate** to Billing and Cost Management → Cost Allocation Tags
3. **Locate the "User-defined cost allocation tags" tab**
4. **Verify current status** matches this document:
   - `Client`: Active ✅
   - `Environment`: Active ✅
   - `ManagedBy`: Active ✅
   - `Repo`: Active ✅
   - `Project`: Inactive ⚠️
   - `BillingModel`: Inactive ⚠️
   - `Application`: Inactive ⚠️
   - `CostCenter`: Inactive ⚠️
   - `Company`: Inactive ⚠️
5. **To activate** (only if approved): Select the inactive tag keys → Click "Activate"
6. **Verify** that no other tags are accidentally activated or deactivated
7. **Note:** Activation takes up to 24 hours to appear in Cost Explorer. Historical data from before activation will NOT be retroactively tagged.

### Safety Guidance

- Activating a tag key is non-destructive — it adds visibility, does not change resources
- Deactivating a tag key removes it from Cost Explorer — avoid doing this for `Client`
- Do not modify the "AWS-generated cost allocation tags" section
- No credentials, MFA codes, or account IDs need to be shared back
- Confirm only: which tags were activated and the date

---

## 11. What Remains Unknown

| Item | Reason | Resolution |
|------|--------|------------|
| Whether CloudWatch alarm billing can ever be attributed by resource tag | AWS billing limitation | Accept or file AWS support case |
| Exact tag state of bootstrap S3 bucket and DynamoDB lock table | Workload SSO expired | Refresh SSO session for resource-level verification |
| Whether tax charges will eventually appear | Currently $0.00 | Monitor monthly |
| Whether AWS Support charges appear in this account | Not visible in current data | Confirm billing structure |
| Lambda log group existence and count | Workload SSO expired | Refresh SSO for `logs describe-log-groups` |

---

## 12. Approval Gates for Next Steps

| Action | Required Approval |
|--------|-------------------|
| Activate `Project`, `CostCenter`, `Company`, `Application`, `BillingModel` tags | Matthew + payer admin |
| Add 100% actual-spend and 80% forecasted-spend budget alerts | Matthew |
| Create Cost Explorer saved report | Matthew |
| Tag Terraform state S3 bucket | Matthew |
| Tag Terraform lock DynamoDB table | Matthew |
| Tag Lambda-created CloudWatch log groups | Matthew |
| Refresh workload SSO for resource-level re-verification | Matthew (routine) |

---

## 13. Next Recommended Bounded Task

**Phase 23B Step 2: Cost-allocation tag activation and Budget alert enhancement**

Scope (requires Matthew approval):
1. Activate the 5 inactive user-defined tag keys from the payer account
2. Add a 100% actual-spend alert to the existing budget
3. Add an 80% forecasted-spend alert to the existing budget
4. Create the proposed Cost Explorer saved report
5. Tag the Terraform state S3 bucket (`Client=TogAndDogs` + full standard)
6. Document results

Each item can be approved individually or as a batch.

---

## 14. Queries Executed (Audit Trail)

| # | Command Purpose | Scope | Mutating |
|---|----------------|-------|----------|
| 1 | Identify caller account and org role | STS + Organizations | No |
| 2 | List active cost-allocation tags | Cost Explorer | No |
| 3 | List inactive cost-allocation tags | Cost Explorer | No |
| 4 | Check `Component` tag existence | Cost Explorer | No |
| 5 | Query Client-tagged spend (July) | Cost Explorer | No |
| 6 | Query total workload-account spend (July) | Cost Explorer | No |
| 7 | Query tagged spend by service | Cost Explorer | No |
| 8 | Query total spend by service | Cost Explorer | No |
| 9 | Query untagged spend by service | Cost Explorer | No |
| 10 | Query untagged CloudWatch by usage type | Cost Explorer | No |
| 11 | Verify CloudWatch tagged cost (confirms $0) | Cost Explorer | No |
| 12 | Query untagged S3 by usage type | Cost Explorer | No |
| 13 | Query trailing 6-month total spend trend | Cost Explorer | No |
| 14 | Query trailing 6-month tagged spend trend | Cost Explorer | No |
| 15 | Query full-month cost forecast | Cost Explorer | No |
| 16 | Query `Client` tag values in billing | Cost Explorer | No |

All queries read-only. No budget, tag, resource, or billing configuration was modified.
