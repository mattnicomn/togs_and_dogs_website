# PetCare Hero — Workflow / State / Action Contract (OPS-0)

**Status:** PLANNED / CONTRACT — design only. No application, backend, mobile,
Terraform, or runtime code is created or changed by this document.
**Owner:** Matthew
**Program:** PetCare Hero Operational Workflow & Mobile-First Experience (`PCH-OPS`)
**Phase:** OPS-0 — Workflow / State / Action Contract (first implementation gate)
**Created:** 2026-09-30
**Repository checkpoint:** branch `main`, HEAD `ed74516ce7afa46c28a9bb5e6183574384583a19`,
clean tree, index empty, stash empty.
**Parent plan:** `docs/planning/petcare-hero-operational-workflow-mobile-first.md`
**Evidence base:** direct source reads of `src/backend/common/status.py`,
`src/backend/common/cascade.py`, `src/backend/handlers/{review,assignment,job,intake,cancellation,admin}_handler.py`,
`src/backend/common/{google_calendar,client_profile,pet_profile}.py`,
`src/backend/common/notifications/*`, `web/src/components/{AdminDashboard,CareCard,MasterScheduler,ClientPortal,IntakeForm}.jsx`,
`web/src/utils/workflowActions.js`, `mobile/src/screens/RequestDetailScreen.tsx`,
`mobile/src/components/RequestCard.tsx`, `mobile/src/api/client.ts`,
`shared/constants/*.json`.

> This is the authoritative contract OPS-1 and later phases follow so they do not
> guess at workflow behavior. It **documents** current source behavior and the
> **desired** future contract, and records design recommendations. It does **not**
> rename deployed statuses, add new statuses, or implement anything.

---

## 0. Domain boundary (preserved)

```
USMISSIONHERO LLC            (platform operator)
  └── PetCare Hero           (SaaS platform / product)
        └── Tenant / business (e.g. Togs & Dogs — Ryan's individual business)
              └── Client
                    └── Pets
                          └── Service Request / Booking   (REQ#{request_id} / CLIENT#{client_id})
                                └── one or more Visit / JOB (JOB#{job_id} / REQ#{request_id})
                                      └── Visit Updates / Completion
```

**Decision — keep two state machines.** Repository evidence confirms Request/Booking
(`REQ#`) and Visit/JOB (`JOB#`) are already distinct entities with distinct status
enums (`RequestStatus` vs `JobStatus`) and distinct transition tables
(`REQUEST_TRANSITIONS` vs `JOB_TRANSITIONS`) in `src/backend/common/status.py`.
`cascade.py` propagates REQ→JOB one-directionally only. **Do not collapse them.**

---

## 1. Request / Booking state table (authoritative, from source)

Source of truth: `RequestStatus` enum + `REQUEST_TRANSITIONS` in
`src/backend/common/status.py`; `shared/constants/request-statuses.json`
(`customerVisible`, `terminal`, `staffSettable`, synonyms); display in
`web/src/components/ClientPortal.jsx` and `AdminDashboard.jsx`.
Primary transition handler: `review_handler` (`POST /admin/review`).

Legend for coverage: **W**=web supports the action, **M**=mobile supports the
action today.

