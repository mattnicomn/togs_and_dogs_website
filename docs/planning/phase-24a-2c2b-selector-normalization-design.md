# Phase 24A-2C.2B — Selector Membership and Noncanonical Service-Type Compatibility Design

**Status:** **LOCALLY COMPLETE FOR APPROVED FRONTEND SCOPE / BACKEND POLICY, PRODUCTION ASSESSMENT, AND MIGRATION DEFERRED / NOT DEPLOYED / PRODUCTION PRESENCE OF NONCANONICAL IDENTIFIERS UNVERIFIED**

**Planning date:** 2026-08-03
**Planning checkpoint:** `ca477be3b79f54466b99339a932e66c218583f55`
**Authorization at planning checkpoint:** Documentation-only planning approved by Matthew. Later explicit approvals separately authorized Phase 24A-2C.2B.2A customer IntakeForm canonical selection, the bounded local Phase 24A-2C.2B.1 ClientPortal/MasterScheduler display-compatibility candidate, Phase 24A-2C.2B.2B CareCard Option 2, and Phase 24A-2C.2B.2C MasterScheduler canonical service-filter correction. All four approved frontend slices are locally validated and reviewed at their stated gates. Production-data inspection, migration, deployment, distribution, backend accepted-identifier policy, and all other implementation remain unapproved.

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
- Phase 24A-2C.2B.2B is locally validated and independently reviewed, with the CareCard service-type correction complete and not deployed. CareCard no longer presents the ignored editable Service Type selector; Visit Details remains request-first/historical-fallback read-only, and top-level `service_type` is omitted from PET update payloads. No request editor or PET-level service preference was created.
- Phase 24A-2C.2B.2C is locally validated and independently reviewed, documented, awaiting a commit decision, and not deployed. MasterScheduler adds static `WALK_60MIN`, `PET_SITTING`, and `MEET_GREET` canonical filter options while retaining the `ALL` default, exact case-sensitive `service_type` equality, `window_type` separation, pending-intake independence, and shared desktop/mobile filtered collection. No legacy options were added.
- Phase 24A-2C.2B is locally complete for approved frontend scope. Backend policy, legacy normalization, production-data assessment, migration/deprecation, scheduler-specific contract metadata, further availability changes, deployment, and distribution remain separate future decisions and are not approved.
- Phase 24A-2C.2D.1 is locally implemented, locally validated, and independently reviewed: parity and validator hardening is complete with no runtime behavior change and is not deployed. Phase 24A-2C.2D.2 is also locally validated and independently reviewed: the deterministic generated backend service metadata adapter is complete with no runtime consumption and is not deployed. These are continuity corrections only, not selector-normalization work. Phase 2D.3 calendar runtime duration and friendly-name wiring and 2D.4 optional calendar color metadata remain deferred and unapproved. Phase 24A-2C.1 request-status wiring also remains deferred and was not started.
- The latest completed validated production release remains Phase 1B.5C-D.2. No Phase 24A work described here has been deployed or distributed.

At the planning checkpoint, static repository evidence confirmed three noncanonical values in active frontend option lists: `DOG_WALKING`, `WALKING`, and `OTHER`. Phase 2C.2B.2A subsequently removed `DOG_WALKING` from new customer intake without mapping or record rewriting. Phase 2C.2B.2B subsequently removed the CareCard selector that emitted ignored PET fields `WALKING` and `OTHER`, without mapping or rewriting historical values. Request creation still passes through arbitrary values without a canonical allowlist. None of this evidence confirms current production contents.

