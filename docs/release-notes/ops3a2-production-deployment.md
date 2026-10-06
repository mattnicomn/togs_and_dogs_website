# OPS-3A.2 — Client Quote Accept / Decline Production Deployment (Gate B apply)

Status: **DEPLOYED TO PRODUCTION / VERIFIED / COMPLETE.** Matthew-approved Gate B
apply of the exact reviewed saved Terraform plan executed successfully against the
production account (`358604342897`). All post-apply verification passed (read-only).
No RC merge/push, no OPS-3A.3, no deferred-feature deployment, no AC-9 deployment, and
no production functional-test-data creation occurred.

Deployment date: 2026-10-05.

References:
- Gate A plan review: saved plan `ops3a2-clean-rc-20261005.tfplan`.
- OPS-3A.2A backend Accept/Decline (commit `7e2fc59`).
- OPS-3A.2B quote Accept/Decline API routes (commit `df56e57`).
- Contract: `docs/planning/petcare-hero-quote-contract.md` — "OPS-3A.2 — Client
  Accept / Decline — APPROVED BY MATTHEW (2026-10-05)".
- Prior production release: `docs/release-notes/ops3a1d-production-deployment.md`.

---

## Authoritative candidate

- Main / origin-main: `df56e5771a79e5ad5ae871c506ec13a6c381378b` (unchanged by this task).
- Clean deployment RC branch: `release/ops3a2-clean-rc`, HEAD
  `95bb45837a3b7b31432f954a8d3328884b6d71b2` (local, unpushed, **not merged**).
- RC worktree: `C:\Users\mattn\AppData\Local\Temp\togs-ops3a2-clean-rc`.
- Terraform root: `<RC worktree>\infra\prod`. Terraform v1.14.8; providers aws v5.100.0, archive v2.7.1.
- Applied saved plan: `ops3a2-clean-rc-20261005.tfplan`.
- Saved-plan SHA256: `350c9e9fa848810235d22cb243d15c75db546c61b1e1929ca3d62861b304e041` (size 171530).
- New authoritative backend package `source_code_hash`:
  `6c9QCRC/swzv6BKPsi5YEnoqp0KJzpfjbXPxIHrW84g=` (prior production hash
  `A1JZvJVtWgzfA90ZQHdEQOAp40GQqOxZgLH0mJFjr5c=`).

### RC lineage note (deployment-only; MUST NOT merge)
The RC was built from the deployed-equivalent baseline `cc55e21` plus six cherry-picks
(`d29d833` quote contract, `a025154` handler, `fcfdec2` API routes, `626f36b` Terraform
hygiene, `7e2fc59` OPS-3A.2A backend, `df56e57` OPS-3A.2B API routes). It deliberately
excludes AC-9 and later main-only mobile/docs. **Main already contains the approved
OPS-3A.2 implementation plus unrelated later work and AC-9; the RC is a deployment-only
artifact and must not be merged into main.**

## Pre-apply gates (all PASS)

- Main `df56e57` == origin/main, 0/0, no tracked modifications, index empty, stash empty.
- RC `95bb458` on `release/ops3a2-clean-rc`, tracked tree clean, unpushed, origin has no RC branch.
- RC-local `terraform.tfvars` present, gitignored, unstaged; size 433 and SHA256 equal
  to main's production tfvars (contents never read/displayed).
- AWS identity: account `358604342897` via profile `usmissionhero-website-prod`.
- Saved-plan identity: exact file, size `171530`, SHA256 `350c9e9f…` (did not overwrite OPS-3A.1D plans).
- `terraform validate`: Success. `terraform init`: existing S3 backend configured, no state migration.
- Final read-only forensic recheck: `15 add / 14 change / 1 destroy`; 13 Lambdas change
  only `source_code_hash` + `last_modified` with ZERO environment-variable changes;
  2 quote-action resources + methods + integrations + OPTIONS/CORS; 1 deployment
  replacement; 1 stage update; forbidden-token scan 0 hits.

## Apply result

`terraform apply ops3a2-clean-rc-20261005.tfplan` — exit code 0 (~84s).

> Apply complete! Resources: 15 added, 14 changed, 1 destroyed.

- All 13 existing Lambdas modified in place (no recreation, no replacement).
- 2 quote-action resources created: `client_quote_accept` (id `s08tkp`),
  `client_quote_decline` (id `bamqgq`) — children of the existing
  `/client/quotes/{requestId}` resource (no duplicate parent).
