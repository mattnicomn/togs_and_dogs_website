# PetCare Hero — W3-C MANUAL_EXTERNAL Adapter — Implementation Plan (Planning Only)

**Date:** 2026-10-23
**Phase:** W3-C planning / source reconciliation. **This document implements nothing.**
**Disposition:** `W3C_MANUAL_EXTERNAL_IMPLEMENTATION_PLAN_HARDENED_READY_FOR_MATTHEW`
(PR #30 IAM/atomicity hardening applied)

**Authoritative checkpoint:** `main == origin/main == 2813451e7182eb0f1b9ee0b85e26f3247eef9889`
(PR #29 MERGED; W3-B `MERGED_NOT_DEPLOYED`).

**Authorization state:**
- `W3_PLANE_B_MODEL_SELECTED=OPTION_D`
- `W3_SELECTED_MVP_MODEL=PROVIDER_ABSTRACTION + MANUAL_EXTERNAL`
- `W3_SELECTED_LONG_TERM_MODEL=PROVIDER_ABSTRACTION + STRIPE_CONNECT_DIRECT_CHARGES`
- `W3_C_IMPLEMENTATION_AUTHORIZED=NO` (planning only; implementation requires a
  separate explicit Matthew authorization)
- `W3C1_IAM_CHANGE_AUTHORIZED=NO`; `W3C1_TERRAFORM_CHANGE_AUTHORIZED=NO`;
  `W3C1_DEPLOYMENT_AUTHORIZED=NO` — the required runtime `dynamodb:TransactWriteItems`
  IAM grant (see §4.1) is **not** authorized in this planning turn.
- Stripe Connect Direct remains **known, non-executable, not started**. Marketplace /
  indirect remains **not selected**.

W3-C1 proves the merged W3-B domain with **no payment-processor integration**: a
server-only MANUAL_EXTERNAL settlement-recording service, atomic persistence, and an
owner/admin authorization boundary — no API route, no UI, no Stripe.

---

## 1. Source reconciliation (read-only audit at `2813451`)

`W3C1_SOURCE_RECONCILIATION=PASS` — the merged W3-B domain plus the existing
auth/RBAC, tenant-ownership, concurrency, and audit machinery are sufficient to build
W3-C1 with **no new AWS resource** and **no new spoofing surface**. (One runtime IAM
policy grant is required before deployment — `dynamodb:TransactWriteItems` — see §4.1;
it is an existing-role modification, not a new resource, and is not authorized here.)

**W3-B domain (`src/backend/common/payment_domain.py`, merged):** provides everything
the adapter needs as pure building blocks — `canonical_cents`, the six-state
`PaymentStatus` machine (`validate_transition`), `validate_payment_amounts`,
`validate_active_provider` (MANUAL_EXTERNAL only), `build_payment_event`,
`build_payment_summary`, `is_booking_payment_ready`, `load_owned_request`, and
`persist_payment_event` with the `CREATED`/`DUPLICATE_SAME_EVENT`/
`CONFLICTING_IDEMPOTENCY_KEY` result contract. W3-C1 is largely an orchestration layer
over these.

**Auth / role model (`src/backend/common/auth.py`):** Cognito-group-derived role
hierarchy `owner(4) > admin(3) > staff(2) > client(1) > platform_admin(0.5)` via
`get_effective_role(event)`. Helpers: `is_owner`, `is_admin` (owner|admin),
`require_owner_or_admin(event)` (raises `PermissionError` otherwise). Tenant identity is
resolved **only** from the trusted claim `custom:company_id` via
`get_current_company_id(event)` — never from body/query/header.
`validate_tenant_ownership(item, event)` compares `item.company_id` (default
`tog_and_dogs`) to the caller company.

**REQUEST ownership / keys:** the canonical REQUEST item is
`PK=REQ#{request_id}`, `SK=CLIENT#{client_id}`; `company_id` lives on the item
(absent → `DEFAULT_COMPANY_ID`, the live convention). W3-B's `load_owned_request`
already loads by this key and fails closed on tenant/client mismatch. PAYMENT_EVENTs
share the collection at `SK=PAYEVENT#{idempotency_key}`.

**Concurrency convention:** the quote accept/decline/send paths in
`admin_handler.py` use **optimistic conditional `UpdateItem`** —
`ConditionExpression = Attr('quote_revision').eq(expected) & Attr('quote_status').eq(expected)`,
catching `ConditionalCheckFailedException` → HTTP 409 "reload and retry", with the audit
trail appended via `audit_log = list_append(if_not_exists(audit_log, :empty), :entry)`.
This is the established stale-read/race protection W3-C1 will mirror for the REQUEST
summary.

**Atomic multi-item writes:** **`TransactWriteItems` is NOT currently used anywhere**
in the backend (only named, as explicitly avoided, in `tenant_read_adapter.py`). It is a
standard DynamoDB API available through the existing `boto3` resource/client with **no
new resource to provision**, BUT the active Lambda DynamoDB IAM policy
(`modules/iam/main.tf`) does **not** currently grant `dynamodb:TransactWriteItems`
(`W3C1_TRANSACTWRITE_IAM_PRESENT=NO`) — so runtime use requires a future owner-approved
IAM policy modification (an existing-role change, not a new resource). See §4.1.

**Audit (`src/backend/common/audit.py`):** `log_action(event, action, target_pk, …)`
derives `user_email`/`user_role` **server-side** from claims and writes an immutable
`AUDIT#` item. W3-C1 reuses this in addition to the immutable PAYMENT_EVENT.

**No payment-status spoofing surface today:** `payment_status` is only ever written
server-side — to `payment_link_sent` (admin checkout route) or `paid`
(`stripe_webhook_handler`). **No route reads `payment_status`/`amount_paid` from the
request body.** `review_handler.py` only *reads* legacy payment status. There is no
generic admin PATCH that whitelists arbitrary REQUEST fields from the body. W3-C1 must
preserve this: the caller never supplies an authoritative status.

**Legacy Plane-A/B conflation (unchanged, noted):** `stripe_client.create_checkout_session`
uses the platform `STRIPE_SECRET_KEY`; `stripe_webhook_handler` sets REQUEST
`payment_status='paid'`. W3-C1 does **not** touch these and does **not** switch runtime
onto the new domain.

---

## 2. Recommended W3-C phase ordering

| Phase | Scope | Explicitly NOT in scope |
|-------|-------|-------------------------|
| **W3-C1** | MANUAL_EXTERNAL backend adapter/service + atomic REQUEST-summary/PAYMENT_EVENT write + owner/admin authorization boundary + comprehensive tests | API route, UI, Stripe |
| **W3-C2** | Narrow owner/admin external-payment mutation API route + RBAC + request/tenant ownership + idempotency/concurrency tests | UI, Stripe |
| **W3-D1** | Admin UI for MANUAL_EXTERNAL operational use + read/display of safe canonical summary | Stripe Connect |
| **W3-D2+ (separate approval)** | Stripe Connect Direct **sandbox** architecture/wiring, per-tenant account config, Plane-B webhook split, hosted payment UI | live keys |

Each phase requires its own explicit authorization. This plan details **W3-C1** and
sketches the **W3-C2** boundary only.

---

## 3. W3-C1 functional contract (recommended)

A narrow, server-only backend service — e.g. `common/manual_external_adapter.py` with:

```
record_external_payment(
    event,                 # the Lambda event; identity/tenant derived server-side
    request_id,            # path/operation input (non-authoritative)
    client_id,             # operation input; validated against REQUEST ownership
    amount_delta_cents,    # canonical minor units (strict; no x100)
    currency,
    idempotency_key,       # caller-supplied, deterministic SK + conditional write
    external_reference=None,        # opaque (e.g. "CHECK-10482")
    payment_method_category=None,   # small enum (see §11)
    note=None,                      # bounded, allowlist-sanitized audit note
) -> { result, previous_status, resulting_status, amount_paid_cents,
       payment_completed_at, booking_ready, booking_ready_reason }
```

**Server-derived (NEVER caller-supplied as authoritative):** `company_id`
(`get_current_company_id`), caller role/actor (`get_effective_role` / claims), REQUEST
ownership, current payment status/amount, the **resulting** payment status, the
`amount_paid_cents` total, `payment_completed_at`, and the actor on the event.

**Caller-supplied (non-authoritative operation inputs only):** `amount_delta_cents`,
`currency`, `idempotency_key`, optional `external_reference`, optional
`payment_method_category`, optional `note`. A caller can **never** submit
`payment_status=PAID` or an arbitrary resulting status.

---

## 4. Payment-write atomicity design

`W3C1_PAYMENT_WRITE_ATOMICITY_DESIGN=DYNAMODB_TRANSACTWRITEITEMS_CONDITIONAL_EVENT_PUT_PLUS_CONDITIONAL_REQUEST_UPDATE`

Recording a payment must update **both** the append-only PAYMENT_EVENT and the REQUEST
summary **all-or-nothing**. Recommended approach:

Use a single **DynamoDB `TransactWriteItems`** containing two conditional operations on
the existing single table:

1. **`Put` the PAYMENT_EVENT** with
   `ConditionExpression = attribute_not_exists(PK) AND attribute_not_exists(SK)`
   (append-only; deterministic `SK=PAYEVENT#{idempotency_key}`; never overwrite).
2. **`Update` the REQUEST summary** (`PK=REQ#{request_id}`, `SK=CLIENT#{client_id}`)
   with an optimistic guard, e.g.
   `ConditionExpression = attribute_exists(PK) AND payment_summary_revision = :expected_rev`
   (or `= expected_status AND amount_paid_cents = expected_paid` if a dedicated revision
   attribute is not added), setting the derived `payment_status`, `amount_paid_cents`,
   `payment_completed_at`, `payment_provider=MANUAL_EXTERNAL`, a bumped
   `payment_summary_revision`, and appending the audit entry.

Because both operations are in one transaction, **either both commit or neither does** —
no half-written state. A `TransactionCanceledException` carries per-item cancellation
reasons that map cleanly to the result contract:

- event-side `ConditionalCheckFailed` → key already exists → classify
  duplicate-vs-conflict by reading the stored event (`DUPLICATE_SAME_EVENT` idempotent
  success, or `CONFLICTING_IDEMPOTENCY_KEY` → 409);
- summary-side `ConditionalCheckFailed` → stale read / concurrent writer / amount race →
  409 "reload and retry" (no partial write);
- both succeed → `CREATED`.

Covers: **idempotency** (deterministic SK + conditional put), **concurrent owner/admin
attempts** (summary revision/status guard), **stale summary status** (guard mismatch →
409), **amount race** (revision guard invalidates a stale computed total), **conflicting
idempotency keys** (semantic-payload comparison), **all-or-nothing** (transaction).

### 4.1 Infrastructure classification (corrected — PR #30 IAM review)

The earlier blanket `W3C1_INFRA_CHANGE_REQUIRED=NO` was imprecise. A confirmed source
review of `modules/iam/main.tf` shows the active Lambda DynamoDB policy
(`${name_prefix}-dynamodb-access`, attached to the `lambda_exec` role, scoped to the
application `data_table_arn` + `/index/*`) grants exactly `dynamodb:GetItem`,
`PutItem`, `UpdateItem`, `DeleteItem`, `Query`, `Scan` — and **does NOT grant
`dynamodb:TransactWriteItems`**. So:

- `W3C1_TRANSACTWRITE_IAM_PRESENT=NO`
- `W3C1_NEW_AWS_RESOURCE_REQUIRED=NO`
- `W3C1_DYNAMODB_SCHEMA_CHANGE_REQUIRED=NO`
- `W3C1_NEW_TABLE_REQUIRED=NO`
- `W3C1_NEW_GSI_REQUIRED=NO`
- `W3C1_NEW_SECRET_REQUIRED=NO`
- `W3C1_NEW_LAMBDA_REQUIRED=NO`
- `W3C1_NEW_API_ROUTE_REQUIRED=NO`
- **`W3C1_RUNTIME_IAM_CHANGE_REQUIRED=YES`**

**Required future IAM action:** add `dynamodb:TransactWriteItems` to the `Action` list of
the existing `${name_prefix}-dynamodb-access` policy for the existing application table.
This is a **modification of an existing role/policy, not a new AWS resource** (one line
in `modules/iam/main.tf`).

**Governance:** Matthew has **not** authorized this IAM/Terraform change in this planning
turn. No Terraform/IAM file is edited here; nothing is applied or deployed.

- `W3C1_IAM_CHANGE_AUTHORIZED=NO`
- `W3C1_TERRAFORM_CHANGE_AUTHORIZED=NO`
- `W3C1_DEPLOYMENT_AUTHORIZED=NO`

**Implementation vs runtime enablement** — two distinct concepts:

- **A. W3-C1 LOCAL IMPLEMENTATION** — the adapter/service code, transaction-orchestration
  code, and tests can be written and run entirely against a **mocked transaction
  client** (as the existing backend tests mock `common.db.table` and the boto3 client).
  No AWS mutation is needed to build or test it.
  `W3C1_LOCAL_CODE_CAN_BE_IMPLEMENTED_WITHOUT_INFRA_MUTATION=YES`.
- **B. W3-C1 RUNTIME ENABLEMENT** — for the code to actually execute against production
  DynamoDB, the Lambda role must possess `dynamodb:TransactWriteItems`, which requires
  the owner-approved IAM/Terraform change above **before** any deployment/use.
  `W3C1_RUNTIME_ENABLEMENT_REQUIRES_IAM_CHANGE=YES`.

The atomicity design is **not** weakened to avoid IAM: REQUEST summary and PAYMENT_EVENT
remain two distinct items that must commit all-or-nothing, so `TransactWriteItems`
remains the recommendation. A two-independent-writes fallback is explicitly **rejected**
(it can leave the event persisted without the summary, or vice versa), and the separate
PAYMENT_EVENT entity is **not** collapsed into an embedded audit list merely to dodge the
IAM grant.

---

## 5. Derived payment-state algorithm

The service reads the canonical current summary and computes the new total; it never
accepts a target status.

```
existing_paid   = canonical_cents(summary.amount_paid_cents)
delta           = canonical_cents(amount_delta_cents)          # > 0 required
new_amount_paid = existing_paid + delta
required        = canonical_cents(summary.amount_required_cents)
deposit         = canonical_cents(summary.deposit_amount_cents)
req             = summary.payment_requirement
prev            = normalize_payment_status(summary.payment_status)
```

Derivation (then validated against the W3-B state machine via `validate_transition`):

- **NONE:** no collection mutation is valid — reject a MANUAL_EXTERNAL settlement for a
  no-payment-required request (nothing to record).
- **DEPOSIT:**
  - `new_amount_paid < deposit` → remains `UNPAID` (or `PAYMENT_LINK_SENT` if already in
    that state) — recorded as `PAYMENT_PARTIALLY_SETTLED` event but **not** enough to
    cross the deposit threshold;
  - `deposit <= new_amount_paid < required` → `PARTIALLY_PAID`;
  - `new_amount_paid >= required` → `PAID`.
- **FULL:**
  - `new_amount_paid < required` → `PARTIALLY_PAID`;
  - `new_amount_paid >= required` → `PAID`.
- **Overpayment** (`new_amount_paid > required`) → **rejected** (W3-B policy; no
  overpayment modeled). `validate_payment_amounts` enforces this before any write.
- The computed transition must satisfy `validate_transition(prev, resulting)`; an illegal
  transition (e.g. `REFUNDED → PAID`) is rejected. A same-status replay is idempotent.

**PAYMENT_LINK_SENT interaction:** MANUAL_EXTERNAL does not create a link, so it normally
operates `UNPAID → PARTIALLY_PAID / PAID`. If a request is already `PAYMENT_LINK_SENT`
(e.g. a link was sent but the client paid by check instead), the W3-B machine already
permits `PAYMENT_LINK_SENT → PARTIALLY_PAID` and `PAYMENT_LINK_SENT → PAID`, so recording
an external payment from that state is valid and requires no new transition. W3-C1 does
**not** require a request to pass through `PAYMENT_LINK_SENT`.

This matches the merged W3-B `_ALLOWED_TRANSITIONS` and `is_booking_payment_ready`
semantics; no state-machine change is needed.

---

## 6. Refund boundary

`W3C1_REFUND_OPERATION_DEFERRED=YES` — refund recording (`REFUNDED`,
`PAYMENT_REFUNDED`) is **deferred** to a later slice. W3-C1 records positive external
settlements only (`UNPAID/PARTIALLY_PAID → PARTIALLY_PAID/PAID`). The `REFUNDED`
vocabulary and its transitions in the W3-B machine are left intact and unweakened; W3-C1
simply does not exercise the refund path. Deferring refunds does not reduce any existing
domain guarantee.

---

## 7. Owner/admin authorization model

`W3C1_EXTERNAL_PAYMENT_AUTHORIZATION_MODEL=OWNER_OR_ADMIN_ONLY_SERVER_DERIVED`

- **Owner and admin only** may record an external settlement — enforced by the existing
  `require_owner_or_admin(event)` (server-derived role from Cognito groups).
- **Staff:** **NOT authorized** by default. No existing requirement grants staff
  payment-settlement authority, so the fail-safe default is deny. (If a future requirement
  explicitly grants it, that is a separate, documented decision.)
- **Client:** **NEVER** authorized. There is no client/self-service payment-confirmation
  path, and none will be added. A browser redirect is never settlement proof.
- Tenant authority is `get_current_company_id(event)`; REQUEST ownership is enforced by
  `load_owned_request(request_id, client_id, company_id)` — fail closed, no write on
  mismatch. A spoofed body `company_id` cannot widen access.

---

## 8. Safe external evidence / reference model

PetCare Hero records **state**, not instrument data. Recommended safe fields on the
PAYMENT_EVENT:

- `external_reference` — **opaque** short string (e.g. `CHECK-10482`, `DEP-2026-14`);
  never a full account/card number.
- `payment_method_category` — a **small fixed enum** (recommended, low cost):
  `CASH | CHECK | BANK_TRANSFER | EXTERNAL_PROCESSOR | OTHER`. This is cheap, improves
  audit quality, and avoids free-text sprawl. (If review prefers to defer, it can start
  as `OTHER`-only; but the 5-value enum is recommended and not over-engineering.)
- `note` — a short owner/admin audit note, passed through the W3-B
  `sanitize_payment_event_metadata` allowlist (bounded length; sensitive-key patterns
  rejected).

**Never stored:** PAN, CVC/CVV, bank account numbers, routing numbers, provider
credentials, raw receipts containing private/payment data, or arbitrary provider
payloads. Enforced by reusing the W3-B metadata sanitizer and keeping
`external_reference` opaque.

---

## 9. Canonical REQUEST summary fields

The adapter updates the canonical W3-B summary fields
(`src/backend/common/payment_domain.py::PAYMENT_SUMMARY_FIELDS`):

- `payment_requirement`
- `payment_status`
- `amount_required_cents`
- `amount_paid_cents`
- `currency`
- `payment_provider` (`MANUAL_EXTERNAL`)
- `payment_completed_at` (set only when the derived status reaches `PAID`)

Plus a new monotonic `payment_summary_revision` guard attribute (optimistic concurrency;
analogous to the existing `quote_revision`).

**Legacy compatibility (read-only):** the current deployed path writes lowercase
`payment_status` (`payment_link_sent`/`paid`) and `payment_amount_cents` /
`payment_requested_by` on the REQUEST. W3-C1 should **normalize reads** via
`normalize_payment_status` and treat the legacy lowercase/`payment_amount_cents` fields
as **read-only compatibility** inputs; it writes the canonical fields. No duplicate
competing field is introduced beyond the revision guard. Whether to also mirror the
canonical status back into the legacy lowercase field for the current UI is a W3-C2/W3-D
display-reconciliation decision, not a W3-C1 concern.

---

## 10. Booking-readiness behavior

After recording, the service MAY recompute `is_booking_payment_ready(...)` and **return
it as informational output only**. W3-C1 MUST NOT: set `APPROVED`, create JOBs, schedule,
assign, notify staff/client, or trigger booking confirmation. This preserves
*quote accepted ≠ payment complete ≠ APPROVED*, consistent with the existing read-only
`evaluate_booking_approval_predicate` usage in the quote-accept path.

---

## 11. Audit model

Each successful external settlement produces **exactly one immutable PAYMENT_EVENT**
(via `build_payment_event`), event type reused from the existing W3-B vocabulary:

- `PAYMENT_SETTLED` when the derived status reaches `PAID`;
- `PAYMENT_PARTIALLY_SETTLED` when it reaches/stays `PARTIALLY_PAID` (or records a
  below-threshold deposit contribution).

No new event/status vocabulary is created. The actor on the PAYMENT_EVENT is
**server-derived** from the authenticated identity.

**Atomicity scope clarification (PR #30 review):** the TransactWriteItems transaction
contains **exactly two items** — the PAYMENT_EVENT `Put` and the REQUEST summary
`Update` — and those two are atomic with each other. The PAYMENT_EVENT is the
**mandatory, authoritative payment audit event** and the canonical payment audit trail;
it carries the server-derived actor, previous/resulting status, amount delta, currency,
and opaque reference. The generic `audit.log_action(...)` `AUDIT#` write is
**supplementary** and is performed **after** the transaction commits successfully — it is
deliberately **outside** the two-item transaction. Consequences made explicit:

- Do **not** claim all three records (PAYMENT_EVENT + REQUEST summary + AUDIT#) are
  atomic. Only the first two are.
- A failure to write the supplementary `AUDIT#` item MUST NOT leave payment state
  ambiguous: the authoritative payment state (summary + PAYMENT_EVENT) is already durably
  and atomically committed, so a missing supplementary `AUDIT#` is a non-fatal logging
  gap (log and continue), never a payment-state inconsistency.
- The transaction is **not** expanded to a third (`AUDIT#`) item in W3-C1 absent a
  concrete requirement; the PAYMENT_EVENT already satisfies the authoritative
  payment-audit need.

---

## 12. W3-C2 API boundary (sketch only — not this slice)

Recommended first mutation route (a **W3-C2** slice, after the adapter is proven):

```
POST /admin/requests/{requestId}/payments/external
```

- Body contains only non-authoritative operation inputs: `amount_delta_cents`,
  `currency`, `idempotency_key`, optional `external_reference`, optional
  `payment_method_category`, optional `note`.
- Server derives tenant, client/request ownership, current status, resulting status,
  `amount_paid` total, `payment_completed_at`, and actor.
- Explicitly **not** `PATCH /request` and **not** `POST /mark-paid` (both invite status
  spoofing). RBAC = owner/admin only.

This route is **W3-C2**, not W3-C1. W3-C1 ships the adapter/service + atomic persistence
+ tests with **no route**.

---

## 13. Stripe Connect boundary

`W3_SELECTED_LONG_TERM_MODEL=PROVIDER_ABSTRACTION + STRIPE_CONNECT_DIRECT_CHARGES`.
Stripe Connect Direct remains **known, non-executable, not started**, requiring separate
explicit authorization (W3-D2+). Marketplace / indirect remains **not selected**. No
Connect/OAuth/account/Checkout/PaymentIntent/webhook design is produced here.

---

## 14. W3-C1 test matrix (planned)

Authorization: owner allowed; admin allowed; staff denied (default); client denied;
no generic client self-confirmation path. Ownership: wrong tenant rejected (no write);
wrong request/client association rejected (no write); missing request rejected (no
write). Amounts: canonical-cents Decimal magnitude preserved (no ×100); full exact →
`PAID`; deposit exact threshold → `PARTIALLY_PAID`; partial below deposit → stays
`UNPAID`; deposit then balance → `PARTIALLY_PAID` then `PAID`; overpayment rejected;
currency mismatch rejected. Idempotency/concurrency: duplicate identical idempotency key
→ `DUPLICATE_SAME_EVENT` (idempotent success); duplicate conflicting key →
`CONFLICTING_IDEMPOTENCY_KEY` (409, not success); concurrent attempts (summary revision
guard) → one wins, other 409; stale status race → 409. Atomicity: event + summary commit
together; no summary write when the event put fails and vice versa; **no write on
authorization failure**; **no write on validation failure**. Invariants: no
auto-approval / no JOB / no schedule / no notify; no Stripe/network imports (AST check,
as in W3-B).

---

## 15. Cost / infrastructure expectation

`W3C1_INCREMENTAL_RESOURCE_COST_EXPECTATION=NEGLIGIBLE_WITHIN_EXISTING_ARCHITECTURE`

W3-C1 as an internal backend service/helper requires **no new AWS service, table, GSI,
secret, Lambda, or API Gateway route**, and uses the existing single DynamoDB table and
the existing `boto3` client. Cost is **negligible, not literally zero**, because:

- there is **no new standalone AWS resource** and the IAM policy update itself carries no
  standalone resource cost;
- DynamoDB **transaction request** pricing (a TransactWriteItems write is billed as 2×
  the write units of the equivalent non-transactional writes) applies **only when the
  operation is actually executed at runtime** — i.e. once W3-C2/W3-D exercise the path on
  real data, not from the W3-C1 code/tests themselves (which use a mocked client);
- the existing application table remains in use with no capacity-model change.

See §4.1 for the precise infrastructure-change classification. The single required future
infra action is the owner-approved `dynamodb:TransactWriteItems` IAM policy addition
(`W3C1_RUNTIME_IAM_CHANGE_REQUIRED=YES`); there is **no new AWS resource**
(`W3C1_NEW_AWS_RESOURCE_REQUIRED=NO`).

---

## 16. Non-goals (W3-C1)

No API route (W3-C2); no UI (W3-D1); no Stripe API/Connect/OAuth/Checkout/PaymentIntent/
webhook/secret; no refunds (deferred); **no Terraform/IAM edit** (the required
`dynamodb:TransactWriteItems` grant is a future, separately-authorized change — §4.1); no
AWS mutation/deploy; no production mutation or production test data; no second tenant; no
tenant-resolution change; no Ryan testing; no scheduling; no mobile distribution; no
auto-approval / booking creation; no runtime switch of the existing Stripe path; no client
payment-confirmation path. W3-C1 local code + tests are built against a **mocked**
transaction client only.

---

## 17. Gates preserved

Latest completed production backend release remains
`PR22_PRIVACY_PRODUCTION_DEPLOYED_VERIFIED`. W1 and W4 remain merged-not-deployed; W3-B is
merged, not deployed. Stripe sandbox-only; no customer money through the USMISSIONHERO
Stripe platform account. `SCHEDULING_WORKSTREAM_STATUS=DRAFT_PR_DELIVERY_CHECKPOINT`;
`SCHEDULING_PR_MERGE_AUTHORIZED=NO`; `RYAN_TESTING_AUTHORIZED=NO`; no second tenant; no
production test data; `W3_C_IMPLEMENTATION_AUTHORIZED=NO`;
`W3C1_IAM_CHANGE_AUTHORIZED=NO`; `W3C1_TERRAFORM_CHANGE_AUTHORIZED=NO`;
`W3C1_DEPLOYMENT_AUTHORIZED=NO`.

**Disposition:** `W3C_MANUAL_EXTERNAL_IMPLEMENTATION_PLAN_HARDENED_READY_FOR_MATTHEW`.
STOP before implementation.
