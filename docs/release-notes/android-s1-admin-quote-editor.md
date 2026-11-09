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
- **Client-side stale check (not server-enforced):** before every save/send the request is re-read and its canonical quote fields compared with what is displayed. Any difference (including a quote sent or edited elsewhere) refuses the action, loads the latest data and explains why. The PATCH itself remains last-write-wins on the server; a write between this check and the PATCH cannot be detected.
- **Reconciliation:** after success the request is re-read and only quote fields plus the derived status mirror are merged into the screen, preserving PR #46's visit, occurrence and draft-note state. If that refresh fails, the user is told the save/send **succeeded** but could not be refreshed.
- **Errors (`ApiError.status`):** 400 shows the server message; 401 uses the existing logout path; 403 permission; 404 not found; 409 reload and explain; network/5xx/unexpected are treated as *unknown outcome*: a read-only reload is attempted and the user is told to verify. No mutation is ever retried automatically; Save/Send are locked while in flight.
- **PR #46 integration:** `QUOTE_NEEDED` next-step copy now points to the on-screen Quote section instead of the web editor. All PR #46 M&G, approval, visit-selection, draft-note and Start/Complete behavior is unchanged.

## Validation

- Isolated Node 22.23.4 (matches CI); `npm ci` from the committed lockfile; no dependency changes.
- Focused suites (`quoteMoney`, `adminQuoteApi`, `AdminQuoteEditor`, `RequestDetailAdminQuote`, `bookingWorkflowCopy`, `AndroidBookingWorkflow`): **6/6 suites, 143/143 tests PASS**.
- `npm run typecheck`: **PASS** (0 errors).
- Full `npm run test:ci`: **39/39 suites, 440/440 tests PASS** (PR #46 baseline 35 suites / 334 tests, plus 4 new suites and 106 new tests; zero failed, skipped or todo). Existing React act/open-handle notices persist; no suppression or timeout increase was introduced.
- Author-agent self-review only; no independent review is claimed.

## Known limitations

- Concurrency protection for draft saves is client-side only (see above). Concurrent web and mobile edits within the same moment can still overwrite each other on the server.
- If the request object passed to the detail screen lacks quote fields that the authoritative read returns, the first save is refused as "changed" and the latest data is loaded; a second attempt proceeds. Not verified against production list responses.
- No Resend, no revise-after-DECLINED, no NOT_REQUIRED toggle, no payment recording, no quote notifications.
- Not exercised on an emulator or device; UI layout is unverified.

## Acceptance gates

| Gate | Status |
| --- | --- |
| Local TypeScript and Jest | PASS — tsc 0 errors; 440/440 tests across 39 suites |
| Android emulator / device acceptance | NOT RUN — requires separate authorization |
| Production behavior against `test_tenant_alpha` | NOT RUN — requires separate authorization |
| Build / distribution / Ryan testing | NOT AUTHORIZED OR PERFORMED |
