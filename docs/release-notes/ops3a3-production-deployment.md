# OPS-3A.3 — Client Quote UX Backend Production Deployment (Gate B apply)

Status: **DEPLOYED TO PRODUCTION / VERIFIED / COMPLETE.** Matthew-approved Gate B
apply of the exact reviewed saved Terraform plan (`ops3a3-production.tfplan`) executed
successfully against the production account (`358604342897`). All post-apply
verification passed (read-only). No RC merge/push, no OPS-3B, no deferred-feature
deployment, no AC-9 deployment, no mobile distribution, no Ryan testing, and no
production functional-test-data creation occurred.

Deployment date: 2026-10-06.

References:
- Gate A plan review: saved plan `ops3a3-production.tfplan`
  (`PETCARE_HERO_OPS3A3_GATE_A_PLAN_READY_FOR_MATTHEW_APPROVAL`).
- OPS-3A.3 backend DRAFT/SUPERSEDED visibility guard (`admin_handler.py`, commit `d33a7d2`).
- Prior production release: `docs/release-notes/ops3a2-production-deployment.md`.

---

## Authoritative candidate

- Main / origin-main: `936f0a364dbc52286fa89087a69412a8598ff956` (unchanged by this task).
- Clean deployment RC branch: `release/ops3a3-clean-rc`, HEAD
  `ce6b72414444511dd2ce36df023329943f255946` (local, unpushed, **not merged**).
- RC worktree: `C:\Users\mattn\AppData\Local\Temp\togs-ops3a3-clean-rc`.
- Terraform root: `<RC worktree>\infra\prod`. Providers aws v5.100.0, archive v2.7.1.
- Applied saved plan: `ops3a3-production.tfplan` (size 173,049).
- New authoritative backend package `source_code_hash`:
  `gBjdlXDUn0+0gHHyF/W5aKv35NROe81lsQZbBf4YR6I=` (prior production hash
  `6c9QCRC/swzv6BKPsi5YEnoqp0KJzpfjbXPxIHrW84g=`).

### RC lineage note (deployment-only; MUST NOT merge)
The RC was built from the deployed-equivalent baseline `cc55e21` (pre-AC-9) plus six
OPS-3A.2 cherry-picks (`d29d833`, `a025154`, `fcfdec2`, `626f36b`, `7e2fc59`, `df56e57`)
plus the OPS-3A.3 backend guard `d33a7d2`. The only runtime delta versus the deployed
OPS-3A.2 package (`6c9QCRC…`) is `src/backend/handlers/admin_handler.py` (DRAFT/SUPERSEDED
quote visibility guard → non-disclosing 404). It deliberately excludes AC-9 and later
main-only mobile/docs. **Main already contains the approved OPS-3A.3 implementation plus
unrelated later work and AC-9; the RC is a deployment-only artifact and must not be
merged into main.**

## Pre-apply gates (all PASS)

- Main `936f0a3` == origin/main; working tree clean except retained Gate A evidence
  (`infra/prod/_gatea_plan_out.txt`, untracked).
- RC `ce6b724` on `release/ops3a3-clean-rc`; tracked tree clean (only untracked local
  evidence/log artifacts); unpushed, not merged.
- RC-local `terraform.tfvars` present, gitignored, SHA256 equal to main's production
  tfvars `CBEFDBCEB7B0DAB31DF48947660EA43155852919A6E5EE21E02BD19D7A8CA258` (contents
  never read/displayed).
- AWS identity: account `358604342897` via profile `usmissionhero-website-prod`
  (assumed-role `AWSReservedSSO_AdministratorAccess_…/multi_account_user`).
- Immediate pre-apply baseline: 13 Lambdas on prior hash `6c9QCRC…`; admin
  State unverified-in-list / direct get-function-configuration = Active, Successful,
  `TENANT_RESOLUTION_MODE=multi`, Runtime python3.11; REST API `a022yxuiue`, stage
  `prod -> hhryhc`. No drift vs OPS-3A.2 records.
- Saved plan `ops3a3-production.tfplan` present (not re-generated). `terraform validate`:
  Success. `terraform init`: existing S3 backend, no state migration.
- Gate A plan forensic: `0 add / 13 change / 0 destroy`; all 13 are
  `aws_lambda_function.*` in-place changing only `source_code_hash` + `last_modified`;
  no environment/handler/runtime/role/API/stage/IAM/DynamoDB/Cognito/Secrets changes.

## Apply result

`terraform apply ops3a3-production.tfplan` — exit code 0.

> Apply complete! Resources: 0 added, 13 changed, 0 destroyed.

- All 13 existing Lambdas modified in place (no recreation, no replacement).
- No API Gateway resource/route/stage/deployment change (deployment remained `hhryhc`).
- One pre-existing, unrelated deprecation warning (`dynamodb_table` → `use_lockfile`),
  from the backend lock configuration; not introduced by this change.

## Post-apply verification (all PASS, read-only)

