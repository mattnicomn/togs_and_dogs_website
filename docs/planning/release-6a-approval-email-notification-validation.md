# Release 6A: Client Approval Email Notification — Validation Report

## Summary
Dry-run validation PASSED on 2026-05-18. The `CUSTOMER_APPROVED` email template renders correctly in dry-run mode with no critical failures.

## Deployment Timeline

| Date | Event | Result |
|------|-------|--------|
| 2026-05-18 | Initial deploy (templates + DRY_RUN=true) | Applied successfully |
| 2026-05-17 | Dry-run validation attempt 1 | FAILED — `'NoneType' object has no attribute 'replace'` |
| 2026-05-18 | Null-safety hotfix applied + redeployed | Applied (terraform: "no changes" — fix was included in prior apply) |
| 2026-05-18 | Dry-run validation attempt 2 | PASSED ✅ |

## Dry-Run Validation Results

### Environment Confirmed
- `NOTIFICATIONS_ENABLED = "true"`
- `NOTIFICATION_DRY_RUN = "true"`
- `NOTIFICATION_PROVIDER = "postmark"`
- `NOTIFICATION_MODE = "external_provider"`

### Test Execution
- **Action:** Approved a test request with `client_email = mbn@usmissionhero.com`
- **Lambda:** `togs-and-dogs-prod-review`
- **CloudWatch Log Group:** `/aws/lambda/togs-and-dogs-prod-review`

### CloudWatch Log Validation
- ✅ `NOTIFICATION_DRY_RUN_LOG` appeared after approval
- ✅ `provider = postmark`
- ✅ `dry_run = true`
- ✅ Recipient domain = `usmissionhero.com`
- ✅ Approval email subject preview rendered correctly
- ✅ No `NOTIFICATION_CRITICAL_FAILURE` after hotfix deploy
- ✅ No `AttributeError`
- ✅ No `NOTIFICATION_MISSING_TEMPLATE`
- ✅ No real Postmark API call made (dry-run mode)

### Error History (Pre-Fix)
- May 11-17: `type object 'NotificationTemplates' has no attribute 'customer_approved'` (template method missing)
- May 17: `'NoneType' object has no attribute 'replace'` (null service_type in normalize_context)
- May 18+: No errors after null-safety hotfix

## Hotfix Details

### Root Cause
`normalize_context()` in `templates.py` used:
```python
service_type = context.get('service_type', 'PET_SITTING')
```
The default `'PET_SITTING'` only applies when the key is **absent**. When the key exists with value `None` (which happens when the DynamoDB record has no `service_type` field), `.get()` returns `None`. Then `service_type.replace('_', ' ')` crashes.

### Fix Applied
1. Added `_safe(value, default)` static helper method
2. Changed to `context.get('service_type') or 'PET_SITTING'` — the `or` handles both missing keys AND explicit `None`
3. Applied same pattern to `client_name`, `staff_name`, `pet_names`, `start_date`

### Local Test Results
6 tests covering all-None, happy path, empty strings, missing keys, None service_type, unknown service_type — all PASS.

## Current Status
**Dry-Run Validated — Ready for Controlled Live Send Test**

### Next Steps (Pending Approval)
1. Set `NOTIFICATION_DRY_RUN = "false"` in `infra/prod/locals.tf`
2. `terraform apply`
3. Approve test request with `client_email = mbn@usmissionhero.com`
4. Verify email arrives in inbox
5. Verify HTML rendering, links, content accuracy
6. Verify idempotency (re-approve same request → no duplicate email)

### Postmark Account Note
Account is still in Test Mode. Until approved by Postmark, emails can only be delivered to `@usmissionhero.com` addresses. This provides a natural safety gate for the live send test.
