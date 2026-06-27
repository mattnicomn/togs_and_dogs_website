# Current Project State

**Last Updated:** 2026-06-26

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
| Cognito custom:company_id | ✅ Schema added (18B), all users backfilled (18C) |
| TENANT_RESOLUTION_MODE | ✅ Enabled (strict `multi` mode active — 18T validated) |
| Strict-mode observation | ✅ Post-enable monitoring complete (18U — PASS) |
| Second tenant | ❌ Not created |
| Tenant provisioning script | ✅ Dry run validated (19B) |

## Current Blockers

| Blocker | Impact | Owner |
|---------|--------|-------|
| EIN unavailable | Live Stripe payments blocked | Matthew (IRS) |
| Ryan testing paused | Cannot validate real staff workflow externally | Decision (19-series) |
| Second-tenant creation not approved | No multi-business testing yet | Matthew approval required |

## Latest Completed Releases

- 18U: Post-enable strict-mode monitoring checkpoint (PASS)
- 18T: Strict-mode enablement (`TENANT_RESOLUTION_MODE=multi` on all 13 Lambdas)
- 18Q: Strict mode final gate review preparation plan
- 18UI-A: Web/mobile UI parity review plan
- 18P: Calendar cancellation cascade defensive fix
- 18N: Phase 2 entitlement controlled validation

## Next Recommended Action

**Second-tenant provisioning dry-run planning** — strict mode is validated, provisioning script exists (17W). Next step is planning the controlled creation of a test second tenant through the Platform Admin workflow or provisioning script. Requires Matthew's explicit approval before execution.
