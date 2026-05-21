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
**Sender signature mismatch:**
- `NOTIFICATION_EMAIL_FROM` in Terraform = `support@usmissionhero.com`
- `postmark-setup.md` documents verified sender as `mbn@usmissionhero.com`
- If the full domain `usmissionhero.com` is verified in Postmark, both work
- If only `mbn@usmissionhero.com` is verified as a sender signature, `support@` may fail for external recipients

## Scope

### Must Do (Release 6C)
1. Verify sender signature status in Postmark dashboard
2. Send test email to a real external address (Gmail, Outlook, etc.)
3. Update `docs/operations/postmark-setup.md` to reflect current production status
4. Update `docs/release-notes/index.md`

### May Do (If Sender Issue Found)
- Change `NOTIFICATION_EMAIL_FROM` in `locals.tf` to match verified sender
- OR verify `support@usmissionhero.com` as additional sender in Postmark

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
