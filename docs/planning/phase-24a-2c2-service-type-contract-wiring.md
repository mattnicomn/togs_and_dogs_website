# Phase 24A-2C.2 — Cross-Platform Service-Type Contract Wiring Plan

**Status:** 📋 **PARTIALLY COMPLETE LOCALLY / 2C.2A COMPLETE / 2C.2B LOCALLY COMPLETE FOR APPROVED FRONTEND SCOPE / 2C.2C COMPLETE / 2C.2D.1 COMPLETE / 2C.2D.2 COMPLETE / 2C.2D.3 COMPLETE / 2C.2D.4 DEFERRED / NOT DEPLOYED OR DISTRIBUTED**

**Planning Date:** 2026-08-03
**Planning Checkpoint:** `40620cff8cd1cc18e338c62a8b9abd2e991b7f7b`
**Authorization:** Matthew originally approved documentation-only planning, then separately approved bounded local implementations for 2C.2A, the approved 2C.2B frontend slices, 2C.2C, the validation-only 2C.2D.1 candidate, the no-runtime-consumption 2C.2D.2 generated backend metadata candidate, and the behavior-preserving 2C.2D.3 generated calendar duration and friendly-name wiring candidate. Phases 2C.2D.1, 2C.2D.2, and 2C.2D.3 are locally validated and independently reviewed; Kiro returned `READY_FOR_PHASE_24A_2C_2D_3_DOCUMENTATION_AND_LOCAL_CLOSEOUT` for the exact three-file 2D.3 candidate. Optional color metadata (2D.4), production-data inspection, deployment, mobile build, and distribution remain unapproved.

---

## 1. Background

Phase 24A-2 created the canonical `shared/constants/service-types.json` reference contract. Phase 24A-2A generated `SERVICE_TYPES` into the existing web and mobile adapters but deliberately did not wire service identifiers, labels, selectors, durations, or availability into application behavior.

Phase 24A-2B is complete locally and independently reviewed. At this plan's original checkpoint, Phase 24A-2C had not entered implementation. This document plans only Phase 24A-2C.2 service-type wiring and separates behavior-preserving label sourcing from higher-risk membership, mobile, duration, backend, and data-normalization decisions.

The original recommended first implementation was Phase 24A-2C.2A: a bounded AdminDashboard-only display-label substitution that preserves every identifier, option, payload, fallback, and backend behavior.

## 2. Current Canonical `SERVICE_TYPES` Inventory

Canonical source: `shared/constants/service-types.json`. Deterministic generated copies now exist in `web/src/generated/contracts.js`, `mobile/src/contracts/generatedContracts.ts`, and the no-runtime-consumption backend module `src/backend/common/generated_service_types.py`.

| Identifier | `label` | `labelLong` | `durationMinutes` | `availableInIntake` | `supportedOnMobile` |
|---|---|---|---:|---|---|
| `WALK_30MIN` | `30-Min Walk` | `30-Minute Walk` | 30 | `true` | `true` |
| `WALK_60MIN` | `60-Min Walk` | `60-Minute Walk` | 60 | `true` | `true` |
| `DROPIN_1HR` | `1-Hour Drop-in` | `1-Hour Drop-in` | 60 | `true` | `true` |
| `DROPIN_3HR` | `3-Hour Drop-in` | `3-Hour Drop-in` | 180 | `true` | `true` |
| `OVERNIGHT` | `Overnight Care` | `Overnight Care` | 720 | `true` | `true` |
| `PET_SITTING` | `Pet Sitting` | `Pet Sitting` | 60 | `true` | `true` |
| `MEET_GREET` | `Meet & Greet` | `Meet & Greet` | 45 | `false` | `true` |

The generator already serializes the entire service contract into both adapters. Phase 24A-2C.2D.1 subsequently hardened the constants validator to require a plain object, all five non-null required fields, nonempty string labels, a finite positive integer duration, and exact booleans for every canonical entry. It also hardened adapter validation to prove complete ordered equality among canonical, web, and mobile `SERVICE_TYPES`. No contract property/value, generator, or generated adapter changed.

## 3. Complete Static Usage Inventory

### 3.1 Shared and Generated Layers

