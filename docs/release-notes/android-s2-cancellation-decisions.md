# Android S2 — Owner/Admin Mobile Cancellation Decisions

**Date:** 2026-11-09 (America/New_York)
**Disposition:** `ANDROID_S2_CANCELLATION_DECISIONS_LOCAL_DRAFT_NOT_RELEASED`
**Base:** stacked on Draft PR #68 head `257e045fe15095c981a08b6345efd076ee80ba3f` (`mobile/s1-visit-rbac-a1`) → PR #67 → PR #46 → `main` `8fe7fa78ad707ac67a05d29059d2771a9aa256c8`.
**Authority:** Matthew approved S2 mobile source and tests only, plus one stacked Draft PR. NOT merged, built, deployed, distributed or Ryan-tested. Not linked from canonical continuity documents.

## Scope

Owner/admin can approve or deny a client's cancellation request on the Android request detail screen using the backend route `PUT /admin/cancel/decision` with body `{ request_id, client_id, decision, note }`, plus `cancellation_request_id` when the authoritative read has one (D-4, below). No backend, web, infrastructure, dependency, lockfile, app-config or canonical-document change. No client-initiated cancellation request was added. Booking approval and payment gates are unchanged.

## Behavior

- **Roles:** explicit owner/admin allowlist. Staff, client, unknown, empty and null roles see nothing and trigger no reads. Backend 403 remains authoritative.
- **Status gating:** the panel is considered only when the screen's request is `CANCELLATION_REQUESTED`. It then performs an authoritative `GET /admin/requests/{id}?clientId=`. Actions appear only if that read confirms `CANCELLATION_REQUESTED` **and** the exact `request_id` and `client_id`. If the screen later stops showing a pending cancellation (for example PR #46 "Refresh booking"), offered actions and any open confirmation are withdrawn.
- **Pre-submit check:** immediately before submitting, the request is re-read. A different status, a changed request (status, `cancellation_requested_at`, `cancellation_reason`) or an identity mismatch refuses the submission and shows the latest data. A failed read refuses the submission.
- **Decision:** **Approve Cancellation** / **Deny Cancellation**, each with explicit confirmation describing its effect; only the literals `APPROVE` and `DENY` are sent; optional note (≤ 500 characters, trimmed); one submission at a time; never retried automatically.
- **Reconciliation:** after success the request is re-read and handed to the screen (identity-checked), which re-resolves the exact routed visit, so visit actions follow the server's child-job states (Approve → jobs `CANCELLED`; Deny under BE-CANCEL-1 → booking restored to its verified prior status, jobs unchanged). A refresh failure after success is reported as success-but-not-refreshed with calendar/notification results unknown, and no second decision is offered.
- **Calendar / notification results:** the backend does not return these; it appends failures to `REQUEST.sync_failures`. The app shows only entries added after the decision, and otherwise states that no failures were recorded and that these steps are best-effort. Server messages such as "Deleted N calendar event(s)" are relayed verbatim. Nothing claims synchronization succeeded.
- **Errors (`ApiError.status`):** 400 server message; 401 existing logout path; 403 permission; 404 not found. 409, network failure, 5xx and unexpected responses are treated as unknown outcomes: a safe read decides what is shown (still pending → "may not have been applied", changed → "booking now shows X; confirm in history", read failure → actions withheld until an explicit reload).

## D-4 compatibility correction (BE-CANCEL-1 contract)

