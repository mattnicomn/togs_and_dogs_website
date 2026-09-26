# PTM0-S2A.2d — Terraform convergence plan preflight

Date: 2026-09-04.

Disposition: **PTM0_S2A2D_TERRAFORM_PLAN_BLOCKED**

Status: **STOPPED BEFORE TERRAFORM / NO PLAN / NO PRODUCTION ACCESS**.

## Checkpoint and scope

Starting branch main; HEAD and local origin/main both
`2f78dc98c620db7bdf6d819e75678cbc93145795`.
Starting worktree clean; index and stash empty. The eight-file reviewed source
reconciliation commit is present. No source, configuration, state or lock file
was edited during this preflight.

Matthew authorizes plan-only convergence verification, minimum provider/state
reads, and explicitly prohibits secret-value access. That prohibition applies
to provider-internal reads as well as manually issued API calls; hiding output
would not make an otherwise forbidden read acceptable.

## Established planning workflow inspected, not executed

Local historical evidence:

- `scratch/ptm0_s1_plan/run_plan.py` and its 2026-09-03 plan record.
- `infra/prod/backend.tf`, `providers.tf`, `.terraform.lock.hcl`, and the current
  archive/Lambda wiring in `infra/prod/main.tf`.
- `modules/secrets/main.tf` and the S2A.2b/S2A.2c evidence.
- [S1 production closeout](../release-notes/ptm0-s1-production-deployment-acceptance.md).

The established S1 script uses Terraform 1.14.8, backend initialization,
validation, state pull, a refresh-enabled full saved plan, state locking, and
sanitized inspection. It is pinned to the old isolated RC and deployment
preconditions; it is not directly reusable for this new checkpoint.

Recorded executable exists locally at
`C:\Users\mattn\AppData\Local\Temp\codex-terraform-1.14.8\terraform.exe`.
It was not launched. Current lock-file selections are hashicorp/aws **5.100.0**
and hashicorp/archive **2.7.1**. No provider binary or backend was initialized or
executed in this task; these versions are local configuration/history evidence.

## Blocking secret-value access

Current configuration includes:
`module.secrets.aws_secretsmanager_secret_version.google_user_tokens_init`.
It declares `secret_string = "{}"` and `ignore_changes = [secret_string]`.
The previous full production plan record includes this managed secret-version
resource, so it cannot safely be assumed absent from the planning graph/state.

The locked AWS provider's version-specific source establishes the read path:
`resourceSecretVersionRead` calls `findSecretVersionByTwoPartKey`, which reaches
`conn.GetSecretValue`. Returned SecretString/SecretBinary are assigned into
resource state. Lifecycle ignore_changes does not bypass that read path.
Thus the established full refreshed plan is not compatible with the explicit
no-secret-value-access boundary. Sanitizing logs or marking attributes sensitive
does not remove the access.
[HashiCorp AWS provider v5.100.0 source](https://raw.githubusercontent.com/hashicorp/terraform-provider-aws/v5.100.0/internal/service/secretsmanager/secret_version.go).

No GetSecretValue, secret-version refresh, raw state pull, tfvars-content read,
plan/show command or saved-plan creation was performed. No claim about the
current secret payload or historical access is made by this preflight.

## Other planning-shape constraints, not observed drift

The repository root archive data source packages the current src/backend tree.
The recorded production package came from the isolated S1 RC, not current main.
Current main also declares independently gated platform-preview infrastructure.
This is a source/planning-scope concern, not evidence of any particular changed
resource or a fresh production discrepancy. A new safe convergence procedure
must explicitly address the deployed artifact/source baseline without silently
editing runtime files, substituting archives or deploying main wholesale.

The historical workflow also uses remote backend locking. No locking operation
was started here. Any revised strictly read-only workflow must explicitly
reconcile transient lock behavior with the requested no-production-write scope.

Neither `-refresh=false` nor a target-only plan would establish the requested
complete refreshed managed-resource convergence. Targeting may omit the
secret-version read but also omits required drift coverage; it must not be
presented as a full-plan PASS. No resource removal, state manipulation, provider
patch, IAM deny, temporary override or scope substitution was attempted.

## Requested evidence: availability

| Requested result | This task's evidence |
| --- | --- |
| AWS identity/account | Not freshly checked; account 358604342897 is the recorded expected target, not a new STS result |
| State serial/lineage | Not read; historical closeout records serial 519 / lineage 7235fddd-c101-fe62-7669-7b7b3d858955, not certified current |
| Plan add/change/destroy/replace | UNAVAILABLE, not zero: no plan ran |
| Complete changed-resource list/classifications | UNAVAILABLE; no plan-derived drift classification |
| IAM DescribeSecret reconciliation | Committed source preserves the reviewed addition; plan no-op NOT VERIFIED |
| Token CompanyId reconciliation | Committed source includes the resource-specific merge; plan no-op NOT VERIFIED |
| Other tags/secret replacement/unrelated resources | No changes made; refreshed no-op/drift status NOT VERIFIED |
| DynamoDB backfill/tenant creation | No operations performed; Option B retained; no plan result claimed |
| Lambda/API/Cognito/Stripe/notifications/frontend/workflow/networking/observability | No deployment or mutation performed; complete plan checks NOT VERIFIED |
| TENANT_RESOLUTION_MODE | Source untouched; no fresh production read or plan verification |
| Saved-plan path/hash | NONE |

There is no evidence here that either migrated property would be reverted, so
RECONCILIATION_DRIFT_FOUND would be unsupported. The correct disposition is a
pre-execution planning blocker, not reconciliation failure or convergence PASS.

## Scope accounting and next gate

- Exact Terraform commands performed: **NONE** (workflow text read only).
- AWS account/provider service/state access: **ZERO**.
- Public HashiCorp provider source read for API-behavior verification: **YES**.
- Production mutations, secret-value access, Google/provider business API calls:
  **ZERO**.
- Terraform init/refresh/plan/apply/state operations: **NONE**.
- Runtime/application edits or deployment: **NONE**.
- Files changed: only this new, untracked Markdown preflight record.
- Commits, pushes, staging: **NONE**.
- Ending HEAD/local origin/main unchanged; tracked worktree/index clean;
  stash empty; this one untracked evidence document. Whitespace/link checks pass.
- S2A.3 and S2B–S2E: **NOT STARTED**. F02 unresolved; PTM-0 incomplete.

Required next direction: separately review a planning approach that preserves
the no-secret-value-access boundary and explicitly states any excluded-resource
coverage, state handling, locking and deployed-artifact assumptions. A narrower
metadata-only convergence result is possible in principle but is not equivalent
to the full-plan acceptance requested here. Do not weaken the boundary, alter
source/state or start a substitute procedure automatically. Stop here.
