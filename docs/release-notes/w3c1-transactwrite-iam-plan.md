# W3-C1 — Lambda DynamoDB `TransactWriteItems` IAM Change (PLAN ONLY, Not Applied)

**Date:** 2026-09-24
**Disposition:** `W3C1_TARGETED_IAM_PLAN_VERIFIED_READY_FOR_OWNER_REVIEW`
**Branch:** `infra/w3c1-transactwrite-iam-plan` (from `main == origin/main == da2fb1fc6179bb3335a6cef06aafdf90d183e5d8`)
**Plan results:** `W3C1_TERRAFORM_VALIDATE=PASS`;
`W3C1_FULL_TERRAFORM_PLAN=0_ADD_14_CHANGE_0_DESTROY`;
`W3C1_FULL_PLAN_SCOPE_DRIFT=13_LAMBDA_SOURCE_CODE_HASH_CHANGES`;
`W3C1_TARGETED_IAM_PLAN=PASS`;
`W3C1_TARGETED_IAM_PLAN_COUNTS=0_ADD_1_CHANGE_0_DESTROY`;
`W3C1_TARGETED_IAM_PLAN_RESOURCE=module.iam.aws_iam_policy.dynamodb_access`.
Apply remains unauthorized: `W3C1_TERRAFORM_APPLY_AUTHORIZED=NO`, `W3C1_RUNTIME_ENABLED=NO`,
`W3C1_DEPLOYMENT_AUTHORIZED=NO`.

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

Once prod SSO was refreshed, the backend was initialized against the real S3 backend
(`terraform init` — "Successfully configured the backend 's3'", established config, no
reconfiguration) and two non-applying plans were executed. No apply, destroy, import, state
mutation, refresh-only apply, or targeted apply was run; both plans performed read-only state
refresh only.

### Full production plan (executed, non-applying)

`W3C1_FULL_TERRAFORM_PLAN=0_ADD_14_CHANGE_0_DESTROY`
`W3C1_FULL_PLAN_SCOPE_DRIFT=13_LAMBDA_SOURCE_CODE_HASH_CHANGES`

`terraform plan` (full) returned **`Plan: 0 to add, 14 to change, 0 to destroy`**:

- 1 authorized change — `module.iam.aws_iam_policy.dynamodb_access` (adds only
  `dynamodb:TransactWriteItems`; Resource unchanged).
- 13 **pre-existing** `aws_lambda_function.*` in-place drifts — `admin, assign, cancellation,
  device, google_auth, intake, job, pet, platform, postmark_webhook, review, ses_feedback,
  stripe_webhook` — each a `source_code_hash` change `W6cqyudlRQF3Zw7uN2V42JzziwYITg8r5mCnsGdDAq4=`
  → `58C9BlEJNwm/Gf1AYO028ynYmf42KjeXQn2E1U/MbK8=` (repo `main` backend code is ahead of the
  prod artifact last deployed 2026-10-22). These are independent of the IAM edit (an IAM
  policy change cannot alter a Lambda archive hash) and are NOT authorized for apply here.

Because the full plan shows changes beyond the single authorized IAM change, the full plan is
**not clean**: `W3C1_IAM_PLAN_SCOPE_DRIFT`. A blanket apply of the full plan would also
redeploy 13 Lambdas — outside this plan-only authorization.

### Targeted IAM plan (executed, non-applying) — scoped validation only

`W3C1_TARGETED_IAM_PLAN=PASS`
`W3C1_TARGETED_IAM_PLAN_COUNTS=0_ADD_1_CHANGE_0_DESTROY`
`W3C1_TARGETED_IAM_PLAN_RESOURCE=module.iam.aws_iam_policy.dynamodb_access`

`terraform plan -target=module.iam.aws_iam_policy.dynamodb_access` returned **`Plan: 0 to add,
1 to change, 0 to destroy`**:

- Exactly one resource in the plan: `module.iam.aws_iam_policy.dynamodb_access`, in-place
  update; its `policy` diff adds only `+ "dynamodb:TransactWriteItems"` to the existing
  Statement's `Action` list. Resource ARN unchanged.
- **No `aws_lambda_function` (or any other) resource appears** in the targeted plan.
- Terraform emitted the standard informational "Resource targeting is in effect" warning;
  `-target` was used for plan **validation only**, never with apply.

This targeted plan isolates and proves the IAM change is a clean `0/1/0`. It is a scoped
validation tool only and does **not** mean the full production plan is clean — the full plan
still carries the 13 pre-existing Lambda drifts recorded above, which must be reconciled or
separately authorized before any apply.

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