| Location | Current behavior | Phase 24A-2C.2 disposition |
|---|---|---|
| `shared/constants/service-types.json` | Defines seven canonical identifiers and their label, duration, intake, and mobile metadata. | Read-only for 2C.2A. |
| `shared/generate-contract-adapters.mjs` | Emits complete `SERVICE_TYPES` objects into both platform adapters. | No change or regeneration. |
| `shared/validate-constants.mjs` | Validates service JSON, identifier format/uniqueness, and the complete five-field canonical service shape. | Hardened in approved 2C.2D.1 without changing contract values. |
| `shared/validate-contract-adapters.mjs` | Validates adapter presence, complete canonical/web/mobile `SERVICE_TYPES` equality, existing `PET_FIELDS` parity, and deterministic generation. | Hardened in approved 2C.2D.1; generator and adapters remain unchanged. |
| `web/src/generated/contracts.js` | Exports the canonical web `SERVICE_TYPES` object. | Import from here in 2C.2A; do not edit generated output. |
| `mobile/src/contracts/generatedContracts.ts` | Exports the canonical mobile `SERVICE_TYPES` object. | No 2C.2A consumption or edit. |
| `web/tests/contracts.test.jsx`, `mobile/__tests__/generatedContracts.test.ts` | Prove that representative service entries are exported. | Regression only; no 2C.2A test edit required. |

### 3.2 Web Usage

| Location | Current service-type usage | Planned disposition |
|---|---|---|
| `web/src/components/AdminDashboard.jsx` — `getServiceLabel` (current lines 466–477) | Seven-entry case-sensitive long-label map; blank-like values return `UNKNOWN SERVICE`; unknown identifiers have underscores replaced with spaces and each segment's first character uppercased without lowercasing the remainder. Used in request cards, details, search-label matching. | **2C.2A:** replace known-value map lookup with `SERVICE_TYPES.services[serviceType]?.labelLong`; preserve current case-sensitive lookup and fallback exactly. |
| `AdminDashboard.jsx` — dispatch export `FRIENDLY_SERVICES` / `getFriendlyService` (current lines 1970–1982) | Seven-entry short-label map; lookup is case-insensitive; unknown nonblank values are returned exactly; blank-like values become `''`. | **2C.2A:** replace known-value map lookup with `SERVICE_TYPES.services[key]?.label`; preserve current fallback exactly. |
| `AdminDashboard.jsx` — New Visit selector (current lines 5693–5706) | Static seven-option selector. Values/order are `PET_SITTING`, `WALK_30MIN`, `WALK_60MIN`, `DROPIN_1HR`, `DROPIN_3HR`, `OVERNIGHT`, `MEET_GREET`; visible text matches `labelLong`. Default is `PET_SITTING`. | **2C.2A eligible:** keep seven explicit `<option>` elements and source only their text from explicit `labelLong` properties. Do not iterate or filter the contract. |
| `AdminDashboard.jsx` — New Visit payload (current line 2889) | Sends `newVisitForm.service_type` unchanged. | Preserve exactly; assert payload parity. |
| `AdminDashboard.jsx` — workflow classification (current line 295) | Local array classifies four identifiers as visit bookings when other metadata matches. | Excluded; classification is behavior, not display-label wiring. |
| `AdminDashboard.jsx` — raw request backup export (current line 2110) | Writes raw `service_type` to the requests worksheet. | Excluded; preserve raw export value. |
| `web/src/components/MasterScheduler.jsx` | Static four-option service filter remains unchanged. Phase 2C.2B.1 now uses a shared exact-known-label resolver only for desktop service-only visit cards and pending-intake `service_type`; truthy `window_type` remains raw and mobile visit/time behavior remains unchanged. | 2C.2B.1 locally validated and independently reviewed; filter membership/equality, window precedence, raw identifiers, callbacks, scheduling, and grouping remain unchanged. |
| `web/src/components/IntakeForm.jsx` | Phase 2C.2B.2A now derives six canonical options from generated `SERVICE_TYPES` where `availableInIntake === true`, keeps contract order and the `PET_SITTING` default, and submits `formData.service_type` unchanged. | Locally validated and reviewed, complete locally, and not deployed; legacy `DOG_WALKING` remains read-compatible and unmapped. |
| `web/src/components/CareCard.jsx` | Phase 2C.2B.2B removes the ineffective editable PET Service Type selector. Visit Details remains read-only, preferring request `_originItem.service_type` and using historical `pet.service_type` only as fallback; the existing helper supplies canonical `labelLong` and three approved aliases, unresolved nonblank values remain raw, and missing/blank values display `Not Specified`. `service_type` is explicitly absent from `onUpdate` PET payloads. | Locally validated and independently reviewed; correction complete and not deployed. No request editor, PET-level service preference, backend source, persistence, API-client, contract, adapter, mobile, scheduling, notification, or production-data change. |
| `web/src/components/ClientPortal.jsx` | Phase 2C.2B.1 now uses canonical `labelLong` and exact display aliases `DOG_WALKING` → `Daily Dog Walking`, `WALKING` → `Dog Walking`, and `OTHER` → `Other`; unresolved values retain exact underscore-only, case, whitespace, and `Pet Care Visit` fallbacks. | Locally validated and independently reviewed; fetching, state, cancellation identifiers, payloads, navigation, and request objects remain unchanged. |

