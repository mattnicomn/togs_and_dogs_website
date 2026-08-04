# Phase 24A-2C.2B.1 — Web Service-Type Display Compatibility

**Date:** 2026-08-04

**Status:** **LOCALLY VALIDATED AND INDEPENDENTLY REVIEWED / WEB DISPLAY COMPATIBILITY COMPLETE / NOT DEPLOYED**

## Approval and scope

Matthew explicitly approved a bounded local web display-only candidate for ClientPortal booking headings, MasterScheduler desktop visit cards when their displayed value originates from `service_type`, and MasterScheduler pending-intake cards. Exact canonical identifiers use generated `SERVICE_TYPES.services[value].labelLong`; exact legacy values use these display aliases:

| Stored identifier | Display label |
|---|---|
| `DOG_WALKING` | `Daily Dog Walking` |
| `WALKING` | `Dog Walking` |
| `OTHER` | `Other` |

These are display aliases only. They do not map a legacy identifier to a canonical identifier, infer duration, trim or normalize input, or modify records.

## Helper and owner behavior

New `web/src/utils/serviceLabels.js` exports only `getKnownServiceTypeLabel(value)`. It uses exact case-sensitive own-property checks for generated canonical services and a frozen private alias table. Canonical hits return `labelLong`; exact alias hits return the approved wording; unknown, case-variant, nullish, empty, whitespace-only, prototype-like, and metadata-like inputs return `undefined` so each owner retains its prior fallback.

- ClientPortal uses a helper result only for an exact known value. Every unresolved value still uses `req.service_type?.replace(/_/g, ' ') || 'Pet Care Visit'`: unknown underscores are replaced without capitalization, case variants preserve case, null/undefined/empty display `Pet Care Visit`, and whitespace remains whitespace.
- MasterScheduler uses the helper only for desktop service-only visit output and pending-intake `service_type`. A truthy `job.window_type` remains raw, including `EXACT_TIME` and overlapping `WALK_30MIN`, `DROPIN_1HR`, `DROPIN_3HR`, and `OVERNIGHT` values. Falsey `window_type` retains the original fallthrough to `service_type`; unresolved services remain raw.
- Mobile scheduler visit cards still do not display service type. Their time precedence remains `start_time`, `window_start`, `window_type`, then empty.

Original service identifiers, request/job objects, payloads, persistence, filter membership and exact equality, callbacks, navigation, scheduling, grouping, search, workflow classification, notifications, and exports remain unchanged.

## Tests and validation

- New helper and real-owner coverage: 37/37 passed across `serviceLabels.test.jsx` and `ServiceTypeDisplayOwners.test.jsx`.
- Existing AdminDashboard/IntakeForm exclusion regressions: 11/11 passed across 2 files.
- Complete Vitest: 202/202 passed across 18 files.
- Legacy web: 99/99 passed across 15 suites.
- Unique complete web total: 301 passed.
- Shared constants: 18/18 passed.
- Generated adapter validation: 6/6 passed, including deterministic zero second diff.
- Vite 8.0.8 build: passed with 109 modules transformed; assets `index-mPUri6lj.js`, `index-bVFIMo3n.css`, and `usmh-logo-CrRnxp7-.png`.
- Helper plus both new tests: 0 lint errors and 0 warnings.
- ClientPortal retains its exact pre-change 2-error/1-warning lint baseline.
- MasterScheduler retains its exact pre-change 1-error/0-warning lint baseline.
- Complete web lint retains the established 51-error/9-warning baseline. Candidate-introduced lint: 0 errors and 0 warnings.

No pre-existing focused ClientPortal suite exists; the new rendered-owner suite is the applicable real-component coverage. The complete Vitest run retained the existing jsdom navigation notice. The build retained the existing `optimizeDeps.esbuildOptions` deprecation and large-chunk warnings.

## Independent review

Kiro independently reviewed the complete 11-file candidate and returned `READY_FOR_LOCAL_PHASE_24A_2C_2B_1_CLOSEOUT`. It independently reproduced 18 shared-constant tests, 6 adapter checks with deterministic regeneration, 37 focused tests, 99 legacy tests, 202 complete Vitest tests / 301 unique web tests, the successful Vite build, and zero candidate-introduced lint findings. It confirmed that truthy `window_type` remains raw outside the helper, unknown and case-variant values retain their owner-specific fallbacks, and ClientPortal/MasterScheduler retain their pre-existing lint baselines. No blocking or non-blocking correction was required.

## Scope audit

Unchanged: AdminDashboard, CareCard, IntakeForm, API clients, CSS, shared service contract, generated adapters, generators, validators, backend, mobile, dependencies, lockfiles, filter membership, exports, navigation, scheduling, notifications, infrastructure, Cognito, tenants, Stripe, Google Calendar, and production data.

No production-data inspection, production API call, deployment, S3 sync, CloudFront invalidation, Terraform action, mobile build/distribution, tester change, or notification action occurred. Ignored build output is not part of the candidate. Passing tests and local closeout do not authorize deployment.

Phase 24A-2C.2 and Phase 24A-2C.2B remain partially complete locally. CareCard cleanup, backend accepted-identifier policy, production assessment, migration/deprecation, and Phase 24A-2C.2D remain deferred and unapproved. The latest completed validated production release remains Phase 1B.5C-D.2.

---

**LOCALLY VALIDATED AND INDEPENDENTLY REVIEWED / WEB DISPLAY COMPATIBILITY COMPLETE / NOT DEPLOYED**
