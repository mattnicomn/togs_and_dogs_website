# Phase 24A-2C.2B — Selector Membership and Noncanonical Service-Type Compatibility Design

**Status:** **PARTIALLY IMPLEMENTED LOCALLY / PLANNING COMPLETE / 2B.1 LOCALLY VALIDATED AND INDEPENDENTLY REVIEWED / WEB DISPLAY COMPATIBILITY COMPLETE / NOT DEPLOYED / 2B.2A CUSTOMER INTAKE CANONICAL SELECTION COMPLETE / OTHER SUBPHASES DEFERRED / PRODUCTION PRESENCE OF NONCANONICAL IDENTIFIERS UNVERIFIED**

**Planning date:** 2026-08-03
**Planning checkpoint:** `ca477be3b79f54466b99339a932e66c218583f55`
**Authorization at planning checkpoint:** Documentation-only planning approved by Matthew. Later explicit approvals separately authorized Phase 24A-2C.2B.2A customer IntakeForm canonical selection and the bounded local Phase 24A-2C.2B.1 ClientPortal/MasterScheduler display-compatibility candidate. Production-data inspection, migration, deployment, distribution, and all other implementation remain unapproved.

---

## 1. Purpose

This document defines an implementation-ready design for reconciling context-specific service selectors with the seven-identifier `SERVICE_TYPES` contract while preserving compatibility for known noncanonical values. It records current emitters and consumers, separates repository-confirmed code paths from unverified production presence, compares bounded future options, and establishes approval gates.

This plan does not decide that every selector should have identical membership. Public intake, staff pet editing, admin booking creation, and scheduler filtering serve different purposes. It also does not choose business meanings for `DOG_WALKING`, `WALKING`, or `OTHER`.

## 2. Confirmed current-state boundaries

- Phase 24A-2C.2A is locally validated and reviewed. AdminDashboard display labels use generated contract values while retaining its exact selector, payload, search, export, and fallback behavior.
- Phase 24A-2C.2C is locally validated and reviewed. Four mobile display paths use one type-safe helper for exact canonical keys and preserve the exact legacy fallback for every other value.
- Phase 24A-2C.2 remains partially complete locally.
- Phase 24A-2C.2B.2A subsequently implemented only the approved customer IntakeForm membership: the six canonical `availableInIntake: true` identifiers in contract order, with contract `labelLong` labels and the existing `PET_SITTING` default. It is locally validated and reviewed, complete locally, and not deployed.
- Phase 24A-2C.2B.1 is locally validated and independently reviewed: exact canonical identifiers use generated `labelLong`; exact `DOG_WALKING`, `WALKING`, and `OTHER` values display as `Daily Dog Walking`, `Dog Walking`, and `Other` in ClientPortal, MasterScheduler desktop service-only visit cards, and MasterScheduler pending-intake cards. Raw `window_type`, owner-specific unknown/nullish/blank fallbacks, identifiers, filters, callbacks, navigation, payloads, persistence, exports, scheduling, and backend behavior remain unchanged. Kiro returned `READY_FOR_LOCAL_PHASE_24A_2C_2B_1_CLOSEOUT`; no correction was required. It is not deployed.
- Remaining selector/filter changes, CareCard cleanup, normalization, backend enforcement, production-data assessment, migration, deployment, and distribution are not approved.
- Phase 24A-2C.2D duration/scheduling metadata and Phase 24A-2C.1 request-status wiring remain deferred and were not started.
- The latest completed validated production release remains Phase 1B.5C-D.2. No Phase 24A work described here has been deployed or distributed.

At the planning checkpoint, static repository evidence confirmed three noncanonical values in active frontend option lists: `DOG_WALKING`, `WALKING`, and `OTHER`. Phase 2C.2B.2A subsequently removed `DOG_WALKING` from new customer intake without mapping or record rewriting; `WALKING` and `OTHER` remain in unchanged CareCard. Request creation still passes through arbitrary values without a canonical allowlist. None of this evidence confirms current production contents.

Implementation records: `docs/release-notes/phase-24a-2c2b1-web-display-compatibility.md` and `docs/release-notes/phase-24a-2c2b2a-intake-canonical-service-options.md`.

## 3. Canonical contract inventory

The authoritative reference is `shared/constants/service-types.json`. The existing generator emits the full object into `web/src/generated/contracts.js` and `mobile/src/contracts/generatedContracts.ts`.

| Identifier | `label` | `labelLong` | Duration | `availableInIntake` | `supportedOnMobile` |
|---|---|---|---:|---|---|
| `WALK_30MIN` | `30-Min Walk` | `30-Minute Walk` | 30 minutes | `true` | `true` |
| `WALK_60MIN` | `60-Min Walk` | `60-Minute Walk` | 60 minutes | `true` | `true` |
| `DROPIN_1HR` | `1-Hour Drop-in` | `1-Hour Drop-in` | 60 minutes | `true` | `true` |
| `DROPIN_3HR` | `3-Hour Drop-in` | `3-Hour Drop-in` | 180 minutes | `true` | `true` |
| `OVERNIGHT` | `Overnight Care` | `Overnight Care` | 720 minutes | `true` | `true` |
| `PET_SITTING` | `Pet Sitting` | `Pet Sitting` | 60 minutes | `true` | `true` |
| `MEET_GREET` | `Meet & Greet` | `Meet & Greet` | 45 minutes | `false` | `true` |

The metadata flags are descriptive contract fields, not authorization to generate options dynamically. In particular, the current AdminDashboard intentionally offers `MEET_GREET` even though `availableInIntake` is false.

## 4. Complete emitter and consumer inventory

### 4.1 Shared contract and adapter layer

| File / owner | Role and exact values | Canonical / user-facing / mutation boundary | Existing coverage and future concern |
|---|---|---|---|
| `shared/constants/service-types.json` | Defines the seven canonical identifiers and metadata in section 3. | Canonical authority; not itself user-facing; changing identifiers or metadata can affect both generated clients. | `shared/validate-constants.mjs`; contract edits require separate approval and adapter regeneration. |
| `shared/generate-contract-adapters.mjs` | Reads the service contract and emits `SERVICE_TYPES` unchanged to web and mobile adapters. | Generator/adapter plumbing only; no selector filtering. | `shared/validate-contract-adapters.mjs`; no change or regeneration is part of 2C.2B planning. |
| `web/src/generated/contracts.js` | Exposes all seven service objects to web. | Generated canonical consumer. | `web/tests/contracts.test.jsx`; never edit directly. |
| `mobile/src/contracts/generatedContracts.ts` | Exposes all seven service objects as a TypeScript `as const` structure. | Generated canonical consumer. | `mobile/__tests__/generatedContracts.test.ts`; never edit directly. |
| `shared/validate-constants.mjs` | Validates parseability, uppercase identifiers, uniqueness, labels, and numeric duration. | Validates contract shape, not application selector membership or backend acceptance. | A future allowlist policy must not be inferred from this validator. |
| `shared/validate-contract-adapters.mjs` | Validates generated outputs and deterministic regeneration. | Adapter validation only. | Run unchanged in any implementation subphase that touches contract consumers. |