No existing web test is focused on AdminDashboard service labels. Existing real-component AdminDashboard coverage is primarily in `web/tests/ClientDrawerEditorConsolidation.test.jsx` and `web/tests/GoogleCalendarRBAC.test.jsx`. A dedicated `web/tests/AdminDashboardServiceTypes.test.jsx` is therefore the narrowest proposed characterization and regression location for 2C.2A.

### 3.3 Mobile Usage

There is no mobile service selector. Four separate generic formatters currently split on underscores and uppercase each segment's first character without lowercasing the remainder:

| Location | Display call |
|---|---|
| `mobile/src/screens/BookingsScreen.tsx` (current lines 18–19, 127) | Booking-card service detail |
| `mobile/src/components/RequestCard.tsx` (current lines 59–64, 178) | Request-card service detail |
| `mobile/src/screens/RequestDetailScreen.tsx` (current lines 192–197, 308) | Request-detail service metadata |
| `mobile/src/screens/ScheduleScreen.tsx` (current lines 46–51, 263) | Schedule service detail |

Phase 2C.2C subsequently replaced these four duplicated formatters with the reviewed type-safe mobile helper. Exact canonical identifiers now use generated short `label`; every noncanonical, unknown, case-variant, nullish, and blank input preserves the exact prior formatter result. No selector, payload, navigation, capability, build, or distribution behavior changed.

`mobile/src/types/index.ts` types `service_type` as an unrestricted string. `mobile/__tests__/BookingsScreen.test.tsx` uses a `PET_SITTING` fixture but does not establish complete formatter parity, while `mobile/__tests__/generatedContracts.test.ts` proves only representative `SERVICE_TYPES` export availability. These remain unchanged in 2C.2A.

### 3.4 Backend Usage

| Location | Current behavior | Boundary |
|---|---|---|
| `src/backend/handlers/intake_handler.py` | Public/client and admin-created paths store `body.get('service_type', 'PET_SITTING')` without enforcing a canonical fixed allowlist. | Backend validation/normalization excluded. |
| `src/backend/handlers/job_handler.py` | Copies the parent request `service_type` unchanged into jobs. | Excluded. |
| `src/backend/common/google_calendar.py` | Owns `SERVICE_DURATIONS`, `SERVICE_COLORS`, and `FRIENDLY_SERVICE_NAMES`; unknown types fall back to 60 minutes, color `8`, and the raw identifier. | Remains authoritative; no calendar change. |
| `src/backend/common/notifications/templates.py` | Uses long-friendly labels for the seven canonical values; null-like values default to `PET_SITTING`; unknown identifiers are underscore-split/title-cased. | Notification wording excluded. |
| `src/backend/common/notifications/service.py` | Passes stored `service_type` values into notification contexts and preserves the field in relevant normalized event data. | Notification pipeline excluded. |
| `src/backend/common/status.py` | Uses a local service-type subset as one workflow-classification heuristic. | Workflow behavior excluded. |

Existing relevant backend regression files include `tests/backend/test_r7d_calendar_hardening.py`, `tests/backend/test_r6g_calendar_all_day.py`, `tests/backend/test_r6a_templates.py`, `tests/backend/test_r6b_templates.py`, `tests/backend/test_intake_validation.py`, and `tests/backend/test_r6f_offline_booking.py`.

Repository-wide search also found `service_type` as fixture/pass-through data in `tests/backend/test_public_intake_tenant_routing.py`, `tests/backend/test_r11e_tenant_enforcement.py`, `tests/backend/test_r6g_calendar_retry.py`, `tests/backend/test_r6g_calendar_token.py`, `tests/backend/test_r7a_optional_email.py`, `tests/backend/test_r7e_multi_day_jobs.py`, `tests/backend/test_r7j_notification_content_polish.py`, and `tests/backend/test_r8u_staff_cleanup.py`. Those files do not create an additional application label owner and are unchanged by 2C.2A.

## 4. AdminDashboard Label Parity Matrix

