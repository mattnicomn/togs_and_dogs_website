# Release 17S: SaaS Maturity and Multi-Business Owner Readiness Structural Review

**Status:** Review Complete
**Date:** 2026-06-21
**Priority:** Strategic (gates second-tenant creation)
**Scope:** Evaluate platform readiness for multi-business-owner operations

---

## 1. SaaS Maturity Assessment

### Production-Ready (✅)

| Capability | Evidence |
|------------|----------|
| Tenant isolation at API layer | `validate_tenant_ownership()` in all handlers (11E) |
| Tenant metadata record model | `TENANT#tog_and_dogs / METADATA` exists (11C) |
| Platform admin backend APIs | GET/PATCH tenants + audit log deployed (17L) |
| Platform admin UI | Tenant list, detail, entitlement, edit, audit (17P) |
| Platform admin access control | `platform_admin` Cognito group + route guard (17L/17P) |
| Platform audit trail | PLATFORM_AUDIT records for all admin changes (17L/17R) |
| Phase 1 entitlement enforcement | Export, calendar, staff limit gates active (17D/17I) |
| Subscription tier/status on metadata | Professional/active on tog_and_dogs |
| Usage counts visible | Staff/client counts displayed in platform UI (17P) |
| Safe metadata editing via UI | Notes updated, confirmed with audit (17R) |
| Payment sandbox workflow | End-to-end validated (12L–14I) |
| Mobile multi-role support | Admin/staff/client validated on TestFlight (15H) |
| Operations documentation | Payment ops guide, admin reference, emergency checklist |

### Not Ready (❌)

| Capability | Gap | Severity |
|------------|-----|----------|
| Tenant provisioning/creation tool | No way to create a second tenant through UI or safe script | High |
| Cognito user creation for new tenant | Manual AWS Console only | High |
| Google Calendar per-tenant isolation | One shared OAuth connection, not per-tenant | Medium |
| Postmark notification sender isolation | Single sender domain; no per-tenant separation | Low |
| Phase 2 entitlement gates | Client limit, booking limit, subscription-status login gate not wired | Medium |
| Live Stripe payments | Blocked on EIN | High (for billing) |
| Self-service business owner onboarding | No public signup flow | High (for scale) |
| Per-tenant branding | Not implemented | Low |
| Usage metering (monthly counters) | Staff/client are count-on-read; bookings not metered monthly | Medium |
| Business owner "Getting Started" guide | Not written | Medium |
| Password/credential hygiene | Shared default dev password exposed in chat; needs rotation | High (security) |

---

## 2. Second-Tenant Dry Run Readiness Gates

### Go/No-Go Checklist

| # | Gate | Status | Blocking? |
|---|------|--------|-----------|
| G1 | Tenant metadata can be created safely (provisioning) | ❌ No tool/script exists | **Yes** |
| G2 | Cognito user can be created for new owner with correct company_id | ❌ Manual only, no automation | **Yes** |
| G3 | New tenant entitlement defaults are set correctly | ✅ TIER_LIMITS derive from tier | No |
| G4 | Phase 1 enforcement protects new tenant from exceeding limits | ✅ Active | No |
| G5 | Platform Admin can view/manage new tenant | ✅ UI supports multi-tenant list | No |
| G6 | Google Calendar is isolated (new tenant gets own connection) | ⚠️ Not verified for multi-tenant | Soft |
| G7 | Notifications are safe (won't send to wrong tenant's clients) | ✅ company_id filter on notify_event | No |
| G8 | Existing tog_and_dogs tenant is NOT affected by new tenant creation | ✅ Shared-table with company_id isolation | No |
| G9 | Rollback: new tenant can be disabled without affecting existing | ✅ Set status=disabled via Platform Admin | No |
| G10 | Audit trail records tenant creation | ✅ PLATFORM_AUDIT works | No |
| G11 | Password/credential security cleanup complete | ❌ Shared dev password needs rotation | **Yes** |
| G12 | Matthew explicitly approves second-tenant creation | ❌ Not yet given | **Yes** |

### Hard Blockers: G1, G2, G11, G12

Second-tenant dry run cannot proceed until:
1. A safe tenant creation method exists (script, API endpoint, or documented manual steps)
2. Cognito user creation for new owner is documented/automated
3. Shared development passwords are rotated
4. Matthew explicitly approves

---

## 3. Credential Security Cleanup Recommendation

### Issue

A shared/default development password was exposed in chat during earlier development. Any Cognito user accounts still using that password should be rotated before:
- Ryan or external testers are invited
- A second tenant/business owner is created
- Any real client-facing operations begin

