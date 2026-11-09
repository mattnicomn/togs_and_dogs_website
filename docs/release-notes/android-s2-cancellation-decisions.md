# Android S2 — Owner/Admin Mobile Cancellation Decisions

**Date:** 2026-11-09 (America/New_York)
**Disposition:** `ANDROID_S2_CANCELLATION_DECISIONS_LOCAL_DRAFT_NOT_RELEASED`
**Base:** stacked on Draft PR #68 head `257e045fe15095c981a08b6345efd076ee80ba3f` (`mobile/s1-visit-rbac-a1`) → PR #67 → PR #46 → `main` `8fe7fa78ad707ac67a05d29059d2771a9aa256c8`.
**Authority:** Matthew approved S2 mobile source and tests only, plus one stacked Draft PR. NOT merged, built, deployed, distributed or Ryan-tested. Not linked from canonical continuity documents.

## Scope

Owner/admin can approve or deny a client's cancellation request on the Android request detail screen using the existing backend route `PUT /admin/cancel/decision` with body `{ request_id, client_id, decision, note }`. No backend, web, infrastructure, dependency, lockfile, app-config or canonical-document change. No client-initiated cancellation request was added. Booking approval and payment gates are unchanged.

## Behavior

- **Roles:** explicit owner/admin allowlist. Staff, client, unknown, empty and null roles see nothing and trigger no reads. Backend 403 remains authoritative.
- **Status gating:** the panel is considered only when the screen's request is `CANCELLATION_REQUESTED`. It then performs an authoritative `GET /admin/requests/{id}?clientId=`. Actions appear only if that read confirms `CANCELLATION_REQUESTED` **and** the exact `request_id` and `client_id`. If the screen later stops showing a pending cancellation (for example PR #46 "Refresh booking"), offered actions and any open confirmation are withdrawn.
- **Pre-submit check:** immediately before submitting, the request is re-read. A different status, a changed request (status, `cancellation_requested_at`, `cancellation_reason`) or an identity mismatch refuses the submission and shows the latest data. A failed read refuses the submission.
- **Decision:** **Approve Cancellation** / **Deny Cancellation**, each with explicit confirmation describing its effect; only the literals `APPROVE` and `DENY` are sent; optional note (≤ 500 characters, trimmed); one submission at a time; never retried automatically.
- **Reconciliation:** after success the request is re-read and handed to the screen (identity-checked), which re-resolves the exact routed visit, so visit actions follow the server's child-job states (Approve → jobs `CANCELLED`, Deny → jobs `ASSIGNED`). A refresh failure after success is reported as success-but-not-refreshed with calendar/notification results unknown, and no second decision is offered.
- **Calendar / notification results:** the backend does not return these; it appends failures to `REQUEST.sync_failures`. The app shows only entries added after the decision, and otherwise states that no failures were recorded and that these steps are best-effort. Server messages such as "Deleted N calendar event(s)" are relayed verbatim. Nothing claims synchronization succeeded.
- **Errors (`ApiError.status`):** 400 server message; 401 existing logout path; 403 permission; 404 not found. 409, network failure, 5xx and unexpected responses are treated as unknown outcomes: a safe read decides what is shown (still pending → "may not have been applied", changed → "booking now shows X; confirm in history", read failure → actions withheld until an explicit reload).

## Backend release-safety blockers (not fixed under S2)

The deployed behavior is UNVERIFIED; the following come from backend source on `main` (`src/backend/handlers/cancellation_handler.py`, `src/backend/common/cascade.py`):

1. **No status precondition:** `handle_admin_decision` does not require the request to be `CANCELLATION_REQUESTED`. A decision can be applied to any request state by any owner/admin client.
2. **Lenient decision literal:** any `decision` other than exactly `APPROVE` is treated as `DENY`.
3. **No concurrency guard:** the update has no condition expression or revision; concurrent decisions (web + mobile, two admins) are last-write-wins, and an Approve's calendar/SNS side effects can run after a competing Deny.
4. **Deny side effect:** `CANCELLATION_DENIED` cascades every non-completed child job to `ASSIGNED`, including jobs that were never assigned a worker; the parent's prior status is not restored.
5. **Side-effect reporting:** calendar cleanup and SNS failures are recorded only in `sync_failures`; tenant-context calendar skips are recorded but not returned.

The mobile checks above reduce the risk of deciding a stale or ineligible request from this app; they do **not** replace server-side status validation, literal validation or concurrency control.

## Validation

- Isolated Node 22.23.4 (CI major); dependencies reused from the PR #67 worktree via a git-ignored directory junction (identical lockfile; no install or download).
- New suites: `cancellationDecisionApi` (contract), `CancellationDecisionPanel` (roles, status/identity gating, hydration and retry, decisions, sync-failure reporting, stale refusal, error mapping, duplicate lock, screen-driven withdrawal), `RequestDetailCancellation` (screen integration, visit actions after Approve/Deny).
- Focused (7 suites incl. PR #46/#67/#68 regressions): **160/160 PASS**.
- `npm run typecheck`: **PASS**. Full `npm run test:ci`: **43/43 suites, 573/573 PASS** (PR #68 baseline 40 / 501 + 3 suites / 72 tests); 0 failed, 0 skipped; 0 React `act()` warnings.
- A mutation check (staff allowed + pre-submit guard disabled) was prepared but **not completed** because the local shell became unresponsive; both temporary edits were reverted and verified before the full run and commit.
- Author-agent self-review only; no independent review is claimed.

## Acceptance gates

| Gate | Status |
| --- | --- |
| Local TypeScript and Jest | PASS — tsc 0 errors; 573/573 across 43 suites |
| GitHub CI workflow | UNVERIFIED — `ci.yml` runs only for PRs targeting `main` |
| Backend status/literal/concurrency enforcement | BLOCKER — not implemented server-side (see above) |
| Android emulator / device acceptance | NOT RUN — requires separate authorization |
| Production behavior against `test_tenant_alpha` | NOT RUN — requires separate authorization |
| Build / distribution / Ryan testing | NOT AUTHORIZED OR PERFORMED |
