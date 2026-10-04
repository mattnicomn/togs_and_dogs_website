# OPS-3A.1B — Quote Handler Integration + Tests (local implementation)

Status: **LOCAL IMPLEMENTATION — READY FOR REVIEW. NOT DEPLOYED.** No production
deployment, Terraform, AWS, API Gateway, Stripe, migration, or production-data
operation occurred. The new routes are **not reachable** in any environment yet —
API Gateway wiring is a separate, deploy-gated slice (OPS-3A.1C).

Starting checkpoint: `main == origin/main == d29d833ca74bdc424e9fd9b0d26f7279e40faeda`
(working tree clean, index empty, stash empty at task start). No commit, stage, or
push was performed by this task; the working tree change is left for review.

Approved contract reference: `docs/planning/petcare-hero-quote-contract.md`
(product-contract approved by Matthew on 2026-10-03). Foundation reference:
`docs/release-notes/ops3a1-backend-quote-contract-local-implementation.md`
(OPS-3A.1 foundation, committed `d29d833`). This slice wires the already-approved,
already-tested pure contract module (`common/quote_contract.py`) into HTTP handlers.

---

## What was implemented

Handler integration in a single existing handler plus focused handler tests:

- `src/backend/handlers/admin_handler.py` (modified — three new route branches)
- `tests/backend/test_quote_contract_handlers.py` (new — 23 tests)

No new Lambda, no new module, and no change to `common/quote_contract.py`. All
quote business logic continues to live in the pure contract module; the handlers
only perform dispatch, authorization, lookup, persistence, and the derived
RequestStatus mirror.

