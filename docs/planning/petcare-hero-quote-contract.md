# PetCare Hero — Quote Contract Design (OPS-3A)

Status: **CONTRACT APPROVED (Matthew, 2026-10-03) — documentation only; runtime not
yet implemented.** This document defines the commercial quote contract before any
client/mobile quote UI is built. No runtime source, backend, mobile, web, Stripe, or
Terraform change accompanies it. The product-contract approval gate is **CLEARED**
(see "Product decisions — APPROVED BY MATTHEW ON 2026-10-03" and "Implementation
gate" below); bounded OPS-3A implementation may now proceed under the project's
normal release discipline (reviewed RC, tests, plan/apply separation, per-release
Matthew approval). OPS-3B (payment/Stripe) remains separate and Stripe-gated.

Checkpoint at authoring: branch `main`, HEAD == `origin/main` ==
`7700bddfeeb0a05570ef011a1a2572e2db5b0c7b`.

Final-review refinements (R1–R6) are appended at the end of this document and
tighten: RequestStatus vs `quote_status` authority (R1), money representation (R2),
revision semantics (R3), the booking-confirmation predicate (R4), client accept/
decline concurrency (R5), and the resulting field additions (R6).

Companion audit: see the "OPS-3 — Client Booking / Quote Experience (audit-first)"
section of `docs/planning/petcare-hero-operational-workflow-mobile-first.md` for the
source-cited current-state findings this design builds on.

---

## 0. Source-backed current state (recap)

- Quote fields today live on **PET metadata** (`PK=PET#{pet_id}`, `SK=CLIENT#{client_id}`):
  `quote_amount` (Decimal), `deposit_required`, `deposit_paid`, `payment_status`,
  `quote_sent_date`, `quote_accepted_date`, `quote_notes`, `internal_pricing_notes`
  (written via `PUT /admin/pets/{petId}`, owner/admin/staff with staff pricing redaction).
- Payment/Stripe fields live on the **REQ record**: `payment_status`
  (`unpaid`/`payment_link_sent`/`paid`), `stripe_checkout_session_id`,
  `stripe_payment_url`, `payment_amount_cents`, `payment_requested_at/by`,
  `payment_completed_at`.
- `payment_status` therefore exists in **two different domains with different
  vocabularies** (PET: `Accepted`/`Deposit Paid`/`Paid in Full`/…; REQ:
  `unpaid`/`payment_link_sent`/`paid`). Quote acceptance and payment are conflated
  in the PET field.
- Request status machine (`src/backend/common/status.py`) already has quote-phase
  **request** statuses: `QUOTE_NEEDED`, `QUOTE_SENT`, `QUOTED`, with transitions
  `QUOTE_SENT → APPROVED` and `QUOTE_SENT → QUOTE_NEEDED` (revision). `BOOKED` is a
  synonym of `APPROVED`. There is no `QUOTE_ACCEPTED`/`QUOTE_DECLINED` request status.
- A REQUEST can reference multiple pets (`pet_ids`) and multiple dates
  (`selected_dates`); JOBs are created by the async Lambda only on `APPROVED`.
- Clients cannot read `quote_amount` (redacted) and cannot write any quote field
  (`PUT /client/pets/{petId}` strict allowlist). No client quote-acceptance endpoint
  exists.

---

## 1. Canonical quote ownership (Phase 2)

**Recommendation: B — the quote belongs to the REQUEST / BOOKING, not the PET.**

Rationale against the current PET placement, from the stated requirements:
- A pet has **many** bookings over time; a single `quote_amount` on the pet cannot
  represent per-booking pricing and is overwritten each booking (loses history).
- Quote amounts vary **per booking**; a booking may cover multiple dates/visits and
  multiple pets — pricing is a property of the commercial booking, not any one pet.
- Commercial history must be **immutable/auditable per booking**; the REQ record
  already has `audit_log` and is the natural per-booking commercial anchor.
- Payment already lives on REQ (`payment_amount_cents`, Stripe ids). Co-locating the
  quote with payment on REQ removes the cross-entity split that forces today's
  conflation.
- Visit/JOB stays execution-only (OPS-0 invariant); the quote must not live there.

A separate QUOTE entity (option C) is **deferred as over-engineering for MVP**: the
only requirement it uniquely satisfies is multiple concurrent competing quotes per
booking, which is not a current product need. Revision history (Phase 7) is instead
captured by an append-only `quote_history` list on the REQ plus the existing
`audit_log`. If future needs demand independent quote documents (e.g., multiple
open quotes, PDF quote artifacts), promote to a QUOTE entity then.

**Canonical owner: the REQUEST record.** The PET keeps only pet-care data. Pricing
defaults/templates (e.g., a standard price per service type) are a separate future
concern and are not pet-level quote state.

### Migration note (detail in Phase 10)
PET quote fields become **legacy/read-fallback**. New writes target REQ. No
immediate data migration.

---

## 2. Proposed quote data model (Phase 3) — on the REQUEST record

Two **independent** lifecycles. Do not overload one field for both.

**Money is stored in integer minor units (cents).** See Final-QA refinement
"Money representation" (section R2) for the rationale; the field table below
reflects that decision. Field-table cross-references labelled "R#" point to the
Final-QA refinement sections appended at the end of this document.

### Quote fields (commercial offer + acceptance)
| Field | Type | Who writes | Notes |
|---|---|---|---|
| `quote_amount_cents` | integer | owner/admin | total for the booking in minor units (see R2, Phase 8) |
| `currency` | string, default `"USD"` | owner/admin (default) | single-currency MVP |
| `quote_status` | enum (see below) | owner/admin + client (accept/decline only) | QUOTE lifecycle (authoritative — see R1) |
| `quote_revision` | integer, default `1` | owner/admin | increments on each new revision of a SENT/ACCEPTED quote (R3) |
| `quote_sent_at` | ISO8601 | owner/admin | set when → SENT |
| `quote_accepted_at` | ISO8601 | client (or owner/admin on behalf) | set when → ACCEPTED; cleared on commercial revision (R3) |
| `quote_accepted_revision` | integer | client (or owner/admin) | which revision was accepted (concurrency; see R5) |
| `quote_declined_at` | ISO8601 | client (or owner/admin) | set when → DECLINED |
| `quote_notes_client` | string (≤2000) | owner/admin | client-facing note (commercial — see R3) |
| `quote_notes_internal` | string (≤2000) | owner/admin | internal-only, never client-visible (not commercial — see R3) |
| `quote_history` | append-only list | system | prior revision snapshots (amount_cents, revision, status, notes_client, timestamps) |

### Payment fields (settlement) — mostly already on REQ
| Field | Type | Who writes | Notes |
|---|---|---|---|
| `payment_status` | enum (see below) | owner/admin + Stripe webhook | PAYMENT lifecycle (normalized single vocabulary) |
| `payment_requirement` | enum (see R4) | owner/admin | declares what settlement gates confirmation |
| `deposit_amount_cents` | integer | owner/admin | optional; ≤ `quote_amount_cents` |
| `payment_amount_cents` | integer | payment-session (existing) | Stripe charge amount (already cents) |
| `stripe_*` | existing | payment-session / webhook (existing) | unchanged |

`internal_pricing_notes` is retained as internal-only (never client-visible),
distinct from `quote_notes_client`. (The legacy boolean `deposit_required` maps to
`payment_requirement = DEPOSIT`; see R4.)

### Proposed QuoteStatus enum
`NOT_REQUIRED` · `DRAFT` · `SENT` · `ACCEPTED` · `DECLINED` · `SUPERSEDED`
- `NOT_REQUIRED`: booking needs no priced quote (e.g., flat/standard service with no
  quote). Keeps the "quote_amount == 0 means no gate" behavior explicit.
- `DRAFT`: owner/admin is preparing a price (maps to existing request `QUOTE_NEEDED`).
- `SENT`: quote delivered to client (maps to existing request `QUOTE_SENT`/`QUOTED`).
- `ACCEPTED`: client (or admin on behalf) accepted.
- `DECLINED`: client (or admin) declined this quote.
- `SUPERSEDED`: **history-only.** This value appears ONLY on snapshot entries inside
  `quote_history`; the REQ's current `quote_status` is **never** `SUPERSEDED` (see
  refinement R3, revision rules). When a SENT/ACCEPTED quote is revised, the outgoing
  revision is snapshotted into `quote_history` with status `SUPERSEDED`, and the
  current `quote_status` becomes `DRAFT`/`SENT` for the new revision.

