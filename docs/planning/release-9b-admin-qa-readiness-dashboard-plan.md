# Release 9B: Admin QA / Smoke Test Dashboard & Ryan Readiness Checklist

**Status:** Planning
**Priority:** Medium (improves confidence before broader testing)
**Risk to Production:** Very Low (read-only status display + documentation)
**Terraform Required:** No (Option C docs-only) or Minimal (Option A lightweight UI)
**Backend Changes:** Optional (read-only health check endpoint)
**Scope:** Readiness visibility for Matthew/Ryan before production trial

---

## 1. Purpose

Provide a single place where Matthew and Ryan can verify the system is ready for broader business testing — without needing DynamoDB queries, CloudWatch log searches, or scattered release notes. Today, validating readiness requires:
- Manual smoke test checklist (docs/validation/)
- AWS console access for notification/calendar health
- Checking multiple operational docs
- Remembering which test records exist and whether they're cleaned up

---

## 2. Current Readiness Gaps

### What Still Blocks Ryan from Daily Usage

| Blocker | Status | Notes |
|---------|--------|-------|
| Ryan account access confirmed | ✅ | Owner Cognito account validated |
| Staff account(s) configured | ✅ | `mattnicomn10@yahoo.com` validated |
| Google Calendar connected | ⚠️ Must verify | Connection can expire; no visible status without opening Settings |
| Postmark sending enabled | ✅ | Live since Release 6A |
| Test records cleaned up | ⚠️ Partial | Some test bookings may remain from validation cycles |
| Mobile app distributed to Ryan | ❌ | Preview build exists but Ryan hasn't installed |
| Ryan has read the quick reference | ❌ | Doc exists but unconfirmed |

### What Must Be Manually Checked Today

| Check | Current Method | Effort |
|-------|---------------|--------|
| Google Calendar connected | Admin Dashboard → Settings card | 2 clicks |
| Postmark sending | CloudWatch logs or DynamoDB quota counter | 5+ min |
| Notification ledger health | DynamoDB scan | 5+ min |
| Test records exist | Request List → filter to test names | 2 min |
| Staff profiles active | Staff Management tab | 1 min |
| Client profiles exist | Client Management tab | 1 min |
| Multi-day booking works | Create test → verify JOBs | 10 min |
| Per-visit completion works | Staff mobile → complete day | 5 min |

---

## 3. Options Analysis

### Option A: Lightweight Checklist Section in Admin Dashboard

Add a small "System Health" or "Readiness" card panel to the Dashboard view showing:
- Google Calendar connection status (already fetched)
- Notification system status (enabled/dry-run indicator)
- Staff accounts count (active/assignable)
- Client profiles count
- Pending requests count
- Monthly notification quota usage

**Pros:** Ryan sees health at a glance every time he opens the dashboard
**Cons:** Requires frontend changes; some backend enrichment for notification status

### Option B: Dedicated QA/Readiness Tab

Add a full "QA" tab to the admin view selector with a structured checklist that auto-validates where possible.

**Pros:** Comprehensive, interactive
**Cons:** Significant frontend development; overkill for current user count (2 people)

### Option C: Documentation-Only Readiness Checklist (Recommended First)

Create a structured "Ryan Readiness Checklist" document that references existing admin screens and provides exact click-paths. No code changes.

**Pros:** Zero risk, zero deployment, immediately useful
**Cons:** Manual — requires Matthew/Ryan to follow the doc

### Recommendation: Option C First, Then Option A

Start with a documentation-only readiness checklist (zero risk). If Ryan uses the system daily and wants at-a-glance health, add the lightweight dashboard card in a follow-up release.

---

## 4. Readiness Checklist (The Deliverable)

### Categories

#### 1. Authentication & Access
- [ ] Ryan can log into admin web dashboard
- [ ] Ryan can log into mobile app (iOS preview build installed)
- [ ] Staff test account (`mattnicomn10@yahoo.com`) can log into mobile app
- [ ] No expired Cognito sessions blocking access

#### 2. Google Calendar Integration
- [ ] Admin Dashboard → Settings shows "Connected" (green badge)
- [ ] If "Needs Reconnect" → follow reconnection guide
- [ ] Test: assign a booking → verify event appears on Google Calendar

