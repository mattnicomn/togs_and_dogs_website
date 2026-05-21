# Roadmap & Phase Plan

Last updated: 2026-05-21

## Completed Releases

| Release | Scope | Status |
|---------|-------|--------|
| 1 | Scheduling Record Integrity | ✅ Accepted |
| 2 | Intake Enhancements | ✅ Accepted |
| 3 | Client Management Automation | ✅ Accepted |
| 4A | Multi-Pet Intake | ✅ Accepted |
| 4B | CareCard Multi-Pet Display | ✅ Accepted |
| 4C | Client Phone Persistence | ✅ Accepted |
| 4D | Quote/Payment Inline Editing | ✅ Accepted |
| 4E | Staff Assignment from CareCard | ✅ Accepted |
| 5A | Multi-Pet Independent Editing | ✅ Accepted |
| 5B | Add Pet from CareCard | ✅ Accepted |
| 5C | Archive Pet from CareCard | ✅ Accepted |
| 5D | Client Pet Visibility | ✅ Accepted |
| 5E | Permanent Pet Delete | ⏸️ Deferred indefinitely |
| 5F | Archived Pets Visibility & Restore | ✅ Accepted |
| 6A | Client Approval Email Template | ✅ Accepted |
| 6B | Notification Coverage Expansion | ✅ Accepted (Phase 1 + 2) |

## Current / Next

| Release | Scope | Status | ETA |
|---------|-------|--------|-----|
| 6C | Postmark Production Readiness | Planning | ~30 min |

## Future Candidates (Prioritized)

### Tier 1: Quick Wins / Operational
| Item | Effort | Value |
|------|--------|-------|
| Cancellation reason persistence | 15 min | Completes notification polish |
| Postmark sender verification | 30 min | Unblocks external delivery |
| Repo cleanup (gitignore, temp files) | 15 min | Hygiene |

### Tier 2: Client Experience
| Item | Effort | Value |
|------|--------|-------|
| Client portal identity resolution | 2-4 hrs | Unblocks client portal testing |
| Repeat customer booking flow | 4-8 hrs | Enables returning clients to book |
| Client-facing booking confirmation page | 2-4 hrs | Better UX after submission |

### Tier 3: Operational Maturity
| Item | Effort | Value |
|------|--------|-------|
| Notification quota tracker | 4-6 hrs | Cost protection at scale |
| Postmark webhooks (bounce handling) | 4-6 hrs | Delivery observability |
| Notification ledger (audit trail) | 6-8 hrs | Compliance/debugging |
| Google Calendar sync reliability | 4-6 hrs | Reduces refresh-token errors |

### Tier 4: Admin Productivity
| Item | Effort | Value |
|------|--------|-------|
| Admin dashboard filter integrity | 2-4 hrs | Count/display alignment |
| CareCard admin entry improvements | 2-4 hrs | Pet loading reliability |
| Reporting/analytics dashboard | 8-16 hrs | Business insights |
| Staff availability/scheduling | 8-16 hrs | Operational efficiency |

## Decision Framework
Priority is determined by:
1. **Is it blocking real client operations?** → Do it now
2. **Is it a quick win (<1 hour)?** → Bundle with next release
3. **Does it improve reliability of existing features?** → Schedule soon
4. **Is it a new feature?** → Plan and scope before implementing
