# OPS-3A.1C — API Gateway Terraform Route Definitions (local implementation)

Status: **LOCAL TERRAFORM SOURCE EDIT — READY FOR REVIEW. NOT APPLIED. NOT DEPLOYED.**
No Terraform command (`init`/`validate`/`plan`/`apply`/`test`) was run. No AWS
runtime, deployment, Stripe, payment, tenant, or production-data operation occurred.
The three routes are **defined in Terraform source only**; they remain **not live** in
any environment until the separate OPS-3A.1D validate/plan/apply gate.

Starting checkpoint: `main == origin/main == a025154e6279787079d24654ae4e4d676a150402`
(working tree clean, index empty, stash empty at task start). No commit, stage, or
push was performed by this task; the working-tree change is left for review.

References:
- Handlers already implemented and committed in **OPS-3A.1B**
  (`docs/release-notes/ops3a1b-quote-handler-integration-local-implementation.md`,
  commit `a025154`). This slice only adds the API Gateway wiring that makes those
  handlers reachable; it does **not** change any handler behavior or contract.
- Quote contract: `docs/planning/petcare-hero-quote-contract.md` (approved 2026-10-03).

---

## What was defined (local Terraform only)

Three new API Gateway routes were added to the existing API module, reusing the
module's established per-route convention exactly (resource + Cognito-authorized
method + `AWS_PROXY` integration to the existing admin handler Lambda). No new Lambda
and no new Lambda permission were introduced.

### A. `PATCH /admin/requests/{requestId}/quote`
- `aws_api_gateway_resource.admin_quote` — child of the existing
  `aws_api_gateway_resource.admin_request_id` (`path_part = "quote"`).
- `aws_api_gateway_method.patch_admin_quote` — `PATCH`, `COGNITO_USER_POOLS`,
  `authorizer_id = aws_api_gateway_authorizer.cognito.id`.
- `aws_api_gateway_integration.patch_admin_quote_lambda` — `AWS_PROXY`,
  `integration_http_method = "POST"`, `uri = var.admin_handler_invoke_arn`.

### B. `POST /admin/requests/{requestId}/quote/send`
- `aws_api_gateway_resource.admin_quote_send` — child of `admin_quote`
  (`path_part = "send"`).
- `aws_api_gateway_method.post_admin_quote_send` — `POST`, `COGNITO_USER_POOLS`,
  Cognito authorizer.
- `aws_api_gateway_integration.post_admin_quote_send_lambda` — `AWS_PROXY`,
  `POST`, `uri = var.admin_handler_invoke_arn`.

### C. `GET /client/quotes/{requestId}`
- `aws_api_gateway_resource.client_quotes` — child of the existing
  `aws_api_gateway_resource.client` (`path_part = "quotes"`).
- `aws_api_gateway_resource.client_quote_id` — child of `client_quotes`
  (`path_part = "{requestId}"`).
- `aws_api_gateway_method.get_client_quote` — `GET`, `COGNITO_USER_POOLS`,
  Cognito authorizer.
- `aws_api_gateway_integration.get_client_quote_lambda` — `AWS_PROXY`, `POST`,
  `uri = var.admin_handler_invoke_arn` (the client quote-read handler lives in the
  admin Lambda, matching the existing `GET /client/requests` integration target).

The exposed paths are exactly those three. No `client_id` was added to any path or to
the public body contract; `requestId`-only resolution is handled inside the handler
(OPS-3A.1B). No `BOOKING_CONFIRMED`, no new RequestStatus value, no client
Accept/Decline, no Stripe/payment execution, and no mobile/web change are part of this
slice.

## Cross-cutting deployment wiring

- **CORS/OPTIONS:** the four new resources (`admin_quote`, `admin_quote_send`,
  `client_quotes`, `client_quote_id`) were added to the module's `local.cors_resources`
  map, so the existing `for_each` OPTIONS/MOCK + CORS method/integration responses
  cover them exactly as they cover `admin_payment_session`, `admin_send_payment_email`,
  and `client_pet_id`. No bespoke CORS definition was introduced.
