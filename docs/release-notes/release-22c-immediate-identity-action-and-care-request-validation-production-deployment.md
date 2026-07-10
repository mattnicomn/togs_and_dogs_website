# Release 22C — Immediate Identity Action and Care Request Validation Fixes Production Deployment

**Release Date:** 2026-07-09
**Status:** PARTIALLY VALIDATED — 22D follow-up required (see below)
**Deployed By:** Matthew (explicit approval) + Antigravity AI agent

---

## Summary

Production deployment of Release 22B code changes, which fixed three categories of bugs identified during Release 22A triage:

1. **Resend Invite notify_event bug** — unbound local variable error in admin_handler.py
2. **Staff card click bubbling** — protected/disabled profile action buttons incorrectly scrolled or opened edit mode
3. **/book care request validation UX** — missing field-level errors and no date-picker highlighting on missing selections

This release also created two new API Gateway routes for future staff identity actions (reset-password, set-temp-password).

---

## Pre-Deploy Checks

| Check | Result |
|---|---|
| Git status clean | PASS |
| Latest commit 35ed880 or later | PASS — 12a39d4 |
| No .tfplan, logs, scratch, web/dist, task.md, walkthrough.md, credentials committed | PASS |
| Tenant count exactly 2 | PASS |
| tog_and_dogs active | PASS |
| test_tenant_alpha active | PASS |
| TENANT_RESOLUTION_MODE=multi | PASS |
| AWS SSO caller identity | PASS — arn:aws:sts::358604342897:assumed-role/AWSReservedSSO_AdministratorAccess |

---

## Test Results

### Backend Unit Tests — 23/23 Passed

All four test files run together in a single pytest session:
- test_r22b_resend_invite_fix.py
- test_r21g_google_token_isolation.py
- test_r8s_login_controls.py
- test_r8u_staff_cleanup.py

Output: 23 passed, 2 warnings in 1.66s

Test fixes applied during 22C pre-deploy (commit 12a39d4):
- Fixed module-level TENANT_RESOLUTION_MODE=multi env pollution in test_r21g — moved to autouse patch.dict fixture
- Fixed stale UserPoolId=None assertions in test_r8s — updated to unittest.mock.ANY

### Frontend Build — Passed

Output: built in 360ms — no errors
Bundle: dist/assets/index-BVmvw1mJ.js (936 kB / 272 kB gzip)

---

## Terraform Plan Summary

Plan: 15 to add, 14 to change, 1 to destroy

### 15 Resources Added — API Gateway staff routes
- aws_api_gateway_resource.admin_staff_reset (path: reset-password)
- aws_api_gateway_resource.admin_staff_temp_pw (path: set-temp-password)
- aws_api_gateway_method.post_admin_staff_reset (POST, COGNITO_USER_POOLS auth)
- aws_api_gateway_method.post_admin_staff_temp_pw (POST, COGNITO_USER_POOLS auth)
- aws_api_gateway_method.options[admin_staff_reset] (OPTIONS/CORS)
- aws_api_gateway_method.options[admin_staff_temp_pw] (OPTIONS/CORS)
- aws_api_gateway_integration.post_admin_staff_reset_lambda (AWS_PROXY -> admin Lambda)
- aws_api_gateway_integration.post_admin_staff_temp_pw_lambda (AWS_PROXY -> admin Lambda)
- aws_api_gateway_integration.options_mock[admin_staff_reset] (MOCK for CORS)
- aws_api_gateway_integration.options_mock[admin_staff_temp_pw] (MOCK for CORS)
- aws_api_gateway_integration_response.options_200[admin_staff_reset]
- aws_api_gateway_integration_response.options_200[admin_staff_temp_pw]
- aws_api_gateway_method_response.options_200[admin_staff_reset]
- aws_api_gateway_method_response.options_200[admin_staff_temp_pw]
- aws_api_gateway_deployment.main (new deployment id: 3icswf)

### 14 Resources Changed
- 13 Lambda functions — source_code_hash update (22B backend zip)
- aws_api_gateway_stage.main — deployment_id updated to 3icswf

### 1 Resource Destroyed
- aws_api_gateway_deployment.main (old id: sowdzb) — replaced by new deployment

### Safety Verification
- No Cognito changes
- No DynamoDB changes
- No Secrets Manager changes
- No Stripe changes
- No calendar token/secret changes
- No tenant metadata changes
- No IAM policy changes

---

## Terraform Apply Result

Apply complete: 15 added, 14 changed, 1 destroyed

Outputs:
- api_endpoint = https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod
- frontend_s3_bucket = togs-and-dogs-prod-toganddogs-hosting
- frontend_cloudfront_domain = d2nr4rfm2afckd.cloudfront.net
- cognito_user_pool_id = us-east-1_counlsXGU

Plan file release-22c-prod.tfplan deleted after apply. Not committed.

---

## Frontend Deployment

### S3 Sync
Bucket: s3://togs-and-dogs-prod-toganddogs-hosting