Implementation records: `docs/release-notes/phase-24a-2c2b1-web-display-compatibility.md`, `docs/release-notes/phase-24a-2c2b2a-intake-canonical-service-options.md`, and `docs/release-notes/phase-24a-2c2b2b-carecard-service-type-correction.md`.

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
| `web/src/components/CareCard.jsx` — Visit tab Service Type | Phase 2C.2B.2B removes the ignored editable selector and retains read-only information. | Raw source precedence is `pet._originItem?.service_type` then historical `pet.service_type`. The existing helper returns canonical `labelLong` and exact aliases for `DOG_WALKING`, `WALKING`, and `OTHER`; unresolved nonblank values remain raw and untrimmed; missing/blank values display `Not Specified`. | Canonical lookup plus three display-only compatibility aliases; no identifier normalization. | Yes, read-only. | `handleSave` explicitly removes inherited top-level `service_type` before `onUpdate`; all other payload fields remain exact. No request/booking edit or PET-level service persistence exists. | `web/tests/CareCardServiceType.test.jsx` has 22 focused real-component tests; backend PET suites characterize existing ignored/rejected behavior. | Locally validated and independently reviewed; correction complete and not deployed. Historical values remain displayable; backend policy and persistence are unchanged. |
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
| `src/backend/handlers/pet_handler.py` — staff/admin PET create/update | Uses an explicit `editable_fields` list that does not contain `service_type`. | A submitted `service_type` is ignored on staff/admin create/update; an absent stored field is not added and an existing stored value is preserved. Client PET updates reject it because the customer allowlist excludes it, and customer sanitization excludes it. | Staff/admin can return success without persisting the submitted field; customer path rejects it. | Phase 2C.2B.2B adds test-only characterization in both PET-handler suites. Backend source remains unchanged; this is not request service normalization. |
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
| `WALK_60MIN` | IntakeForm and AdminDashboard New Visit; MasterScheduler emits it only as a filter selection. | Request paths persist; jobs copy (`REPOSITORY_CONFIRMED_ACCEPTANCE_PATH`). | Contract labels; exact MasterScheduler filter; calendar scheduling; no fallback workflow service heuristic. | Already canonical. | No migration indicated; production contents not assessed. |
| `DROPIN_1HR` | AdminDashboard New Visit; MasterScheduler filter (`REPOSITORY_CONFIRMED_EMITTER`). | Request paths persist; jobs copy (`REPOSITORY_CONFIRMED_ACCEPTANCE_PATH`). | Contract labels; filter; scheduling; both workflow heuristics. | Already canonical. | No migration indicated; production contents not assessed. |
| `DROPIN_3HR` | AdminDashboard New Visit; MasterScheduler filter (`REPOSITORY_CONFIRMED_EMITTER`). | Request paths persist; jobs copy (`REPOSITORY_CONFIRMED_ACCEPTANCE_PATH`). | Contract labels; filter; scheduling; both workflow heuristics. | Already canonical. | No migration indicated; production contents not assessed. |
| `OVERNIGHT` | IntakeForm and AdminDashboard New Visit; MasterScheduler emits it only as a filter selection. CareCard is now read-only. | Request paths persist; jobs copy. | All display owners; filter; scheduling; both workflow heuristics. | Already canonical. | No migration indicated; production contents not assessed. |
| `PET_SITTING` | IntakeForm and AdminDashboard editable selectors; fixed default in both. CareCard is read-only; MasterScheduler emits it only as a filter selection. | Request paths persist/default; jobs copy. | All display owners; exact MasterScheduler filter; calendar/notifications; not in the service fallback heuristic. | Already canonical. | No migration indicated; production contents not assessed. |
| `MEET_GREET` | AdminDashboard New Visit; MasterScheduler emits it only as a filter selection (`REPOSITORY_CONFIRMED_EMITTER`). | Request paths persist; jobs copy (`REPOSITORY_CONFIRMED_ACCEPTANCE_PATH`). | All contract label owners, exact MasterScheduler filter, and scheduling; not in the service fallback heuristic. | Already canonical; its `availableInIntake: false` does not govern the admin selector or scheduler filter. | No migration indicated; production contents not assessed. |
| `DOG_WALKING` | IntakeForm was a `REPOSITORY_CONFIRMED_EMITTER` at the planning checkpoint; Phase 2C.2B.2A stopped new IntakeForm emission. | Request creation still accepts the legacy value and jobs copy it (`REPOSITORY_CONFIRMED_ACCEPTANCE_PATH`). | Generic/fallback display in Admin, portal, mobile, notifications, and calendar (`REPOSITORY_CONFIRMED_CONSUMER`); no exact MasterScheduler filter or service fallback classification. | `CANONICAL_MAPPING_UNDECIDED`; `AMBIGUOUS_MAPPING`; `NO_SAFE_AUTOMATIC_MAPPING`; 30 versus 60 minutes is not encoded. `DISPLAY_ONLY_COMPATIBILITY_POSSIBLE`. | Migration is not presumed; `PRODUCTION_PRESENCE_UNVERIFIED`. |
| `WALKING` | No longer emitted by CareCard after the local 2B.2B candidate; historical/request values remain display-compatible. | Request-creation endpoints still accept and persist the arbitrary string (`REPOSITORY_CONFIRMED_ACCEPTANCE_PATH`). | Approved exact display alias; no exact filter/classifier match. | `CANONICAL_MAPPING_UNDECIDED`; `AMBIGUOUS_MAPPING`; `NO_SAFE_AUTOMATIC_MAPPING`; duration is absent. | Migration is not presumed; `PRODUCTION_PRESENCE_UNVERIFIED`. |
| `OTHER` | No longer emitted by CareCard after the local 2B.2B candidate; historical/request values remain display-compatible. | Request-creation endpoints still accept and persist the arbitrary string (`REPOSITORY_CONFIRMED_ACCEPTANCE_PATH`). | Approved exact display alias; no exact filter/classifier match. | `CANONICAL_MAPPING_UNDECIDED`; generic meaning creates `AMBIGUOUS_MAPPING` and `NO_SAFE_AUTOMATIC_MAPPING`. | Migration is not presumed; `PRODUCTION_PRESENCE_UNVERIFIED`. |

