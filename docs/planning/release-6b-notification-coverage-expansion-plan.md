# Release 6B: Notification Coverage Expansion — Planning Document

## Objective
Polish the remaining stub notification templates into production-quality branded emails, matching the style established in Release 6A for `CUSTOMER_APPROVED` and `REQUEST_RECEIVED`.

## Current State

### Completed (Release 6A — Live)
| Template | Event | Recipient | Status |
|----------|-------|-----------|--------|
| `customer_approved` | CUSTOMER_APPROVED | Client | ✅ Production — branded HTML |
| `request_received` | REQUEST_RECEIVED | Admin | ✅ Production — branded HTML |
| `welcome_invite_client` | WELCOME_INVITE_CLIENT | Client | ✅ Production — branded HTML (pre-existing) |
| `welcome_invite_staff` | WELCOME_INVITE_STAFF | Staff | ✅ Production — branded HTML (pre-existing) |

### Stubs Requiring Polish (Release 6B Scope)
| Template | Event | Recipient | Trigger Location | Risk |
|----------|-------|-----------|-----------------|------|
| `visit_scheduled` | VISIT_SCHEDULED | Client | review_handler (ASSIGNED), assignment_handler | **Medium** — client-facing |
| `staff_assigned` | STAFF_ASSIGNED | Staff | review_handler (ASSIGNED), assignment_handler | **Low** — internal staff |
| `visit_cancelled` | VISIT_CANCELLED | Client + Staff + Admin | review_handler (CANCELLED), cancellation_handler, admin_handler (bulk) | **Medium** — multi-recipient |
| `visit_time_changed` | VISIT_TIME_CHANGED | Client | No active trigger in code | **None** — dormant |

## Event Trigger Map

### VISIT_SCHEDULED
- **Fires when:** VISIT_BOOKING transitions to ASSIGNED
- **Triggered from:** `review_handler.handle_notifications()`, `assignment_handler`
- **Recipient:** Client email (via `NOTIFY_CLIENT_ON_SCHEDULED` flag)
- **Record context:** Full request item with `worker_id`, `worker_name` injected

### STAFF_ASSIGNED
- **Fires when:** VISIT_BOOKING transitions to ASSIGNED
- **Triggered from:** `review_handler.handle_notifications()`, `assignment_handler`
- **Recipient:** Staff email (via `NOTIFY_STAFF_ON_ASSIGNMENT` flag, resolved from `assigned_to_email` or `worker_id` if it contains @)
- **Record context:** Full request item with `worker_id`, `worker_name` injected

### VISIT_CANCELLED
- **Fires when:** Request transitions to CANCELLED
- **Triggered from:** `review_handler.handle_notifications()`, `cancellation_handler`, `admin_handler` (bulk status)
- **Recipients:** Client + Staff + Admin (each gated by `NOTIFY_*_ON_CANCELLED` flags)
- **Record context:** Full request item at time of cancellation

### VISIT_TIME_CHANGED
- **Fires when:** Not currently triggered by any code path
- **Recipient:** Client email
- **Status:** Dormant — no implementation needed until a reschedule feature is built

## Available Context Fields

The service builds this context dict from the DynamoDB record for all non-welcome events:

```python
context = {
    "client_name": get_client_name(record),      # Always available
    "client_email": record.get('client_email'),   # Added in 6A Hotfix 1
    "client_phone": record.get('client_phone'),   # Added in 6A Hotfix 1
    "staff_name": get_staff_name(record),         # Available when assigned
    "request_id": request_id,                     # Always available
    "pet_names": get_pet_names(record),           # Always available
    "service_type": record.get('service_type'),   # May be None
    "start_date": record.get('start_date'),       # May be None
    "start_time": record.get('start_time'),       # May be None
    "details": record.get('details'),             # May be None
}
```

After `normalize_context()`:
- `client_name` → guaranteed non-None (fallback: 'Valued Client')
- `staff_name` → guaranteed non-None (fallback: 'Team Member')
- `pet_names` → guaranteed non-None (fallback: 'your pets')
- `service_label` → friendly mapped from service_type (fallback: 'Pet Sitting')
- `date_label` → formatted date/time string (fallback: 'scheduled date')

### Missing Context Fields (Enhancement Opportunities)

