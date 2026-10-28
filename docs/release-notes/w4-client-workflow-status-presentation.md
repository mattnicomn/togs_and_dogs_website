# W4 Option A — Client Workflow Status Presentation (frontend-only)

**Disposition:** `W4_OPTION_A_MERGED_NOT_DEPLOYED`

`W4_IMPLEMENTATION_STATUS=MERGED_NOT_DEPLOYED`

**Merge checkpoint (2026-10-22):** PR #24 (`fix: normalize client workflow status
presentation`, head `fix/w4-frontend-workflow-summary`) was squash-merged into `main`.
- pre-merge main: `e72b479aee0ba4968b15b167a634e3408e6cc0e2`
- authorized PR head: `01a3e97b3d831d33c790e411b61feb85ca444902`
- resulting main: `main == origin/main == 853b73ac399a6ff47bd37f5059c1c1e99b02949d`
- scope: exactly the approved 9 files (mobile/web frontend + tests + this doc); frontend-only;
  no backend/API/infra change.

**Deployment boundary:** `W4_DEPLOYED=NO`. Merging PR #24 did **not** change production. The
latest completed production backend release remains the PR #22 release
(`PR22_PRIVACY_PRODUCTION_DEPLOYED_VERIFIED`); production web/mobile remain on their existing
deployed state. This merge integrates source into `main` only; no web deploy, no mobile build
or distribution, no Terraform, no AWS mutation occurred.

**Original authoring checkpoint:** branch `fix/w4-frontend-workflow-summary` was created from
`origin/main == e72b479aee0ba4968b15b167a634e3408e6cc0e2`.

## What this implements (architecture `W4_OPTION_A_FRONTEND_WORKFLOW_SUMMARY`)

Client-facing list/card surfaces present a **non-commercial workflow-position summary**
derived from the request-list `RequestStatus`. Canonical commercial quote state
(SENT / ACCEPTED / DECLINED / NOT_REQUIRED) remains isolated to the detail surface that
intentionally fetches `GET /client/quotes/{requestId}`.

### Mobile
- `mobile/src/utils/workflowStatus.ts` (new): centralized `getWorkflowStatusPresentation`
  helper. Raw enums never leak; quote-phase statuses (`QUOTE_NEEDED`, `QUOTE_SENT`,
  `QUOTED`) collapse to neutral `In Review`; known non-quote statuses keep friendly
  labels; unknown values fall back to `In Review` (never a raw enum). No commercial quote
  terminology is synthesized from `RequestStatus`.
- `mobile/src/screens/BookingsScreen.tsx`: badge now uses the helper instead of a map whose
  `?? item.status` fallback leaked raw enums. No per-row `getClientQuote` call added.

> **Hardening correction (2026, PR #24 follow-up commit):** the helper now also maps the
> customer-visible terminal/warning RequestStatus values `DECLINED` (→ "Declined"),
> `CANCELLATION_REQUESTED` (→ "Cancellation Pending"), and `CANCELLATION_DENIED`
> (→ "Cancellation Denied") with request-oriented wording, so they no longer fall through to the
> neutral "In Review" unknown-fallback. `DECLINED` here is the REQUEST/workflow decline — NOT
> canonical quote_status DECLINED — and carries no quote/commercial/payment claim. The web
> `ClientPortal` gained the same `DECLINED` ("This request was declined.") and
> `CANCELLATION_DENIED` request-oriented entries. Quote-phase (`QUOTE_NEEDED`/`QUOTE_SENT`/`QUOTED`)
> and genuinely unknown values remain neutral "In Review".
- `mobile/src/screens/ClientRequestDetailScreen.tsx` (§4.3): the unknown/default canonical
  quote state now renders neutral "Quote status unavailable…" language instead of reusing
  the `NOT_REQUIRED` "No quote action is required" copy. **UNKNOWN != NOT_REQUIRED.**
  SENT / ACCEPTED / DECLINED / NOT_REQUIRED behavior, Accept/Decline UX, pricing display,
  and `expected_revision` mutation behavior are unchanged; no new mutation was introduced.

### Web
- `web/src/components/ClientPortal.jsx`: quote-phase `RequestStatus` values and the unknown
  fallback now collapse to neutral `In Review` workflow-summary wording (previously rendered
  "Quote Needed"/"Quote Sent"/"Quoted" + commercial messaging, and an underscore-stripped raw
  enum for unknowns). `AdminQuoteEditor` / `MasterScheduler` owner/admin quote semantics are
  OUT OF SCOPE and unchanged.

## Guarantees
- `W4_PRIVACY_BOUNDARY_PRESERVED=PASS` — no `quote_status`/amount/payment/notes/history added
  to any `/client/requests`-backed list surface; PR #22 client-safe projection untouched; no
  PK/SK fallbacks; no DRAFT exposure; no commercial state inferred from `RequestStatus`.
- `W4_N_PLUS_ONE_QUOTE_FETCHES_ADDED=NO` — the list uses only the existing request-list payload.
- `W4_FRONTEND_ONLY_SCOPE=PASS` — no backend/infra/API/contract/DynamoDB/tenant/Stripe/scheduling change.

## Tests
- Mobile focused: `workflowStatus` + `BookingsScreen` + `ClientRequestDetailScreen.test` —
  53 tests PASS.
- Mobile broad: 33 suites / 290 tests pass; mobile `tsc --noEmit` clean. Pre-existing act()
  warnings (IntakeScreen / RequestDetailDecline* / mutations) are unchanged and unrelated.
- Web: vitest 28 files / 438 tests pass (incl. updated ClientPortal W4 assertions; MasterScheduler
  admin assertions untouched). eslint on changed files shows only pre-existing ClientPortal issues
  (unused `userRole`/`setTenantInfo`, `checkSession` hoisting) not touched by W4.
- `W4_NEW_REGRESSIONS=0`.

## Next workstream (approved sequence W2 → W4 → W1 → W3)
`NEXT_RECOMMENDED_WORKSTREAM=W1`. W1 remains `W1_IMPLEMENTATION_AUTHORIZED=NO` until Matthew
separately approves it; W1 is NOT started by this merge/closeout.

## Gates preserved (unchanged by W4 merge)
`SCHEDULING_WORKSTREAM_STATUS=DRAFT_PR_DELIVERY_CHECKPOINT`;
`SCHEDULING_PR_MERGE_AUTHORIZED=NO`; Stripe sandbox-only; `RYAN_TESTING_AUTHORIZED=NO`;
no second tenant; no production test data; no production functional quote mutation;
no EAS/TestFlight/App Store/Google Play/public mobile distribution. No deployment authorized
(`W4_DEPLOYED=NO`).