| State (enum value) | Business meaning | Deployed? | Kind | Customer-visible? | Terminal? | Allowed next state(s) (from `REQUEST_TRANSITIONS`) | Primary action / handler | Roles (traced) | W | M |
|---|---|---|---|---|---|---|---|---|---|---|
| `PENDING_REVIEW` (syn `NEEDS_REVIEW`) | New request/intake awaiting owner review | Yes | active | Yes | No | MEET_GREET_REQUIRED, READY_FOR_APPROVAL, PROFILE_CREATED, QUOTE_NEEDED, QUOTE_SENT, QUOTED, APPROVED, DECLINED, CANCELLED, ARCHIVED, DELETED | review / create-profile / `review_handler` | owner/admin (sensitive); staff limited | W | approve only |
| `PROFILE_CREATED` | Client profile created from intake | Yes | intermediate | No | No | READY_FOR_APPROVAL, MEET_GREET_REQUIRED, QUOTE_NEEDED, QUOTE_SENT, APPROVED, DECLINED, CANCELLED, ARCHIVED | `review_handler('PROFILE_CREATED')` | owner/admin | W | — |
| `MEET_GREET_REQUIRED` (syn `NEEDS_MG`) | M&G needed before approval | Yes | intermediate | No | No | MG_SCHEDULED, MG_COMPLETED, READY_FOR_APPROVAL, QUOTE_NEEDED, DECLINED, CANCELLED, ARCHIVED | `review_handler` / `VERIFY_MEET_GREET` pseudo-status | owner/admin/staff (settable) | W | — |
| `MG_SCHEDULED` | M&G scheduled | Yes | intermediate | No | No | MG_COMPLETED, MEET_GREET_REQUIRED, CANCELLED, ARCHIVED | `review_handler` | owner/admin/staff | W | — |
| `MG_COMPLETED` | M&G done; eligible to advance | Yes | intermediate | No | No | QUOTE_NEEDED, QUOTE_SENT, QUOTED, READY_FOR_APPROVAL, APPROVED, CANCELLED, ARCHIVED | `review_handler` / `VERIFY_MEET_GREET` sets this | owner/admin/staff | W | — |
| `READY_FOR_APPROVAL` (syn `NEW_REQUEST`) | Ready for owner approval | Yes | intermediate | No | No | APPROVED, QUOTE_NEEDED, QUOTE_SENT, QUOTED, DECLINED, ARCHIVED | `review_handler` | owner/admin | W | — |
| `QUOTE_NEEDED` | A quote must be prepared | Yes | intermediate | No | No | QUOTE_SENT, QUOTED, APPROVED, READY_FOR_APPROVAL, DECLINED, CANCELLED, ARCHIVED | CareCard quote fields + `review_handler` | owner/admin | W | — |
| `QUOTE_SENT` (syn `QUOTED`) | Quote sent to client | Yes | intermediate | Yes | No | APPROVED, QUOTE_NEEDED (revision), DECLINED, CANCELLED, ARCHIVED | CareCard + `review_handler` | owner/admin | W | — |
| `APPROVED` (syn `BOOKED`) | Owner approved; job creation triggered | Yes | active | Yes | No | ASSIGNED, CANCELLATION_REQUESTED, CANCELLATION_DENIED, ARCHIVED, CANCELLED | `review_handler('APPROVED')` → async `job_handler` | owner/admin | W | **M** |
| `ASSIGNED` (syn `JOB_CREATED`, `SCHEDULED`) | Worker assigned to the booking/jobs | Yes | active | Yes | No | APPROVED (rollback), COMPLETED, ARCHIVED, CANCELLED, CANCELLATION_REQUESTED, CANCELLATION_DENIED | `assignment_handler` (`POST /admin/assign`) | owner/admin **only** | W | **M** |
| `DECLINED` | Request declined by owner | Yes | terminal | Yes | **Yes** | ARCHIVED, QUOTED, PENDING_REVIEW (reopen) | `review_handler('DECLINED')` | owner/admin | W | — |
| `CANCELLATION_REQUESTED` | Client requested cancellation | Yes | intermediate | Yes | No | CANCELLED, CANCELLATION_DENIED, ARCHIVED | `POST /client/cancel` (`cancellation_handler`) | client (request); owner/admin (decide) | W (client) | — |
| `CANCELLATION_DENIED` | Owner denied cancellation | Yes | intermediate | Yes | No | ARCHIVED, CANCELLED | `PUT /admin/cancel/decision` DENY | owner/admin | W | — |
| `CANCELLED` | Booking cancelled | Yes | terminal | Yes | **Yes** | ARCHIVED, PENDING_REVIEW, QUOTED, APPROVED (reopen) | `PUT /admin/cancel/decision` APPROVE | owner/admin | W | — |
| `COMPLETED` | All visits completed (rollup) | Yes | terminal | Yes | **Yes** | ARCHIVED, ASSIGNED, APPROVED (reopen) | auto-rollup in `job/complete`; `review_handler('COMPLETED')` | owner/admin/staff | — | staff complete (per build) |
| `ARCHIVED` | Removed from active views, retained | Yes | terminal | No | **Yes** | PENDING_REVIEW, DELETED | `performAdminAction('ARCHIVE')` | owner/admin | W | — |
| `DELETED` | Soft-deleted (pre-purge) | Yes | terminal | No | **Yes** | PENDING_REVIEW | `performAdminAction('DELETE')` / `PURGE` | owner/admin | W | — |

Notes:
- `is_valid_transition` additionally allows `ARCHIVED`/`DELETED` from **any** state,
  and treats same-status transitions as idempotent.
- "Customer-visible" is taken from `request-statuses.json` `customerVisible`.
- No `IN_PROGRESS` exists in `RequestStatus` (see §2 and §5).

---

## 2. Visit / JOB state table (authoritative, from source)