No additional actual service identifier was found in active application source. `HOUSE_SITTING`, `UNKNOWN_SERVICE_TYPE`, `CUSTOM_CARE_2HR`, `Spa_Day`, lowercase/mixed-case values, and `Dog Walking` appear only as synthetic fallback/test fixtures or planning examples. `ALL` is a filter sentinel, `Service` is a missing-value calendar label, and `window_type` is a separate scheduling field; none is an application service identifier emitter.

### 5.2 Backend rejection and readability summary

- The public/client and admin request creation handlers do not enforce a service allowlist and do not reject unknown strings.
- An absent `service_type` key defaults to `PET_SITTING`; an explicit blank or null is not replaced by that default.
- Existing request/job values remain API-readable if a frontend selector later stops emitting them because current read paths do not validate service membership.
- Readability does not guarantee editability or filterability: an HTML selector whose options omit the current value cannot faithfully represent it. MasterScheduler now exposes all seven canonical exact filter choices, while legacy, unknown, case-variant, blank, and null values remain accessible only through `ALL` when other filters match.
- Backend characterization confirms CareCard's former staff/admin PET field was ignored because it is not editable on PET records; the local 2B.2B candidate no longer sends it.

## 6. Selector membership matrix

| Context | Exact ordered values and labels | Default | Availability and source | Contract flags / dynamic generation | Noncanonical emission | Stranding / backend compatibility concern |
|---|---|---|---|---|---|---|
| IntakeForm | `WALK_30MIN` — 30-Minute Walk; `WALK_60MIN` — 60-Minute Walk; `DROPIN_1HR` — 1-Hour Drop-in; `DROPIN_3HR` — 3-Hour Drop-in; `OVERNIGHT` — Overnight Care; `PET_SITTING` — Pet Sitting | `PET_SITTING` | Generated contract order; entries where `availableInIntake === true` | Uses generated `SERVICE_TYPES` and `labelLong`; dynamic filtering is explicitly approved for this customer context | No | Phase 2C.2B.2A stops new `DOG_WALKING` emission while preserving legacy read compatibility; backend acceptance remains unchanged. |
| CareCard Visit Details | No selector after local Phase 2C.2B.2B; read-only canonical/approved-alias/raw/`Not Specified` display | Request `_originItem.service_type` first, historical `pet.service_type` fallback | Always read-only, including edit mode | Existing helper; no option generation or contract flags | No emitted value | `service_type` is explicitly omitted from PET update payloads; no request editor or PET persistence was added. Locally closed after independent review. |
| AdminDashboard New Visit | `PET_SITTING` — Pet Sitting; `WALK_30MIN` — 30-Minute Walk; `WALK_60MIN` — 60-Minute Walk; `DROPIN_1HR` — 1-Hour Drop-in; `DROPIN_3HR` — 3-Hour Drop-in; `OVERNIGHT` — Overnight Care; `MEET_GREET` — Meet & Greet | `PET_SITTING` | Static owner/admin modal | Explicit contract `labelLong` properties only; membership is not generated or filtered | No | Already covered for exact parity. Do not apply `availableInIntake` because this is an admin context. |
| MasterScheduler filter | `ALL` — All Services; `WALK_30MIN` — 30m Walk; `WALK_60MIN` — 60m Walk; `DROPIN_1HR` — 1hr Drop-in; `DROPIN_3HR` — 3hr Drop-in; `OVERNIGHT` — Overnight; `PET_SITTING` — Pet Sitting; `MEET_GREET` — Meet & Greet | `ALL` | Static scheduler filter; exact case-sensitive `service_type` equality | No contract/flags; not dynamic | No service emission (`ALL` is a sentinel) | All seven canonical identifiers are selectable. Legacy, unknown, blank, and null values remain visible under `ALL` but have no explicit option and do not match canonical selections. `window_type` and pending intake remain outside this filter path. |
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
| `WALKING` | `AMBIGUOUS_DURATION_OR_SERVICE_MEANING` | The former CareCard label said Dog Walking, with no 30/60-minute distinction; backend characterization confirms PET updates ignore the field. | No. | Preserve rather than normalize. The local Option 2 candidate displays historical/request values only and does not choose a canonical replacement. |
| `OTHER` | `GENERIC_FALLBACK_REQUIRES_POLICY_DECISION` | It represents an open-ended category with no canonical equivalent or duration. No adjacent field proves service meaning. | No. | Preserve the original value. A display label of Other is possible, but removal, replacement, or new canonical category needs business-policy input. |