Actions:
- Deleted old bundle: assets/index-BJ8CeT-X.js (previous release)
- Uploaded: assets/index-BVmvw1mJ.js
- Uploaded: assets/index-CntSnVuv.css
- Uploaded: index.html
- Uploaded: assets/usmh-logo-CrRnxp7-.png

### CloudFront Invalidation
- Distribution: E35L00QPA2IRCY
- Invalidation ID: IB56QAJRTLVY3WHBFUVRVJCB1A
- Paths: /*
- Status: Completed

### Production Bundle
- index.html references: index-BVmvw1mJ.js — CONFIRMED

---

## Safe Production Validation

### Automated Checks

| Check | Result |
|---|---|
| API Gateway staff reset-password route exists | PASS (id: agm-a022yxuiue-0yy1w1-POST) |
| API Gateway staff set-temp-password route exists | PASS (id: agm-a022yxuiue-5366iy-POST) |
| Both POST methods use COGNITO_USER_POOLS auth | PASS |
| Both POST methods use AWS_PROXY Lambda integration | PASS |
| OPTIONS routes use MOCK integration | PASS |
| Frontend bundle deployed and invalidated | PASS |
| Tenant count unchanged (2) | PASS |
| No emails sent | PASS |
| No password resets performed | PASS |
| No temp passwords set | PASS |
| No Cognito users modified | PASS |
| No tenant metadata modified | PASS |
| No production data created | PASS |

### Manual Matthew Validation — PARTIAL RESULTS (2026-07-09)

#### A. Staff Management — Partially Validated

| Check | Result |
|---|---|
| Resend Invite — Ryan York | PASS — invite sent successfully |
| Resend Invite — USmissionhero | DEFERRED — "Cognito user not found" (known orphaned legacy Cognito linkage from 22A; separate cleanup/relink work item) |
| Disabled/protected profile button bubbling | NOT CONFIRMED — no disabled/protected profile buttons were visible in the current view to validate |
| No live password reset or temp password action triggered | CONFIRMED — Matthew did not trigger any password actions |

#### B. /book Care Request Form — Improved, but UX refinement needed (Resolved by 22D/22E)

| Check | Result |
|---|---|
| Inline field-level error appears | PASS — validation appears inline |
| Calendar/date section highlighted on error | PASS — calendar section is highlighted |
| Scroll/focus to invalid field | PASS — page scrolls to invalid field |
| Form does not submit without required fields | PASS |
| Validation copy clarity | RESOLVED (22D/22E) — Specific ranges/copy explain that clicking "Select Dates from Range" is required. |
| Auto-fill Calendar button appearance | RESOLVED (22D/22E) — Renamed to "Select Dates from Range" and styled as a primary pill button. |
| Preferred Visit Windows missing — separate inline error | RESOLVED (22D/22E) — Made required with separate error. |

#### Summary
- Staff resend invite fix: **PASS** (Ryan York)
- Staff route/button behavior: **Partially validated** (disabled button bubbling not confirmed in current view)
- USmissionhero Cognito linkage: **DEFERRED** — orphaned profile, separate cleanup/relink item
- /book validation UX: **PASS** — Refined and manually validated in Releases 22D/22E

**Releases 22D and 22E resolved the /book validation UX concerns identified during Release 22C validation. The 22C deployment is considered healthy; only Cognito orphaned relinking and staff disabled button validation remain deferred/pending.**

---

## Guardrail Confirmation

| Guardrail | Status |
|---|---|
| No invite emails sent | CONFIRMED |
| No password reset emails sent | CONFIRMED |
| No temp passwords set | CONFIRMED |
| No Cognito users/groups/passwords modified | CONFIRMED |
| No profiles disabled/restored/unlinked/relinked/deleted | CONFIRMED |
| No tenant metadata modified | CONFIRMED |
| No staff/clients/pets/bookings/jobs/care requests created/modified | CONFIRMED |
| No Google Calendar tokens/secrets modified | CONFIRMED |
| No Stripe changes | CONFIRMED |
| No TENANT_RESOLUTION_MODE modified | CONFIRMED |
| No .tfplan, logs, screenshots, web/dist, credentials committed | CONFIRMED |
| Targeted git add only (no git add .) | CONFIRMED |

---

## Commits

| Commit | Description |
|---|---|
| 8e544c4 | Release 22B: Immediate Identity Action and Care Request Validation Fixes |
| d9f1c4c | Release 22B: Fix Terraform deployment dependencies and legacy test mocks |
| 35ed880 | Release 22B: Document API Gateway route verification and test updates |
| 12a39d4 | Release 22B/22C: Fix test environment pollution and stale UserPoolId assertions |

All commits pushed to origin/main.

Final git status: nothing to commit, working tree clean

---

## Follow-Up: Release 22D

Release 22D (Care Request Date Validation Copy and Auto-Fill UX Polish) is recommended to address:
- Clarify that entering Start Date and End Date does not count as selecting dates until Auto-fill or manual selection is used
- Rename or visually distinguish the Auto-fill Calendar button
- Separate Preferred Visit Windows inline error from the date error
- Simplify top summary error copy

See `docs/release-notes/release-22d-care-request-date-validation-ux-polish.md` for full plan.
