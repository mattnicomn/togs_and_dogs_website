# Ryan Slice E3A — Child Start Contract and Occurrence Read Model

**Date:** 2026-08-20
**Status:** ✅ IMPLEMENTED / VALIDATED / NOT DEPLOYED
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
- Terraform CLI was unavailable in the local environment, so `terraform fmt -check` could not run. Focused source coverage verifies both authenticated route resources, methods, and Lambda integrations; the infrastructure was not planned or applied.

## Validation

- focused E3A backend/API coverage: 24/24;
- affected E3A + Complete + occurrence/job creation + tenant/RBAC/status suites: 137/137; the broader R11E tenant file remains 13 passed / the same 3 checkpoint-environment failures;
- shared constants: 24/24; generated-adapter validators: 9/9 and 7/7;
- Web contract adapter: 13/13; full Web: 310/310 plus legacy 99/99; build success with 111 modules; targeted changed-file lint pass;
- Mobile contract adapter: 10/10; full Mobile: 128/128; TypeScript pass;
- full backend candidate: 977 passed / 100 failed versus exact starting checkpoint 953 passed / the same 100 baseline environment failures; and
- `git diff --check`: pass.

## Boundaries and Next Slice

E3A, E2, E1, and O1 are NOT DEPLOYED. No Mobile build/distribution, production write, Calendar mutation, notification, tenant/Cognito/Postmark/Stripe change, or public-site action occurred.

E3B Mobile remains future work. Early/late/same-day Start policy, Start correction, mandatory Start-before-Complete, client visibility, Start notifications, Calendar effects, offline/device time, and any admin “Start on behalf” UX remain explicit product decisions.

## Disposition

**Final Status:** `RYAN_SLICE_E3A_CHILD_START_CONTRACT_OCCURRENCE_READ_MODEL_IMPLEMENTED_VALIDATED_NOT_DEPLOYED`