#### 3. Notification System
- [ ] Postmark sender signature is active (check postmarkapp.com dashboard)
- [ ] Monthly quota not exceeded (check DynamoDB: `QUOTA#tog_and_dogs` / `MONTH#2026-XX`)
- [ ] No recent bounces/suppressions blocking valid recipients
- [ ] Kill switches NOT active: `NOTIFICATION_DRY_RUN=false`, `NOTIFICATIONS_ENABLED=true`

#### 4. Client Intake Flow
- [ ] Public `/book` form loads and renders correctly
- [ ] Terms/Privacy acceptance checkbox works
- [ ] Test submission → request appears in Intake Queue
- [ ] Admin receives "New Request" email notification

#### 5. Admin Approval & Assignment
- [ ] Approve a test request → status changes to APPROVED
- [ ] Client receives approval confirmation email
- [ ] Assign staff → status changes to ASSIGNED
- [ ] Staff receives assignment email
- [ ] Google Calendar event created

#### 6. Multi-Day Booking
- [ ] Create 3-day booking (admin or client)
- [ ] 3 child JOB records created
- [ ] 3 calendar events created
- [ ] Per-day completion badge shows "0/3 visits done"

#### 7. Staff Mobile Workflow
- [ ] Staff opens mobile app → sees Today/Upcoming schedule
- [ ] Staff taps visit → sees full booking detail
- [ ] Staff marks Day 1 completed with notes → only Day 1 gone
- [ ] Admin sees "1/3 visits done" on web dashboard

#### 8. Per-Visit Completion Visibility
- [ ] CareCard shows per-day breakdown for multi-day booking
- [ ] Each completed day shows timestamp + notes + who completed
- [ ] Pending days show as "Pending" with assigned worker

#### 9. Test Data Cleanup
- [ ] No test bookings remain in active filters (Pending, Approved, Assigned)
- [ ] Test records are archived or tagged as test
- [ ] No test notification records polluting the ledger

#### 10. Export/Backup
- [ ] Admin can click Export → generates Excel file
- [ ] File includes requests, clients, staff, completed visits

#### 11. Known Limitations (Documented, Not Blocking)
- [ ] Push notifications not enabled yet (future)
- [ ] Client-facing per-visit notes not visible (admin/staff only)
- [ ] Photo upload not supported (future)
- [ ] Mobile app requires Expo Go or preview build (not App Store yet)

---

## 5. Automated vs Manual Checks

| Check | Can Auto-Check? | Method |
|-------|----------------|--------|
| Google Calendar connected | ✅ | Already fetched by `getGoogleStatus()` |
| Notification system enabled | ✅ | Read env var status from config |
| Staff account count | ✅ | Already fetched by `getStaff()` |
| Client profile count | ✅ | Already fetched by `getClients()` |
| Monthly quota usage | ⚠️ Needs endpoint | Query DynamoDB counter |
| Pending requests exist | ✅ | Already computed for dashboard |
| Test records present | ❌ | Requires naming convention check |
| Email delivery working | ❌ | Requires Postmark dashboard or ledger query |
| Mobile build installed | ❌ | Physical device check only |
| Ryan has read docs | ❌ | Human confirmation only |

### Recommendation for Option A (Future)

If a dashboard health card is added later, show:
- 🟢 Google Calendar: Connected
- 🟢 Notifications: Active (37/100 this month)
- 🟢 Staff: 2 active, 2 assignable
- 🟢 Clients: 5 profiles
- 🟡 Pending: 2 requests need review
- ⚪ Mobile: N/A (check device)

This requires NO new backend endpoint — all data is already fetched by the admin dashboard on load.

---

## 6. Production Safety During Readiness Testing

| Concern | Mitigation |
|---------|-----------|
| Creating test records accidentally | Use clearly named test clients: "TEST-*" or "QA-*" |
| Accidental notifications to real clients | Test with offline clients (no email) or test email addresses |
| Calendar pollution | Use test bookings that are cancelled/archived after validation |
| Notification quota waste | Minimal — each test booking sends 1-2 emails max |
| Breaking live data | Readiness checks are read-only; only test bookings are created/destroyed |