No `SAFE_CANONICAL_EQUIVALENT_IDENTIFIED` conclusion is supported for these three values. Display-only compatibility is possible for each, but it must not rewrite the underlying identifier or imply a duration.

## 11. Recommended subphase split

| Subphase | Exact scope and prerequisite | Behavior changed | Local validation / deployment / data | Approval and rollback boundary |
|---|---|---|---|---|
| 24A-2C.2B.1 — Display compatibility | **Locally validated and independently reviewed; web display compatibility complete; not deployed.** One exact-known-label resolver serves ClientPortal and selected MasterScheduler `service_type`-only paths. Canonical values use `labelLong`; `DOG_WALKING`, `WALKING`, and `OTHER` use the approved aliases; raw values and payloads remain preserved. | Intentional canonical and three legacy visible labels only. | 37/37 focused tests, 202/202 complete Vitest, 99/99 legacy, successful build; no production data or deployment. | Kiro returned `READY_FOR_LOCAL_PHASE_24A_2C_2B_1_CLOSEOUT` with no correction required. Later deployment approval remains separate. Roll back the helper, two owner calls, focused tests, and documentation only. |
| 24A-2C.2B.2 — Selector emission and membership decisions | 2B.2A IntakeForm, 2B.2B CareCard Option 2, and 2B.2C MasterScheduler canonical filter correction are locally validated and reviewed at their stated gates. | IntakeForm membership changed in 2B.2A; CareCard ceased ignored PET-field emission in 2B.2B; MasterScheduler added the three missing canonical exact filter choices in 2B.2C. No persistence, request editing, normalization, or backend policy was added. | 2B.2C: 15 focused owner, 231 complete Vitest, 99 legacy / 330 unique web, successful build; no production data or deployment. | Kiro returned `READY_FOR_PHASE_24A_2C_2B_2C_DOCUMENTATION_AND_LOCAL_CLOSEOUT`. Phase 2B is locally complete for approved frontend scope; rollback remains bounded per slice, and deployment remains separately gated. |
| 24A-2C.2B.3 — Backend accepted-identifier policy | Define missing/blank/canonical/legacy/unknown handling and compatibility window after supported clients are understood. | API acceptance, persistence, errors, and possibly normalization. | Locally testable with synthetic API fixtures; backend deployment required; no production query inherently required. | Separate implementation and deployment approval. Prefer a reversible compatibility flag/version. |
| 24A-2C.2B.4 — Optional production-data assessment | Execute only the minimum approved aggregate read described in section 16. | No application behavior. | Query can be rehearsed locally; production read approval required; no deployment. | Separate data-access approval. Stop without modifying data; control aggregate artifact retention. |
| 24A-2C.2B.5 — Optional migration/deprecation | Proceed only after provable mappings, compatibility rollout, optional evidence, dry run, audit, and rollback approval. | Stored values and all affected downstream semantics. | Extensive local/staging validation; production mutation and possibly coordinated deployments required. | Highest approval class: explicit migration execution approval. Reverse from immutable audit/backup per batch. |

