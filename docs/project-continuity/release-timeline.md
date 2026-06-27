# Release Timeline (Major Milestones)

**For full details, see `docs/release-notes/index.md`**

---

## Core Platform (Releases 1–9)

| Phase | Scope |
|-------|-------|
| 1–5 | Intake form, admin dashboard, pet/client management, multi-pet CareCard |
| 6 | Notifications (Postmark), permissions, Google Calendar sync, RBAC |
| 7 | Multi-day scheduling, admin hardening, Terms/Privacy, operations docs |
| 8 | Mobile React Native app (staff/admin/client), visit completion, notes |
| 9 | QA readiness, production operations, Google Calendar health |

## Mobile Distribution (Releases 10)

| Release | Milestone |
|---------|-----------|
| 10A–10C | TestFlight preparation, App Store Connect setup |
| 10D–10E | First iOS build + TestFlight upload |
| 10F–10K | P0 bug fixes, build 1.0.0(3) |

## Multi-Tenant Foundation (Releases 11)

| Release | Milestone |
|---------|-----------|
| 11A | SaaS architecture roadmap |
| 11B | DynamoDB key audit |
| 11C | Tenant metadata record created |
| 11D | Tenant enforcement hardening plan |
| 11E | **Tenant enforcement deployed** (validate_tenant_ownership in all handlers) |
| 11F–11G | Production deployment + monitoring checkpoint |

## Billing / Payments (Releases 12–14)

| Release | Milestone |
|---------|-----------|
| 12A–12C | Billing architecture + webhook design |
| 12D | **Stripe webhook handler + entitlement interface code** |
| 12G | Checkout Session creation endpoint |
| 12I | AWS Secrets + API Gateway Stripe route deployed |
| 12L | End-to-end sandbox payment validated |
| 12M–12N | Card-only + redirect fixes |
| 12O–12P | Duplicate payment guard |
| 12R | Admin payment link UI deployed |
| 12T–12W | Payment email send UI deployed + validated |
| 12X–12Z | Full sandbox payment lifecycle validated |
| 13A–13D | Live mode readiness planning (blocked on EIN) |
| 14A–14I | Admin UX polish, payment ops guide, support contact, readiness checkpoint |

## Mobile TestFlight (Releases 15)

| Release | Milestone |
|---------|-----------|
| 15B–15D | Mobile readiness audit + fresh build 1.0.0(4) |
| 15E | Internal TestFlight smoke validation passed |
| 15H | Matthew multi-role (admin/staff/client) validation passed |
| 15J | Apple Beta App Review submitted |

## SaaS Maturity (Releases 16–18)

| Release | Milestone |
|---------|-----------|
| 16A | Repository readiness + SaaS maturity audit |
| 16B | Roadmap reprioritization (Ryan paused, SaaS-first) |
| 17A–17B | Entitlement enforcement design + core helpers |
| 17D–17E | Phase 1 gates wired + deployed |
| 17I | **Phase 1 enforcement enabled in production** |
| 17K–17P | Platform Management Console (design → backend → UI) |
| 17R | Safe tenant metadata edit validated |
| 17S | SaaS maturity structural review |
| 17T–17U | Credential security cleanup |
| 17V–17W | Tenant provisioning script |
| 17X–17Y | Company ID resolution hardening |
| 18A–18C | Cognito custom:company_id schema + backfill |
| 18F–18I | Google Calendar reconnect + sync validation |
| 18K–18N | Phase 2 entitlement gates (client limit, booking counter) |
| 18O–18P | **Calendar cancellation cascade race condition fix** |
| 18Q | Strict-mode gate review preparation |
| 18R | Strict-mode early readiness review |
| 18S–18T | **Strict mode enabled (`TENANT_RESOLUTION_MODE=multi` on all 13 Lambdas)** |
| 18U | Post-enable monitoring checkpoint (PASS — zero fallback/failure events) |
| 18UI-A | Web/mobile UI parity review |
| 19A | Second-tenant provisioning dry-run planning |
| 19B | **Tenant provisioning script dry run (validated for test_tenant_alpha)** |
| 19C | Second-tenant metadata approval checkpoint |
| 19D | **Controlled second-tenant metadata creation (test_tenant_alpha)** |
| 19E | Platform Admin second-tenant visibility validation |
| 19F | Second-tenant owner Cognito user creation planning |
| 19G | **Second-tenant owner Cognito user creation approval checkpoint & runbook** |
| 19H | **Controlled second-tenant owner Cognito user creation** |
| 19I | **Second-tenant owner login isolation defect triage** |
| 19J | **Second-tenant owner login isolation remediation planning** |
| 19K | **Backend tenant isolation remediation (Pre-Deploy)** |
| 19L | **Frontend tenant display remediation (Pre-Deploy)** |
| 19M | **Production deployment and tenant isolation revalidation** |