| Identifier | Contract `labelLong` | Current `getServiceLabel` | Contract `label` | Current dispatch export | Static selector text | Parity |
|---|---|---|---|---|---|---|
| `WALK_30MIN` | `30-Minute Walk` | `30-Minute Walk` | `30-Min Walk` | `30-Min Walk` | `30-Minute Walk` | Exact |
| `WALK_60MIN` | `60-Minute Walk` | `60-Minute Walk` | `60-Min Walk` | `60-Min Walk` | `60-Minute Walk` | Exact |
| `DROPIN_1HR` | `1-Hour Drop-in` | `1-Hour Drop-in` | `1-Hour Drop-in` | `1-Hour Drop-in` | `1-Hour Drop-in` | Exact |
| `DROPIN_3HR` | `3-Hour Drop-in` | `3-Hour Drop-in` | `3-Hour Drop-in` | `3-Hour Drop-in` | `3-Hour Drop-in` | Exact |
| `OVERNIGHT` | `Overnight Care` | `Overnight Care` | `Overnight Care` | `Overnight Care` | `Overnight Care` | Exact |
| `PET_SITTING` | `Pet Sitting` | `Pet Sitting` | `Pet Sitting` | `Pet Sitting` | `Pet Sitting` | Exact |
| `MEET_GREET` | `Meet & Greet` | `Meet & Greet` | `Meet & Greet` | `Meet & Greet` | `Meet & Greet` | Exact |

The selector order is intentionally different from canonical JSON object order. Static label sourcing is safe only if the seven explicit option elements remain in their current order.

## 5. Noncanonical Identifier Findings

- At this plan's original checkpoint, `IntakeForm.jsx` could submit `DOG_WALKING`; Phase 2C.2B.2A subsequently stopped new customer-intake emission without mapping legacy values.
- Before Phase 2C.2B.2B, `CareCard.jsx` could submit `WALKING` and `OTHER` in an ignored PET update field. The local candidate removes that selector and explicitly omits top-level `service_type` from PET update payloads without mapping or rewriting historical values.
- The intake backend stores the supplied value without a canonical fixed allowlist.
- Job creation propagates the stored value unchanged.
- AdminDashboard, ClientPortal, mobile, notifications, and Google Calendar each have different unknown-value fallback behavior.

These findings prohibit treating selector generation or backend allowlisting as a label-only change.

## 6. Data-Safety Clarification

Noncanonical service identifiers may exist in stored records because current frontend workflows can submit them and the backend does not enforce the shared allowlist. Their current presence in production has not been verified. No production-data inspection or migration is included in this phase.

This plan is based only on committed static repository evidence. It does not claim that `DOG_WALKING`, `WALKING`, `OTHER`, or any other noncanonical identifier was found in production.

## 7. Unknown-Value and Blank-Value Fallback Contract

The following table captures current behavior that must be characterized before and preserved after 2C.2A:

| Input | `getServiceLabel` long-display/search | Dispatch `getFriendlyService` | ClientPortal generic display | Mobile generic display |
|---|---|---|---|---|
| `DOG_WALKING` | `DOG WALKING` | `DOG_WALKING` | `DOG WALKING` | `DOG WALKING` |
| `WALKING` | `WALKING` | `WALKING` | `WALKING` | `WALKING` |
| `OTHER` | `OTHER` | `OTHER` | `OTHER` | `OTHER` |
| `HOUSE_SITTING` (representative unknown) | `HOUSE SITTING` | `HOUSE_SITTING` | `HOUSE SITTING` | `HOUSE SITTING` |
| `null` | `UNKNOWN SERVICE` | empty string | `Pet Care Visit` | empty string |
| `undefined` | `UNKNOWN SERVICE` | empty string | `Pet Care Visit` | empty string |
| empty string | `UNKNOWN SERVICE` | empty string | `Pet Care Visit` | empty string |

Phase 24A-2C.2A must use the existing fallback expressions after a contract hit is attempted:

- Long AdminDashboard context: blank-like input remains `UNKNOWN SERVICE`; unknown nonblank input retains its existing case while underscores become spaces and segment initials are uppercased.
- Short dispatch-export context: case-insensitive canonical lookup remains; unknown nonblank input remains the original value; blank-like input remains `''`.

No new user-facing fallback wording is permitted.

## 8. Duration and Scheduling Boundary

Canonical `durationMinutes` exactly mirrors the current backend `SERVICE_DURATIONS` values for all seven canonical identifiers. The backend remains the runtime authority for Google Calendar scheduling.

Phase 24A-2C.2A must not import duration metadata, change `scheduled_duration`, change unknown-type 60-minute fallback behavior, change `SERVICE_COLORS`, change `FRIENDLY_SERVICE_NAMES`, or change calendar summaries/descriptions. Duration centralization, calendar formatting, and backend use of the shared contract require separate 2C.2D planning and approval.

## 9. Intake-Availability and Static-Selector Boundary

`availableInIntake` is contract metadata, not an authorization to alter existing selectors:

- `MEET_GREET` is `false` but is present in the AdminDashboard New Visit selector.
- The public `IntakeForm` now includes the six canonical `availableInIntake: true` services in contract order after the separately approved Phase 2C.2B.2A implementation.
- CareCard formerly had a different four-option membership; Phase 2C.2B.2B removes that ignored PET-field selector and retains compatibility display only.

### Static label sourcing — eligible for 2C.2A