### Recommended Actions

| # | Action | Priority | Owner |
|---|--------|----------|-------|
| 1 | Identify all Cognito users still using the default password | High | Matthew |
| 2 | Force password reset for any affected accounts | High | Matthew |
| 3 | Confirm staff test account password has been changed | High | Matthew |
| 4 | Document that no default/shared passwords remain active | High | Matthew |
| 5 | Do NOT include the password value in any docs or chat going forward | Ongoing | All |

**This is a manual Matthew action — not a code/Terraform change.** AG should not handle credentials.

---

## 4. Risk Matrix

| # | Risk | Likelihood | Impact | Mitigation | Owner | Release |
|---|------|-----------|--------|------------|-------|---------|
| 1 | Second tenant affects existing tenant data | Low | Critical | Shared-table isolation + company_id enforcement | AG | Already mitigated (11E) |
| 2 | New tenant user logs in and sees tog_and_dogs data | Low | Critical | company_id in JWT + handler checks | AG | Already mitigated |
| 3 | Shared dev password used by external tester | Medium | High | Password rotation before external access | Matthew | 17T |
| 4 | Google Calendar events leak to wrong tenant | Medium | Medium | Gate calendar per tenant; don't auto-connect new tenants | AG | 17U+ |
| 5 | Notification sent to wrong tenant's client | Low | High | company_id filter on all notify_event paths | AG | Already mitigated |
| 6 | New tenant exceeds limits (no Phase 2 gates) | Medium | Low | Phase 1 gates cover staff/export/calendar; add Phase 2 later | AG | 17V |
| 7 | EIN never obtained; live payments impossible | Medium | High | Continue sandbox; re-attempt EIN periodically | Matthew | External |
| 8 | Platform Admin UI has auth bypass | Low | Critical | Backend 403 enforcement + frontend guard | AG | Already mitigated (17L/17P) |
| 9 | Tenant creation leaves orphan/partial state | Medium | Medium | Atomic creation script with rollback | AG | 17U |
| 10 | Ryan invited before platform is mature | Low | Medium | Deferred to 19-series; gates documented | Kiro | 19A |

---

## 5. Decision: Next Release Direction

### Should Second-Tenant Dry Run Proceed Now?

**Not yet.** Three hard blockers remain:

1. **No tenant creation tooling (G1/G2)** — need a safe, documented method
2. **Credential cleanup (G11)** — security prerequisite
3. **Matthew approval (G12)** — explicit go-ahead required

### Recommended Next Steps (In Order)

| Priority | Release | Scope |
|----------|---------|-------|
| 1 | **17T** | Credential security cleanup plan (password rotation checklist for Matthew) |
| 2 | **17U** | Tenant creation/provisioning design (how to safely seed a second tenant) |
| 3 | **17V** | Tenant provisioning implementation (script or API endpoint) |
| 4 | **17W** | Second-tenant dry run execution (create test tenant, validate isolation) |
| 5 | **17X** | Phase 2 entitlement gates (client limit, booking limit) |
| 6 | **18A** | Business owner onboarding flow design |

---

## 6. Recommended Release Sequence After 17S

| Release | Scope | Type | Depends On |
|---------|-------|------|------------|
| **17T** | Credential security cleanup plan + Matthew execution checklist | Planning + manual action | — |
| **17U** | Tenant provisioning design (creation method, Cognito user, defaults) | Planning | 17T |
| **17V** | Tenant provisioning implementation | Code (AG) | 17U |
| **17W** | Second-tenant dry run (create test_tenant_alpha, validate isolation) | Execution (AG + Matthew) | 17V + G11 + G12 |
| **17X** | Phase 2 entitlement gates (client limit, booking limit) | Code (AG) | 17W validated |
| **18A** | Business owner onboarding flow design | Planning (Kiro) | 17W |
| **18B** | Self-service signup/provisioning | Code (AG) | 18A |
| **19A** | Ryan external TestFlight re-evaluation | Planning (Kiro) | 17W + 18A |

---

## 7. What This Document Does NOT Authorize

- ❌ Creating a second tenant
- ❌ Modifying tenant metadata
- ❌ Changing Cognito users/groups/passwords
- ❌ Code changes
- ❌ Terraform/AWS changes
- ❌ Frontend/mobile deployment
- ❌ Stripe/Postmark/payment changes
- ❌ DynamoDB writes
- ❌ Ryan/tester changes
- ❌ Apple Beta Review submission

This is a structural review document. Each subsequent release requires separate approval.
