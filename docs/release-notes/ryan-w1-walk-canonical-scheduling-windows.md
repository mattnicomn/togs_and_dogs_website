# Ryan Cross-Platform Alignment W1 — 20-Minute Walk Canonical Scheduling Windows

**Date:** 2026-08-17
**Status:** COMMITTED / PUSHED / NOT DEPLOYED
**Starting SHA:** `66d6cc3e70d6edb5923f3eb94e6414840afc115b`

## Approved Decision

Matthew and Ryan approved one canonical scheduling model for each new `WALK_20MIN` request:

- duration: 20 minutes, confirmed;
- exactly one selected window;
- Morning: 06:30–09:30;
- Mid-day: 10:30–15:30;
- Evening: 18:00–21:30; and
- the same selected window applies to every selected date.

W1 does not introduce per-date independent windows, pricing, deposits, or a new payload field. New writes use `visit_windows` with exactly one canonical identifier and never use `visits_per_day`.

The backend also persists the same canonical ID in the existing singular `visit_window` compatibility mirror for downstream historical readers; Web and Mobile new-write payloads do not send that singular field.

## Previous Fallthrough

Before W1, the Walk contract had `allowedWindowIds: []` and `windowSelectionMode: unresolved`. Web customer, Web Admin, and Mobile omitted Walk windows. Backend normalization could fall back to `ANYTIME`; Walk jobs were not deterministic canonical-window children; and Calendar handled supplied Walk windows through legacy starts (08:00, 11:00, or 17:00) or all-day fallback.

## Local Implementation

- The shared service contract now gives `WALK_20MIN` the existing Morning/Mid-day/Evening window IDs and `windowSelectionMode: exactly_one`.
- Generated Web, Mobile, and Backend adapters were regenerated through the established deterministic generator.
- New Walk writes reject missing, multiple, duplicate, legacy, unknown, and `visits_per_day` input while historical reads remain untouched.
- One deterministic child job is created per selected date, carrying the same occurrence window, canonical start, stable job identity, and stable Calendar event identity.
- Calendar events start at 06:30, 10:30, or 18:00 and end exactly 20 minutes later.
- Web customer, Web Admin New Visit, and Mobile intake use contract-derived exactly-one controls, reset incompatible hidden state, include one `visit_windows` entry, omit `visits_per_day`, and show the friendly selected window in review where that review already exists.
- MasterScheduler continues to use the canonical service label and existing item handoff while displaying the occurrence window and scheduled start supplied by the child job.
- Assignment notification frequency and recipients are unchanged: the current assignment handler emits one `STAFF_ASSIGNED` and one `VISIT_SCHEDULED` notification for the assignment batch, not one pair per child.

## Compatibility and Boundaries

Historical `WALK_30MIN`, `WALK_60MIN`, `AFTERNOON`, `ANYTIME`, and legacy `visit_window` records remain readable. No migration or reinterpretation was added. Overnight hours/duration, pricing, deposit policy, legacy retirement, Stripe automation, Slice E, and Slice F remain unresolved or deferred.

Independent review returned `RYAN_W1_WALK_CANONICAL_SCHEDULING_IMPLEMENTATION_CORRECT`. W1 is committed and pushed, but it has not been deployed, built for Mobile, distributed, received by Ryan, or exercised against production data, Calendar, notifications, Cognito, Stripe, tenants, or public website systems.

## Local Validation

- shared constants: 23/23;
- generated adapter parity/determinism: 9/9;
- focused W1 backend: 20/20;
- Slice B backend regression: 31/31;
- R1 backend regression: 3/3;
- combined W1/Slice A/Slice B/R1 backend: 68/68;
- focused Web customer/Admin/Scheduler: 50/50;
- full Web Vitest: 284/284 across 22 files;
- legacy Web: 99/99;
- Web production build: success, 110 modules transformed;
- Mobile TypeScript: pass;
- focused Mobile Intake: 27/27;
- combined Mobile Intake/D1 regression: 33/33; and
- full Mobile: 127/127 across 13 suites.