Source of truth: `JobStatus` enum + `JOB_TRANSITIONS` in `status.py`; execution
handlers in `admin_handler.py` (`/admin/job/start`, `/admin/job/complete`);
creation in `job_handler.py`; assignment in `assignment_handler.py`.

| State (enum / field) | Business meaning | How represented in source | Allowed next (from `JOB_TRANSITIONS`) | Set by |
|---|---|---|---|---|
| `JOB_CREATED` (syn `APPROVED`) | Visit created from approved request | `job_handler` writes `status=JOB_CREATED` | ASSIGNED, CANCELLED, ARCHIVED | `job_handler` (async after `APPROVED`) |
| `ASSIGNED` | Worker assigned to this visit | `assignment_handler` sets `status=ASSIGNED` + `worker_id` | ASSIGNED (reassign), JOB_CREATED (rollback), COMPLETED, CANCELLED, ARCHIVED | `POST /admin/assign` |
| **started** (not a separate enum) | Visit physically started / in progress | `started_at` + `started_by` fields set on the JOB; **status stays `ASSIGNED`** | — (remains ASSIGNED until completed) | `POST /admin/job/start` |
| `COMPLETED` | Visit completed | `status=COMPLETED` + `completed_at`/`completed_by` | ASSIGNED (reopen), JOB_CREATED (reopen), ARCHIVED | `POST /admin/job/complete` |
| `CANCELLED` | Visit cancelled | `status=CANCELLED` via cascade from REQ | JOB_CREATED (reopen), ARCHIVED | `cascade.py` from REQ cancel |
| `ARCHIVED` | Archived visit | `status=ARCHIVED` | DELETED | cascade / admin |
| `DELETED` | Soft-deleted visit | `status=DELETED` | (none) | admin |

Key source facts:
- **"In progress" is represented today by a JOB having `started_at` set, while its
  `status` remains `ASSIGNED`.** `/admin/job/start` requires current status
  `ASSIGNED`, writes `started_at`/`started_by` via a conditional expression
  (`attribute_not_exists(started_at) AND #stat = :assigned`) for idempotency, and
  does **not** change `status` and does **not** touch the calendar or notifications.
- `/admin/job/complete` accepts current status in
  `{ASSIGNED, JOB_CREATED, SCHEDULED, PENDING}`, sets `COMPLETED` + `completed_at`,
  stores optional `visit_notes` (≤500 chars), and performs **parent auto-rollup**:
  the parent `REQ#` only becomes `COMPLETED` when **all** child job IDs are
  `COMPLETED`; otherwise it updates `completed_job_ids`/`completed_count` and leaves
  the parent active.
- Completion does **not** delete the calendar event (completed events retained).

### 2.1 `IN_PROGRESS` recommendation (DESIGN DECISION)

**Recommendation: model `IN_PROGRESS` as a Visit/JOB concept, NOT a `RequestStatus`.**
Evidence: physical execution is already a JOB-level concern (`started_at` on the
JOB; the request status stays `ASSIGNED`; the parent only rolls up to `COMPLETED`
when all children finish). A booking with multiple visits cannot have a single
coherent request-level "in progress" value when occurrences start/finish
independently.

Two acceptable implementation options for a **later** phase (OPS-4 / status-model
work), to be chosen then — **not implemented now:**
- **Option A (preferred, lowest-disruption):** keep JOB `status=ASSIGNED` and treat
  presence of `started_at` as the canonical "in progress" signal; add a derived
  display label only. No new enum value; no migration.
- **Option B:** add a first-class `JobStatus.IN_PROGRESS` with transitions
  `ASSIGNED → IN_PROGRESS → COMPLETED`, updating `JOB_TRANSITIONS`, the shared
  contract, and the start handler. Higher blast radius; requires backward-compat
  with existing `started_at`-only records.

**Do NOT add `IN_PROGRESS` to `RequestStatus`.** Do not implement either option in
OPS-0.

---

## 3. `NEEDS_CLIENT_INFO` recommendation (DESIGN DECISION)

Desired workflow: "Ryan needs more information from the client" before he can
proceed. No equivalent state or flag exists in source today.

**Recommendation: a Request-level status is the cleanest fit, but confirm need at
OPS-2 before adding it.** Options, in order of preference:
1. **Existing status + flag (lowest disruption):** keep `PENDING_REVIEW` and add a
   non-enum flag (e.g. `info_requested_at` / `info_request_note`) plus a
   customer-visible message. No transition-table change; reversible; no migration.
   This mirrors how `started_at` already models an operational sub-state without a
   new enum.
