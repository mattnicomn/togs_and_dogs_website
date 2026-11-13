# Android S1 — Owner/Admin Mobile Quote Editor

**Date:** 2026-11-09 (America/New_York)
**Disposition:** `ANDROID_S1_ADMIN_QUOTE_EDITOR_LOCAL_DRAFT_NOT_RELEASED`
**Base:** stacked on Draft PR #46 head `06ee9d628ac57d1a988e264ec74c26fe41174125` (`mobile/android-workflow-remediation`), which is based on `main` `8fe7fa78ad707ac67a05d29059d2771a9aa256c8`.
**Authority:** Matthew approved S1 source-only development (mobile admin quote create/edit/send) and one stacked Draft PR. NOT merged, built, deployed, distributed or Ryan-tested.

This note is intentionally not yet linked from the canonical continuity documents or the release-notes index; registration follows PR #46's separately authorized integration.

## Scope

Owner/admin can create and edit a DRAFT canonical quote and send it to the client from the Android request detail screen, using the already-deployed backend contract:

| Operation | Endpoint | Server behavior relied on |
| --- | --- | --- |
| Create / edit draft | `PATCH /admin/requests/{id}/quote` | owner/admin only; integer cents; **last-write-wins, no `expected_revision`** |
| Send | `POST /admin/requests/{id}/quote/send` (no body) | DRAFT→SENT; requires stored amount > 0; conditional write → **409** on a concurrent change; never approves the booking |
| Authoritative read | `GET /admin/requests/{id}?clientId=` | raw REQUEST including quote fields |

No backend, web, infrastructure, dependency, lockfile, app-config or canonical-document change.

## Behavior