### Proposed PaymentStatus enum (normalized single vocabulary)
`NOT_REQUIRED` · `UNPAID` · `PAYMENT_LINK_SENT` · `PARTIALLY_PAID` · `PAID` ·
`REFUNDED`
- Replaces the dual PET/REQ vocabularies with one canonical set on REQ.
- Legacy mapping (read-compat): PET `Accepted`→(quote ACCEPTED, payment `UNPAID`);
  `Deposit Paid`→`PARTIALLY_PAID`; `Paid in Full`→`PAID`; `Not Quoted`→`NOT_REQUIRED`;
  REQ `unpaid`→`UNPAID`, `payment_link_sent`→`PAYMENT_LINK_SENT`, `paid`→`PAID`.

**Key separation:** quote acceptance is `quote_status == ACCEPTED`, NOT a
`payment_status` value. Payment progresses independently.

---

## 3. Client acceptance authority (Phase 4)

A client may, for **their own** booking only:
- **Read** their own client-safe quote projection (Phase 5).
- **Accept** the current `SENT` quote → `quote_status = ACCEPTED`, `quote_accepted_at` set.
- **Decline** the current `SENT` quote → `quote_status = DECLINED`, `quote_declined_at` set.
- **Request change** → records a client message/flag for owner/admin review (does
  NOT itself change price or status; see Phase 11). This reuses the "request more
  information" gap identified in OPS-2B and remains **NEEDS_DESIGN** for the exact
  message mechanism; it is NOT required for the OPS-3A.1/3A.2 MVP.

Mechanism decision: client acceptance calls a **dedicated quote endpoint**
(`POST /client/quotes/{requestId}/accept|decline`) that writes only the acceptance
fields and appends an immutable entry to `quote_history`. It must NOT reuse the pet
or generic request mutation path. Rationale: a dedicated, narrowly-scoped endpoint
with a hard allowlist is the only safe way to let a client write a single,
well-defined transition without exposing other fields.

The client must NOT be able to write: `quote_amount`, `currency`, `quote_notes_internal`,
`internal_pricing_notes`, `payment_status`, tenant approval status, staff assignment,
or any Visit/JOB state. Backend RBAC remains authoritative; the endpoint validates
`resolve_client_identity` ownership and `quote_status == SENT` precondition.

---

## 4. Client-safe quote projection (Phase 5)

