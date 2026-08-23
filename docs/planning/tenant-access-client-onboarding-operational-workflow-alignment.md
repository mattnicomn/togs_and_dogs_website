# Tenant Access, Client Onboarding, and Operational Workflow Alignment

**Status:** Authoritative planning reconciliation / no implementation authorized

**Date:** 2026-08-23

**Audited repository checkpoint:** `1748aea12f973c104c3196ca707fb56fef17b667`

**Priority:** P0 tenant-access decision; P1 onboarding and Visit Requests source-of-truth

**Scope:** SaaS URL planes, tenant login bootstrap, customer onboarding, Visit Requests, Web Request List, Mobile navigation, and Gate B1A dependencies

---

## 1. Executive Decision

`test_tenant_alpha` is operationally present, active, isolated, and visible to Platform Admin. Its existing Cognito identity is enabled and tenant-mapped. The newly confirmed gap is not an identity defect: the product has no normal tenant-specific application landing URL from which that owner can naturally enter and validate the tenant UI.

Gate B0 remains complete. Gate B1A is blocked because authenticated API readiness is not equivalent to a complete owner login and tenant-surface experience.

The recommended target is:

| Plane | Canonical pattern | Purpose |
|-------|-------------------|---------|
| Control plane | `platform.toganddogs.usmissionhero.com` | USMissionHero Platform Admin, tenant registry, subscriptions, entitlements, support, and platform audit |
| Tenant plane | `<tenant-slug>.toganddogs.usmissionhero.com` | Tenant owner/admin/staff and authenticated client application |
| Existing compatibility host | `toganddogs.usmissionhero.com` | Temporary primary-tenant alias during migration; it must not remain the permanent mixed control/tenant surface |
| Optional custom domain | Verified customer domain mapped to one tenant slug | Later alias only; never a separate authorization model |

Examples:

- `toganddogs.toganddogs.usmissionhero.com` -> internal `company_id=tog_and_dogs`
- `test-tenant-alpha.toganddogs.usmissionhero.com` -> internal `company_id=test_tenant_alpha`

DNS-safe slugs and internal company IDs are intentionally distinct. A server-controlled registry owns the mapping.

---

## 2. Evidence and Current Architecture

The current Web SPA serves public, client, tenant-admin, and Platform Admin routes from one CloudFront hostname. `web/src/App.jsx` exposes `/admin` and `/platform-admin` within the same application shell and shows a Platform Admin navigation link to authorized users. Authentication uses one Cognito pool and the API derives tenant scope from `custom:company_id` under strict `TENANT_RESOLUTION_MODE=multi`.

The backend correctly fails when an authenticated token has no company claim and validates persisted-record ownership. Public intake already uses a separate trusted server-side domain map and rejects claim/domain mismatch. Authenticated tenant routes do not currently receive or validate an expected tenant derived from the browser hostname. The frontend also has no hostname-to-tenant bootstrap or tenant-specific login landing route.

Infrastructure currently provisions one frontend alias/certificate, and the response CORS allowlist is enumerated rather than wildcard/registry driven. Google OAuth return behavior is also tied to the existing production host. These are planning dependencies, not authorization to change infrastructure.

---

## 3. URL Architecture Alternatives

| Alternative | Benefits | Costs / risks | Disposition |
|-------------|----------|---------------|-------------|
| Existing shared host plus routes | No immediate DNS change; useful for a bounded internal bridge | Weak product separation; route context must be propagated and checked; easy to regress into claim-only bootstrap | Temporary B1A bridge only |
| Tenant subdomains | Natural tenant landing page; strong visual/operational separation; scalable provisioning | Requires wildcard DNS/certificate/CloudFront, host bootstrap, CORS, and callback work | Recommended canonical tenant plane |
| Dedicated custom domains | Customer branding and vanity URLs | Ownership verification, certificate lifecycle, support, redirect, and abuse controls | Later optional phase |

The nested product namespace is preferred over flat `<slug>.usmissionhero.com` because it reserves a coherent Togs & Dogs SaaS surface while remaining under a USMissionHero-managed domain. `platform.toganddogs.usmissionhero.com` is preferred over a tenant route for Platform Admin because platform authorization and tenant authorization are different trust domains.

---

## 4. Tenant Resolution Security Model

Hostname or route alone must never grant access. For the canonical tenant plane, all three inputs must agree:

1. The requested hostname resolves through a server-controlled active slug registry.
2. The authenticated Cognito token contains `custom:company_id`.
3. Strict backend tenant resolution resolves that claim to the same active tenant.