### 4.2 Web emitters and consumers

| File / function or component | Role | Exact values / behavior | Canonical? | User-facing? | Payload or persistence impact | Relevant coverage | Compatibility concern |
|---|---|---|---|---|---|---|---|
| `web/src/components/IntakeForm.jsx` — initial form and Service Type selector | Emits through public and authenticated-client request submission. | Phase 2C.2B.2A options, in contract order: `WALK_30MIN`, `WALK_60MIN`, `DROPIN_1HR`, `DROPIN_3HR`, `OVERNIGHT`, `PET_SITTING`, using generated `labelLong` where `availableInIntake === true`. Fixed default remains `PET_SITTING`. | All six are canonical; `MEET_GREET` is excluded by metadata. | Yes. | `payload = { ...formData }`; raw selection reaches `submitRequest` or `submitClientRequest` unchanged. | `web/tests/IntakeFormServiceTypes.test.jsx` covers membership, labels, order, default, validation, payloads, endpoints, and execution states. | Legacy `DOG_WALKING` remains read-compatible elsewhere and is not automatically mapped. |
| `web/src/components/CareCard.jsx` — Visit tab Service Type selector | Emits a field in the admin/staff pet-update request; also displays `pet.service_type` raw when not editing. | Ordered options: `PET_SITTING` / `Pet Sitting`; `WALKING` / `Dog Walking`; `OVERNIGHT` / `Overnight Stay`; `OTHER` / `Other`. Current value comes from `pet.service_type` or blank; there is no fixed default. Static and unconditional inside edit mode; no contract flags. | `WALKING` and `OTHER` are noncanonical. | Yes. | `handleSave` includes the selected value in the object sent to `onUpdate` and `updatePet`. The current admin pet backend editable-field list omits `service_type`, so this route accepts the request but ignores that field rather than persisting it to the PET record. A selector change still changes the API payload and local edit behavior. | CareCard suites cover broader behavior; no focused exact service selector/payload/ignored-field characterization exists. | Existing values absent from this option list can render raw but cannot be faithfully selected; current apparent edit persistence must be characterized before any change. |
| `web/src/components/AdminDashboard.jsx` — New Visit selector | Emits canonical request identifiers through `createAdminBooking`. | Ordered values: `PET_SITTING`, `WALK_30MIN`, `WALK_60MIN`, `DROPIN_1HR`, `DROPIN_3HR`, `OVERNIGHT`, `MEET_GREET`; exact `labelLong` text; default `PET_SITTING`; static explicit options; no flag-driven filtering. | All canonical. | Yes; owner/admin New Visit flow. | Sends `newVisitForm.service_type` unchanged. Membership/value changes alter request payloads and stored request/job records. | `web/tests/AdminDashboardServiceTypes.test.jsx` proves exact values, labels, order, default, exclusion of three known noncanonical values, and raw payload parity. | Preserve the already reviewed static membership unless a later business decision explicitly changes it. |
| `AdminDashboard.jsx` — `getServiceLabel` and request search | Displays canonical long labels; unknown nonblank values retain case while underscores become spaces; blank-like values become `UNKNOWN SERVICE`. Search matches both raw value and rendered label. | Exact-case canonical lookup through `SERVICE_TYPES.services[value]?.labelLong`. | Canonical lookup plus generic compatibility. | Yes. | Display/search only; no payload mutation. | `AdminDashboardServiceTypes.test.jsx`. | Display aliases must not silently change search semantics without characterization. |
| `AdminDashboard.jsx` — `getFriendlyService` / Daily Dispatch export | Displays/exports canonical short labels using an uppercase lookup; unknown nonblank values remain byte-for-byte raw; blank-like values become empty. | Seven canonical contract labels plus raw fallback. | Canonical lookup plus generic compatibility. | Yes, in generated workbook. | Export formatting only; does not change records. | `AdminDashboardServiceTypes.test.jsx`. | A friendly legacy alias in this context would intentionally change exported display output. |
| `AdminDashboard.jsx` — All Requests backup export | Exports `request.service_type` raw. | Any stored string or blank. | Pass-through. | Yes, operational export. | No mutation; raw audit/backup fidelity. | `AdminDashboardServiceTypes.test.jsx`. | Must remain raw even if separate display compatibility is introduced. |
| `AdminDashboard.jsx` — `getWorkflowType` | Classifies a record with a start date and one of `WALK_30MIN`, `DROPIN_1HR`, `DROPIN_3HR`, `OVERNIGHT` as `VISIT_BOOKING` when stronger signals are absent. | Four canonical identifiers. | Canonical subset. | Indirectly; changes workflow grouping/labels. | No stored mutation, but behavior can alter UI classification. | Covered indirectly by dashboard suites. | Noncanonical aliases here could reclassify records and are not display-only. |
| `web/src/components/MasterScheduler.jsx` — Service filter | Filters by exact equality. | `ALL` sentinel / `All Services`, then `WALK_30MIN` / `30m Walk`, `DROPIN_1HR` / `1hr Drop-in`, `DROPIN_3HR` / `3hr Drop-in`, `OVERNIGHT` / `Overnight`; default `ALL`. Static, unconditional, no contract or flags. `ALL` is a filter sentinel, not a service identifier. | Four canonical filter values. | Yes. | No payload/storage mutation; membership controls which exact identifiers can be selected for filtering. | `ServiceTypeDisplayOwners.test.jsx` proves exact, case-sensitive identifier filtering remains independent of visible labels. | `WALK_60MIN`, `PET_SITTING`, `MEET_GREET`, and every noncanonical value can display in the scheduler but cannot be selected as an exact service filter. |
| `MasterScheduler.jsx` — visit and pending-intake cards | Phase 2C.2B.1 uses the shared exact-known-label resolver only when the desktop visit value originates from `service_type` and for pending-intake `service_type`. Truthy `window_type` remains raw and never enters the helper. Canonical values use `labelLong`; the three approved legacy values use explicit aliases; unresolved values remain raw. Mobile visit-card/time behavior is unchanged. | Canonical lookup plus three exact display aliases and raw compatibility. | Yes. | Display only. | `ServiceTypeDisplayOwners.test.jsx` covers desktop/pending owners, raw window precedence, fallbacks, exact filtering, callback identity, mobile non-regression, and object immutability. | Filter membership/equality, `window_type`, callbacks, scheduling, grouping, and raw identifiers remain independent of display labels. |
| `web/src/components/ClientPortal.jsx` — booking heading | Phase 2C.2B.1 uses generated canonical `labelLong` and the three exact approved aliases. Every unresolved value retains the original underscore-only replacement expression; nullish/empty values remain `Pet Care Visit`, case remains unchanged, and whitespace remains whitespace. | Canonical lookup plus three exact display aliases and generic compatibility. | Yes, customer-facing. | Display only. | `ServiceTypeDisplayOwners.test.jsx` covers the real component, all canonical/legacy/fallback classes, cancellation identifiers, and object immutability. | No identifier, request object, cancellation input, fetch/state contract, or navigation behavior changes. |
| `web/src/api/client.js` — request wrappers | Sends submitted objects without service transformation. | `submitRequest`, `submitClientRequest`, and `createAdminBooking` pass the raw field; `updatePet` spreads the raw body. | Pass-through. | Not directly. | Any upstream change reaches the corresponding API payload. | Existing contract/API tests cover request mechanics, not the full selector matrix. | Centralizing here would affect multiple workflows and is not a display-only option. |

