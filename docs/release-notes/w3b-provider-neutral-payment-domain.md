# W3-B — Provider-Neutral Payment Domain (Local Implementation, Not Deployed)

**Date:** 2026-09-24
**Disposition:** `W3B_PROVIDER_NEUTRAL_PAYMENT_DOMAIN_READY_FOR_FINAL_REVIEW`
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
- `tests/backend/test_w3b_payment_domain.py` — new unit/integration tests (110).
- `docs/release-notes/w3b-provider-neutral-payment-domain.md` — this note.
- `docs/release-notes/index.md`, `docs/project-continuity/current-state.md`,
  `docs/planning/petcare-hero-tenant-customer-payment-architecture.md` — doc updates.

No other files changed. `W3B_SCOPE_REVIEW=PASS` (no Terraform / API / Stripe-exec /
UI / scheduling / tenant-resolution change).

## What the domain provides

- **Reuses** canonical enums (`PaymentRequirement` NONE|DEPOSIT|FULL, `PaymentStatus`
  NOT_REQUIRED|UNPAID|PAYMENT_LINK_SENT|PARTIALLY_PAID|PAID|REFUNDED, `QuoteStatus`) and
  money helpers (`to_cents`, `normalize_stored_cents`, `normalize_legacy_payment_status`)
  from `common/quote_contract.py` rather than defining competing vocabulary.
  `W3B_EXISTING_DOMAIN_RECONCILIATION=PASS`.
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
- **Amount invariants** (`validate_payment_amounts`): integer minor units only (no
  float authority), non-negative, currency required when money is required, and no
  overpayment (paid must not exceed the relevant required amount; W3-B does not model
  overpayment). `W3B_PAYMENT_AMOUNT_INVARIANTS=PASS`.
- **Provider abstraction** (`PaymentProvider`): `MANUAL_EXTERNAL` (selected MVP, only
  `W3B_SUPPORTED`), `STRIPE_CONNECT_DIRECT` (long-term direction, adapter not built
  here), `STRIPE_CONNECT_MARKETPLACE` (forward label only, not selected, not
  executable). `W3B_PROVIDER_ABSTRACTION=PASS`.
- **Booking-readiness predicate** (`is_booking_payment_ready`): pure `(ready, reason)`;
  amount-aware strengthening of the existing status-only
  `evaluate_booking_approval_predicate`. NONE → ready iff quote ACCEPTED; DEPOSIT →
  accepted + paid ≥ deposit + status in {PARTIALLY_PAID, PAID}; FULL → accepted + paid ≥
  total + status PAID. Never approves/books/schedules; preserves
  *quote accepted ≠ paid ≠ APPROVED*. `W3B_BOOKING_READINESS_PREDICATE=PASS`;
  `W3B_AUTO_APPROVAL_ADDED=NO`.
- **Hybrid persistence model**: provider-neutral REQUEST-level summary
  (`build_payment_summary`) plus append-only `PAYMENT_EVENT` records
  (`build_payment_event`). `W3B_PAYMENT_ENTITY_MODEL=HYBRID_REQUEST_SUMMARY_PLUS_PAYMENT_EVENT`.
  Events live in the **existing single table**, in the REQUEST's item collection
  (`PK=REQ#{request_id}`, `SK=PAYEVENT#{idempotency_key}`), so a conditional
  `attribute_not_exists` put is naturally duplicate-safe — **no new table or GSI**:
  `W3B_PAYMENT_EVENT_STORAGE_INFRA_CHANGE_REQUIRED=NO`;
  `W3B_PAYMENT_EVENT_IDEMPOTENCY=PASS`.
- **MANUAL_EXTERNAL boundary**: events carry only an **opaque** `provider_txn_ref` and
  an `actor`; a client can never self-assert PAID; forbidden metadata keys
  (`pan`/`cvc`/`secret`/`token`/`jwt`/auth material, …) are rejected. No PAN/CVC/secret
  is ever stored. `W3B_MANUAL_EXTERNAL_BOUNDARY=PASS`;
  `W3B_CLIENT_PAYMENT_PRIVACY_BOUNDARY=PASS`.
- **Tenant isolation**: `company_id` is required and trusted on every event; events are
  scoped under the tenant/request-owned REQUEST key. `W3B_PAYMENT_TENANT_ISOLATION=PASS`.
- **No network coupling**: the module imports no `stripe`/`requests`/`urllib`/`boto3`
  (verified by AST inspection in tests); persistence is left to callers.

## Verification

- Focused suite `tests/backend/test_w3b_payment_domain.py`: **110 passed**.
- `tests/backend/test_quote_contract.py` (shared enums): **50 passed**.
- Full backend suite on the feature branch: **1870 passed, 90 failed**.
- Clean baseline at `f1c49fe` (throwaway worktree, since removed with
  `git worktree remove --force`, no prune): **1760 passed, 90 failed**.
- Failing-test node-ID sets are **identical** between baseline and feature branch
  (`Compare-Object` → 0 newly failing, 0 newly passing among the failures); the +110
  passing delta is exactly the new W3-B tests. **`W3B_NEW_REGRESSIONS=0`.** The 90
  pre-existing failures are environmental (Terraform/IAM static analysis, Google
  Calendar tenant resolution, Stripe/Postmark, entitlement DB, rbac/purge,
  terms-acceptance, intake) and unrelated to the payment domain.

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
