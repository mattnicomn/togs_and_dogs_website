# PetCare Hero — Workstream 3 (Tenant Customer Payment Architecture) — Decision Package

**Phase:** W3-A (architecture / decision). **Matthew has SELECTED the architecture (Option D).**
This document still implements nothing.

**Disposition:** `W3_OPTION_D_SELECTED_ARCHITECTURE_READY_FOR_FINAL_REVIEW`

- `W3_ARCHITECTURE_DECISION_PHASE_AUTHORIZED=YES`
- `W3_ARCHITECTURE_DECISION_COMPLETE=YES`
- `W3_PAYMENT_MODEL_SELECTED=YES`
- `W3_PLANE_B_MODEL_SELECTED=OPTION_D`
- `W3_OPTION_D_OWNER_APPROVED=YES`
- `W3_SELECTED_MVP_MODEL=PROVIDER_ABSTRACTION + MANUAL_EXTERNAL`
- `W3_SELECTED_LONG_TERM_MODEL=PROVIDER_ABSTRACTION + STRIPE_CONNECT_DIRECT_CHARGES`
- `W3_B_IMPLEMENTATION_READY_FOR_OWNER_AUTHORIZATION=YES`
- `W3_B_IMPLEMENTATION_AUTHORIZED=NO` (a separate owner authorization is required before any
  payment-domain code; this selection authorizes **architecture only**, not implementation)
- `W3_PAYMENT_IMPLEMENTATION_AUTHORIZED=NO`

> **Owner decision (recorded):** Matthew approved **Option D** —
> `PROVIDER_ABSTRACTION + MANUAL_EXTERNAL_FIRST`, with the long-term direction
> `PROVIDER_ABSTRACTION + STRIPE_CONNECT_DIRECT_CHARGES_LATER`. This **selects** the W3
> architecture; it does **not** authorize W3-B implementation in this turn. Marketplace/indirect
> Connect (destination/separate charges, platform-first funds flow) was **not** selected.

**Checkpoint:** authored from `main == origin/main == c6e514ed7f47ff9e5ebe2e9b74c29018ecd18943`
on branch `planning/w3-tenant-customer-payment-architecture`. Documentation/planning only — no
payment implementation, no Stripe secret access, no AWS/Terraform/deploy. Latest completed
production backend release remains `PR22_PRIVACY_PRODUCTION_DEPLOYED_VERIFIED`.

> **Naming boundary:** this is *Workflow & Payment Architecture — Workstream 3 (Tenant Customer
> Payment Architecture)*. It is NOT the historical Ryan scheduling workstreams.

---

## 1. Executive summary

PetCare Hero is a multi-business SaaS. Two money planes must stay architecturally distinct:

- **Plane A — SaaS billing:** USMISSIONHERO LLC → tenant business (subscription). Already
  implemented and sandbox-validated; USMISSIONHERO's own Stripe account belongs here.
- **Plane B — tenant customer payments:** pet owner → tenant business (e.g. pet owner → Togs &
  Dogs). The **tenant** owns this commercial relationship.

**Core finding:** the current source implements an early Plane-B booking-payment path
(`admin create-payment-session` → Stripe Checkout → `stripe_webhook_handler`) **through the same
single platform Stripe account and the same webhook/secret used for Plane A SaaS billing.** The
precise, code-grounded characterization (no legal conclusion asserted): the customer charge is
**created on and settles through the USMISSIONHERO Stripe platform account**; the tenant has **no
independent Plane-B provider-account identity**; this produces unacceptable Plane-A/Plane-B
funds-flow and responsibility ambiguity. Any legal/business-of-record characterization requires
formal commercial/legal confirmation and is out of scope here. This is sandbox-only today (no real
customer money has flowed), but the architecture must be corrected before any live Plane-B money.

**Taxonomy note (corrected):** for a SaaS platform integrating *programmatically* with
tenant-owned Stripe accounts, connected-account authorization/representation **is part of Stripe
Connect**. There is no clean "tenant-owned Stripe via OAuth" alternative that sits *outside*
Connect. Stripe's current model should be described by **funds flow and responsibility**
(connected/merchant configuration, where funds first appear, fee responsibility,
refund/chargeback/negative-balance responsibility, dashboard/KYC responsibility, direct vs
indirect charges), not by a "Connect vs non-Connect Stripe" split.

**Recommendation (for Matthew to accept or override; re-derived from the corrected matrix in §7):**
- **MVP:** `W3_RECOMMENDED_MVP_MODEL = PROVIDER_ABSTRACTION + MANUAL_EXTERNAL` (Option D wrapping
  Option A) — a canonical provider-neutral payment domain whose first adapter is `MANUAL/EXTERNAL`
  (tenant collects via their own means; PetCare Hero records state). This avoids PetCare Hero
  directly handling cardholder data and **materially minimizes** payment/PCI scope and funds-flow
  responsibility while the product matures (final compliance obligations must be confirmed before
  live enablement).
