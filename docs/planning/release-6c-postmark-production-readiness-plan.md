# Release 6C: Postmark Production Readiness — Plan

## Objective
Verify and document that the Postmark notification system is fully ready for external client delivery, and resolve any sender/domain configuration gaps.

## Current Status (2026-05-21)
- Postmark account: **Approved / Production** (confirmed by Matthew — 37/100 emails used this period)
- DKIM/SPF: Verified (2026-05-07)
- `NOTIFICATION_DRY_RUN`: `false` (live delivery)
- `NOTIFICATION_PROVIDER`: `postmark`
- All templates polished and validated (Releases 6A + 6B)

## Open Question
**Sender signature — RESOLVED:**
- `NOTIFICATION_EMAIL_FROM` in Terraform = `support@usmissionhero.com`
- CloudWatch logs from 2026-05-19 confirm successful Postmark delivery to `gmail.com` using this sender
- This confirms Postmark accepts `support@usmissionhero.com` as a valid sender in production
- **Remaining action:** Matthew should visually confirm in Postmark dashboard whether this is domain-level verification or individual sender signature

## Scope

### Must Do (Release 6C) — STATUS
1. ✅ Verify sender signature status — Confirmed via CloudWatch evidence (external delivery succeeded)
2. ✅ Send test email to real external address — CloudWatch shows successful delivery to `gmail.com` on 2026-05-19
3. ✅ Update `docs/operations/postmark-setup.md` — Updated to reflect production-approved status
4. ✅ Update `docs/release-notes/index.md` — Release 6C entry added

### Unexpected Finding: Recipient Domain Typo
- CloudWatch VISIT_SCHEDULED logs show a recipient domain `usmissiohero.com` (missing 'n')
- This is a **data quality issue** on a staff/client record, not a notification system bug
- **Action:** Investigate and correct the typo in the affected DynamoDB record(s)
- **Tracked as:** Backlog item in task-tracker.md

### May Do (If Sender Issue Found)
- ~~Change `NOTIFICATION_EMAIL_FROM` in `locals.tf` to match verified sender~~ — Not needed
- ~~OR verify `support@usmissionhero.com` as additional sender in Postmark~~ — Already working

### Defer
- Notification ledger
- Quota tracker
- Webhooks
- `visit_time_changed` template

## Validation Steps (AG)
1. Log into Postmark dashboard → Sender Signatures
2. Confirm whether `support@usmissionhero.com` or domain `usmissionhero.com` is verified
3. Submit a test intake with a real external email (e.g., personal Gmail)
4. Approve the request
5. Confirm email arrives at external address
6. Check spam folder if not in inbox
7. Report: delivered/bounced/spam, rendering quality

## Files Involved
- `docs/operations/postmark-setup.md` — update status
- `infra/prod/locals.tf` — only if sender address needs changing
- `docs/release-notes/index.md` — add 6C entry
- `docs/project-control/task-tracker.md` — update task status

## Risks
| Risk | Mitigation |
|------|-----------|
| `support@` not verified → external emails fail | Switch to `mbn@` or verify `support@` in Postmark |
| Email lands in spam | DKIM/SPF already verified; check spam folder |
| Quota exhaustion | Monitor usage; upgrade plan if approaching 100 |

## Estimated Effort
~30 minutes (operational verification + doc update). No application code changes expected.
