# Release 7Q: Production Operations Readiness & Admin Safety Audit

**Status:** Planning
**Priority:** Low-Medium (operational hygiene, not blocking features)
**Risk to Production:** Very Low (documentation + minor frontend display improvements)
**Terraform Required:** No
**Backend Changes:** None
**Scope:** Documentation + optional frontend-only display improvements

---

## 1. Audit Findings

### 1.1 What's Already Solid

The operational documentation and admin safety workflows are in good shape:

| Area | Status | Evidence |
|------|--------|----------|
| **Production smoke test checklist** | ✅ Complete | `docs/validation/production-smoke-test-checklist.md` — covers single-day, multi-day, cancellation |
| **Notification system runbook** | ✅ Complete | `docs/operations/notification-system-runbook.md` — quota, ledger, suppression, kill switches |
| **Offline client management guide** | ✅ Complete | `docs/operations/offline-client-management-guide.md` — full workflow documentation |
| **Google Calendar troubleshooting** | ✅ Complete | `docs/operations/google-calendar-reauthorization.md` — reauth, edge cases, validation |
| **Release checklist** | ✅ Complete | `docs/project-control/release-checklist.md` — pre/post deploy, rollback |
| **Agent operating model** | ✅ Complete | `docs/project-control/agent-operating-model.md` — roles, guardrails, handoffs |
| **Purge safety (frontend)** | ✅ Complete | Dry-run analysis, typed confirmation, status pre-check |
| **Bulk action safety** | ✅ Complete | Context-aware options, confirmation modal, pre-validation |
| **Delete protection (backend)** | ✅ Complete | Rejects DELETE on active records (Release 6D) |
| **Protected account guardrails** | ✅ Complete | Backend + frontend protection (Release 6H) |
| **Terms/Privacy acceptance** | ✅ Complete | Frontend checkbox + backend validation (Releases 7N/7O) |
| **Multi-day cascade** | ✅ Complete | Cancel/archive/delete cascades to all child JOBs |
| **Notification dedup** | ✅ Complete | 5-minute window prevents multi-day spam (Release 7F) |

### 1.2 Documentation Gaps Identified

| # | Gap | Severity | Notes |
|---|-----|----------|-------|
| 1 | **No admin-facing "How to Use" guide** | Medium | Ryan has no single document explaining the admin dashboard workflows (approve, assign, cancel, archive, purge, restore). The offline client guide exists but doesn't cover the full request lifecycle. |
| 2 | **No incident/emergency response checklist** | Low | The release checklist has a rollback section, but there's no standalone "something went wrong in production" guide for Ryan or Matthew. |
| 3 | **No data export/backup documentation** | Low | The admin dashboard has an export feature but no documentation on what it exports or how to use it for backup purposes. |
| 4 | **Smoke test checklist doesn't cover Terms/Privacy** | Very Low | The production smoke test doesn't verify that /terms and /privacy pages render correctly after deployment. |
| 5 | **No documentation of the request status lifecycle** | Medium | No visual or textual reference showing all possible status transitions (PENDING_REVIEW → APPROVED → ASSIGNED → COMPLETED, etc.) |

### 1.3 Admin Dashboard Visibility Gaps

| # | Gap | Severity | Notes |
|---|-----|----------|-------|
| 6 | **No notification delivery status visible on request rows** | Low | Admin can't see at a glance whether notifications were sent/failed for a booking without checking CloudWatch or DynamoDB |
| 7 | **No audit trail visible in the request list** | Low | Admin can't see who approved/assigned/cancelled a request without opening the CareCard detail |
| 8 | **No "last updated" timestamp on request rows** | Very Low | Hard to tell when a request was last touched |

### 1.4 Regression Risk Assessment (Releases 7E–7P)

| Release | Risk | Assessment |
|---------|------|-----------|
| 7E (multi-day JOBs) | None | Backend-only; frontend handles display correctly |
| 7E Phase 2B (date picker) | None | New Visit modal only |
| 7E Phase 2C (public intake) | None | IntakeForm only |
| 7F (notification dedup) | None | Backend-only |
| 7N (policy content) | None | Constants file only |
| 7O (no-op) | None | Documentation only |
| 7P (UX polish) | None | Display-only CSS/JSX |

**No regressions detected.** The system is stable.

---

## 2. Recommended Release 7Q Scope

### Focus: Documentation Only (Safest Possible)

Given that the admin portal is functionally complete and Ryan is actively using it, the highest-value work is **documentation that helps Ryan operate independently** — not more code changes.

### In Scope

| # | Item | Type | Effort | Risk |
|---|------|------|--------|------|
| 1 | **Admin Operations Quick Reference** — a single-page guide for Ryan covering: approve, assign, cancel, archive, delete, purge, restore, offline client creation, multi-day booking | Documentation | 1 hour | None |
| 2 | **Request Status Lifecycle Diagram** — visual reference showing all status transitions | Documentation | 30 min | None |
| 3 | **Emergency/Incident Response Checklist** — what to do if notifications stop, calendar breaks, or the site is down | Documentation | 30 min | None |
| 4 | **Smoke test addendum** — add Terms/Privacy page check and multi-day date picker check to existing checklist | Documentation | 15 min | None |