The split is recommended because display, emission, API acceptance, observation, and mutation have materially different risks and approval boundaries. There is no assumption that 2B.3, 2B.4, or 2B.5 should ever be implemented.

## 12. Characterization-first test strategy

All future tests must use synthetic fixtures, mock API/authentication/browser boundaries, avoid production calls, avoid source-string assertions, avoid test-order dependencies, and label current characterization separately from intended changed behavior.

### 12.1 Current-behavior characterization before implementation

1. IntakeForm: exact three values, labels, order, `PET_SITTING` default, no conditional filtering, and exact raw identifiers sent through public and authenticated-client calls.
2. CareCard: the implemented 2B.2B coverage proves request-first/historical fallback display, all canonical/alias/raw/blank classes, no edit control, exact payload omission with every other field preserved, immutability, multi-pet/new-flow parity, staff/admin ignored behavior, and customer rejection/sanitization.
3. AdminDashboard: retain the existing four tests for seven canonical labels, fallbacks, exact selector/default/raw payload, search, Daily Dispatch friendly output, and raw request export.
4. MasterScheduler: 2B.1 and 2B.2C real-owner coverage proves the exact eight-option static filter, `ALL` default, all seven canonical selections, case-sensitive exact `service_type` equality, legacy/unknown/case/nullish/blank `ALL` behavior, absence of legacy options, pending-intake independence, raw `window_type` precedence and filter separation, shared desktop/mobile filtering, unchanged ancillary filters/counts, callback identity, and object immutability.
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

Phase 2C.2B.2B final validation completed with 22/22 focused CareCard tests, 37/37 existing service-label/owner regressions, 11/11 AdminDashboard/IntakeForm regressions, 224/224 complete Vitest across 19 files, 99/99 legacy / 323 unique web, 23/23 staff/admin PET backend tests, 18/18 customer PET backend tests, 18/18 shared constants, 6/6 deterministic adapter checks, and a successful 109-module Vite build. The new focused test is lint-clean; CareCard retains its exact pre-change 6-error/1-warning baseline, complete lint remains 51 errors/9 warnings, and candidate-introduced lint is zero. Backend source, contracts, adapters, API clients, mobile, persistence, scheduling, notifications, and production data were unchanged. Kiro independently confirmed the exact 10-file candidate and returned `READY_FOR_LOCAL_PHASE_24A_2C_2B_2B_CLOSEOUT` with no blocking correction. No production inspection, deployment, distribution, or external-system action occurred; passing tests and local closeout do not authorize deployment.