### Lambdas (13) — `LAMBDAS_ON_OPS3A3_HASH=13/13`
All of `admin, assign, cancellation, device, google_auth, intake, job, pet, platform,
postmark_webhook, review, ses_feedback, stripe_webhook`:
- `CodeSha256 = gBjdlXDUn0+0gHHyF/W5aKv35NROe81lsQZbBf4YR6I=` (identical across all 13),
- `State = Active`, `LastUpdateStatus = Successful` (verified per-function),
- `Runtime = python3.11`, `Architectures = [x86_64]`, handlers unchanged, role
  `togs-and-dogs-prod-lambda-exec` unchanged, per-function memory/timeout unchanged,
- `admin`: `TENANT_RESOLUTION_MODE = multi` unchanged; secret-bearing env present
  (values never read/displayed).
- Production Lambda count = 13; deferred-feature Lambda count = 0.

### Configuration-drift verification
No handler/runtime/architecture/memory/timeout/role/layers/VPC/env-name change on any
Lambda. `TENANT_RESOLUTION_MODE=multi` unchanged.

### API Gateway — `API_GATEWAY_CHANGED_BY_OPS3A3=NO`
- REST API remains `a022yxuiue`; stage `prod` remains on deployment `hhryhc` (identical
  pre/post apply).
- Quote routes still present: `/client/quotes`, `/client/quotes/{requestId}`,
  `/client/quotes/{requestId}/accept`, `/client/quotes/{requestId}/decline`,
  `/admin/requests/{requestId}/quote`, `/admin/requests/{requestId}/quote/send`.
- No unexpected route/resource/stage mutation.

### Terraform post-apply convergence
Read-only `terraform plan -detailed-exitcode` returned exit code 0 and
**"No changes. Your infrastructure matches the configuration."** No drift.

### AC-9 deployment status — `AC9_DEPLOYED=NO`
The deployed canonical artifact is the clean RC Terraform-generated `backend.zip`
(archive id `a1778bcca287a01041979083a6d5d2be8891b7e3`, identical in the saved plan and
the post-apply convergence refresh). Inside that package `handlers/google_auth_handler.py`
(SHA256 `B5D0EEBC…`) corresponds to the pre-AC-9 clean RC content with zero AC-9 markers;
`handlers/admin_handler.py` (SHA256 `A1228526…`) carries the OPS-3A.3 DRAFT/SUPERSEDED
guard. All 13 Lambdas carry the Gate A canonical hash `gBjdlXDUn0…`. No AC-9 code was
introduced.

### Non-mutating production verification
Read-only only: Lambda state/hash checks, Terraform convergence, API route/stage reads,
config presence, and a safe CloudWatch Errors metric check (admin: zero datapoints in the
observed window; no invocation triggered). No customer data read/displayed.

## Boundaries honored (NOT performed)

OPS-3A.3 deployment did NOT: run a fresh plan or any apply beyond the saved plan; run
targeted apply / direct `aws lambda update-function-code` / API Gateway deployment /
manual config change / destroy / workspace change / provider upgrade; create production
quote/request/client/booking test data; invoke Accept/Decline; create a second tenant;
change `TENANT_RESOLUTION_MODE`; change Stripe/payment state or activate live Stripe;
perform AWS Organization migration; deploy AC-9; or activate deferred features. No
mobile build / TestFlight / App Store / Google Play / Expo distribution and no Ryan
testing occurred.

- `FUNCTIONAL_PRODUCTION_TEST_AUTHORIZED=NO`
- `MOBILE_DISTRIBUTION_AUTHORIZED=NO`
- `RYAN_TESTING_AUTHORIZED=NO`
- `AWS_ORG_MIGRATION_IN_SCOPE=NO`

## Rollback readiness

- Rollback source commit: `95bb45837a3b7b31432f954a8d3328884b6d71b2` (OPS-3A.2
  deployed-equivalent RC tip).
- Rollback hash: `6c9QCRC/swzv6BKPsi5YEnoqp0KJzpfjbXPxIHrW84g=`.
- Not required: apply succeeded, 13/13 on the new hash, Active/Successful, zero drift.

## Git / artifact state

- Main `936f0a3` == origin/main; only this documentation closure is added (left local/
  unstaged for review).
- RC `ce6b724`, tracked tree clean, unpushed, not merged, not deleted — retained.
- `terraform.tfvars`, `backend.zip`, the saved plan, and the apply/convergence logs
  remain local to the RC worktree and gitignored.

## Resume point

- Production state: OPS-3A.3 DEPLOYED and VERIFIED. Client quote UX backend
  (DRAFT/SUPERSEDED non-disclosing visibility guard) is live; backend
  `CodeSha256 = gBjdlXDUn0+0gHHyF/W5aKv35NROe81lsQZbBf4YR6I=` on all 13 Lambdas.
- No production functional testing performed (infrastructure/runtime verification only).
- Mobile distribution remains NOT authorized; Ryan testing remains NOT authorized.
- Functional production test of DRAFT → client GET → 404 remains separately gated
  (`FUNCTIONAL_PRODUCTION_TEST_AUTHORIZED=NO`).
- Required approval: Matthew for any functional production testing, mobile distribution,
  Ryan testing, OPS-3B, or RC cleanup.

Disposition: **`PETCARE_HERO_OPS3A3_PRODUCTION_DEPLOYED_VERIFIED`**.
