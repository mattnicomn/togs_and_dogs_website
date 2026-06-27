# Current Project State

**Last Updated:** 2026-06-27

---

## Production App

| Component | Status |
|-----------|--------|
| Web app (React/Vite) | ✅ Live at `toganddogs.usmissionhero.com` |
| Backend (Python/Lambda) | ✅ Deployed |
| API Gateway | ✅ Active |
| DynamoDB | ✅ Single table, shared-tenant model |
| Google Calendar | ✅ Connected (fixed in 18G, cancellation cascade fixed in 18P) |
| Postmark email | ✅ Active (notifications, payment emails) |

## Mobile / TestFlight

| Item | Status |
|------|--------|
| Framework | Expo / React Native |
| Latest build | 1.0.0 (4) — Internal TestFlight |
| Internal tester (Matthew) | ✅ Active |
| External tester (Ryan) | ❌ Paused (deferred to 19-series) |
| Apple Beta App Review | Submitted (15J), outcome pending/unknown |
| Public App Store | ❌ Not submitted, not approved |

## Stripe / Payments

| Item | Status |
|------|--------|
| Sandbox payment workflow | ✅ Fully validated (12L–14I) |
| Live Stripe mode | ❌ Blocked (usmissionhero LLC EIN pending) |
| Admin payment link UX | ✅ Deployed |
| Payment email sending | ✅ Deployed |
| Payment terms draft | ✅ Written (not published to website) |

## Tenant / Multi-Business Readiness

| Item | Status |
|------|--------|
| Tenant isolation (company_id enforcement) | ✅ Active in all handlers (11E) |
| Entitlement enforcement Phase 1 | ✅ Active (export, calendar, staff limit) |
| Entitlement enforcement Phase 2 | ✅ Deployed (client limit, monthly booking counter) — 18L |
| Platform Admin UI | ✅ Deployed (/platform-admin) |
| Platform audit trail | ✅ Working |
| Cognito custom:company_id | ✅ Backend tenant isolation remediation implemented & verified (19K) |
| TENANT_RESOLUTION_MODE | ✅ Enabled (strict `multi` mode active — 18T validated) |
| Strict-mode observation | ✅ Post-enable monitoring complete (18U — PASS) |
| Second tenant | ✅ Created & Validated in Platform Admin (19E) |
| Tenant provisioning script | ✅ Dry run validated (19B) |

## Current Blockers

| Blocker | Impact | Owner |
|---------|--------|-------|
| EIN unavailable | Live Stripe payments blocked | Matthew (IRS) |
| Ryan testing paused | Cannot validate real staff workflow externally | Decision (19-series) |
| SaaS isolation defects (Frontend) | Profile/company label shows "Tog and Dogs" instead of "Test Tenant Alpha" | Frontend branding fix required (19L/next) |

## Latest Completed Releases

- 19K: Backend Tenant Isolation Remediation Plan (Pre-Deploy Complete)
- 19J: Second-Tenant Owner Login Isolation Remediation Planning
- 19I: Second-tenant owner login isolation defect triage (Triage Complete)
- 19H: Controlled second-tenant owner Cognito user creation (FAIL/BLOCKED)
- 19G: Second-tenant owner Cognito user creation approval runbook
- 19E: Platform Admin second-tenant visibility validation
- 19D: Controlled second-tenant metadata creation
- 19B: Tenant provisioning script dry run
- 18U: Post-enable strict-mode monitoring checkpoint (PASS)

## Next Recommended Action

**Remediation of SaaS Isolation Defects (Frontend Branding - 19L)** — Update the frontend React UI (e.g. `AdminDashboard.jsx`, `UserProfile.jsx`, etc.) to dynamically retrieve the tenant display name from the backend `/admin/tenant-info` endpoint rather than hardcoding "Tog and Dogs".