**Total: ~2.5 hours, documentation-only, zero production risk.**

### Explicitly Deferred

| Item | Reason |
|------|--------|
| Notification delivery status on request rows | Requires backend API change to include ledger data in request list response |
| Audit trail visible in request list | Requires backend change to return audit_log in list queries |
| "Last updated" timestamp on rows | Low value; data already available in CareCard detail |
| Data export documentation | Low priority; feature works, just undocumented |
| Admin CareCard acceptance display | Planned in original spec but low priority |

---

## 3. Detailed Deliverables

### 3.1 Admin Operations Quick Reference

**File:** `docs/operations/admin-quick-reference.md`

Sections:
1. **Logging In** — URL, credentials, role expectations
2. **Dashboard Overview** — stat cards, filters, views (Scheduler, List, Staff, Clients)
3. **Request Lifecycle** — status flow diagram reference
4. **Approving a Request** — step-by-step
5. **Assigning Staff** — step-by-step, what happens with calendar
6. **Creating a Manual Booking** — New Visit modal, single-day vs multi-day vs selected-dates
7. **Cancelling a Visit** — what cascades, what notifications fire
8. **Archiving and Deleting** — when to use each, how purge works
9. **Restoring a Record** — Restore to Approved, Reopen to Pending
10. **Managing Offline Clients** — link to existing guide
11. **Managing Staff** — create, assign, disable, link login
12. **Google Calendar** — what syncs, when to reconnect, troubleshooting link
13. **Notifications** — what emails are sent, when, kill switch reference
14. **Common Issues** — FAQ-style troubleshooting

### 3.2 Request Status Lifecycle Diagram

**Included in:** `docs/operations/admin-quick-reference.md` (Section 3)

```
PENDING_REVIEW → MEET_GREET_REQUIRED → MG_SCHEDULED → MG_COMPLETED → APPROVED
PENDING_REVIEW → APPROVED (skip M&G)
APPROVED → ASSIGNED (staff assigned, calendar synced)
ASSIGNED → COMPLETED
ASSIGNED → CANCELLED
Any Active → CANCELLED → ARCHIVED → DELETED (Trash) → PURGED (permanent)
CANCELLED → RESTORED TO APPROVED
DELETED → RESTORED TO APPROVED
```

### 3.3 Emergency/Incident Response Checklist

**File:** `docs/operations/emergency-response-checklist.md`

Sections:
1. **Notifications stopped sending** — check NOTIFICATION_DRY_RUN, check Postmark dashboard, check quota
2. **Google Calendar not syncing** — check connection status in admin, reconnect flow
3. **Site is down / 500 errors** — check CloudFront, check Lambda errors in CloudWatch
4. **Client can't log in** — check Cognito user status, resend invite
5. **Data looks wrong** — check Data Issues filter, check audit log in CareCard
6. **Need to stop all notifications immediately** — set NOTIFICATION_DRY_RUN=true
7. **Need to rollback a deployment** — frontend (S3 revert), backend (terraform apply with previous code)

### 3.4 Smoke Test Addendum

**File:** Update `docs/validation/production-smoke-test-checklist.md`

Add:
- Scenario D: Terms & Privacy Pages (navigate to /terms, /privacy, verify content renders)
- Scenario E: Selected-Date Booking (use date picker, submit 3 non-consecutive dates, verify JOBs)

---

## 4. Files Affected

| File | Change | New? |
|------|--------|------|
| `docs/operations/admin-quick-reference.md` | Admin operations guide | ✅ New |
| `docs/operations/emergency-response-checklist.md` | Incident response guide | ✅ New |
| `docs/validation/production-smoke-test-checklist.md` | Add Scenarios D and E | Modified |

### Files NOT Changed

- No frontend code
- No backend code
- No Terraform
- No CSS
- No API changes

---

## 5. Acceptance Criteria

- [ ] `docs/operations/admin-quick-reference.md` exists with all 14 sections
- [ ] Includes a text-based status lifecycle diagram
- [ ] `docs/operations/emergency-response-checklist.md` exists with 7 scenarios
- [ ] `docs/validation/production-smoke-test-checklist.md` updated with Scenarios D and E
- [ ] All documentation is accurate to current production behavior
- [ ] No code changes, no deployment required
- [ ] Ryan can use the quick reference to perform all common admin tasks without developer assistance

---

## 6. Validation Plan

| # | Check | Method |
|---|-------|--------|
| 1 | Admin quick reference covers all workflows | Manual review against admin dashboard features |
| 2 | Status lifecycle matches actual code behavior | Cross-reference with `getWorkflowState()` in AdminDashboard.jsx |
| 3 | Emergency checklist references correct env vars | Cross-reference with `locals.tf` and notification runbook |
| 4 | Smoke test addendum is executable | Walk through steps mentally against production |
| 5 | No broken links or references | Check all cross-references to other docs |

---

## 7. Risks and Rollback

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Documentation is inaccurate | Low | Low | Cross-reference with code; Matthew reviews before publishing |
| Documentation becomes stale | Medium | Low | Include "Last Updated" header; update with each release |
| Ryan confused by documentation | Very Low | None | Plain language, step-by-step format |