`web/src/Admin.css` and `web/src/constants/policy.js` contain incidental text matches only; they do not emit, consume, validate, filter, classify, export, persist, or schedule service identifiers.

### 4.3 Mobile consumers

No mobile service selector, service-submission workflow, service-type filter, or mobile identifier emitter was found in `mobile/src`.

| File / owner | Role and exact behavior | User-facing / payload boundary | Relevant coverage and future concern |
|---|---|---|---|
| `mobile/src/utils/serviceLabels.ts` — `getServiceTypeLabel` | Exact case-sensitive own-property lookup returns canonical `label`; any noncanonical, unknown, or case-variant string uses the legacy underscore-split/initial-uppercase formatter; nullish/blank returns empty. | Display-only helper; never changes raw input. | `mobile/__tests__/serviceLabels.test.ts` covers seven canonical values, the three known noncanonical values, representative unknowns/case variants, blank-like values, prototype/metadata-like keys, and contract immutability. |
| `mobile/src/screens/BookingsScreen.tsx` | Displays `getServiceTypeLabel(item.service_type)`. | Customer-facing display; no payload mutation. | Covered by `BookingsScreen.test.tsx` and owner-integration tests. |
| `mobile/src/screens/ScheduleScreen.tsx` | Copies raw `req.service_type` into expanded visit state, displays through the helper, and passes the original raw identifier in navigation data. | Staff-facing display; raw navigation value preserved. | `ServiceTypeLabelOwners.test.tsx` proves real rendering and raw navigation preservation. |
| `mobile/src/screens/RequestDetailScreen.tsx` | Displays the helper result. | Display only; action identifiers/payloads remain independent. | Owner-integration test covers the real render path. |
| `mobile/src/components/RequestCard.tsx` | Displays the helper result and passes the original request object to navigation. | Display only; raw request preserved. | Owner-integration tests cover canonical and `DOG_WALKING` fallback output. |
| `mobile/src/types/index.ts` — `PetRequest` | Types `service_type` as unrestricted `string`. | Read/pass-through compatibility; no compile-time canonical allowlist. | Future narrowing would be a behavior/API compatibility decision, not a label-only refactor. |

### 4.4 Backend acceptance, persistence, scheduling, classification, and notification consumers

| File / function | Role | Exact behavior for service values | User-facing / stored-record effect | Relevant coverage and future concern |
|---|---|---|---|---|
| `src/backend/handlers/intake_handler.py` — public/client request creation | Validates client, date, pet, and public consent fields, but does not include `service_type` in required fields and has no canonical allowlist. | Persists `body.get('service_type', 'PET_SITTING')`. An absent key defaults; an explicit blank, noncanonical, unknown, or case-variant value passes through as supplied. | Creates REQ records. This is a `REPOSITORY_CONFIRMED_ACCEPTANCE_PATH` for arbitrary submitted identifiers. | `test_intake_validation.py`, `test_public_intake_tenant_routing.py`, `test_r18l_client_booking_limits.py`. Future policy must decide missing versus blank behavior. |
| `intake_handler.py` — admin-created booking | Validates booking/client/pet/date concerns but has no service allowlist. | Persists `body.get('service_type', 'PET_SITTING')` unchanged. | Creates approved VISIT_BOOKING REQ records. | `test_r6f_offline_booking.py` and later booking suites. Any allowlist requires backend deployment and compatibility decisions. |
| `src/backend/handlers/job_handler.py` — job creation | Copies the parent field. | `request_item.get('service_type')` is written unchanged to each child JOB. | Propagates canonical, noncanonical, unknown, case-variant, blank, or null values already present on a request. | `test_r7e_multi_day_jobs.py` proves canonical copying. Legacy/unknown copying needs characterization. |
| `src/backend/handlers/pet_handler.py` — staff/admin PET create/update | Uses an explicit `editable_fields` list that does not contain `service_type`. | A CareCard `service_type` field in the body is neither rejected nor copied into the PET item; it is ignored. Client PET updates reject it because the customer allowlist excludes it. | Staff/admin path can return success without persisting the emitted field; customer path rejects the field. | Pet-handler suites cover allowlists broadly; add focused characterization if CareCard scope changes. This is not a request service normalization path. |
| `src/backend/common/google_calendar.py` — `_build_event_body` | Schedules and labels events. | Canonical duration/color/friendly maps cover seven keys. Unknown values use 60 minutes, color `8`, and the raw identifier. A missing key defaults the local value to `Service`; an explicit null receives the same duration/color fallbacks but renders as `None` through string formatting. | Changes calendar duration, color, and visible summary when invoked; no value normalization. | `test_r6g_calendar_all_day.py`, `test_r6g_calendar_retry.py`, `test_r6g_calendar_token.py`, and `test_r7d_calendar_hardening.py`. Alias or mapping changes here are scheduling behavior and belong behind separate approval. |
| `src/backend/common/notifications/templates.py` — `normalize_context` | Formats notification service labels. | Null-like values default to `PET_SITTING`; seven canonical values map to friendly labels; every other string uses underscore replacement plus `.title()`. | Customer/staff email and notification wording. | `test_r6a_templates.py`, `test_r6b_templates.py`, `test_r7j_notification_content_polish.py`; `HOUSE_SITTING` is a synthetic unknown test, not an application emitter. |
| `src/backend/common/notifications/service.py` | Copies parent `service_type` into job notification context and exposes the stored value to templates. | Pass-through. | Notification context only; no normalization or stored mutation. | Notification test suites. |
| `src/backend/common/status.py` — workflow classification | Uses service as a fallback heuristic. | With a start date, only `WALK_30MIN`, `DROPIN_1HR`, `DROPIN_3HR`, or `OVERNIGHT` trigger `VISIT_BOOKING` through this heuristic. Stronger workflow/status/job signals still take precedence. | Can affect workflow classification returned to consumers. | Status/workflow regression suites; adding aliases would be a behavior change. |

