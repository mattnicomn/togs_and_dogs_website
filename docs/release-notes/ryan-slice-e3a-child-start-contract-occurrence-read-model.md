# Ryan Slice E3A — Child Start Contract and Occurrence Read Model

**Date:** 2026-08-20; production Gate A deployed 2026-08-21; Gate B0 completed 2026-08-23
**Status:** ✅ DEPLOYED TO PRODUCTION / GATE B0 COMPLETE / B1A–B3 NOT APPROVED
**Starting SHA:** `694555f0f10be80bd99099a1b00f329c5bbbf73d`

## Objective

E3A establishes the backend foundation for a later Mobile Start Visit flow. It adds an explicit idempotent Start action for one child JOB and exposes occurrence-aware child data through the existing exact admin-request read. E3A includes no Mobile Start UI.

## Child Start Contract

- `POST /admin/job/start` accepts only the authoritative child relationship identifiers `job_id` and `request_id`; it accepts no status or device timestamp.
- The normal and exact first-start predecessor is canonical child status `ASSIGNED`. `JOB_CREATED`, `SCHEDULED`, `PENDING`, and terminal/non-actionable statuses are not broadened into Start predecessors.
- Start preserves child status, parent aggregate status, assignment, and the parent record. It writes server UTC `started_at`, authenticated `started_by`, `updated_at`, and `updated_by` to the child and appends one `JOB_STARTED` entry to the child audit history.
- No canonical `IN_PROGRESS` status was added. Start is child occurrence metadata/event history, while the parent request remains the aggregate booking.
- Start creates no request/job, performs no Calendar mutation, and sends no notification.

## Authorization and Idempotency

- Existing owner and admin authorization conventions permit the child action.
- Staff may Start only when the authenticated normalized email matches the child `worker_id`, matching the existing Complete identity convention.
- Tenant ownership is validated before either the first write or a concurrent-result response.
- One conditional atomic child update requires `attribute_not_exists(started_at)` and status `ASSIGNED`. The winning request writes the timestamp and audit entry together.
- A replay returns the originally persisted timestamp without a write or duplicate audit entry. A conditional loser performs a strongly consistent child read and returns the persisted winning result when Start already succeeded.

## Occurrence-Aware Read Model

The existing authenticated `GET /admin/requests/{requestId}?clientId=...` response now enriches `job_completion_summary.jobs` from authoritative child JOB records. Each occurrence exposes `job_id`, `request_id`, occurrence date/end date/window/index/count, canonical child status, worker identity/name, start/end time, start metadata, completion metadata, and existing visit notes.

The read supports both legacy singular `job_id` and current `job_ids`, keeps same-date Check-In windows distinct, and orders deterministically by occurrence date, generated occurrence index, canonical window order, and stable job ID fallback. Missing legacy metadata remains optional; no data migration or historical inference is performed. Parent and child tenant boundaries are enforced, and staff reads remain assignment-scoped.

## Complete Compatibility

The existing child Complete implementation is unchanged. Complete continues to work for assigned jobs both with and without Start metadata, so older callers are not required to Start first.

## Contracts and Infrastructure

- Added canonical shared paths for `/admin/job/start` and `/admin/requests/{requestId}` and regenerated the existing Web/Mobile adapters.
- Added authenticated API Gateway methods/integrations for the new Start action and the existing exact-request handler path.
- Request-status and service/job lifecycle constants are unchanged; executable contract checks confirm `IN_PROGRESS` remains non-canonical.
- Before deployment, Terraform 1.14.8 format and validation passed, the production budget declarations were reconciled to the existing three-alert state, and the saved production plan was reviewed against an exact resource whitelist.

## Validation

- focused E3A backend/API coverage: 24/24;
- affected E3A + Complete + occurrence/job creation + tenant/RBAC/status suites: 137/137; the broader R11E tenant file remains 13 passed / the same 3 checkpoint-environment failures;
- shared constants: 24/24; generated-adapter validators: 9/9 and 7/7;
- Web contract adapter: 13/13; full Web: 310/310 plus legacy 99/99; build success with 111 modules; targeted changed-file lint pass;
- Mobile contract adapter: 10/10; full Mobile: 128/128; TypeScript pass;
- full backend candidate: 977 passed / 100 failed versus exact starting checkpoint 953 passed / the same 100 baseline environment failures; and
- `git diff --check`: pass.

