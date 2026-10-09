# PetCare Hero — Workflow & Payment Architecture Audit + Workstreams

Status: **DISCOVERY + PLANNING ONLY (documentation).** No runtime, backend, mobile,
web, Stripe, Terraform, or production change accompanies this document. It records a
source-cited audit of product/workflow gaps found during live production-backed M3
testing and defines four tracked workstreams plus the platform-billing-vs-tenant-
payment architecture decision. Implementation of any workstream is separately gated
under the project's normal release discipline.

Authoring checkpoint: branch `main`, HEAD == `origin/main` ==
`5680452a90fce114cbf21678c02d0cd1ca152198`.

Companion docs (authoritative, not duplicated here):
- `docs/planning/petcare-hero-quote-contract.md` — the approved OPS-3A quote contract.
- `docs/planning/petcare-hero-operational-workflow-mobile-first.md` — PCH-OPS program.
- `docs/backlog/saas-maturity-and-multi-business-owner-readiness.md` — backlog index.

M4 note: the Matthew-only production Decline mutation test is
`M4_PRODUCTION_MUTATION_TEST_AUTHORIZED=PAUSED_FOR_WORKFLOW_RECONCILIATION` — approval
is not revoked, but execution is paused because no safe canonical `SENT` quote can be
produced today (see Workstream 2). M4 may resume under a new explicit execution prompt
once the owner/admin quote-send bridge exists.

---

## A. Source-cited audit findings

### A1. Existing-pet selection (Workstream 1)
- **Mobile (`mobile/src/screens/IntakeScreen.tsx`)** already fetches existing pets
  (`getClientPets()`), renders a multi-select chip list (`availablePets.map`,
  `togglePetSelection`, `selectedPetNames`), pre-selects the first pet, and supports a
  free-text "add new pet" fallback (`fallbackPetName`). So a *selection UI exists* on
  mobile. **Gap:** selection and the submit payload are keyed by **pet NAME**, not
  pet **ID** — `petsPayload` is built by matching `availablePets.find(p => p.name ===
  name)`, and the request sends `pet_names` as a **comma-joined string**
  (`petsPayload.map(p => p.name).join(', ')`). There is no canonical `pet_ids` on the
  client intake payload.
- **Web (`web/src/components/AdminDashboard.jsx`)** new-visit form models pets with
  BOTH `pet_names: ''` and `pet_ids: []`; `handleSelectPet` prefers `item.pet_ids`,
  falling back to single `pet_id`, then a request `pets` array, then a legacy
  comma-separated `pet_names` string that `CareCard.jsx` splits for display. The web
  **client** new-request flow is not a first-class existing-pet picker comparable to
  the mobile chip UI.
- **Consequence:** pet association is carried in three overlapping shapes across the
  stack — canonical `pet_ids` (array), a request `pets` array, and legacy `pet_names`
  (string). The same legacy `pet_names`-as-string shape is what crashed the mobile
  client detail screen in M3 (fixed defensively at `5680452` via `toStringArray`).
- **Desired canonical behavior:** `Book Care → select existing pet(s) by pet_id →
  add new pet only if needed → choose service/dates → submit`, supporting: one
  existing pet; multiple existing pets; add-new-pet; existing + newly-added in one
  request; and removal/reselection before submit. The canonical association is a
  `pet_ids` array on the REQUEST; `pet_names` should be a *derived display* value, not
  the authority.

### A2. Quote / pricing duplication (Workstream 2)
`web/src/components/CareCard.jsx` renders TWO pricing sections, both operating on the
**legacy PET record** (`pet._originItem`), not the canonical REQUEST quote:
- **`Pricing & Quote`** — legacy PET quote fields (`quote_amount` on PET).
- **`Pricing & Payment (Stripe Sandbox)`** ("Release 12R") — legacy Stripe
  payment-link generation (`handleGeneratePaymentLink`, `sendPaymentEmail`,
  `payment_link_sent`).