An unknown slug, inactive mapping, missing claim, stale claim, or mismatch fails closed before tenant data is returned. Browser-controlled body, query, local storage, Origin, Referer, or arbitrary headers may not grant or switch tenant authority.

An asserted tenant slug may be sent by the frontend only as an additional constraint. The API must compare it with server-derived host/registry context and the authenticated claim; it must never treat it as authority.

Platform Admin is separate:

- `platform_admin` authorization is required on the control plane.
- Cross-tenant target IDs come from platform routes and remain subject to platform RBAC and audit.
- Platform Admin cannot impersonate a tenant user or silently enter tenant data workflows.
- A person who needs both roles uses explicit, separately authorized surfaces; ordinary tenant navigation does not expose Platform Admin.

### Required planning impacts

| Layer | Required design work |
|-------|----------------------|
| Frontend bootstrap | Parse canonical host; load non-sensitive tenant branding; require host/claim agreement after login; fail to a safe mismatch page |
| API tenant context | Add an expected-tenant constraint for authenticated tenant-plane calls; compare registry, claim, active status, and record ownership |
| Cognito login | Preserve one pool initially; ensure invitations and login links point to the intended tenant landing host; no user-selected tenant authority |
| CloudFront | Route control and wildcard tenant hosts deliberately; prevent accidental platform routes on tenant hosts |
| Route53 / ACM | Wildcard tenant DNS and certificate plus explicit control-plane hostname; certificate renewal and validation ownership documented |
| CORS | Replace fixed single-host assumptions with a strict server-controlled origin policy; do not use permissive credentialed wildcards |
| Callback/logout URLs | Register exact allowed tenant/control callbacks or use a verified central callback that safely returns to the original mapped tenant |
| Google OAuth | Return to the initiating verified tenant/control origin instead of a hardcoded primary tenant host |
| Mobile | Continue claim-authoritative access; receive tenant branding/context after login; deep links must map to a tenant and agree with the token |
| Custom domains | Resolve verified aliases to canonical tenant slugs, then apply the same claim agreement; redirect or canonicalize consistently |

---

## 5. Phased Domain Plan

| Phase | Scope | Exit condition |
|-------|-------|----------------|
| DOMAIN-1 | Approve control-plane/tenant-plane architecture, slug rules, compatibility-host disposition, and security invariants | One signed-off ADR and threat model |
| DOMAIN-2 | Implement host/route expected-tenant resolver and fail-closed frontend bootstrap | Mapped match succeeds; missing/unknown/mismatch/inactive cases fail before tenant data |
| DOMAIN-3 | Add wildcard tenant DNS, ACM, and CloudFront support | Two internal tenant hosts serve correct bootstrap with no cross-host leakage |
| DOMAIN-4 | Wire tenant-specific login, invitation, callback, logout, recovery, and deep-link behavior | Both internal tenants complete login/logout/recovery isolation matrix |
| DOMAIN-5 | Move Platform Admin to the control hostname and remove it from ordinary tenant navigation | Tenant users cannot discover or render platform routes; platform RBAC/audit remains intact |
| DOMAIN-6 | Provision and validate a unique DNS-safe slug during approved tenant onboarding | Duplicate/reserved/invalid slugs fail; dry-run/review/apply remains gated |
| DOMAIN-7 | Add verified optional customer domains | Verification, certificate, alias, disable, and rollback runbooks pass |

No phase in this document authorizes DNS, certificate, CloudFront, Cognito, or deployment changes.

---

## 6. Platform Admin Navigation Separation

The long-term tenant owner navigation is:

- Dashboard
- Visit Requests
- Client Management
- Schedule
- Staff
- Pets
- Tenant settings/reporting where applicable

Platform Admin belongs only on the control-plane hostname. The existing conditional Platform Admin link in ordinary Web navigation is a transitional implementation and should be removed in DOMAIN-5.

RBAC rules remain:

- `platform_admin`: platform metadata, entitlements, subscription/support controls, and cross-tenant audit; no tenant impersonation.
- `owner` / `admin`: one claim-matched tenant's operational data and settings.
- `staff`: assigned operational work and minimum required client/pet information.
- `client`: own canonical household/profile, pets, requests, and bookings.

---

## 7. Client Onboarding Source of Truth

Client onboarding and repeat booking are separate workflows.

### New prospective customer

