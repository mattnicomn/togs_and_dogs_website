# Phase 23A: AWS Tagging Evidence Audit and Minimal Remediation

**Status:** ✅ EVIDENCE AUDIT COMPLETE — Optional remediation deferred
**Date:** 2026-07-24
**Starting HEAD:** `7243de2c839fd7425ddb909f8b71223548386384`
**Locked AWS Provider:** `hashicorp/aws 5.100.0` (constraint `~> 5.0`)

---

## 1. Purpose and Scope

A strictly read-only audit to determine whether every Terraform-managed AWS resource associated with Togs & Dogs is consistently tagged and whether the required tag keys are available for cost-allocation and Budgets filtering.

**Scope boundaries:**
- Read-only repository inspection and read-only AWS CLI commands only.
- No tag mutations, no Terraform apply, no cost-allocation tag activation.
- Independent of the saved Phase 1B.5C-A Terraform plan (which must not be altered or combined with any tagging work).

---

## 2. Provider-Level Default-Tag Behavior

All three AWS provider configurations in `infra/prod/providers.tf` include:

```hcl
default_tags {
  tags = local.common_tags
}
```

Under AWS provider 5.100.0, `default_tags` propagate automatically to any resource type that implements the `tags` schema attribute — **regardless of whether the HCL block includes an explicit `tags = ...` argument**. Effective tags are visible in the computed `tags_all` attribute in Terraform state.

---

## 3. Current Nine-Key Tag Standard

Defined in `infra/prod/locals.tf`:

| Key | Value |
|-----|-------|
| `Company` | `USMissionHero` |
| `Project` | `TogsAndDogs` |
| `Environment` | `prod` |
| `ManagedBy` | `terraform` |
| `Repo` | `togs_and_dogs_website` |
| `Client` | `TogAndDogs` |
| `Application` | `PetScheduling` |
| `CostCenter` | `ClientBillable` |
| `BillingModel` | `PassThrough` |

---

## 4. Verified Findings

### 4.1 All Supported Terraform-Managed Resources Are Tagged

Live verification via the AWS Resource Groups Tagging API returned **46 resources** with the `Project=TogsAndDogs` tag, covering:

- 13 Lambda functions
- 7 IAM policies
- 2 IAM roles (verified via direct `iam list-role-tags`)
- 1 Cognito user pool
- 4 Secrets Manager secrets
- 1 DynamoDB table
- 3 SNS topics
- 7 CloudWatch metric alarms
- 2 CloudWatch log groups (Terraform-managed)
- 1 API Gateway REST API
- 1 API Gateway stage
- 1 S3 bucket (frontend hosting)
- 1 CloudFront distribution
- 1 ACM certificate
- 1 Step Functions state machine
- 1 EventBridge rule
- 1 AWS Budgets budget

All 46 resources carry the full nine-key tag set.

### 4.2 Correction: IAM Policies Are NOT Missing Tags

A preliminary planning review incorrectly identified seven IAM policies as missing tags because they lack an explicit `tags` argument in HCL. Live verification confirms that provider `default_tags` propagate to `aws_iam_policy` resources in provider 5.100.0.  All seven policies carry 9/9 keys.

### 4.3 Correction: AWS Budget Is NOT Missing Tags

The `aws_budgets_budget` resource similarly inherits `default_tags` without an explicit `tags` argument.  All nine keys confirmed present on the live budget resource.

### 4.4 SES Configuration Set Does Not Support Tags

The `aws_ses_configuration_set` resource type (SES v1 API) does **not** expose a `tags` schema attribute in AWS provider 5.100.0. Provider `default_tags` cannot propagate to resources that lack this attribute.

- Terraform Registry documentation for `aws_ses_configuration_set` (5.100.0): no `tags` in Argument Reference, no `tags_all` in Attribute Reference.
- Live SES v2 API query confirms zero tags on the configuration set.
- The Resource Groups Tagging API returns no SES configuration-set resources.

