# Project Guardrails

**These rules apply to ALL AI agents (ChatGPT, Kiro, AG) working on this project.**

---

## Secrets and Credentials

- ❌ Never commit secrets, tokens, passwords, API keys, or webhook secrets
- ❌ Never print/log Cognito tokens, Stripe keys, OAuth tokens or codes, JWTs, raw auth/session data, `terraform.tfvars` values, or other credentials
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
- ❌ No production test data or DynamoDB writes (including clients, bookings, or jobs) without Matthew's explicit approval
- ❌ No Google Calendar event creation without approval
- ❌ No emails/SMS/notifications to real clients without approval

## Tenant and Multi-Business Safety

- ❌ **BUSINESS / BRAND OWNERSHIP BOUNDARY**: Togs & Dogs is Ryan's individual pet-care business/tenant. It is NOT the USMissionHero platform brand and must not be used as the namespace, branding, default identity, or implied business owner for unrelated tenants. USMissionHero LLC is the platform/operator layer. Tenant business identity must remain isolated per tenant.
- ❌ Do not disable or change `TENANT_RESOLUTION_MODE` without Matthew's explicit approval (strict `multi` mode is active and validated)
- ❌ Do not create, remove, or repurpose any tenant—including the existing `test_tenant_alpha` validation tenant—without explicit approval
- ❌ Do not modify existing tenant metadata (tier/status) without approval
- ❌ Do not run `scripts/provision_tenant.py --mode=apply` without approval

## Stripe / Payments

- ❌ No Stripe live mode activation (blocked on EIN)
- ❌ No live subscription Checkout work until the documented EIN, pricing, product, policy, and Matthew approval prerequisites are satisfied
- ❌ No real payment card charges
- ❌ No Stripe Dashboard configuration changes without approval
- ❌ Sandbox operations only until explicitly told otherwise

## Mobile / App Store

- ❌ No public App Store submission without explicit approval
- ❌ No EAS build without approval (creates billable resource)
- ❌ No TestFlight, App Store Connect, Google Play build, or distribution changes without explicit approval
- ✅ Ryan's physical Android install and operational review were completed on 2026-08-15; the full historical remediation smoke matrix was not rerun
- ❌ Do not add Ryan or external testers, issue another build, change distribution, or perform production-write testing without explicit approval

## Cognito / Auth

- ❌ No user creation/deletion/group changes without approval
- ❌ No password resets without approval
- ❌ No Cognito pool schema changes without approval

## Email Provider

- ✅ Postmark is the approved production transactional email provider
- ❌ AWS SES production sending was NOT approved (sandbox-only); do not pursue SES production access without explicit Matthew approval
- ❌ Do not switch Cognito or application notifications to SES
- ❌ Never expose Postmark tokens, Secrets Manager values, or API keys
- ✅ For Cognito-originated email, the approved architecture is: Cognito → Custom Email Sender Lambda → Postmark
- ✅ Existing sender identity: `support@usmissionhero.com` (verified in Postmark)

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

## Cross-Platform Service & Workflow Alignment

- ✅ Ryan O1 Overnight Fixed Scheduling is committed and pushed but **NOT DEPLOYED** and is absent from the current internal mobile builds
- ❌ Do not deploy O1 without a separate explicit Matthew approval
- ✅ Any operational service or workflow change must be assessed across: Web, Mobile, Shared contracts, Backend, Calendar/scheduling, and Notifications
- ✅ Shared contracts (`shared/constants/`) are the canonical source of truth for service IDs, labels, durations, visit rules, and time windows
- ❌ Do not create platform-specific duplicate service definitions (web-only or mobile-only service IDs)
- ✅ Service IDs, labels, durations, statuses, validations, time-window definitions, and scheduling semantics must remain aligned across all platforms
- ✅ Operational screens should expose one obvious primary next action where safe
- ❌ Do not bypass RBAC, required human review, payment gates, cancellation confirmations, or tenant isolation for workflow convenience