Classification: both are **(B) the older PET-based pricing + payment-link workflow**,
NOT **(A) the canonical OPS-3A REQUEST quote contract**. They overlap/duplicate
pricing against the legacy PET placement that the approved quote contract explicitly
deprecates to "legacy compatibility/read-fallback." Direct Stripe payment-link
generation is **legacy** relative to the canonical quote/payment separation.
**No removal in this turn** — only classification. Recommended eventual direction:
the canonical owner/admin quote workflow (create/edit/send) replaces "Pricing &
Quote"; payment collection (OPS-3B) is a *separate, later* settlement step, not a
PET-level sandbox link.

### A3. Owner/admin quote-send UX — the missing bridge (Workstream 2)
- Backend canonical quote endpoints are deployed (OPS-3A.1D/3A.2):
  `PATCH /admin/requests/{requestId}/quote`, `POST .../quote/send`,
  `GET /client/quotes/{requestId}`, `POST /client/quotes/{id}/accept|decline`.
- **`web/src/api/client.js` has NO canonical quote calls** — grep for
  `quote`/`quote/send`/`quote_status` returns no admin quote endpoint usage. The web
  admin app therefore **cannot create or SEND a canonical quote**; it only drives the
  legacy PET pricing + Stripe sandbox link.
- Mobile is a client/owner surface; its client side has `getClientQuote` /
  `accept` / `decline` but there is **no owner/admin quote-send UX** on mobile either.
- **This is why Matthew cannot find a `SENT` quote to test M4.** The mobile client
  correctly shows Accept/Decline only for canonical `quote_status == SENT`
  (OPS-3A.3A), but **nothing in the deployed UI calls `POST .../quote/send`**, so no
  canonical `SENT` quote can be produced through the product. The missing bridge is
  owner/admin quote create+send UX wired to the deployed endpoints.

### A4. Status vocabulary mismatch — `STATUS_VOCABULARY_MISMATCH_FOUND=YES`
- Observed: a request card showed **`QUOTE_NEEDED`** while the client detail screen
  showed **"No quote action is required for this booking."**
- Source/derivation:
  - The **card** label derives from the legacy **RequestStatus** (`QUOTE_NEEDED`,
    from `src/backend/common/status.py` / request `status`). Mobile `BookingsScreen`
    maps request `status` to display labels.
  - The **detail** copy derives from the canonical **`quote_status`** path in
    `ClientRequestDetailScreen.renderQuoteSection()` — its `default` branch (which
    covers `DRAFT` and any unknown/absent status) and the `NOT_REQUIRED` branch BOTH
    render "No quote action is required for this booking." So an effective-DRAFT or
    no-canonical-status quote shows the NOT_REQUIRED copy on the detail screen while
    the card still shows the legacy `QUOTE_NEEDED` summary.
- Per the approved contract (quote-contract R1): **`quote_status` is authoritative**;
  `QUOTE_NEEDED`/`QUOTE_SENT`/`QUOTED` are **derived workflow-summary/compatibility**
  states, not a second authoritative machine. The mismatch is a *display* drift, not
  a commercial-logic defect.