Keep each current AdminDashboard option value, element, order, membership, and default exactly as written. Only replace literal visible text with the corresponding explicit `SERVICE_TYPES.services.<ID>.labelLong` property. This remains display-label wiring.

### Dynamic option generation — excluded from 2C.2A

Do not iterate `SERVICE_TYPES.services`, filter on `availableInIntake`, sort contract keys, add/remove options, or share one generated option list across contexts. Those operations can change membership/order and belong to 2C.2B.

## 10. Mobile Boundary

Phase 24A-2C.2A makes no mobile change. Phase 24A-2C.2C must separately decide which canonical label property fits each of the four mobile contexts and must preserve generic fallback behavior for noncanonical and unknown values.

Mobile 2C.2C must not introduce selectors, change payloads, alter feature availability, or claim build/distribution authorization. It requires separate local implementation approval, complete mobile regression review, and a separate later approval for any EAS build or distribution.

## 11. Proposed Subphases

### Phase 24A-2C.2A — Web Admin Display-Label Contract Wiring

**Approval:** `ROADMAP_ONLY_NO_EXPLICIT_APPROVAL`
**Risk:** LOW, provided characterization passes before source changes.

Proposed implementation files:

- `web/src/components/AdminDashboard.jsx`
- new focused behavioral coverage: `web/tests/AdminDashboardServiceTypes.test.jsx`
- a Phase 24A-2C.2A release record and necessary continuity updates

Exact bounded source scope:

1. Import `SERVICE_TYPES` from `web/src/generated/contracts.js`.
2. Replace only the seven-entry `getServiceLabel` map lookup with the case-sensitive `SERVICE_TYPES.services[serviceType]?.labelLong` lookup while preserving current blank and unknown fallbacks.
3. Replace only `FRIENDLY_SERVICES` lookup with `SERVICE_TYPES.services[key]?.label` while preserving uppercase lookup and raw/blank fallback behavior.
4. Keep the AdminDashboard New Visit selector static and in its existing order; optionally replace only its seven text nodes with explicit `labelLong` properties because direct parity is proven.
5. Preserve `PET_SITTING` as the default and preserve `newVisitForm.service_type` in the exact existing payload.

Explicit 2C.2A exclusions:

- no dynamic option generation or `availableInIntake` filtering;
- no option value, membership, order, or default change;
- no workflow-classification array change;
- no raw backup-export value change;
- no service identifier, payload, or stored-value change;
- no IntakeForm, CareCard, MasterScheduler, ClientPortal, or mobile change;
- no backend, duration, scheduling, calendar, color, notification, contract, adapter, generator, or validator change.

### Phase 24A-2C.2B — Selector Membership and Availability Normalization

**Status:** `LOCALLY COMPLETE FOR APPROVED FRONTEND SCOPE / BACKEND POLICY, PRODUCTION ASSESSMENT, AND MIGRATION DEFERRED / NOT DEPLOYED`.

**Current reconciliation (2026-08-05):** Documentation-only planning completed in `docs/planning/phase-24a-2c2b-selector-normalization-design.md`. Phase 24A-2C.2B.1 display compatibility, 2B.2A customer IntakeForm canonical membership, and 2B.2B CareCard Option 2 are locally validated and reviewed at their stated gates. Phase 2B.2C is also locally validated and independently reviewed: MasterScheduler retains its static `ALL` default and exact case-sensitive `service_type` equality while adding the missing canonical `WALK_60MIN`, `PET_SITTING`, and `MEET_GREET` filter choices. Kiro returned `READY_FOR_PHASE_24A_2C_2B_2C_DOCUMENTATION_AND_LOCAL_CLOSEOUT` with no blocking correction. Phase 2C.2B is therefore locally complete for the approved frontend scope only. Backend accepted-identifier policy, backend allowlisting/rejection, legacy normalization, production-data assessment, migration/deprecation, scheduler-specific contract metadata, additional product/service availability decisions, and deployment remain deferred and unapproved.

The exact final MasterScheduler filter is `ALL` — All Services; `WALK_30MIN` — 30m Walk; `WALK_60MIN` — 60m Walk; `DROPIN_1HR` — 1hr Drop-in; `DROPIN_3HR` — 3hr Drop-in; `OVERNIGHT` — Overnight; `PET_SITTING` — Pet Sitting; `MEET_GREET` — Meet & Greet. `window_type` remains outside filtering, pending intake remains independent, and desktop/mobile continue to consume the same filtered scheduler collection. No legacy, unknown, blank, null, or undefined filter option was added.

This phase must separately decide how to handle `DOG_WALKING`, `WALKING`, `OTHER`, canonical `availableInIntake`, current selector memberships/orders, legacy-value display, future backend validation, and possible data normalization. It must not presume that a production migration is needed.

