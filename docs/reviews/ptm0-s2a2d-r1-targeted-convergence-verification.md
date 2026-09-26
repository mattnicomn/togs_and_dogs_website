# PTM0-S2A.2d-R1 — Targeted Terraform convergence verification

Date: 2026-09-04.

Disposition: **PTM0_S2A2D_TARGETED_TERRAFORM_CONVERGENCE_PASS**

**This targeted plan proves only convergence for the S2A.2 IAM policy and Google
user-token secret. It does NOT certify global Terraform no-drift, unrelated
infrastructure convergence, the secret-version resource, or the remainder of
the 431+ managed-resource configuration.**

## Authority and starting checkpoint

Matthew explicitly authorized normal-refresh targeting of exactly the two S2A
resources, with metadata-only dependencies, no secret-value access and no apply.
The [prior full-plan blocker](ptm0-s2a2d-terraform-convergence-plan-preflight.md)
remains valid for full refreshed planning; this exceptional targeted approval
does not remove that concern.

Starting branch main; HEAD and local origin/main:
`2f78dc98c620db7bdf6d819e75678cbc93145795`.
Tracked worktree clean, index/stash empty. The prior blocker record was the only
untracked file. No tracked source change was made.

## Pre-plan dependency and secret-access safety gate

Static review found this exact managed-resource closure:

| Address | Why included | Provider read behavior |
| --- | --- | --- |
| module.iam.aws_iam_policy.google_secrets_access | Explicit target | IAM policy/version metadata |
| module.secrets.aws_secretsmanager_secret.google_user_tokens | Explicit target and IAM resource reference | Secret metadata and resource policy |
| module.secrets.aws_secretsmanager_secret.google_client_creds | Existing IAM statement references its ARN | Secret metadata and resource policy |
| module.secrets.aws_secretsmanager_secret.postmark_token | Existing IAM statement references its ARN | Secret metadata and resource policy |

The policy expression references only name_prefix and the three secret ARN
variables. Existing module inputs/outputs trace each ARN to its corresponding
secret resource. Other IAM module arguments feed other resources and are not
dependencies of this policy. Resource naming/common tags depend on ordinary
configuration variables; the default AWS provider supplies shared tags. There
is no module-wide depends_on expanding this closure.

`module.secrets.aws_secretsmanager_secret_version.google_user_tokens_init`
depends on the user-token secret, not vice versa. No selected output/resource
references the secret version. App secrets, role attachments, Lambda resources,
archive data source, API and all other managed resources are outside the closure.

