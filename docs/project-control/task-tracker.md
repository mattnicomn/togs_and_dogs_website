# Task Tracker

Last updated: 2026-05-21

## Active / Next Up

| # | Task | Phase | Priority | Status | Owner | Validator | Target |
|---|------|-------|----------|--------|-------|-----------|--------|
| 1 | ~~Verify Postmark sender signature~~ | 6C | High | ✅ Complete | AG | Matthew | Release 6C |
| 2 | ~~Update `postmark-setup.md` to reflect approved/production status~~ | 6C | High | ✅ Complete | Kiro | — | Release 6C |
| 3 | ~~Send test email to real external address~~ | 6C | High | ✅ Complete (CloudWatch evidence) | AG | Matthew | Release 6C |
| 4 | Cancellation reason persistence in review handler | Backlog | Low | Planned | Kiro | AG | TBD |
| 5 | Client portal identity resolution guardrail | Backlog | Medium | Planned | Kiro | AG | TBD |
| 6 | Admin/staff email protection on client profile auto-creation | Backlog | Medium | Planned | Kiro | AG | TBD |
| 7 | Investigate `usmissiohero.com` recipient domain typo | Data Quality | Low | Not Started | Matthew | — | TBD |

## Completed (Recent)

| # | Task | Release | Completed | Commit |
|---|------|---------|-----------|--------|
| 7 | Polish `visit_cancelled` template | 6B Phase 2 | 2026-05-20 | `f12d92f` |
| 8 | Polish `staff_assigned` + `visit_scheduled` templates | 6B Phase 1 | 2026-05-19 | `c2bb31b` |
| 9 | Polish `request_received` admin notification | 6A Hotfix 1 | 2026-05-18 | `8350ac5` |
| 10 | Implement `customer_approved` template + null-safety | 6A | 2026-05-18 | `32fadc0` |
| 11 | Release 5F: Archived pets visibility & restore | 5F | 2026-05-15 | — |
| 12 | Release 5D: Client pet visibility | 5D | 2026-05-15 | — |
| 13 | Release 5C: Archive pet from CareCard | 5C | 2026-05-15 | — |
| 14 | Release 5B: Add pet from CareCard | 5B | 2026-05-15 | — |
| 15 | Release 5A: Multi-pet independent editing | 5A | 2026-05-15 | — |

## Backlog (Prioritized)

| # | Task | Category | Priority | Notes |
|---|------|----------|----------|-------|
| B1 | Cancellation reason persistence | Notifications | Low | 2-3 line fix in review_handler |
| B2 | Client portal identity resolution | Auth/Identity | Medium | Admin/owner can't use client portal |
| B3 | Admin/staff email protection on auto-profile | Auth/Identity | Medium | Prevent accidental client profiles for admin emails |
| B4 | Notification quota tracker | Notifications | Low | Not urgent at 37/100 usage |
| B5 | Postmark webhooks (bounce/complaint) | Notifications | Low | Adds observability, not blocking |
| B6 | Notification ledger (DynamoDB audit) | Notifications | Low | From original spec, deferred |
| B7 | `visit_time_changed` template polish | Notifications | None | No trigger exists — dormant |
| B8 | Repeat customer profile booking flow | Client Portal | Medium | Existing clients can't book from portal |
| B9 | Staff calendar sync reliability | Integrations | Medium | Google refresh token errors observed |
| B10 | CareCard admin entry improvements | Admin UI | Low | Pet loading failures observed |
| B11 | Admin dashboard filter integrity | Admin UI | Low | Count/filter alignment |
| B12 | AWS cost allocation tagging | Infrastructure | Low | Standardize tags across all Terraform resources |
| B13 | Admin-created CareCards/visits | Admin UI | Medium | Allow admin to create visits without public form |
| B14 | Recipient domain typo `usmissiohero.com` | Data Quality | Low | Typo in staff/client record — investigate and correct |

## Deferred Indefinitely

| Task | Reason |
|------|--------|
| Permanent pet delete (Release 5E) | Ghost-reference risk |
| SES as notification provider | Replaced by Postmark |
