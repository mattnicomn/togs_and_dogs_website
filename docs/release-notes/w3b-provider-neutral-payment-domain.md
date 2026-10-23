# W3-B — Provider-Neutral Payment Domain (Local Implementation, Not Deployed)

**Date:** 2026-10-23
**Disposition:** `W3B_PROVIDER_NEUTRAL_PAYMENT_DOMAIN_HARDENED_READY_FOR_FINAL_REVIEW`
**Status flags:** `W3_B_IMPLEMENTATION_AUTHORIZED=YES`;
`W3_B_PROVIDER_NEUTRAL_PAYMENT_DOMAIN_IMPLEMENTED_LOCAL_NOT_DEPLOYED`;
`W3_B_DEPLOYED=NO`.

## Summary

Implements the provider-neutral payment **domain** selected under W3 Option D
(`PROVIDER_ABSTRACTION + MANUAL_EXTERNAL` first; `STRIPE_CONNECT_DIRECT` long-term).
This is a pure, backend domain module plus unit/integration tests using mocks / local
data only. It is built **alongside** the existing deployed Stripe booking-payment path
and does **not** switch runtime execution, call any Stripe API, touch secrets, or
deploy. No Stripe Connect/OAuth/Checkout/PaymentIntent/webhook, no Terraform, no AWS,
no UI, no scheduling, no tenant-resolution change.