2. **New explicit `RequestStatus.NEEDS_CLIENT_INFO`:** clearer lifecycle visibility
   and client-portal messaging, but requires enum + `REQUEST_TRANSITIONS` +
   `shared/constants/request-statuses.json` changes and backward-compat handling.

**Decision for OPS-0:** recommend **Option 1 (flag on `PENDING_REVIEW`)** unless
OPS-2 UX review proves a distinct client-facing lifecycle state is required, in
which case escalate to Option 2 under the status-model phase. **Do not implement
either in OPS-0.** Do not rename deployed statuses.

---

## 4. Action / role matrix (authoritative, RBAC traced from backend)

Roles traced from `src/backend/common/auth.py` (`get_effective_role`,
`require_owner_or_admin`, `require_client_booking_access`) and per-handler checks —
**not** inferred from visible buttons. `W`=web control exists; `M`=mobile control
exists today.

| State → | Action | API / handler | Backend role enforced | → Next | Owner (R/V) | W | M | Calendar effect | Notification | Client-visible | Internal-only |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PENDING_REVIEW | Create profile | `review_handler('PROFILE_CREATED')` | owner/admin | PROFILE_CREATED | Request | ✓ | — | none | none | status copy | audit |
| PENDING_REVIEW / MG | Verify M&G | `review_handler` `VERIFY_MEET_GREET` | owner/admin/staff* | MG_COMPLETED | Request | ✓ | — | none | none | no | audit |
| MG_COMPLETED / QUOTE_* | Set/send quote | CareCard fields + `review_handler('QUOTE_SENT')` | owner/admin | QUOTE_SENT | Request | ✓ | — | none | (future) | quote msg | quote_amount |
| PENDING…/QUOTE_SENT | Approve | `review_handler('APPROVED')` | owner/admin | APPROVED (+async JOB create) | Request | ✓ | **✓** | create (single-day) / child jobs sync own | `CUSTOMER_APPROVED` | yes | audit |
| any reviewable | Decline | `review_handler('DECLINED')` | owner/admin | DECLINED | Request | ✓ | — | delete if event exists | (no rejection email today) | yes | reason/note |
| APPROVED/ASSIGNED | Assign / reassign | `assignment_handler` (`/admin/assign`) | **owner/admin only** | ASSIGNED | Visit (cascade) | ✓ | **✓** | create/update same event (worker in desc) | `STAFF_ASSIGNED` + `VISIT_SCHEDULED` | sched msg | worker_id |
| ASSIGNED (started not set) | Start visit | `/admin/job/start` | owner/admin/staff (staff = assigned worker) | ASSIGNED + `started_at` | Visit | — | **✓** (per build) | none | none | (future update) | started_by |
| ASSIGNED/started | Complete visit | `/admin/job/complete` | owner/admin/staff (staff = assigned worker) | JOB COMPLETED → parent rollup | Visit → Request | — | **✓** (per build) | **retain** event | (future) | completion/notes | visit_notes |
| APPROVED/ASSIGNED | Client request cancel | `/client/cancel` | client (own booking) | CANCELLATION_REQUESTED | Request | ✓ | — | none yet | (future) | status | reason |
| CANCELLATION_REQUESTED | Decide cancel | `/admin/cancel/decision` | owner/admin | CANCELLED / CANCELLATION_DENIED | Request (cascade) | ✓ | — | delete events (on approve) | `VISIT_CANCELLED` + worker SNS | status | note |
| terminal | Archive / Delete / Purge | `performAdminAction` | owner/admin | ARCHIVED / DELETED | Request+Visit | ✓ | — | n/a | none | no | audit |
| (any) | Platform operator mgmt | `/platform/*` | `platform_admin` only | tenant metadata | Tenant (control plane) | ✓ | — | n/a | n/a | n/a | audit |

\* `MEET_GREET_REQUIRED`/`MG_*` are `staffSettable` in the contract; the sensitive
transitions (`APPROVED`, `DECLINED`, `CANCELLED`, `ARCHIVED`, `DELETED`) require
owner/admin in `review_handler`.

**Platform operator (`platform_admin`)** acts only on the control plane
(`/platform/*`), never on tenant request/visit lifecycle actions.

---

## 5. Mobile action coverage (reconciled from source)

Mobile surfaces: `mobile/src/components/RequestCard.tsx` (list),
`mobile/src/screens/RequestDetailScreen.tsx` (detail),
`mobile/src/api/client.ts` (API client).

API client already wires: `reviewRequest`, `assignWorker`, `completeJob`,
`startJob`, `getAdminRequests`, `getAdminRequest`, plus client/intake calls.

