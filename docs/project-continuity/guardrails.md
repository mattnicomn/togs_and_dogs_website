# Project Guardrails

**These rules apply to ALL AI agents (ChatGPT, Kiro, AG) working on this project.**

---

## Secrets and Credentials

- ❌ Never commit secrets, tokens, passwords, API keys, or webhook secrets
- ❌ Never print/log Cognito tokens, Stripe keys, OAuth tokens, or session data
- ❌ Never include private emails, phone numbers, addresses, or client details in docs
- ❌ Never include the previously-exposed shared development password value
- ✅ Use placeholders only (e.g., `<POOL_ID>`, `<USERNAME>`, `sk_test_XXXXX`)

## Git Discipline

- ✅ Use `git add <specific_files>` only (targeted add)
- ❌ Never use `git add .`
- ❌ Never commit: `.tfplan`, `terraform.tfvars`, `task.md`, `walkthrough.md`, screenshots, logs, scratch files, generated artifacts, browser storage exports, raw Cognito exports, or credentials
- ✅ Keep commits scoped to the stated release/task

## Production Safety

- ❌ No production deployment without Matthew's explicit approval
- ❌ No `terraform apply` without Matthew reviewing the plan first
- ❌ No Lambda code updates without test suite passing
- ❌ No frontend deployment without build passing
- ❌ No DynamoDB writes (creating clients/bookings/jobs) without approved test data
- ❌ No Google Calendar event creation without approval
- ❌ No emails/SMS/notifications to real clients without approval

## Tenant and Multi-Business Safety

- ❌ Do not disable or change `TENANT_RESOLUTION_MODE` without Matthew's explicit approval (strict `multi` mode is active and validated)
- ❌ Do not create a second tenant without explicit approval
- ❌ Do not modify existing tenant metadata (tier/status) without approval
- ❌ Do not run `scripts/provision_tenant.py --mode=apply` without approval

## Stripe / Payments

- ❌ No Stripe live mode activation (blocked on EIN)
- ❌ No real payment card charges
- ❌ No Stripe Dashboard configuration changes without approval
- ❌ Sandbox operations only until explicitly told otherwise

## Mobile / App Store

- ❌ No public App Store submission without explicit approval
- ❌ No EAS build without approval (creates billable resource)
- ❌ No TestFlight/App Store Connect changes without approval
- ❌ Do not add Ryan or external testers without approval

## Cognito / Auth

- ❌ No user creation/deletion/group changes without approval
- ❌ No password resets without approval
- ❌ No Cognito pool schema changes without approval

## Plan/Apply Separation

- ✅ Always `terraform plan` first, report output, wait for approval
- ✅ Always run tests before deployment
- ✅ Always document what was done in release notes
- ✅ Planning docs are safe to create/commit without approval
- ✅ Read-only CloudWatch/DynamoDB queries are safe

## Notification Safety

- ❌ Do not send emails to real clients during testing
- ❌ Do not create bookings that trigger notifications unless client email is omitted
- ✅ Use test data with no email address to prevent notification delivery
