# Major Decisions Log

---

## Business / Legal

| Decision | Context | Date |
|----------|---------|------|
| Direct Stripe payments under usmissionhero LLC | Not Stripe Connect/marketplace. Togs & Dogs is a product of usmissionhero LLC. | 2026-06 |
| Stripe sandbox-only until EIN + Matthew approval | Live payments blocked pending LLC EIN. | 2026-06 |
| Ryan testing paused until SaaS maturity gates pass | Platform not ready for external business-owner use. | 2026-06 (16B) |
| Public App Store publishing deferred | Not approved until full validation + Matthew explicit go-ahead. | 2026-06 |
| No second tenant until provisioning + strict mode ready | Hard blockers documented in 17S. | 2026-06 |

## Architecture / Technical

| Decision | Context | Date |
|----------|---------|------|
| Shared DynamoDB table with company_id filtering | Not table-per-tenant. Cost-effective, simpler. | 2026-06 (11A) |
| Single Cognito user pool with custom:company_id | Not pool-per-tenant. Custom attribute for tenant routing. | 2026-06 (11A) |
| No website rewrite | Web is already React (Vite). Parity through style alignment only. | 2026-06 (18UI-A) |
| Backend entitlement over App Store IAP | Business owners pay via web; staff/clients use free app. | 2026-06 (12A) |
| Platform Admin separate from tenant admin | /platform-admin is usmissionhero-only; /admin is per-tenant. | 2026-06 (17K) |
| TENANT_RESOLUTION_MODE toggle (single/multi) | Allows safe phased rollout of strict tenant routing. | 2026-06 (17X) |
| Defensive calendar cancellation (collect all event IDs) | Fixes race condition where child job misses parent's event ID. | 2026-06 (18O/18P) |
| Payment does not gate scheduling | Admin can schedule before payment received. Web-first billing. | 2026-06 (12F) |
| Card-only Stripe Checkout | No Klarna/BNPL/bank for booking payments. | 2026-06 (12M) |

## Process / Workflow

| Decision | Context | Date |
|----------|---------|------|
| Kiro = planning/docs; AG = implementation; ChatGPT = strategy | Clear role separation. | 2026-06 |
| Plan-then-apply with Matthew approval gate | No terraform apply without reviewed plan. | Ongoing |
| Docs-only releases can be pushed without deployment approval | Documentation doesn't affect production. | Ongoing |
| Feature flags for entitlement enforcement | ENTITLEMENT_ENFORCEMENT_ENABLED allows safe rollout. | 2026-06 (17A) |
| Credential rotation before external access | Shared dev passwords must be rotated before Ryan/second-tenant. | 2026-06 (17T) |
