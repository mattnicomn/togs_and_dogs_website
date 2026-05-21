# Backlog: AWS Cost Allocation Tagging

## Priority: Low
## Status: Planned

## Problem
AWS resources managed by Terraform have partial tagging via `common_tags` in `locals.tf`, but coverage is inconsistent across all resource types. A standardized tagging strategy is needed for cost allocation, billing visibility, and operational grouping.

## Scope

### Resources to Tag
| Resource Type | Current Tagging | Action |
|--------------|----------------|--------|
| Lambda functions | ✅ `common_tags` applied | Review Component tag |
| DynamoDB table | ✅ `common_tags` applied | Review Component tag |
| S3 (frontend hosting) | ✅ `common_tags` applied | Confirm |
| CloudFront distribution | ✅ `common_tags` applied | Confirm |
| Secrets Manager secrets | Partial | Add full tag set |
| SNS topics | Partial | Add full tag set |
| CloudWatch Log Groups | Check | Add where supported |
| IAM roles/policies | Check | Add where useful |
| Cognito User Pool | Check | Add where supported |
| API Gateway | Check | Add where supported |
| Step Functions | Check | Add where supported |

### Proposed Tag Schema
```hcl
tags = {
  Project      = "TogAndDogs"
  Application  = "OperationsPortal"
  Environment  = "prod"
  Owner        = "USMissionHero"
  ManagedBy    = "Terraform"
  CostCenter   = "TogAndDogs"
  Component    = "<one of below>"
}
```

### Component Values
| Component | Resources |
|-----------|-----------|
| `frontend` | S3, CloudFront |
| `backend` | Lambda functions, API Gateway |
| `auth` | Cognito, IAM |
| `data` | DynamoDB |
| `notifications` | SNS, SES config, Postmark-related Lambdas |
| `calendar` | Google Auth Lambda, related secrets |
| `monitoring` | CloudWatch Log Groups, Alarms, Budgets |
| `workflow` | Step Functions |
| `secrets` | Secrets Manager |

## Implementation Approach
1. Audit current `common_tags` in `infra/prod/locals.tf`
2. Add `Component` tag to each resource or module
3. Ensure all modules pass tags through to child resources
4. Verify in AWS Cost Explorer that tags appear for billing allocation
5. No application behavior changes — Terraform-only

## Files Involved
- `infra/prod/locals.tf` — update `common_tags` if needed
- `infra/prod/main.tf` — add Component tag per resource
- `modules/*/` — ensure tags are passed through

## Effort: 2-3 hours
## Risk: None (tags don't affect runtime behavior)