No separate backend export formatter was found. The current operational workbook export is owned by AdminDashboard. Historical scheduling, intake, CareCard, manual-booking, calendar, notification, and production-validation records were reviewed to confirm how these paths evolved; historical fixture or checklist strings are not treated as current application emitters.

## 5. Identifier matrix

### 5.1 Authoritative identifier findings

| Identifier | Emitted by active UI | Accepted / persisted path | Display, filter, and classification consumers | Safe canonical equivalent / ambiguity | Migration and production status |
|---|---|---|---|---|---|
| `WALK_30MIN` | AdminDashboard New Visit (`REPOSITORY_CONFIRMED_EMITTER`); MasterScheduler emits it only as a filter selection. | Both request-creation paths accept and persist it; jobs copy it (`REPOSITORY_CONFIRMED_ACCEPTANCE_PATH`). | Contract labels in Admin/mobile/notifications/calendar; MasterScheduler exact filter; Admin/backend workflow heuristics. | Already canonical; no mapping. | No migration indicated; production contents not assessed. |
| `WALK_60MIN` | AdminDashboard New Visit (`REPOSITORY_CONFIRMED_EMITTER`). | Request paths persist; jobs copy (`REPOSITORY_CONFIRMED_ACCEPTANCE_PATH`). | Contract labels; calendar scheduling; no MasterScheduler option and no fallback workflow service heuristic. | Already canonical. | No migration indicated; production contents not assessed. |
| `DROPIN_1HR` | AdminDashboard New Visit; MasterScheduler filter (`REPOSITORY_CONFIRMED_EMITTER`). | Request paths persist; jobs copy (`REPOSITORY_CONFIRMED_ACCEPTANCE_PATH`). | Contract labels; filter; scheduling; both workflow heuristics. | Already canonical. | No migration indicated; production contents not assessed. |
| `DROPIN_3HR` | AdminDashboard New Visit; MasterScheduler filter (`REPOSITORY_CONFIRMED_EMITTER`). | Request paths persist; jobs copy (`REPOSITORY_CONFIRMED_ACCEPTANCE_PATH`). | Contract labels; filter; scheduling; both workflow heuristics. | Already canonical. | No migration indicated; production contents not assessed. |
| `OVERNIGHT` | IntakeForm, CareCard payload, AdminDashboard New Visit, and MasterScheduler filter (`REPOSITORY_CONFIRMED_EMITTER`). | Request paths persist; jobs copy. CareCard PET update ignores the field (`REPOSITORY_CONFIRMED_ACCEPTANCE_PATH`). | All display owners; filter; scheduling; both workflow heuristics. | Already canonical. | No migration indicated; production contents not assessed. |
| `PET_SITTING` | All three editable selectors; fixed default in IntakeForm/AdminDashboard (`REPOSITORY_CONFIRMED_EMITTER`). | Request paths persist/default; jobs copy. CareCard PET update ignores it (`REPOSITORY_CONFIRMED_ACCEPTANCE_PATH`). | All display owners; calendar/notifications; not in MasterScheduler filter or service fallback heuristic. | Already canonical. | No migration indicated; production contents not assessed. |
| `MEET_GREET` | AdminDashboard New Visit (`REPOSITORY_CONFIRMED_EMITTER`). | Request paths persist; jobs copy (`REPOSITORY_CONFIRMED_ACCEPTANCE_PATH`). | All contract label owners and scheduling; not in MasterScheduler filter or service fallback heuristic. | Already canonical; its `availableInIntake: false` does not govern the admin selector. | No migration indicated; production contents not assessed. |
| `DOG_WALKING` | IntakeForm was a `REPOSITORY_CONFIRMED_EMITTER` at the planning checkpoint; Phase 2C.2B.2A stopped new IntakeForm emission. | Request creation still accepts the legacy value and jobs copy it (`REPOSITORY_CONFIRMED_ACCEPTANCE_PATH`). | Generic/fallback display in Admin, portal, mobile, notifications, and calendar (`REPOSITORY_CONFIRMED_CONSUMER`); no exact MasterScheduler filter or service fallback classification. | `CANONICAL_MAPPING_UNDECIDED`; `AMBIGUOUS_MAPPING`; `NO_SAFE_AUTOMATIC_MAPPING`; 30 versus 60 minutes is not encoded. `DISPLAY_ONLY_COMPATIBILITY_POSSIBLE`. | Migration is not presumed; `PRODUCTION_PRESENCE_UNVERIFIED`. |
| `WALKING` | CareCard selector/body (`REPOSITORY_CONFIRMED_EMITTER`). | CareCard PET update ignores it, but either request-creation endpoint would accept and persist the same arbitrary string (`REPOSITORY_CONFIRMED_ACCEPTANCE_PATH`). | Generic/fallback display consumers (`REPOSITORY_CONFIRMED_CONSUMER`); no exact filter/classifier match. | `CANONICAL_MAPPING_UNDECIDED`; `AMBIGUOUS_MAPPING`; `NO_SAFE_AUTOMATIC_MAPPING`; duration is absent. `DISPLAY_ONLY_COMPATIBILITY_POSSIBLE`. | Migration is not presumed; `PRODUCTION_PRESENCE_UNVERIFIED`. |
| `OTHER` | CareCard selector/body (`REPOSITORY_CONFIRMED_EMITTER`). | CareCard PET update ignores it, but request-creation endpoints accept and persist the arbitrary string (`REPOSITORY_CONFIRMED_ACCEPTANCE_PATH`). | Generic/fallback display consumers (`REPOSITORY_CONFIRMED_CONSUMER`); no exact filter/classifier match. | `CANONICAL_MAPPING_UNDECIDED`; generic meaning creates `AMBIGUOUS_MAPPING` and `NO_SAFE_AUTOMATIC_MAPPING`. `DISPLAY_ONLY_COMPATIBILITY_POSSIBLE`. | Migration is not presumed; `PRODUCTION_PRESENCE_UNVERIFIED`. |

No additional actual service identifier was found in active application source. `HOUSE_SITTING`, `UNKNOWN_SERVICE_TYPE`, `CUSTOM_CARE_2HR`, `Spa_Day`, lowercase/mixed-case values, and `Dog Walking` appear only as synthetic fallback/test fixtures or planning examples. `ALL` is a filter sentinel, `Service` is a missing-value calendar label, and `window_type` is a separate scheduling field; none is an application service identifier emitter.

