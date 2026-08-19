# Ryan Cross-Platform Alignment Slice E1 — Web Admin Guided Assignment and Calendar Actions

**Date:** 2026-08-19
**Status:** ✅ IMPLEMENTED / VALIDATED / NOT DEPLOYED
**Starting SHA:** `f2352812edcee9a4856c52f32d3fd87ac85988e8`

## Objective

Slice E1 implements only two Web Admin next-action handoffs from the approved Ryan workflow direction:

- booking created / ready for staffing → **Assign Sitter**; and
- sitter assigned / scheduled → **View in Calendar**.

The slice does not implement intake **Approve & Schedule**, Mobile **Start Visit → Complete Visit**, or any new status or backend transition.

## Local Implementation

- Added a pure `resolveGuidedWorkflowAction()` resolver with explicit `STATUS_TRANSITION`, `ASSIGNMENT_HANDOFF`, and `CALENDAR_NAVIGATION` semantics.
- `APPROVED`, `BOOKED`, and `JOB_CREATED` visit-booking states resolve to **Assign Sitter** when assignment is allowed.
- **Assign Sitter** opens the existing dynamic staff selector and retains the existing `assignWorker(jobId, requestId, clientId, workerId, workerName)` behavior and payload.
- `ASSIGN` and `VIEW_CALENDAR` are explicitly rejected by the status-transition function, preventing either UI action from reaching `reviewRequest` as a backend status.
- `ASSIGNED` and `SCHEDULED` states with a worker resolve to **View in Calendar**.
- **View in Calendar** switches locally to the existing AdminDashboard Scheduler view, preserves the current in-memory records, and deliberately skips the navigation-triggered data refetch. It causes no review/status request, assignment request, admin mutation, Google OAuth request, or Calendar mutation.
- The existing Process Workflow primary-action map now consumes the same resolver. Existing transition actions remain status-transition semantics.
- `MasterScheduler.jsx`, APIs, payloads, shared/status/service contracts, backend, Calendar runtime, notifications, infrastructure, and Mobile source are unchanged.

## Preserved Behavior

- Assignment completion still uses the existing staff list, filtering, identifiers, `assignWorker` path, refresh, notification, and Calendar-warning handling.
- Complete still submits canonical `COMPLETED` through `reviewRequest`.
- Cancel still submits canonical `CANCELLED` through `reviewRequest`.
- Intake approval still submits canonical `APPROVED` through the existing review path.
- Archive, Edit, secondary actions, confirmations, RBAC, asynchronous approval-side job/profile behavior, notification behavior, service-type behavior, and status case compatibility remain unchanged.

## Local Validation

- focused resolver/rendered E1 suite: 16/16;
- E1 plus required AdminDashboard/service/status/Calendar RBAC suites: 58/58 across 5 files;
- full Web Vitest: 302/302 across 23 files;
- legacy Web: 99/99;
- combined Web: 401/401;
- Vite production build: success, 111 modules transformed;
- targeted lint: new resolver and E1 test file clean;
- `AdminDashboard.jsx` lint: 17 errors / 5 warnings versus clean-HEAD baseline 18 errors / 5 warnings; zero E1-introduced findings; and
- `git diff --check`: pass.

## Boundaries and Remaining Slice E Decisions

E1 is local only and NOT DEPLOYED. O1 also remains NOT DEPLOYED. No production request, booking, job, test data, DynamoDB write, Calendar mutation, notification, AWS/infrastructure change, tenant change, Cognito/Postmark change, Stripe change, Mobile build/distribution, tester-access change, or public-site action occurred.

The remaining Slice E design still needs separate approval and clarification for:

- intake reviewed → **Approve & Schedule**, because approval already triggers asynchronous job/profile creation and a second booking flow could duplicate scheduling; and
- Mobile visit day → **Start Visit → Complete Visit**, because no approved canonical `IN_PROGRESS` backend transition exists for this workstream.

## Disposition

**Final Status:** `RYAN_SLICE_E1_WEB_ADMIN_GUIDED_ACTIONS_IMPLEMENTED_VALIDATED_NOT_DEPLOYED`
