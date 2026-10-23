# W3-C1 — Lambda DynamoDB `TransactWriteItems` IAM Change (PLAN ONLY, Not Applied)

**Date:** 2026-09-24
**Disposition:** `W3C1_TRANSACTWRITE_IAM_PLAN_READY_FOR_OWNER_REVIEW`
**Branch:** `infra/w3c1-transactwrite-iam-plan` (from `main == origin/main == da2fb1fc6179bb3335a6cef06aafdf90d183e5d8`)

## Authorization boundary

Owner authorized the IAM/Terraform **source change** for
`dynamodb:TransactWriteItems`, strictly **PLAN ONLY**:

`W3C1_IAM_PLAN_ONLY_AUTHORIZED=YES`
`W3C1_IAM_CHANGE_AUTHORIZED=YES_FOR_PLAN_ONLY`
`W3C1_TERRAFORM_CHANGE_AUTHORIZED=YES_FOR_PLAN_ONLY`
`W3C1_IAM_SOURCE_CHANGE_IMPLEMENTED_LOCAL=YES`
`W3C1_TERRAFORM_APPLY_AUTHORIZED=NO`
`W3C1_RUNTIME_ENABLED=NO`
`W3C1_DEPLOYMENT_AUTHORIZED=NO`

This phase does **not** apply Terraform, mutate AWS, deploy, enable the MANUAL_EXTERNAL
runtime path, or begin W3-C2 (API). The runtime IAM permission does **not** change until a
separate, future apply authorization. The W3-C1 adapter remains
`W3C1_MANUAL_EXTERNAL_ADAPTER_MERGED_NOT_DEPLOYED`.

## Scope

`W3C1_IAM_SCOPE=EXISTING_POLICY_SINGLE_ACTION`

Exactly one file changed: `modules/iam/main.tf`. One line added — `dynamodb:TransactWriteItems`
appended to the existing Lambda DynamoDB access policy (`aws_iam_policy.dynamodb_access`),
which already grants `GetItem/PutItem/UpdateItem/DeleteItem/Query/Scan`.

```diff
       Action = [
         "dynamodb:GetItem",
         "dynamodb:PutItem",
         "dynamodb:UpdateItem",
         "dynamodb:DeleteItem",
+        "dynamodb:TransactWriteItems",
         "dynamodb:Query",
         "dynamodb:Scan"
       ]
       Effect = "Allow"
       Resource = [
         var.data_table_arn,
         "${var.data_table_arn}/index/*"
       ]
```

No new IAM role, no new policy resource, no trust-policy change, no unrelated permission
change, no new AWS resource.

## Least privilege

`W3C1_IAM_LEAST_PRIVILEGE=PASS`

- `Resource` is unchanged — still limited to the existing application table ARN
  (`var.data_table_arn`) and its index scope (`${var.data_table_arn}/index/*`).
- No wildcard DynamoDB action (`dynamodb:*` not used); only the single required action was
  added. `TransactGetItems` was **not** added (the W3-C1 adapter performs only a
  conditional transactional **write** — event Put + summary Update).
- No account-wide DynamoDB access, no resource-ARN widening, no other statement touched.

## Terraform

- **Root/module path:** `infra/prod/` (consumes `modules/iam`). Backend: S3 remote state
  (`togs-and-dogs-358604342897-us-east-1-tfstate`, key `prod/terraform.tfstate`, us-east-1,
  DynamoDB lock), profile `usmissionhero-website-prod` (account `358604342897`).
- **Terraform version:** v1.14.8; providers `hashicorp/aws 5.100.0`, `hashicorp/archive 2.7.1`.
- **Initialization:** `terraform init -backend=false -input=false` — succeeded (credential-free,
  modules + providers initialized).
- **`terraform validate`:** **PASS** — "Success! The configuration is valid."
  `W3C1_TERRAFORM_VALIDATE=PASS`.
- **`terraform plan`:** **NOT EXECUTED (blocked)** — `W3C1_TERRAFORM_PLAN=BLOCKED_ON_EXPIRED_PROD_SSO`.
  A backend-connected plan requires `terraform init` against the S3 backend plus valid
  credentials for account `358604342897`; the prod SSO token is expired and cannot
  auto-refresh ("Token has expired and refresh failed"). Re-authenticating prod SSO and
  running a state-refreshing plan against live prod is outside this PLAN-ONLY, no-AWS-access
  scope, so it was intentionally not performed. No apply, destroy, import, state mutation,
  refresh-only apply, or targeted apply was run.

### Expected plan (prediction — must be confirmed by a credentialed `terraform plan`)

The edit is a static change to an inline IAM policy document (`jsonencode(...)`) with no
dependency on live resource state, so the expected non-applying plan is:

- **0 to add, 1 to change, 0 to destroy**
- Single in-place update: `module.iam.aws_iam_policy.dynamodb_access` — its `policy`
  attribute changes only to include `dynamodb:TransactWriteItems` in the existing
  Statement's `Action` list.
- No Lambda code/config change, no API Gateway change, no DynamoDB table/index change, no
  secrets/networking change, no new resource, no destroy.

If an actual plan shows anything beyond this single in-place IAM policy change, treat it as
`W3C1_IAM_PLAN_SCOPE_DRIFT` and STOP.

## Source verification after edit

- `modules/iam/main.tf` includes `dynamodb:TransactWriteItems` (one insertion).
- W3-C1 adapter `src/backend/common/manual_external_adapter.py` unchanged; no
  handlers/API/UI/Stripe code touched (`git diff --name-only` = `modules/iam/main.tf` only).

## Gates preserved

`W3C1_TRANSACTWRITE_IAM_PRESENT=NO` (runtime), `W3C1_RUNTIME_IAM_CHANGE_REQUIRED=YES`,
`W3C1_TERRAFORM_APPLY_AUTHORIZED=NO`, `W3C1_DEPLOYMENT_AUTHORIZED=NO`,
`W3C1_RUNTIME_ENABLED=NO`. No W3-C2/API Gateway/API route/UI, no Stripe/Connect/OAuth/secrets,
no production mutation/test data, no second tenant, no tenant-resolution change, no Ryan
testing, no scheduling, no mobile distribution. Scheduling
`SCHEDULING_WORKSTREAM_STATUS=DRAFT_PR_DELIVERY_CHECKPOINT`,
`SCHEDULING_PR_MERGE_AUTHORIZED=NO`; Stripe sandbox-only; `RYAN_TESTING_AUTHORIZED=NO`.
Latest completed production backend release remains `PR22_PRIVACY_PRODUCTION_DEPLOYED_VERIFIED`.

Checkpoint: `main == origin/main == da2fb1fc6179bb3335a6cef06aafdf90d183e5d8`.
