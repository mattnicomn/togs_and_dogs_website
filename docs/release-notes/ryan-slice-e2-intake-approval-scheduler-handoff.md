# Ryan Cross-Platform Alignment Slice E2 — Intake Approval to Scheduler Handoff

**Date:** 2026-08-20
**Status:** ✅ IMPLEMENTED / VALIDATED / NOT DEPLOYED
**Starting SHA:** `622edf222c893b21734bfdd916dc7311e9ce2855`

## Objective

Slice E2 adds the Web Admin customer-intake action **Approve & Open Scheduler**. It performs the existing canonical approval once, reconciles the same request while asynchronous job setup finishes, and opens the existing Scheduler. It does not create a second booking, assign a sitter, or complete scheduling.

## Local Implementation

- Extended the E1 action model with an explicit `APPROVAL_SCHEDULER_HANDOFF` semantic. The backend action remains canonical `APPROVED`; no synthetic status or payload was added.
- Customer-intake approval actions are labeled **Approve & Open Scheduler** in both the action menu and guided workflow. Visit-booking approval remains the existing standard status transition.
- The handoff calls the existing `reviewRequest(requestId, clientId, 'APPROVED', note)` operation exactly once. It never calls `createAdminBooking()` and never retries approval automatically.
- After approval succeeds, AdminDashboard reads existing `GET /admin/requests` data up to five times: once immediately, then at 500 ms intervals for at most four additional reads. The maximum reconciliation wait is 2 seconds.
- Each read locates the same `request_id`, merges that refreshed request into local state, and recognizes either `job_id` or a non-empty `job_ids` value as ready.
- Readiness opens the existing Scheduler locally. The action does not assign a sitter; staff assignment remains the separate E1 **Assign Sitter** handoff.
- An in-flight ref blocks repeated approval submission. Existing local Scheduler navigation is shared with E1; E2 readiness does not rely on incidental view-change fetching.
- `MasterScheduler.jsx`, API client, APIs, payloads, shared/generated contracts, backend, Calendar runtime, assignment mutations, infrastructure, and Mobile source are unchanged.

## Failure and Timeout Behavior

- Canonical approval failure preserves the current list UI, displays the existing error convention, performs no job-readiness reads, and does not open Scheduler.
- The frontend does not automatically resubmit an ambiguous or failed approval operation.
- If readiness is not observed within the bounded window, or reconciliation itself fails after approval, the successful approval is not rolled back. Scheduler opens with: **“Approved successfully; job setup is still initializing. Refresh before assigning.”**
- Scheduler date filtering is unchanged. A future request can be present in Scheduler data without appearing in the currently visible day or week.

## Preserved Behavior

The existing `/admin/review` path remains authoritative for RBAC, tenant enforcement, transition and payment/Meet & Greet gates, profile automation, asynchronous job creation, notifications, Calendar behavior, audit behavior, and status handling. E1 **Assign Sitter** and **View in Calendar**, standard visit-booking approval, Complete, Cancel, Archive, Edit, confirmation, and secondary actions remain unchanged.

## Local Validation

- focused resolver/rendered E1+E2 suite: 24/24;
- required AdminDashboard/service/status/Calendar RBAC suites: 86/86 across 7 files;
- full Web Vitest: 310/310 across 23 files;
- legacy Web: 99/99;
- combined Web: 409/409;
- Vite production build: success, 111 modules transformed;
- targeted lint: utility and test file clean; `AdminDashboard.jsx` remains the exact clean-HEAD baseline of 17 errors / 5 warnings, with zero E2-introduced findings; and
- `git diff --check`: pass.

## Boundaries and Remaining Slice E Decision

E2, E1, and O1 are NOT DEPLOYED. No production request, booking, job, data write, Calendar mutation, notification, AWS/infrastructure change, tenant change, Cognito/Postmark change, Stripe change, Mobile build/distribution, tester-access change, or public-site action occurred.

The remaining Slice E product decision is Mobile **Start Visit → Complete Visit**. This workstream still has no approved canonical `IN_PROGRESS` transition, so no Mobile or backend implementation was attempted.

## Disposition

**Final Status:** `RYAN_SLICE_E2_INTAKE_APPROVAL_SCHEDULER_HANDOFF_IMPLEMENTED_VALIDATED_NOT_DEPLOYED`