### 5.2 Backend rejection and readability summary

- The public/client and admin request creation handlers do not enforce a service allowlist and do not reject unknown strings.
- An absent `service_type` key defaults to `PET_SITTING`; an explicit blank or null is not replaced by that default.
- Existing request/job values remain API-readable if a frontend selector later stops emitting them because current read paths do not validate service membership.
- Readability does not guarantee editability or filterability: an HTML selector whose options omit the current value cannot faithfully represent it, and MasterScheduler exact filtering only exposes four canonical choices.
- CareCard's staff/admin PET update behavior is distinct: the field can be sent but is ignored because it is not editable on PET records.

## 6. Selector membership matrix

| Context | Exact ordered values and labels | Default | Availability and source | Contract flags / dynamic generation | Noncanonical emission | Stranding / backend compatibility concern |
|---|---|---|---|---|---|---|
| IntakeForm | `WALK_30MIN` — 30-Minute Walk; `WALK_60MIN` — 60-Minute Walk; `DROPIN_1HR` — 1-Hour Drop-in; `DROPIN_3HR` — 3-Hour Drop-in; `OVERNIGHT` — Overnight Care; `PET_SITTING` — Pet Sitting | `PET_SITTING` | Generated contract order; entries where `availableInIntake === true` | Uses generated `SERVICE_TYPES` and `labelLong`; dynamic filtering is explicitly approved for this customer context | No | Phase 2C.2B.2A stops new `DOG_WALKING` emission while preserving legacy read compatibility; backend acceptance remains unchanged. |
| CareCard edit | `PET_SITTING` — Pet Sitting; `WALKING` — Dog Walking; `OVERNIGHT` — Overnight Stay; `OTHER` — Other | Current `pet.service_type` or blank; no fixed default | Static when editing the card | No contract/flags; not dynamic | Yes: `WALKING`, `OTHER` | A current value outside the list has no matching option. The existing backend ignores this PET field, so apparent edit semantics need characterization before membership work. |
| AdminDashboard New Visit | `PET_SITTING` — Pet Sitting; `WALK_30MIN` — 30-Minute Walk; `WALK_60MIN` — 60-Minute Walk; `DROPIN_1HR` — 1-Hour Drop-in; `DROPIN_3HR` — 3-Hour Drop-in; `OVERNIGHT` — Overnight Care; `MEET_GREET` — Meet & Greet | `PET_SITTING` | Static owner/admin modal | Explicit contract `labelLong` properties only; membership is not generated or filtered | No | Already covered for exact parity. Do not apply `availableInIntake` because this is an admin context. |
| MasterScheduler filter | `ALL` — All Services; `WALK_30MIN` — 30m Walk; `DROPIN_1HR` — 1hr Drop-in; `DROPIN_3HR` — 3hr Drop-in; `OVERNIGHT` — Overnight | `ALL` | Static scheduler filter; exact equality | No contract/flags; not dynamic | No service emission (`ALL` is a sentinel) | Missing identifiers remain visible but cannot be selected as exact filters. Expanding membership affects operational filtering, not request payloads. |
| Mobile | No selector or option list found | N/A | N/A | Generated contract is used only by display helper | No | Any future mobile request flow requires its own product/availability design; `supportedOnMobile` currently describes all seven but does not create a workflow. |

Context-specific memberships should not be unified merely for symmetry. Each future change needs an explicit statement of which services the context is intended to offer or filter.

## 7. Backend acceptance and persistence findings

There is no enforced canonical `service_type` allowlist on either request-creation path. Unknown values are not rejected based on service membership and can reach REQ persistence; job creation then copies the value unchanged. Therefore all arbitrary values have a repository-confirmed acceptance path, but only active UI option values are repository-confirmed emitters.

Unknown or noncanonical identifiers have these downstream effects:

- Google Calendar uses the default 60-minute duration, default color `8`, and raw value as the friendly name. This can silently assign a duration that may not match business intent.
- Notifications title-case underscore-separated unknowns; null-like values become `Pet Sitting`.
- AdminDashboard long display and search replace underscores while preserving remaining case; Daily Dispatch keeps unknown values raw; All Requests export keeps every value raw.
- ClientPortal removes underscores; mobile uses its exact legacy formatter; MasterScheduler displays raw values.
- Admin and backend fallback workflow classifiers do not recognize noncanonical values through their service-specific heuristic, though explicit workflow/status/job evidence can still classify a visit correctly.
- Selector changes alone do not make legacy records unreadable, but they can make a value unselectable and can stop new emission without changing backend acceptance.
- Backend validation, normalization, or alias handling would require code changes, backend tests, deployment review, and a separately approved deployment.

Compatibility does not inherently require aliases. Pass-through reads plus display-only formatting can preserve legacy readability while the original stored value remains unchanged.

## 8. Production-presence limitation

**Repository evidence establishes that these identifiers can follow the documented code path. It does not establish that corresponding records currently exist in production.**

One historical repository validation report describes a past production test using `DOG_WALKING`, and an old smoke checklist uses the same example. Those documents do not prove that any corresponding record still exists, do not establish counts, and do not authorize a new production query. No production API, database, log, export, or customer record was accessed for this plan.

Consequently:

- current production presence and counts are `PRODUCTION_PRESENCE_UNVERIFIED`;
- a migration is not presumed necessary;
- no raw customer records should be requested for compatibility planning;
- any later assessment is optional Phase 24A-2C.2B.4 and needs separate authorization.

## 9. Compatibility options

### Option A — Display compatibility only

| Dimension | Design |
|---|---|
| User value | Consistent generated canonical long labels plus friendly display for specifically approved legacy values while preserving submitted/stored identifiers. |
| Behavior change | Intentional display wording changes only in the approved ClientPortal and MasterScheduler service-only contexts. Exports remain unchanged. |
| Systems / likely files | Implemented candidate scope: `web/src/utils/serviceLabels.js`, `ClientPortal.jsx`, `MasterScheduler.jsx`, two focused tests, and applicable records. CareCard, AdminDashboard, mobile, notifications, and calendar are excluded. |
| Test burden | Completed real render coverage for both changed owners plus canonical/noncanonical/unknown/case/blank inputs, raw window precedence, filtering, callbacks, mobile non-regression, and immutability. |
| Deployment / data | Web deployment required to expose a web UI change; no backend deployment or production-data access. |
| Risk | Low to moderate: visible wording and operational export/display differences can surprise users; aliases can imply an unapproved meaning. |
| Rollback | Revert the display helper/owner calls and redeploy the same web artifact boundary; records remain untouched. |
| Approval / blockers | Matthew approved the exact values, labels, and contexts. Independent review passed with no correction required; deployment remains separately gated and no semantic mapping to a canonical duration exists. |