Source-only correction to this Draft PR so the panel matches the BE-CANCEL-1 backend
contract (Draft PR #71). Owner-approved product policy: O-1 = A.

- **Cycle identity:** the decision request carries `cancellation_request_id` taken only from
  the authoritative pre-submit read. It is omitted only when the record genuinely has none
  (a legacy request) and is never invented. The id and the verified prior status are part
  of the stale-request fingerprint, so a change between loading and submitting refuses the
  submission.
- **DENY (O-1 A):** Deny is offered only when the read shows a verified prior status of
  exactly `APPROVED` or `ASSIGNED`. Otherwise the panel states that owner review is
  required; Approve stays available. A DENY is reported as successful only when the re-read
  shows exactly that prior status (no job cascade). Any other status, including
  `CANCELLATION_DENIED`, is shown as a mismatch, never as success.
- **409 handling:** `ApiError` now carries the server's optional `code` (messages unchanged).
  `LEGACY_PRIOR_STATUS_UNKNOWN` withdraws Deny and asks for owner review;
  `CANCELLATION_CYCLE_MISMATCH` and `CANCELLATION_STATE_CHANGED` re-read and show the current
  request for review; `CANCELLATION_NOT_PENDING` shows the current status with no actions.
  Each makes one safe read and never resubmits. A 409 without a known code keeps the
  previous generic reconciliation.
- **Copy:** the Deny confirmation and result describe restoration to the previous status,
  unchanged visits and no client email. The client-portal denial marker (D-1) is a separate,
  not-yet-authorized web workstream and is not part of this change.

## Backend dependency (release blocker)

This mobile behaviour requires BE-CANCEL-1 (Draft PR #71, source-only, NOT deployed) to be
deployed and its production contract verified first. Against the backend currently on
`main`, which never records a prior status and whose DENY writes `CANCELLATION_DENIED`, Deny
would never be offered and any DENY result would show a mismatch.

The original S2 backend blockers on `main` (no status precondition, lenient literal, no
concurrency guard, DENY job cascade to `ASSIGNED`, side-effect reporting only in
`sync_failures`) are addressed in BE-CANCEL-1 source but remain unresolved in production until
that release is separately approved, deployed and verified. Deployed behavior is UNVERIFIED.

The mobile checks reduce the risk of deciding a stale or ineligible request from this app;
they do **not** replace server-side enforcement.

## Validation

- Isolated Node 22.23.4 (CI major); dependencies reused from the PR #67 worktree via a git-ignored directory junction (identical lockfile; no install or download).
- New suites: `cancellationDecisionApi` (contract), `CancellationDecisionPanel` (roles, status/identity gating, hydration and retry, decisions, sync-failure reporting, stale refusal, error mapping, duplicate lock, screen-driven withdrawal), `RequestDetailCancellation` (screen integration, visit actions after Approve/Deny).
- Focused (7 suites incl. PR #46/#67/#68 regressions): **160/160 PASS**.
- `npm run typecheck`: **PASS**. Full `npm run test:ci`: **43/43 suites, 573/573 PASS** (PR #68 baseline 40 / 501 + 3 suites / 72 tests); 0 failed, 0 skipped; 0 React `act()` warnings.
- A mutation check (staff allowed + pre-submit guard disabled) was prepared but **not completed** because the local shell became unresponsive; both temporary edits were reverted and verified before the full run and commit.
- Author-agent self-review only; no independent review is claimed.

### D-4 validation (local only; the figures above are the original S2 run)

- Node 22.23.4; dependencies reused through the same git-ignored junction; nothing installed.
- `tsc --noEmit`: 0 errors.
- Cancellation suites (`cancellationDecisionApi`, `CancellationDecisionPanel`, `RequestDetailCancellation`): 107/107 pass, no `act()` warnings from these suites.
- Full `jest --ci`: 43/43 suites, 608/608 tests, 0 failed, 0 skipped. The log contains `act()` warnings from other suites this change does not touch (for example `RequestDetailDecline*`, `RequestDetailVerifyMeetGreet*`, `IntakeScreen`); they were not investigated here.
- Mutation checks (applied to a throwaway worktree copy, never this branch), each made at least one test fail: dropping the cycle id from the request (7 failed), accepting `CANCELLATION_DENIED` as the DENY result (6 failed), offering Deny without a verified prior status (9 failed), dropping `ApiError.code` (3 failed). Restoring the files returned 107/107.
- Author-agent self-review only; no independent review is claimed. CI does not run for this stacked PR.

## Acceptance gates

| Gate | Status |
| --- | --- |
| Local TypeScript and Jest | PASS — tsc 0 errors; 573/573 across 43 suites |
| GitHub CI workflow | UNVERIFIED — `ci.yml` runs only for PRs targeting `main` |
| Backend status/literal/concurrency enforcement | BLOCKER — implemented in BE-CANCEL-1 source (Draft PR #71), not deployed |
| D-4 compatibility correction | Local only — tsc clean; 608/608 Jest (see D-4 validation above) |
| Android emulator / device acceptance | NOT RUN — requires separate authorization |
| Production behavior against `test_tenant_alpha` | NOT RUN — requires separate authorization |
| Build / distribution / Ryan testing | NOT AUTHORIZED OR PERFORMED |

---

## Supersession & Stack Integration Note (2026-11-12 — Draft PR #78)

> **Historical record preserved.** All sections above remain the exact historical record for standalone Draft PR #69 (`e4040ef040cd49fb05bd3ba09b7999475f765ea5`). Subsequent integration updates:
>
> 1. **Index registration:** This note is now registered in [index.md](index.md) and [document-map.md](../project-continuity/document-map.md).
> 2. **Full-stack integration & GitHub CI evidence:** Combined with backend/web PR `#77` (`16471f858062f20ec3814e22a5cae76524d0a94b`, containing `#75` backend CI/R7E fix, `#76` web lint/tenant-detail fix, `#71` `BE-CANCEL-1`, `#72` `WEB-CANCEL-1`, and `#73` `D-1` client-portal denial marker) in **Draft PR #78** (`2ef5a1f43b256189860a9c5f97d87e274c338211` → `main`). In PR `#78`, all 5 GitHub Actions CI jobs (`backend`, `web`, `mobile` 43 suites / 608 tests, `shared`, `GitGuardian`) passed (`SUCCESS`, run `43359979814`), and independent B2-B source review of `#46`, `#67`, `#68`, and `#69` completed (`ACCEPTABLE`).
> 3. **D-1 web marker cross-reference:** The separate web client-portal denial marker noted in D-4 above is implemented in Draft PR #73 ([d1-client-denial-marker.md](d1-client-denial-marker.md)) and included in PR `#78`. The mobile client-facing denial marker remains deferred per D-1 policy.
> 4. **Gates unchanged:** `BE-CANCEL-1` (PR #71) remains source-only and NOT deployed in production (`togs-and-dogs-prod-cancellation` and `togs-and-dogs-prod-review` still run `W6cqyudl…`). Merge, backend/web deployment, D-2 legacy cancellation inventory, Android build, Play internal distribution, device acceptance, and Ryan testing remain **NOT AUTHORIZED**.