Phase 2C.2B.2C final validation completed with 15/15 focused ServiceTypeDisplayOwners, 29/29 service-label helper, 22/22 CareCard, 11/11 AdminDashboard/IntakeForm, 231/231 complete Vitest across 19 files, 99/99 legacy / 330 unique web, 18/18 shared constants, 6/6 deterministic adapter checks, and a successful 109-module Vite build (`index-C5FqHoe-.js`, `index-bVFIMo3n.css`, `usmh-logo-CrRnxp7-.png`). The changed test is lint-clean; MasterScheduler retains one pre-existing unused `onAssign` error; complete lint remains 51 errors/9 warnings; candidate-introduced lint is zero. Kiro independently verified the exact two-file implementation candidate and returned `READY_FOR_PHASE_24A_2C_2B_2C_DOCUMENTATION_AND_LOCAL_CLOSEOUT` with no blocking correction. No production inspection, deployment, distribution, or external-system action occurred; passing tests and local closeout do not authorize deployment.

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
3. Matthew separately approved and Kiro reviewed the bounded 2B.2A IntakeForm, 2B.2B CareCard, and 2B.2C MasterScheduler frontend corrections. Phase 2B is locally complete only for that approved frontend scope. Any further selector/filter membership, values, labels, order, defaults, availability, payload effects, or scheduler-specific contract metadata require separate approval.
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

Beyond the separately approved 2B.1 display compatibility, 2B.2A IntakeForm membership, bounded 2B.2B CareCard correction, and bounded 2B.2C MasterScheduler canonical filter correction plus focused tests and documentation, this phase does not:

- modify contracts, generated adapters, generators, validators, dependencies, lockfiles, AdminDashboard, API clients, backend source, or mobile code;
- normalize an identifier or change any selector/filter beyond the explicitly approved IntakeForm and MasterScheduler memberships; no other order, default, availability, payload, validation, persistence, workflow classification, duration, calendar, notification, navigation, scheduling, or export behavior changed;
- inspect, export, migrate, or modify production data;
- build web/mobile artifacts; deploy; sync S3; invalidate CloudFront; run Terraform; generate APK/AAB/IPA files; or change TestFlight, Google Play, App Store, testers, or Ryan testing;
- change Cognito, tenants, `TENANT_RESOLUTION_MODE`, Stripe, Google Calendar, infrastructure, or production systems;
- start Phase 24A-2C.2D or Phase 24A-2C.1.

## 18. Recommended next decision

Phase 2B is locally complete for approved frontend scope after independent review of 2B.1, 2B.2A, 2B.2B, and 2B.2C. Any commit, deployment, backend-policy work, production assessment, normalization, migration, scheduler-specific metadata, or additional product/service availability change requires a separate explicit decision. Future business policy may still answer:

1. Does public Daily Dog Walking mean 30 minutes, 60 minutes, a configurable duration, or a separate product?
2. CareCard Option 2 is now the approved local direction: it stops presenting the ignored PET field as editable and does not edit request service. Any future request editor or PET-level service preference requires separate approval.
3. Is `OTHER` still a required selectable category, and if so should it remain a distinct legacy identifier or receive a new canonical contract entry?
4. Whether future contexts or new services require additional availability or scheduler-specific metadata beyond the currently approved memberships.

Do not approve backend enforcement, production assessment, or migration until these decisions and the relevant characterization tests exist.

---

**Final phase status:** **LOCALLY COMPLETE FOR APPROVED FRONTEND SCOPE / BACKEND POLICY, PRODUCTION ASSESSMENT, AND MIGRATION DEFERRED / NOT DEPLOYED / PRODUCTION PRESENCE OF NONCANONICAL IDENTIFIERS UNVERIFIED**
