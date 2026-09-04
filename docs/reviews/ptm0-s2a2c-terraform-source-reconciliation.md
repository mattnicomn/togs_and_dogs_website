# PTM0-S2A.2c — Terraform source reconciliation

Date: 2026-09-04.

Disposition: **PTM0_S2A2C_TERRAFORM_SOURCE_RECONCILIATION_READY_FOR_INDEPENDENT_REVIEW**

Status: **LOCAL SOURCE ONLY / UNSTAGED / UNCOMMITTED / NO PRODUCTION PLAN OR APPLY**

## Authority and checkpoint

Matthew reports `PTM0_S2A2B_INDEPENDENT_MIGRATION_VERIFICATION_APPROVED` and
authorizes reconciliation of exactly the two Terraform resources below with
the [verified migration evidence](ptm0-s2a2b-provider-ownership-migration-evidence.md).
No new production observation or mutation is claimed by this local task.

Starting branch main; HEAD and local origin/main both
`1cca9dd1cca9be3a39257f4d3c11ed7de4c53ac3`. Tracked worktree/index clean;
stash empty; five intentional untracked S2 review/evidence records.

Option B remains authoritative: no DynamoDB calendar_secret_ref backfill.
Explicit-primary compatibility is a future S2A.3 runtime concern, not implemented
here. Ordinary-tenant explicit reference/ownership enforcement is also unchanged.

## Exact tracked source diff

### modules/iam/main.tf

Resource `aws_iam_policy.google_secrets_access` previously had two statements:
Google client/token GetSecretValue/PutSecretValue, then Postmark GetSecretValue.
Both statements, including their Action/Resource arrays and ordering, remain
unchanged. Append the third statement matching verified v3:

```diff
         Resource = [
           var.postmark_token_arn
         ]
+      },
+      {
+        Effect   = "Allow"
+        Action   = "secretsmanager:DescribeSecret"
+        Resource = var.google_user_tokens_arn
       }
```

This is a singleton resource expression, not an addition to the existing
two-resource Google statement. No wildcard, TagResource, UntagResource or
existing permission change. No other IAM resource or role attachment changes.

### modules/secrets/main.tf

Only `aws_secretsmanager_secret.google_user_tokens.tags` changes:

```diff
-  tags        = var.tags
+  tags = merge(var.tags, {
+    CompanyId = "tog_and_dogs"
+  })
```

The existing common tag map remains an input; the resource-specific owner value
is composed last. This deliberately fixes the security ownership tag for this
legacy resource rather than allowing a shared tag input to override it. All nine
recorded common tags are preserved, yielding the ten-tag migrated state. The
module's other secrets still use their unchanged var.tags expressions.

CompanyId is not added to local.common_tags, module variables, provider defaults,
Google client credentials, Postmark, app secrets, or other resources. The secret
name/description and google_user_tokens_init secret-version resource remain
unchanged. No value, initialization, rotation or lifecycle behavior is edited.

Final tracked delta: **2 files, 8 insertions, 1 deletion**. Unrelated original
whitespace was preserved. The only additional file is this Markdown record.

## Source / verified-production semantic reconciliation

Verified token ARN:
`arn:aws:secretsmanager:us-east-1:358604342897:secret:togs-and-dogs-prod/google/user-tokens-0zvNfK`.

Existing production wiring maps module.iam.google_user_tokens_arn to
module.secrets.google_user_tokens_arn, whose output is exactly
aws_secretsmanager_secret.google_user_tokens.arn. That resource is the recorded
live token secret. This task does not introduce a hardcoded account ARN into
the Terraform source or change the resource identity.

Static assertions removed only the exact proposed insertion/merge and compared
both complete files against HEAD: all remaining source matched. The tag occurred
exactly once in the secrets module and within the exact user-token resource.
The module/output ARN wiring was also checked.

The saved v2 policy JSON plus the exact approved singleton statement, substituting
the recorded token ARN for the verified variable wiring, reproduces the saved
v3 canonical policy SHA-256:
`e4333ff54dbf1a9fe77b18d0a0a9e354e108c32843f282d1cfe7a78403e48474`.
This is static semantic reconstruction against independently verified evidence,
not an evaluated production Terraform plan or a fresh AWS policy read.