Limitation: display compatibility does not stop new noncanonical emission, expand filters, enforce backend policy, or resolve duration semantics.

### Option B — Frontend selector canonicalization

| Dimension | Design |
|---|---|
| User value | Stops specifically approved frontend paths from creating new noncanonical request identifiers and clarifies service choices. |
| Behavior change | Changes selector membership/labels/defaults as approved and changes raw identifiers in new payloads. Existing values retain read/display compatibility. |
| Systems / likely files | `IntakeForm.jsx`, `CareCard.jsx`, focused web tests; possibly MasterScheduler only if its filter membership is separately approved. `AdminDashboard.jsx` should remain unchanged unless a distinct membership decision exists. |
| Test burden | Exact before/after selector matrices, raw payload identifiers, defaults/order/availability, existing-value editing, CareCard ignored-field behavior, and complete web regressions. |
| Deployment / data | Web deployment required. No production-data inspection required to stop new emission. Backend allowlisting is excluded. |
| Risk | Moderate to high: `DOG_WALKING`/`WALKING` lack duration, and `OTHER` lacks a canonical category. A guessed mapping changes service meaning and calendar duration. |
| Rollback | Restore the prior static option lists and deploy; preserve read/display support for values emitted during either version. |
| Approval / blockers | Explicit Matthew business decision for each removed/replaced value, labels/order/defaults, and whether CareCard should edit request service or cease presenting an ignored field. |

No automatic `DOG_WALKING -> WALK_30MIN`, `DOG_WALKING -> WALK_60MIN`, `WALKING -> ...`, or `OTHER -> ...` mapping is safe from repository semantics alone.

### Option C — Backend compatibility and validation

| Dimension | Design |
|---|---|
| User value | Makes API acceptance explicit and prevents unintended new identifiers after all supported clients are ready. |
| Behavior change | Separately choose: accept legacy aliases unchanged; accept and normalize with an audit trail; reject for new writes while preserving reads; or version policy by endpoint/client. |
| Systems / likely files | `intake_handler.py`, potentially shared backend policy/helper, `job_handler.py`, status/calendar/notification compatibility only if semantics are approved, and focused backend/API tests. |
| Test burden | Missing/blank/canonical/legacy/unknown cases for public, client, and admin creation; old-record reads; job propagation; notifications; scheduling; workflow classification; API error compatibility. |
| Deployment / data | Backend deployment required. Production-data access is not inherently required, but enforcement should not deploy until legacy-client and optional data questions are resolved. |
| Risk | High: rejection can break older web artifacts or callers; normalization changes persisted identifiers; scheduling aliases can change duration/calendar behavior. |
| Rollback | Feature-gated or versioned policy preferred; redeploy pass-through acceptance. Never destroy original values without an audit/rollback field. |
| Approval / blockers | Separate explicit Matthew approval for accepted set, per-alias behavior, blank/missing policy, API compatibility window, rollout order, and deployment. |

### Option D — Optional production-data assessment

| Dimension | Design |
|---|---|
| User value | Quantifies whether legacy compatibility or a migration warrants further work. |
| Behavior change | None; read-only assessment only. |
| Systems / likely files | Prefer an approved aggregate query/report over the production REQ/JOB store. No application code change is required. |
| Test burden | Validate query scope against synthetic/nonproduction data; reconcile aggregate totals without exporting record bodies. |
| Deployment / data | No deployment; separately approved read-only production access is required. |
| Risk | Moderate privacy/operational risk if scope is broad or output exposes customer data. |
| Rollback | Stop query; delete any approved temporary aggregate artifact according to the agreed handling policy. No production records change. |
| Approval / blockers | Explicit Matthew approval of operator, environment, table/index, tenant, time range, allowed fields, aggregation, retention, and report destination. |

Minimum useful output is aggregate counts grouped only by exact `service_type`, record class (REQ/JOB), tenant scope, and a bounded time range. Do not retrieve names, emails, phones, pet details, notes, addresses, dates of service, tokens, or raw records.

### Option E — Optional migration or deprecation

| Dimension | Design |
|---|---|
| User value | Reduces long-term identifier ambiguity only if evidence and approved business mappings justify it. |
| Behavior change | Rewrites or deprecates selected identifiers; may alter scheduling, filtering, workflow classification, notifications, and exports. |
| Systems / likely files | Data migration tooling/runbook plus all compatibility consumers; exact scope depends on approved mappings and assessment. |
| Test burden | Dry-run fixtures, idempotency, before/after counts, per-record audit, collision/conflict handling, old/new client compatibility, complete backend/web/mobile/scheduling regressions. |
| Deployment / data | Separate production-data and mutation approval; likely staged backend/frontend deployment before any record mutation. |
| Risk | Very high, especially where duration/service meaning is ambiguous. Migration may be unnecessary. |
| Rollback | Immutable backup or reversible old-value audit, deterministic inverse operation, per-batch checkpoints, stop thresholds, and post-rollback verification. |
| Approval / blockers | Options B/C decisions, optional aggregate evidence, provable mapping, migration runbook review, backup/rollback proof, maintenance window, and explicit Matthew approval for execution. |

## 10. Ambiguous semantic decisions

Each known noncanonical identifier receives exactly one semantic classification:

| Identifier | Classification | Repository semantics | Duration known? | Safer current treatment / input required |
|---|---|---|---|---|
| `DOG_WALKING` | `AMBIGUOUS_DURATION_OR_SERVICE_MEANING` | Public intake label says Daily Dog Walking, but does not choose 30 or 60 minutes and supplies no additional duration context. | No; calendar therefore falls back to 60 if no explicit scheduled duration exists. | Preserve the original identifier and use only approved display compatibility. Matthew/business policy must decide future selectable walk products. |
| `WALKING` | `AMBIGUOUS_DURATION_OR_SERVICE_MEANING` | CareCard label says Dog Walking, with no 30/60-minute distinction; the current PET update ignores the field. | No. | Preserve rather than normalize. Decide whether CareCard should represent request service at all, then choose any canonical service explicitly. |
| `OTHER` | `GENERIC_FALLBACK_REQUIRES_POLICY_DECISION` | It represents an open-ended category with no canonical equivalent or duration. No adjacent field proves service meaning. | No. | Preserve the original value. A display label of Other is possible, but removal, replacement, or new canonical category needs business-policy input. |

No `SAFE_CANONICAL_EQUIVALENT_IDENTIFIED` conclusion is supported for these three values. Display-only compatibility is possible for each, but it must not rewrite the underlying identifier or imply a duration.