1. Owner receives a call, email, text, or inquiry.
2. Owner opens Client Management and creates one prospective/offline client record with initial contact information, Meet & Greet notes, and onboarding notes.
3. Meet & Greet is scheduled and recorded using the existing canonical Meet & Greet states where a request record participates.
4. After approval, the owner uses **Meet & Greet Approved — Send Client Onboarding** (recommended concise label: **Approve M&G & Send Onboarding**).
5. The backend links or creates exactly one Cognito identity for the existing client profile, sends one onboarding invitation, and records invitation state/audit idempotently.
6. The customer signs in on the tenant-specific Web or Mobile surface and completes one canonical client/household profile.
7. The customer adds pets and required care, emergency, veterinary, and agreement data.
8. Client Management shows onboarding progress and the owner validates completion.

### Canonical completion model required

The current repository has no single customer-editable client-profile endpoint, no onboarding-completion state machine, no Mobile customer profile screen, and no customer pet-create endpoint. Terms/privacy acceptance is currently request-scoped. Therefore a future bounded product/data slice must define:

- canonical household/client profile fields;
- required versus optional fields and field limits;
- onboarding status such as invited / account active / profile incomplete / complete, without overloading booking status;
- acceptance version, timestamp, actor, and source;
- pet-create ownership and validation;
- idempotent invite/link behavior;
- owner-visible completion evidence;
- immutable booking snapshots derived from the canonical profile.

Web and Mobile must write the same backend representation. Platform-specific shadow profiles are prohibited.

### Existing implementation to preserve or revise

| Current behavior | Assessment |
|------------------|------------|
| Web owner can create profile-only client through `POST /admin/clients` | Useful prospective-client foundation |
| Web owner can use `POST /admin/clients/onboard` | Useful identity/invitation primitive; needs product wording and explicit M&G gate |
| Drawer label says “Send welcome invite email” | Revise to onboarding language after workflow decision |
| Web/Mobile authenticated care request uses `POST /client/requests` | Correct repeat-booking path; must not repeat onboarding |
| Web/Mobile customer pet editing uses `GET /client/pets` and `PUT /client/pets/{petId}` | Shared persistence is good; customer pet creation is missing |
| Request submission stores terms/privacy acceptance | Retain as request evidence; not a substitute for versioned onboarding acceptance |

---

## 8. Visit Requests Source of Truth

An existing authenticated customer submits new care through Web or Mobile. The request enters a Visit Requests queue; it does not re-enter client onboarding.

Owner decisions should be expressed using existing canonical states wherever possible:

- **Approve:** canonical `APPROVED`, then scheduling/assignment and the existing E3 lifecycle.
- **Decline:** canonical `DECLINED` with reason/notification semantics.
- **Tentative / Conditional:** not currently canonical. `QUOTE_NEEDED`, `QUOTE_SENT`, and `READY_FOR_APPROVAL` cover specific existing business cases but are not a generic tentative state. A new tentative status requires a separate product/data-model decision defining customer visibility, expiry, capacity reservation, notifications, Calendar behavior, cancellation, and allowed transitions.

Capacity evaluation must consider owner/staff availability and existing child occurrences. Approval must not imply assignment, and assignment must not bypass availability checks.

---

## 9. Web Request List Audit

This is a static, read-only audit of `web/src/components/AdminDashboard.jsx` at the audited checkpoint. The user has reported runtime tab problems. No authenticated browser retest was performed in this planning slice, so “implemented” below does not mean production-verified.

### Tabs and status sections