Fields a client MAY receive:
`request_id`, `quote_amount`, `currency`, `quote_status`, `service_type` (label),
`selected_dates`/`start_date`/`end_date`, `pet_names`, `deposit_required`,
`deposit_amount` (if set), `quote_notes_client`, `quote_sent_at`,
`quote_accepted_at`, `payment_required` (derived boolean), `payment_status`
(normalized), and `quote_expires_at` **if** expiration is adopted (see note).

Explicitly EXCLUDED from the client projection: `quote_notes_internal`,
`internal_pricing_notes`, discount rationale, tenant margin, `audit_log`,
`quote_history`, staff-only notes, `stripe_*` identifiers / secrets, and any
tenant-internal metadata.

Delivery decision: a **dedicated** `GET /client/quotes/{requestId}` endpoint that
returns the projection above, rather than embedding in `GET /client/requests`.
Rationale: pricing is currently redacted from `GET /client/requests` by
`sanitize_booking_for_role`; a dedicated endpoint keeps the client booking list
unchanged, makes the pricing-exposure decision explicit and reviewable, and avoids
widening the general booking read. (A thin `has_quote`/`quote_status` summary MAY
later be added to the list for badges, but the authoritative projection is the
dedicated endpoint.)

Quote expiration is **optional / deferred**: not currently modeled. If adopted, add
`quote_expires_at` and treat an expired `SENT` quote as non-acceptable (client sees
"expired"; re-send creates a new revision). Not required for MVP.

---

## 5. Tenant approval vs client acceptance ordering (Phase 6)

Target commercial order:
`request → tenant review → (M&G if required) → tenant prepares quote → quote SENT →
client ACCEPTED → payment/deposit if required → tenant final approval / booking
confirmed → JOB creation → assignment → execution`.

Decisions, preferring deployed states:
- **Preserve existing `APPROVED` semantics.** `APPROVED` continues to mean tenant
  final approval and continues to trigger JOB creation. Do not change the JOB
  trigger.
- **Client acceptance occurs before tenant final approval.** The existing approval
  gate already blocks `APPROVED` when a quote exists and is not accepted; under the
  new model that precondition becomes `quote_status == ACCEPTED` (plus payment
  condition per Phase 9) instead of the overloaded PET `payment_status`.
- **No separate `BOOKING_CONFIRMED` status for MVP.** `APPROVED` already serves as
  "booking confirmed" and already fires `CUSTOMER_APPROVED`. Introducing a new state
  is not clearly justified and would add state-machine risk. Revisit only if product
  needs a confirmed-but-not-yet-approved stage.
- Mapping to existing request statuses: QuoteStatus `DRAFT↔QUOTE_NEEDED`,
  `SENT↔QUOTE_SENT`/`QUOTED`. Client ACCEPTED does **not** need a new request status;
  it is recorded in `quote_status` while the request remains `QUOTE_SENT` until the
  tenant moves it to `APPROVED`. This avoids introducing `QUOTE_ACCEPTED`.

---

## 6. Quote revision semantics (Phase 7)

- Editing an **already-SENT** quote (changing `quote_amount`) creates a **new
  revision**: increment `quote_revision`, snapshot the prior (amount, revision,
  status, timestamps) into `quote_history`, mark the prior as `SUPERSEDED`.
- A new revision **resets acceptance**: `quote_status` returns to `SENT` (or `DRAFT`
  until re-sent) and any prior `quote_accepted_at` is cleared on the active quote
  (retained in history). Client must accept the new amount.
- Historical values are **retained** in `quote_history` (append-only) and
  `audit_log`; never destructively overwritten.
- `quote_revision` (integer) is needed to disambiguate which revision a client
  accepted. Maps cleanly onto the existing `QUOTE_SENT → QUOTE_NEEDED → QUOTE_SENT`
  revision transition already in the status machine.

---

## 7. Multi-pet / multi-visit pricing (Phase 8)

**MVP: `quote_amount` represents the TOTAL for the entire booking/request** (single
total, single currency). This is the minimum viable contract and matches the current
single `quote_amount` semantics and the Request→many-JOB model.

Design the field so it can later support richer pricing without breaking the MVP:
- Reserve an **optional** `quote_line_items` array (future) — each item
  `{description, pet_id?, date?, amount, type: service|surcharge|discount|tax}` —
  whose sum equals `quote_amount`. MVP leaves it unset; `quote_amount` is
  authoritative.
- This supports future per-pet, per-visit, overnight surcharges, discounts, and
  taxes as additive line items without changing the top-level `quote_amount`
  contract. Do not build the line-item engine now (no accounting system).

---

## 8. Payment boundary (Phase 9)

- `QuoteAccepted` (quote lifecycle) is **independent** of `PaymentStatus` (settlement
  lifecycle). A quote may be accepted before any payment.
- Not every booking requires payment: `payment_status = NOT_REQUIRED` (and/or
  `deposit_required = false`, `quote_amount = 0`) means no payment gating.
- Booking-confirmation gate (what allows `APPROVED`): quote must be accepted when a
  quote exists, AND the payment precondition must be satisfied — where the payment
  precondition is:
  - no quote / `quote_amount == 0` / `payment_status == NOT_REQUIRED` → satisfied; else
  - if `deposit_required` → `payment_status ∈ {PARTIALLY_PAID, PAID}`; else
  - `payment_status ∈ {PAID}` OR tenant explicitly waives (owner/admin override).
