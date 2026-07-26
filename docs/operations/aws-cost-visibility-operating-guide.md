# AWS Cost Visibility Operating Guide

**For:** Matthew
**Last Updated:** 2026-07-26
**Budget:** `togs-and-dogs-prod-monthly-budget`

---

## Quick Reference

| Item | Value |
|------|-------|
| Monthly budget limit | $20 USD |
| Current monthly spend | ~$6–8 |
| Cost filter | `Client = TogAndDogs` |
| Alert thresholds | 80% actual, 80% forecasted, 100% actual |
| Typical monthly cost | $6–8 USD |
| Top cost driver | AWS Step Functions (~$4.40) |

---

## 1. Check Budget Status

1. Sign in to the **AWS Management Console**
2. Navigate to **Billing and Cost Management** (search "Billing" in the top bar)
3. In the left nav, click **Budgets**
4. Select **togs-and-dogs-prod-monthly-budget**
5. Review:
   - **Current vs. Budgeted**: Bar shows actual spend against $20 limit
   - **Forecast**: Predicted end-of-month spend
   - **Alert status**: Green (OK) or Red (ALARM)

---

## 2. Review Alert Conditions

On the budget detail page, scroll to **Alerts**:

| Alert | Meaning | Action if triggered |
|-------|---------|---------------------|
| 80% Actual ($16) | You've spent $16 this month | Investigate unexpected cost increase |
| 80% Forecasted ($16) | Projected to exceed $16 by month-end | Review trending services |
| 100% Actual ($20) | Budget limit reached | Immediate investigation required |

---

## 3. Open Cost Explorer

1. From Billing and Cost Management, click **Cost Explorer** in the left nav
2. Or: From the budget detail page, click **Explore in Cost Explorer**

---

## 4. View Togs & Dogs Costs

1. In Cost Explorer, set **Date range** to desired period (e.g., Last 6 months)
2. Under **Filters**, click **Tag**
3. Select tag key: **Client**
4. Select value: **TogAndDogs**
5. Apply

---

## 5. Group by Service

1. Under **Group by**, select **Service**
2. The chart shows cost broken down by AWS service
3. Expected top services:
   - AWS Step Functions (~$4.40/month)
   - AWS Secrets Manager (~$1.25/month)
   - Amazon API Gateway (~$0.02/month)
   - Others: minimal

---

## 6. Change Granularity

- **Monthly**: Click the "Monthly" granularity option — shows cost bars per month
- **Daily**: Click "Daily" — shows daily cost over the selected period
- Daily is useful for identifying when a cost spike occurred

---

## 7. Compare Tagged vs. Total (Identify Unallocated Costs)

To see what costs are NOT captured by the Client tag:

1. **View 1**: Remove all filters, add filter: Linked Account = [workload account]. Note the total.
2. **View 2**: Add filter: Tag → Client → TogAndDogs. Note the reduced total.
3. **Difference** = unallocated costs (~$0.47/month currently)

Known unallocated sources:
- CloudWatch alarm monitoring (~$0.45) — tagged at resource level but AWS billing doesn't attribute
- Terraform state S3 bucket (~$0.01) — untagged bootstrap resource

---

## 8. Review Trailing Trend

1. Set date range to **Last 6 months**
2. Set granularity to **Monthly**
3. Review whether costs are stable, increasing, or decreasing
4. Current pattern: $6–8/month (stable since May 2026)

---

## 9. Additional Filter Options (Now Available)

After tag activation on 2026-07-26, these filters are available for new data:

| Filter | Value | Use Case |
|--------|-------|----------|
| Client | TogAndDogs | Primary project filter |
| Project | TogsAndDogs | Confirm same scope as Client |
| Environment | prod | Filter by environment |
| CostCenter | ClientBillable | Billing model view |
| Company | USMissionHero | Company-level grouping |
| Application | PetScheduling | Application filter |
| BillingModel | PassThrough | Billing model view |

**Note:** These tags will only show data from 2026-07-26 forward (activation date). Historical data before this date is only filterable by `Client`, `Environment`, `ManagedBy`, and `Repo`.

---

## 10. Avoid Accidental Changes

- **Do not** click "Activate" or "Deactivate" on cost-allocation tags without intent
- **Do not** modify the budget limit, filter, or alerts without a documented reason
- **Do not** delete budget notifications
- Cost Explorer views are read-only — viewing data does not change anything
- Creating a saved report is safe (read-only configuration)

---

## 11. Save a Cost Explorer Report (One-Time Setup)

1. Configure the view as described above (Client=TogAndDogs, Monthly, Group by Service, 6 months)
2. Click **Save as new report** (top right)
3. Name: `Togs-and-Dogs-Monthly-Cost-Overview`
4. Click **Save**
5. Access it later from Cost Explorer → Saved Reports