Locked provider source review established that the secret-resource read uses
DescribeSecret and GetResourcePolicy, not value retrieval. The IAM resource read
uses GetPolicy/GetPolicyVersion and metadata tags. This distinguishes a
Secrets Manager secret resource from the excluded secret-version resource.
Sources: [AWS provider 5.100.0 secret resource](https://raw.githubusercontent.com/hashicorp/terraform-provider-aws/v5.100.0/internal/service/secretsmanager/secret.go),
[AWS provider 5.100.0 IAM policy resource](https://raw.githubusercontent.com/hashicorp/terraform-provider-aws/v5.100.0/internal/service/iam/policy.go).

The gate was established before any production Terraform operation. The runner
rechecked the policy-variable reference set and absence of blanket depends_on.
During execution it recorded refresh_start/refresh_complete addresses and enforced
the exact four-address allowlist, stopping on any unexpected address. Actual
refresh events matched the closure exactly. No secret-version or archive/runtime
refresh occurred.

**GetSecretValue was not invoked by this targeted workflow.** Evidence is the
complete observed resource-refresh set combined with the locked provider read
paths above; no SDK debug log, raw request/response payload or credential trace
was captured. This is not represented as an independent CloudTrail/wire audit.
GetSecretValue appearing as text inside the unchanged IAM policy is a permission
declaration, not an API invocation. Secret values returned/exposed: ZERO.

## Backend, identity, versions and state consistency

- Fresh STS account verification: **358604342897**.
- Profile: usmissionhero-website-prod; default AWS region us-east-1.
- Terraform version: **1.14.8**, windows_amd64.
- Provider selections: **hashicorp/aws 5.100.0**, **hashicorp/archive 2.7.1**.
  Archive provider selected in lock configuration, but no archive data source read.
- Established backend: S3 bucket togs-and-dogs-358604342897-us-east-1-tfstate,
  key prod/terraform.tfstate. Workspace: **default**.
- State serial before/after: **519 / 519**.
- Lineage before/after: **7235fddd-c101-fe62-7669-7b7b3d858955**.
- S3 object ETag and VersionId also identical before/after (recorded in sanitized
  machine evidence). No remote state persistence or version change occurred.

The helper read only the leading state header until serial/lineage, then closed
the stream before outputs/resources. No raw state was printed or separately
dumped. Terraform itself necessarily loads existing backend state for planning;
the saved binary can contain sensitive existing state/variables and must stay
private/local/ignored. Neither show view was printed raw or saved as raw JSON.
Only allowlisted metadata/resource outcomes were extracted for review.

To honor ZERO production writes, the plan used **-lock=false** rather than write
backend locks. The normal refresh remained enabled. State identity was compared
before/after to detect concurrent backend changes; this is not an exclusive lock
or guarantee against unrelated out-of-band resource changes. Any changed state
identity would have blocked a pass. No backend initialization was needed.

## Exact Terraform commands

Executable:
`C:\Users\mattn\AppData\Local\Temp\codex-terraform-1.14.8\terraform.exe`.

Working directory for all commands: repository `infra/prod`.

1. `terraform version -json`
2. `terraform workspace show`
3. Targeted command (absolute saved path below):

```text
terraform plan -input=false -no-color -json -detailed-exitcode -refresh=true -lock=false -parallelism=1 -target=module.iam.aws_iam_policy.google_secrets_access -target=module.secrets.aws_secretsmanager_secret.google_user_tokens -out=C:\Users\mattn\OneDrive\Desktop\togs_and_dogs_website\scratch\ptm0_s2a2d_r1\s2a2d-r1-targeted-convergence-20260904.tfplan
```

4. `terraform show -no-color <absolute saved-plan path>`
5. `terraform show -json <absolute saved-plan path>`
6. Repeated `terraform show -json <absolute saved-plan path>` for final sanitized
   stored-state drift and tag inspection; this did not refresh production.

Existing production terraform.tfvars was consumed normally by Terraform, not
printed or inspected for its values. TF_LOG/TF_CLI_ARGS overrides were removed;
checkpoint checks disabled, TF_INPUT=0, TF_IN_AUTOMATION=1, TF_WORKSPACE=default,
EC2 metadata credential lookup disabled. No init, full plan, refresh=false,
state push, apply, provider update or manual AWS mutation occurred.

## Plan and reconciliation results

Plan started 2026-09-04T12:58:25.779902Z; core inspection completed
2026-09-04T12:58:34.000574Z. Plan exit **0**. Human-readable show confirmed
**No changes**. One warning diagnostic was observed during exceptional targeting;
no error diagnostic occurred. Raw diagnostic payloads were not persisted.

Summary: **0 add / 0 change / 0 destroy / 0 replace**.
Complete planned changed-managed-resource list: **EMPTY**.

All four resources in the closure have `actions=[no-op]`, empty replacement
paths and identical refreshed before/after values. Both dependency secrets are
also no-op; no CompanyId is present on them.

IAM policy result:

- Exact verified v3 semantics retained, canonical policy hash
  `e4333ff54dbf1a9fe77b18d0a0a9e354e108c32843f282d1cfe7a78403e48474`.
- Existing Google client/token Get/Put and Postmark statements unchanged.
- Separate DescribeSecret Allow remains scoped to the exact approved user-token
  ARN; no wildcard or runtime TagResource/UntagResource addition.

User-token secret result:

- ARN remains
  `arn:aws:secretsmanager:us-east-1:358604342897:secret:togs-and-dogs-prod/google/user-tokens-0zvNfK`.
- CompanyId=tog_and_dogs retained; all nine original common tags preserved.
- Ten tags; before/after equal; no replacement, tag removal or config change.
- Shared/common tags and unrelated secret source remain unchanged.

### Stored state versus refreshed metadata (not planned writes)

Terraform reports two expected resource_drift entries relative to the older
persisted state: IAM `policy`, and token-secret `tags.CompanyId` /
`tags_all.CompanyId`. These are the already approved S2A.2b manual changes,
not regression, unexpected drift, or pending Terraform resource updates.
After refresh, source matches both live post-migration values and plans no-op.
The updated observations were not persisted to remote state because no apply
was run. No unrelated dependency/resource change surfaced in this closure.

## Saved artifacts and local hygiene

Saved plan:
`C:\Users\mattn\OneDrive\Desktop\togs_and_dogs_website\scratch\ptm0_s2a2d_r1\s2a2d-r1-targeted-convergence-20260904.tfplan`

SHA-256:
`3DA0755698C0AB254937C0E10D67735B10AD7ACD96DDB6F003713C9F867F0400`.

Other new ignored local files in the same directory:

- run_targeted_plan.py — bounded orchestration/allowlist script; no apply path.
- sanitized-plan-evidence.json — machine-readable outcomes and metadata only.
- sanitized-human-show.txt — safe human-show outcome/coverage summary.

This Markdown evidence is the only new untracked repository record in this turn;
the previous blocker record remains unchanged/untracked. No raw provider logs
or raw plan JSON were created. The binary plan must not be published or applied
merely because it is saved; no apply is authorized.

Before/after hashes matched for infra/prod/.terraform.lock.hcl,
infra/prod/.terraform/terraform.tfstate (local backend metadata), and
infra/prod/backend.zip. No runtime packaging, provider-lock/state change or
tracked source edit occurred. Git diff/link/whitespace checks passed.

Production mutations: **ZERO**, including backend lock writes.
Secret-value API access/exposure: **ZERO**. Google/provider business APIs:
**ZERO**. Terraform apply: **NO**. DynamoDB writes/tenant creation/backfill: **ZERO**.
No runtime/application deployment or changes to tenant-resolution settings.

No staging, commits or pushes. Ending main HEAD/local origin/main remain
`2f78dc98c620db7bdf6d819e75678cbc93145795`; tracked worktree/index clean, stash
empty; two untracked review records plus the ignored local artifacts above.

## Coverage and handoff

Only the two S2A security resources and their necessary metadata dependencies
were assessed. No conclusion about excluded API/Lambda/Cognito/Stripe/notification/
frontend/workflow/network/observability resources is implied. The secret-version
resource remains explicitly excluded and unverified.

The full-plan secret-value limitation remains a separate infrastructure/tooling
concern. Under Matthew's R1 approval it is not itself an S2A.3 blocker if the
targeted convergence evidence passes independent review. S2A.3 is nevertheless
**NOT STARTED** here; independent review and subsequent implementation authority
remain required. S2B–S2E not started; F02 unresolved; PTM-0 incomplete. Stop.