- Quote POST methods + AWS_PROXY integrations + OPTIONS/CORS created exactly as reviewed.
- API Gateway deployment replaced (new `hhryhc`; prior deposed `wsmits` destroyed); stage `prod` updated.
- One pre-existing, unrelated deprecation warning (`dynamodb_table` → `use_lockfile`),
  from the backend lock configuration; not introduced by this change.

## Post-apply verification (all PASS, read-only)

### Lambdas (13)
All of `admin, assign, cancellation, device, google_auth, intake, job, pet, platform,
postmark_webhook, review, ses_feedback, stripe_webhook`:
- `CodeSha256 = 6c9QCRC/swzv6BKPsi5YEnoqp0KJzpfjbXPxIHrW84g=` (identical across all 13),
- `Runtime = python3.11`, handlers unchanged, role `togs-and-dogs-prod-lambda-exec` unchanged,
- `LastUpdateStatus = Successful`, `State = Active`, existing functions (not recreated),
- ZERO environment-variable changes.
- `admin`: `STRIPE_SECRET_KEY` remains PRESENT and non-empty (41 env keys); value never read/displayed.
- Production Lambda count = 13; deferred-feature Lambda count = 0.

### Quote Accept/Decline API (REST API `a022yxuiue`)
- `POST /client/quotes/{requestId}/accept` (resource `s08tkp`) — exists.
- `POST /client/quotes/{requestId}/decline` (resource `bamqgq`) — exists.
- Both business methods: `COGNITO_USER_POOLS` (existing authorizer `r0gk6r`), `AWS_PROXY`
  to the existing admin Lambda.
- OPTIONS present on both resources: authorization `NONE`, integration `MOCK` (CORS).

### API deployment / state convergence
- New API Gateway deployment `hhryhc`; prior `wsmits` replaced/destroyed; stage `prod -> hhryhc`.
- Terraform state records `source_code_hash = 6c9QCRC/swzv6BKPsi5YEnoqp0KJzpfjbXPxIHrW84g=`
  for all 13 Lambda resources; the 2 new route resources + methods + integrations are
  present in state; no deferred-feature resource appeared. Verified via read-only
  `terraform state list`/`state show` (no new plan, no apply, no state surgery).

### AC-9 isolation (NOT deployed)
OPS-3A.2 production deployment **continued to EXCLUDE AC-9 runtime changes.** The clean
RC's `src/backend/handlers/google_auth_handler.py` matched the pre-AC-9 deployed-equivalent
baseline (`cc55e21`) and differs from main's AC-9 version. The AC-9 commits remain on
`main` but were **not** part of this production RC and are **not deployed**. The 13-Lambda
`source_code_hash` change carries only the approved quote accept/decline code, not AC-9.

## Boundaries honored (NOT performed)

OPS-3A.2 deployment did NOT: create production quote/request test data; invoke
Accept/Decline against real customer data; create payment transactions; invoke live
Stripe behavior; enable `TENANT_RESOLUTION_MODE=multi`; create a second tenant; alter
Ryan testing; alter App Store/TestFlight/Google Play; deploy AC-9; or activate deferred
features (`cognito_email_sender`, `platform_preview`, `platform_onboarding`). Stripe
remains sandbox-only; Ryan testing remains paused; public mobile-store publishing
remains deferred.

## Git / artifact state

- Main `df56e57` == origin/main; only this documentation closure is added on top.
- RC `95bb458`, tracked tree clean, unpushed, not merged, not deleted — retained pending
  separate RC-cleanup authorization.
- `terraform.tfvars`, `backend.zip`, and the saved plan remain local to the RC worktree
  and gitignored.

## Resume point

- Production state: OPS-3A.2 DEPLOYED and VERIFIED. Client quote Accept/Decline backend
  + Cognito-protected API routes are live; backend `CodeSha256 =
  6c9QCRC/swzv6BKPsi5YEnoqp0KJzpfjbXPxIHrW84g=`.
- No production functional testing performed (infrastructure/runtime verification only).
- Next recommended sequence (separately gated): (1) RC cleanup / housekeeping, then
  (2) OPS-3A.3 mobile-first client quote UX planning/implementation. Neither started here.
- Mobile UI for quote acceptance does **not** exist yet (OPS-3A.3).
- Required approval: Matthew for RC cleanup and for any OPS-3A.3 work.
