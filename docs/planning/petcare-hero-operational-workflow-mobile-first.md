# PetCare Hero — Operational Workflow & Mobile-First Experience

**Status:** PLANNED (program/discovery definition only — no implementation has occurred)
**Owner:** Matthew
**Priority:** P1 — operational usability (Ryan's daily mobile field work)
**Created:** 2026-09-30
**Type:** DOCUMENTATION / PLANNING ONLY
**Program ID:** `PCH-OPS` (PetCare Hero Operational Workflow)
**Repository state at authoring:** branch `main`, HEAD `9cd693d179d2192c3a70d95686d71af9a99dc8c7`, clean working tree, in sync with `origin/main`, no stash.
**Prior disposition:** `PETCARE_HERO_OPERATIONAL_WORKFLOW_DISCOVERY_COMPLETE`

> This document preserves the read-only discovery/gap analysis performed for the
> PetCare Hero operational-workflow program. Creating it is planning, not a
> software release. No frontend, backend, mobile, infrastructure, tenant, Stripe,
> or production change has been made. Every phase below is
> PLANNED / APPROVAL-REQUIRED.

---

## 0. How this relates to existing work (read first)

`PCH-OPS` is the operational-usability companion to the broader
PetCare Hero program. It does **not** fork or re-specify existing engineering
tracks; it cross-references them:

- Brand / platform-experience master tracker — `docs/backlog/petcare-hero-brand-platform-experience.md` (`PCH-A..PCH-R`)
- SaaS maturity / multi-business readiness — `docs/backlog/saas-maturity-and-multi-business-owner-readiness.md`
- Platform Tenant Management Control Plane — `docs/planning/platform-tenant-management-control-plane.md` (PTM-0..PTM-13)
- Tenant access / client onboarding / mobile ops alignment — `docs/planning/tenant-access-client-onboarding-operational-workflow-alignment.md` (DOMAIN-1..7)
- Tenant-aware mobile presentation — `docs/planning/tenant-aware-mobile-presentation-architecture.md`
- Cross-platform design system — `docs/planning/phase-24a-cross-platform-design-system-and-mobile-workflow-alignment.md`
- Ryan cross-platform services/scheduling/workflow alignment — `docs/planning/ryan-cross-platform-services-scheduling-workflow-alignment.md`

Where a requirement is already tracked (PTM, DOMAIN, Phase 24A, Ryan slices, SaaS
backlog), `PCH-OPS` references it rather than creating a competing item.

---

## Program

**PetCare Hero Operational Workflow & Mobile-First Experience.**

Consolidates the mobile-usability and end-to-end workflow-correctness findings
into one first-class program whose acceptance model is
*backend + web + mobile + end-to-end business workflow*.

---

## Product objective

A pet-care owner or staff member (today: Ryan, Togs & Dogs) should be able to run
ordinary day-to-day pet-sitting operations from the **mobile application** without
needing the desktop web app. Mobile is a first-class execution surface, not a
read-only companion.

---

## Core domain model

```
Tenant
  └── Client
        └── Pets
              └── Service Request / Booking        (REQ#{request_id} / CLIENT#{client_id})
                    └── Visit / JOB                (JOB#{job_id} / REQ#{request_id})
                          └── Visit Updates / Completion
```

The existing **Request/Booking (`REQ#`) ↔ Visit/JOB (`JOB#`) separation is correct
and must be preserved** unless later evidence proves redesign is necessary.
`job_handler` already expands multi-day ranges, CHECK_IN visits/day, WALK_20
windows, and OVERNIGHT into deterministic child JOBs (uuid5) with per-child
calendar events; `cascade.py` propagates REQ→JOB one-directionally and preserves
`COMPLETED`. The recommended direction is to **enrich the Visit record**, not to
restructure the model.

Status authority: `src/backend/common/status.py`
(`RequestStatus`, `JobStatus`, `REQUEST_TRANSITIONS`, `JOB_TRANSITIONS`,
`is_valid_transition`, `determine_workflow_type`). Workflow types:
`CUSTOMER_INTAKE` and `VISIT_BOOKING`.

---

## Workflow 1 — New-client acquisition / onboarding

```
Prospect → application → review → approve/reject → invitation
         → onboarding / meet-and-greet → profile/pets → active client
```

Current reality (classification per step):

| Step | Web | Mobile | Backend | Classification |
|---|---|---|---|---|
| Discover provider / select Togs & Dogs tenant | — | — | — | **MISSING** |
| Prospect submits request to become a client | `IntakeForm` `/book` → `POST /requests` | `IntakeScreen` | `intake_handler` writes `REQ#` `PENDING_REVIEW`, `CUSTOMER_INTAKE` | **PARTIAL** (prospect = a `REQ#`, no distinct lead entity) |
| Provide contact + reason + preliminary pet info | ✅ | ✅ | ✅ | **WORKS** |
| Application appears on owner dashboard | admin queue + MasterScheduler intake queue | RequestList (Pending) | `GET /admin/requests` | **WEB_ONLY** (rich) / mobile PARTIAL |
| Owner reviews and accepts/rejects | approve/decline + M&G verify + create-profile | approve only | `review_handler` (current transition set) | **WEB_ONLY** |
| Approved → branded approval notification | `notify_event('CUSTOMER_APPROVED')` | (server) | Postmark template | **PARTIAL** (template hard-coded Togs & Dogs) |
| Meet-and-greet scheduling | `MG_SCHEDULED/MG_COMPLETED` + `VERIFY_MEET_GREET` | — | ✅ | **WEB_ONLY** (actual scheduling offline) |
| Account invitation → client identity | `onboardClient` / invite / link-cognito | — | Cognito endpoints | **WEB_ONLY** (not one-click conversion) |
| Tenant membership granted / auto-routed | `custom:company_id`; `/t/:slug/admin` | — | `get_current_company_id`, `resolve_expected_tenant` | **PARTIAL / NEEDS_REDESIGN** (route registry is a hardcoded stub) |
| Client completes profile + pets → Active | client mgmt + `PET#` on approval | MyPets read/edit (per builds) | `client_profile`, `pet_profile` | **PARTIAL** (profile auto-created `portal_enabled=False`) |
| Rejected → branded rejection message | decline reason/note only | — | **no rejection email template** | **MISSING** (email) / PARTIAL (status) |
| Rejected prospect archived / retained | ARCHIVE/PURGE via `performAdminAction` | — | terminal `DECLINED`/`ARCHIVED` | **WORKS** (web); not auto-archived |

Workflow 1 is the least mobile-critical for Ryan today and overlaps the PTM /
DOMAIN tenant-onboarding track.

---

## Workflow 2 — Existing-client operational booking

```
request → review → needs info / decline / approve → quote → client confirmation
        → assignment → visits → start → in progress → completion → client update/history
```

Current reality (classification per step):

| Step | Web | Mobile | Backend | Classification |
|---|---|---|---|---|
| Client signs in → routed to authorized tenant | Cognito + `/t/:slug` | Login | claim-based | **PARTIAL** (auto-routing stubbed) |
| Request service from home / My Pets | `IntakeForm` via `submitClientRequest` | `IntakeScreen` | `intake_handler` `VISIT_BOOKING` | **WORKS** |
| Request appears on owner dashboard/mobile | ✅ | ✅ (list) | `GET /admin/requests` | **WORKS** |
| Owner reviews client/pet/request from phone | CareCard | RequestDetail | `GET /admin/requests/{id}` | **WORKS** |
| Owner: approve | `reviewRequest('APPROVED')` | Approve | `review_handler` | **WORKS** |
| Owner: decline | decision modal | — | `review_handler('DECLINED')` | **WEB_ONLY** |
| Owner: request more info | — | — | — | **MISSING** (no `NEEDS_CLIENT_INFO`) |
| Owner: contact client | mailto/tel | tel/mail/maps deep links | — | **WORKS** |
| Set/confirm price (quote) | CareCard `quote_amount` + `payment_status` + `QUOTE_SENT` | — | statuses + fields | **WEB_ONLY** (core mobile gap) |
| Tentatively assign staff | assign before/after confirm | assign (APPROVED) | `assignment_handler` | **PARTIAL** (not gated on quote acceptance) |
| Client receives quote → accept/cancel | email + Stripe link; cancel in portal | — | `PAYMENT_LINK_EMAIL`; `requestCancellation` | **PARTIAL** (no in-portal "Accept Quote") |
| Final confirmation after client acceptance | implicit via payment | — | — | **NEEDS_REDESIGN** (no explicit confirmation gate) |
| Booking generates one/more Visits | — | — | `job_handler` child expansion | **WORKS** |
| Assign each Visit | inline staff select | staff picker | `assignment_handler` cascade | **WORKS** |
| Visit → in progress (Start) | — | Start (staff, per builds) | `job/start` | **PARTIAL** (no request `IN_PROGRESS`; E3B source-only) |
| Complete visit | — | Complete (staff) | `job/complete`, `review COMPLETED` | **PARTIAL** (strongest on mobile, not in current builds) |
| Client cancellation from history | `/my-bookings` cancel | — | `POST /client/cancel` | **WEB_ONLY** |

### Cancellation behavior (current, confirmed)

- Customer `POST /client/cancel` → `CANCELLATION_REQUESTED` (soft; 24h fee warning;
  full `audit_log` retained).
- Admin `PUT /admin/cancel/decision` (owner/admin only): `APPROVE` → `CANCELLED`,
  `DENY` → `CANCELLATION_DENIED`.
- On approve: de-duplicated Google Calendar event deletion across parent + child
  jobs, worker SNS alert, `notify_event('VISIT_CANCELLED')`.
- **Soft cancel preserves business history.** Hard delete (`PURGE`) is a separate,
  typed-confirmation admin action — not the normal cancellation path.
- `cascade.py` maps `CANCELLATION_DENIED → ASSIGNED` (stays assigned) and preserves
  `COMPLETED` jobs.

### Calendar behavior (current, confirmed)

See the Calendar Principle section below.

---

## Workflow 3 — Pet-care business onboarding

```
business prospect → USMISSIONHERO review → onboarding → SaaS billing
                  → tenant provisioning/configuration → owner invitation → launch
```

Current reality (classification per step):

| Step | Web | Backend | Classification |
|---|---|---|---|
| Business owner visits "For Pet Businesses" | — | — | **MISSING** |
| Submit business application | — | — | **MISSING** (no self-serve intake) |
| USMISSIONHERO review | Platform Admin directory/detail | `platform_handler` GET/PATCH | **PARTIAL** (no application object) |
| Outreach / onboarding meeting | — | — | **MISSING** (manual/offline) |
| Tenant setup / provisioning | preview-only orchestrator | `platform_onboarding_handler` validate/preview | **PARTIAL** (no Apply/Create; Matthew-gated) |
| Subscription / payment setup | tier/status PATCH | subscription webhooks | **PARTIAL** (Stripe live EIN-blocked) |
| Owner invitation | Cognito onboarding (reused) | Cognito endpoints | **PARTIAL** (manual) |
| Services / branding / integrations config | — | per-tenant calendar binding exists | **PARTIAL / MISSING** (branding hard-coded) |
| Launch | — | tenant status `active` gate | **PARTIAL** (new tenants default `disabled`) |

Long-term, provisioning should be a **platform-control-plane capability** (the
"Keep" automation) rather than requiring manual tenant creation by ChatGPT/Kiro.
This workflow maps to the existing PTM-0..PTM-13 roadmap and remains on that
gated track; it is the least mobile-relevant.

---

## Critical mobile finding (proven root cause)

**The "assignment works on mobile but I can't process the rest of the request"
complaint is a mobile UI workflow-coverage gap — not a backend gap and not an
API-client wiring gap.**

Traced evidence:

- `mobile/src/api/client.ts` already wires `reviewRequest`, `assignWorker`,
  `completeJob`, and `startJob` to the correct endpoints.
- The existing backend and mobile API client already support **substantial
  portions of the current request lifecycle** — including review/status
  transitions through `POST /admin/review` (`review_handler`), assignment, Start,
  and Complete. This is **not** a claim that every desired future workflow action
  exists: the desired future business workflow contains additional states, actions,
  and UX (e.g. an explicit "request more info" state, an in-portal quote
  acceptance/confirmation gate, client-visible/internal note separation) that
  require OPS-0 design and later implementation. The precise per-capability status
  is in the capability matrix below.
- `RequestDetailScreen` / `RequestCard` only render actions for three request
  states: footer visibility is
  `showFooter = (role !== 'staff' && (isPending || isApproved || isAssigned)) || (role === 'staff' && isAssigned)`.
- Assignment "works" because it only needs the `APPROVED` / `ASSIGNED` states the
  mobile UI renders, and the staff-picker + `/admin/assign` chain is fully built.
- When a request needs an intermediate step (meet-and-greet completion or quote
  acceptance), the backend correctly rejects a premature `APPROVED` with HTTP 400,
  and mobile surfaces the raw error with **no in-app path to resolve it.**

**Current mobile action exposure:** Approve (`PENDING_REVIEW`, non-staff),
Assign Staff (`APPROVED`, non-staff), Change Staff (`ASSIGNED`, non-staff),
Start Visit (`ASSIGNED` + staff + exact job + not started), Complete Visit
(`ASSIGNED` + staff + started). Roughly **3 of ~10** actionable lifecycle steps.

**Missing mobile actions/states:** Decline; quote entry / set price / mark quote
sent; meet-and-greet verify/schedule; request-more-info; cancel-approval /
cancellation decision; visibility + actions for all intermediate statuses
(`MEET_GREET_REQUIRED`, `MG_SCHEDULED`, `MG_COMPLETED`, `QUOTE_NEEDED`,
`QUOTE_SENT`/`QUOTED`, `READY_FOR_APPROVAL`, `PROFILE_CREATED`,
`CANCELLATION_REQUESTED`); client-visible vs internal note separation; photo
capture on a visit; client-side cancellation parity.

**Secondary findings:**
- `RequestCard` (list) exposes Approve/Assign/Change with **no client-side role
  gating**, unlike `RequestDetailScreen` which gates by role — reconcile.
- Occurrence-safe Start/Complete (E3B / E3B.1) exists in source
  (`resolveActionJobId`, `occurrences` util) but per continuity docs is **not in
  the current internal builds** (iOS `1.0.0 (6)`, Android versionCode `4`).

**Limitation classification:** mobile UI not exposing already-existing backend
capability (**primary**); status-model clarity (no first-class `IN_PROGRESS`)
(**secondary/contributing**). Not a backend API gap for the capabilities already
present, not an API-client wiring gap for those, not an RBAC gap for Ryan (he has
owner/admin).

**To avoid overstating backend coverage, distinguish four distinct categories**
(do not treat all desired future workflow behavior as already supported):

1. **Already implemented in backend + API client, missing only from the mobile
   UI** — e.g. Decline, meet-and-greet verify, quote-sent transition, admin
   cancellation decision. These reuse existing deployed endpoints and are the core
   of Ryan's complaint.
2. **Partially implemented** — e.g. mobile Start/Complete (occurrence-safe code in
   source but not confirmed in the current build); quote fields exist but no
   client-facing acceptance flow; client-visible vs internal notes split exists on
   web by field/status but mobile has a single field.
3. **Absent from the desired future business workflow** — e.g. an explicit
   "request more info" / `NEEDS_CLIENT_INFO` state; an explicit in-portal client
   quote acceptance / confirmation gate before staff are committed; branded
   rejection email; visit photo capture. These require new design + build.
4. **Requiring status/domain redesign** — e.g. where physical visit execution
   (`IN_PROGRESS`) belongs (Request vs Visit/JOB); tenant auto-routing (hardcoded
   stub); per-tenant branded notifications. These are OPS-0 design questions and/or
   belong to the gated PTM/DOMAIN track.

The "roughly 3 of ~10 actionable steps" figure above describes the *current*
mobile exposure against the *current* request lifecycle; the *desired future*
workflow is larger still (categories 3 and 4), so mobile coverage must be measured
against the OPS-0 contract once defined, not assumed from today's statuses.

---

## Capability matrix (summary)

Classifications used: `WORKS`, `PARTIAL`, `WEB_ONLY`, `MOBILE_ONLY`, `MISSING`,
`DEFECTIVE`, `NEEDS_REDESIGN`, `UNKNOWN / NEEDS VALIDATION`.

| Capability | Classification |
|---|---|
| Public/portal intake (request submission) | **WORKS** |
| Request appears in admin queue (web + mobile list) | **WORKS** |
| Approve request | **WORKS** (web + mobile) |
| Decline request | **WEB_ONLY** |
| Meet-and-greet verify / schedule | **WEB_ONLY** |
| Quote entry / set price / mark quote sent | **WEB_ONLY** |
| Request more info | **MISSING** |
| Assign / reassign staff | **WORKS** (web + mobile) |
| Job/Visit generation + multi-visit expansion | **WORKS** |
| Start visit | **PARTIAL** (mobile source only, not in current build) |
| Complete visit + completion history | **PARTIAL** (mobile source only, not in current build) |
| Client cancellation from history | **WEB_ONLY** |
| Admin cancellation decision | **WEB_ONLY** |
| Client in-portal "Accept Quote" | **MISSING** |
| Client-visible vs internal visit notes | **PARTIAL** (field/status split on web; single field on mobile) |
| Photo capture on a visit | **MISSING** |
| Google Calendar sync / reassignment / cancellation cleanup | **WORKS** |
| Completed-event retention | **WORKS** |
| Branded approval email | **PARTIAL** (hard-coded Togs & Dogs) |
| Branded rejection email | **MISSING** |
| Push-notification delivery | **MISSING** (tokens registered, no delivery) |
| Tenant auto-routing (approved client → tenant) | **NEEDS_REDESIGN** (hardcoded stub) |
| Per-tenant branded notification templates | **MISSING / NEEDS_REDESIGN** |
| Configurable per-tenant customer payment methods | **MISSING** (Stripe card only) |
| SaaS subscription billing (business → platform) | **PARTIAL** (sandbox; EIN-blocked live) |
| Self-serve business-application intake (Workflow 3) | **MISSING** |
| Tenant Apply/Create provisioning | **PARTIAL** (preview-only, gated) |

---

## Recommended release structure

Phase names are a starting point; dependencies may refine them. Nothing here is
authorized to implement. Each phase is separately approval-gated.

- **OPS-0 — Workflow / State / Action Contract (FIRST IMPLEMENTATION GATE).**
  OPS-0 is the mandatory first gate and must precede OPS-1. It is **compact and
  implementation-oriented** — a concrete contract that the mobile/web/API work in
  OPS-1..OPS-6 builds against — **not** an extended architecture project, and it
  changes no runtime code. At minimum it must define:
  - **Authoritative Request/Booking states** (the `REQ#` lifecycle).
  - **Authoritative Visit/JOB states** (the `JOB#` lifecycle).
  - **Which state belongs to Request vs Visit** (clear ownership; booking/commercial
    state on the Request, physical-execution state on the Visit).
  - **Valid transitions** for each (reconciled against `REQUEST_TRANSITIONS` /
    `JOB_TRANSITIONS` in `src/backend/common/status.py`).
  - **Role allowed for each action** (owner / admin / staff / client), reconciled
    with backend enforcement in `review_handler` / `assignment_handler`.
  - **Mobile / web / API action mapping** — for each action, the API endpoint, the
    web control, and the mobile control (surfacing the "primary next action per
    state" model, reusing the semantics of web `web/src/utils/workflowActions.js`).
  - **Calendar side effect per transition** (create / update-in-place / delete /
    retain; PetCare Hero authoritative, calendar is a projection).
  - **Notification side effect per transition** (which `notify_event` fires, to
    whom; note the current absence of a rejection email).
  - **Client-visible vs internal data ownership** — the explicit data/privacy
    boundary between client-visible updates and internal staff notes on the Visit.
  - **Cancellation behavior** — soft-cancel / history retention, `CANCELLATION_
    REQUESTED` → decision → `CANCELLED` / `CANCELLATION_DENIED`, calendar cleanup.
  - **Quote / client-confirmation behavior** — quote entry/send and whether an
    explicit client acceptance / confirmation gate precedes staff commitment.

  **Design questions OPS-0 must resolve (but NOT implement):**
  - **`IN_PROGRESS` placement.** Do **not** automatically add `IN_PROGRESS` to
    `RequestStatus`. Assess whether it should be a **Visit/JOB** state instead,
    since physical visit execution is operationally distinct from the
    booking/request state. Current behavior represents "in progress" via a JOB
    `started_at`; OPS-0 should decide whether to formalize a JOB-level `IN_PROGRESS`
    rather than a request-level one.
  - **`NEEDS_CLIENT_INFO`.** Assess similarly before adding any new deployed status;
    confirm it is genuinely required by the OPS-2 "request more info" action and
    define its transitions/ownership before any implementation.
  - Record the `RequestCard` vs `RequestDetailScreen` role/action-gating discrepancy
    as an explicit OPS-0 validation item.

  OPS-0 produces documentation/contract artifacts only. No code, no status renames,
  no new deployed statuses in this gate.

  **OPS-0 contract (authored):** the full Workflow / State / Action Contract is in
  `docs/planning/petcare-hero-workflow-state-action-contract.md`. It contains the
  authoritative Request/Booking and Visit/JOB state tables, the action/role matrix
  (RBAC traced from backend), the Request-vs-Visit ownership decisions, the
  `IN_PROGRESS` recommendation (JOB-level, not `RequestStatus`), the
  `NEEDS_CLIENT_INFO` recommendation (flag-on-`PENDING_REVIEW` preferred),
  quote/confirmation and cancellation contracts, calendar and notification matrices,
  the client-visible/internal privacy contract, multi-visit rules, terminal/archive
  semantics, exact OPS-1/OPS-2 scope, and unresolved questions. Disposition:
  `PETCARE_HERO_OPS0_WORKFLOW_CONTRACT_READY_FOR_REVIEW`.

- **OPS-1 — Mobile Visit Operations MVP.**
  Today / Upcoming; visit detail (care/client/pet info); Start Visit; in-progress
  UX; Complete Visit; completion history; occurrence-safe multi-visit behavior.
  Brings E3B / E3B.1 (already in source) into a build. Reconcile `RequestCard`
  role gating. *Highest daily value, lowest new risk.*

  **OPS-1 readiness audit (2026-09-30, read-only).** The OPS-1 Visit-execution
  surface is **already implemented and tested in source** at `main`
  `31cc2cbb8b40638a440f957407387f8a5993396d`:
  - `mobile/src/screens/ScheduleScreen.tsx` — staff Today/Upcoming list that
    projects a Request into per-occurrence visits (`projectOccurrences`) and
    navigates to the exact occurrence.
  - `mobile/src/screens/RequestDetailScreen.tsx` — visit detail + Start/Complete,
    gated to the assigned staff worker, with occurrence-safe `resolveActionJobId`,
    a mutation lock, and stale-response guards. In-progress is derived from the
    JOB `started_at` (no new enum), per the OPS-0 contract.
  - Backend already serves the authoritative occurrence array via
    `GET /admin/requests/{id}` → `job_completion_summary.jobs[]`
    (`_build_job_occurrence_summary`), staff-scoped; `POST /admin/job/start` and
    `POST /admin/job/complete` enforce assigned-worker RBAC, idempotency, and
    parent auto-rollup only when all child JOBs are `COMPLETED`. **No backend
    change is required for OPS-1.**
  - Multi-visit safety gate: **PASS** (each occurrence starts/completes
    independently; wrong-JOB application is blocked by the resolver + backend
    conditional writes; parent rolls up only when all children complete).
  - Focused tests GREEN: `occurrences`, `ScheduleE3B1`, `RequestDetailE3B1`, plus a
    new `RequestDetailVisitPermissions` test (403 permission handling). Full mobile
    suite 152/152 and `tsc --noEmit` clean.
  - **Remaining OPS-1 gate is build inclusion, not source.** Per continuity docs,
    E3B/E3B.1 are not in the current internal builds (iOS Build 6 / Android
    versionCode 4 predate commit `33e5764`). Shipping them is an EAS build +
    distribution decision that is **approval-gated and out of scope** for this
    read-only/local turn — `UNKNOWN / NEEDS VALIDATION` resolves to "present in
    source, pending a build," not a code gap.
  - `RequestCard` vs `RequestDetailScreen` client-side gating discrepancy is
    **outside Visit execution** (`RequestCard` exposes approve/assign, not
    Start/Complete); tracked for **OPS-2**, not expanded here. Backend RBAC remains
    authoritative.

  **OPS-1 DEFECT (LOCALLY FIXED — awaiting review).** As of 2026-09-30 the bounded
  fix below is implemented locally in `handleStart` and validated by tests; it is not
  deployed or in a build. The description is retained for review context.
  **Authentication-error handling asymmetry on Start.**
  The mobile API client (`mobile/src/api/client.ts`) centrally normalizes an HTTP
  401 (and any `expired`/`unauthorized` message) to the single error
  `"Your session expired. Please sign in again."`; a 403 is surfaced with the
  backend's permission message verbatim. The screen then decides session recovery.
  `handleMarkCompleted`, `handleApprove`, and `handleConfirmAssignment` all log out
  on that normalized session message, but **`handleStart` has no logout branch** —
  on any error it attempts a `getAdminRequest` reconciliation and otherwise sets an
  inline `mutationError`. Result: for an equivalent **authentication (401)** failure,
  completing a visit recovers the session (logout → re-auth) while starting a visit
  shows an inline "session expired" message and leaves the user on a dead session.
  Classification: category-A (authentication) inconsistency, **not** an authorization
  (403) issue and **not** an intentional contract.
  - 403 behavior is correct and consistent on both Start and Complete (permission
    error shown, no logout) and is locked by the stable tests in
    `mobile/__tests__/RequestDetailVisitPermissions.test.tsx`.
  - The desired consistent 401 behavior for Start is captured as an
    intentionally-skipped acceptance test (`it.skip`) in that same file; it must be
    un-skipped only after the reviewed minimal source fix lands.
  - **Fix applied (local, bounded):** in `handleStart`'s inner `catch` (after the
    reconciliation `fetchOccurrence` attempt fails to confirm a started occurrence),
    the original `error.message` is checked for `unauthorized`/`expired` and
    `await logout()` is called in that case, otherwise the existing `setMutationError`
    fallback is used. This reuses the existing `useAuth().logout` contract and the
    identical message check already present three times in the same file. The
    reconciliation logic is unchanged; no backend/API/Terraform change. Validated by
    `mobile/__tests__/RequestDetailVisitPermissions.test.tsx` (Start-401 → logout;
    Start-403 → inline, no logout; Complete-401 → logout; Complete-403 → inline).
    Disposition: `PETCARE_HERO_OPS1_AUTH_ERROR_HANDLING_FIX_READY_FOR_REVIEW`
    (local only; not committed, not built, not deployed).

- **OPS-2 — Mobile Request Processing.**
  Status-driven guided actions. Transitions that already exist in the deployed
  backend (review/status transitions via `/admin/review`, assignment, decline,
  meet-and-greet verify, quote-sent, cancellation decision) can be surfaced on
  mobile **without new backend work** — this is category-1 work and the core of
  closing Ryan's complaint. Actions that do **not** yet exist in the desired future
  workflow (e.g. explicit "request more info" / `NEEDS_CLIENT_INFO`, in-portal
  quote confirmation gate) are category-3/4 and require OPS-0 design plus later
  backend + contract changes; they are **not** assumed to be already supported.
  Includes graceful gate-error resolution for backend 400s (M&G/quote gates).

- **OPS-3 — Client Booking / Quote Experience.**
  In-portal client quote review / accept / cancel; request history; completed-visit
  updates; explicit client-visible vs internal notes (web + mobile).

- **OPS-4 — Notification / Calendar Consistency.**
  Assignment synchronization; reassignment; cancellation; completed-event policy;
  tenant-safe notifications. Calendar remains a projection; PetCare Hero remains
  source of truth. (Per-tenant branded templates + push delivery are gated and
  cross-referenced to the PTM/brand track.)

- **OPS-5 — New Client Acquisition.**
  Public tenant prospect intake; approval / rejection (incl. branded rejection
  email); onboarding / invitation; active-client transition.

- **OPS-6 — Tenant / Business Onboarding.**
  Platform business application; operator review; subscription / onboarding;
  controlled provisioning; eventual "Keep" automation. Maps to PTM-0..PTM-13; stays
  on that gated track.

> These phase names are **not final**. If repository evidence suggests better
> dependencies (e.g., folding Ryan Slice E/E3 remainder into OPS-1/OPS-2), refine
> them at OPS-0.

---

## Proposed acceptance criteria per phase

- **OPS-0:** A reviewed Workflow / State / Action Contract document exists that
  defines authoritative Request/Booking states, authoritative Visit/JOB states,
  state ownership (Request vs Visit), valid transitions, per-action roles,
  mobile/web/API action mapping, calendar side effect per transition, notification
  side effect per transition, the client-visible vs internal data boundary,
  cancellation behavior, and quote/client-confirmation behavior. The contract
  records an explicit **recommendation** on where `IN_PROGRESS` belongs
  (Request vs Visit/JOB) and whether `NEEDS_CLIENT_INFO` is required, **without**
  implementing either, and logs the `RequestCard` vs `RequestDetailScreen` gating
  discrepancy as a validation item. No runtime code, no status renames.
- **OPS-1:** From a physical phone, a staff/owner opens an assigned visit, Starts
  it (→ started), records notes, Completes it (→ completed history retained);
  multi-day completes only the targeted occurrence; no duplicate/stale mutations;
  calendar event retained. Verified backend + mobile end-to-end on a device.
- **OPS-2:** From the phone, an owner can move a request through M&G → quote →
  approve and decline a request using transitions that already exist in the deployed
  backend (`/admin/review`); blocked transitions show an actionable in-app message
  and the resolving action; role gating consistent with backend. Any "request more
  info" behavior depends on the OPS-0 decision on `NEEDS_CLIENT_INFO` and is only in
  scope here if that state is defined and implemented — it is not assumed to already
  exist.
- **OPS-3:** A client-visible update and an internal note are entered on a visit;
  the client portal shows only the client-visible update; the internal note never
  appears to the client; web/mobile parity; client can accept a quote in-portal.
- **OPS-4:** Assignment/reassignment/cancellation reflect correctly on Google
  Calendar; completed events retained; notifications tenant-safe; calendar remains
  a projection of PetCare Hero state.
- **OPS-5:** Prospect intake → approve/reject → invitation → active-client
  transition works end-to-end; branded rejection email sent on decline.
- **OPS-6:** Operator can review a business application and provision a tenant
  through a controlled, approval-gated path (no manual Kiro/ChatGPT creation).

Global standard for OPS phases: **backend works + web works + mobile works +
end-to-end business workflow works**, verified on a physical device for
mobile-facing items.

---

## Product acceptance rule

For operational workflows, a capability is **not** complete merely because backend
+ web work. Completion ultimately requires:

```
Backend works  +  Web works  +  Mobile works  +  end-to-end business workflow works
```

For Ryan-style operational activity, mobile is a first-class execution surface.

---

## Priority principle

- Do **not** automatically prioritize backend technical debt ahead of real
  operational usability.
- Do **not** prioritize visual polish ahead of complete workflows.
- Ryan's daily mobile usability is a **first-class product requirement.**
- Recommended sequence: **OPS-0 (first implementation gate) → OPS-1 → OPS-2**
  (mobile-first, reusing existing deployed backend where capabilities already
  exist), then OPS-3, OPS-4, OPS-5/OPS-6. OPS-0 must precede OPS-1. The
  PTM/DOMAIN/brand track
  (tenant branding, push delivery, auto-routing, payment methods, self-serve
  onboarding) stays on its existing gated path and must not outrank Ryan's daily
  usability. Existing backend hardening remains intact.

---

## Status model review

Current authoritative statuses (`src/backend/common/status.py`, mirrored in
`shared/constants/request-statuses.json`):

`PENDING_REVIEW`, `MEET_GREET_REQUIRED`, `MG_SCHEDULED`, `MG_COMPLETED`,
`PROFILE_CREATED`, `READY_FOR_APPROVAL`, `QUOTE_NEEDED`, `QUOTE_SENT` (`QUOTED`),
`APPROVED` (`BOOKED`), `ASSIGNED` (`JOB_CREATED` / `SCHEDULED`), `DECLINED`,
`CANCELLATION_REQUESTED`, `CANCELLATION_DENIED`, `CANCELLED`, `COMPLETED`,
`ARCHIVED`, `DELETED`.
`JobStatus`: `JOB_CREATED`, `ASSIGNED`, `COMPLETED`, `CANCELLED`, `ARCHIVED`,
`DELETED`.

Least-disruptive mapping of the desired business-language lifecycle onto the
existing model (map, do **not** rename deployed statuses):

| Desired business state | Map to existing | Action |
|---|---|---|
| SUBMITTED | `PENDING_REVIEW` | none |
| UNDER_REVIEW | `PENDING_REVIEW` (+ optional owner "reviewing" sub-flag) | optional flag only |
| NEEDS_CLIENT_INFO | *(none today)* | **ASSESS adding later — genuinely missing** |
| APPROVED_PENDING_QUOTE | `QUOTE_NEEDED` | reuse |
| AWAITING_CLIENT_CONFIRMATION | `QUOTE_SENT` / `QUOTED` | reuse |
| CONFIRMED | `APPROVED` | reuse |
| SCHEDULED | `ASSIGNED` (synonym `SCHEDULED`) | reuse |
| IN_PROGRESS | JOB `started_at` today | **ASSESS adding first-class state later** |
| COMPLETED | `COMPLETED` | none |
| DECLINED / CANCELLED / ARCHIVED | same | none |

**Decisions deferred to OPS-0 (DESIGN QUESTIONS — do NOT implement now):**
- **`IN_PROGRESS` placement is an open design question, not an implemented
  decision.** Do **not** automatically add `IN_PROGRESS` to `RequestStatus`.
  Assess whether it belongs as a **Visit/JOB** state instead, since physical visit
  execution is operationally distinct from booking/request state. It is currently
  represented only by a JOB `started_at` (it appears as a heuristic string in
  `determine_workflow_type` and as a web scheduler filter option, but is **not** a
  `RequestStatus` enum member, not in `REQUEST_TRANSITIONS`, and not in the shared
  contract). Recommended leaning: a first-class **JOB-level** `IN_PROGRESS` rather
  than a request-level one — to be confirmed in OPS-0.
- **`NEEDS_CLIENT_INFO`** — assess similarly before adding any new deployed status;
  add only if the OPS-2 "request more info" action genuinely requires it, with
  transitions and state ownership defined first. The one genuinely missing state in
  the desired workflow, but still a design question, not an approved addition.

**Do not rename deployed statuses yet.** Any status addition must be
backward-compatible with existing production data, the transition table, and the
shared contract, and is separately approval-gated.

---

## Calendar principle

- **PetCare Hero (DynamoDB) is the source of truth. Google Calendar is a
  projection.**
- `sync_calendar_event` creates on first sync and updates in place when an event id
  is present, so reassignment updates the same event (worker name written into the
  description).
- Cancellation deletes and de-duplicates events across parent + child jobs and
  removes stored `google_event_id`s (404/410 treated as already-gone).
- **Completed visits should generally remain historical calendar events** unless a
  later design decision establishes otherwise.
- **Cancellation handling is separate** from completion.
- Per-tenant Google token binding is enforced via `TENANT#{id}`
  `calendar_secret_ref` with strict Secrets Manager ownership validation.
- Operational caveat: the primary Togs & Dogs Google connection is currently
  `VALIDATION_FAILED` / needs reconnect — a write-capable OAuth mutation that is
  **Matthew-gated** and out of scope here.

---

## Payment principle

Two distinct relationships, already separate in code:

- **A. PetCare Hero SaaS subscription billing — tenant business → USMISSIONHERO.**
  Tier limits (`tenant_catalog`), subscription-lifecycle webhooks updating
  `TENANT#` metadata, billing ledger.
- **B. Tenant customer payments — pet owner → Togs & Dogs / tenant.**
  `stripe_client.create_checkout_session` (payment mode, card only); webhook with
  `payment_type=booking` sets `payment_status=paid` on the `REQ#`; admin generates
  / sends the payment link from CareCard.

Gaps (assessment only): only Stripe card is supported — **no configurable
per-tenant payment methods** (PayPal / Venmo / Cash App / cash / check / external);
no in-portal client accept/pay affordance beyond the emailed link.

**Stripe live work is NOT authorized.** Stripe remains sandbox-only; live mode is
EIN-blocked.

---

## Approval gates (preserved)

The following remain gated and are **not** authorized by this planning document:

- No production deployment without Matthew approval.
- No new customer / additional tenant without approval.
- Do not change `TENANT_RESOLUTION_MODE` (strict `multi` is active).
- Stripe remains sandbox-only unless approved; no Stripe live-mode work; no real
  customer payment.
- No App Store / TestFlight / Google Play production or distribution changes.
- No Ryan tester-state changes; no EAS build.
- No production test-data creation or DynamoDB writes.
- No OAuth / Google Calendar reconnect / provider mutation (primary is
  `VALIDATION_FAILED`).
- No reading/exposing secrets, tokens, JWTs, or raw auth/session data.
- No enabling push-notification delivery to real devices.
- Targeted `git add <file>` only — never `git add .`. No commit/push without
  explicit approval.
- Preserve the saved Phase 1B.5C-A plan unless Matthew explicitly approves
  replacing it.

---

## Capabilities to reuse (not rebuild)

- `POST /admin/review` full transition engine (approve/decline/quote/M&G/complete
  + `VERIFY_MEET_GREET`).
- `POST /admin/assign` with staff eligibility validation and multi-day cascade.
- `POST /admin/job/start` and `/admin/job/complete` (+ occurrence-safe resolver
  `resolveActionJobId` / `occurrences` util in mobile source).
- `job_handler` deterministic multi-visit expansion + child calendar sync.
- `cancellation_handler` soft-cancel + calendar cleanup + worker SNS +
  `VISIT_CANCELLED`.
- `google_calendar` create/update/delete with per-tenant token binding and
  completed-event retention.
- `notify_event` dispatcher + Postmark + ledger + quota.
- Stripe payment-link generation / send-email / status handling (sandbox).
- Web `workflowActions.js` guided next-action resolver — a ready blueprint for the
  mobile guided-action model.
- Shared contracts (`shared/constants/*`) as the single source of truth for
  services, windows, statuses, pet fields.

---

## Blockers / contradictions found

- **No product-code blockers to planning.** The backend supports the lifecycle the
  mobile UI lacks; OPS-1/OPS-2 can reuse deployed endpoints.
- **Build-state caveat (updated 2026-10-01):** occurrence-safe Start/Complete is in
  source and was absent from the prior distributed builds. A Matthew-only Android
  preview build (EAS `9558ab2c-a159-45f1-bc58-0e3b0eed5385`, from `13e8178`) has
  since been produced and passed Tier A read-only validation on an Android
  emulator (see "OPS-1 Tier A validation record" below). The mutating Start/Complete
  path itself is not yet exercised (Tier B deferred pending a safe fixture), and no
  physical-device pass is claimed.
- **Runtime caveats taken from continuity (not exercised here):** live entitlement
  enforcement status and Google/OAuth runtime status (primary Google
  `VALIDATION_FAILED`).
- **No contradictions** between the discovery findings and the repository source
  were found.

---

## References

- Discovery source: previous Kiro session read-only discovery report
  (`PETCARE_HERO_OPERATIONAL_WORKFLOW_DISCOVERY_COMPLETE`), preserved in this
  document.
- Status authority: `src/backend/common/status.py`,
  `shared/constants/request-statuses.json`.
- Mobile surface: `mobile/src/screens/RequestDetailScreen.tsx`,
  `mobile/src/components/RequestCard.tsx`, `mobile/src/api/client.ts`.
- Web surface: `web/src/components/AdminDashboard.jsx`,
  `web/src/components/CareCard.jsx`, `web/src/utils/workflowActions.js`.
- Backend: `src/backend/handlers/{review,assignment,job,intake,cancellation}_handler.py`,
  `src/backend/common/{status,cascade,google_calendar,client_profile,pet_profile}.py`,
  `src/backend/common/notifications/`.

---

## OPS-1 Tier A validation record (Android preview build, Matthew-only)

**Date:** 2026-10-01. **Disposition:** `PETCARE_HERO_ANDROID_MATTHEW_TIER_A_VALIDATION_COMPLETE`.
Documentation-only record; no code, no test data, no Tier B, no production mutation.

### OPS-1 source state (confirmed implemented in source at `13e8178`)
- OPS-1 Visit-execution capability is implemented in source.
- Schedule / Today / Upcoming occurrence projection exists (`ScheduleScreen.tsx`,
  `utils/occurrences.ts` `projectOccurrences`).
- Exact Visit/JOB occurrence navigation exists (Schedule → `RequestDetail` with the
  exact `jobId`/`occurrence`).
- Occurrence-safe Start/Complete exists (`RequestDetailScreen.tsx` +
  `resolveActionJobId`).
- Active / In-Progress presentation derives from JOB `started_at` (no new enum).
- No `RequestStatus` `IN_PROGRESS` was introduced.
- Parent Request completion rolls up only when all applicable child JOBs complete
  (backend `/admin/job/complete` auto-rollup).
- Start 401/session-recovery behavior was corrected and committed
  (`13e8178 fix: align mobile visit auth error handling`).
- 403 permission failures remain inline (shown in-screen) without logout.
- No backend change was required for OPS-1.

### Build validation
- Android preview build ID: `9558ab2c-a159-45f1-bc58-0e3b0eed5385`.
- Built from source SHA: `13e8178bd56e0fc69cac5ab7c97f226e8ae81c8d`.
- Profile `preview`, internal distribution, standalone APK, v1.0.0 / versionCode 4.
- Tier A executed by Matthew on an **Android emulator**.
- No Google Play / TestFlight submission was involved.
- Ryan testing remained **paused** throughout.

### Tier A results — all nine items PASS
1. APK launch — PASS (clean launch to Sign In; no crash/blank/glitch).
2. Login — PASS (owner/admin; lands on Admin Dashboard; tab bar present).
3. Schedule availability — PASS ("Dispatch Schedule" opens cleanly).
4. Today empty state — PASS (no visits today; matches Today = 0).
5. Upcoming empty state — PASS (none upcoming; future `PROFILE_CREATED` correctly excluded).
6. Safe existing occurrence / detail resolution — PASS (single occurrence resolved
   with no identity-safety warning).
7. Client / pet / care field rendering — PASS (all fields render; correct
   "Not provided" / "None provided" conditionals; email tappable; Maps/phone
   suppressed when absent).
8. Existing state presentation — PASS (Assigned badge; no false Started indicator;
   Cancelled badge; Completed empty-state correct).
9. Mobile calendar-linkage observation — PASS (no calendar marker on mobile detail;
   expected — see calendar note below).

**Exact defects observed: NONE.** No crash, missing/incorrect field, navigation
defect, display defect, unexpected state, authentication problem, or
occurrence-selection problem.

Positive signal: role gating matched the OPS-1 contract — the `ASSIGNED` booking on
the owner/admin surface showed **Change Staff** and correctly did **not** show
Start/Complete (staff/assigned-worker actions).

### Fixture observations (existing data only; no data created)
- Assigned historical 1-Hour Drop-in: date 2026-08-22, status `ASSIGNED`, assigned
  to Ryan York. Booking detail resolved without any occurrence-safety warning.
- Future Overnight Care 2026-12-10 → 2026-12-11 remained `PROFILE_CREATED` and was
  correctly excluded from the dispatch Schedule.
- No completed-booking fixture existed.
- No today/upcoming active-visit fixture existed.

(Client contact values are intentionally omitted from this record.)

### Tier B status — DEFERRED — SAFE FIXTURE / PRODUCTION-MUTATION GATE
OPS-1 is **not** failed or blocked. Tier B would exercise Start Visit, In Progress,
Complete Visit, multi-visit rollup, 403 assigned-worker behavior, and
expired-session behavior **against the production API**. No approved existing safe
fixture currently exists for that validation. Creating production test data is **not
authorized**, and the historical August booking must **not** be repurposed/mutated
merely for testing. Tier B therefore remains deferred until either:
1. an appropriate existing safe fixture is identified and explicitly approved, or
2. a future non-production mobile validation environment provides safe data.

### Environment caveat
Tier A was completed on an **Android emulator**. This establishes Android
application behavior for the read-only workflow but does **not** claim a Matthew
physical-device pass or a Ryan physical-device pass. Ryan testing remains paused.

### Calendar note
The mobile Booking Details screen does not display the web-side Google Calendar
linkage marker. Classification: **informational web/mobile parity observation — NOT
an OPS-1 defect.** No OAuth/reconnect or calendar change was initiated.