| Action | Category | Evidence |
|---|---|---|
| Approve | **A** (backend + API client + mobile UI) | `RequestDetailScreen.handleApprove`, `RequestCard` approve button |
| Assign / change staff | **A** | `handleConfirmAssignment` + `StaffPickerSheet` → `/admin/assign` |
| Start visit | **C** (partial) | `handleStart`/`startJob` + occurrence-safe `resolveActionJobId` exist in source; per continuity **not in current internal builds** → `UNKNOWN / NEEDS VALIDATION` against a live build |
| Complete visit | **C** (partial) | `handleMarkCompleted`/`completeJob` present in source; same build caveat |
| Decline | **B** (backend + API client via `reviewRequest`, no mobile UI) | `reviewRequest` exists; no Decline control renders |
| Verify / schedule M&G | **B** | `/admin/review` supports it; no mobile control |
| Set / send quote | **B/D** | status transition exists (B); price-entry UX absent from mobile (D) |
| Cancel-approval / cancellation decision | **B** | `/admin/cancel/decision` exists; no mobile control |
| Request more info | **D** (not implemented anywhere) | no state/flag/UX exists |
| Intermediate-status visibility | **B** | list filters are Pending/Approved/Assigned/All/Completed/Cancelled only |
| Client-visible vs internal notes | **E** (needs redesign) | single `visit_notes` field only |
| Visit photo capture | **D** | none |
| Client cancellation from history | **B/D** | `/client/cancel` exists (B); no mobile client UI (D) |

### 5.1 RequestCard vs RequestDetailScreen gating — authoritative source

**Discrepancy (confirmed in source):**
- `RequestDetailScreen` gates the action footer by role:
  `showFooter = (role !== 'staff' && (isPending || isApproved || isAssigned)) || (role === 'staff' && isAssigned)`,
  and gates Start/Complete to staff who are the assigned worker.
- `RequestCard` renders Approve / Assign / Change **without any client-side role
  gating.**

**Authoritative resolution for OPS-1/OPS-2:** the **backend RBAC is authoritative**
(assignment is owner/admin only; sensitive review transitions are owner/admin;
staff start/complete require assigned-worker match). Client-side gating must
**match backend RBAC**, so **`RequestDetailScreen`'s role-aware pattern is the
model to follow**, and `RequestCard` must be reconciled to it. This is recorded as
an **OPS-1 validation item** (reconcile `RequestCard` gating); **do not fix in
OPS-0.** Client-side gating is UX-only; the backend remains the security boundary
regardless.

---

## 6. Quote / client-confirmation contract

Desired: owner approves intent → quote/price → client review → client accept/cancel
→ confirmed operational booking → assignment/scheduling.

Current source support:
- Quote fields (`quote_amount`, `payment_status`, `QUOTE_SENT` status) and
  Stripe-sandbox payment-link generation/send exist on web CareCard.
- There is **no in-portal client "Accept Quote" action**; acceptance is implicit via
  the emailed Stripe link. There is **no explicit `AWAITING_CLIENT_CONFIRMATION` →
  `CONFIRMED` gate** before staff are treated as committed.
- `review_handler` blocks `APPROVED` if a quote exists and `payment_status` is not
  in {Accepted, Deposit Paid, Paid in Full}, and if M&G is required but not
  completed — i.e. a backend gate already exists, surfaced today only on web.

Least-disruptive future model (design only):
- **Tentative assignment** is allowed in `APPROVED`/`ASSIGNED` but should be labeled
  *tentative* in UX until client confirmation where a quote is in play.
- **A booking is "truly confirmed"** when the client has accepted the quote
  (map to existing `QUOTE_SENT`→`APPROVED` with an explicit acceptance signal, or a
  future `CONFIRMED` sub-state — decide in OPS-3, do not add now).
- **Calendar creation** already happens at `APPROVED`/`ASSIGNED` (single-day parent)
  or per child job; keep this, but for quote-gated bookings prefer creating the
  authoritative event at confirmation/assignment, not before client acceptance.
- **Client cancels before confirmation:** request returns to a non-committed state
  (e.g. `CANCELLED` or back to `QUOTE_SENT`), no staff commitment, any tentative
  calendar hold removed.
- **After confirmation:** normal assignment → visits → start → complete applies.

No payment integration work in OPS-0; Stripe remains sandbox-only.

---

## 7. Cancellation contract (by stage)

Normal cancellation **preserves history** (soft state change + retained
`audit_log`); hard delete (`PURGE`) is a separate, typed-confirmation admin action,
never the normal path.

