# Phase 23B Steps 2A–2C: Cost Visibility Dashboard and Budget Alerts

**Status:** ✅ IMPLEMENTATION COMPLETE
**Date:** 2026-07-26
**Starting HEAD:** `7aff6c8`

---

## 1. Summary of Changes

| Step | Action | Result |
|------|--------|--------|
| 2A | Activate 5 inactive cost-allocation tags | ✅ All 5 activated |
| 2B | Cost Explorer saved report | ⚠️ Manual console step required (CLI unsupported) |
| 2C | Add budget alerts | ✅ 2 new alerts added |

---

## 2. Step 2A: Cost-Allocation Tag Activation

### Pre-Change State (verified before mutation)

| Tag Key | Status Before | Status After | Activation Timestamp |
|---------|--------------|--------------|---------------------|
| `Client` | Active | Active (unchanged) | 2026-04-20T18:21:04Z |
| `Environment` | Active | Active (unchanged) | 2026-04-17T15:45:11Z |
| `ManagedBy` | Active | Active (unchanged) | 2026-04-17T15:45:11Z |
| `Repo` | Active | Active (unchanged) | 2026-04-17T15:45:11Z |
| `Project` | **Inactive** | **Active** | 2026-07-26T01:49:53Z |
| `Application` | **Inactive** | **Active** | 2026-07-26T01:49:53Z |
| `CostCenter` | **Inactive** | **Active** | 2026-07-26T01:49:53Z |
| `Company` | **Inactive** | **Active** | 2026-07-26T01:49:53Z |
| `BillingModel` | **Inactive** | **Active** | 2026-07-26T01:49:53Z |
| `Component` | Not present | Not present (not activated — never applied to resources) | N/A |

### Tags Intentionally NOT Activated

| Tag Key | Reason |
|---------|--------|
| `Component` | Does not exist on any resource; cannot be activated |
| `Name` | Already active; not a project-standard tag |
| `Department` | Already active; not a project-standard tag |
| `Usage` | Already active; not a project-standard tag |

### Processing Note

Cost-allocation tag activation takes up to 24 hours to appear in Cost Explorer queries. Historical cost data from before activation will NOT be retroactively associated with the newly activated tags. Cost data for `Project`, `Application`, `CostCenter`, `Company`, and `BillingModel` will begin appearing from 2026-07-26 forward.

**Verification query:** `Project=TogsAndDogs` currently returns $0.00 — this is expected due to the processing delay. It should show data within 24–48 hours.

---

## 3. Step 2B: Cost Explorer Report

### CLI Support

AWS Cost Explorer **does not provide a CLI or API method** to create saved views/reports. Saved reports are a console-only feature. The `aws ce` API supports querying cost data but not creating or managing saved views.

### Proposed Report Configuration

| Setting | Value |
|---------|-------|
| Report name | `Togs-and-Dogs-Monthly-Cost-Overview` |
| Metric | Unblended cost |
| Primary filter | Tag: `Client` = `TogAndDogs` |
| Confirmation filter (future) | Tag: `Project` = `TogsAndDogs` (once data appears) |
| Default date view | Current month |
| Secondary view | Trailing 6 months |
| Granularity | Monthly (daily drill-down available) |
| Primary group-by | Service |
| Optional group-by | Environment |
| Forecast | Enabled |

### Manual Console Steps for Matthew

1. Sign in to the AWS Management Console (management/payer account)
2. Navigate to **Billing and Cost Management → Cost Explorer**
3. Set date range to **Last 6 months**
4. Set granularity to **Monthly**
5. Under Filters, add: **Tag → Client → TogAndDogs**
6. Under Group by, select: **Service**
7. Click **Save as new report**
8. Name: `Togs-and-Dogs-Monthly-Cost-Overview`
9. Save

### Unallocated Cost Comparison Method

To compare total workload-account spend with Client-tagged spend:

