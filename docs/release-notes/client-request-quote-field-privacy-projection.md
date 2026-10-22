# Client Request Quote-Field Privacy Projection (local remediation)

**Disposition:** `CLIENT_REQUEST_QUOTE_PRIVACY_REMEDIATION_LOCAL_COMPLETE_READY_FOR_REVIEW`
**Date:** 2026-10-21
**Branch:** `fix/client-request-quote-privacy-projection`
**Base checkpoint:** `main == origin/main == d04f6cfc6da46388e1c77616708cf34fef7b8244`

## Status / scope

- **LOCAL remediation only. NOT deployed.** No `terraform apply`, no Lambda/API
  deployment, no AWS mutation.
- **No production records were inspected.** The exposure path was proven from source
  and tests only.
- **No evidence that any specific production customer record was exposed.** This
  corrects a source-level exposure *path*; it does not assert a production incident.
- Delivered as an isolated branch and **Draft PR** (not merged).

## Problem (source-proven)

`GET /client/requests` returned the client's own REQUEST records passed through the
denylist-based `sanitize_booking_for_role(item, 'client')`. A denylist exposes every
REQUEST field by default. The canonical quote lifecycle
(`common/quote_contract.apply_quote_update` / `apply_quote_send` / `apply_quote_accept`
/ `apply_quote_decline`) writes commercial and internal quote fields onto the REQUEST
record — `quote_amount_cents`, `currency`, `deposit_amount_cents`,
`payment_requirement`, `quote_notes_client`, `quote_notes_internal`,
`internal_pricing_notes`, `quote_history`, `quote_revision`, and quote lifecycle
timestamps. Of these, only `internal_pricing_notes` and `audit_log` were in the
denylist, so the remaining commercial/internal quote fields could pass through to the
client booking list.

This is in tension with the approved quote contract (Phase 5): pricing is intentionally
redacted from the general client booking list, and the dedicated
`GET /client/quotes/{requestId}` projection is the authoritative client-safe commercial
view (which additionally hides DRAFT).

## Fix — explicit client-safe list projection

- Added `common.auth.project_client_request_list_item(record)` and
  `CLIENT_REQUEST_LIST_ALLOWLIST`: an **explicit allowlist** that builds a NEW dict
  containing only client-safe booking-list fields. The raw REQUEST dict is never
  reused, so quote/commercial/internal fields — and any future REQUEST field — are
  absent by construction.
- Rewired the `GET /client/requests` handler to use the projection instead of the
  denylist pass-through.
- `quote_status` is **intentionally NOT** added to the list projection: a list-level
  canonical quote status is a separate future design decision. This remediation makes
  the accidental pass-through disappear rather than canonize it.
  - `CLIENT_REQUEST_LIST_QUOTE_STATUS_CONTRACTUALLY_EXPOSED=NO`
  - `CLIENT_REQUEST_LIST_QUOTE_STATUS_CAN_PASS_THROUGH_INCIDENTALLY=NO` (after fix)
- The dedicated `GET /client/quotes/{requestId}` endpoint and its DRAFT 404 behavior
  are **unchanged**.

The allowlist is the union of the fields the current client list consumers legitimately
depend on (mobile `BookingsScreen`; web `ClientPortal`) and contains no
quote/commercial/internal fields. Raw `PK`/`SK` are deliberately excluded; `request_id`
and `client_id` (the primary id fields both consumers already prefer) are retained.

## Consumer field contract preserved

Identity/routing (`request_id`, `client_id`, `entity_type`), workflow `status`,
client-safe display (`client_name`, `pet_name`, `pet_names`, `service_type`),
dates/scheduling (`selected_dates`, `start_date`, `end_date`, `is_multi_day`,
`total_occurrences`, `completed_count`, `visit_windows`, `visit_window`, `timeframe`),
client-safe assignment display (`worker_name`, `assigned_sitter`), and `created_at`.

## Tests

`tests/backend/test_client_requests_quote_privacy.py` (17 tests):
- Projection strips all commercial/internal quote fields for every status
  (DRAFT/SENT/ACCEPTED/DECLINED/NOT_REQUIRED).
- DRAFT privacy invariant through the handler (price/notes/deposit/history excluded).
- `quote_status` not incidentally exposed.
- Internal/admin fields (`admin_notes`, `audit_log`, `worker_id`, `job_id`,
  `is_test_booking`) excluded.
- Legitimate client-list fields preserved; legacy/never-quoted REQUEST renders.
- SENT/ACCEPTED/DECLINED list responses do not widen commercial exposure.

## Verification

- Focused suite: 17 passed.
- Directly affected suites (quote contract + accept/decline + sanitizer visibility):
  140 passed.
- Full backend suite: 1709 passed, 90 failed — the 90 are the pre-existing baseline
  (payment/intake/tenant-isolation/terms/rbac suites that fail in the local
  environment regardless of this change), confirmed by rerunning representative suites
  on clean `origin/main` with the edits stashed (identical failures; root causes are
  local AWS-credential / Google-calendar environment assumptions, not this change).

## Relationship to W4

`W4_CAN_PROCEED_INDEPENDENTLY=YES`. W4 (mobile frontend status vocabulary) is parked
until this remediation reaches a reviewed Draft PR checkpoint. No W4 code is modified
on this branch.

## Gates preserved

M4-B/M4-C unchanged; scheduling parked; Stripe sandbox-only; Ryan NO; no tenant /
second-tenant / mobile-distribution change; no deployment.