---

## 7. Files to Create

| File | Change | New? |
|------|--------|------|
| `docs/validation/ryan-readiness-checklist.md` | Structured pre-trial readiness checklist | ✅ New |
| `docs/validation/production-smoke-test-checklist.md` | Add reference to readiness checklist | Modified (1 line) |

### Files NOT Changed

- No frontend code (Option C is docs-only)
- No backend code
- No Terraform
- No mobile app
- No infrastructure

---

## 8. Future Option A Enhancement (Not in 9B)

If Ryan wants visual health in the dashboard, a follow-up release could add a small "System Status" card to the Dashboard screen:

```jsx
<View style={styles.healthCard}>
  <Text style={styles.healthTitle}>System Health</Text>
  <HealthRow label="Google Calendar" status={googleStatus === 'CONNECTED' ? 'ok' : 'warn'} />
  <HealthRow label="Notifications" status="ok" detail="Active (37/100)" />
  <HealthRow label="Staff Ready" status={staffList.length > 0 ? 'ok' : 'warn'} detail={`${staffList.length} active`} />
</View>
```

This would be ~30 lines of JSX using data already available. Defer to Release 9C if desired.

---

## 9. Acceptance Criteria

- [ ] `docs/validation/ryan-readiness-checklist.md` exists with all 11 categories
- [ ] Checklist is actionable without developer access (no AWS console needed for most checks)
- [ ] Known limitations section is honest and clear
- [ ] No code changes required
- [ ] No deployment required
- [ ] Checklist can be printed/shared with Ryan as a PDF

---

## 10. Validation Plan

- Read through the checklist — verify every item references a real admin screen or document
- Cross-reference with existing smoke test checklist for overlap/gaps
- Confirm the checklist is completable by Ryan without Matthew's help (except AWS-specific checks)

---

## 11. Deployment Requirements

| Layer | Needed? |
|-------|---------|
| Backend | ❌ No |
| Web frontend | ❌ No |
| Mobile/EAS | ❌ No |
| Terraform | ❌ No |
| Documentation only | ✅ Yes |

---

## 12. Rollback

Delete the documentation file. Zero production impact.

---

## 13. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 9B: Admin QA Readiness Checklist.

Documentation-only. No code changes, no deployment.

=== 1. Create docs/validation/ryan-readiness-checklist.md ===

Title: "Ryan Production Readiness Checklist"
Last Updated: Release 9B
Audience: Ryan (Business Owner) + Matthew (Technical Support)

Structure the 11 categories from Section 4 of this planning document as a
printable/sharable checklist:

1. Authentication & Access (4 items)
2. Google Calendar Integration (3 items)
3. Notification System (4 items)
4. Client Intake Flow (4 items)
5. Admin Approval & Assignment (5 items)
6. Multi-Day Booking (4 items)
7. Staff Mobile Workflow (4 items)
8. Per-Visit Completion Visibility (3 items)
9. Test Data Cleanup (3 items)
10. Export/Backup (2 items)
11. Known Limitations (4 items — documented, not blocking)

For each item: include [ ] checkbox, brief description, and which screen/tool to check.
Add a "How to Check" column or note for non-obvious items.
Add a header note: "Complete this checklist before beginning daily operational use."
Add a footer: "If any item fails, contact Matthew before proceeding."

Tone: plain language for a business owner. No developer jargon.

=== 2. Update docs/validation/production-smoke-test-checklist.md ===

Add a reference at the top (after the title/intro):

> **Note:** For pre-trial readiness validation, see also:
> [Ryan Production Readiness Checklist](ryan-readiness-checklist.md)

=== 3. Do NOT ===

- Do NOT modify any code files
- Do NOT modify infrastructure
- Do NOT deploy anything
- Do NOT create test records

Return: files created/modified, word count, confirmation no code touched.
```

---

## 14. Commit Command (Planning Doc Only)

```bash
git add docs/planning/release-9b-admin-qa-readiness-dashboard-plan.md
git commit -m "docs: plan release 9b admin qa readiness dashboard"
```
