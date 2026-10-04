# OPS-3A.1 — Backend Quote Contract + Client-Safe Read (local implementation)

Status: **LOCAL IMPLEMENTATION — READY FOR REVIEW. NOT DEPLOYED.** No production
deployment, Terraform, AWS, Stripe, migration, or production-data operation occurred.

Starting checkpoint: `main == origin/main == 1f3da4756fd4fa6b9efdf5622ddd31682893a9be`
(working tree clean, index empty, stash empty at task start).

Approved contract reference: `docs/planning/petcare-hero-quote-contract.md`
(product-contract approved by Matthew on 2026-10-03). This slice implements the
**backend contract/read foundation** only; it is OPS-3A.1 — the first of the
OPS-3A slices.

---

## What was implemented

A single new, pure, framework-free module plus focused tests:

- `src/backend/common/quote_contract.py`
- `tests/backend/test_quote_contract.py`

The module has **no AWS / HTTP / DynamoDB coupling** so it can be unit-tested in
isolation and consumed by the later handler-wiring and client/mobile slices. It
implements the approved canonical contract:

### A. Canonical quote fields + enums (REQUEST-owned)
- `QuoteStatus`: `NOT_REQUIRED | DRAFT | SENT | ACCEPTED | DECLINED`, plus
  `SUPERSEDED` which is **history-only** (`CURRENT_VALID` frozenset excludes it;
  `validate_quote_status_current` rejects `SUPERSEDED` and unknown values).
- `PaymentRequirement`: `NONE | DEPOSIT | FULL`.
- `PaymentStatus`: normalized single vocabulary
  (`NOT_REQUIRED | UNPAID | PAYMENT_LINK_SENT | PARTIALLY_PAID | PAID | REFUNDED`).
- Canonical field set modeled on the REQUEST record: `quote_status`,
  `quote_revision`, `quote_amount_cents`, `currency`, `deposit_amount_cents`,
  `payment_requirement`, `quote_notes_client`, `quote_notes_internal`,
  `quote_sent_at`, `quote_accepted_at`, `quote_accepted_revision`, `quote_history`.

### B. Owner/admin quote mutation foundation (pure logic)
- `apply_quote_update(current_req, incoming, now_iso)` — draft/update. A
  client-visible **commercial** change (`quote_amount_cents`, `currency`,
  `deposit_amount_cents`, `payment_requirement`, `quote_notes_client`) to an already
  `SENT`/`ACCEPTED` quote starts a **new revision**: snapshots the prior quote into
  `quote_history` as `SUPERSEDED`, increments `quote_revision`, clears acceptance,
  and returns status to `DRAFT`. **Internal-only** note changes
  (`quote_notes_internal`, `internal_pricing_notes`) never bump the revision or clear
  acceptance. The function never writes a RequestStatus and never emits `APPROVED`;
  it does not mutate its input.
- `apply_quote_send(current_req, now_iso)` — `DRAFT → SENT` (`quote_sent_at` set);
  rejects zero amount and non-DRAFT status.

### C. Client-safe quote read projection
- `build_client_quote_projection(request_item, legacy_pet_item=None)` — builds the
  client-visible projection via a hard allowlist (`CLIENT_QUOTE_ALLOWLIST`) and an
  explicit forbidden set (`CLIENT_QUOTE_FORBIDDEN`). It never emits internal notes,
  internal pricing notes, `quote_history`, `audit_log`, any `stripe_*`/payment
  internals, or tenant-internal metadata. `payment_required` is a derived boolean.
  **Authorization is the caller's responsibility** — the projection is pure and the
  handler (deferred, see below) MUST enforce tenant context and authenticated client
  ownership before returning it.

### D. Legacy dual-read compatibility (no migration)
- `resolve_quote_from_record(request_item, legacy_pet_item)` — canonical
  `quote_status` wins when present; otherwise derives the quote from legacy signals
  (PET `quote_amount` Decimal + `payment_status`, and the REQUEST quote-summary
  status). `legacy_quote_amount_to_cents` converts legacy Decimal **major units** to
  integer cents at **read time only** (half-up); no record is mutated and no
  DynamoDB migration is performed.
- `resolve_commercial_quote_status(...)` — single decision point proving
  `quote_status` is authoritative for commercial logic and the RequestStatus
  quote-summary values (`QUOTE_NEEDED`/`QUOTE_SENT`/`QUOTED`) are never commercially
  authoritative.

### E. Payment-requirement normalization + booking-approval predicate
- `normalize_legacy_payment_status(...)` maps legacy PET/REQ vocabularies to the
  canonical `PaymentStatus`.
- `evaluate_booking_approval_predicate(quote_status, payment_requirement,
  payment_status, quote_amount_cents, payment_waived)` — the approved R4 predicate as
  a **read-only eligibility** check: quote condition (`NOT_REQUIRED`/amount 0, OR
  `ACCEPTED`) AND payment condition (`NONE` → satisfied; `DEPOSIT` → `PARTIALLY_PAID`
  or `PAID`; `FULL` → `PAID`; authorized owner/admin waiver satisfies payment).
  `PARTIALLY_PAID` never satisfies `FULL`. It returns `(ok, reason)` and **never
  performs or implies the `APPROVED` transition** — quote acceptance does not
  auto-approve a booking (approved decision 13).