Before any production inspection or mutation, create a separate read-only data-safety design and obtain separate explicit Matthew approval. Any later migration requires its own evidence, rollback design, authorization, and production safeguards.

### Phase 24A-2C.2C — Mobile Service-Label Wiring

**Status:** `LOCALLY VALIDATED AND REVIEWED / NOT BUILT OR DISTRIBUTED`.

The four former `formatServiceType` owners now use one type-safe helper with generated canonical short labels and exact legacy fallback preservation. No selector, payload, capability, build, or distribution change is included.

### Phase 24A-2C.2D — Duration and Scheduling Metadata

**Status:** `PARTIALLY COMPLETE / 2D.1 LOCALLY VALIDATED AND INDEPENDENTLY REVIEWED / 2D.2 LOCALLY VALIDATED AND INDEPENDENTLY REVIEWED WITH NO RUNTIME CONSUMPTION / 2D.3–2D.4 DEFERRED AND UNAPPROVED / NOT DEPLOYED`.

Phase 2D.1 is validation and parity hardening only. It strengthens canonical service metadata checks, proves complete ordered equality among canonical/web/mobile `SERVICE_TYPES`, and adds 48 focused backend tests against real canonical JSON and real `_build_event_body()` behavior using synthetic records without Google API calls. It changes no runtime behavior.

Exact canonical duration and short-label parity is now characterized as `WALK_30MIN` 30 / `30-Min Walk`; `WALK_60MIN` 60 / `60-Min Walk`; `DROPIN_1HR` 60 / `1-Hour Drop-in`; `DROPIN_3HR` 180 / `3-Hour Drop-in`; `OVERNIGHT` 720 / `Overnight Care`; `PET_SITTING` 60 / `Pet Sitting`; and `MEET_GREET` 45 / `Meet & Greet`. Numeric and numeric-string `scheduled_duration` overrides, falsey fallthrough, exact case-sensitive unresolved 60-minute/color-`8` fallback behavior, canonical colors, exclusive-next-day all-day events, and the existing 08:00/11:00/14:00/17:00 window starts are characterized without normalization or centralization.

Kiro independently verified the exact three-file candidate and reproduced 18 shared constant checks, 7 adapter checks, 48 focused parity tests, and 100 combined affected backend tests. It returned `READY_FOR_PHASE_24A_2C_2D_1_DOCUMENTATION_AND_LOCAL_CLOSEOUT`; no blocking correction was identified.

Phase 2D.2 extends the existing generator to emit `src/backend/common/generated_service_types.py` from the cleaned canonical `SERVICE_TYPES` root while leaving web and mobile output byte-identical. The generated module contains only header comments and one plain-dictionary `SERVICE_TYPES` assignment with exact canonical identifiers, order, camelCase fields, strings, positive integers, and booleans. It has no imports, functions, helpers, derived maps, aliases, normalization, or side effects, and no runtime backend source imports it.

Adapter validation now safely extracts the Python literal through a standard-library subprocess using `ast.parse`, a strict direct-assignment check, `ast.literal_eval`, and JSON serialization without `eval`, arbitrary execution, or generated-module import. Complete equality, membership, order, fields, values, and types are proved across canonical, web, mobile, and backend targets. Deterministic zero-diff validation covers all three generated outputs. Three focused backend tests prove real import, canonical equality/order/types, module location, and the absence of static or literal dynamic runtime consumers. Kiro reproduced 18 shared constant checks, 8 adapter checks, deterministic three-target generation, web/mobile byte parity, and 103 combined affected backend tests, then returned `READY_FOR_PHASE_24A_2C_2D_2_DOCUMENTATION_AND_LOCAL_CLOSEOUT` with no blocking correction.

Remaining subphases require separate approval:

- **2D.3:** calendar runtime duration and friendly-name wiring;
- **2D.4:** optional calendar color metadata.

The backend remains the runtime authority. Backend identifier policy, production assessment, legacy normalization, migration/deprecation, deployment review, and existing-event resynchronization also remain deferred and unapproved.

## 12. Phase 24A-2C.2A Test Strategy

### 12.1 Pre-change characterization

Add focused behavioral tests against the real `AdminDashboard` before changing source. Mock authentication, API calls, browser download APIs, and SheetJS boundaries. Do not use source-string assertions.

Characterization must prove:

1. All seven `getServiceLabel` outputs are byte-for-byte identical to current UI/search labels.
2. Dispatch export uses the seven current short labels.
3. `DOG_WALKING`, `WALKING`, `OTHER`, `HOUSE_SITTING`, and a case-variant identifier preserve the current fallback behavior.
4. Null, undefined, and empty-string values preserve current long-display and export behavior without blanks, exceptions, or the string `undefined` where those do not occur today.
5. The New Visit selector values, text, membership, and order are exactly unchanged.
6. The initial New Visit `service_type` remains `PET_SITTING`.
7. Submitting each existing selector choice sends the exact selected identifier unchanged in `createAdminBooking` payloads.

