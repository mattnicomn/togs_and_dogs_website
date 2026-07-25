# Phase 23B: AWS Budget Coverage and Cost Visibility Dashboard

**Status:** 📋 PLANNED — Implementation not approved
**Date:** 2026-07-25
**Depends on:** Phase 23A evidence audit (complete)
**Blocked by:** Nothing (independent of Phase 1B.5C-A)

---

## 1. Goal

Ensure Matthew can see and monitor the **complete** Togs & Dogs cost footprint through AWS Billing and Cost Management — not merely that resources are tagged, but that all costs are visible, correctly attributed, and actionable through a clear dashboard.

---

## 2. Current Verified Budget State

| Property | Value |
|----------|-------|
| Budget name | `togs-and-dogs-prod-monthly-budget` |
| Budget type | Monthly COST |
| Monthly limit | $20 USD |
| Cost filter | `TagKeyValue = Client$TogAndDogs` |
| Alert threshold | 80% ACTUAL spend |
| Actual spend observed | ~$5.46 (at time of Phase 23A audit) |
| Forecasted spend observed | ~$7.46 |
| Tag coverage | All supported Terraform-managed resources carry 9-key standard via provider `default_tags` |
| Account type | Linked/member account in AWS Organization |
| Cost-allocation activation | **Unverified** — requires payer/management account access |
| Budget tracking | Observed working (non-zero actual/forecast) — strongly implies `Client` tag is active |

---

## 3. Planned Work Items

### 3.1 Cost-Allocation Tag Verification

**Goal:** Authoritatively confirm which user-defined tag keys are active for cost allocation.

**Planned actions (read-only from payer account):**
- `aws ce list-cost-allocation-tags --type UserDefined --status Active`
- `aws ce list-cost-allocation-tags --type UserDefined --status Inactive`

**Determine:**
- Active keys (expected: at minimum `Client`, possibly `Project`, `Environment`)
- Inactive keys that could be activated
- Keys that have never appeared in Billing
- Activation dates (cost allocation begins only after activation, not retroactively)
- Whether historical reporting requires a waiting period after activation

**Required permissions (high-level):**
- Payer/management account access with `ce:ListCostAllocationTags` permission
- Or AWS Organizations delegated administrator for Billing

**Approval gate:** Read-only payer-account verification requires Matthew coordination with the payer account administrator.

### 3.2 Current Budget Coverage Validation

**Planned verification:**
- Confirm filter expression matches `Client$TogAndDogs`
- Review actual spend vs. total account spend (are any Togs & Dogs costs excluded?)
- Determine whether refunds, credits, taxes, support fees, or shared charges are included
- Determine whether costs from untagged resources (bootstrap S3, lock table, Lambda log groups) fall outside the filtered view
- Determine whether AWS Marketplace charges, if any, are included
- Confirm alert recipients are correct (redacted in documentation)
- Confirm notification delivery has been received historically

**Do not modify the budget during this investigation.**

### 3.3 Untagged-Resource Cost Coverage

From Phase 23A, the following resources lack tags:

| Resource | Estimated Cost | Tagging Support | Recommended Disposition |
|----------|---------------|-----------------|------------------------|
| Terraform state S3 bucket | Minimal (single object storage) | Full (manual tag) | One-time manual tag recommended |
| Terraform lock DynamoDB table | Minimal (pay-per-request, rare writes) | Full (manual tag) | One-time manual tag recommended |
| 12× Lambda-created CloudWatch log groups | Measurable (log ingestion/storage) | Full (manual tag or import) | Evaluate cost share vs. management burden |
| SES configuration set (v1) | None (config sets are free) | Not supported in provider 5.100.0 | Accept — zero cost, no action needed |

**For each, determine:**
- Whether it produces measurable cost
- Whether that cost currently appears in the Client-filtered budget
- Whether tagging is straightforward
- Whether the remediation is worth its operational complexity

**Do not recommend SESv2 migration solely for tagging — it has zero cost impact.**

### 3.4 Cost Explorer Saved Report