- **Recommended canonical display rule:** both card and detail must derive their
  user-facing quote label from the effective resolved `quote_status` (DRAFT→"Quote in
  preparation"/no client action; SENT→"Quote ready for review"; ACCEPTED→"Quote
  accepted"; DECLINED→"Quote declined"; NOT_REQUIRED→"No quote required"). The legacy
  RequestStatus may remain an internal/admin workflow summary but must not drive the
  client-facing quote label. The detail screen's `default` branch should distinguish
  DRAFT ("quote in preparation") from NOT_REQUIRED rather than collapsing both to
  "no quote action is required."

### A5. Platform billing vs tenant customer payments (Workstream 3)
Two distinct money planes must not be conflated:
- **Plane A — PetCare Hero SaaS billing:** USMISSIONHERO LLC → charges tenant
  businesses (e.g., Togs & Dogs subscription/plan/add-ons). USMISSIONHERO's Stripe
  account belongs **here**. (Backlog item 2: Stripe subscription Checkout, blocked on
  EIN.)
- **Plane B — Tenant customer payments:** pet owner → the tenant business (Togs &
  Dogs today; future tenants later). The **tenant** owns this customer-payment
  relationship.
- **Current implementation conflation risk:** the deployed/legacy sandbox payment
  link (`CareCard` "Pricing & Payment (Stripe Sandbox)", `handleGeneratePaymentLink`,
  REQ `stripe_*` fields) is a **Plane B** customer payment, but it is wired to the
  single platform Stripe (sandbox) configuration. There is no provider abstraction
  that separates "who gets paid." Collecting a tenant's customer payments through
  USMISSIONHERO's own Stripe account would commingle Plane A and Plane B and is a
  product/compliance decision, **not** an implementation default.
- **Decision criteria to resolve later (NOT chosen now):** tenant-owned external/
  off-platform payment; per-tenant Stripe account; Stripe Connect (platform-of-record
  with connected accounts); or a configurable payment-provider abstraction. **Do NOT
  default to Stripe Connect.** Stripe remains **sandbox-only** until Matthew
  explicitly approves live work (EIN-blocked per guardrails).
- **Pending Matthew product decision:** which Plane-B model Togs & Dogs (and future
  tenants) will use, and whether PetCare Hero provides only workflow/UI vs also acting
  as payment processor/platform-of-record.

### A6. Web vs mobile shared-state architecture (Workstream cross-cut)
Web and mobile must NOT be separate business systems. They already share the same
backend REST API (`a022yxuiue`), the same request/quote records, and
`shared/constants/` service definitions (per guardrails). The canonical pipeline —
`Request → Quote → Client decision → Payment requirement → Booking readiness →
Service execution` — and its rules (`quote_status` authority, `payment_requirement`
semantics, booking-approval predicate, client ownership/auth, request/booking data)
must remain single-sourced in the backend contract. UX/responsibility may differ by
surface, but **no business logic may be duplicated per platform.**

Recommended capability placement:
- **Owner/admin WEB:** primary quote create/edit/**send**, pricing, payment-requirement
  setting, approvals, roster/scheduling. (This is where the A3 bridge should land
  first — richest admin surface.)
- **Owner/admin MOBILE:** field operations (assignment, start/complete), and
  — later — a mobile quote-send parity surface reusing the same endpoints.
- **Client MOBILE:** view quote, Accept/Decline (already built), Book Care (existing-
  pet selection — Workstream 1), My Pets read/edit.
- **Client WEB:** parity for the same client capabilities (web forgot-password gap is
  separately documented).

---

## B. Tracked workstreams

### Workstream 1 — Existing Pet Selection (canonical pet association)
Requirements:
- Select existing profile pet(s) **by `pet_id`**; multi-pet supported.
- Add-new-pet only when needed; existing + newly-added in one request.
- Removal/reselection before submit.
- Canonical REQUEST↔pet association is a `pet_ids` array; `pet_names` becomes a
  derived display string, never the authority.
- Mobile + web parity **at the backend contract level** (same payload shape).
- Eliminates the legacy comma-joined `pet_names`-as-string producer that caused the
  M3 client-detail crash.

### Workstream 2 — Unified Quote Workflow (owner/admin send bridge)
Requirements:
- One canonical quote source of truth (the REQUEST `quote_status`, per the approved
  contract) — PET-based pricing becomes read-fallback only.
- Owner/admin **create/edit/SEND** quote UI wired to the deployed
  `PATCH /admin/requests/{id}/quote` + `POST .../quote/send` (the A3 missing bridge).
- Client Accept/Decline only when `SENT` (already built); revision-safe
  (`expected_revision`, 409 on stale).
- Deprecate or clearly isolate the legacy "Pricing & Quote" + "Pricing & Payment
  (Stripe Sandbox)" PET workflow (no removal without a separate approved change).
- Admin/mobile/web consistency on canonical quote state.
- **Unblocks M4** (produces a safe canonical `SENT` quote to Decline-test).

#### Known backend-contract limitations (discovered during W2B source audit)

These are **contract limitations found through source audit** of the deployed
`PATCH /admin/requests/{requestId}/quote` handler and `apply_quote_update` (OPS-3A.1B),
not production incidents. They bound the W2B supported-state editor and are tracked for
later, separately approved backend work. They do **not** change the approved quote
contract: canonical `quote_status` remains authoritative; `SUPERSEDED` remains
history-only; a commercial edit of a `SENT`/`ACCEPTED` quote already creates a new
revision and returns the quote to `DRAFT` (clearing acceptance for `ACCEPTED`). W2B
makes **no** backend change, and W2C (Send Quote / `DRAFT → SENT`) does not address
these gaps either; GAP-1/GAP-2 remediation is out of scope for W2B/W2C unless
separately approved.

**GAP-1 — DECLINED cannot be revived to DRAFT.** The deployed PATCH accepts a
commercial update while `quote_status == DECLINED` (it does not reject it), but it does
**not** increment `quote_revision`, does **not** transition `quote_status` back to
`DRAFT`, and does **not** start a new revivable quote lifecycle — the record remains
`DECLINED`. W2B behavior: DECLINED is **display-only** for commercial quote editing;
there is **no frontend workaround**. Future remediation: a separate approved backend
contract change is required if the product must support re-quoting after a client
decline.

**GAP-2 — NOT_REQUIRED cannot be promoted to DRAFT.** The deployed PATCH accepts
canonical quote fields while `quote_status == NOT_REQUIRED`, but does **not** transition
it to `DRAFT` — the record remains `NOT_REQUIRED`. W2B behavior: NOT_REQUIRED is
**display-only**; there is **no frontend workaround**. Future remediation: a separate
approved backend change is required if an owner must convert a `NOT_REQUIRED` request
into a quoted request.

**GAP-3 — initial statusless half-create is possible.** For a request with no
`quote_status`, the deployed quote-update contract establishes `DRAFT` only when the
first PATCH includes `quote_amount_cents` **or** `quote_notes_client`. A first PATCH
containing only fields such as `currency`, `deposit_amount_cents`, `payment_requirement`,
or internal-only notes can leave `quote_status` absent. W2B mitigation: the first
canonical quote save **requires a valid quote amount**, so W2B never generates this
half-created state. Future remediation: backend hardening may normalize any valid
initial commercial quote update into `DRAFT`.

These gaps do **not** block the primary W2B supported-state editor (create/edit `DRAFT`,
commercial-revise `SENT`/`ACCEPTED`, internal-note edits). No production test record
should be created to reproduce or document them.

### Workstream 3 — Tenant Customer Payment Architecture
Requirements:
- Keep **Plane A (USMISSIONHERO SaaS billing)** and **Plane B (tenant customer
  payments)** architecturally distinct.
- Tenant owns the customer-payment relationship; choose a Plane-B model
  (tenant-owned external / per-tenant Stripe / Stripe Connect / provider abstraction)
  as a **pending Matthew product decision** — do not default to Stripe Connect.
- Sandbox-only current state; no USMISSIONHERO-Stripe processing of tenant customer
  payments without explicit architectural approval.
- No Stripe live work (EIN-blocked).

### Workstream 4 — Status Vocabulary Cleanup
Requirements:
- Eliminate contradictory `QUOTE_NEEDED` (card) vs "no quote action required"
  (detail) presentation.
- `quote_status` precedence for all client-facing quote labels; legacy RequestStatus
  is admin/workflow-summary only.
- Define a single display-state mapping shared by admin/client × web/mobile, and
  split the detail screen's `default` branch so DRAFT ≠ NOT_REQUIRED copy.

---

## C. Recommended implementation order
1. **Workstream 2 (owner/admin quote-send bridge)** — highest leverage: it unblocks
   M4 and makes the canonical quote lifecycle usable end-to-end. Web admin first.
2. **Workstream 4 (status vocabulary)** — small, high-clarity; pairs naturally with
   W2 since both touch quote display.
3. **Workstream 1 (existing-pet selection by `pet_id`)** — removes the fragmented
   pet-association model and the legacy `pet_names`-string producer.
4. **Workstream 3 (tenant payment architecture)** — a product/architecture **decision**
   first (pending Matthew), then OPS-3B implementation; Stripe-gated.

Each is a separate reviewed change with its own tests and (for backend/deploy)
separate Matthew approval. No implementation in this turn.

---

## D. Dispositions
- `STATUS_VOCABULARY_MISMATCH_FOUND=YES`
- `M4_PRODUCTION_MUTATION_TEST_AUTHORIZED=PAUSED_FOR_WORKFLOW_RECONCILIATION`
- `RYAN_TESTING_AUTHORIZED=NO`
- `MOBILE_PUBLIC_DISTRIBUTION_AUTHORIZED=NO`
- Stripe remains sandbox-only (EIN-blocked); no live payment work.
