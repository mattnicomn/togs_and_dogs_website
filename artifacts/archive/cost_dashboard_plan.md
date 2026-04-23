# Cost Dashboard & Reporting Plan - Togs & Dogs

This document outlines the lightweight, AWS-native strategy for monitoring, managing, and reporting on the "Togs & Dogs" infrastructure costs for US Mission Hero.

## 1. Current State Assessment

The application utilizes a Serverless architecture that scales on-demand, keeping baseline fixed costs extremely low.

### Dedicated Resources (App-Specific)
- **Lambda Functions**: usage-based (variable)
- **DynamoDB Table**: storage and usage-based (variable)
- **S3 Bucket**: storage and transfer (variable)
- **CloudFront Distribution**: transfer and requests (variable)
- **API Gateway**: usage-based (variable)
- **Cognito User Pool**: free up to 50k MAUs (variable)
- **Secrets Manager**: ~$0.40/secret/month (fixed)
- **SNS Topics**: usage-based (variable)

### Shared Resources (US Mission Hero Baseline)
- **Route 53 Hosted Zone**: Fixed monthly fee ($0.50) per zone.
- **ACM Certificates**: Free.

## 2. Tagging Standard

Effective cost allocation is driven by the following unified tagging standard. **Note**: While several tags are deployed, we use **`Client`** as the primary reporting key because it is already active in the US Mission Hero master billing account.

| Tag | Value | Description |
| :--- | :--- | :--- |
| **Client** | `TogAndDogs` | **Primary reporting key.** Already active in billing. |
| **Project** | `TogsAndDogs` | Secondary grouping (Awaiting activation). |
| **BillingModel** | `PassThrough` | Indicates costs should be billed to the client. |
| **Company** | `USMissionHero` | Identifying the owning entity (Awaiting activation). |
| **Environment** | `prod` | Distinguishes from development/test costs. |

## 3. Cost Monitoring Strategy

US Mission Hero will use the following AWS-native tools for visibility. All billing operations take place in the **Payer Account (253881689673)**.

### AWS CLI (The Data Truth)
Use the `website-infra-sandbox` profile to query raw billable data.
```powershell
aws ce get-cost-and-usage --time-period Start=2026-04-01,End=2026-05-01 --granularity MONTHLY --metrics "UnblendedCost" --filter '{\"Tags\": {\"Key\": \"Client\", \"Values\": [\"TogAndDogs\"]}}'
```

### AWS Cost Explorer (Visual Reporting)
1. **Account**: US Mission Hero Payer Account (`253881689673`).
2. **Setup**: **Manual Action Required**. Create a saved report named "Togs & Dogs Monthly Overview" filtered by `Tag: Client = TogAndDogs` (Group by Service).

### AWS Budgets (The Proactive Guardrail)
An automated budget is implemented in `budgets.tf` within the Payer Account:
- **Threshold**: $20.00 / month.
- **Filter**: `Tag: Client = TogAndDogs`.
- **Alert**: Email notification to `mbn@usmissionhero.com` when 80% ($16.00) is reached.

## 4. Monthly Reporting Workflow

To generate the monthly report for Ryan in under 15 minutes:

1. **Verification**: Run the CLI command above using the `website-infra-sandbox` profile to confirm the total billable amount.
2. **Extraction**: Access the Payer Account (`253881689673`) console to view the "Togs & Dogs Monthly Overview" report.
3. **Report Generation**: Copy the [monthly_client_report_template.md](./docs/monthly_client_report_template.md) and fill in the data.
4. **Shared Cost Allocation**: Shared US Mission Hero overhead (Root DNS) is currently documented but **not** automatically surcharged. Line items for professional services are added separately.

## 5. Monthly Operator Checklist

Follow these steps each month to produce the report in under 15 minutes:
- [ ] **Open Cost Explorer**: Filter by `Tag: Project = TogsAndDogs`.
- [ ] **Configure View**: Set granularity to "Monthly" and group by **Service**.
- [ ] **Capture Totals**: Record the total spend for the **prior full billing month**.
- [ ] **Draft Report**: Transfer totals into the `monthly_client_report_template.md`.
- [ ] **Add Services**: Include any maintenance or professional services line items.
- [ ] **Final Review**: Confirm thresholds haven't been breached (check Budget status).
- [ ] **Send**: Deliver the report to Ryan.

## 6. Reusable Client Onboarding Pattern

This pattern is designed to scale to future customers:
1. **Initialize Project Tag**: Add a new unique value for the `Project` tag in the client's `locals.tf`.
2. **Standardize Infrastructure**: Deploy the client's stack using this repository's modules.
3. **Activate Tags**: **Wait for first spend**, then manually activate the new `Project` tag in the [AWS Billing Dashboard](https://console.aws.amazon.com/billing/home?#/tags).
4. **Create Budget**: Configure a dedicated `aws_budgets_budget` for the new client.
5. **Clone Template**: Use the standard `monthly_client_report_template.md` for their billing cycle.

## 7. Critical Operational Notes

> [!WARNING]
> **Manual Activation Required**: AWS cost allocation tags MUST be manually activated in the Master Payer account billing dashboard. They are NOT active by default.

> [!IMPORTANT]
> **Non-Retroactive Tracking**: Tagged cost tracking only begins *after* the tag is activated. Past spend cannot be retroactively grouped by project tags.

> [!CAUTION]
> **Reporting Window**: Always use the **prior full billing month** for client-facing reports. In-progress months are subject to AWS billing adjustments and may fluctuate.

## 8. Next Steps
1. **Activate Tags**: Manual step required in the AWS Billing Console to make `Project` and `Company` available for Cost Explorer.
2. **Initial Deployment**: Run `terraform apply` to deploy the updated tags and budget resources.
3. **Baseline Review**: Verify the Togs & Dogs saved view appears in Cost Explorer after 24 hours.
