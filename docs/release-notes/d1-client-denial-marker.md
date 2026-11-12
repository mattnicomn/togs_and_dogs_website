# D-1: Client-portal cancellation-denial marker (source-only)

Status: LOCAL SOURCE + TESTS ONLY, Draft PR. Not merged. Not deployed. Not indexed in
`index.md` (non-canonical).
Scope: `src/backend/common/auth.py` (client booking-list projection),
`web/src/components/ClientPortal.jsx`, and tests. No persistence change, no email, no SNS,
no notification, no write of any kind.

Owner-approved product policy (D-1, P-1 to P-6): after a cancellation request is denied the
client sees a denial marker; no denial email; no admin-note exposure; the Cancel button stays
available where otherwise eligible; the date is shown only when a valid client-safe date is
present; legacy `CANCELLATION_DENIED` records are unchanged; the mobile marker is deferred.

## Contract

`GET /client/requests` keeps its explicit allowlist (`CLIENT_REQUEST_LIST_ALLOWLIST`). Two
DERIVED keys are added by `_derive_cancellation_denial` and listed in
`CLIENT_REQUEST_LIST_DERIVED_FIELDS`. They are an explicit exception, not a pass-through:
no raw `cancellation_*` attribute is ever copied into the client projection.

- `cancellation_denied: true`, emitted only when ALL hold:
  - `cancellation_decision` is exactly `"DENY"`;
  - `cancellation_decision_request_id` is a string equal to the booking's CURRENT non-empty
    `cancellation_request_id` (the denial belongs to the current cancellation cycle);
  - `status` is exactly `"APPROVED"` or `"ASSIGNED"` (the statuses BE-CANCEL-1 restores).
- `cancellation_denied_at`: emitted only together with the marker, and only when
  `cancellation_decision_at` is a timezone-aware ISO-8601 string of at most 40 characters.
  It is returned normalized to UTC; anything else omits the key (the marker still shows).

Never emitted: the admin note, actor, `cancellation_decision_by`, audit entries, cycle ids,
`cancellation_prior_status`, reason, `sync_failures`, tenant attributes, `PK`/`SK`, worker
identifiers, or any other client's data. The scan is still limited to the server-resolved
client and tenant, and the projection builds a new dictionary per record.

## Behaviour

| Situation | Marker |
|---|---|
| DENY on the current cycle, booking `APPROVED` / `ASSIGNED` | Shown (with date when valid) |
| Client requests cancellation again (new cycle) | Cleared: BE-CANCEL-1 removes the decision and the portal shows only "Cancellation Pending" |
| Repeated DENY on the same cycle | Unchanged (server no-op; the marker is a pure function of the record) |
| Decision belongs to an earlier cycle, or a cycle id is missing / empty / non-string | Not shown |
| Booking `CANCELLED`, `COMPLETED`, `ARCHIVED`, `DELETED`, `IN_PROGRESS`, `CANCELLATION_REQUESTED`, legacy synonyms, any other status | Not shown |
| Old-backend `CANCELLATION_DENIED` record, or pending record without cycle ids | Not shown; existing wording unchanged (nothing is inferred) |

Portal: when `cancellation_denied === true`, a note below the normal status text reads
"Cancellation request declined" / "Your cancellation request was declined [on <date>]. Your
booking remains active. You can submit another cancellation request or contact the business
for assistance." The normal status badge and message, and the Cancel button, are unchanged;
the notice does not state the booking's current status.

## Dependencies and release order (gates, none authorized here)

- The marker is only produced from BE-CANCEL-1 persistence (Draft PR #71, source-only, NOT
  deployed): `cancellation_decision`, `cancellation_decision_request_id`,
  `cancellation_request_id`. Against the backend currently on `main` nothing ever sets it, so
  deploying this change alone is harmless but shows no marker.
- Order: BE-CANCEL-1 backend deployed and verified, then this backend projection, then the
  portal change (the portal ignores a missing field, so either order is safe for users).
- WEB-CANCEL-1 (Draft PR #72) and the mobile correction (Draft PR #69) are separate and are
  not changed here. The mobile marker is deferred.
- Merge, deployment, production verification and any production test data each need separate
  explicit owner approval. Deployed behaviour is UNVERIFIED.

## Validation

See the PR description for the exact local runs and the CI comparison against the `main`
baseline (74 backend failures and 63 web lint findings that predate this change).