**Rollback:** Delete the new files. No production impact.

---

## 8. Guardrails

- Do NOT modify any application code
- Do NOT modify Terraform
- Do NOT modify CSS or frontend components
- Do NOT modify backend handlers or notification logic
- Do NOT deploy anything — this is documentation only
- Do NOT include internal developer details (AWS account IDs, secret names) in admin-facing docs
- Keep language appropriate for a business owner (Ryan), not a developer

---

## 9. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 7Q: Production Operations Readiness Documentation.

Documentation-only. No code changes, no deployment.

=== 1. Create docs/operations/admin-quick-reference.md ===

A single-page admin operations guide for Ryan (business owner) covering:

1. Logging In — URL (toganddogs.usmissionhero.com), use owner credentials
2. Dashboard Overview — stat cards (Intake Queue, Needs Assignment, Scheduled, Completed), view selector (Scheduler, List, Staff Mgmt, Client Mgmt)
3. Request Status Lifecycle — text diagram showing all transitions:
   PENDING_REVIEW → APPROVED → ASSIGNED → COMPLETED
   Any → CANCELLED → ARCHIVED → DELETED → PURGED
   CANCELLED/DELETED → RESTORE TO APPROVED
4. Approving a Request — find in Intake Queue or Booking Queue, click Approve
5. Assigning Staff — click Assign button, select staff from dropdown, calendar event auto-created
6. Creating a Manual Booking — click + New Visit, select client/pets/dates/service, three modes (Single Day, Date Range, Pick Days)
7. Cancelling a Visit — click Cancel in action menu, provide reason, cascades to all child JOBs, deletes calendar events, sends notification
8. Archiving and Deleting — Archive = saved for records, Delete = move to Trash, Purge = permanent (requires typed confirmation)
9. Restoring a Record — from Trash or Archive, use Restore to Approved or Reopen to Pending
10. Managing Offline Clients — create profile without email, book on their behalf, link to login later if needed
11. Managing Staff — create profile, assign to visits, disable/delete, link Cognito login
12. Google Calendar — events auto-sync on assignment, reconnect if "Needs Reconnect" badge appears
13. Notifications — emails sent on: new request (admin), approval (client), assignment (staff+client), cancellation (all). Kill switch: contact developer to set DRY_RUN.
14. Common Issues — "No pets showing" (check archived), "Calendar not syncing" (check connection), "Client can't log in" (resend invite), "Record stuck" (check Data Issues filter)

Tone: Plain language for a business owner. No developer jargon.
Include "Last Updated: Release 7Q" header.

=== 2. Create docs/operations/emergency-response-checklist.md ===

A quick-reference for "something went wrong" scenarios:

1. Notifications stopped — Check Postmark dashboard, check if DRY_RUN was accidentally enabled, check monthly quota
2. Google Calendar not syncing — Check admin Settings page for connection status, try Disconnect + Reconnect
3. Site showing errors — Clear browser cache, try incognito, if persistent contact developer
4. Client can't log in — Check Client Management for their status badge, try Resend Invite or Set Temp Password
5. Wrong data showing — Check Data Issues filter, refresh the page, check if record was accidentally archived
6. Need to stop all emails immediately — Contact developer to set NOTIFICATION_DRY_RUN=true
7. Need to undo a deployment — Contact developer for S3 revert (frontend) or Lambda rollback (backend)

Tone: Calm, actionable steps. No panic language.
Include "Last Updated: Release 7Q" header.

=== 3. Update docs/validation/production-smoke-test-checklist.md ===

Add two new scenarios at the end:

Scenario D: Terms & Privacy Pages
- [ ] Navigate to /terms directly — confirm page renders with version badge and all sections
- [ ] Navigate to /privacy directly — confirm page renders with version badge and all sections
- [ ] Click footer "Terms of Service" link — confirm navigation works
- [ ] Click footer "Privacy Policy" link — confirm navigation works
- [ ] Open /book intake form, reach Step 3 — confirm acceptance checkbox is visible and required

Scenario E: Selected-Date Booking (Admin)
- [ ] Open Admin Dashboard → click + New Visit
- [ ] Select "Pick Days" scheduling mode
- [ ] Select 3 non-consecutive dates on the calendar
- [ ] Confirm summary shows "3/14 days selected" with correct dates
- [ ] Submit the booking
- [ ] Confirm 3 child JOB records created (check Request List or DynamoDB)
- [ ] Confirm 3 Google Calendar events created (one per selected date)

=== 4. Do NOT ===

- Do NOT modify any .jsx, .css, .py, .tf, or .js files
- Do NOT deploy anything
- Do NOT run terraform
- Do NOT modify the frontend build

Return: files created/modified, word count, confirmation no code was touched.
```

---

## 10. Commit Command (After Approval)

```bash
git add docs/operations/admin-quick-reference.md docs/operations/emergency-response-checklist.md docs/validation/production-smoke-test-checklist.md
git commit -m "docs: Release 7Q — admin operations guide, emergency checklist, smoke test addendum"
```