To add tags, the resource would need to be migrated to `aws_sesv2_configuration_set`. This is an **architectural change** involving resource replacement and is **not approved or required now**.

---

## 5. Live Budget Configuration

| Property | Value |
|----------|-------|
| Budget name | `togs-and-dogs-prod-monthly-budget` |
| Monthly limit | $20.00 USD |
| Cost filter | `TagKeyValue = Client$TogAndDogs` |
| Notification threshold | 80% ACTUAL spend |
| Current month actual spend | ~$5.46 |
| Current month forecasted spend | ~$7.46 |
| Last updated | 2026-07-24 |

The budget is actively tracking real costs filtered by the `Client=TogAndDogs` tag.

---

## 6. Cost-Allocation Tag Limitation

The workload account (`358604342897`) is a **linked/member account** in an AWS Organization.

```
AccessDeniedException: Linked account doesn't have access to cost allocation tags.
```

- Active and inactive cost-allocation tag keys cannot be directly listed from this account.
- Payer/management-account access would be required for authoritative activation-status verification.
- **Inference (not direct proof):** The Budget's cost filter uses `Client$TogAndDogs` and reports non-zero actual spending. This strongly indicates the `Client` tag is **active** as a cost-allocation tag at the payer level. If it were inactive, the filter would match zero spend.

---

## 7. Remaining Gaps

### 7.1 Non-Terraform Bootstrap Resources (Untagged)

| Resource | Service | Reason |
|----------|---------|--------|
| `togs-and-dogs-<ACCOUNT>-us-east-1-tfstate` | S3 | Manually created state bucket; not in Terraform |
| `togs-and-dogs-terraform-lock` | DynamoDB | Manually created lock table; not in Terraform |

### 7.2 Lambda-Created CloudWatch Log Groups (Untagged)

12 log groups matching `/aws/lambda/togs-and-dogs-prod-*` were auto-created by the Lambda service on first invocation. They are not managed by Terraform and carry zero tags.

### 7.3 Legacy SES Configuration Set

`aws_ses_configuration_set.main` cannot be tagged under the current Terraform resource type. Migration to `aws_sesv2_configuration_set` would be required.

---

## 8. Optional Future Choices (All Deferred)

| Item | Disposition |
|------|-------------|
| Tag bootstrap S3 bucket and DynamoDB lock table | One-time manual CLI commands; safe whenever Matthew approves |
| Manage or tag Lambda-created log groups | Import to Terraform or one-time CLI tagging; low priority (minimal cost impact) |
| Evaluate SESv2 migration | Separate architectural design review; resource replacement risk |
| Verify cost-allocation activation at payer account | Requires payer-account access; no workload-account action possible |

**None of these items is urgent.** No Terraform source changes are currently required to maintain the existing nine-key tagging standard.

---

## 9. Separation from Phase 1B.5C-A

No tagging work may be combined with, alter, or replace the saved Phase 1B.5C-A Terraform plan (`infra/prod/phase-1b5c-a-customer-pet-editing.tfplan`). Phase 1B.5C-A deployment should not be delayed solely because of these optional tagging gaps.

---

## 10. Approval Gates

| Action | Requires |
|--------|----------|
| Tag bootstrap resources manually | Matthew approval |
| Migrate SES to SESv2 | Separate design review + Matthew approval + Terraform plan/apply |
| Activate cost-allocation tags | Payer-account administrator action |
| Any Terraform plan/apply for tagging | Matthew approval (never combine with Phase 1B.5C-A plan) |

---

## 11. Known Typo (Not Corrected)

`infra/prod/locals.tf` line 2 contains: `# Mandatry tagging standard`
Should be: `# Mandatory tagging standard`
Not corrected in this documentation task.

---

## 12. Disposition

- ✅ Phase 23A evidence audit: **COMPLETE**
- ⏸️ Optional remediation: **DEFERRED** until Matthew explicitly selects an item
- ⏸️ Phase 1B.5C-A: unaffected — remains ready for Matthew's deployment decision