1. Open Cost Explorer with filter: **Linked Account = [workload account]**
2. Note the total
3. Add filter: **Tag → Client → TogAndDogs**
4. Compare — the difference is unallocated/untagged cost

---

## 4. Step 2C: Budget Alerts

### Pre-Change Alert State

| # | Type | Threshold | State |
|---|------|-----------|-------|
| 1 | ACTUAL | 80% | OK |

### Post-Change Alert State (verified)

| # | Type | Threshold | State | Change |
|---|------|-----------|-------|--------|
| 1 | ACTUAL | 80% | OK | Unchanged (preserved) |
| 2 | FORECASTED | 80% | OK | **NEW** |
| 3 | ACTUAL | 100% | OK | **NEW** |

### Budget Configuration (confirmed unchanged)

| Property | Value |
|----------|-------|
| Budget name | `togs-and-dogs-prod-monthly-budget` |
| Monthly limit | $20.00 USD |
| Cost filter | `TagKeyValue = Client$TogAndDogs` |
| Alert subscribers | [redacted] (1 email subscriber, unchanged) |

### Alert Behavior

- **80% actual** ($16): Fires when actual spend exceeds $16. Currently OK.
- **80% forecasted** ($16): Fires when forecasted end-of-month spend exceeds $16. Currently OK.
- **100% actual** ($20): Fires when actual spend reaches or exceeds $20. Currently OK.

---

## 5. Cost-Coverage Validation

### Current Spend (July 2026, through 7/25)

| Metric | Amount |
|--------|--------|
| Total workload account | $6.28 |
| Client-tagged spend | $5.81 |
| Unallocated | $0.47 |
| Coverage | **92.5%** |
| Budget actual spend | $5.81 |
| Budget forecasted spend | $7.33 |

### Known Exclusions (unchanged from Step 1)

| Source | Monthly Cost | Reason |
|--------|-------------|--------|
| CloudWatch alarm monitoring | ~$0.45 | AWS billing doesn't attribute to resource tag |
| Terraform state S3 bucket | ~$0.01 | Untagged bootstrap resource |
| Negligible items | <$0.01 | Lambda, CloudFront fragments |

### Newly Activated Tag Data

| Tag Key | Current CE Data | Expected |
|---------|----------------|----------|
| `Project=TogsAndDogs` | $0.00 | Processing delay; data expected within 24–48h |
| `CostCenter=ClientBillable` | Not yet queryable | Same processing delay |
| `Company=USMissionHero` | Not yet queryable | Same processing delay |
| `Application=PetScheduling` | Not yet queryable | Same processing delay |
| `BillingModel=PassThrough` | Not yet queryable | Same processing delay |

### Coverage Classification

**SUBSTANTIALLY COMPLETE WITH DOCUMENTED EXCLUSIONS**

The `Client=TogAndDogs` Budget and Cost Explorer filter captures 92–97% of workload-account costs. The documented $0.47/month exclusion is understood and accepted.

---

## 6. Terraform Drift Note

The two new budget notifications were added via the AWS Budgets API, not via Terraform. The Terraform configuration in `infra/prod/budgets.tf` defines only the original 80% actual-spend alert. On the next `terraform plan`, Terraform will detect these two additional notifications.

**Options (all require Matthew approval):**
1. Update `budgets.tf` to include the two new notification blocks (keeps Terraform authoritative)
2. Accept the drift and manage alerts outside Terraform
3. Import the alerts if a future Terraform version supports notification import

This does NOT affect the saved Phase 1B.5C-A plan because that plan was generated before these alerts existed and does not modify the budget resource.

---

## 7. Actions NOT Performed

- ❌ Budget limit not changed ($20 unchanged)
- ❌ Existing 80% actual alert not removed or modified
- ❌ No resource tags changed
- ❌ No Terraform files changed
- ❌ No infrastructure deployed
- ❌ No application code changed
- ❌ No Component tag activated (does not exist)
- ❌ No mobile build or distribution
- ❌ Phase 1B.5C-A not deployed, saved plan untouched