Authored on branch `feat/w3b-provider-neutral-payment-domain` from
`main == origin/main == f1c49fe99e31ce29ca3914fd41e425b9dac212e6` (W3-A Option D docs,
PR #28). Delivered as **one Draft PR** to `main`; not merged, not deployed.

## Scope (exact files)

- `src/backend/common/payment_domain.py` — new provider-neutral payment domain.
- `tests/backend/test_w3b_payment_domain.py` — new unit/integration tests (174).
- `docs/release-notes/w3b-provider-neutral-payment-domain.md` — this note.
- `docs/release-notes/index.md`, `docs/project-continuity/current-state.md`,
  `docs/planning/petcare-hero-tenant-customer-payment-architecture.md` — doc updates.

No other files changed. `W3B_SCOPE_REVIEW=PASS` (no Terraform / API / Stripe-exec /
UI / scheduling / tenant-resolution change).

## What the domain provides

- **Reuses** canonical enums (`PaymentRequirement` NONE|DEPOSIT|FULL, `PaymentStatus`
  NOT_REQUIRED|UNPAID|PAYMENT_LINK_SENT|PARTIALLY_PAID|PAID|REFUNDED, `QuoteStatus`) and
  the strict minor-unit helper `normalize_stored_cents` (plus
  `normalize_legacy_payment_status`) from `common/quote_contract.py` rather than
  defining competing vocabulary. `W3B_EXISTING_DOMAIN_RECONCILIATION=PASS`.
- **Status set unchanged** — exactly the existing six values; no speculative
  `PENDING`/`FAILED`/`PARTIALLY_REFUNDED`. `PAYMENT_LINK_SENT` represents
  "requested / waiting"; provider failures are recorded as `PAYMENT_EVENT` metadata
  (`PAYMENT_FAILED`), not a new authoritative status. `W3B_PAYMENT_STATUS_SET` = 6.
- **Normalization** (`normalize_payment_status`): canonical pass-through;
  lowercase/live values written by the current Stripe path (`paid`,
  `payment_link_sent`, …) and documented legacy values map up; `None`/empty →
  `NOT_REQUIRED`; unknown → `UNKNOWN` sentinel (never silently PAID / NOT_REQUIRED, fail
  safe). `W3B_PAYMENT_STATUS_NORMALIZATION=PASS`; `W3B_LEGACY_PAYMENT_COMPATIBILITY=PASS`.
- **State machine** (`can_transition`/`validate_transition`): deterministic allowed
  transitions; `NOT_REQUIRED` and `REFUNDED` terminal; no backward/fabricated-money
  transitions (e.g. `PAID→UNPAID`, `REFUNDED→PAID`, `NOT_REQUIRED→PAID` rejected);
  same-status replay is idempotent. `W3B_PAYMENT_STATE_MACHINE=PASS`.
- **Canonical cents** (`canonical_cents` → `normalize_stored_cents`): every W3-B money
  field (`amount_required_cents`, `amount_paid_cents`, `deposit_amount_cents`,
  `amount_delta_cents`) is strict minor units — `int 5000 → 5000`,
  `Decimal('5000') → 5000`, `'5000' → 5000`, `Decimal('50.5')`/negative/`bool` rejected,
  magnitude preserved across the DynamoDB `Decimal` round-trip with **no ×100
  inflation**. The module deliberately does **not** use `to_cents` (which treats
  non-`int` as major units and multiplies by 100); `to_cents`'s global behavior is
  unchanged. `W3B_CANONICAL_CENTS_MAGNITUDE_PRESERVED=PASS`.
- **Amount invariants** (`validate_payment_amounts`): integer minor units only (no
  float authority), non-negative, currency required when money is required, and no
  overpayment (paid must not exceed the relevant required amount; W3-B does not model
  overpayment). `W3B_PAYMENT_AMOUNT_INVARIANTS=PASS`.
- **Provider abstraction + execution boundary** (`PaymentProvider`): known identifiers
  are distinguished from providers allowed for active operations.
  `validate_known_provider` accepts any of `MANUAL_EXTERNAL` /
  `STRIPE_CONNECT_DIRECT` / `STRIPE_CONNECT_MARKETPLACE`; `validate_active_provider`
  accepts only `W3B_SUPPORTED = {MANUAL_EXTERNAL}`. Active builders/persistence
  (`build_payment_event`, `build_payment_summary`, `persist_payment_event`) reject
  Stripe Connect Direct (known, selected long-term, **not** executable in W3-B) and
  Marketplace (label only). `W3B_PROVIDER_ABSTRACTION=PASS`;
  `W3B_PROVIDER_EXECUTION_BOUNDARY=PASS`.
- **Booking-readiness predicate** (`is_booking_payment_ready`): pure `(ready, reason)`;
  amount-aware strengthening of the existing status-only
  `evaluate_booking_approval_predicate`. NONE → ready iff quote ACCEPTED; DEPOSIT →
  accepted + paid ≥ deposit + status in {PARTIALLY_PAID, PAID}; FULL → accepted + paid ≥
  total + status PAID. Never approves/books/schedules; preserves
  *quote accepted ≠ paid ≠ APPROVED*. `W3B_BOOKING_READINESS_PREDICATE=PASS`;
  `W3B_AUTO_APPROVAL_ADDED=NO`.
- **Hybrid persistence model with real conditional-write idempotency**:
  provider-neutral REQUEST-level summary (`build_payment_summary`) plus an append-only
  `PAYMENT_EVENT` write path (`persist_payment_event`).
  `W3B_PAYMENT_ENTITY_MODEL=HYBRID_REQUEST_SUMMARY_PLUS_PAYMENT_EVENT`. Events live in
  the **existing single table**, in the REQUEST's item collection
  (`PK=REQ#{request_id}`, `SK=PAYEVENT#{idempotency_key}`). The write is a conditional
  put — `attribute_not_exists(PK) AND attribute_not_exists(SK)` — so an existing event
  is **never overwritten**; deterministic SK alone is not relied on. The result is an
  explicit contract: `CREATED`, `DUPLICATE_SAME_EVENT` (same key + identical semantic
  payload → idempotent no-op/success), or `CONFLICTING_IDEMPOTENCY_KEY` (same key +
  different payload → **not** success; caller maps to 409). A non-conditional DynamoDB
  error is surfaced as a `PaymentDomainError`, not silently treated as success. **No new
  table or GSI**: `W3B_PAYMENT_EVENT_STORAGE_INFRA_CHANGE_REQUIRED=NO`;
  `W3B_PAYMENT_EVENT_PERSISTENCE=PASS`; `W3B_PAYMENT_EVENT_IDEMPOTENCY=PASS` (proven by
  conditional-write tests, not deterministic-key tests alone).
- **Tenant / request ownership enforcement** (`load_owned_request`): before any write,
  the canonical REQUEST is loaded by its key (`PK=REQ#{request_id}`,
  `SK=CLIENT#{client_id}`), must exist, and its trusted `company_id` (defaulting to
  `DEFAULT_COMPANY_ID` when absent, the live convention) must equal the supplied trusted
  `company_id`; `client_id` is validated against the record. Fail closed on any mismatch
  (no write). A spoofed `event.company_id` cannot widen access because ownership is
  decided by the stored REQUEST, not the event body — not merely a non-empty argument.
  `W3B_PAYMENT_TENANT_ISOLATION=PASS`.
- **MANUAL_EXTERNAL boundary**: events carry only an **opaque** `provider_txn_ref` and
  an `actor`; a client can never self-assert PAID. `W3B_MANUAL_EXTERNAL_BOUNDARY=PASS`;
  `W3B_CLIENT_PAYMENT_PRIVACY_BOUNDARY=PASS`.
- **Audit metadata safety** (`sanitize_payment_event_metadata`): allowlist-oriented and
  recursive. Metadata must be a dict of audit-safe scalars/lists/nested dicts; sensitive
  key patterns (`secret`/`password`/`token`/`authorization`/`api_key`/`card`/`pan`/
  `cvc`/`cvv`/`credential`/`private_key`/`bearer`/…) are rejected at **any** nesting
  depth (e.g. `{"details": {"access_token": "x"}}`); raw/opaque provider payload
  objects and `bytes` are rejected; depth/breadth/string-length are capped. No provider
  webhook payload is stored. `W3B_PAYMENT_EVENT_METADATA_SAFETY=PASS`.
- **No Stripe/network coupling**: the module imports no `stripe`/`requests`/`urllib`/
  `http` at any level (AST-verified). The persistence layer imports `common.db` and
  `botocore` **lazily inside the function**, so the pure domain stays import-clean at
  module top level (also AST-verified); there is no new table/GSI/infrastructure.

## Verification (after PR #29 hardening)

- Focused suite `tests/backend/test_w3b_payment_domain.py`: **174 passed** (110
  original + 64 new hardening tests for canonical cents / persistence / tenant
  isolation / provider boundary / metadata safety).
- `tests/backend/test_quote_contract.py` (shared enums): **50 passed**.
- Full backend suite on the feature branch: **1934 passed, 90 failed**.
- Clean baseline at `f1c49fe` (throwaway worktree; its git worktree **registration was
  removed** with `git worktree remove --force` and **no `git worktree prune` was run** —
  a leftover OS temp directory may remain due to a lingering file handle, which does not
  affect repository worktree state): **1760 passed, 90 failed**.
- Failing-test node-ID sets are **identical** between baseline and feature branch
  (`Compare-Object` → `new=0 gone=0`); the +174 passing delta over baseline is exactly
  the W3-B tests. **`W3B_NEW_REGRESSIONS=0`.** The 90 pre-existing failures are
  environmental (Terraform/IAM static analysis, Google Calendar tenant resolution,
  Stripe/Postmark, entitlement DB, rbac/purge, terms-acceptance, intake) and unrelated
  to the payment domain.

## PR #29 hardening summary

Addressed the independent review (`PR29_W3B_FINAL_REVIEW=CHANGES_REQUIRED`):

1. **Canonical cents bug fixed** — switched the four `*_cents` paths off `to_cents`
   (major-unit ×100) onto strict `canonical_cents`/`normalize_stored_cents`.
   `W3B_CANONICAL_CENTS_MAGNITUDE_PRESERVED=PASS`.
2. **Real persistence** — added `persist_payment_event` with an append-only conditional
   write and a `CREATED`/`DUPLICATE_SAME_EVENT`/`CONFLICTING_IDEMPOTENCY_KEY` result
   contract. `W3B_PAYMENT_EVENT_PERSISTENCE=PASS`; `W3B_PAYMENT_EVENT_IDEMPOTENCY=PASS`.
3. **Tenant/request ownership** — `load_owned_request` enforces existence + trusted
   `company_id`/`client_id` ownership, fail-closed, before any write.
   `W3B_PAYMENT_TENANT_ISOLATION=PASS`.
4. **Provider execution boundary** — known vs active split; active paths reject Stripe
   Connect Direct/Marketplace. `W3B_PROVIDER_EXECUTION_BOUNDARY=PASS`.
5. **Audit metadata safety** — recursive allowlist sanitizer rejecting nested
   sensitive keys / raw payloads. `W3B_PAYMENT_EVENT_METADATA_SAFETY=PASS`.

The state machine and the six canonical statuses are unchanged.

## Boundary / gates preserved

`W3_B_DEPLOYED=NO` — a Draft PR changes neither `main` nor production; latest completed
production backend release remains `PR22_PRIVACY_PRODUCTION_DEPLOYED_VERIFIED`. No
Stripe API/secret/Connect/OAuth/Checkout/PaymentIntent/webhook; no Terraform/AWS/API
Gateway/deploy; no runtime switch of the existing Stripe path; no UI mutation; no
auto-approval; no client `mark-paid`. `SCHEDULING_WORKSTREAM_STATUS=DRAFT_PR_DELIVERY_CHECKPOINT`;
`SCHEDULING_PR_MERGE_AUTHORIZED=NO`; Stripe sandbox-only; `RYAN_TESTING_AUTHORIZED=NO`;
no second tenant; no production test data; no worktree prune/repair. W3-C (Stripe Connect
Direct adapter) is **not** started and requires separate explicit authorization.

Checkpoint: `main == origin/main == f1c49fe99e31ce29ca3914fd41e425b9dac212e6`.