### 12.2 Post-change parity and regression

The same tests must pass without expectation changes after contract lookup wiring. Also prove:

- `labelLong` is used only for current long-label/selector contexts.
- `label` is used only for the dispatch-friendly context.
- no duration or availability metadata is read by AdminDashboard.
- no filtering, sorting, option generation, calendar action, or notification action occurs.
- IntakeForm, CareCard, MasterScheduler, ClientPortal, mobile, shared contracts, and generated adapters remain unchanged.

### 12.3 Actual repository commands

From repository root:

```powershell
node shared/validate-constants.mjs
node shared/validate-contract-adapters.mjs
```

From `web/`:

```powershell
npx vitest run tests/AdminDashboardServiceTypes.test.jsx
npx vitest run tests/ClientDrawerEditorConsolidation.test.jsx tests/GoogleCalendarRBAC.test.jsx
node --test tests/phase1b3.test.js
npm run test:legacy
npx vitest run
npm run build
npx eslint src/components/AdminDashboard.jsx tests/AdminDashboardServiceTypes.test.jsx
npm run lint
```

From `mobile/` for regression only:

```powershell
npm test
npm run typecheck
```

Relevant existing backend calendar regression command documented by the repository, to be used only as an unchanged-backend regression when implementation is approved:

```powershell
python -m pytest tests/backend/test_r7d_calendar_hardening.py tests/backend/test_r6g_calendar_all_day.py -v
```

No backend command should be added merely for symmetry. Report the existing full-web lint baseline separately and do not remediate unrelated findings.

## 13. Current Approval and Completion Gates

| Scope | Classification |
|---|---|
| Phase 24A-2C.2 documentation planning | `APPROVED FOR DOCUMENTATION ONLY` |
| Phase 24A-2C.2A implementation | `LOCALLY VALIDATED AND REVIEWED / NOT DEPLOYED` |
| Phase 24A-2C.2B | `LOCALLY COMPLETE FOR APPROVED FRONTEND SCOPE / BACKEND POLICY, PRODUCTION ASSESSMENT, AND MIGRATION DEFERRED / NOT DEPLOYED` |
| Phase 24A-2C.2C | `LOCALLY VALIDATED AND REVIEWED / NOT BUILT OR DISTRIBUTED` |
| Phase 24A-2C.2D.1 | `LOCALLY VALIDATED AND INDEPENDENTLY REVIEWED / PARITY AND VALIDATOR HARDENING COMPLETE / NO RUNTIME BEHAVIOR CHANGE / NOT DEPLOYED` |
| Phase 24A-2C.2D.2 | `LOCALLY VALIDATED AND INDEPENDENTLY REVIEWED / GENERATED BACKEND SERVICE-METADATA ADAPTER COMPLETE / NO RUNTIME CONSUMPTION / NOT DEPLOYED` |
| Phase 24A-2C.2D.3–2D.4 | `DEFERRED / NOT APPROVED` |
| Production deployment | `NOT APPROVED` |
| Mobile build or distribution | `NOT APPROVED` |
| Production-data inspection or migration | `NOT APPROVED` |

Any remaining implementation must begin from a separately verified clean checkpoint and only after Matthew gives explicit approval for the selected subphase.

## 14. Risk and Rollback Boundaries

### Phase 24A-2C.2A

Risk is **LOW** only after exact label and fallback characterization. Its rollback boundary is the bounded AdminDashboard source/test commit:

- revert `AdminDashboard.jsx`, its focused service-label test, and phase release documentation;
- no contract rollback;
- no adapter regeneration rollback;
- no backend rollback;
- no data rollback.

Higher-risk deferred areas are selector membership, availability filtering, backend validation, duration scheduling, legacy-value normalization, and any production-data migration.

## 15. Deferred Work and Explicit Exclusions

Phase 2C.2B.1 validation: 37/37 focused helper/owner tests, 11/11 AdminDashboard/IntakeForm exclusion regressions, 202/202 complete Vitest across 18 files, 99/99 legacy / 301 unique web tests, 18/18 shared constants, 6/6 deterministic adapter checks, and a successful 109-module Vite build. New files lint cleanly; ClientPortal and MasterScheduler retain their exact pre-change 2-error/1-warning and 1-error/0-warning baselines; complete web lint remains 51 errors and 9 warnings with zero candidate-introduced findings. Kiro independently reproduced the required matrix and returned `READY_FOR_LOCAL_PHASE_24A_2C_2B_1_CLOSEOUT` with no correction required. No pre-existing ClientPortal-focused suite exists beyond the new rendered-owner coverage.