**Plan a saved report with:**
- Primary filter: `Client = TogAndDogs`
- Optional secondary filter: `Project = TogsAndDogs`
- Granularity: Monthly (with daily drill-down available)
- Metric: Unblended cost (document whether amortized is relevant for this scale)
- Group by: AWS Service
- Optional groupings: Region, Environment
- Future grouping: Component (only after component-tag design is approved)
- View: Current month + trailing 6 months minimum
- Include: Forecast line
- Compare: Unallocated/untagged cost to identify coverage gaps

**Do not create the report during planning. Implementation requires explicit approval.**

### 3.5 Budget Design Review

**Evaluate whether current configuration remains appropriate:**

| Question | Current | Review Options |
|----------|---------|----------------|
| Monthly threshold | $20 | Is this still realistic after Phase 1B additions? |
| Alert type | 80% actual | Add forecasted-spend alert? |
| 100% alert | Not configured | Should a 100% actual-spend alert exist? |
| Early warning | Not configured | Would 50% or 60% provide useful lead time? |
| Budget scope | Single project-wide | Would per-service budgets add value? |
| Notification channel | Email only | Is this sufficient for Matthew? |

**Do not change the budget without separate Matthew approval.**

### 3.6 Dashboard Operating Instructions

**Plan documentation showing Matthew how to:**
1. Open AWS Billing and Cost Management console
2. Navigate to Budgets → find `togs-and-dogs-prod-monthly-budget`
3. Read actual vs. budgeted spend and forecast
4. Open Cost Explorer from the budget view
5. Change the date range to review trends
6. Group by AWS Service to identify top cost drivers
7. Filter by `Client = TogAndDogs` tag
8. Identify unallocated costs (costs without the project tag)
9. Review alert history
10. Determine whether spend is trending above budget

**Do not include console URLs containing account-specific identifiers.**

### 3.7 Validation and Acceptance Criteria

Phase 23B is not complete until:

- [ ] The current budget is confirmed to match Togs & Dogs tagged spend
- [ ] Cost Explorer shows the same scope as the budget filter
- [ ] Known untagged resources have been cost-evaluated
- [ ] Any excluded spend is documented with a reason
- [ ] Matthew can locate and interpret the Cost Explorer report
- [ ] Alert thresholds have been reviewed and confirmed appropriate
- [ ] No unrelated account or company costs appear in the Togs & Dogs view
- [ ] The result is recorded in project continuity documents

---

## 4. Approval Gates

| Action | Requires |
|--------|----------|
| Read-only payer-account tag verification | Matthew coordination + payer admin |
| Activating or deactivating cost-allocation tags | Explicit Matthew approval + payer admin |
| Modifying the existing AWS Budget | Explicit Matthew approval |
| Creating additional budgets | Explicit Matthew approval |
| Creating Cost Explorer saved reports | Explicit Matthew approval |
| Applying manual resource tags | Explicit Matthew approval |
| Importing bootstrap resources into Terraform | Explicit Matthew approval + plan/apply |
| Adding a Component tag to `local.common_tags` | Explicit Matthew approval + Terraform plan/apply |
| Any payer-account Billing configuration change | Explicit Matthew + payer admin approval |

---

## 5. Priority and Dependencies

- Phase 23B is **not blocked by** Phase 1B.5C-A deployment.
- Phase 23B **does not block** Phase 1B.5C-A deployment.
- Phase 23B should be completed before declaring AWS cost allocation fully operational.
- Phase 24A-4 (Mobile My Pets) does not alter AWS cost tracking (not yet distributed).
- A later mobile EAS build could introduce additional build-service costs — evaluate separately when mobile distribution is approved.
- No mobile distribution is currently approved.

---

## 6. What This Document Does NOT Authorize

- ❌ Budget creation or modification
- ❌ Cost Explorer report creation
- ❌ Cost-allocation tag activation or deactivation
- ❌ Resource tag application
- ❌ Terraform changes
- ❌ Payer-account access or configuration
- ❌ Production deployments
- ❌ Mobile builds or distribution