| Stage | Allowed actor | Resulting state | Archival | Calendar | Notification | Staff impact |
|---|---|---|---|---|---|---|
| Pending request | owner/admin (decline); client (withdraw via cancel) | DECLINED / CANCELLED | retained; archivable | none (usually no event yet) | (rejection email missing today) | none |
| Approved / quoted | client requests → owner decides | CANCELLATION_REQUESTED → CANCELLED/DENIED | retained | delete event(s) on approve | `VISIT_CANCELLED` + worker SNS | worker alerted |
| Confirmed booking | client requests → owner decides | same as above | retained | delete parent+child events (de-duped) | `VISIT_CANCELLED` | worker alerted |
| Scheduled visit (ASSIGNED) | owner/admin decision | CANCELLED (cascade to JOBs) | retained | delete each visit event | `VISIT_CANCELLED` | worker alerted |
| In-progress visit (`started_at` set) | owner/admin | **policy decision — not in source today** | retain started record | retain/clean per decision | future | worker alerted |
| Completed visit | not cancellable | COMPLETED (terminal) | archivable | **retain** completed event | none | none |

- Backend: `cancellation_handler` — client `POST /client/cancel` →
  `CANCELLATION_REQUESTED`; `PUT /admin/cancel/decision` APPROVE → `CANCELLED`,
  DENY → `CANCELLATION_DENIED`; `cascade.py` maps `CANCELLATION_DENIED → ASSIGNED`
  and preserves `COMPLETED` jobs.
- **Open item:** cancelling an **in-progress** visit has no explicit source policy;
  OPS-0 flags it for a decision (recommend: allow owner/admin cancel, retain the
  started record for history, notify worker).

---

## 8. Calendar side-effect contract

**PetCare Hero (DynamoDB) is the source of truth. Google Calendar is a projection.**
Source: `src/backend/common/google_calendar.py`.

| Transition | Calendar side effect |
|---|---|
| APPROVED (single-day) | **create** event; persist `google_event_id` |
| APPROVED (multi-day / CHECK_IN / WALK_20 / OVERNIGHT fixed) | parent sync suppressed; **each child JOB creates its own** event |
| ASSIGNED / reassigned | **update in place** the existing event (reuse `google_event_id`; worker name written into description) |
| Start visit | **no-op** (no calendar write) |
| Complete visit | **retain** event (completed events are explicitly kept as history) |
| Cancel (approved) | **delete / remove** event(s) across parent + child jobs, de-duplicated; 404/410 treated as already-gone; `google_event_id` removed from records |
| Decline (with event) | delete event if one exists |

Per-tenant Google token binding is enforced via `TENANT#{id}` `calendar_secret_ref`
with strict Secrets Manager ownership validation. Service-type color support exists.
**Policy:** completed visits remain as historical calendar events unless a later
design decision changes it. No OAuth/calendar mutation in OPS-0.

---

## 9. Notification contract

Source: `src/backend/common/notifications/service.py` (`notify_event`), Postmark
provider, per-tenant ledger/quota.

| Transition | Intended recipient(s) | Status today |
|---|---|---|
| Intake received | tenant owner/admin | **exists** (`REQUEST_RECEIVED`, CUSTOMER_INTAKE) |
| Approved | client | **exists** (`CUSTOMER_APPROVED`) |
| Assigned | assigned staff | **exists** (`STAFF_ASSIGNED`) |
| Scheduled | client | **exists** (`VISIT_SCHEDULED`) |
| Visit cancelled | client + staff + admin | **exists** (`VISIT_CANCELLED`) + worker SNS |
| Visit time changed | client | **exists** (`VISIT_TIME_CHANGED`) |
| Payment link | client | **exists** (`PAYMENT_LINK_EMAIL`, sandbox) |
| Welcome / invite | client/staff | **exists** (`WELCOME_INVITE_*`) |
| **Declined / rejected** | client | **MISSING** — no rejection event/template |
| **Visit started / completed update** | client | **MISSING / FUTURE** |
| Push notifications (any) | any | **MISSING** — Expo tokens registered (`device_handler`) but `notify_event` only emails |
| Per-tenant branded templates | all | **MISSING / FUTURE** — templates hard-coded Togs & Dogs (multi-tenant gap; PTM/brand track) |

Platform operator is not a routine notification recipient for tenant lifecycle
events. No notification implementation in OPS-0.

---

## 10. Client-visible vs internal data (privacy contract)