Previously source omitted both migrated properties, so reconciliation could
propose removal of the permission/tag. Source now explicitly declares both,
preventing those omissions from being a reason to revert S2A.2b. A later
separately approved plan must still verify actual source/state/production
alignment, provider normalization and absence of unrelated drift. No whole-main
deployment, zero-drift plan or production convergence is certified here.

## Local validation

Terraform executable located from repository release records:
`C:\Users\mattn\AppData\Local\Microsoft\WinGet\Packages\Hashicorp.Terraform_Microsoft.Winget.Source_8wekyb3d8bbwe\terraform.exe`.

Commands performed, relative to repository root unless noted:

1. `terraform fmt -check modules/iam/main.tf modules/secrets/main.tf`.
   Initial sandbox launch was access-denied; authorized elevated local execution
   worked and identified the secret expression's formatting. No AWS access.
2. `terraform fmt modules/secrets/main.tf` — formatted only the approved file.
3. `terraform fmt -check modules/iam/main.tf modules/secrets/main.tf` — PASS,
   also repeated after restoring unrelated original EOF whitespace.
4. `terraform -chdir=infra/prod validate -no-color` — PASS:
   `Success! The configuration is valid.` Existing installed modules/providers
   were used; no init, download, refresh, plan or apply. Validation environment
   disabled EC2 credential metadata and used a deliberately nonexistent AWS
   profile; Terraform logging was OFF and checkpoint checks disabled.
5. `python -m pytest tests/backend/test_cognito_email_sender_infrastructure.py -q`
   — 8 passed with a local pytest cache permission warning. These are existing
   static infrastructure safety tests, not runtime/provider tests.
6. Repeated with `-p no:cacheprovider` — **8/8 PASS**, no warning. No test edits.
7. Local exact-delta/resource-scope/wiring assertions and recorded-policy
   reconstruction — PASS. An initial ad hoc reverse-diff assertion had an
   incorrect replacement string; correcting that checker yielded the exact
   source comparison above, without changing the approved source delta.
8. `git diff --check` and the new record's whitespace/link checks — PASS.

No additional Terraform/test source changes were needed. Full root validate
passed; no production plan was required to establish source validity.

## Provider lock, state and generated-file checks

SHA-256 before/after local validation matched for both existing files:

| Local file | Unchanged SHA-256 |
| --- | --- |
| infra/prod/.terraform.lock.hcl | 4481E01E8C1DC7FCC5C0204A4EA19CBB8853C33152A65EBDB0D9C99A68009AA2 |
| infra/prod/.terraform/terraform.tfstate | 7DA2037320B274FD7A054F6B31B268483E15577AB0E61BE9D993B591FC6B105A |

Only hashes of the local backend metadata file were compared; its contents were
not printed. Remote/production state was not accessed. No provider lock/state
files changed or were generated; no Terraform initialization or packaging ran.
No tracked generated, runtime, application, test, or unrelated Terraform files
changed. Local pytest cache access failed in the initial run; the clean rerun
disabled that cache provider.

## Final scope and interlock

- AWS/production reads or writes: **ZERO**; no AWS CLI/SDK operations.
- Secret-value access, Google/provider calls, DynamoDB operations: **ZERO**.
- Terraform operations: local fmt/fmt-check/validate only, as recorded above.
- Terraform init/refresh/plan/apply, production state access: **NONE**.
- Runtime/application deployment, tenant-resolution/Mobile/Stripe/Ryan changes:
  **NONE**.
- Files staged: **NONE**; commits/pushes: **NONE**.
- Ending main HEAD/local origin/main unchanged at the starting SHA.
- Tracked unstaged modifications: only modules/iam/main.tf and
  modules/secrets/main.tf. Index and stash empty. Six intentional untracked
  review/evidence documents including this new record; prior five unchanged.

S2A.3 remains **NOT STARTED / BLOCKED** until source reconciliation is independently
reviewed and a later separately approved production plan confirms no unwanted
reversion or drift. S2B–S2E not started. S1 remains complete; F02 unresolved and
PTM-0 incomplete. Stop here: no commit, push, production plan or enforcement work.
