# Workstream 3-C2 — MANUAL_EXTERNAL Payment API Route: Production Deployment (Technical Complete, Functional Acceptance Pending)

**Date:** 2026-10-24
**Disposition:** `W3C2_TECHNICAL_DEPLOYMENT_COMPLETE_FUNCTIONAL_ACCEPTANCE_PENDING`
**Checkpoint:** `main == origin/main == ef39b178d2ac3b255246174b739952892fd0bea1`
**Account:** `358604342897` (profile `usmissionhero-website-prod`)

`W3C2_DEPLOYED=YES`; `W3C2_RUNTIME_ENABLED=YES`; `W3C2_FUNCTIONAL_ACCEPTANCE=PENDING`;
`W3C1_TRANSACTWRITE_IAM_PRESENT=YES`; `W3C2_UNTARGETED_APPLY_ACTIVATES_W1=YES`;
`W1_PRODUCTION_RELEASE_AUTHORIZED=NO`.

## Summary

The W3-C2 MANUAL_EXTERNAL payment API route —
`POST /admin/requests/{requestId}/external-payment` — is now **technically deployed and
runtime-enabled in production**. It is a thin, Cognito-gated, owner/admin HTTP adapter over
the merged W3-C1 service `common.manual_external_adapter.record_external_payment`, which
remains the single source of truth for authorization, tenant/request ownership,
canonical-cent validation, idempotency/conflict classification, the atomic DynamoDB
`TransactWriteItems` write, the authoritative `PAYMENT_EVENT`, and the post-commit audit
entry. No business logic is duplicated by the route.

**Functional acceptance is explicitly PENDING:** no live external-payment settlement has
been recorded and no production payment transaction has been performed. The first
end-to-end exercise is a separate, owner-gated step to be run with controlled, non-customer
data.

## How it was released — three separately-authorized targeted applies

Released from `main` (PR #33 route source + PR #34 docs + PR #35 fingerprint + invoke-ARN
decoupling, all squash-merged) via **targeted** Terraform applies only. An untargeted apply
was never run (it would sweep all 13 Lambdas and activate W1).

### Phase A — IAM grant
`terraform apply -target=module.iam.aws_iam_policy.dynamodb_access` →
`Apply complete! 0 added, 1 changed, 0 destroyed`.
Added exactly `dynamodb:TransactWriteItems` to `togs-and-dogs-prod-dynamodb-access` with no
Resource/ARN widening. Policy default version **v2 → v3**; **v2 retained** as rollback.

### Phase B — admin Lambda code
Pre-apply, the deployed admin package was downloaded (read-only `get-function` presigned
URL) and its ZIP SHA-256 verified **equal** to the live `CodeSha256 W6cqyudl…` — the true
rollback artifact (admin has no published versions; Terraform rebuilds `main` to
`1EPLbycK…` and cannot regenerate the old artifact). Retained in a durable,
access-restricted, non-repo location + an independent copy with a recovery runbook.
`terraform apply -target=aws_lambda_function.admin` →
`Apply complete! 0 added, 1 changed, 0 destroyed`.
Admin `source_code_hash W6cqyudl… → 1EPLbycK…`; only `source_code_hash`/`last_modified`
changed. Because all Lambdas build from one shared backend ZIP, this admin artifact now
**includes the W3-C1 MANUAL_EXTERNAL adapter and the W3-B provider-neutral payment-domain
code it imports** — present and reachable only via the admin Lambda's W3-C2 route. The
other 12 Lambdas were **not** updated (remain `W6cqyudl…`), so **W1 intake validation stays
undeployed** and that W3-B/W3-C1 path stays dormant on them.

### Phase C — API route + deployment + stage
`terraform apply` of the 5 named targets
(`module.api.aws_api_gateway_resource.admin_external_payment`,
`module.api.aws_api_gateway_method.post_admin_external_payment`,
`module.api.aws_api_gateway_integration.post_admin_external_payment_lambda`,
`module.api.aws_api_gateway_deployment.main`, `module.api.aws_api_gateway_stage.main`) →
`Apply complete! 8 added, 1 changed, 1 destroyed`.
Added the `external-payment` resource (`/admin/requests/{requestId}/external-payment`,
resource id `l47lcy`), its POST method (`authorization=COGNITO_USER_POOLS`, authorizer
`r0gk6r`) with `AWS_PROXY` integration to the admin invoke ARN, the OPTIONS method
(`authorization=NONE`) + MOCK integration + method/integration responses for CORS, and the
new deployment. The `prod` stage cut over to the new deployment; the old deployment was
destroyed (create-before-destroy). **Zero Lambda updates, zero IAM changes, zero
existing-integration URI changes** — the PR #35 invoke-ARN decoupling isolated the route
apply from the Lambda fleet.

## Verified live post-deployment state

- **IAM:** `togs-and-dogs-prod-dynamodb-access` default **v3**, includes
  `dynamodb:TransactWriteItems`; **v2 retained**.