## Production Gate-A Deployment (2026-08-21)

Matthew explicitly approved Gate A for isolated backend/API RC `732e48b930f6fd9aac958351c4ac7823c14cf3e0`. Terraform applied only the saved plan with SHA-256 `01DA5C94E022420A0E3456ED888F9800DDD972FACA32BF61106FFE801B696854`; the deployed backend ZIP SHA-256 is `C7E407664A170CA1C2077029E6750BDEBE736E648E505666DE3DED091C66635A`. The apply ran from `2026-08-21T19:47:12Z` through `2026-08-21T19:48:35Z` and completed with `14 added, 14 changed, 1 destroyed`. The only warning was the pre-existing deprecated DynamoDB backend-lock parameter.

All 13 shared-package Lambdas reached `Active` / `Successful`, matched the approved package hash, and retained their pre-deploy configuration fingerprints. API Gateway `prod` moved from deployment `28dv28` to `886zij`; all 50 baseline paths remained, `/admin/job/start` and the exact-request GET have Cognito authorization plus Lambda proxy integration, and both OPTIONS/CORS paths passed. Unauthenticated Start and exact GET returned `401` before integration; both OPTIONS checks returned `200`. Deployment-window log review found no import, initialization, or syntax errors; the SES-feedback function had no log group to inspect but independently passed Lambda health and package verification. Production budget notifications remained ACTUAL 80%, ACTUAL 100%, and FORECASTED 80%.

No successful Start, Complete, assignment/review/booking mutation, production test-data creation, Calendar action, notification, tenant, IAM, DynamoDB, Cognito, Postmark, Stripe, or budget change occurred. Authenticated malformed Start was skipped because no approved production authentication context was supplied. Authenticated exact-record GET was skipped because no preapproved internal validation record was documented. At Gate-A closeout, all Gate-B work and successful Start validation remained separately approval-gated.

## Production Gate-B0 Identity Enablement (2026-08-23)

Matthew explicitly approved Gate B0 to enable the sole existing Cognito identity mapped to `test_tenant_alpha` without changing the identity. The pre-mutation checkpoint confirmed clean `main` at `c56dc860571cd200452efbfda01e16de4b96c2ce`, exactly one tenant identity, `CONFIRMED` status, disabled state, `custom:company_id=test_tenant_alpha`, groups `client,owner`, and no other enabled identity in that tenant.

Exactly one `AdminEnableUser` operation succeeded from `2026-08-23T12:00:09Z` through `2026-08-23T12:00:10Z`. Post-enable verification confirmed the same identity is enabled and remains `CONFIRMED`, with groups and tenant mapping unchanged. Existing credentials were preserved: no password reset, temporary password, invitation/resend, group change, attribute change, or session-revocation operation occurred. CloudTrail showed `AdminEnableUser` as the only Cognito mutation in the execution window.

The available browser context had no existing authenticated session or safely available credentials, so login was not attempted and no credential flow was triggered. Read-only tenant verification found only the existing tenant metadata record and zero client, staff, pet, request, or job records. Enablement itself sent no email, Postmark, SES, push, or other notification and caused no Calendar, Stripe, tenant, profile, request/job, Start, or Complete action. The identity was intentionally left enabled. Gate B1A, B1B, B2, and B3 remain not approved.

## Boundaries and Next Slice

E3A backend/API Gate A is deployed and Gate B0 identity enablement is complete. B1A, B1B, B2, and B3 remain NOT APPROVED. E2, E1, and O1 remain NOT DEPLOYED. E3B/E3B.1 Mobile remain NOT BUILT, NOT DISTRIBUTED, and NOT DEPLOYED. No Ryan testing or tester change was authorized.

E3B/E3B.1 Mobile are implemented and validated locally but remain future build/distribution/deployment work. Early/late/same-day Start policy, Start correction, mandatory Start-before-Complete, client visibility, Start notifications, Calendar effects, offline/device time, and any admin “Start on behalf” UX remain explicit product decisions.

## Disposition

**Final Status:** `RYAN_SLICE_E3A_DEPLOYED_GATE_A_VALIDATED_GATE_B0_COMPLETE_B1A_THROUGH_B3_NOT_APPROVED`