| Field | Needed For | Source | Priority |
|-------|-----------|--------|----------|
| `worker_name` | visit_scheduled, staff_assigned | `record.get('worker_name')` — already on record when assigned | High |
| `cancellation_reason` | visit_cancelled | `record.get('reason')` or audit log | Medium |
| `portal_url` | All client-facing | Config `NOTIFICATION_PORTAL_URL` | Medium |

**Recommendation:** Add `worker_name` and `portal_url` to the service context dict. These are 2-line additions (same pattern as `client_email`/`client_phone` in 6A Hotfix 1).

## Recommended Implementation Order

### Phase 1: staff_assigned (Low Risk)
- **Why first:** Internal staff recipient only. If formatting is imperfect, no client impact.
- **Content:** Assignment details, client name, pet names, service type, date, portal CTA
- **Accent color:** Purple (matching staff portal branding)
- **Validation:** Assign a worker to a test request, check staff inbox

### Phase 2: visit_scheduled (Medium Risk)
- **Why second:** Client-facing but fires alongside staff_assigned (same trigger). Can validate both in one action.
- **Content:** Confirmation with sitter name, service details, date, portal CTA
- **Accent color:** Green (matching approval/positive branding)
- **Validation:** Same assignment action validates both

### Phase 3: visit_cancelled (Medium Risk)
- **Why third:** Multi-recipient (client + staff + admin). More complex but well-gated by `NOTIFY_*` flags.
- **Content:** Cancellation notice, service details, reason (if available), contact info
- **Accent color:** Red/muted (cancellation tone)
- **Validation:** Cancel a test request, check all three recipient inboxes

### Phase 4: visit_time_changed (No Risk — Deferred)
- **Why last:** No code path triggers this event. Polish it for future use but no production validation possible until a reschedule feature exists.
- **Content:** Updated time details, original vs new, portal CTA
- **Status:** Implement template but mark as dormant

## Deployment Strategy

Each phase can be deployed independently:
1. Polish template in `templates.py`
2. Add any needed context fields to `service.py` (if required)
3. Run local tests
4. `terraform apply` (Lambda code hash update only)
5. Trigger the event and validate live email
6. Commit after validation

Alternatively, all 3 active templates can be polished in a single commit and deployed together, then validated sequentially (assign → check staff + client emails → cancel → check cancellation emails).

## Postmark Account Consideration

The Postmark account is still in **Test Mode** — only `@usmissionhero.com` addresses can receive emails. This means:
- `staff_assigned` will only work if staff email is `@usmissionhero.com`
- `visit_scheduled` will only work if client email is `@usmissionhero.com`
- `visit_cancelled` same constraint

**Recommendation:** Request Postmark production approval before or during Release 6B to enable delivery to real client/staff addresses.

## Terraform/Infrastructure Changes

**None required.** All `NOTIFY_*` flags are already `"true"` in `locals.tf`. Only Lambda code package updates needed.

## .kiro/specs/postmark-notifications/ Assessment

This directory contains:
- `.config.kiro` — Kiro spec metadata (feature spec, requirements-first workflow)
- `requirements.md` — Comprehensive 11-requirement spec covering the full notification subsystem (Postmark client, service orchestration, ledger, quota, webhooks, testing, ops docs)

**Recommendation:** Keep but do NOT commit yet. The spec describes the full vision (ledger, quota, webhooks) which is partially implemented. It serves as a reference for future work but committing it now could imply those features are complete. Options:
1. **Keep untracked** — reference during planning, commit when more of the spec is implemented
2. **Add to .gitignore** — if you want to prevent accidental commits
3. **Commit as-is** — if you want it version-controlled for team reference (add a status note at the top)

## Estimated Effort

| Phase | Template | Effort | Deploy Risk |
|-------|----------|--------|-------------|
| 1 | staff_assigned | ~30 min | Low |
| 2 | visit_scheduled | ~30 min | Low-Medium |
| 3 | visit_cancelled | ~45 min | Medium |
| 4 | visit_time_changed | ~20 min | None (dormant) |
| — | Context field additions | ~10 min | None |
| **Total** | | **~2.5 hours** | |

## Success Criteria

- All 3 active templates render branded HTML with no None/NoneType values
- Each template passes local null-safety tests
- Live emails received and rendered correctly for each event type
- No `NOTIFICATION_CRITICAL_FAILURE` in CloudWatch
- Existing `customer_approved` and `request_received` continue working
- `visit_time_changed` template exists but is acknowledged as dormant