- **Admin Lambda:** `CodeSha256 1EPLbycKQSFOwH58Y7c5xGU+eG/Ht8qNS7pxkoFdBKk=`,
  Active/Successful.
- **Other 12 Lambdas:** all on `W6cqyudl…` (W1 dormant).
- **API Gateway `a022yxuiue`:** stage `prod` → deployment **`n40vai`**; route `l47lcy`
  live with Cognito POST + NONE OPTIONS; integration `AWS_PROXY` →
  `togs-and-dogs-prod-admin`.
- **Terraform convergence:** targeted `plan` after each phase = **No changes** (zero drift).
- **Monitoring:** in the first hour, **no CloudWatch error datapoints were observed** for
  the admin Lambda (Errors, Throttles) or API prod (`5XXError`) — consistent with a
  deployed-but-not-yet-exercised route; **not** evidence of functional acceptance
  (`W3C2_FUNCTIONAL_ACCEPTANCE=PENDING`).
- `TENANT_RESOLUTION_MODE=multi` unchanged.

## Hash reconciliation

- `1EPLbycK…` — current deployed admin artifact (built from `main` `ef39b178`); live on
  `aws_lambda_function.admin` only.
- `W6cqyudl…` — pre-W3-C2 deployed baseline (PR #22 privacy release); still on the other 12
  Lambdas; the retained admin rollback artifact.
- `58C9Bl…` — a pre-PR#34/#35 planning estimate of the `main` backend build; **never
  deployed**, superseded by `1EPLbycK…`.

## Rollback readiness

- **IAM (Phase A):** `set-default-policy-version --version-id v2`.
- **Admin Lambda (Phase B):** `update-function-code --zip-file fileb://<durable>\admin-rollback-W6cqyudl.zip`
  (pre-check base64 SHA == `W6cqyudl…`), then targeted Terraform reconciliation; never
  untargeted.
- **API (Phase C):** prior deployment `hhryhc` was destroyed by the replacement and is NOT
  a stage-repoint target. Retained deployments `72m3x0`/`z6edb6`/`o8ofzg` predate several
  intervening API releases and are **not assumed equivalent** to pre-W3-C2 behavior.
  Preferred recovery is a forward-fix or a fresh targeted redeploy of the corrected config
  (which preserves all unrelated routes), not repointing the stage to an old deployment.
- After any emergency out-of-band change, reconcile Terraform state with a **targeted** plan
  and never resolve drift via an untargeted apply.

## Automated-evidence checkpoint (2026-10-26)

This records **LOCAL OFFLINE AUTOMATED TEST EVIDENCE** only (mock-only; no AWS, no network).
It is **not a new release and not functional acceptance** — the W3-C2 production deployment
of 2026-10-24 remains the latest technical deployment, and the deployed admin artifact
(`1EPLbycK…`, stage `n40vai`) is unchanged by this checkpoint.

As of `main == 617b587f0cad3ffe478fdbce9857cc8df833a3b7`, the four offline suites report
**320 tests passing, 0 failures**:

- W3-C1 MANUAL_EXTERNAL adapter — **60 passed**
- W3-B provider-neutral payment domain — **174 passed**
- Quote contract — **50 passed**
- W3-C2 handler route (`POST /admin/requests/{requestId}/external-payment`) — **36 passed**

PR #38 (squash-merged to `main` as `617b587`) added three tests closing the
previously-uncovered post-commit audit path on the adapter (W3-C1 suite 57 → 60):

- `test_audit_entry_written_on_created` — exactly one `EXTERNAL_PAYMENT_RECORDED` audit
  call on a successful `RECORD_CREATED`, with REQUEST identity + previous/new status.
- `test_audit_failure_is_non_fatal` — an audit-sink failure does not fail the committed
  settlement, re-apply money, or bump the revision (and the audit path is asserted reached).
- `test_audit_not_written_on_duplicate_replay` — an idempotent duplicate emits no second
  audit event.

**`W3C2_FUNCTIONAL_ACCEPTANCE=PENDING` is unchanged.** The following remain UNVERIFIED:
live external-payment settlement end-to-end; the runtime IAM `dynamodb:TransactWriteItems`
grant proven by an authorized write; Cognito authorizer edge behavior (401 unauthenticated /
OPTIONS open); and API Gateway rollback equivalence (prior deployment `hhryhc` was destroyed,
and retained deployments are not assumed equivalent).

## Remaining gates

- **Functional acceptance** (live settlement) — separate owner authorization required;
  controlled non-customer data only. `RYAN_TESTING_AUTHORIZED=NO`; no production test data;
  Stripe sandbox-only.
- **W1 intake behavior remains undeployed** (the `intake` Lambda is unchanged). W1
  (PR #26/#27) stays merged-not-deployed and dormant on all 12 non-admin Lambdas. W3-B
  (PR #29) is likewise undeployed on those 12, though its payment-domain code now ships
  inside the admin artifact as a W3-C1 dependency (active only via the admin W3-C2 route).
  Any untargeted apply would activate W1 and promote that path fleet-wide — prohibited
  without separate owner authorization + W1 acceptance.
- Future provider adapters (Stripe Connect Direct, W3-D1 UI) not started.

See also: [W3-C1 MANUAL_EXTERNAL adapter](w3c1-manual-external-adapter.md),
[W3-C1 TransactWriteItems IAM plan](w3c1-transactwrite-iam-plan.md),
and the project continuity doc `docs/project-continuity/current-state.md`
(2026-10-24 deployment-complete section).

---

## Serialization-fix deployment checkpoint (2026-10-27)

**Disposition:** `W3C2_SERIALIZATION_FIX_DEPLOYED_TECHNICAL_AND_INFRA_VERIFIED_FUNCTIONAL_ACCEPTANCE_PENDING`
**Checkpoint:** `main == origin/main == 263b3e744a2815f0d9da781b2589ce643d2750f6` (PR #40 squash-merged)
**Account:** `358604342897` (profile `usmissionhero-website-prod`)

This records the production deployment of the W3-C1/W3-C2 `TransactWriteItems`
serialization-boundary correction (PR #40) to the admin Lambda **only**. It does **not**
change the API route, IAM, or any other Lambda, and it is **not** functional acceptance.

### (a) Technical deployment — COMPLETE
- `terraform apply -target=aws_lambda_function.admin` of a reviewed `0 add / 1 change / 0 destroy`
  plan. Admin `source_code_hash 1EPLbycKQSFOwH58Y7c5xGU+eG/Ht8qNS7pxkoFdBKk= →
  GlA3mUtq3O0RJcdc3i2MQjwcbuo8aiv52ACvacQH99o=`; only `source_code_hash`/`last_modified`
  changed (handler/role/runtime/memory/timeout/env unchanged). Apply result:
  `Apply complete! Resources: 0 added, 1 changed, 0 destroyed.`
- The candidate artifact hash `GlA3…` was independently reproduced offline from `main`
  `263b3e7` using the pinned `hashicorp/archive 2.7.1` packager before apply, then matched
  exactly by the Terraform-computed `source_code_hash` at plan and apply time.

### (b) Infrastructure verification — COMPLETE
- Admin Lambda `CodeSha256 GlA3…`, `State=Active`, `LastUpdateStatus=Successful`.
- Other 12 Lambdas unchanged on `W6cqyudl…` (W1 intake behavior stays DORMANT).
- IAM `togs-and-dogs-prod-dynamodb-access` default **v3** unchanged — still includes
  `dynamodb:TransactWriteItems`, Resource scoped to the app table + `/index/*`.
- API Gateway `a022yxuiue` stage `prod` deployment **`n40vai`** unchanged.
- Targeted convergence: `terraform plan -target=aws_lambda_function.admin` = **No changes**
  (`-detailed-exitcode` 0; zero residual drift).
- CloudWatch (recent window): admin Lambda **0 errors, 0 throttles, 0 invocations** — the
  route has not been exercised; zero invocations is **not** proof of functionality.

### (c) Functional acceptance — PENDING
- `W3C2_FUNCTIONAL_ACCEPTANCE=PENDING`. **The runtime `dynamodb:TransactWriteItems`
  permission remains UNPROVEN by an authorized live transaction.** No live external-payment
  settlement has been recorded and no production payment transaction performed. The first
  end-to-end exercise remains a separate, owner-gated step with controlled non-customer
  data. `RYAN_TESTING_AUTHORIZED=NO`; Stripe sandbox-only.

### Rollback readiness
- The prior admin artifact `1EPLbycK…` was captured before apply as the immediate rollback
  baseline into **two independently base64-SHA-256-verified copies on separate physical
  disks** (abstract labels **ROLLBACK-PRIMARY** and **ROLLBACK-SECONDARY**), each in
  access-restricted, non-repository, non-cloud-synced storage with a capture manifest and a
  recovery procedure. Both were reverified immediately before apply and again post-apply.
  (No private paths or ZIP contents are recorded here.) Admin has no published Lambda
  versions, so this capture is the sole restore source; restore is a future, separately
  authorized action.

### Gates preserved (unchanged by this deployment)
No Stripe live activity, tenant change, Ryan testing, production test data, mobile
distribution, or W1 deployment. Only `aws_lambda_function.admin` was updated;
`W3C2_UNTARGETED_APPLY_ACTIVATES_W1=YES` and `W1_PRODUCTION_RELEASE_AUTHORIZED=NO` remain in
force — any untargeted apply would sweep all 13 Lambdas to `GlA3…` and activate W1.

See also: [W3-C1 MANUAL_EXTERNAL adapter](w3c1-manual-external-adapter.md),
[W3-C1 TransactWriteItems IAM plan](w3c1-transactwrite-iam-plan.md),
and the project continuity doc `docs/project-continuity/current-state.md`
(2026-10-27 deployment checkpoint).