- This replaces today's overloaded check (`pet.payment_status ∈ {Accepted, Deposit
  Paid, Paid in Full}`) with explicit `quote_status == ACCEPTED` + a payment
  condition. Deposit vs full-payment timing is captured by `PARTIALLY_PAID` vs `PAID`.
- No Stripe invocation in this design; payment execution remains the existing
  (sandbox) payment-session + webhook flow, unchanged, and is OPS-3B.

---

## 9. Migration / compatibility strategy (Phase 10) — no execution

- **Read-old / write-new with dual-read fallback.** New quote reads resolve from REQ
  canonical fields first; if absent (legacy booking), fall back to the pet
  `quote_amount`/`payment_status` (mapped via the Phase 2/legacy table). New writes
  always target REQ.
- **Legacy field preservation.** PET quote fields are not deleted; they remain for
  historical bookings and as the read fallback until a later, separately approved
  one-time backfill.
- **Approval-gate compatibility.** During transition the gate accepts EITHER the new
  `quote_status == ACCEPTED` (+ payment condition) OR the legacy PET
  `payment_status ∈ {Accepted, Deposit Paid, Paid in Full}`, so in-flight bookings
  are never blocked by the cutover.
- **No immediate production migration.** A one-time backfill (copy pet quote → REQ,
  normalize `payment_status`) is a later, separately approved step with its own
  review. This document does not execute or schedule it.

---

## 10. API contract proposal (Phase 11) — proposed only, not implemented

### Owner/Admin
- `PATCH /admin/requests/{requestId}/quote` — body `{quote_amount, currency?,
  deposit_required?, deposit_amount?, quote_notes_client?, quote_notes_internal?}`.
  RBAC owner/admin (staff excluded from pricing, matching current pet redaction).
  Precondition: request in a quotable state (`PENDING_REVIEW`/`MG_COMPLETED`/
  `QUOTE_NEEDED`/`QUOTE_SENT`/`QUOTED`/`READY_FOR_APPROVAL`). Sets `quote_status =
  DRAFT`. Errors: 403 (role), 404 (not found), 409 (invalid state), 400 (validation).
- `POST /admin/requests/{requestId}/quote/send` — transitions `quote_status → SENT`,
  sets `quote_sent_at`, request status → `QUOTE_SENT`. Re-send after SENT increments
  `quote_revision`, snapshots history, resets acceptance. Owner/admin.
- (Revision is `PATCH quote` on a `SENT` quote followed by `send` — no separate
  endpoint needed.)

### Client (dedicated, narrow)
- `GET /client/quotes/{requestId}` — returns the Phase 5 client-safe projection for
  the caller's own booking. RBAC client (own records via `resolve_client_identity`).
  Errors: 401 (unauthenticated), 403 (not owner), 404 (no quote).
- `POST /client/quotes/{requestId}/accept` — precondition `quote_status == SENT` and
  caller owns the booking; sets `ACCEPTED` + `quote_accepted_at`; appends history.
  Writes nothing else. Errors: 401/403/404, 409 (not in SENT).
- `POST /client/quotes/{requestId}/decline` — precondition `quote_status == SENT`;
  sets `DECLINED` + `quote_declined_at`; appends history.
- `POST /client/quotes/{requestId}/request-change` — records a client-facing message
  for owner/admin; NEEDS_DESIGN (shared with OPS-2B request-more-info); not in the
  first slice.

All client endpoints: hard field allowlist, owner-scoped, no pricing writes, no
status/assignment/JOB writes.

---

## 11. Notification contract (Phase 12) — intended, separate from implementation

| Event | Recipient | Trigger | MVP? | Current status |
|---|---|---|---|---|
| `QUOTE_READY` (a.k.a. QUOTE_SENT) | client | quote → SENT | MVP | **not implemented** (no template today) |
| `QUOTE_REVISED` | client | re-send after revision | later | not implemented |
| `QUOTE_ACCEPTED` | owner/admin | client accepts | MVP | not implemented |
| `QUOTE_DECLINED` | owner/admin | client declines | MVP | not implemented |
| `BOOKING_CONFIRMED` | client | request → APPROVED | exists-ish | `CUSTOMER_APPROVED` already sends on APPROVED |
| `PAYMENT_REQUIRED` | client | payment link generated | later (OPS-3B) | `PAYMENT_LINK_EMAIL` exists (Stripe sandbox) |

Preserve the OPS-2 finding that **UI copy can overstate actual backend
notifications**: today there is no QUOTE_READY/REVISED/ACCEPTED/DECLINED send. These
must be built as real sends if adopted; do not assume UI labels imply delivery. No
notification code is written in this task.

---

## 12. Proposed OPS-3A implementation slices (Phase 13)

Split chosen from source evidence (quote state must move to REQ, and no client write
path exists today, so backend precedes UI):

- **OPS-3A.1 — Backend quote contract + client-safe read.** Add canonical quote
  fields to the REQ record and the quote write/send admin endpoints; add
  `GET /client/quotes/{requestId}` with the client-safe projection; dual-read
  fallback to legacy PET fields; normalize `payment_status`. Approval gate updated to
  accept new OR legacy acceptance. No Stripe, no live payment, no production
  migration, no Visit/JOB change. (Backend work — a separate reviewed RC with its own
  tests and separately approved deployment.)
- **OPS-3A.2 — Client accept/decline.** `POST /client/quotes/{id}/accept|decline`
  (narrow, owner-scoped, mandatory `expected_revision`, 409 on stale) +
  `QUOTE_ACCEPTED`/`QUOTE_DECLINED` notifications.
- **OPS-3A.3 — Web/mobile client UI parity.** Display the quote projection and the
  accept/decline action on web client portal and mobile.
- **OPS-3B — Payment / Stripe.** Deposit/payment setup, payment-link generation,
  payment status sync, client payment UI. Stripe (sandbox→live separately approved).

The **first** implementation slice (OPS-3A.1) must NOT require Stripe calls, live
payment, production mutation, new tenant work, or Visit/JOB redesign — satisfied by
the scope above.

### Recommended next action (contract approved 2026-10-03)

**OPS-3A.1 — Backend quote contract + client-safe read**, as a bounded, audit-first,
backend-only slice: add the canonical quote fields to the REQUEST record, the
owner/admin quote write/send endpoints, and the client-safe `GET
/client/quotes/{requestId}` projection, with dual-read fallback to legacy PET fields
and the normalized `payment_status`/`payment_requirement` gate. It must reuse
existing contracts where possible, introduce no new RequestStatus, keep quote/payment
state off Visit/JOB, invoke no Stripe, and perform no production migration — delivered
as its own reviewed RC with tests and a separately approved deployment. OPS-3A.2 and
OPS-3A.3 follow; OPS-3B (payment/Stripe) remains separately gated.

---

## 13. Product decisions — APPROVED BY MATTHEW ON 2026-10-03

The following commercial-contract decisions are **APPROVED BY MATTHEW ON 2026-10-03**.
They are no longer recommendations or pending decisions — they are the ratified
contract for OPS-3A. (Historical note: in the final-review turn these were documented
as recommended defaults pending approval; Matthew has now explicitly approved them.)

Primary decisions:
1. **Quote expiration** — **APPROVED: NOT in MVP.** No `quote_expires_at` field in
   the MVP contract.
2. **Pricing model** — **APPROVED: one total booking price in MVP**
   (`quote_amount_cents`); line-item pricing is deferred (future `quote_line_items`).
3. **Booking confirmation** — **APPROVED: reuse the existing `APPROVED` status; do
   NOT add a `BOOKING_CONFIRMED` status.**
4. **Client acceptance** — **APPROVED: authenticated client self-service
   accept/decline through dedicated narrow quote endpoints.**

Ratified contract specifics (approved by Matthew on 2026-10-03):
5. **Canonical quote ownership** — the REQUEST / BOOKING record (PET quote fields
   become legacy compatibility/read-fallback).
6. **Money representation** — integer minor units (cents) + `currency`
   (`quote_amount_cents`, `deposit_amount_cents`, `payment_amount_cents`).
7. **Authoritative quote lifecycle** — `quote_status` is authoritative for the
   commercial quote lifecycle.
8. **RequestStatus quote values** (`QUOTE_NEEDED`/`QUOTE_SENT`/`QUOTED`) remain
   compatibility/workflow-summary states derived from `quote_status`, NOT a second
   authoritative commercial state machine; deployed statuses are not removed.
9. **`SUPERSEDED` is history-only** and must never be the current `quote_status`.
10. **Client Accept/Decline requires `expected_revision`**; stale status/revision
    attempts return **HTTP 409**.
11. **`payment_requirement = NONE | DEPOSIT | FULL`** is the explicit settlement
    gate input.
12. **Commercial-vs-internal revision rule** — client-visible commercial changes
    create a new quote revision and invalidate prior acceptance; internal-only notes
    do not.
13. **Acceptance does not auto-approve** — quote acceptance does NOT automatically
    approve the booking; `APPROVED` remains an explicit tenant/business workflow
    action taken after the quote and payment predicates are satisfied.
14. **Booking-approval predicate** preserves the approved R4 behavior: no quote /
    `NOT_REQUIRED` → quote condition satisfied; accepted quote + `NONE` → payment
    condition satisfied; accepted quote + `DEPOSIT` → `PARTIALLY_PAID` or `PAID`;
    accepted quote + `FULL` → `PAID`; an authorized owner/admin payment waiver may
    satisfy the payment condition; `PARTIALLY_PAID` must never satisfy `FULL`.

---

## Implementation gate — CONTRACT APPROVED; implementation may be planned/executed under normal gates

The product-contract approval gate is **CLEARED** (Matthew approved the decisions
above on 2026-10-03). OPS-3A implementation is therefore **no longer blocked by
product-contract approval** and may proceed to bounded implementation planning and
execution under the project's normal release discipline (reviewed RC, tests,
plan/apply separation, and Matthew's standard per-deployment approval).

Normal release boundaries still apply (unchanged by this approval):
- Each implementation slice is a separate reviewed change with its own tests and,
  for backend, a separately approved deployment. No production deployment without
  Matthew's explicit per-release approval.
- OPS-3B (payment/Stripe) remains separate and Stripe-gated (sandbox-only; live
  blocked on EIN).
- This documentation turn performs **no** runtime implementation.

---

# Final-QA refinements

These sections tighten specific contract details. Every product choice they imply is
now listed under "Product decisions — APPROVED BY MATTHEW ON 2026-10-03" above and is
**approved**, not a pending recommendation.

## R1 — RequestStatus vs quote_status: source of truth

1. **Authoritative quote lifecycle:** `quote_status` is the single authoritative
   representation of the commercial quote lifecycle (NOT_REQUIRED/DRAFT/SENT/
   ACCEPTED/DECLINED, with SUPERSEDED history-only).
2. **Purpose of the deployed RequestStatus quote values** (`QUOTE_NEEDED`,
   `QUOTE_SENT`, `QUOTED`): they remain the broader **booking/workflow** state and
   act as **workflow-summary / compatibility** states derived from `quote_status` —
   not an independent commercial state machine.
3. They are therefore **workflow-summary states derived from `quote_status`** (and,
   during migration, compatibility states), NOT independently authoritative for the
   commercial lifecycle.
4. **Writers:** `quote_status` is written by the quote endpoints (admin quote
   write/send; client accept/decline). The RequestStatus value is written by the
   same quote operations as a **derived** side effect (e.g. send sets
   `quote_status=SENT` and request `status=QUOTE_SENT`). No other layer writes
   `quote_status`.
5. **If they disagree:** `quote_status` wins for all commercial decisions (gating,
   client display, acceptance). A mismatch is treated as a derived-state drift to be
   reconciled toward `quote_status`; it never changes commercial behavior.
6. **During migration:** for legacy records with no `quote_status`, the RequestStatus
   quote value (plus legacy PET fields) is the fallback source; for records that have
   `quote_status`, `quote_status` wins. (Dual-read; see Phase 10.)
7. **Can a request be APPROVED while `quote_status != ACCEPTED`?** Only when no quote
   is required (`quote_status == NOT_REQUIRED`, i.e. `quote_amount_cents == 0` / no
   quote) or via an explicit authorized owner/admin waive (R4). When a quote exists
   and is required, `APPROVED` requires `quote_status == ACCEPTED`. This replaces the
   legacy overloaded PET `payment_status` precondition.
8. **Should `QUOTED` remain a valid RequestStatus?** Yes — it is **not removed** this
   task (OPS-0: do not remove deployed statuses). It persists as a workflow-summary
   synonym alongside `QUOTE_SENT`. New code treats `QUOTE_SENT`/`QUOTED` as "quote
   sent" summary states and relies on `quote_status` for the authoritative lifecycle.

Deterministic synchronization (not two independent machines):
`quote_status DRAFT → request QUOTE_NEEDED`; `SENT → QUOTE_SENT`;
`ACCEPTED → request stays QUOTE_SENT` (acceptance recorded only in `quote_status`
until the tenant moves the request to `APPROVED`); `DECLINED → request DECLINED`
only when the tenant chooses to decline the booking (client decline sets
`quote_status=DECLINED` but does not itself force the request to `DECLINED`).

## R2 — Money representation

**Recommendation: Option B — integer minor units (cents) + `currency`.** Canonical
fields: `quote_amount_cents`, `deposit_amount_cents`, `payment_amount_cents` (already
cents today), plus `currency` (default `"USD"`).

Rationale:
- **Arithmetic safety:** integer cents avoid floating-point/`Decimal` rounding drift
  across sums (taxes/surcharges later).
- **Stripe interoperability:** Stripe's `unit_amount` is already integer cents; no
  conversion at the payment boundary (the existing `payment_amount_cents` is already
  cents).
- **JSON / DynamoDB:** integers serialize cleanly in JSON and store natively in
  DynamoDB (no `Decimal`-string round-tripping ambiguity).
- **API ergonomics:** clients/UI format `cents/100` with the currency; one obvious
  representation.
- **Legacy conversion/fallback:** existing PET `quote_amount` is a `Decimal` in major
  units. The dual-read fallback (Phase 10) converts legacy → `round(Decimal(value) *
  100)` as integer cents at read time; new writes always store `*_cents`. No
  destructive conversion of legacy records (read-time only) until a separately
  approved backfill. (No conversion code is written in this task.)

## R3 — Quote revision semantics

- **Commercial change → new revision.** A change to any client-visible commercial
  field — `quote_amount_cents`, `currency`, `deposit_amount_cents`,
  `payment_requirement`, or `quote_notes_client` — on a quote that is already `SENT`
  or `ACCEPTED`:
  - snapshots the prior revision into `quote_history` (status `SUPERSEDED`, with its
    amount/revision/notes_client/timestamps),
  - increments `quote_revision`,
  - sets current `quote_status` to `DRAFT` (until re-sent) then `SENT` on send,
  - **clears `quote_accepted_at` and `quote_accepted_revision`** on the current quote
    (acceptance becomes invalid), while the prior acceptance remains preserved in
    `quote_history`.
- **Internal-only change → NOT a revision.** Editing `quote_notes_internal` or
  `internal_pricing_notes` does **not** increment `quote_revision`, does **not**
  change `quote_status`, and does **not** invalidate client acceptance. These are not
  commercial, not client-visible, and never surfaced to the client.
- **Price-only vs note-only:** a `quote_amount_cents` change is commercial (revision);
  a `quote_notes_client` change is also commercial/client-visible (revision), because
  the client sees it and acceptance was against that presented offer. An internal note
  change is neither.
- Historical values are retained append-only; never destructively overwritten.

## R4 — Booking-confirmation gate (exact predicate)

Introduce `payment_requirement` (enum, owner/admin-set) to express the settlement
requirement explicitly rather than inferring it from an ambiguous `payment_status`:
`NONE · DEPOSIT · FULL`.

`APPROVED` (tenant final approval → JOB creation) is permitted iff
**quote condition AND payment condition** both hold:

- **Quote condition:**
  `quote_status == NOT_REQUIRED` (no priced quote) **OR** `quote_status == ACCEPTED`.
- **Payment condition**, by case:
  - A. **No quote required** (`quote_status == NOT_REQUIRED`): satisfied.
  - B. **Quote required, no payment** (`payment_requirement == NONE`): satisfied once
    the quote condition holds.
  - C. **Quote required, deposit required** (`payment_requirement == DEPOSIT`):
    `payment_status ∈ {PARTIALLY_PAID, PAID}`.
  - D. **Quote required, full prepayment** (`payment_requirement == FULL`):
    `payment_status == PAID`.
  - E. **Payment waived** by an authorized owner/admin: an explicit
    `payment_waived_by` + `payment_waived_at` override satisfies the payment condition
    regardless of `payment_status` (owner/admin only, audited). Never settable by
    staff or client.

This avoids relying on `PARTIALLY_PAID` alone: `PARTIALLY_PAID` satisfies only the
DEPOSIT case, never the FULL case. `payment_requirement` is the authoritative gate
input; `deposit_amount_cents` is informational for the DEPOSIT case.

## R5 — Client accept/decline concurrency (stale-revision safety)

`POST /client/quotes/{requestId}/accept` and `/decline` **must** include the client's
expected `quote_revision` in the request body (`{ "expected_revision": <int> }`).

- **Optimistic concurrency:** the server accepts the action only if
  `expected_revision == current quote_revision` AND `quote_status == SENT`.
- **Stale revision:** if the tenant revised the quote after the client loaded it
  (`expected_revision < current quote_revision`, or `quote_status != SENT`), the
  server returns **409 Conflict** with the current `quote_status`/`quote_revision` so
  the client UI can reload and re-present the new offer. An old quote can never be
  accepted after revision.
- **Ownership checks (both required):** tenant/company ownership
  (`validate_tenant_ownership`) AND client/request ownership
  (`resolve_client_identity` matches the booking's client). Failure → 403.
- On success: set `quote_status = ACCEPTED|DECLINED`, `quote_accepted_at`/
  `quote_declined_at`, `quote_accepted_revision = expected_revision`, append history.
  Writes nothing else (hard allowlist).

## R6 — Summary of refinement-driven field additions

Relative to the first draft, the contract adds/renames: `quote_amount_cents` and
`deposit_amount_cents` (integer cents, replacing Decimal `quote_amount`/
`deposit_amount`); `quote_accepted_revision`; `payment_requirement` (NONE/DEPOSIT/
FULL, replacing the implicit `deposit_required` boolean); and `payment_waived_by`/
`payment_waived_at` (owner/admin override for the gate). All remain **proposed** and
gated behind product-contract approval.

---

# OPS-3A.2 — Client Accept / Decline — APPROVED BY MATTHEW (2026-10-05)

Status: **CONTRACT FINALIZED / APPROVED — documentation only; runtime not yet
implemented.** These decisions are authoritative and remove OPS-3A.2 from "open"
status. They supersede any softer or exploratory wording in sections 3, 10, 12, and
R5 above where there is a conflict (e.g. ownership-failure disposition and
notification scope). Implementation proceeds under normal release discipline
(reviewed RC, tests, plan/apply separation, per-release Matthew approval); no code,
Terraform, AWS, or deployment change accompanies this approval.

Checkpoint at approval: `main == origin/main == d591d60f8cdf51631f66d2e6624db8145eacedef`.

## A2-1. Quote revision semantics (NO ambiguity)

Accept and Decline are **lifecycle decisions about the current quote revision**;
they are **not** a new commercial offer and therefore **do NOT create a new quote
revision**:

- **Accept does NOT increment `quote_revision`.**
- **Decline does NOT increment `quote_revision`.**
- The accept/decline action is **bound to the current authoritative revision**.
- Accept records `quote_accepted_revision = current quote_revision`.
- Decline records equivalent revision-binding metadata (`quote_declined_revision =
  current quote_revision`) plus `quote_declined_at`.
- The client action is recorded in `quote_history`/`audit_log` as a lifecycle event
  (not a SUPERSEDED revision snapshot).
- A **later staff change to client-visible commercial terms** (amount, currency,
  `payment_requirement`, `deposit_amount_cents`, `quote_notes_client`) **does** create
  a NEW quote revision — that is what "commercial client-visible changes create
  revisions" means: a change to the OFFER itself.

Clarification of the pre-existing rule: "commercial client-visible changes create
revisions" refers to changes to the OFFER (amount / currency / payment requirement /
other client-visible commercial terms). A client's Accept/Decline **response** is not
a new offer and therefore does not create a revision. `SUPERSEDED` remains
**history-only** and is never the current `quote_status`.

## A2-2. Accept endpoint

- Route: `POST /client/quotes/{requestId}/accept`.
- Required body: `expected_revision` (integer). **No caller-supplied `client_id`.**
- Client identity/ownership resolved **server-side** from the authenticated Cognito
  identity (`resolve_client_identity`); tenant authority server-side
  (`validate_tenant_ownership`).
- Eligible current status: **`SENT`**. Successful transition: **`SENT → ACCEPTED`**.
- Accept MUST NOT: set the booking/request to `APPROVED`; modify `payment_status`;
  create payment; or alter `payment_requirement`.
- Lifecycle metadata set: `quote_accepted_at`, an accepted-by identity reference
  appropriate to the existing model (client email/sub actor in audit), and
  `quote_accepted_revision = current quote_revision`.
- RequestStatus compatibility/workflow fields are updated only if the already-approved
  contract explicitly requires a derived mirror; `quote_status` remains authoritative.
  Per R1, client acceptance does not change the request's workflow status (the request
  remains `QUOTE_SENT` until the tenant moves it to `APPROVED`).

## A2-3. Decline endpoint

- Route: `POST /client/quotes/{requestId}/decline`.
- Required body: `expected_revision` (integer). Optional body: `decline_reason`.
- `decline_reason` MVP behavior: optional; leading/trailing whitespace trimmed;
  whitespace-only treated as absent; **maximum 500 characters** (over-length →
  validation error); stored as **client-visible / client-originated** audit metadata
  (`quote_declined_reason_client`); **no separate internal-only semantics**.
- Eligible current status: **`SENT`**. Successful transition: **`SENT → DECLINED`**.
- Declining a quote MUST NOT automatically set the overall request/booking lifecycle
  to `DECLINED`. A later staff commercial revision may supersede the declined quote
  and be sent as a new revision.

## A2-4. Concurrency (atomic optimistic lock)

- Both mutations require integer `expected_revision`. Missing/invalid → validation
  error (HTTP 400) using existing API conventions (not 409).
- The mutation MUST be atomic (single conditional `update_item`); no read-then-write
  race is permitted.
- The condition MUST protect BOTH `quote_revision == expected_revision` AND
  `quote_status == SENT`, using the established DynamoDB conditional-update pattern
  already used by `POST /admin/requests/{id}/quote/send`
  (`ConditionExpression Attr('quote_revision').eq(expected_revision) &
  Attr('quote_status').eq('SENT')`).
- Conditional failure (stale revision or changed lifecycle state) maps to **HTTP 409**
  with safe authoritative current-state metadata (`quote_status`, `quote_revision`)
  per existing response conventions.
- Ownership/tenant mismatch is **non-disclosing** (returns 404, matching the deployed
  `GET /client/quotes/{requestId}` handler) rather than 403; this supersedes the R5
  "→ 403" wording.

## A2-5. Retry / idempotency (STRICT, MVP)

Strict deterministic conflict semantics; **first valid action wins**:

- first Accept succeeds; repeated Accept at same `expected_revision` → **409**;
- first Decline succeeds; repeated Decline → **409**;
- Accept after Decline → **409**; Decline after Accept → **409**;
- competing simultaneous Accept/Decline → one succeeds, the loser → **409**.

Do NOT introduce softened 200 retry behavior in MVP. Do NOT introduce a separate
idempotency-key system in OPS-3A.2 unless later approved.

## A2-6. Booking readiness

- Accepting a quote does NOT imply booking approval.
- Preserve the existing predicate (`evaluate_booking_approval_predicate`):
  `NOT_REQUIRED` satisfies the quote condition; accepted + `NONE` → payment satisfied;
  accepted + `DEPOSIT` → `PARTIALLY_PAID` or `PAID`; accepted + `FULL` → `PAID`; an
  authorized waiver satisfies payment; `PARTIALLY_PAID` never satisfies `FULL`.
- The Accept success response SHOULD include a **read-only computed `booking_ready`**
  derived from that predicate, and MAY expose the safe client-facing fields needed to
  explain readiness (e.g. `payment_requirement`, `payment_status`) if already permitted
  by the quote/client projection.
- `booking_ready` is computed information only. Do NOT persist `APPROVED` merely
  because `booking_ready` is true; the booking transition remains a separately
  authorized workflow action.

## A2-7. Payment interaction

Accept/Decline do not create payment, do not change `payment_status`, do not change
`payment_requirement`, do not invoke Stripe, and require no Stripe configuration
change. OPS-3B remains the payment-collection workstream; Stripe remains sandbox-only.

## A2-8. Notifications

Notifications (`QUOTE_ACCEPTED` / `QUOTE_DECLINED`) are **DEFERRED** from the core
Accept/Decline implementation. Core backend correctness must not be blocked on
Postmark template creation. Notifications become a later, independently reviewed slice
after the core mutation/API behavior is complete. (This supersedes the section-12
listing that bundled notifications into OPS-3A.2.)

## A2-9. Client UI direction

Future client UI consumption is **MOBILE-FIRST** (no UI this turn). The future mobile
client should support: quote details, quote revision, payment requirement, Accept,
Decline, optional decline reason, 409 stale-state refresh/reconciliation, and
read-only booking-readiness / next-step messaging. Web may consume the same APIs later.
UI is OPS-3A.3.

## A2-10. API Gateway direction

Reuse the existing `/client/quotes/{requestId}` resource (`client_quote_id`) as the
**parent**; add child resources `/client/quotes/{requestId}/accept` and
`/client/quotes/{requestId}/decline`. Both: `POST`, Cognito-authorized, `AWS_PROXY` to
the existing admin Lambda (unless an implementation audit proves a material reason
otherwise), OPTIONS/CORS via the established `cors_resources` `for_each` module
pattern. No new Lambda required. No Terraform implementation this turn.

## OPS-3A.2 implementation gate

The OPS-3A.2 product-contract decisions above are **APPROVED (2026-10-05)**.
Implementation may proceed under normal gates in the recommended slice order:
**OPS-3A.2A** (backend contract `apply_quote_accept`/`apply_quote_decline` + client
handlers + tests, no deploy) → **OPS-3A.2B** (API Gateway routes; Gate-A plan then
gated apply) → **OPS-3A.2C** (mobile-first client UI, then web) → **OPS-3A.2D**
(deferred `QUOTE_ACCEPTED`/`QUOTE_DECLINED` notifications). No implementation,
Terraform, AWS, or deployment occurs under this approval; each slice is a separate
reviewed change with its own tests and (for backend/infra) a separately approved
deployment. OPS-3B (payment/Stripe) remains separate and Stripe-gated.
