# BE-CANCEL-1: Cancellation decision safety (source-only)

Status: LOCAL SOURCE + TESTS ONLY. Not deployed. Not indexed in `index.md` (non-canonical).
Scope: `src/backend/handlers/cancellation_handler.py`, an opt-in guard in
`src/backend/common/cascade.py` (BE-CANCEL-1A), a cancellation-state guard in
`src/backend/handlers/review_handler.py` (BE-CANCEL-1C), and backend tests.

## Contract

### `POST .../cancel` (client cancellation request)

- Ownership, tenant, and booking-access checks are unchanged.
- Allowed only from `APPROVED`, `ASSIGNED`, the legacy display synonyms `BOOKED`,
  `SCHEDULED`, `JOB_CREATED` (the web portal's `canCancel` list), or a repeat while
  already `CANCELLATION_REQUESTED`. Every other status, including finished/closed,
  early-workflow (`PENDING_REVIEW` through `QUOTED`) and `CANCELLATION_DENIED`, is
  refused with 409 `BOOKING_NOT_CANCELLABLE`. This matches `common/status.py`, where only
  `APPROVED` and `ASSIGNED` transition to `CANCELLATION_REQUESTED`.
- Refused with 409 `BOOKING_STATE_UNKNOWN` when the booking has no status.
- The write is conditional on the status that was read (`#stat = :observed`).
  A concurrent change returns 409 `CANCELLATION_STATE_CHANGED`.
- New cancellation cycle: if the observed status is `APPROVED` or `ASSIGNED`, it is
  stored as `cancellation_prior_status` (+ `cancellation_prior_status_captured_at`) in
  the same conditional write. For a legacy synonym, any stale prior is removed. Stale
  `cancellation_decision` / `cancellation_decision_result_status` from an earlier
  cycle are always removed.
- A repeat request while already `CANCELLATION_REQUESTED` never replaces the
  recorded prior status.

### `PUT .../decision` (owner/admin decision)

- Owner/admin only. Validation happens before any read or write:
  - `decision` must be exactly `APPROVE` or `DENY` (case-sensitive, string) or 400.
  - `note` optional; must be a string of at most 500 characters or 400.
- Tenant ownership is validated on the initial read and on the consistent
  reconciliation read.
- Atomic decision gate: `ConditionExpression "#stat = :requested"` (plus
  `AND cancellation_prior_status = :prior` for DENY). Exactly one competing decision
  can win.
- Records `cancellation_decision`, `cancellation_decision_result_status`,
  `cancellation_decision_at`, `cancellation_decision_by`, `cancellation_decision_actor`
  (caller email), `cancellation_decision_note`, and an audit-log entry.
- Non-pending read or conditional-write failure: reconciled with
  `GetItem(ConsistentRead=True)`:
  - still `CANCELLATION_REQUESTED`: 409 `CANCELLATION_STATE_CHANGED`;
  - same decision already applied (status equals the recorded result status):
    200 with `idempotent_replay: true`;
  - anything else: 409 `CANCELLATION_NOT_PENDING` with `current_status`
    and `previous_decision`.
- Response: `message`, `new_status`, `decision`, `sns_message_id`, `idempotent_replay`,
  `warnings[]`. 409 bodies: `{error, code, ...}`.

## D1 Option A: DENY restoration

Restorable prior statuses: exactly `APPROVED` and `ASSIGNED`, the canonical
predecessors of `CANCELLATION_REQUESTED` (asserted by a test against
`REQUEST_TRANSITIONS`). Restoring them is a deliberate D1 Option A exception: the
canonical map lists only `CANCELLED`, `CANCELLATION_DENIED` and `ARCHIVED` as successors
of `CANCELLATION_REQUESTED`. The cancellation handler does not consult that map.

`BOOKED`, `SCHEDULED` and `JOB_CREATED` are display synonyms of `APPROVED`/`ASSIGNED`
in `shared/constants/request-statuses.json`, not backend `RequestStatus` values. They
are deliberately not restorable: restoring one would write a non-canonical status,
and normalizing it would be inference. A DENY on such a request fails closed (owner
decision; see below).

- DENY sets the booking back to the recorded prior status (e.g. ASSIGNED→ASSIGNED,
  APPROVED→APPROVED). It does not write `CANCELLATION_DENIED`.
- DENY runs no job cascade (the old forced-ASSIGNED cascade is not used). Assigned,
  unassigned and completed visits keep their existing state; no job or assignment
  is created.
- DENY sends no SNS and no notification event.

### Legacy records: owner recovery requirement

A request in `CANCELLATION_REQUESTED` without a trustworthy, allowlisted
`cancellation_prior_status` cannot be denied automatically. This covers every request
created before this change, any that reached `CANCELLATION_REQUESTED` through the
generic review transitions, and any made from a legacy synonym. For such a request,
DENY returns 409 `LEGACY_PRIOR_STATUS_UNKNOWN` and nothing is written to the booking
or its jobs. The prior status is never inferred from job records.

APPROVE remains available for such records. There is no web or mobile tool to
resolve a legacy DENY; the owner must resolve these bookings manually (an
owner-approved, audited data correction). That procedure is not part of this change.

## BE-CANCEL-1C: `/admin/review` cancellation-state guard

`src/backend/handlers/review_handler.py` previously allowed generic, unconditional
transitions such as `APPROVED/ASSIGNED → CANCELLATION_REQUESTED` (creating a request
with no cycle identity or prior status) and `CANCELLATION_REQUESTED → CANCELLED /
CANCELLATION_DENIED / ARCHIVED` (bypassing the decision gate). Staff could set
`CANCELLATION_DENIED`, because it was not in the sensitive-status list.

- For every role (owner, admin, staff), `/admin/review` now returns
  409 `CANCELLATION_TRANSITION_NOT_ALLOWED`, with no booking or job write and no audit,
  notification, calendar or cascade side effects, when the request would:
  - enter `CANCELLATION_REQUESTED` or `CANCELLATION_DENIED`, compared after trim and
    uppercase; or
  - leave `CANCELLATION_REQUESTED`, including through the `VERIFY_MEET_GREET`
    pseudo-status, which also writes REQ status.
- The guard runs after the existing RBAC and tenant checks; it does not replace or
  weaken them. Staff still get 403 for the existing sensitive statuses.
- The review status write (and the `VERIFY_MEET_GREET` REQ write) is now conditioned
  on `attribute_not_exists(status) OR status <> CANCELLATION_REQUESTED`. A booking that
  becomes `CANCELLATION_REQUESTED` after review read it is never overwritten (409).
- BE-CANCEL-1C-R1, `VERIFY_MEET_GREET` corrections (confirmed defects):
  - Tenant authorization: the path used to write client metadata (overwriting its
    `company_id` with the caller's tenant), pet metadata and the REQ status before
    any tenant check, and could create a stub REQ. Now tenant ownership is verified
    before any write. A missing or foreign booking gets the same generic 403 (no stub,
    no status disclosure). Client-level verification refuses client metadata owned
    by another tenant, and that write is conditioned on
    `attribute_not_exists(company_id) OR company_id = :caller`.
  - Write ordering: the guarded booking write (`attribute_exists(PK)` and not
    `CANCELLATION_REQUESTED`) now runs first. A rejected booking write (cancellation
    race, booking deleted) leaves the client and pet Meet & Greet metadata unchanged.
  - Residual (not atomic): if the booking write succeeds and a later metadata write
    fails, the booking shows `MG_COMPLETED` without the metadata flag. The response
    says so (500) and the writes are idempotent, so retrying verification repairs
    it. This fails safe: approval still checks the pet metadata. Full atomicity would
    need a transaction, which is out of scope.
- Ordinary non-cancellation review transitions are unchanged, including a direct
  owner/admin `APPROVED/ASSIGNED → CANCELLED`.
- Not changed and UNVERIFIED for cancellation-state interactions: the archive/delete
  lifecycle actions via `POST /admin/requests` (`performAdminAction`), bulk lifecycle
  actions, and purge. They may still move a `CANCELLATION_REQUESTED` booking.
- Web callers that used `/admin/review` for cancellation (`DENY_CANCEL →
  CANCELLATION_DENIED`, `CANCEL` on a pending request) will now get 409. That is
  intended: cancellation must go through `PUT /admin/cancel/decision`. No web code
  is changed in this release.

## Release blockers (unresolved)

- The decision cycle ID is still optional. Until callers send `cancellation_request_id` and it
  is made mandatory (owner-gated, coordinated web + mobile change), a decision
  delivered after a newer cycle exists cannot be distinguished.
- Legacy pending requests without a prior status (and, once the ID is mandatory,
  without a cycle ID) fail closed. Recovery needs a separately approved owner process.
- Notification delivery is not guaranteed across process crashes (below).

Source-only implementation. Nothing in BE-CANCEL-1, 1A or 1C is deployed.

## Side effects and limitations

Only the invocation that wins the decision write runs side effects. Each is
separately fallible; failures are appended to `sync_failures` and returned in
`warnings[]` (`AUDIT_LOG`, `JOB_CASCADE`, `GOOGLE_CALENDAR`, `SNS_NOTIFICATION`,
`NOTIFICATION`). A side-effect failure does not undo the committed decision.

- Not atomic: the job cascade and calendar cleanup run after the decision is
  committed. A partial cascade is recorded truthfully (COMPLETED jobs preserved).
- Replay: a same-decision APPROVE replay re-runs only the idempotent steps (job
  cascade to CANCELLED, calendar cleanup of event IDs still recorded). DENY replay
  runs nothing.
- Notifications are never re-sent by a replay. If the winning invocation fails or
  crashes before SNS / notification delivery, they are missed, not duplicated, and
  must be followed up manually. Recorded failures make this visible. A crash after
  the decision commits but before delivery is NOT detectable: no pending-notification
  marker or delivery-success record is written, so the only evidence is the decision
  without a matching `SNS_NOTIFICATION` / `NOTIFICATION` failure entry, which looks the
  same as a successful send. Delivery is not guaranteed (release limitation).
## BE-CANCEL-1A: cancellation-cycle identity

- Each new cancellation cycle gets a server-generated UUID4 in
  `cancellation_request_id`. A repeat request while pending never replaces it (a legacy
  pending request without one is assigned one once). `cancellation_requested_at` is
  deliberately not used: a repeat request rewrites it, so it is not immutable.
- Every decision write is pinned to one cycle (`#cyc = :cyc`, or
  `attribute_not_exists` for a legacy request with none) and records it in
  `cancellation_decision_request_id`. A new cycle clears that field.
- Decisions accept an optional `cancellation_request_id` (strict lowercase UUID4;
  malformed → 400 before any read). When supplied, a decision for any other cycle gets
  409 `CANCELLATION_CYCLE_MISMATCH` with no write, no side effects and no replay.
- Same-decision replay is idempotent only when the recorded decision belongs to the
  booking's current cycle.
- Compatibility: the field is optional, so mobile S2 (which does not send it) keeps
  working. Without it, the server still binds the decision to the cycle it read, so a
  new cycle created between that read and the write is never decided. A request
  issued against cycle A but delivered after cycle B already exists cannot be told
  apart without the field. Full delayed-delivery protection therefore needs mobile to
  send `cancellation_request_id`, and making it mandatory is a breaking contract change
  that needs owner approval.

## BE-CANCEL-1A: missing-job safety

- Previously `common.cascade.cascade_status_to_job` defaulted a missing JOB to
  `JOB_CREATED` and ran an unconditional `UpdateItem`, which creates a stub JOB
  (`CANCELLED`) for a dangling `job_ids` reference.
- The cancellation APPROVE cascade now passes the new opt-in `require_existing=True`:
  a missing JOB is skipped and never written; every write is conditioned on
  `attribute_exists(PK)`; a JOB that became `COMPLETED` after it was read is not
  overwritten. Missing ids are recorded as a `JOB_MISSING` sync failure and returned
  in `warnings[]`; write-time conflicts are recorded as `JOB_CASCADE`.
- Other cascade callers keep the default `require_existing=False` (unchanged, still
  stub-capable). Extending the guard to them is a separate decision.
- A replay re-records `JOB_MISSING` each time it runs while the reference stays dangling.

## Mobile compatibility (PR #69, not changed here)

`CancellationDecisionPanel` expects `CANCELLATION_DENIED` after DENY and will show a
status-mismatch warning against this backend. A follow-up mobile change is required
before both ship together.

## Deployment note (not authorized)

Any future deploy should be an RC built on the currently deployed baseline plus this
change, applied as a targeted cancellation-Lambda-only change with a convergence
proof. Never run an untargeted apply. Requires explicit owner approval.
