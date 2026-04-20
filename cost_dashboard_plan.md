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

Effective cost allocation is driven by the following unified tagging standard implemented in Terraform's `common_tags`:

| Tag | Value | Description |
| :--- | :--- | :--- |
| **Project** | `TogsAndDogs` | Primary grouping for Cost Explorer. |
| **Company** | `USMissionHero` | Identifying the owning entity. |
| **Client** | `TogAndDogs` | Specifically for client-facing reports. |
| **BillingModel** | `PassThrough` | Indicates costs should be billed to the client. |
| **Environment** | `prod` | Distinguishes from development/test costs. |

## 3. Cost Monitoring Strategy

US Mission Hero will use the following AWS-native tools for visibility:

### AWS Cost Explorer (The Single Pane)
1. **Navigate to**: [AWS Cost Explorer](https://console.aws.amazon.com/costmanagement/home#/costexplorer)
2. **Filter by**: `Tag: Project = TogsAndDogs`
3. **Group by**: `Service` (to see which component is driving cost)
4. **Save Report**: Save this view as "Togs & Dogs Monthly Overview" for one-click access.

### AWS Budgets (The Proactive Guardrail)
An automated budget is implemented in `budgets.tf` with the following parameters:
- **Threshold**: $20.00 / month.
- **Alert**: Email notification to `mbn@usmissionhero.com` when 80% ($16.00) is reached.

## 4. Monthly Reporting Workflow

To generate the monthly report for Ryan in under 15 minutes:

1. **Extraction**: Open the "Togs & Dogs Monthly Overview" in Cost Explorer for the previous month.
2. **Data Gathering**: Identify the total cost for the `TogsAndDogs` project tag.
3. **Report Generation**: Copy the [monthly_client_report_template.md](./docs/monthly_client_report_template.md) and fill in the data.
4. **Shared Cost Allocation**: Shared US Mission Hero overhead (Root DNS) is currently documented but **not** automatically surcharged. Line items for professional services are added separately.

## 5. Assumptions & Limitations
- **Latency**: Tags can take up to 24 hours to appear in Cost Explorer after being activated in the Billing console.
- **Tag Activation**: Ensure that newly added tags (`Project`, `Company`) are marked as "Active" in the [AWS Cost Allocation Tags](https://console.aws.amazon.com/billing/home?#/tags) console.

## 6. Next Steps
1. **Activate Tags**: Manual step required in the AWS Billing Console to make `Project` and `Company` available for Cost Explorer.
2. **Run Initial Terraform Apply**: Deploy the updated tags and budget resources.
3. **First Month Review**: Perform the first internal cost review at the end of the current billing cycle.