## 11. Recommended subphase split

| Subphase | Exact scope and prerequisite | Behavior changed | Local validation / deployment / data | Approval and rollback boundary |
|---|---|---|---|---|
| 24A-2C.2B.1 — Display compatibility | **Locally validated and independently reviewed; web display compatibility complete; not deployed.** One exact-known-label resolver serves ClientPortal and selected MasterScheduler `service_type`-only paths. Canonical values use `labelLong`; `DOG_WALKING`, `WALKING`, and `OTHER` use the approved aliases; raw values and payloads remain preserved. | Intentional canonical and three legacy visible labels only. | 37/37 focused tests, 202/202 complete Vitest, 99/99 legacy, successful build; no production data or deployment. | Kiro returned `READY_FOR_LOCAL_PHASE_24A_2C_2B_1_CLOSEOUT` with no correction required. Later deployment approval remains separate. Roll back the helper, two owner calls, focused tests, and documentation only. |
| 24A-2C.2B.2 — Selector emission and membership decisions | Decide IntakeForm, CareCard, and any scheduler-filter changes independently. Requires business meaning for every replacement and a decision on CareCard's ignored field. | New selectable values, raw payloads, and/or filter capabilities. | Locally testable; web deployment later; no data required to stop future emission. | Separate approval per selector/context. Roll back static membership while retaining legacy reads. |
| 24A-2C.2B.3 — Backend accepted-identifier policy | Define missing/blank/canonical/legacy/unknown handling and compatibility window after supported clients are understood. | API acceptance, persistence, errors, and possibly normalization. | Locally testable with synthetic API fixtures; backend deployment required; no production query inherently required. | Separate implementation and deployment approval. Prefer a reversible compatibility flag/version. |
| 24A-2C.2B.4 — Optional production-data assessment | Execute only the minimum approved aggregate read described in section 16. | No application behavior. | Query can be rehearsed locally; production read approval required; no deployment. | Separate data-access approval. Stop without modifying data; control aggregate artifact retention. |
| 24A-2C.2B.5 — Optional migration/deprecation | Proceed only after provable mappings, compatibility rollout, optional evidence, dry run, audit, and rollback approval. | Stored values and all affected downstream semantics. | Extensive local/staging validation; production mutation and possibly coordinated deployments required. | Highest approval class: explicit migration execution approval. Reverse from immutable audit/backup per batch. |

The split is recommended because display, emission, API acceptance, observation, and mutation have materially different risks and approval boundaries. There is no assumption that 2B.3, 2B.4, or 2B.5 should ever be implemented.

## 12. Characterization-first test strategy

All future tests must use synthetic fixtures, mock API/authentication/browser boundaries, avoid production calls, avoid source-string assertions, avoid test-order dependencies, and label current characterization separately from intended changed behavior.

### 12.1 Current-behavior characterization before implementation

1. IntakeForm: exact three values, labels, order, `PET_SITTING` default, no conditional filtering, and exact raw identifiers sent through public and authenticated-client calls.
2. CareCard: exact four values/labels/order; inherited/blank current value; exact body sent to `updatePet`; backend staff/admin success-with-field-ignored behavior; customer rejection if the field is sent to the client endpoint.
3. AdminDashboard: retain the existing four tests for seven canonical labels, fallbacks, exact selector/default/raw payload, search, Daily Dispatch friendly output, and raw request export.
4. MasterScheduler: 2B.1 real-owner coverage now proves exact `ALL` sentinel behavior, case-sensitive exact-equality filtering, canonical and approved aliases, unknown/case/nullish/blank fallbacks, raw `window_type` precedence including `EXACT_TIME` and overlapping keys, unchanged mobile time behavior, callback identity, and object immutability.
5. ClientPortal: 2B.1 real-owner coverage now proves all canonical `labelLong` values, the three approved aliases, arbitrary unknown and case fallbacks, null/undefined/empty `Pet Care Visit`, whitespace preservation, cancellation identifier parity, and object immutability.
6. Mobile: retain helper and all four real-owner tests; prove display-only formatting never changes raw navigation/input data.
7. Backend intake: missing key, explicit blank/null, all seven canonical identifiers, three known noncanonical identifiers, and arbitrary unknown value across public/client/admin paths.
8. Job creation: exact raw copying for canonical, known noncanonical, unknown, blank, and null fixtures.
9. Scheduling: exact duration/color/title fallback for the same fixture classes, including explicit `scheduled_duration` precedence.
10. Notifications: exact canonical label, known noncanonical/unknown title-case fallback, and null-like `PET_SITTING` default.
11. Workflow classification: service-only heuristic behavior versus explicit workflow/status/job evidence.
12. Existing-value compatibility: records remain readable and displayable when their value is not a current selector option.

### 12.2 Intended-change tests by option

- Option A tests should assert only approved visible outputs and exact raw payload/export parity.
- Option B tests should make before/after selector differences explicit and assert the newly approved raw identifier; unchanged selectors and availability must retain exact membership/order/defaults.
- Option C tests should state acceptance, pass-through, normalization, or rejection for every class and verify backward-compatible reads.
- Option D uses only synthetic query fixtures locally and aggregate schema validation.
- Option E requires dry-run/no-op, deterministic batches, idempotency, audit, rollback, and cross-client compatibility tests.

## 13. Validation strategy

The original documentation-only planning pass ran no application tests or builds. The approved 2B.1 implementation subsequently used these validation surfaces:

### Shared

```text
node shared/validate-constants.mjs
node shared/validate-contract-adapters.mjs
```

### Web (from `web/`)

```text
npx vitest run <focused service-type test files>
npm run test:legacy
npx vitest run
npm run lint
npm run build
```

### Mobile (only if a future subphase changes or could regress mobile)

```text
npm test -- --runInBand
npm run typecheck
```

### Backend (select the files affected by the approved option)

```text
python -m pytest tests/backend/test_intake_validation.py tests/backend/test_r6f_offline_booking.py tests/backend/test_r7e_multi_day_jobs.py tests/backend/test_r7d_calendar_hardening.py tests/backend/test_r6a_templates.py tests/backend/test_r6b_templates.py
```

Phase 2C.2B.1 local validation completed with synthetic fixtures and mocked external boundaries: 37/37 new focused tests, 11/11 existing AdminDashboard/IntakeForm exclusion regressions, 202/202 complete Vitest tests across 18 files, 99/99 legacy tests / 301 unique web tests, 18/18 shared constants, 6/6 adapter checks including deterministic zero second diff, and a successful Vite 8.0.8 build with 109 modules transformed (`index-mPUri6lj.js`, `index-bVFIMo3n.css`, `usmh-logo-CrRnxp7-.png`). The complete Vitest run retained the existing jsdom navigation notice; the build retained the existing `optimizeDeps.esbuildOptions` deprecation and large-chunk warnings.

