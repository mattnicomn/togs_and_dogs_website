# Ryan Slice E3B.1 — Mobile Visit Workflow Safety Remediation

**Date:** 2026-08-20
**Status:** ✅ IMPLEMENTED / VALIDATED / NOT DEPLOYED
**Distribution:** NOT INCLUDED IN CURRENT INTERNAL MOBILE BUILDS
**Starting SHA:** `8ce0615618e1795908634de570692f6a5c65ead7`

E3B.1 hardens the local Mobile Start/Complete workflow without changing the E3A backend, API/status contracts, Terraform, Web, Calendar, or notification semantics.

## Action identity and mutations

One Mobile resolver now supplies the child `job_id` for both **Start Visit** and **Complete Visit**. An authoritative occurrence wins; a supplied route `jobId` must match it, and the occurrence must belong to the displayed parent. Any mismatch fails safe with a refresh-required error and no mutation. Without authoritative occurrence data, one deduplicated legacy `job_id` remains actionable without a route ID; multiple possible child IDs remain blocked and are never inferred from date or array position.

A synchronous ref lock is acquired before either visit mutation awaits the network. Two immediate Start taps issue one request, and Complete cannot race an active Start or its reconciliation. Mounted-state and request-sequence guards prevent late Start/refetch and Complete responses from updating an obsolete screen. Start continues to display only server-returned or authoritatively refetched `started_at`/`started_by`; it creates no local success timestamp or `IN_PROGRESS` state. Complete continues to use the existing exact child endpoint, preserves visit notes, never calls parent review `COMPLETED`, and remains allowed without prior Start for safely identified legacy visits.

## Hydration failure

Schedule still performs the existing 1 + N exact-request hydration pattern. When one exact hydration fails, Mobile now marks that parent explicitly degraded and projects non-actionable placeholders for safely known `selected_dates × visit_windows`. Each placeholder has no child ID, remains refresh-required, and cannot expose Start/Complete. If list data cannot describe multiple windows, Mobile shows only the truthful known date/window representation and does not fabricate occurrences. Batching the 1 + N reads remains a future performance optimization, outside this safety slice.

## Validation

- focused E3B.1 RequestDetail, Schedule, and occurrence suites: 19/19;
- related Mobile integration coverage: 23/23;
- Mobile generated contracts/colors: 15/15;
- full Mobile: 148/148 across 16 suites;
- Mobile TypeScript: pass;
- Mobile lint: no lint script/configuration is present;
- shared constants: 24/24; adapter validators: 7/7 and 9/9;
- unchanged E3A backend regression: 24/24; and
- `git diff --check`: pass.

No Expo/EAS build, TestFlight/Google Play change, tester/distribution change, deployment, production write, Calendar mutation, notification, or infrastructure action occurred. E3A, E3B, and E3B.1 remain NOT DEPLOYED.

## Disposition

The independently identified local safety gaps are remediated and E3B is ready for separately approved Mobile build-planning. Build creation, distribution, deployment, early/late/same-day policy, Start reversal, mandatory Start-before-Complete, client visibility, offline behavior, and admin-on-behalf Start remain separately gated.
