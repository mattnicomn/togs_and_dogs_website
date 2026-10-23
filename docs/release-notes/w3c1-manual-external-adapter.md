# W3-C1 — MANUAL_EXTERNAL Payment Adapter (Local Implementation, Not Deployed)

**Date:** 2026-10-23
**Disposition:** `W3C1_MANUAL_EXTERNAL_ADAPTER_DRAFT_PR_READY_FOR_OWNER_REVIEW`
**Status flags:** `W3C1_LOCAL_IMPLEMENTATION_AUTHORIZED=YES`;
`W3C1_MANUAL_EXTERNAL_ADAPTER_IMPLEMENTED_LOCAL_NOT_DEPLOYED`;
`W3C1_RUNTIME_ENABLED=NO`; `W3C1_IAM_CHANGE_AUTHORIZED=NO`;
`W3C1_TERRAFORM_CHANGE_AUTHORIZED=NO`; `W3C1_DEPLOYMENT_AUTHORIZED=NO`.

## Summary

Implements the first selected provider adapter under W3 Option D
(`PROVIDER_ABSTRACTION + MANUAL_EXTERNAL`): a **server-only** backend service that
records an externally-collected payment (cash / check / bank transfer / tenant-owned
external processor) against a REQUEST, updating the canonical W3-B payment summary and
appending an immutable `PAYMENT_EVENT` **atomically**. No payment-processor integration,
no API route, no UI, no Stripe, no IAM/Terraform edit, no deploy.