The helper and both new tests lint with 0 errors and 0 warnings. Comparison against `HEAD` proves ClientPortal retains its exact pre-change 2-error/1-warning baseline and MasterScheduler retains its exact pre-change 1-error/0-warning baseline. Complete web lint remains the established 51-error/9-warning baseline. Candidate-introduced lint is zero. No applicable pre-existing ClientPortal-focused suite exists beyond the new rendered-owner coverage.

Kiro independently reproduced 18 shared-constant tests, 6 adapter checks, 37 focused tests, 99 legacy tests, 202 complete Vitest tests / 301 unique web tests, the successful build, and zero candidate-introduced lint findings. It confirmed raw truthy `window_type`, exact owner fallbacks, and the bounded scope, returning `READY_FOR_LOCAL_PHASE_24A_2C_2B_1_CLOSEOUT` with no blocking or non-blocking correction. Deployment validation remains a later approval boundary.

## 14. Risk and rollback

| Risk | Consequence | Mitigation | Rollback |
|---|---|---|---|
| Ambiguous walk mapping | Wrong service duration or customer expectation | Require explicit duration/product decision; never infer from label alone | Restore original emitted identifier and compatibility display |
| Generic `OTHER` removal | Users lose a needed service category | Decide product requirement before selector change; consider retaining as legacy | Restore option; do not rewrite stored values |
| Selector/value mismatch for existing records | Blank/unselectable current value or accidental overwrite | Characterize existing-value edit behavior; add legacy-preserving placeholder only if approved | Restore prior option list and edit logic |
| Backend enforcement breaks older clients | Request failures after deployment | Coordinate version/rollout; preserve accepted legacy values during compatibility window | Disable/revert enforcement and redeploy |
| Alias affects scheduling/classification | Silent 60/30-minute or workflow change | Keep display aliases separate from scheduling aliases; test each consumer | Remove behavioral alias; retain raw pass-through |
| Friendly export hides raw evidence | Operational backup loses fidelity | Keep All Requests export raw; scope display formatting explicitly | Restore raw export owner |
| Broad production query exposes customer data | Privacy/security incident | Aggregate-only approved fields, tenant/time bounds, no raw output | Stop; securely remove approved temporary artifact per policy |
| Migration is incomplete or wrong | Mixed identifiers or altered bookings | Do not migrate without reversible audit, batch checkpoints, dry run, and stop thresholds | Apply deterministic inverse from backup/audit |

## 15. Approval gates

1. Matthew explicitly approved the bounded 2B.1 local candidate using generated canonical `labelLong`, the three exact aliases, ClientPortal, and selected MasterScheduler service-only display paths.
2. Phase 2B.1 independent review and local closeout passed; passing tests and local closeout do not authorize deployment.
3. 2B.2 requires Matthew to approve each selector/filter's membership, values, labels, order, default, availability rules, and raw payload effects. `DOG_WALKING`, `WALKING`, and `OTHER` require explicit business decisions.
4. 2B.3 requires separate approval of the accepted identifier set; missing/blank/unknown behavior; legacy compatibility duration; normalization versus rejection; API rollout; and backend implementation.
5. Any web or backend deployment requires a later explicit deployment approval after independent validation.
6. 2B.4 requires separate production read authorization with the safeguards in section 16.
7. 2B.5 requires separate implementation, migration-runbook, production mutation, and execution approvals after rollback proof.
8. Contract, adapter, generator, validator, calendar, notification, workflow classification, duration, mobile selector, mobile build/distribution, and Phase 2C.2D changes each remain outside this plan unless separately approved.

## 16. Production-data safeguards

If Matthew later approves 2B.4, the authorization must name the environment, tenant scope, record types, bounded time range, aggregate fields, operator, output location, and retention period. The minimum permitted assessment should:

- be read-only and aggregate counts by exact `service_type` and REQ/JOB record class;
- avoid scans when a bounded/indexed method is available, or explicitly approve a bounded scan if no index supports the aggregate;
- return no PK/SK, request/job/client/pet IDs, names, emails, phones, addresses, notes, care data, service dates, payment data, credentials, tokens, sessions, logs, or record bodies;
- avoid writing flags, timestamps, audit entries, or normalization results to production;
- distinguish duplicate propagation into child jobs from unique parent requests;
- record query time and limitations so counts are not presented as permanent truth;
- keep any output in an approved private location and remove temporary artifacts according to the approved retention rule.

No such access was performed or requested in this phase.

## 17. Explicit exclusions

Beyond the explicitly approved 2B.1 helper, two display-owner calls, focused tests, and documentation, this phase does not:

- modify contracts, generated adapters, generators, validators, dependencies, lockfiles, AdminDashboard, CareCard, IntakeForm, API clients, backend, or mobile code;
- normalize an identifier, alter a selector/filter, or change membership, order, defaults, availability, payloads, validation, persistence, workflow classification, duration, calendar, notifications, navigation, scheduling, or exports;
- inspect, export, migrate, or modify production data;
- build web/mobile artifacts; deploy; sync S3; invalidate CloudFront; run Terraform; generate APK/AAB/IPA files; or change TestFlight, Google Play, App Store, testers, or Ryan testing;
- change Cognito, tenants, `TENANT_RESOLUTION_MODE`, Stripe, Google Calendar, infrastructure, or production systems;
- start Phase 24A-2C.2D or Phase 24A-2C.1.

## 18. Recommended next decision

Phase 2B.1 is locally closed after independent review. Any deployment requires a separate explicit decision. In parallel, business policy should answer these questions before further 2B.2 work:

1. Does public Daily Dog Walking mean 30 minutes, 60 minutes, a configurable duration, or a separate product?
2. Should CareCard edit a request's service type, stop presenting the currently ignored PET field, or serve another purpose?
3. Is `OTHER` still a required selectable category, and if so should it remain a distinct legacy identifier or receive a new canonical contract entry?
4. Which services should each context offer or filter, independent of the other contexts?

Do not approve backend enforcement, production assessment, or migration until these decisions and the relevant characterization tests exist.

---

**Final phase status:** **PARTIALLY IMPLEMENTED LOCALLY / PLANNING COMPLETE / 2B.1 LOCALLY VALIDATED AND INDEPENDENTLY REVIEWED / WEB DISPLAY COMPATIBILITY COMPLETE / NOT DEPLOYED / 2B.2A CUSTOMER INTAKE CANONICAL SELECTION COMPLETE / OTHER SUBPHASES DEFERRED / PRODUCTION PRESENCE OF NONCANONICAL IDENTIFIERS UNVERIFIED**
