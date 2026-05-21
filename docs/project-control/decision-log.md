# Decision Log

## 2026-05-20

### Release 6B Closed
- **Decision:** Release 6B (Notification Coverage Expansion) is complete and pushed
- **Scope:** Phase 1 (staff_assigned + visit_scheduled) and Phase 2 (visit_cancelled) accepted
- **Deferred:** `visit_time_changed` remains dormant (no trigger exists)
- **Commit:** Phase 1 at `c2bb31b`, Phase 2 at `f12d92f`

### CUSTOMER_INTAKE Cancellations Do Not Trigger VISIT_CANCELLED
- **Decision:** By design, only `workflow_type = VISIT_BOOKING` cancellations send VISIT_CANCELLED
- **Rationale:** CUSTOMER_INTAKE cancellations are intake withdrawals — no visit was scheduled, no staff to notify
- **Future:** May add `INTAKE_CANCELLED` or `REQUEST_DECLINED` template in a separate release if needed

### Cancellation Reason Persistence Deferred
- **Decision:** Do not fix in Release 6B
- **Issue:** Admin direct cancel via review handler doesn't persist `cancellation_reason` on the record
- **Impact:** VISIT_CANCELLED email correctly hides the reason section (null-safe)
- **Backlog:** `docs/planning/backlog-cancellation-reason-persistence.md`

### Postmark Status Conflict — Requires Dashboard Verification
- **Issue:** Kiro's docs say "Test Mode (Pending Approval)" but Matthew confirmed Postmark is in production with 37/100 emails used
- **Decision:** Release 6C will verify and update documentation. No code changes until sender signature is confirmed.
- **Action:** Matthew or AG must check Postmark dashboard for sender verification status of `support@usmissionhero.com`

## 2026-05-19

### Client Portal Identity Resolution — Backlog Only
- **Decision:** Do not modify `resolve_client_identity()` in notification releases
- **Issue:** Admin/owner accounts can't use client portal because resolver only works for `role == 'client'`
- **Backlog:** `docs/planning/backlog-identity-portal-role-resolution.md`

### Notification Duplicate Sends — Not a Code Bug
- **Decision:** Multiple sends observed during Phase 1 validation were caused by AG's repeated assignment attempts, not a code loop
- **Evidence:** Each Lambda invocation fires exactly one notification per event type

## 2026-05-18

### Postmark as Primary Provider
- **Decision:** Postmark is the production email provider (replacing SES sandbox)
- **Config:** `NOTIFICATION_PROVIDER = "postmark"`, `NOTIFICATION_MODE = "external_provider"`
- **Rollback:** Set `NOTIFICATION_DRY_RUN = "true"` for immediate halt

### Null-Safety Required for All Templates
- **Decision:** All notification templates must use `_safe()` helper and handle None/empty fields
- **Trigger:** Production crash from `'NoneType' object has no attribute 'replace'`
- **Pattern:** `context.get('field') or 'default'` (not `context.get('field', 'default')`)
