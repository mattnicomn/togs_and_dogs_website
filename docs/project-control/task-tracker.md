# Task Tracker

Last updated: 2026-05-21

## Active / Next Up

| # | Task | Phase | Priority | Status | Owner | Validator | Target |
|---|------|-------|----------|--------|-------|-----------|--------|
| 1 | ~~Verify Postmark sender signature~~ | 6C | High | ✅ Complete | AG | Matthew | Release 6C |
| 2 | ~~Update `postmark-setup.md` to reflect approved/production status~~ | 6C | High | ✅ Complete | Kiro | — | Release 6C |
| 3 | ~~Send test email to real external address~~ | 6C | High | ✅ Complete (CloudWatch evidence) | AG | Matthew | Release 6C |
| 4 | ~~Fix Needs Assignment count/navigation mismatch~~ | 6D Phase 1 | High | ✅ Deployed | Kiro | AG | Release 6D |
| 5 | ~~Harden `isDeletedRecord` — remove `deleted_at` fallback~~ | 6D Phase 2 | High | ✅ Deployed | Kiro | AG | Release 6D |
| 6 | ~~Frontend purge visibility & bulk purge pre-validation~~ | 6D Phase 3 | Medium | ✅ Deployed | Kiro | AG | Release 6D |
| 7 | ~~Backend delete atomicity — reject DELETE on active records~~ | 6D Phase 4 | High | ✅ Deployed | Kiro | AG | Release 6D |
| 8 | ~~AG pre-scan: find records with `deleted_at` but non-DELETED status~~ | 6D Pre-work | High | ✅ Complete | AG | Kiro | Release 6D |
| 9 | ~~Data cleanup: fix zombie REQ#69780136~~ | 6D Cleanup | Medium | ✅ Complete | AG | Kiro | Release 6D |
| 10 | Cancellation reason persistence in review handler | Backlog | Low | Planned | Kiro | AG | TBD |
| 11 | Client portal identity resolution guardrail | Backlog | Medium | Planned | Kiro | AG | TBD |
| 12 | Admin/staff email protection on client profile auto-creation | Backlog | Medium | Planned | Kiro | AG | TBD |
| 13 | Investigate `usmissiohero.com` recipient domain typo | Data Quality | Low | Not Started | Matthew | — | TBD |

## Completed (Recent)

| # | Task | Release | Completed | Commit |
|---|------|---------|-----------|--------|
| 17 | Staff calendar sync reliability (7 phases) | 6G | 2026-05-22 | `e3fe2f6` |
| 16 | Repeat customer / offline client booking flow | 6F | 2026-05-22 | `3934ef5` |
| 15 | Identity messaging + phone normalization + protected email guard | 6E | 2026-05-21 | `79b2b89` |
| 14 | Admin filter integrity & safe delete guardrails | 6D | 2026-05-21 | `ee751c1` |
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
| B15 | Move protected emails from hardcoded to config/env vars | Infrastructure | Low | Currently hardcoded in admin_handler.py and client_profile.py |

## Deferred Indefinitely

| Task | Reason |
|------|--------|
| Permanent pet delete (Release 5E) | Ghost-reference risk |
| SES as notification provider | Replaced by Postmark |