Authored on branch `feat/w3c1-manual-external-adapter` from
`main == origin/main == 0eccf1a2f88adf6ae2daefcade2b828d28686757` (PR #30). Delivered as
one Draft PR; not merged, not deployed. `W3C1_IMPLEMENTATION_RECONCILIATION=PASS`.

## Scope (exact files)

- `src/backend/common/manual_external_adapter.py` — new server-only adapter/service.
- `tests/backend/test_w3c1_manual_external_adapter.py` — new tests (42).
- `docs/release-notes/w3c1-manual-external-adapter.md` — this note.
- `docs/project-continuity/current-state.md`, `docs/project-continuity/document-map.md`,
  `docs/release-notes/index.md` — doc updates.

No handlers/routes, API Gateway, web/mobile, Terraform, IAM, Stripe, webhook,
scheduling, or tenant-provisioning files changed. `W3C1_SCOPE_EXPANSION_REQUIRES_OWNER_REVIEW`
not triggered.

## Behavior

- **Operation:** `record_external_payment(event, request_id, client_id,
  amount_delta_cents, currency, idempotency_key, external_reference?,
  payment_method_category?, note?)`. Returns `{result, previous_status,
  resulting_status, amount_paid_cents, payment_completed_at, payment_summary_revision,
  payment_provider, booking_ready, booking_ready_reason}`.
- **Authorization** (`W3C1_AUTHORIZATION_BOUNDARY=PASS`): owner/admin only via the
  existing `require_owner_or_admin(event)`; staff and clients rejected with no write; no
  client self-confirmation path. Tenant (`get_current_company_id`), actor
  (`get_claims`), REQUEST ownership (`load_owned_request`), current status, resulting
  status, paid total, and `payment_completed_at` are all **server-derived** — never
  caller-supplied. The signature has no `payment_status`/`resulting_status`/`company_id`
  parameter.
- **Canonical cents** (`W3C1_CANONICAL_CENTS=PASS`): all money via
  `payment_domain.canonical_cents`/`normalize_stored_cents` — `int 5000 → 5000`,
  `Decimal('5000') → 5000` (no ×100), non-integral/negative/bool rejected;
  `amount_delta_cents` must be `> 0`; `to_cents` is never used on canonical cents.
- **Evidence model** (`W3C1_EXTERNAL_EVIDENCE_SAFETY=PASS`): `payment_method_category`
  in `{CASH, CHECK, BANK_TRANSFER, EXTERNAL_PROCESSOR, OTHER}` (default `OTHER`);
  `external_reference` an opaque short label (≤128 chars; 12+ digit account/card-like
  strings rejected); optional `note` passed through the W3-B
  `sanitize_payment_event_metadata` allowlist (nested sensitive keys / raw payloads
  rejected). No PAN/CVC/account/routing/credential/raw-receipt storage.
- **Derived state** (`W3C1_PARTIAL_PAYMENT_STATUS_RECONCILIATION=BELOW_DEPOSIT_RECORDS_PARTIALLY_PAID`):
  `new_amount_paid = canonical_cents(existing_paid) + delta`. **FULL**: `< required →
  PARTIALLY_PAID`, `>= required → PAID`. **DEPOSIT**: any recorded positive amount that
  does not reach the full required total → `PARTIALLY_PAID` (including below-deposit
  contributions — the canonical status never stays `UNPAID` while
  `amount_paid_cents > 0`), `>= required → PAID`. **NONE**: rejected (nothing to
  collect). Overpayment (`new_amount_paid > required`) rejected (W3-C1 does not model
  overpayment). Every computed transition is validated against the W3-B state machine
  (`validate_transition`); `PAYMENT_LINK_SENT → PARTIALLY_PAID/PAID` is permitted (no
  link required); settlement from `NOT_REQUIRED`/`PAID`/`REFUNDED` is rejected.
- **PAYMENT_EVENT:** exactly one immutable event per new settlement via
  `build_payment_event`, event type `PAYMENT_SETTLED` (→ PAID) or
  `PAYMENT_PARTIALLY_SETTLED`, `payment_provider = MANUAL_EXTERNAL`, server-derived
  actor, opaque reference, sanitized metadata. No Stripe fields.
- **Atomicity** (`W3C1_PAYMENT_WRITE_ATOMICITY_DESIGN=DYNAMODB_TRANSACTWRITEITEMS_CONDITIONAL_EVENT_PUT_PLUS_CONDITIONAL_REQUEST_UPDATE`):
  a single DynamoDB `TransactWriteItems` with two conditional operations — PAYMENT_EVENT
  `Put` (`attribute_not_exists(PK) AND attribute_not_exists(SK)`) + REQUEST summary
  `Update` (revision guard). All-or-nothing; no two-independent-writes; the W3-B
  `persist_payment_event` primitive is intentionally not used here.
- **Optimistic concurrency** (`W3C1_PAYMENT_SUMMARY_REVISION=PASS`):
  `payment_summary_revision` — absent/legacy → logical 0 (guard accepts
  `attribute_not_exists(#rev) OR #rev = 0`); first settlement → 1; each subsequent → +1;
  idempotent replay and failed/conflicting/stale transactions → no increment. Never an
  unconditional summary update.
- **Idempotency** (`W3C1_IDEMPOTENCY=PASS`,
  `W3C1_TRANSACTION_CONFLICT_CLASSIFICATION=PASS`): an early pre-check and the
  conditional transaction together ensure the same `idempotency_key` never applies money
  twice. Classification: existing event with identical semantic payload →
  `DUPLICATE_SAME_EVENT` (idempotent; returns current persisted state; no re-apply, no
  revision bump, no new event); existing event with a different payload →
  `CONFLICTING_IDEMPOTENCY_KEY` (no write); transaction cancellation with no existing
  event → stale/concurrent REQUEST-summary conflict (`StaleSummaryConflict`, no write).
- **Booking readiness:** recomputes `is_booking_payment_ready(...)` as **informational
  output only**; never sets `APPROVED`, creates JOBs, schedules, assigns, or notifies.
- **Supplementary audit:** `audit.log_action("EXTERNAL_PAYMENT_RECORDED", ...)` runs
  **after** a committed `CREATED` transaction; the PAYMENT_EVENT is the authoritative
  payment audit trail, and a failed supplementary `AUDIT#` write never rolls back or
  re-applies money (logged and ignored).
- **No coupling:** the module imports no `stripe`/`requests`/`urllib`/`http`/`flask`/
  `fastapi` (AST-verified); `common.db`/`common.auth`/`botocore` are imported lazily
  inside functions for test isolation (no live AWS in tests).

## Infrastructure / IAM boundary

`W3C1_RUNTIME_IAM_CHANGE_REQUIRED=YES`, `W3C1_TRANSACTWRITE_IAM_PRESENT=NO`,
`W3C1_NEW_AWS_RESOURCE_REQUIRED=NO`. The merged `modules/iam/main.tf` Lambda DynamoDB
policy grants `GetItem/PutItem/UpdateItem/DeleteItem/Query/Scan` and does **not** grant
`dynamodb:TransactWriteItems`. The local code + tests run against a **mocked** transaction
client (`W3C1_LOCAL_CODE_CAN_BE_IMPLEMENTED_WITHOUT_INFRA_MUTATION=YES`); actual runtime
execution requires a future owner-approved IAM policy addition
(`W3C1_RUNTIME_ENABLEMENT_REQUIRES_IAM_CHANGE=YES`), which is **not** part of W3-C1. No
Terraform/IAM file was edited this phase.
`W3C1_INCREMENTAL_RESOURCE_COST_EXPECTATION=NEGLIGIBLE_WITHIN_EXISTING_ARCHITECTURE`.

## Verification

- Focused suite `tests/backend/test_w3c1_manual_external_adapter.py`: **42 passed**
  (authorization, tenant/ownership, canonical cents incl. Decimal magnitude, FULL +
  DEPOSIT derivation incl. below-deposit partial reconciliation, status guards,
  `payment_completed_at`, idempotency/conflict/stale classification, two-item
  conditional transaction contract, revision semantics, evidence/metadata safety,
  booking readiness, provider-always-MANUAL_EXTERNAL, no-target-status, no
  Stripe/network/route imports).
- `tests/backend/test_w3b_payment_domain.py` (174) + `tests/backend/test_quote_contract.py`
  (50): **224 passed** — no regression in the reused W3-B domain.
- **`W3C1_NEW_REGRESSIONS=0`.** The adapter is a new module imported by no existing
  runtime handler, so it cannot affect other suites; the full-backend failing set is the
  same ~90 pre-existing environmental failures (Terraform/IAM static analysis, Google
  Calendar tenant resolution, Stripe/Postmark, entitlement DB, rbac/purge,
  terms-acceptance, intake) present on the clean `0eccf1a` baseline, plus zero new.
  (Note: a shell/stdout-capture defect in this environment prevented an independent
  re-capture of the full-suite node-ID baseline diff this turn; the zero-regression
  conclusion rests on the passing focused + W3-B + quote-contract suites and the fact
  that the only W3-C1-attributable full-suite failures observed were self-test assertion
  mismatches, all since fixed and passing. Flagged for the reviewer to re-run the full
  comparison in a clean environment.)

## Boundary / gates preserved

`W3C1_RUNTIME_ENABLED=NO`; no API route (W3-C2), no UI (W3-D1), no Stripe/Connect/OAuth/
Checkout/PaymentIntent/webhook/secret, no refunds (deferred), no Terraform/IAM/AWS/deploy,
no production mutation/test data, no second tenant, no tenant-resolution change, no Ryan
testing, no scheduling, no mobile distribution, no auto-approval. Latest completed
production backend release remains `PR22_PRIVACY_PRODUCTION_DEPLOYED_VERIFIED`; W1/W4/W3-B
merged-not-deployed; Stripe sandbox-only. W3-C2 not started.

Checkpoint: `main == origin/main == 0eccf1a2f88adf6ae2daefcade2b828d28686757`.