- **Long term:** `W3_RECOMMENDED_LONG_TERM_MODEL = PROVIDER_ABSTRACTION + STRIPE_CONNECT_DIRECT_CHARGES`
  — Stripe Connect with **direct charges on the connected tenant account** (SaaS-fit; the customer
  charge appears on the tenant's connected account). A marketplace/indirect model
  (destination/separate charges, funds originating on the platform) is **not** recommended unless
  PetCare Hero deliberately becomes a marketplace/payments platform. "Stripe Connect" is **not
  automatically high-risk** — the risk is a function of funds-flow/responsibility configuration.
- `W3_RECOMMENDATION_CONFIDENCE = MEDIUM` (the processor/charge-model choice is Matthew's product
  decision; the provider-abstraction + keep-platform-out-of-Plane-B spine, and the preference for
  direct charges over marketplace charges, are HIGH confidence).

The actual model choice is deferred to Matthew via the single decision block in **§8**.

---

## 2. Plane A vs Plane B

| | Plane A — SaaS billing | Plane B — tenant customer payments |
|---|---|---|
| Relationship | USMISSIONHERO LLC → tenant | pet owner → tenant business |
| Example | PetCare Hero subscription, plan tier, add-ons | pet owner pays Togs & Dogs for a booking |
| Who is paid | USMISSIONHERO | the **tenant** |
| Stripe account | USMISSIONHERO's own account (correct) | **must be the tenant's**, not USMISSIONHERO's |
| Current code | `stripe_webhook_handler` subscription/invoice events; `billing.py`; tenant `subscription_status`/`billing_provider` | `admin create-payment-session` → `stripe_client.create_checkout_session` → webhook `payment_type=='booking'` |
| W3 scope | **out of scope** (do not change) | **the subject of W3** |

`W3_PLANE_A_B_SEPARATION_AUDIT = FAIL` **(current state)** — the two planes share one Stripe
account, one `STRIPE_SECRET_KEY`, one `STRIPE_WEBHOOK_SECRET`, and one webhook handler. W3's
purpose is to make `W3_PLANE_A_B_SEPARATION_AUDIT = PASS` the target architecture. (The *target*
designs in §7 all restore separation; the *audit of today* is FAIL and is the problem statement.)

---

## 3. Current-state payment source audit (at `c6e514e`)

Read-only audit of the current source. No secret values were read; secret stores are referenced
by name only.

### 3.1 Source-of-truth matrix

| Component | Current function | Plane | Canonical/legacy | Credential owner | Risk |
|---|---|---|---|---|---|
| `src/backend/common/stripe_client.py` `create_checkout_session` | Creates a Stripe Checkout Session (`mode=payment`) for a **booking** using `STRIPE_SECRET_KEY`; metadata `company_id/request_id/client_id/payment_type=booking` | **B** | canonical-ish (webhook-settled) | **USMISSIONHERO platform account** | **HIGH** — tenant customer money lands in platform balance; no Connect/`on_behalf_of`/transfer |
| `handlers/admin_handler.py` `create-payment-session` route | Owner/admin creates the booking payment link; sets `payment_status='payment_link_sent'`, `stripe_checkout_session_id`, `stripe_payment_url` on REQUEST; tenant-ownership validated (`validate_tenant_ownership`) | B | canonical (REQUEST fields) | platform | HIGH (same account); MED (vocabulary: writes lowercase `payment_link_sent`/`paid`, not the contract's `PaymentStatus`) |
| `handlers/admin_handler.py` `send-payment-email` route | Emails the payment link (`PAYMENT_LINK_EMAIL`); guards `paid/refunded/waived` | B | canonical | platform | LOW |
| `handlers/stripe_webhook_handler.py` | **Shared** endpoint `POST /webhooks/stripe`: Plane-A subscription/invoice events AND Plane-B `checkout.session.completed payment_type=booking` → sets REQUEST `payment_status='paid'`, `stripe_payment_intent_id`; idempotency via `is_event_already_processed`; resolves `company_id` from metadata; validates request↔company | A **and** B | canonical | platform (one `STRIPE_WEBHOOK_SECRET`) | HIGH — one secret/endpoint spans both planes; Plane-B settlement tied to platform account |
| `src/backend/common/billing.py` | Plane-A tenant subscription state (`subscription_status`, `billing_provider`, `stripe_customer_id`, `stripe_subscription_id`), signature verify, event ledger, idempotency, tier limits | **A** | canonical | platform (correct for A) | LOW (out of W3 scope) |
| `src/backend/common/quote_contract.py` | Provider-neutral canonical quote + `PaymentRequirement` (NONE/DEPOSIT/FULL) + `PaymentStatus` (NOT_REQUIRED/UNPAID/PAYMENT_LINK_SENT/PARTIALLY_PAID/PAID/REFUNDED); client projection **forbids** all `stripe_*` fields; quote-accept ≠ payment ≠ approval | neutral | **canonical** | n/a (pure) | LOW — strong foundation to build on |
| `handlers/pet_handler.py` | Legacy PET-level `quote_amount`/`payment_status`/`deposit_paid`/`quote_sent_date` editable fields | B (legacy) | **legacy** | platform (via same link flow) | MED — legacy PET pricing vocabulary (`Accepted`/`Deposit Paid`/`Paid in Full`) |
| `handlers/review_handler.py` | Reads legacy PET `payment_status`/`quote_amount` for booking-readiness gating | B (legacy) | legacy | n/a | MED — legacy readiness path |
| `web/src/components/CareCard.jsx` | Legacy "Pricing & Payment (Stripe Sandbox)" admin UI; payment-link actions | B (legacy) | legacy | platform | MED |
| `web/src/components/AdminQuoteEditor.jsx` | Canonical quote editor (W2) | B | canonical | n/a | LOW |
| `web/src/components/PaymentSuccess.jsx` | Client browser success page after Checkout redirect | B | display-only | n/a | MED — must NOT be treated as proof of payment (webhook is authoritative) |
| `web/src/api/client.js` | `createPaymentSession`/payment-link calls | B | canonical/legacy | n/a | LOW |
| `mobile/src/screens/ClientRequestDetailScreen.tsx`, `RequestDetailScreen.tsx` | Render quote/payment-requirement (no card entry) | B | canonical | n/a | LOW |
| `modules/api/*.tf*` | API route + Lambda env wiring; webhook route `POST /webhooks/stripe`; env names `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_ENV`/`STRIPE_ENVIRONMENT` | A+B | infra | platform | HIGH — single account/secret for both planes |
| `common/tenant_provisioning.py`, `PlatformAdminOnboarding.jsx`, `PlatformTenantDetail.jsx` | Tenant onboarding/metadata (Plane-A billing config) | A | canonical | platform | LOW |

### 3.2 Canonical vs legacy payment findings

- **Canonical (keep/extend):** `quote_contract.py` (`PaymentRequirement`, `PaymentStatus`,
  quote lifecycle, client allowlist that already forbids `stripe_*`); the webhook-settled
  booking `payment_status` on the REQUEST; idempotent event processing in `billing.py`.
- **Legacy (freeze, later retire):** PET-level `quote_amount`/`payment_status` pricing and the
  `CareCard` "Pricing & Payment (Stripe Sandbox)" UI; `review_handler` reading PET payment state.
- **Vocabulary gap:** the live payment path writes lowercase `payment_link_sent`/`paid` strings,
  while `quote_contract.PaymentStatus` defines `PAYMENT_LINK_SENT`/`PAID`. The canonical domain
  (§11) must reconcile these (dual-read exists via `normalize_legacy_payment_status`).

---

## 4. Legacy Plane-B Stripe path — conflation risk

Verified call chain (current source):

1. Admin/owner → `POST /admin/requests/{id}/create-payment-session` (`admin_handler.py`).
2. → `common.stripe_client.create_checkout_session(company_id, request_id, client_id, amount_cents)`
   using `STRIPE_SECRET_KEY` (the **platform** account). No connected account, no `on_behalf_of`,
   no `transfer_data`, no application fee.
3. REQUEST record receives `stripe_checkout_session_id`, `stripe_payment_url`,
   `payment_status='payment_link_sent'`, `payment_amount_cents`, `payment_requested_by`.
4. Pet owner pays on Stripe Checkout (platform account).
5. `checkout.session.completed` → `stripe_webhook_handler` (`payment_type=='booking'`) →
   REQUEST `payment_status='paid'`, `stripe_payment_intent_id`, `payment_completed_at`.

- **Whose Stripe account:** USMISSIONHERO's platform account (same as Plane A).
- **Is the payment for the tenant's customer:** yes (pet owner → tenant), but it settles to the
  **platform**, not the tenant.
- **Does the tenant have independent payment-account identity:** **NO.** Tenant metadata has
  Plane-A billing fields only; there is no `payment_provider`/`payment_provider_account_ref`.
- **Webhook completion canonical:** yes (idempotent, signature-verified, request↔tenant validated).
- **Refunds/disputes modeled:** **NO** (no refund/dispute events handled for bookings; no refund
  entity).
- **Can it be cleanly isolated/deprecated later:** yes — it is reachable only via the dedicated
  admin route + a `payment_type=='booking'` branch in the webhook; both are isolable behind a
  provider adapter and a feature flag.

`W3_LEGACY_PLATFORM_STRIPE_CONFLATION_RISK = YES`.

---

## 5. Current canonical quote/payment semantics — answers

1. **Does quote acceptance mean payment occurred?** No. `apply_quote_accept` sets
   `quote_status=ACCEPTED` only; it explicitly "never touches payment."
2. **Does `APPROVED` require payment?** No. Quote acceptance does not auto-approve; approval is a
   separate admin/workflow action. There is no enforced payment-gated approval predicate today.
3. **Authoritative canonical `payment_status` state machine?** **PARTIAL.** A canonical vocabulary
   exists (`PaymentStatus`), but the live path writes lowercase ad-hoc strings and there is no
   enforced transition/state-machine validator for payments.
4. **Payment transaction entity?** No. Payment state is denormalized onto the REQUEST.
5. **Webhook-driven settlement?** Yes, for the platform-account booking path.
6. **Idempotent payment-event processing?** Yes (`is_event_already_processed`), shared with Plane A.
7. **Refunds represented?** No (no booking refund handling/entity).
8. **Partial/deposit payments represented?** Vocabulary only (`PARTIALLY_PAID`, `DEPOSIT`); no
   deposit+balance ledger or logic.
9. **Any UI implying payment completion without canonical proof?** Risk: `PaymentSuccess.jsx` is a
   browser redirect page; it must be display-only and never treated as proof (webhook is truth).
10. **Does legacy PET-level Stripe mutate REQUEST payment state?** Indirectly — the same
    create-session/webhook flow writes REQUEST fields; legacy PET pricing is read for readiness.

`W3_CURRENT_PAYMENT_STATE_MACHINE_EXISTS = PARTIAL`.

---

## 6. Architecture options (taxonomy corrected)

The options are framed by **funds flow and responsibility**, not by a false "Connect vs
non-Connect Stripe" split. Any programmatic integration with a tenant-owned Stripe account is a
**Stripe Connect** integration; the meaningful axis is the **charge model** (direct vs indirect)
and the resulting responsibility configuration.

### Option A — External / off-platform tenant payments
PetCare Hero does **not** integrate with a processor. The tenant owns the processor relationship
entirely outside PetCare Hero (tenant's own Stripe link, Square, invoice, cash/check). PetCare
Hero records payment state (manually now, or via a later import adapter).
- **Pros:** PetCare Hero does not handle cardholder data → payment/PCI scope materially minimized;
  near-zero incremental cost; trivial tenant onboarding; works for any tenant/processor; fastest
  MVP; reconciliation ownership stays with the tenant.
- **Cons:** manual/limited automation; no in-product payment UX; reconciliation is tenant-driven.

### Option B — Stripe Connect, SaaS / **direct-charge** model
The tenant is represented as a **connected merchant account**; the customer payment (Checkout/
PaymentIntent) is created **on the tenant/connected account**, so funds first appear in the
**connected tenant account balance**. The connected tenant is the seller/merchant-facing payment
account. The platform *may optionally* collect an application fee later (separately approved).
- **Funds flow:** customer → **connected tenant account** (direct charge).
- **Fee responsibility:** configuration-dependent (tenant pays Stripe fees; optional platform app
  fee).
- **Refund/chargeback balance impact:** generally the **connected-account** balance.
- **Loss/negative-balance responsibility:** configuration-dependent; direct charges keep this
  primarily with the connected tenant.
- **Dashboard/KYC responsibility:** the connected tenant (platform assists onboarding).
- **Account/responsibility configuration:** evaluate against **current Stripe Accounts v2 /
  controller-based responsibility configuration** (who is responsible for fees, losses, pricing,
  requirements/KYC, dashboard). Do **not** design primarily around the legacy Standard/Express/
  Custom labels (see §4-note below). Suited to SaaS-style platforms.
- **Pros:** in-product UX; tenant is the customer-facing payment account; automation; SaaS-fit.
- **Cons:** Connect onboarding + requirements management; per-connected-account webhook handling;
  Stripe lock-in for this adapter.

### Option C — Stripe Connect, **marketplace / indirect-charge** model
**Destination charges** (`on_behalf_of` + `transfer_data`) and/or **separate charges + transfers**:
the charge **originates on the platform** and funds first appear in the **platform** balance
before transfer.
- **Funds flow:** customer → **platform** balance → transfer to tenant.
- **Refund/chargeback balance impact + negative-balance risk:** substantially greater **platform**
  exposure.
- **Fit:** marketplace-style models. **Not appropriate** for PetCare Hero's current SaaS model
  unless the product deliberately becomes a marketplace/payments platform. PetCare Hero should
  **NOT default to destination/separate charges.**
- **Pros:** central control of funds/splits (marketplace use cases).
- **Cons:** highest platform liability (fees/refunds/chargebacks/negative balance), highest
  complexity, Stripe lock-in.

### Option D — Provider abstraction
Define a canonical internal `PaymentProvider` interface with adapters: `MANUAL/EXTERNAL`
(= Option A), `STRIPE_CONNECT_DIRECT` (= Option B), future `STRIPE_CONNECT_MARKETPLACE`
(= Option C) only if ever needed, and future non-Stripe providers.
- **Pros:** decouples the durable domain from the processor; supports non-Stripe tenants; lets MVP
  ship with `MANUAL/EXTERNAL` and grow into direct-charge Connect; isolates the legacy platform
  path behind one adapter.
- **Cons:** small upfront abstraction cost (mitigated: the payment domain model is needed
  regardless). YAGNI risk is low because a multi-tenant SaaS will realistically need ≥2 providers.

> **§4-note (current Stripe model):** Stripe's current architecture (Accounts v2) supports
> **configurable merchant/account responsibilities** — including fee collection and
> negative-balance/loss responsibility. New designs should be evaluated against the current
> Accounts v2 / controller responsibility configuration, **not solely** the legacy Standard /
> Express / Custom account-type labels (retained here only as older background terminology). OAuth
> connect flows may still involve Accounts v1 in some cases; that is an implementation detail to
> resolve in the later adapter phase (W3-C), not a separate Plane-B architecture.

---

## 7. Decision matrix (re-scored on funds flow / responsibility)

Scores: ✅ strong / 🟡 moderate / ❌ weak, from PetCare Hero's multi-tenant SaaS standpoint. The
B-vs-C distinction is about **funds flow / responsibility**, not "Connect vs non-Connect."

| Dimension | A External | B Connect SaaS **direct charges** | C Connect **marketplace/indirect** | D Abstraction (+A first, B later) |
|---|---|---|---|---|
| Tenant customer relationship (tenant owns it) | ✅ | ✅ | 🟡 | ✅ |
| Charge account (where charge is created) | tenant (off-platform) | **connected tenant acct** | **platform** | adapter-dependent |
| Where funds first appear | tenant | **connected tenant balance** | **platform balance** | adapter-dependent |
| Fee responsibility | tenant | tenant (config; optional app fee) | platform-mediated | adapter-dependent |
| Refund/chargeback balance impact | tenant | connected-account balance | **platform balance** | adapter-dependent |
| Loss / negative-balance responsibility | tenant | tenant (config; direct) | **platform** | adapter-dependent |
| Onboarding / KYC responsibility | tenant (external) | connected tenant (+platform assist) | connected tenant (+more platform) | A: none → B later |
| SaaS fit | 🟡 | ✅ | ❌ | ✅ |
| Marketplace fit | ❌ | 🟡 | ✅ | 🟡 |
| Implementation complexity | ✅ lowest | 🟡 | ❌ highest | 🟡 (domain + 1 adapter) |
| Platform liability (USMISSIONHERO) | ✅ lowest | 🟡 low (direct) | ❌ highest | ✅ (A first) |
| Payment/PCI scope (PetCare Hero handling card data) | ✅ none | ✅ none (hosted Checkout/Elements) | ✅ none (hosted) | ✅ (A first) |
| Tenant portability | ✅ | ✅ | 🟡 | ✅ |
| Non-Stripe portability | ✅ | ❌ | ❌ | ✅ |
| Credential isolation | ✅ none held | 🟡 per-connected-account | 🟡 | ✅ |
| User experience (in-product pay) | ❌ | ✅ | ✅ | 🟡→✅ (grows) |
| Automation / reconciliation | 🟡 | ✅ | 🟡 | 🟡→✅ |
| Cost/fees exposure to USMISSIONHERO | ✅ lowest | ✅ low | 🟡 | ✅ |
| Near-term MVP speed | ✅ fastest | 🟡 | ❌ slowest | ✅ (A adapter) |
| Future SaaS maturity | 🟡 | ✅ | 🟡 | ✅ |

**Cost profile (`W3_COST_PROFILE`):** A = **LOW**; B (Connect direct) = **LOW–MEDIUM**;
C (Connect marketplace/indirect) = **MEDIUM–HIGH** (greater platform liability/ops);
D = **LOW** initially (matches its first adapter), rising only with the chosen charge model.
(Exact Stripe fees are not asserted here; verify against a current authoritative Stripe source
before any live-enablement decision.)

**Re-derived recommendation:** Option **D** with a **MANUAL/EXTERNAL** first adapter (= A) and a
**Connect direct-charge** adapter later (= B). Option C (marketplace/indirect) is explicitly not
recommended for the current SaaS model. This is a recommendation, not a selection.

---

## 8. Matthew decision block

**`W3_PLANE_B_MODEL_DECISION_REQUIRED`** — choose exactly one:

- **A. External / manual first only** — Client sees the quote in PetCare Hero and pays the tenant
  **outside** the app (tenant's own link/invoice/in-person). Who gets paid: the tenant directly.
  Payment account owner: the tenant (off-platform). Disputes/refunds: the tenant. PetCare Hero's
  role: workflow + records payment status.
- **B. Stripe-integrated SaaS **direct-charge** model now** — Client pays inside PetCare Hero; the
  charge is created **on the tenant's connected account** (direct charge) so funds appear in the
  **tenant's** balance. Who gets paid: the tenant. Account: tenant's connected account.
  Disputes/refunds: primarily the connected-account balance. PetCare Hero's role: integrate +
  orchestrate (SaaS platform, direct charges).
- **C. Marketplace / platform **indirect-charge** model now** — Charge originates on the
  **platform** (destination/separate charges); funds appear in the **platform** balance first.
  Who gets paid: tenant after transfer. Disputes/refunds/negative-balance: **substantially the
  platform**. PetCare Hero's role: marketplace/payments platform. (Higher platform liability; not
  recommended for the current SaaS model.)
- **D. Provider abstraction, MANUAL/EXTERNAL first, Stripe **direct-charge** adapter later** —
  Build the canonical provider-neutral payment domain now; ship with `MANUAL/EXTERNAL` (= A), add
  a `STRIPE_CONNECT_DIRECT` adapter (= B) later; marketplace (= C) only if ever needed. PetCare
  Hero's role: workflow now, orchestration later.
- **E. Other** — specify.

**Kiro's recommendation (re-derived, not assumed):** **D** — provider abstraction with
`MANUAL/EXTERNAL` first and a **Stripe Connect direct-charge** adapter later (i.e. D wrapping A
now, B later). Option C (marketplace/indirect) is not recommended unless PetCare Hero deliberately
becomes a payments platform. Note: "Stripe Connect" is **not automatically high-risk** — risk
depends on funds-flow/responsibility configuration, and direct charges keep the tenant as the
customer-facing payment account. `W3_RECOMMENDATION_CONFIDENCE=MEDIUM`.

**OWNER SELECTION (recorded 2026-10-23):** Matthew selected **Option D** —
`W3_PLANE_B_MODEL_SELECTED=OPTION_D`; `W3_PAYMENT_MODEL_SELECTED=YES`;
`W3_SELECTED_MVP_MODEL=PROVIDER_ABSTRACTION + MANUAL_EXTERNAL`;
`W3_SELECTED_LONG_TERM_MODEL=PROVIDER_ABSTRACTION + STRIPE_CONNECT_DIRECT_CHARGES`;
`W3_OPTION_D_OWNER_APPROVED=YES`. Options B (Stripe Connect SaaS direct-charge **as the MVP**),
C (marketplace/indirect), and E were not selected; C specifically (destination / separate charges /
platform-first funds flow) is **not** the selected architecture and remains a future change
requiring explicit approval (not prohibited forever, simply not selected).

This selection **selects the architecture only**. It does **not** authorize W3-B implementation:
`W3_B_IMPLEMENTATION_READY_FOR_OWNER_AUTHORIZATION=YES` but `W3_B_IMPLEMENTATION_AUTHORIZED=NO`.
A separate implementation authorization follows after this decision record is reviewed/merged.

### Selected architecture — what it means

**MVP (`MANUAL_EXTERNAL` adapter):**
- PetCare Hero implements a provider-neutral payment domain.
- PetCare Hero does **not** move tenant customer money; the tenant collects customer payment using
  the tenant's own external method.
- PetCare Hero records provider-neutral payment state/workflow only.
- PetCare Hero does **not** handle PAN/CVC.
- **No** tenant customer charge is created on the USMISSIONHERO Stripe account.
- Plane A (SaaS billing) and Plane B (tenant customer payments) remain separated.

**Long-term (`STRIPE_CONNECT_DIRECT` adapter, later, separately authorized):**
- Tenant represented as a connected merchant/payment account.
- **Direct-charge / SaaS-style** funds flow; the customer charge is created against the
  tenant-connected account (funds appear in the tenant's balance).
- **Avoid** marketplace / destination / separate-charge architecture unless separately approved.
- Platform responsibility / funds-flow configuration (Accounts v2 / controller) must be reviewed
  again before implementation and again before live enablement.
- This is the selected long-term **architectural adapter direction**; Stripe Connect
  implementation is **NOT** approved now.

---

## 9. Canonical provider-neutral payment domain (proposal only — not implemented)

Reconciled against `quote_contract.py`. Reuse the existing enums; add the smallest correct
payment state machine.

- **`PaymentRequirement`** (exists): `NONE | DEPOSIT | FULL`.
- **`PaymentStatus`** (exists; adopt as the canonical set, reconciling the live lowercase strings):
  `NOT_REQUIRED | UNPAID | PAYMENT_LINK_SENT | PARTIALLY_PAID | PAID | REFUNDED`.
  - Proposed minimal additions for correctness, **pending reconciliation**: `PENDING` (provider
    session created, awaiting settlement — maps the current `payment_link_sent` intent) and
    `FAILED`; `PARTIALLY_REFUNDED` only if deposits+refunds are actually built. **Do not adopt
    speculative values** — keep the smallest set the chosen adapter needs. The existing
    `PAYMENT_LINK_SENT` already covers the "awaiting payment after link" case, so `PENDING` may be
    unnecessary; decide during W3-B.
- **Smallest correct state machine (candidate):**
  `NOT_REQUIRED` (terminal) ; `UNPAID → PAYMENT_LINK_SENT → PAID` ; `PAYMENT_LINK_SENT → UNPAID`
  (link expired/voided) ; `PAID → REFUNDED` ; with `PARTIALLY_PAID` only on the DEPOSIT path.
  Illegal transitions (e.g. `PAID → PAYMENT_LINK_SENT`) are rejected.
- **Payment fields (provider-neutral):** `payment_requirement`, `payment_status`,
  `amount_required_cents`, `amount_paid_cents`, `currency`, `provider` (enum: MANUAL/EXTERNAL,
  STRIPE_CONNECT_DIRECT, STRIPE_CONNECT_MARKETPLACE, …), `provider_account_ref` (opaque, NOT a secret),
  `provider_txn_ref` (session/payment-intent id), `request_id`/`booking_id`, `company_id`
  (tenant), `client_id`, `created_at`, `updated_at`, `payment_completed_at`, refund state
  (`refunded_amount_cents`, `refunded_at`), failure state (`last_failure_reason`), and
  audit/event metadata.
- **Never store:** PAN, CVC, full card data, raw provider secrets, or anything beyond opaque
  references. The existing client projection already forbids `stripe_*` fields — preserve that.

---

## 10. Payment entity boundary

Options: (A) fields on REQUEST; (B) fields on BOOKING/JOB; (C) separate PAYMENT entity;
(D) hybrid — summary on REQUEST + separate transaction/event records.

**`W3_PAYMENT_ENTITY_RECOMMENDATION = D (hybrid)`** — keep a denormalized summary
(`payment_status`, `amount_required_cents`, `amount_paid_cents`, `provider`) on the REQUEST for
fast reads/display (consistent with today), and add append-only `PAYMENT_EVENT` / transaction
records (keyed under the REQUEST/tenant) for attempts, deposits+balance, refunds, retries,
webhook-replay idempotency, audit history, and future providers. Rationale: deposits+balance,
refunds, and idempotent webhook replay cannot be represented correctly by REQUEST fields alone,
but list/card surfaces should not pay an N+1 or join cost for the common display case.

---

## 11. Booking-readiness contract (provider-neutral proposal)

Preserve **`quote acceptance != payment complete != APPROVED`**. Proposed predicates (terminology
from `quote_contract.py`; derive exact field names in W3-B):

- `payment_requirement == NONE`: booking-ready when `quote_status == ACCEPTED`.
- `payment_requirement == DEPOSIT`: booking-ready when `quote_status == ACCEPTED AND
  amount_paid_cents >= deposit_amount_cents` (i.e. `payment_status in {PARTIALLY_PAID, PAID}` with
  the deposit satisfied).
- `payment_requirement == FULL`: booking-ready when `quote_status == ACCEPTED AND
  amount_paid_cents >= quote_amount_cents` (i.e. `payment_status == PAID`).

Approval remains a distinct admin/workflow action; readiness is a computed predicate, not an
auto-transition. No production behavior changes in W3-A.

`W3_BOOKING_READINESS_CONTRACT_PROPOSED = YES`.

---

## 12. Webhook / event architecture (proposal only)

For any integrated-provider adapter:
- Dedicated, signature-authenticated webhook; **per-plane separation** (do not keep Plane-B
  booking settlement on the same endpoint/secret as Plane-A SaaS billing — split them).
- Resolve tenant + provider-account from event metadata/account id (server-trusted, never client).
- Idempotency key per provider event id; duplicate-event no-op; out-of-order handling via state
  machine (ignore illegal/backward transitions).
- Transaction lookup by `provider_txn_ref`; verify amount + currency against the expected quote.
- Validate request/booking belongs to the resolved tenant (fail closed on mismatch — the current
  handler already does this for bookings; keep it).
- Append a `PAYMENT_EVENT` audit record; dead-letter/retry on processing failure (return 5xx so
  the provider retries, as today).
- **Never** treat a browser success redirect (`PaymentSuccess.jsx`) as proof of payment.

No infrastructure is implemented in W3-A.

---

## 13. Tenant configuration + secret boundary (proposal only)

- **Tenant metadata/config (DynamoDB, non-secret):** `payment_provider`
  (`MANUAL|STRIPE_CONNECT_DIRECT|STRIPE_CONNECT_MARKETPLACE`), `payments_enabled` (bool), `payment_mode`
  (`sandbox|live`), `payment_provider_account_ref` (opaque account id, **not** a secret),
  `default_currency`.
- **Secret store (Secrets Manager/SSM, by name only):** any provider credential/connection token,
  per-tenant, referenced by a tenant-scoped secret **name** that contains no customer/private
  data. Raw secrets are never stored in DynamoDB config and never logged/echoed.
- **Application database:** the canonical payment summary + `PAYMENT_EVENT` records.
- **Provider:** holds the actual money movement + PCI scope (the whole point of keeping
  USMISSIONHERO out of Plane B for the MVP).

---

## 14. Multi-tenant isolation (design)

Every payment operation must require: trusted tenant resolution (`get_current_company_id`),
trusted authenticated identity (`resolve_client_identity`/role), provider-account association
belonging to that tenant, request/booking belonging to that tenant, and payment belonging to the
same tenant. No caller-supplied `client_id`/`company_id`/account id is authoritative. This mirrors
the existing W1 ownership model and the current `validate_tenant_ownership` guard.

`W3_PAYMENT_TENANT_ISOLATION_DESIGN = PASS` (design-level; enforced in implementation phases).

---

## 15. Legacy migration / deprecation plan (bounded; nothing executed in W3-A)

Legacy = PET-level "Pricing & Payment (Stripe Sandbox)" (`CareCard`, PET `quote_amount`/
`payment_status`, `review_handler` readiness reads) + the platform-account booking path.
1. **Freeze** legacy expansion (no new features on the legacy PET pricing / platform-account path).
2. **Introduce** the canonical provider abstraction + payment domain (W3-B), provider-neutral.
3. **Feature-flag** the canonical Plane-B flow per tenant (`payment_provider`), default MANUAL.
4. **Compatibility / read-only** legacy state (dual-read already exists via
   `normalize_legacy_payment_status`; keep reading legacy records, stop writing legacy vocabulary).
5. **Explicit future retirement** of the platform-account booking path and legacy PET pricing UI,
   owner-approved, after the canonical flow is proven. **No deletion and no production data
   migration in W3-A.**

---

## 16. Implementation roadmap (after Matthew chooses — not executed)

- **W3-B — provider-neutral payment domain:** canonical `PaymentStatus` state machine + validator;
  hybrid PAYMENT summary + `PAYMENT_EVENT` entity; booking-readiness predicate; unit tests. **No
  Stripe calls.**
- **W3-C — selected provider adapter:** implement the adapter for Matthew's chosen Plane-B model
  (`MANUAL/EXTERNAL`, or Stripe Connect **direct-charge**, or Stripe Connect marketplace/indirect).
  Resolve the current Accounts v2 / controller responsibility configuration (and any OAuth/account
  authorization details) here.
- **W3-D — sandbox integration:** sandbox-only wiring, split per-plane webhook/events, admin/client
  UI; **no live keys**.
- **W3-E — controlled acceptance:** separate owner approval; bounded sandbox acceptance.
- **W3-F — production/live enablement:** explicit future Matthew approval only; likely
  EIN/business/compliance-gated (ties to the existing `stripe-live-activation-blocked-pending-ein`
  backlog item).

---

## 17. Security review

- **PCI scope:** MVP (`MANUAL/EXTERNAL`) avoids PetCare Hero directly handling cardholder data and
  **materially minimizes** payment/PCI scope; Stripe Connect adapters use hosted Checkout/Elements
  so PetCare Hero still never handles PAN/CVC. **Never** handle PAN/CVC in PetCare Hero. Final PCI/
  compliance obligations (and the distinct merchant/business-of-record, payment/refund/dispute, and
  regulatory/legal responsibilities — which are separate questions) must be confirmed before live
  enablement; this document asserts no legal conclusion.
- **Secrets:** per-tenant provider credentials in a secret store, by name; never in DynamoDB/logs.
- **Tokenization:** rely on provider tokenization; store only opaque references.
- **Webhook auth:** signature-verified; per-plane secret; reject unverified.
- **Replay/idempotency:** per-event idempotency keys + append-only events; duplicate = no-op.
- **Tenant isolation / confused-deputy:** resolve tenant + account server-side; validate every
  entity belongs to the same tenant; fail closed on mismatch.
- **Amount tampering:** verify webhook amount/currency against the expected quote before marking paid.
- **Client-side success spoofing:** browser redirect is never proof; webhook is authoritative.
- **Refund/admin authorization:** refunds and payment mutations gated to owner/admin + audited.
- **Auditability:** every transition writes a `PAYMENT_EVENT`.
- **Provider outage/failure modes:** degrade to UNPAID/PENDING; never fabricate PAID.

`W3_PAYMENT_SECURITY_ARCHITECTURE_REVIEW = PASS` (architecture-level; re-reviewed per phase).

---

## 18. Explicit non-goals (W3-A)

No Stripe Connect calls, connected-account creation, OAuth, account links, Checkout Sessions,
PaymentIntents, webhook endpoints, Terraform, secrets, env vars, payment tables, DynamoDB records,
production code paths, or UI payment buttons. No model selection on Matthew's behalf. No live
Stripe. No secret values read. No deployment. No worktree prune/repair.

---

## 19. Owner decision gate

**Architecture selection: DONE.** Matthew selected **Option D** (§8):
`W3_PAYMENT_MODEL_SELECTED=YES`, `W3_PLANE_B_MODEL_SELECTED=OPTION_D`,
`W3_ARCHITECTURE_DECISION_COMPLETE=YES`.

**Remaining gate — implementation authorization:** W3-B (and all later phases) remain blocked on a
**separate** explicit owner authorization. `W3_B_IMPLEMENTATION_READY_FOR_OWNER_AUTHORIZATION=YES`;
`W3_B_IMPLEMENTATION_AUTHORIZED=NO`; `W3_PAYMENT_IMPLEMENTATION_AUTHORIZED=NO`. No payment-domain
code, no Stripe/Connect work, no deployment proceeds until that separate authorization is given.

### W3-B — Provider-Neutral Payment Domain (planned next phase — NOT authorized/implemented here)

Expected scope (later, upon separate owner authorization):
- canonical `PaymentStatus` normalization + state transitions (reconcile the live lowercase
  `payment_link_sent`/`paid` strings to the contract vocabulary);
- provider-neutral payment summary (on REQUEST);
- append-only `PAYMENT_EVENT` / transaction audit records;
- booking-readiness predicate (NONE/DEPOSIT/FULL; quote-accept ≠ paid ≠ APPROVED);
- amount/currency invariants;
- tenant isolation (trusted resolution; no caller-supplied identity authority);
- idempotency primitives;
- the `MANUAL_EXTERNAL` adapter boundary/interface;
- unit tests.

Explicit W3-B non-goals (do NOT implement in W3-B): no Stripe API calls; no Stripe Connect; no
OAuth/account links; no Checkout Sessions; no PaymentIntents; no live Stripe; no webhook
infrastructure; no Terraform/AWS deployment; no production mutation; no payment UI that moves money.

---

## 20. Gates preserved (unchanged by W3-A)

Stripe sandbox-only; no Stripe live work; no Stripe secret access/display;
`SCHEDULING_WORKSTREAM_STATUS=DRAFT_PR_DELIVERY_CHECKPOINT`; `SCHEDULING_PR_MERGE_AUTHORIZED=NO`;
`RYAN_TESTING_AUTHORIZED=NO`; no second tenant; no production test data; no production quote
mutation; no backend/web deployment; no mobile distribution; no worktree prune/repair. Latest
completed production backend release remains `PR22_PRIVACY_PRODUCTION_DEPLOYED_VERIFIED`.