Today the split is **by field/status, not a per-note toggle**: web CareCard has an
"Internal Admin Notes" tab (`admin_notes`); `visit_notes` is customer-facing;
`request-statuses.json` carries `customerVisible`; `sanitize_pet_for_client` /
`sanitize_booking_for_role` redact internal fields. **Mobile has only a single
`visit_notes` field.**

Future data-visibility contract (design only — no schema change in OPS-0):

| Data item | Visibility | Owner | Contract |
|---|---|---|---|
| Client-visible visit update | client + staff + owner | Visit | explicit `client_visible_update` field; shown in client portal |
| Internal staff note | staff + owner/admin only | Visit | explicit `internal_note` field; **never** returned to client (enforced server-side via sanitizer) |
| Photo | default internal; promote-to-client per photo | Visit | per-item visibility flag; default internal to avoid accidental disclosure |
| Completion note | client-visible by default | Visit | map current `visit_notes` → client-visible completion update |
| Care note (feeding/med/behavior) | staff + owner; subset client-editable | Pet | existing `sanitize_pet_for_client` allowlist governs client exposure |
| Operational alert (e.g. cancellation) | role-targeted | Request/Visit | routed by `notify_event`; never leak internal notes |

**Rule:** default new free-text to **internal**; require explicit action to make
content client-visible. Enforce on the **server** (sanitizer), not just the UI.

---

## 11. Payment ownership

Two distinct relationships (preserved; already separate in code):
- **A. SaaS billing — tenant business → USMISSIONHERO.** Tier limits
  (`tenant_catalog`), subscription webhooks updating `TENANT#` metadata, billing
  ledger.
- **B. Tenant customer payment — client → tenant.** `stripe_client.create_checkout_session`
  (card only); webhook `payment_type=booking` sets `payment_status=paid` on `REQ#`;
  admin generates/sends the link from CareCard.

Payment-aware request states (relationship B): `QUOTE_NEEDED`, `QUOTE_SENT`/`QUOTED`,
and `APPROVED` (approval is gated on quote acceptance when a quote exists).
`PENDING_REVIEW`, M&G states, Visit/JOB states, and terminal states are **not**
payment-aware. **Stripe remains sandbox-only.** No payment implementation in OPS-0.

---

## 12. Multi-visit / multi-day contract (from source)

Source: `job_handler.py` (expansion), `assignment_handler.py` (cascade),
`admin_handler.py` (`job/complete` rollup), `cascade.py`.

- **Expansion:** a Request/Booking may generate multiple Visit/JOB records.
  Multi-day ranges, CHECK_IN visits/day, WALK_20 windows, and OVERNIGHT fixed
  schedules expand into deterministic child JOBs with stable `uuid5` identities and
  per-child calendar events (`job_handler`). Idempotent via `pet_ids`/existing jobs.
- **Assignment:** assigning the parent request cascades to **all** child job IDs
  (`assignment_handler` resolves `parent → job_ids`); assigning a specific job
  targets that one. Reassignment updates each affected visit's own calendar event.
- **Start/complete per occurrence:** each JOB starts (`started_at`) and completes
  (`COMPLETED`) **independently**. Occurrence-safe resolution exists in mobile
  source (`resolveActionJobId`) so the correct child is acted on.
- **Rollup:** completing one occurrence updates the parent's `completed_job_ids` /
  `completed_count`; the parent `REQ#` becomes `COMPLETED` **only when all child
  jobs are COMPLETED** (auto-rollup in `/admin/job/complete`).
- **Cancellation:** cancelling the parent cascades `CANCELLED` to child jobs
  (preserving any already `COMPLETED` ones) and removes each child's calendar event.
- **Calendar mapping:** one calendar event per child visit for multi-occurrence
  bookings; single-day bookings use one parent event.

This behavior is the evidence base; OPS-1 must honor occurrence-level identity for
Start/Complete and must not complete a parent while child visits remain active.

---

## 13. Terminal state & archive semantics

- **Terminal lifecycle states:** `DECLINED`, `CANCELLED`, `COMPLETED` (per
  `request-statuses.json` `terminal: true`).
- **`ARCHIVED` is primarily a visibility/storage state, overloaded with lifecycle
  today:** it is reachable from any state (`is_valid_transition` special-case),
  removes records from active views, is **not** customer-visible, and is reversible
  (`ARCHIVED → PENDING_REVIEW`). `DELETED` is a soft-delete precursor to `PURGE`.
- **Contract decision:** treat `ARCHIVED` as a **visibility/retention** state layered
  over a completed/declined/cancelled lifecycle, **not** a distinct workflow
  outcome. Business history is **retained**; normal cancellation never hard-deletes.
  Avoid introducing new lifecycle meaning into `ARCHIVED`. Do not change semantics
  in OPS-0.