Phase 2C.2B.2B final validation: 22/22 focused CareCard tests, 37/37 existing service-label/owner regressions, 11/11 AdminDashboard/IntakeForm regressions, 224/224 complete Vitest across 19 files, 99/99 legacy / 323 unique web tests, 23/23 staff/admin PET backend tests, 18/18 customer PET backend tests, 18/18 shared constants, 6/6 deterministic adapter checks, and a successful 109-module Vite build (`index-C-Rflmrt.js`, `index-bVFIMo3n.css`, `usmh-logo-CrRnxp7-.png`). The new test is lint-clean; CareCard retains its exact pre-change 6-error/1-warning baseline, complete web lint remains 51 errors/9 warnings, and candidate-introduced lint is zero. Backend source was unchanged; the added tests characterize existing ignored/rejected behavior only. Kiro independently confirmed the exact 10-file candidate and returned `READY_FOR_LOCAL_PHASE_24A_2C_2B_2B_CLOSEOUT` with no blocking correction. No production data, deployment, or distribution action occurred; passing tests and local closeout do not authorize deployment.

Phase 2C.2B.2C final validation: 15/15 focused ServiceTypeDisplayOwners, 29/29 service-label helper, 22/22 CareCard, 11/11 AdminDashboard/IntakeForm, 231/231 complete Vitest across 19 files, 99/99 legacy / 330 unique web, 18/18 shared constants, 6/6 deterministic adapter checks, and a successful 109-module Vite build (`index-C5FqHoe-.js`, `index-bVFIMo3n.css`, `usmh-logo-CrRnxp7-.png`). The changed test is lint-clean; MasterScheduler retains its pre-existing unused `onAssign` error, complete lint remains 51 errors/9 warnings, and candidate-introduced lint is zero. Kiro independently verified the exact two-file implementation candidate and returned `READY_FOR_PHASE_24A_2C_2B_2C_DOCUMENTATION_AND_LOCAL_CLOSEOUT` with no blocking correction. No deployment or production-data access occurred; passing tests and local closeout do not authorize deployment.

Phase 2C.2D.3 final validation: `google_calendar.py` imports `SERVICE_TYPES` from `common.generated_service_types` and derives `SERVICE_DURATIONS` and `FRIENDLY_SERVICE_NAMES` (`label`) directly from generated contract metadata. Exact symbol names, `_build_event_body()`, handwritten `SERVICE_COLORS`, and fallback logic are preserved. 11 new edge characterization tests in `test_phase24a_service_duration_contract_parity.py` preserve existing `scheduled_duration` edge handling. AST inspection proves `google_calendar.py` is the exactly-one runtime consumer of generated metadata in backend source. Validation: 18/18 constants, 8/8 adapters, 6/6 generated metadata tests, 59/59 duration parity tests, 18/18 calendar hardening, 12/12 all-day, 22/22 multi-day, and 117/117 combined affected backend tests. Kiro independently verified the candidate and returned `READY_FOR_PHASE_24A_2C_2D_3_DOCUMENTATION_AND_LOCAL_CLOSEOUT`. No deployment or production-data access occurred; passing tests and local closeout do not authorize deployment.

Deferred work:

- request-status planning/wiring outside this service-type plan;
- backend accepted-identifier policy, legacy normalization, production assessment, migration/deprecation, scheduler-specific contract metadata, and additional product/service availability decisions beyond the locally completed approved 2C.2B frontend scope;
- 2C.2D.4 optional calendar color metadata;
- backend identifier policy, production assessment, legacy normalization, migration/deprecation, deployment review, and existing-event resynchronization;
- staff/mobile feature changes unrelated to label display;
- production inspection or migration design;
- production deployment, mobile build/distribution, and Ryan testing.

This planning phase does not authorize or perform application source changes, tests, contract edits, adapter regeneration, generator/validator changes, backend changes, API Gateway or Terraform changes, production API calls, production-data inspection or mutation, web deployment, S3/CloudFront actions, EAS builds, app-store/tester changes, Cognito changes, tenant changes, Stripe changes, Google Calendar changes, or unrelated lint remediation.

---

**PARTIALLY COMPLETE LOCALLY / 2C.2A COMPLETE / 2C.2B LOCALLY COMPLETE FOR APPROVED FRONTEND SCOPE / 2C.2C COMPLETE / 2C.2D.1 COMPLETE / 2C.2D.2 COMPLETE / 2C.2D.3 COMPLETE / 2C.2D.4 DEFERRED / NOT DEPLOYED OR DISTRIBUTED**