- **Deployment dependency:** the three new integrations
  (`get_client_quote_lambda`, `patch_admin_quote_lambda`,
  `post_admin_quote_send_lambda`) were added to
  `aws_api_gateway_deployment.main.depends_on`.
- **Semantic fingerprint:** `modules/api/deployment-semantics.tf.json`
  (`local.api_deployment_semantics`) was extended with the 4 resources, 3 methods, 3
  integrations, and 4 CORS `resource_keys`. The deployment redeployment trigger is
  `module.deployment_fingerprint.sha1`, so registering the new routes in the manifest
  is what will cause a future apply to roll a new API Gateway deployment. The
  fingerprint submodule's own tests already prove (generically) that adding a
  resource/method/integration/CORS key changes the fingerprint.
- **Lambda permission:** none added. The existing `aws_lambda_permission.api_admin`
  (`infra/prod/main.tf`) grants `apigateway.amazonaws.com` invoke on the admin Lambda
  with no per-route `source_arn` scoping, so it already authorizes these new routes.
  Adding a route-specific permission would be redundant and was deliberately avoided.

## Static verification (no Terraform executed)

- `modules/api/deployment-semantics.tf.json` parses as valid JSON (`json.load`).
- Semantic path reconstruction from the manifest yields exactly
  `PATCH /admin/requests/{requestId}/quote`,
  `POST /admin/requests/{requestId}/quote/send`, and
  `GET /client/quotes/{requestId}`; all three are `COGNITO_USER_POOLS` via the
  `cognito` authorizer; all three integrations are `AWS_PROXY` / `POST` /
  `admin_handler_invoke_arn`.
- Reference integrity: every manifest `parent_key`, `resource_key`, `authorizer_key`,
  and `method_key` resolves; every new CORS key resolves to a declared resource.
- main.tf ↔ manifest consistency: each manifest resource/method/integration key has a
  matching `aws_api_gateway_resource` / `aws_api_gateway_method` /
  `aws_api_gateway_integration` block in `main.tf`; the three new integrations appear
  in the deployment `depends_on`; the four new resources appear in
  `local.cors_resources`.
- No `client_id` appears in any new path part.
- `git diff --stat`: 146 insertions, 0 deletions — purely additive; no existing route
  resource/method/integration was modified or removed.
- `git diff --check`: clean (no whitespace errors).
- Only two files changed: `modules/api/main.tf` and
  `modules/api/deployment-semantics.tf.json`. No backend handler, mobile, web,
  generated, or other files were touched.

No `terraform init|validate|plan|apply|test` was run; `terraform fmt` was not run.
Meaningful plan-level validation (resource graph, provider schema, and the actual
`add/change/destroy` plan) cannot be completed without executing Terraform and is
therefore deferred to the OPS-3A.1D gate.

## Explicitly out of scope (deferred / gated)

- **OPS-3A.1D** — the separate Terraform validation / plan / review / apply /
  deployment gate for these routes (requires explicit authorization; expected plan is
  additive: new resources/methods/integrations/OPTIONS plus one API Gateway deployment
  replacement driven by the changed semantic fingerprint).
- **OPS-3A.2** — client Accept/Decline mutation (and its `expected_revision` + 409
  contract) and client `ACCEPTED` → RequestStatus synchronization.
- **OPS-3A.3** — web/mobile quote UI.
- **OPS-3B** and later — deferred.
- No Stripe/payment execution, no booking approval (`APPROVED`/`BOOKING_CONFIRMED`
  never written), no migration, no tenant-resolution change, no production-data
  operation.

## Resume point

- Ending commit: `a025154e6279787079d24654ae4e4d676a150402` (unchanged — no commit made
  this task).
- Files changed (uncommitted, for review): `modules/api/main.tf`,
  `modules/api/deployment-semantics.tf.json`, and this release note.
- Deployment status: NOT APPLIED / NOT DEPLOYED. Routes defined in source only; not
  reachable in any environment.
- Exact next recommended action: Matthew review of this local Terraform definition;
  on approval, proceed to **OPS-3A.1D** (Terraform validate/plan review, then
  gated apply) as a separate deploy-gated slice.
- Required approval: Matthew (commit decision, and separately any Terraform
  validate/plan/apply and deployment).