- **RBAC:** the editor renders only for `owner`/`admin`. Staff, client, unknown, empty and null roles render nothing and issue no requests. Backend 403 remains authoritative.
- **Editable states:** no canonical quote yet, or `DRAFT`. `SENT`, `ACCEPTED`, `DECLINED`, `NOT_REQUIRED`, `SUPERSEDED` and unknown states are display-only, so mobile cannot create a new commercial revision or reset a client acceptance. There is no Resend.
- **Money:** `^\d+(\.\d{1,2})?$` string parsing to integer cents (no floating point; safe-integer bound), mirroring the web W2B rule. Deposit is required and `0 < deposit ≤ total` when the requirement is `DEPOSIT`; it is cleared to 0 for `NONE`/`FULL`. Currency must be a 3-letter code.
- **Fields:** amount, currency, payment requirement (NONE/DEPOSIT/FULL), deposit, client-facing notes, internal notes, internal pricing notes.
- **Send:** only for a saved DRAFT with a positive persisted amount and no unsaved changes; requires confirmation; the copy states that sending does not approve or schedule the booking.
- **Initial authoritative hydration (S1-R1):** when the editor opens it performs one `GET /admin/requests/{id}` and keeps its own authoritative quote snapshot. The navigation/list `request` is never used for quote state, so an incomplete list payload cannot cause a false "changed" refusal. Until hydration succeeds, no inputs, Save or Send are shown ("Loading the latest quote…"). A failed hydration shows a truthful message (network, 401 logout path, 403, 404) and an explicit read-only **Retry loading quote**; nothing is retried automatically.
- **Client-side stale check (not server-enforced):** before every save/send the request is re-read and its canonical quote fields compared with the version the user's edits are based on. Any difference (including a quote sent or edited elsewhere) refuses the action and explains why. The PATCH itself remains last-write-wins on the server; a write between this check and the PATCH cannot be detected.
- **Unsaved input is never silently overwritten (S1-R1):** background refreshes (for example PR #46 "Refresh booking") and error reloads follow the server only when the user has no unsaved edits, or when the edits already equal the new server state. If the server quote moved while the user has edits, the edits are kept, Save/Send are blocked, and the user explicitly chooses **Keep my changes** (saving will replace the latest saved quote) or **Discard my changes**. Payloads without canonical quote state are ignored rather than treated as "no quote".
- **Reconciliation:** after success the request is re-read and only quote fields plus the derived status mirror are merged into the screen, preserving PR #46's visit, occurrence and draft-note state. If that refresh fails, the user is told the save/send **succeeded** but could not be refreshed.
- **Errors (`ApiError.status`):** 400 shows the server message; 401 uses the existing logout path; 403 permission; 404 not found; 409 reload and explain; network/5xx/unexpected are treated as *unknown outcome*: a read-only reload is attempted and the user is told to verify. No mutation is ever retried automatically; Save/Send are locked while in flight.
- **PR #46 integration:** `QUOTE_NEEDED` next-step copy now points to the on-screen Quote section instead of the web editor. All PR #46 M&G, approval, visit-selection, draft-note and Start/Complete behavior is unchanged.

## Validation

- Isolated Node 22.23.4 (matches CI); `npm ci` from the committed lockfile; no dependency changes.
- S1 (`134ba5a`): focused 6/6 suites, 143/143; full **39/39 suites, 440/440** (PR #46 baseline 35 / 334 plus 4 suites / 106 tests).
- S1-R1 (first-save reliability correction): focused suites (`quoteMoney`, `adminQuoteApi`, `AdminQuoteEditor`, `RequestDetailAdminQuote`, `bookingWorkflowCopy`, `AndroidBookingWorkflow`) **6/6 suites, 167/167 PASS**; `npm run typecheck` **PASS** (0 errors); full `npm run test:ci` **39/39 suites, 464/464 PASS** (24 tests added for hydration, retry, edit preservation, conflict choice and first-save/send from an incomplete list payload). Zero failed, skipped or todo; zero React `act()` warnings in the full log. PR #46's `AndroidBookingWorkflow` (30 tests) passes unchanged. No suppression or timeout increase was introduced.
- Author-agent self-review only; no independent review is claimed.

## Known limitations

- Concurrency protection for draft saves is client-side only (see above). Concurrent web and mobile edits within the same moment can still overwrite each other on the server.
- Opening the request detail as owner/admin now issues one additional authoritative read for the quote. The production admin list/detail response shapes remain unverified on a device.
- "Keep my changes" is an explicit, client-side decision to overwrite the latest saved draft; the server does not enforce a revision guard.
- No Resend, no revise-after-DECLINED, no NOT_REQUIRED toggle, no payment recording, no quote notifications.
- Not exercised on an emulator or device; UI layout is unverified.

## Acceptance gates

| Gate | Status |
| --- | --- |
| Local TypeScript and Jest | PASS — tsc 0 errors; 464/464 tests across 39 suites (S1-R1) |
| GitHub CI workflow | UNVERIFIED — `ci.yml` runs only for PRs targeting `main`; this PR is stacked on PR #46 |
| Android emulator / device acceptance | NOT RUN — requires separate authorization |
| Production behavior against `test_tenant_alpha` | NOT RUN — requires separate authorization |
| Build / distribution / Ryan testing | NOT AUTHORIZED OR PERFORMED |

---

## Supersession & Stack Integration Note (2026-11-12 — Draft PR #78)

> **Historical record preserved.** All sections above remain the exact historical record for standalone Draft PR #67 (`d60b1b203782c7b99382e2cfd525b96757dd720c`). Subsequent stack and integration updates:
>
> 1. **Index registration:** This note is now registered in [index.md](index.md) and [document-map.md](../project-continuity/document-map.md).
> 2. **Stacked Android extensions:** **Draft PR #68** (`257e045fe15095c981a08b6345efd076ee80ba3f`, `mobile/s1-visit-rbac-a1`) stacks on `#67` to expand Android visit `Start`/`Complete` (`const canExecuteVisits` in `mobile/src/screens/RequestDetailScreen.tsx`) from staff-only to `owner | admin | staff`, and **Draft PR #69** (`e4040ef040cd49fb05bd3ba09b7999475f765ea5`, [android-s2-cancellation-decisions.md](android-s2-cancellation-decisions.md)) stacks on `#68` to add owner/admin cancellation decisions with D-4 `BE-CANCEL-1` compatibility.
> 3. **Source review & GitHub CI evidence:** Independent B2-B source review of `#46`, `#67`, `#68`, and `#69` completed (`ACCEPTABLE`). Combined in full-stack **Draft PR #78** (`2ef5a1f43b256189860a9c5f97d87e274c338211` → `main`), where all 5 GitHub Actions CI checks (`backend`, `web`, `mobile` 43 suites / 608 tests, `shared`, `GitGuardian`) passed in workflow run `43359979814`.
> 4. **Gates unchanged:** Merge, deployment, Android build, Play distribution, emulator/device acceptance, and Ryan testing remain **NOT AUTHORIZED**.