### A. `PATCH /admin/requests/{requestId}/quote` — owner/admin draft/update
- Role gate: `owner` and `admin` only; all other roles (staff/client/unknown) → 403.
- **requestId-only lookup** (Correction #1): reuses the exact pattern already
  established by `POST /admin/requests/{requestId}/send-payment-email` — a `get_item`
  on `REQ#{id}/CLIENT#{client_id}` when a `clientId` is supplied, otherwise a
  `table.query(PK = REQ#{id}, SK begins_with CLIENT#)` fallback that resolves the
  `client_id` from the record. **No `client_id` is required in the request body** and
  no second lookup mechanism was introduced. Because REQUEST records are keyed
  one-per-request (`REQ#{id}/CLIENT#{client_id}`), the query resolves a single record.
- Tenant ownership enforced post-read via `validate_tenant_ownership` (cross-tenant
  → 403).
- Delegates to `apply_quote_update(request_item, incoming, now_iso)` for all
  revision/supersede/acceptance-reset logic. Persists **only** the returned field-set
  via a dynamically-built `SET` `UpdateExpression` (name/value placeholders), appends
  an audit entry to `audit_log` (`list_append` with `if_not_exists` seed).
- **Derived RequestStatus mirror (Correction #2):** when the resulting canonical
  `quote_status` is `DRAFT`, the handler also mirrors RequestStatus `status` to
  `QUOTE_NEEDED`. `quote_status` remains authoritative; RequestStatus is a derived
  summary only. The handler **never writes `APPROVED`** and never writes
  `BOOKING_CONFIRMED`.
- Internal-only note edits (`quote_notes_internal`, `internal_pricing_notes`) do not
  bump the revision, do not clear acceptance, and do not write a derived RequestStatus.
- Validation errors from the contract (`QuoteContractError`, e.g. invalid
  `payment_requirement`) → HTTP 400 with no write. Empty update bodies → HTTP 400.

### B. `POST /admin/requests/{requestId}/quote/send` — owner/admin send
- Same role gate and requestId-only lookup/tenant checks as (A).
- Delegates to `apply_quote_send(request_item, now_iso)`, which allows `DRAFT` or
  `SENT` (idempotent resend) and rejects a zero amount (→ HTTP 400, no write).
- **Atomic optimistic-concurrency guard:** the `update_item` carries a
  `ConditionExpression` requiring the stored `quote_revision` to equal the loaded
  revision **and** the stored `quote_status` to equal the loaded status (or be
  absent). A concurrent modification raises
  `ConditionalCheckFailedException`, which is mapped to **HTTP 409**.
- Mirrors RequestStatus `status` to `QUOTE_SENT` (derived summary only). Never
  writes `APPROVED`. Appends a `QUOTE_SENT` audit entry.

### C. `GET /client/quotes/{requestId}` — client-safe read
- Lives inside the existing `/client/` portal boundary, which already enforces the
  active-tenant gate (`require_active_tenant`) and resolves the authenticated client
  via `resolve_client_identity` before any quote logic runs.
- Enforces `role == 'client'` for this route (non-client → 403).
- Loads the request by the **resolved** client identity
  (`REQ#{id}/CLIENT#{resolved_client_id}`), so a client cannot read another client's
  quote. Any miss — wrong owner, missing request, or a `validate_tenant_ownership`
  failure — returns **HTTP 404** (non-disclosing: it never reveals whether another
  client's request exists).
- **Legacy dual-read:** only when the REQUEST has no canonical `quote_status` does
  the handler load the legacy PET (`PET#{pet_id}/CLIENT#{client_id}`) to resolve
  legacy pricing; canonical always wins. A legacy PET read failure degrades to
  `None` (canonical/empty projection) rather than erroring.
- Returns `build_client_quote_projection(request_item, legacy_pet_item)` **unchanged**
  — the hard allowlist is the single source of client-visible fields. No internal
  fields are appended: internal notes, internal pricing notes, `quote_history`,
  `audit_log`, `stripe_*`, and tenant-internal metadata are absent from the response.

---

## Verification

- `py -m py_compile src/backend/handlers/admin_handler.py` — clean.
- New handler tests: **23 passed** (`tests/backend/test_quote_contract_handlers.py`),
  covering: admin update role gates, tenant mismatch, requestId-only lookup
  resolution, first-draft `DRAFT`/`QUOTE_NEEDED` mirror, invalid payment requirement,
  empty update, commercial-change revision bump on a SENT quote, internal-note-only
  no-revise/no-mirror, no-`APPROVED` assertions; send `DRAFT → SENT` with
  `QUOTE_SENT` mirror, idempotent resend, zero-amount rejection, 409 on conditional
  failure, role/tenant gates; client read of own canonical quote, other-client → 404,
  tenant-mismatch → 404, non-client → 403, canonical-wins-over-legacy, legacy
  dual-read conversion, allowlist projection with internal/stripe/history/audit fields
  absent, and `NOT_REQUIRED` projection.
- Full backend suite (`py -m pytest tests/backend`): **78 failed, 1607 passed**. The
  78 failures match the documented pre-existing environment baseline exactly (zero
  new failures); `1607 = 1584` baseline-with-foundation-tests `+ 23` new handler
  tests. The pre-existing `test_r12g_stripe_checkout` failures are an unrelated
  environment artifact (they fail in isolation and import from a separate repo
  checkout); they are not introduced or affected by this change.
- `git diff --check` on the modified handler: clean. The new test file shows only a
  benign CRLF/LF line-ending notice (no whitespace errors), consistent with the repo.
- `git status --porcelain` shows exactly two paths changed: the modified
  `src/backend/handlers/admin_handler.py` and the new
  `tests/backend/test_quote_contract_handlers.py`. No Terraform, infrastructure,
  mobile, web, generated, or other files were touched.

---

## Explicitly out of scope (deferred / gated)

- **OPS-3A.1C** — API Gateway route resources for the three endpoints (new
  `{requestId}/quote`, `{requestId}/quote/send`, and `/client/quotes/{requestId}`
  resources + methods + integrations). Until that deploy-gated slice lands and is
  applied, these handler branches are **not reachable** by any client.
- **OPS-3A.1D** — reviewed Terraform plan/apply for the above.
- **OPS-3A.2** — client Accept/Decline mutation, including the client-side
  `expected_revision` + 409 requirement (preserved for 3A.2; not weakened here).
  Client `ACCEPTED` → RequestStatus synchronization also remains 3A.2.
- **OPS-3A.3** — web/mobile quote UI.
- No Stripe/payment collection, no booking approval (`APPROVED` is never written by
  this slice), no migration, no tenant-resolution change, no production-data
  operation.

## Resume point

- Ending commit: `d29d833ca74bdc424e9fd9b0d26f7279e40faeda` (unchanged — no commit
  made this task).
- Files changed (uncommitted, for review): `src/backend/handlers/admin_handler.py`,
  `tests/backend/test_quote_contract_handlers.py`, and this release note.
- Tests run: focused handler suite (23 passed); full backend suite (78 failed /
  1607 passed — baseline-equivalent, no regression).
- Deployment status: NOT DEPLOYED. Routes not reachable (no API Gateway wiring).
- Exact next recommended action: Matthew review of this local implementation; on
  approval, the OPS-3A.1 foundation + 3A.1B handler integration may be committed,
  then proceed to OPS-3A.1C (API Gateway routes) as a separate deploy-gated slice.
- Required approval: Matthew (commit decision, and separately any Terraform/deploy).
