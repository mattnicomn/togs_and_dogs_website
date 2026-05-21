# Release 6C: Postmark Production Readiness

## Overview
Validates and documents that the Postmark notification system is fully production-approved and capable of delivering emails to external (non-`@usmissionhero.com`) recipients.

## Scope
- Documentation and operational validation only
- No application code changes
- No Terraform infrastructure changes

## Validation Result (2026-05-21)
- **Postmark Account:** Production-approved (confirmed via CloudWatch evidence)
- **External Delivery:** ✅ Successful delivery to `gmail.com` confirmed in CloudWatch logs (2026-05-19)
- **Sender:** `support@usmissionhero.com` accepted by Postmark in production sends
- **DKIM/SPF:** Verified (2026-05-07)
- **DRY_RUN:** `false` (live delivery active)
- **Provider:** `postmark` via `external_provider` mode

## Evidence
CloudWatch `NOTIFICATION_SUCCESS` entries from `/aws/lambda/togs-and-dogs-prod-assign` show:
- `provider: postmark`
- `recipient_domains: ["gmail.com"]`
- `status: success`
- `message_id` present (Postmark MessageID)

A Postmark Test Mode account cannot deliver to external domains. Successful `gmail.com` delivery confirms production approval.

## Unexpected Finding
- Recipient domain typo `usmissiohero.com` (missing 'n') observed in VISIT_SCHEDULED logs
- This is a data quality issue on a staff/client record, not a notification system bug
- Tracked as backlog item for investigation/correction

## Deferred
- Notification ledger (DynamoDB audit trail)
- Quota tracker (not urgent at current volume)
- Postmark webhooks (bounce/complaint auto-handling)
- `visit_time_changed` template (no trigger exists)

## Files Changed
- `docs/operations/postmark-setup.md` — updated to reflect production-approved status
- `docs/planning/release-6c-postmark-production-readiness-plan.md` — marked validation complete
- `docs/release-notes/release-6c-postmark-production-readiness.md` — this file
- `docs/release-notes/index.md` — added 6C entry
- `docs/project-control/task-tracker.md` — updated task status + new backlog item