| UI section / tab | Intended behavior | Actual predicate / fetch | Audit finding | Visit Requests disposition |
|------------------|-------------------|--------------------------|---------------|----------------------------|
| New Customer Intake / Intake Queue | New prospective-customer intake needing review | `CUSTOMER_INTAKE` plus `PENDING_REVIEW`, `NEEDS_REVIEW`, or `PROFILE_CREATED`; active tabs fetch `ALL` | Implemented; `PROFILE_CREATED` inclusion makes the “new” label broader than its wording | Keep in a separate Client Onboarding queue |
| Needs Meet & Greet | Intake awaiting or undergoing M&G | Customer intake plus `MEET_GREET_REQUIRED`, `NEEDS_MG`, or `MG_SCHEDULED` | Predicate is coherent; no dedicated end-to-end tab test located | Client Onboarding, not normal Visit Requests |
| Ready to Approve | Intake ready after M&G | For customer intake: `READY_FOR_APPROVAL`, `NEW_REQUEST`, `MG_COMPLETED`; for visit bookings it also includes `READY_FOR_APPROVAL`, `NEW_REQUEST`, `APPROVED`, `BOOKED` | **Defect:** a tab under New Customer Intake can include visit bookings and already-approved bookings | Split onboarding-ready from visit-review-ready |
| Visit Requests / Booking Queue | Existing-client requests awaiting operational decision | Visit booking plus pending/needs-review/ready/new/**approved/booked** | **Over-broad:** mixes review-needed and accepted/awaiting-assignment work | Replace with explicit Pending Review; move approved/unassigned elsewhere |
| Price Quotes | Requests in quote handling | Visit booking plus `QUOTE_NEEDED`, `QUOTED`, `QUOTE_SENT` | Implemented; three phases compressed into one count | Keep as a queue filter if quoting remains operationally required |
| Scheduled with Staff | Assigned operational work | `ASSIGNED`, `SCHEDULED`, or `IN_PROGRESS` | Implemented; label hides in-progress history and old non-canonical compatibility | Prefer Schedule; retain only as shortcut/history filter |
| Visit Completed | Completed visits | Exact `COMPLETED`; terminal status-specific fetch | Implemented; counts become page/subset-relative after terminal fetch | History/reporting, not active Visit Requests |
| All Active | Active requests | Excludes deleted, archived, completed, cancelled classification, and data issues | Implemented locally; backed by API `ALL`, which itself also returns completed/cancelled before frontend filtering | Keep as operational fallback, not primary queue |
| Needs Action | Broad owner work queue | Intake review, M&G, quote, approved/booked, cancellation requested | Implemented but mixes onboarding, visit review, assignment, and cancellations | Replace with actionable grouped views or explicit reason chips |
| Data Issues | Malformed/unknown/zombie request records | Request-like parent records with missing/unknown fields/status | Useful admin repair surface; protected by capability | Move to Operations/Data Quality, not Visit Requests |
| Cancelled | Cancelled/declined history | `CANCELLED`, `DECLINED`, `REJECTED`, and `CANCELLATION_DENIED` | **Defect:** canonical `CANCELLATION_DENIED` is nonterminal but is classified as cancelled and removed from active views | History after correcting denied-cancellation semantics |
| Saved for Records | Archived records | `ARCHIVED` / legacy `ARCHIVE` | Implemented record-management view | Records/history area |
| Trash | Deleted records | `DELETED` / legacy trash/delete | Implemented destructive-management surface | Operations/Data Quality area |
| Hidden Needs Assignment | Approved/booked/job-created without worker | Dedicated predicate used by dashboard card, not sidebar | Predicate aligns with card count; should become a first-class queue | Visit Requests / Scheduling handoff |

### Filters, counters, actions, and navigation

| Element | Actual implementation | Finding |
|---------|-----------------------|---------|
| Search | Client, pet, email, request ID, service, status, payment | Functional over the currently loaded client-side pool only |
| Payment filter | Unpaid, link sent, paid, waived, refunded | Functional over loaded rows; belongs in billing/Visit Requests context depending workflow |
| Timeframe | Web sends `ALL`, `DAILY`, `WEEKLY`, or `MONTHLY`; backend reads the parameter but does not apply it to the scan/query | **Defect:** selector triggers refetch but does not filter results; counts remain based on the returned pool |
| Staff Quick View | Displays a staff-color legend plus Unassigned | Not interactive and therefore not a staff filter despite its placement among filters; either rename to “Staff Legend” or implement a real filter |
| Sidebar counters | Recomputed from `allRequests` | **Not authoritative totals:** terminal tabs load only a status subset and pagination can truncate the pool, so unrelated counters can become zero/incomplete |
| Data fetching | Two separate effects call `fetchAllData()` for the same view/filter/timeframe changes | **Defect/race risk:** duplicate requests, list resets, and out-of-order completion can make tabs appear unreliable |
| Intake dashboard card | Count uses `INTAKE_QUEUE`; click opens `NEEDS_ACTION` | **Defect:** destination does not match the displayed count |
| Cancellation alert card | Counts `CANCELLATION_REQUESTED`; click opens `ALL` | **Defect:** destination is not filtered to the alert set |
| Scheduled card | Count uses assigned predicate; click opens Scheduler | Directionally correct; Scheduler date visibility may hide a future result |
| Row detail | Client/service, dates/window, status/payment, staff, expanded details | Implemented; exact child occurrences live primarily in exact-request/Scheduler paths |
| Row actions | Workflow-derived approve, quote, M&G, assign, complete, cancel, archive, restore, test, edit | Broadly wired; destructive and status actions need a focused transition/RBAC regression matrix |
| Bulk actions | Context-sensitive status changes, archive/trash/restore/purge | High-risk legacy surface; allows broad status mutation choices and should be outside the simplified Visit Requests MVP |
| Pagination | “Next Page” appends using `lastKey` | Implemented, but counts/search/filter are not server-global and status switches reset the pool |
| Download Offline Backup | Owner/admin export endpoint builds a multi-sheet workbook | Implemented data-management action; belongs under Operations/Export, not Visit Requests filtering |

### Row and bulk action inventory

| Action family | Intended behavior | Actual implementation | Functional / tested assessment | Recommended location |
|---------------|-------------------|-----------------------|--------------------------------|----------------------|
| Create Profile | Create/link a client profile for new intake | `CREATE_PROFILE` is mapped to a `PROFILE_CREATED` review status; the UI success text says “Profile created,” but this action path does not itself call the Client Management create endpoint | **Stale/ambiguous:** approval has separate auto-create/link behavior; focused proof that this action creates a profile was not located | Replace with an explicit Client Management handoff or canonical onboarding action |
| Require / schedule / verify M&G | Move customer intake through M&G states | Review transitions to `MEET_GREET_REQUIRED`, `MG_SCHEDULED`, or pseudo-action `VERIFY_MEET_GREET` | Backend/status tests exist; workflow is implemented | Client Onboarding queue |
| Approve / decline | Make the owner decision | `/admin/review` transitions and associated automation/notifications; E2 guidance is source-only/not deployed | Implemented with broad tests; runtime decision flow still needs queue-slice regression | Visit Requests for bookings; Onboarding approval for prospects |
| Quote / mark quoted | Track requests that require pricing decision | Review transitions to `QUOTE_NEEDED` or legacy-compatible `QUOTED` | Implemented; uses compatibility identifiers and needs business-policy confirmation | Visit Requests quote subqueue |
| Assign / change sitter | Open selector and call assignment handler | UI-only handoff is kept out of status transition; backend cascades assignment | Implemented and tested; availability/capacity decision support is incomplete | Visit Requests -> Schedule handoff |
| View in Calendar | Navigate locally to Scheduler | Guided UI semantic with no status/API mutation | E1 implemented/tested but not deployed | Schedule |
| Complete / reopen / revert | Complete service or recover status | Review transitions, including compatibility recovery to assigned/approved | Implemented; recovery does not restore exact historical status in every case | Schedule/visit detail; recovery in Operations |
| Cancel | Cancel a request directly | Review transition to `CANCELLED`, potentially invoking lifecycle side effects | Implemented; dangerous action with confirmation/notification implications | Visit detail, not a broad queue shortcut without reason |
| Review cancellation | Approve or deny a customer cancellation | Separate cancellation decision endpoint | Implemented; current `window.confirm` + prompt UX is rudimentary | Dedicated Cancellation Requests queue |
| Archive / unarchive / restore | Record retention and controlled recovery | Admin lifecycle action or review recovery; restore commonly chooses pending/approved rather than exact prior state | Implemented with tests; semantics are intentionally approximate | Records/Operations |
| Trash / purge | Soft-delete or permanently delete | Admin action plus typed-confirmation/bulk purge | Implemented high-risk legacy surface | Data Quality/Operations only |
| Mark / unmark test | Set test metadata and cascade to children | Admin action endpoint | Implemented and tested for controlled release use | Internal Operations; hide from normal Visit Requests users |
| Edit pet / row detail | Open CareCard and edit linked pet/request information | Existing modal/drawer handlers | Implemented; exact field ownership remains split between snapshots and profiles | Client/Pet Management or visit detail |
| Bulk status changes | Apply selected transition to many rows | Contextual select permits broad active, terminal, restore, archive, delete, and purge operations | Implemented but insufficiently bounded for a simplified queue; partial failure is possible | Separate Operations bulk-tool slice |

### Existing test evidence

- Release 22ZC verified responsive markup, keyboard activation of four Web stat cards, and preservation of Request List handlers; it did not perform authenticated runtime tab verification.
- Current Web tests cover guided workflow actions, service labels, and status display compatibility.
- No focused automated test was located for every sidebar predicate, counter/destination alignment, duplicate fetch prevention, terminal counter accuracy, or cancellation-denied classification.

### Recommended bounded Request List slice

1. Define one pure canonical queue model with explicit workflow and status membership.
2. Split Client Onboarding from Visit Requests.
3. Make counters server-authoritative or clearly page-scoped.
4. Remove the duplicate fetch effect and add stale-request cancellation/sequence handling.
5. Fix card count/destination pairs and cancellation-denied classification.
6. Test every tab, counter, empty state, action set, RBAC boundary, pagination transition, and navigation target.
7. Defer bulk/destructive redesign to a separate Operations/Data Quality slice.

---

## 10. Cross-Platform Onboarding Parity

| Step | Owner action | Customer action | API / persisted state | Web | iOS/Android Mobile | Validation / tests | Gap |
|------|--------------|-----------------|-----------------------|-----|--------------------|--------------------|-----|
| Prospect creation | Create profile-only client | None | `POST /admin/clients`; active offline `CLIENT#` | Supported | Owner Client Management absent | Backend/admin client tests exist | Mobile owner parity absent |
| M&G notes/decision | Record notes and M&G outcome | Participate offline | Request review states and request/client notes | Partially supported | Request review actions exist, dedicated onboarding UX absent | Status contract tests | Notes and prospective-client model are not one guided flow |
| Send onboarding | Onboard existing profile | Receive invitation | `POST /admin/clients/onboard`; Cognito + linked client state + email | Supported with legacy welcome wording | Absent | Backend onboarding and invite tests | No explicit M&G-approved gate or shared UX |
| Establish account | Verify first login | Set password/sign in | Cognito `FORCE_CHANGE_PASSWORD` -> `CONFIRMED` | Supported | Supported | Auth tests/manual history | Tenant-specific landing missing on Web |
| Complete customer profile | Review progress | Enter contact/address/emergency data | No canonical customer profile write endpoint/state | Absent | Absent | None located | Blocking product/backend gap |
| Add pet | Validate pet inventory | Create pet | No customer `POST /client/pets`; request submission may create/link pets | No direct self-service create | No direct self-service create | Request/pet handler tests | Onboarding pet creation is indirect |
| Edit pet/care/vet | Review data | Edit own pet | `GET /client/pets`, `PUT /client/pets/{petId}` | Supported | Supported in source/internal mobile line | Web/backend/mobile tests | Creation and some household fields remain missing |
| Agreements | Confirm compliance | Accept terms/privacy | Currently stored on request with timestamp/source | Request form supported | Intake supported | Intake validation tests | No versioned onboarding acceptance record |
| Completion validation | Inspect Client Management | See completion state | No canonical completion state | Portal/access badges only | Absent | None | Owner cannot reliably certify onboarding completeness |
| Repeat booking | Review Visit Request | Submit saved-client booking | `POST /client/requests`, request/job/pet links | Supported | Supported | Cross-platform request tests | Must be separated from onboarding and snapshot model completed |

---

## 11. Day-to-Day Operational Lifecycle Matrix

Deployment labels below distinguish current production from source that is implemented but not deployed/built.

| Workflow | Web | Mobile | Backend | Tests | Production state | Gap / blocker |
|----------|-----|--------|---------|-------|------------------|---------------|
| A. New-client intake | Owner can create offline client; public/customer intake exists | Customer intake exists; owner Client Management absent | Client and intake handlers | Broad coverage | Existing paths deployed; newer service slices not deployed | No guided prospective-client source of truth |
| B. Meet & Greet approval | Request actions/notes | Request actions are limited/operational | Canonical M&G states and review logic | Status/review tests | Existing workflow deployed | Not connected cleanly to client onboarding action |
| C. Client onboarding email | Legacy welcome invite action | No owner action | Client onboard/resend plus Cognito email | Onboarding/invite tests | Existing invitation path deployed | Rename, gate, idempotency UX, tenant landing |
| D. Account/profile completion | Login exists; no canonical profile completion screen | Login exists; no profile screen | No complete profile API/state | Auth only | Login deployed/internal | Major gap |
| E. Pet create/edit | Admin create; customer edit; no customer create | Customer edit; no create | Admin pet create, client pet read/update | Strong pet coverage | Web/backend deployed; Mobile internal only | Customer onboarding creation gap |
| F. New booking request | Customer and admin creation | Customer creation | Intake, async jobs, occurrences | Cross-platform coverage | Core deployed; A–C1/W1/O1 not deployed | Ensure saved profile/snapshots and tenant landing |
| G. Owner review | Full Request List actions | Approve/assign subset | Review handler | Guided-action/status tests | Core deployed; E1/E2 not deployed | Queue audit defects and mixed onboarding/booking |
| H. Tentative/conditional | Quote/ready states only | No generic tentative UX | No canonical tentative state | None | Unsupported | Product/data decision required |
| I. Assignment | Web selector/Scheduler | Owner/admin assignment in source | Assignment cascade/notification | Assignment tests | Core deployed; E1 guidance not deployed | Availability/capacity visibility |
| J. Scheduler/Calendar | Web Scheduler and Google controls | Schedule view | Per-tenant Calendar resolver | Calendar/scheduler tests | Primary tenant configured; test tenant provider none | Date-target navigation and multi-provider rollout |
| K. Start Visit | No approved deployed Web Start UX | E3B/E3B.1 source supports exact child | E3A exact Start deployed | E3A/E3B focused tests | Backend deployed; Mobile not built/distributed | B1A–B3 and mobile release gates |
| L. Complete Visit | Web and Mobile operational actions | Exact-child completion in source | Complete handler | Completion tests | Existing completion deployed/internal | Validate with Start without inventing `IN_PROGRESS` |
| M. Cancellation | Customer request + admin decision | Customer cancellation absent | Cancellation request/decision/cascade | Cancellation tests | Web/backend deployed | Mobile parity and denied-cancellation list defect |
| N. Archive/restoration | Web actions and history views | Absent | Admin lifecycle actions | Record-management tests | Web/backend deployed | Keep outside simplified mobile workflow; high-risk bulk UX |
| O. Notifications | Triggered by defined lifecycle actions | Displays local results only | Postmark notification ledger/templates | Notification suites | Postmark active | Onboarding template/tenant link and tentative semantics unresolved |
| P. Cross-platform synchronization | API refresh; some local optimistic merges | Focus refresh and exact refetch patterns | DynamoDB/API authoritative | Parity/focused tests | Mixed deployed/internal/not-deployed state | No canonical onboarding completion; stale async/list race risks |

---

## 12. Mobile Dashboard Navigation Audit

All five current admin Dashboard metrics are already implemented as pressable cards in source (Slice D1), but D1 is not in the current internal builds.

| Current card | Current count | Current target | Finding | Recommended target |
|--------------|---------------|----------------|---------|--------------------|
| Pending Review | Exact `PENDING_REVIEW` parents | Requests / `PENDING_REVIEW` | Pressable and tested; omits compatibility `NEEDS_REVIEW` and does not distinguish onboarding vs visit booking | Visit Requests filtered to canonical pending review, with workflow facet |
| Needs Sitter | All exact `APPROVED` parents | Requests / `APPROVED` | Pressable; count does not explicitly require unassigned, while label does | First-class Unassigned queue using approved/booked/job-created without worker |
| Scheduled | `ASSIGNED`, `SCHEDULED`, or `JOB_CREATED` | Schedule | Pressable; `JOB_CREATED` may be unassigned and should not count as scheduled | Schedule filtered to assigned/scheduled future occurrences |
| Today's Visits | `selected_dates` equal today | Unfiltered Schedule | Pressable; misses start-date-only/child occurrence models and target is not date-filtered | Schedule with a typed `today` filter derived from child occurrences |
| This Week's Visits | `selected_dates` in seven-day window | Unfiltered Schedule | Same data/target limitation | Schedule with typed seven-day date range |

Recommended future cards after navigation contracts exist:

- **Unassigned** -> Visit Requests / Unassigned.
- **Active Clients** -> Client Management / Active.
- **Cancellation Requests** -> Visit Requests / Cancellation Requested.

Do not add a card unless its count and destination share the same canonical selector and the destination can represent the exact filtered set.

---

## 13. Mobile Bottom Navigation Safe Area

Observed issue: the bottom navigation sits too close to iOS and Android system gesture/home controls.

Current `mobile/src/navigation/AppNavigator.tsx` duplicates a fixed `height: 60`, `paddingBottom: 8`, and `paddingTop: 8` across admin, staff, and client tab navigators. It does not calculate tab-bar height/padding from `useSafeAreaInsets()`. Screen-level `SafeAreaView` usage does not make a fixed custom tab-bar height correct across devices.

Backlog requirement:

- create one shared tab-bar options/helper component;
- derive bottom padding and total height from `react-native-safe-area-context` insets;
- preserve minimum touch-target and label/icon spacing;
- validate iPhone home indicator, Android gesture navigation, Android three-button navigation, small/large devices, portrait, and supported landscape;
- avoid device-name checks and arbitrary per-device constants;
- add snapshot/unit coverage for zero and nonzero insets plus physical-device verification.

The older Release 8O plan addressed deprecated SafeAreaView imports and serializable navigation parameters, but it did not resolve the current fixed bottom-tab inset requirement.

---

## 14. Gate B1A Dependency and Recommendation

**Status:** `B0 COMPLETE`; `B1A BLOCKED`; B1B/B2/B3 remain not approved. Keep the existing identity enabled unless separately approved otherwise.

B1A must not proceed through the shared `/admin` surface merely because API handlers are ready. The test must first prove that a tenant-specific expected context and the existing authenticated claim agree.

Full wildcard tenant-subdomain delivery is not required to unblock B1A. The recommended bounded bridge is:

1. Add a temporary internal route such as `/t/test-tenant-alpha/admin` on the existing compatibility host.
2. Resolve `test-tenant-alpha` through the same server-controlled slug registry planned for subdomains.
3. Treat the route slug only as an expected-tenant constraint.
4. Require the authenticated `custom:company_id` and strict resolver result to map to the same active tenant.
5. Fail closed on missing, unknown, inactive, or mismatched context before rendering tenant data or allowing API work.
6. Hide/deny Platform Admin routes within the tenant bootstrap.
7. Validate match and mismatch cases, login/logout, refresh, direct `/admin` behavior, CORS, and recovery links.
8. Deploy that bounded slice only after separate approval; then perform a login-only Gate and seek fresh B1A data-creation approval.

No such safe bridge exists in the current runtime today. The architecture and public-intake resolver provide reusable patterns, but implementation and deployment are still required. Once canonical tenant subdomains ship, remove the temporary path after a measured compatibility period.

---

## 15. Prioritized Implementation Slices

| Priority | Slice | Scope | Dependency / gate |
|----------|-------|-------|-------------------|
| P0 | DOMAIN-1 architecture ADR | Host patterns, slug registry, threat model, compatibility disposition | Matthew architecture approval |
| P0 | B1A-ROUTE | Bounded test-tenant route/bootstrap plus claim agreement and negative tests | DOMAIN-1; code/deploy approval; no B1A data |
| P0 | B1A-LOGIN | Login-only isolation validation through bounded tenant surface | B1A-ROUTE deployed; explicit validation approval |
| P1 | ONBOARD-1 canonical workflow/data contract | Prospective client, M&G approval, invite, profile completion, acceptance, completion state | Product and security decisions |
| P1 | REQUESTS-AUDIT-1 | Pure queue selectors, count/destination contract, duplicate-fetch correction, tests | No status invention |
| P2 | ONBOARD-WEB-1 | Owner and customer Web workflow using canonical APIs/state | ONBOARD-1 |
| P2 | ONBOARD-MOBILE-1 | Mobile profile/pet/onboarding parity | ONBOARD-1 and Web/API contract stabilization |
| P2 | DOMAIN-2–5 | Canonical subdomains and Platform Admin separation | DOMAIN-1/B1A learnings; infra approvals |
| P3 | MOBILE-DASH-2 | Exact actionable cards and typed destination filters | Request/Schedule selectors |
| P3 | MOBILE-NAV-INSETS | Shared inset-aware tab bar | Mobile build/runtime approval |
| P4 | DOMAIN-6–7 | Automated slug provisioning and optional verified custom domains | Canonical domain plane stable |

---

## 16. Acceptance Criteria for Future Work

- Host/route context never grants authority; claim/context mismatches fail before data access.
- Platform Admin is unreachable from ordinary tenant navigation and cannot impersonate tenant users.
- Web and Mobile write one canonical client/household/pet/onboarding model.
- Normal existing-client bookings never repeat onboarding.
- Every Visit Requests counter uses the same selector as its destination.
- Every Request List tab, filter, action, counter, pagination state, and empty state has focused tests.
- Mobile cards navigate to typed, representable filters.
- Bottom navigation derives layout from safe-area/system insets.
- Deployment/build/data/Cognito/DNS changes remain separately gated.

---

## 17. Non-Authorization

This planning document does not authorize application code changes, deployments, DNS/CloudFront/Route53/ACM changes, tenant or production-data writes, Cognito changes, notification sends, Stripe changes, Mobile builds/distribution, B1A fixture creation, assignment, Start, Complete, or cleanup.