---

## 14. Exact OPS-1 scope — Mobile Visit Operations MVP

**Goal:** a staff/owner can run a scheduled visit end-to-end from the phone.

In scope (states/actions/screens):
- **States/actions:** JOB `ASSIGNED` → Start (`started_at`) → Complete
  (`COMPLETED`) → parent rollup; occurrence-safe selection for multi-visit bookings.
- **Screens:** Today/Upcoming visit list; Visit Detail (client, address→maps,
  phone, pets, feeding/medication/behavior notes, emergency, vet, access/care
  instructions); Start Visit control; in-progress indicator (driven by `started_at`
  per §2.1 Option A — no new enum); Complete Visit with completion note; completion
  history.
- **APIs (existing, reused):** `GET /admin/requests`, `GET /admin/requests/{id}`,
  `POST /admin/job/start`, `POST /admin/job/complete`.
- **Reconcile:** align `RequestCard` client-side gating with `RequestDetailScreen` /
  backend RBAC (validation item from §5.1).
- **Build validation:** confirm occurrence-safe Start/Complete (E3B/E3B.1 source) is
  actually present in the shipped build (resolves the `UNKNOWN / NEEDS VALIDATION`).

Out of scope for OPS-1: request-processing actions (decline/quote/M&G), client-side
quote acceptance, notes-model redesign, any new status.

## 15. Exact OPS-2 scope — Mobile Request Processing

**Goal:** an owner/admin can process a request through its lifecycle from the phone,
using transitions that already exist in the deployed backend.

In scope (states/actions/screens):
- **States/actions (category-A/B — reuse existing `/admin/review`, `/admin/assign`,
  `/admin/cancel/decision`):** Decline; meet-and-greet verify/schedule; set/send
  quote (price entry UX); approve (already present); assignment/reassignment
  (present); cancellation decision; intermediate-status visibility (list filters +
  per-state primary action).
- **Guided-action model:** status-driven "primary next action per state," mirroring
  the semantics of web `web/src/utils/workflowActions.js`.
- **Error UX:** gracefully handle backend 400 gates (M&G-not-complete,
  quote-not-accepted) with an in-app resolution path, instead of raw errors.
- **Depends on OPS-0 decisions:** any "request more info" behavior requires the
  §3 `NEEDS_CLIENT_INFO` decision first; it is **not** assumed to exist.

Out of scope for OPS-2: new deployed statuses (unless escalated per §3), payment
integrations, per-tenant branded notifications, push delivery, tenant auto-routing
(PTM/DOMAIN track), client-portal quote acceptance (OPS-3).

---

## 16. Unresolved questions / blockers

1. **In-progress model (OPS-4 decision):** Option A (`started_at` signal, no new
   enum) vs Option B (`JobStatus.IN_PROGRESS`). Recommendation: A. Needs Matthew/
   design sign-off before any status work. *Not blocking OPS-0/OPS-1.*
2. **`NEEDS_CLIENT_INFO` (OPS-2 decision):** flag-on-`PENDING_REVIEW` vs new status.
   Recommendation: flag. Needs OPS-2 UX confirmation. *Not blocking OPS-0.*
3. **Quote-confirmation gate (OPS-3 decision):** whether to add an explicit
   `CONFIRMED` / client-acceptance signal before staff commitment, and whether
   calendar creation should move to confirmation time for quote-gated bookings.
4. **In-progress cancellation policy:** no source policy for cancelling a visit that
   has `started_at`; needs a decision (recommend allow owner/admin, retain record,
   notify worker).
5. **Current-build validation of Start/Complete:** E3B/E3B.1 are in source but
   per continuity not confirmed in the current internal builds — `UNKNOWN / NEEDS
   VALIDATION` until a build is independently verified. Affects OPS-1 sizing.
6. **RequestCard vs RequestDetailScreen gating:** backend RBAC is authoritative;
   reconcile client-side gating in OPS-1 (recorded, not fixed).

None of these block producing a trustworthy OPS-0 contract; each is a scoped design
decision for its named later phase.

---

## Disposition

**PETCARE_HERO_OPS0_WORKFLOW_CONTRACT_READY_FOR_REVIEW**

Source evidence is sufficient to produce an implementation-ready contract for all
required OPS-0 outputs. The two status questions (`IN_PROGRESS`, `NEEDS_CLIENT_INFO`)
are resolved as **recommendations with explicit deferral**, not implemented
decisions, consistent with the no-code / no-rename constraint.