Money is integer minor units (cents) throughout; `to_cents` treats a bare `int` as
already-cents, converts Decimal/float/str major units half-up, and rejects
negative/boolean/non-numeric input. Integer cents serialize as plain JSON integers
(compatible with the existing `DecimalEncoder` response path).

---

## Tests

`tests/backend/test_quote_contract.py` — **35 tests, all passing** (pytest, Python
3.13). Coverage includes: integer-cents behavior and JSON serialization; legacy
Decimal→cents fallback; client-safe allowlist and internal-field exclusion;
`quote_status` precedence over legacy RequestStatus; RequestStatus compatibility
(summary values never commercially authoritative); `SUPERSEDED` cannot be the
current status; revision increment on client-visible commercial change;
internal-only note change does NOT create a revision or clear acceptance; draft/send
transitions; invalid `payment_requirement`/`quote_status` rejection; and the
booking-approval predicate including "no implicit APPROVED" and "`PARTIALLY_PAID`
never satisfies `FULL`".

### Validation results
- Focused: `tests/backend/test_quote_contract.py` → **35 passed**.
- Full backend suite regression check:
  - baseline (excluding the new test): **78 failed, 1543 passed**;
  - with the new test: **78 failed, 1578 passed**.
  - Net effect of this slice: **+35 passing, +0 failing**. The 78 failures are the
    pre-existing environment baseline (DynamoDB `ResourceNotFound` with no real
    table, tenant-fallback, Google-calendar provider, service-type contract drift,
    `fromisoformat` env), none of which involve `quote_contract`.

Run with `py -m pytest tests/backend/test_quote_contract.py` (the environment's
Python 3.13 is on the `py` launcher; `python` is not on PATH).

---

## What is deferred (and why)

### Deferred within OPS-3A.1 — HTTP endpoint wiring (routing/Terraform-gated)
The approved endpoints — owner/admin quote write/send and the client-safe
`GET /client/quotes/{requestId}` — are **not wired** in this slice. The production
API Gateway (`modules/api/main.tf`) uses **explicit per-route Terraform resources
with no `{proxy+}` catch-all**; every path (e.g. `client_pets`, `client_requests`,
`admin_requests`) is individually declared and listed in the deployment
`depends_on` and the semantic-fingerprint resource map. Adding new quote routes
therefore requires **new Terraform API Gateway resources** → `terraform
plan`/`apply`, which is deploy-gated and explicitly out of scope for this task.
Wiring the handlers + routes is the remainder of OPS-3A.1 and must be a separate,
Matthew-approved deployment (reviewed RC, tests, plan/apply separation). The pure
module here is designed to be imported directly by those handlers with no change.

### Deferred to OPS-3A.2 — client Accept/Decline
Client Accept/Decline mutation (`POST /client/quotes/{id}/accept|decline` with
mandatory `expected_revision` and HTTP 409 on stale revision) is **not implemented**
here. The audit confirmed the project already uses DynamoDB `ConditionExpression`
optimistic concurrency (e.g. admin job-start), which OPS-3A.2 will reuse for the
revision guard.

### Deferred to OPS-3A.3 — web/mobile quote UI
No web or mobile UI was added.

### Deferred to OPS-3B — payment / Stripe
No Stripe interaction, payment-link, or payment collection. Stripe remains
sandbox-only and separately gated (EIN blocker unchanged).

---

## Compatibility confirmation (approved contract preserved)
- No new `RequestStatus`; no `BOOKING_CONFIRMED`.
- No quote expiration; no line items (single total `quote_amount_cents`).
- Existing `APPROVED` reused; acceptance does not auto-approve.
- `quote_status` authoritative; RequestStatus quote values remain compatibility
  summaries; `SUPERSEDED` history-only.
- No DynamoDB migration; legacy PET/REQ values preserved and dual-read at read time.
- No Visit/JOB change; no tenant-resolution change; no Stripe.

## Files changed
- `src/backend/common/quote_contract.py` (new)
- `tests/backend/test_quote_contract.py` (new)
- `docs/release-notes/ops3a1-backend-quote-contract-local-implementation.md` (this note)

## Recommended next action
Review this local implementation. On approval, proceed to the OPS-3A.1 **remainder**
as a separate deploy-gated slice: wire the owner/admin quote write/send handler
dispatch and the client-safe `GET /client/quotes/{requestId}` read into the existing
handlers, add the required new API Gateway routes via Terraform, and take it through
the normal reviewed-RC + plan/apply + Matthew-approved deployment. Then OPS-3A.2
(client Accept/Decline) and OPS-3A.3 (web/mobile UI). OPS-3B (payment/Stripe)
remains separately gated.
