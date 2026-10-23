# PetCare Hero — Workstream 3 (Tenant Customer Payment Architecture) — Decision Package

**Phase:** W3-A (architecture / decision only). **This document selects nothing and implements nothing.**

**Disposition:** `W3_PAYMENT_ARCHITECTURE_DECISION_READY_FOR_MATTHEW`

- `W3_ARCHITECTURE_DECISION_PHASE_AUTHORIZED=YES`
- `W3_PAYMENT_MODEL_SELECTED=NO`
- `W3_PAYMENT_IMPLEMENTATION_AUTHORIZED=NO`
- `W3_ARCHITECTURE_DECISION_PHASE_COMPLETE` (pending Matthew's model selection in §8)

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
single platform Stripe account and the same webhook/secret used for Plane A SaaS billing.** This
conflates the two planes: today, a pet owner paying Togs & Dogs would pay **into USMISSIONHERO's
Stripe balance**, making USMISSIONHERO the de-facto merchant/business of record for tenant
customer money. This is sandbox-only today, so no real customer money has flowed, but the
architecture must be corrected before any live Plane-B money is enabled.

**Recommendation (for Matthew to accept or override):**
- **MVP:** `W3_RECOMMENDED_MVP_MODEL = PROVIDER_ABSTRACTION + TENANT_OWNED_EXTERNAL` (Option D
  wrapping Option A) — a canonical provider-neutral payment domain whose first adapter is
  `MANUAL/EXTERNAL` (tenant collects via their own means; PetCare Hero records state). This keeps
  USMISSIONHERO entirely out of the Plane-B money flow and out of PCI/merchant-of-record scope
  while the product matures.
- **Long term:** `W3_RECOMMENDED_LONG_TERM_MODEL = PROVIDER_ABSTRACTION + TENANT_DIRECT (Stripe
  tenant-owned)` with an optional later `STRIPE_CONNECT` adapter if/when PetCare Hero chooses to
  become a payments platform. The provider abstraction is the durable architecture; the specific
  processor is a pluggable adapter.
- `W3_RECOMMENDATION_CONFIDENCE = MEDIUM` (the processor choice is genuinely Matthew's product
  decision; the provider-abstraction + keep-platform-out-of-Plane-B spine is HIGH confidence).

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

## 6. Architecture options

### Option A — Tenant-owned external / off-platform
PetCare Hero manages workflow only; tenant collects customer payments via their own means
(tenant's own Stripe link, Square, invoice, cash/check). PetCare Hero records payment state
(manually or via later import).
- **Pros:** zero PCI/merchant-of-record exposure for USMISSIONHERO; near-zero incremental cost;
  trivial tenant onboarding; works for any tenant/processor; fastest MVP; clean reconciliation
  ownership stays with the tenant.
- **Cons:** manual/limited automation; no in-product payment UX; reconciliation is tenant-driven.

### Option B — Per-tenant Stripe account (tenant-owned Stripe, direct integration)
Each tenant connects/owns their own Stripe account; PetCare Hero integrates against that account.
- **Pros:** tenant is merchant of record; money never touches USMISSIONHERO; good automation.
- **Cons:** credential/secret isolation per tenant; webhook routing per account; offboarding;
  **do NOT** default to raw secret-key entry — prefer Stripe OAuth / account authorization. More
  build + support than A.

### Option C — Stripe Connect (platform)
PetCare Hero becomes a Connect platform with connected tenant accounts. Not one design — the
charge model determines liability:

| Connect model | Merchant/business of record | Who receives charge | Who bears fees | Who bears refunds/disputes/negative balance |
|---|---|---|---|---|
| Direct charges (on connected acct) | **tenant** | tenant account | tenant (platform may add app fee) | **tenant** |
| Destination charges (`on_behalf_of` + `transfer_data`) | can be tenant (with `on_behalf_of`) | **platform** first, then transfer | platform/configurable | **platform** (funds pass through platform) |
| Separate charges + transfers | **platform** | platform | platform | **platform** |

- **Account types:** Standard (tenant owns dashboard/KYC, least platform liability), Express
  (platform-managed onboarding, shared), Custom/controller (max control, max platform liability
  + support + KYC burden).
- **Key warning:** Connect does **not** automatically keep USMISSIONHERO out of the money flow —
  destination/separate-charge models route funds through the platform and can make USMISSIONHERO
  liable for refunds/disputes/negative balances. Only **Standard + direct charges** cleanly keeps
  the tenant as merchant of record.
- **Pros:** best in-product UX; scalable; application-fee monetization possible.
- **Cons:** highest complexity, KYC/requirements management, dispute/liability exposure (model
  dependent), platform support burden, Stripe-only lock-in.

### Option D — Payment-provider abstraction
Define a canonical internal `PaymentProvider` interface with adapters: `MANUAL/EXTERNAL`,
`STRIPE_TENANT_DIRECT`, future `STRIPE_CONNECT`, future others.
- **Pros:** decouples the durable domain from the processor; supports non-Stripe tenants; lets MVP
  ship with `MANUAL/EXTERNAL` and grow; isolates the legacy platform path behind one adapter.
- **Cons:** small upfront abstraction cost (mitigated: the domain model is needed regardless).
  YAGNI risk is low because multi-tenant SaaS will realistically need ≥2 providers.

---

## 7. Decision matrix

Scores: ✅ strong / 🟡 moderate / ❌ weak, from PetCare Hero's multi-tenant SaaS standpoint.

| Criterion | A External | B Tenant-direct Stripe | C Connect | D Abstraction (+A first) |
|---|---|---|---|---|
| Tenant owns customer relationship | ✅ | ✅ | 🟡 (model-dependent) | ✅ |
| Plane A/B separation | ✅ | ✅ | 🟡 | ✅ |
| Regulatory/PCI/compliance exposure (USMISSIONHERO) | ✅ lowest | ✅ low | ❌ highest | ✅ (A first) |
| Merchant/business-of-record clarity | ✅ tenant | ✅ tenant | 🟡 model-dependent | ✅ |
| Tenant portability | ✅ | ✅ | 🟡 | ✅ |
| Multi-business SaaS scalability | 🟡 | 🟡 | ✅ | ✅ |
| Development complexity | ✅ lowest | 🟡 | ❌ highest | 🟡 (domain + 1 adapter) |
| Operational complexity | ✅ | 🟡 | ❌ | 🟡 |
| Onboarding friction | ✅ | 🟡 (OAuth connect) | 🟡 | ✅ (A first) |
| Refund/dispute ownership clarity | ✅ tenant | ✅ tenant | 🟡 | ✅ |
| Webhook complexity | ✅ none | 🟡 per-account | ❌ | 🟡 |
| Credential isolation | ✅ none held | 🟡 per-tenant secret store | 🟡 | ✅ |
| AWS secret-management complexity | ✅ | 🟡 | 🟡 | 🟡 |
| Stripe/platform dependency | ✅ none | 🟡 Stripe | ❌ Stripe platform | ✅ pluggable |
| Supports non-Stripe tenants later | ✅ | ❌ | ❌ | ✅ |
| User experience (in-product pay) | ❌ | ✅ | ✅ | 🟡→✅ (grows) |
| Automation | ❌ | ✅ | ✅ | 🟡→✅ |
| Accounting/reconciliation clarity | 🟡 | ✅ | 🟡 | ✅ |
| Cost/fees to USMISSIONHERO | ✅ lowest | ✅ low | 🟡 (app-fee math) | ✅ |
| Near-term MVP speed | ✅ fastest | 🟡 | ❌ slowest | ✅ (A adapter) |
| Future SaaS maturity | 🟡 | 🟡 | ✅ | ✅ |

**Cost profile (`W3_COST_PROFILE`):** A = **LOW**; B = **LOW–MEDIUM**; C = **MEDIUM–HIGH**;
D = **LOW** initially (matches its first adapter), rising only with the chosen processor.
(Exact Stripe fees are not asserted here; verify against a current authoritative Stripe source
before any live-enablement decision.)

---

## 8. Matthew decision block

**`W3_PLANE_B_MODEL_DECISION_REQUIRED`** — choose exactly one:

- **A. Tenant-owned external / off-platform first** — Client sees a quote in PetCare Hero and pays
  the tenant outside the app (tenant's own link/invoice/in-person). Who gets paid: the tenant
  directly. Stripe/account owner: the tenant (outside PetCare Hero). Disputes/refunds: the tenant.
  PetCare Hero's role: workflow + records payment status.
- **B. Tenant-owned Stripe integration** — Client pays inside PetCare Hero via the **tenant's own**
  connected Stripe account (OAuth connect, not raw keys). Who gets paid: the tenant. Account owner:
  the tenant. Disputes/refunds: the tenant. PetCare Hero's role: integrate + orchestrate.
- **C. Stripe Connect** — PetCare Hero becomes a Connect platform. Who gets paid / disputes depend
  on the charge model (see §6/§7) and can make USMISSIONHERO liable. Account owner: connected
  tenant account under the platform. PetCare Hero's role: payments platform.
- **D. Provider abstraction + [initial adapter]** — Build the canonical provider-neutral payment
  domain now; ship with an initial adapter you name (recommend **`MANUAL/EXTERNAL`**), add
  `STRIPE_TENANT_DIRECT` / `STRIPE_CONNECT` later. Client/paid/disputes follow whichever adapter is
  active. PetCare Hero's role: workflow now, orchestration later.
- **E. Other** — specify.

**Kiro's recommendation:** **D with an initial `MANUAL/EXTERNAL` adapter** (i.e. D wrapping A),
with `STRIPE_TENANT_DIRECT` as the intended next adapter and `STRIPE_CONNECT` only if PetCare Hero
deliberately chooses to be a payments platform. `W3_RECOMMENDATION_CONFIDENCE=MEDIUM`.

No implementation proceeds until Matthew records a selection here.

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
  STRIPE_TENANT_DIRECT, STRIPE_CONNECT, …), `provider_account_ref` (opaque, NOT a secret),
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
  (`MANUAL|STRIPE_TENANT_DIRECT|STRIPE_CONNECT`), `payments_enabled` (bool), `payment_mode`
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
  (MANUAL/EXTERNAL, or tenant-direct, or Connect).
- **W3-D — sandbox integration:** sandbox-only wiring, split per-plane webhook/events, admin/client
  UI; **no live keys**.
- **W3-E — controlled acceptance:** separate owner approval; bounded sandbox acceptance.
- **W3-F — production/live enablement:** explicit future Matthew approval only; likely
  EIN/business/compliance-gated (ties to the existing `stripe-live-activation-blocked-pending-ein`
  backlog item).

---

## 17. Security review

- **PCI scope:** MVP (MANUAL/EXTERNAL) keeps USMISSIONHERO out of PCI entirely; tenant-direct /
  Connect use hosted Checkout/Elements (SAQ-A-ish) — **never** handle PAN/CVC in PetCare Hero.
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

Implementation (W3-B+) is blocked until Matthew records a selection in **§8**
(`W3_PLANE_B_MODEL_SELECTED`). Until then: `W3_PAYMENT_MODEL_SELECTED=NO`,
`W3_PAYMENT_IMPLEMENTATION_AUTHORIZED=NO`.

---

## 20. Gates preserved (unchanged by W3-A)

Stripe sandbox-only; no Stripe live work; no Stripe secret access/display;
`SCHEDULING_WORKSTREAM_STATUS=DRAFT_PR_DELIVERY_CHECKPOINT`; `SCHEDULING_PR_MERGE_AUTHORIZED=NO`;
`RYAN_TESTING_AUTHORIZED=NO`; no second tenant; no production test data; no production quote
mutation; no backend/web deployment; no mobile distribution; no worktree prune/repair. Latest
completed production backend release remains `PR22_PRIVACY_PRODUCTION_DEPLOYED_VERIFIED`.
