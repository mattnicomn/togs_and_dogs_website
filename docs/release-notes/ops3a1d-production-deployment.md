# OPS-3A.1D — Quote API Routes Production Deployment (Gate B apply)

Status: **DEPLOYED TO PRODUCTION / VERIFIED / COMPLETE.** Matthew-approved Gate B
apply of the exact reviewed saved Terraform plan executed successfully against the
production account (`358604342897`). All post-apply read-only verification passed.
No RC merge/push, no OPS-3A.2/3A.3, and no deferred-feature deployment occurred.

Deployment date: 2026-09-30.

References:
- Gate A plan review (tfvars-corrected): the reviewed saved plan
  `ops3a1d-clean-rc-tfvars-20261005.tfplan`.
- Route definitions: `docs/release-notes/ops3a1c-api-gateway-quote-routes-local-implementation.md` (commit `fcfdec2`).
- Handler integration: `docs/release-notes/ops3a1b-quote-handler-integration-local-implementation.md` (commit `a025154`).
- Quote contract: `docs/planning/petcare-hero-quote-contract.md` (approved 2026-10-03).

---

## Authoritative candidate

- Main / origin-main: `626f36bd0697608c58f8ddc60e5fc96f49737f56` (unchanged by this task).
- Clean RC branch: `release/ops3a1-clean-rc`, HEAD `4e391c1cd67db649571f29de9099bddb11eda92d` (unpushed).
- RC worktree: `C:\Users\mattn\AppData\Local\Temp\togs-ops3a1-clean-rc`.
- Terraform root: `<RC worktree>\infra\prod`.
- Terraform v1.14.8; providers aws v5.100.0, archive v2.7.1.
- Applied saved plan: `ops3a1d-clean-rc-tfvars-20261005.tfplan`.
- Saved-plan SHA256: `28c1a1be9ccf5d05bf4cc4a520d887eeca670585f3ebcb9865311f706c29b515` (size 171580).
- Prior rejected (tfvars-less) plan `ops3a1d-clean-rc-20261005.tfplan`
  (SHA256 `44d3252920249d6e1aa09fb1f75946869d16d3d10acd55f16668531e74cd773c`) was
  NOT applied; retained as rejected evidence.
- Authoritative backend package `source_code_hash`:
  `A1JZvJVtWgzfA90ZQHdEQOAp40GQqOxZgLH0mJFjr5c=`.

## Pre-apply gates (all PASS)

- Main `626f36b` == origin/main, 0/0, no tracked modifications, index empty, stash empty.
- RC `4e391c1` on `release/ops3a1-clean-rc`, tracked tree clean, index empty, stash empty, unpushed.
- RC-local `terraform.tfvars` present, gitignored, unstaged; size 433 and SHA256 equal
  to main's production tfvars (contents never read/displayed).
- AWS identity: account `358604342897` via profile `usmissionhero-website-prod`.
- Saved-plan identity: exact file, not overwritten, SHA256 `28c1a1be…`; distinct from the rejected plan.
- Final read-only inspection: `27 add / 14 change / 1 destroy`; 13 Lambdas change only
  `source_code_hash` + `last_modified` with ZERO environment-variable changes; 26
  quote/OPTIONS API Gateway creates; 1 deployment replacement; 1 stage update; forbidden-token scan 0 hits.

## Apply result

`terraform apply ops3a1d-clean-rc-tfvars-20261005.tfplan` — exit code 0 (~83s).

> Apply complete! Resources: 27 added, 14 changed, 1 destroyed.

- All 13 existing Lambdas modified in place (no recreation, no replacement).
- 4 quote resources created: `admin_quote` (id `d9mjkt`), `admin_quote_send` (id
  `w9byet`), `client_quotes` (id `m3u2nw`), `client_quote_id` (id `6nmh50`).
- Quote methods + integrations + OPTIONS/CORS created exactly as reviewed.
- API Gateway deployment replaced (new `wsmits`; prior deposed `atxpw3` destroyed); stage `prod` updated.
- One pre-existing, unrelated deprecation warning (`dynamodb_table` → `use_lockfile`),
  from the backend lock configuration; not introduced by this change.

## Post-apply verification (all PASS, read-only)

### Lambdas (13)
All of `admin, assign, cancellation, device, google_auth, intake, job, pet, platform,
postmark_webhook, review, ses_feedback, stripe_webhook`:
- `CodeSha256 = A1JZvJVtWgzfA90ZQHdEQOAp40GQqOxZgLH0mJFjr5c=`,
- `Runtime = python3.11`, expected handlers, role `togs-and-dogs-prod-lambda-exec`,
- `LastUpdateStatus = Successful`, `State = Active`, existing functions (not recreated).
- `admin`: `STRIPE_SECRET_KEY` remains PRESENT and non-empty (41 env keys); value never read/displayed.

### Quote API (REST API `a022yxuiue`)
- `PATCH /admin/requests/{requestId}/quote`, `POST /admin/requests/{requestId}/quote/send`,
  `GET /client/quotes/{requestId}` — all exist.
- All three business methods: `COGNITO_USER_POOLS` (authorizer `r0gk6r`), `AWS_PROXY` to the admin Lambda.
- OPTIONS/CORS present on all four quote resources (`NONE` + `MOCK`).
- Stage `prod` → deployment `wsmits`.

### Deferred-feature absence
- Production has exactly 13 Lambda functions; no `cognito_email_sender`,
  `platform_preview`, or `platform_onboarding` function/resource present.

### Terraform state convergence
- State records `source_code_hash = A1JZvJVtWgzfA90ZQHdEQOAp40GQqOxZgLH0mJFjr5c=`
  for all 13 Lambda resources; prior S1-era hash drift is converged by this apply.
- No state surgery (`terraform state rm/import`/manual edit) was performed.

## Git / artifact state

- Main `626f36b` == origin/main, no tracked modifications (this release note is a
  local, uncommitted documentation edit awaiting a separate commit decision).
- RC `4e391c1`, tracked tree clean, index empty, stash empty, unpushed.
- `terraform.tfvars`, both saved plans, and `backend.zip` remain local and gitignored.

## Explicitly out of scope (deferred / gated)

- OPS-3A.2 — client Accept/Decline mutation + `expected_revision`/409 + `ACCEPTED` → RequestStatus sync.
- OPS-3A.3 — web/mobile quote UI.
- AC-9 production deployment, deferred-feature deployment, Stripe live-mode/config
  changes, tenant-resolution changes, second tenant, Ryan testing, mobile distribution,
  OAuth runtime changes, RC push/merge — none performed.
- No production-data/test-data creation occurred.

## Resume point

- Production state: OPS-3A.1D DEPLOYED and VERIFIED. Quote routes live and Cognito-protected.
- Ending main commit: `626f36b` (unchanged). RC `4e391c1` (unpushed).
- Exact next recommended action: Matthew decision on (a) committing this release note
  and continuity updates, and (b) whether to push/merge the RC branch; then OPS-3A.2
  planning as a separate gated slice.
- Required approval: Matthew (documentation commit/push, RC push/merge, and any OPS-3A.2/3A.3 work).
