# Release 16A: Repository Readiness and SaaS Maturity Audit

**Status:** Complete (audit/documentation only)
**Date:** 2026-06-19
**Priority:** Strategic
**Scope:** Comprehensive readiness assessment before Ryan invitation and multi-business-owner maturity

---

## 1. Completed Platform Capabilities

### Core Operations (Production-Deployed)

| Capability | Releases | Status |
|------------|----------|--------|
| Client intake form (public) | 1–4 | ✅ Production |
| Admin request review/approve/decline | 4–7 | ✅ Production |
| Multi-day scheduling (selected dates, date ranges) | 7E | ✅ Production |
| Staff assignment + cascade to child jobs | 7G | ✅ Production |
| Google Calendar sync (per-visit events) | 6G, 7D | ✅ Production |
| Postmark email notifications (6 event types) | 6A–6C | ✅ Production |
| Notification dedup for multi-day bookings | 7F | ✅ Production |
| Pet/client profile management | 5A–5F | ✅ Production |
| Staff onboarding + login controls | 8S | ✅ Production |
| Per-visit completion + visit notes | 8V, 8Y | ✅ Production |
| Admin export (tenant-filtered) | 11E | ✅ Production |
| Cancellation workflow (client + admin) | 7E | ✅ Production |
| Terms/Privacy policy pages | 7N | ✅ Production |

### Tenant Isolation (Production-Deployed)

| Capability | Releases | Status |
|------------|----------|--------|
| `company_id` on all records | Existing | ✅ |
| `get_current_company_id(event)` | Existing | ✅ |
| `validate_tenant_ownership(item, event)` called in all handlers | 11E | ✅ Production |
| Export endpoint tenant-filtered | 11E | ✅ Production |
| Notification quota per-tenant | 11E | ✅ Production |
| Tenant metadata record (`TENANT#tog_and_dogs / METADATA`) | 11C | ✅ Production |

### Payment (Sandbox-Validated, Not Live)

| Capability | Releases | Status |
|------------|----------|--------|
| Stripe webhook handler + signature verification | 12D | ✅ Deployed |
| Billing event ledger + idempotency | 12D | ✅ Deployed |
| Entitlement interface (`get_tenant_entitlement`) | 12D | ✅ Deployed |
| Checkout Session creation (card-only) | 12G, 12M | ✅ Deployed |
| Duplicate payment state guard | 12O/12P | ✅ Deployed |
| Admin payment link UX (CareCard) | 12R | ✅ Deployed |
| Send Payment Email backend + frontend | 12T, 12V | ✅ Deployed |
| Payment success/cancel pages | 12Z | ✅ Deployed |
| Admin search + payment filter/chips | 14B | ✅ Deployed |
| CareCard helper text + disabled-state polish | 14C | ✅ Deployed |
| Support contact finalized | 14H | ✅ Deployed |
| Conditional sandbox warning (env-based) | 13B | ✅ Deployed |
| End-to-end sandbox payment validated | 12Y/12Z | ✅ Verified |
| Payment email received + content validated | 12X | ✅ Verified |

### Mobile (TestFlight-Validated)

| Capability | Releases | Status |
|------------|----------|--------|
| Cognito auth + SecureStore | 8H | ✅ TestFlight |
| Role-based navigation (admin/staff/client) | 8H | ✅ TestFlight |
| Staff daily schedule + assigned visits | 8L | ✅ TestFlight |
| Staff mark completed + visit notes | 8T, 8V | ✅ TestFlight |
| Admin request list + approval | 8I, 8J | ✅ TestFlight |
| Client/pet detail (stack navigation) | 8N/8O | ✅ TestFlight |
| Tablet layout polish | 8P | ✅ TestFlight |
| Payment status read-only badge | 15C | ✅ TestFlight |
| Multi-role validation (admin/staff/client) | 15H | ✅ Passed |
| Build: 1.0.0 (4) Internal TestFlight | 15D | ✅ |
| Apple Beta App Review submitted | 15J | ⏳ Awaiting review |

---

## 2. Open Blockers

| Blocker | Impact | Owner | Resolution Path |
|---------|--------|-------|-----------------|
| **EIN unavailable** | Live Stripe payments blocked | Matthew | Obtain EIN → complete Stripe verification |
| **Ryan External TestFlight** | Cannot validate staff workflow with real user | Apple | Beta Review approval (~24-48h) |
| **Payment terms not published** | Legal risk before live charges | Matthew | Review draft → attorney/accountant → publish |
| **Entitlement enforcement not wired** | Any user can access all features regardless of tier | Code | Wire `check_entitlement()` into handlers (future release) |
| **No second tenant provisioning** | Cannot onboard another business | Code | Build provisioning flow (future) |
| **No pricing page / signup flow** | New business owners cannot self-onboard | Code | Build landing + Stripe Checkout for subscriptions |

---

## 3. Multi-Business-Owner SaaS Readiness

### What's Ready

| Dimension | Status | Notes |
|-----------|--------|-------|
| Shared DynamoDB table with `company_id` | ✅ | Foundation exists |
| `validate_tenant_ownership()` enforced | ✅ | All handlers check (11E) |
| Tenant metadata record model | ✅ | `TENANT#{company_id} / METADATA` exists |
| Entitlement data model defined | ✅ | TenantEntitlement class, tier limits, feature flags (12D) |
| Billing webhook handler | ✅ | Processes subscription lifecycle events |
| Single Cognito pool + `custom:company_id` | ✅ | Designed, partially implemented |
| Mobile uses same tenant model | ✅ | `get_current_company_id()` works on mobile API calls |

### What's NOT Ready

| Gap | Severity | Required Work |
|-----|----------|---------------|
| **Entitlement enforcement not active** | High | Wire `check_entitlement()` before each gated action |
| **No tenant provisioning workflow** | High | Cannot create a second tenant programmatically |
| **No pricing/signup page** | High | New business owners have no way to subscribe |
| **No per-tenant branding** | Medium | All tenants see "Tog & Dogs" branding |
| **No Cognito custom:company_id attribute** | Medium | Currently uses env var default |
| **No usage metering** | Medium | Cannot track bookings/month, clients, staff per tenant |
| **No upgrade/downgrade flow** | Medium | No Stripe Customer Portal integration |
| **No tenant admin dashboard** | Medium | Business owners cannot manage their own billing |
| **No self-service staff/client invite** | Low | Admin must manually create accounts |

---

## 4. Tier/Feature Entitlement Findings

### Defined but Not Enforced

The following tier controls are **architecturally defined** (in 12A/12D code) but **not actively enforced** in production handlers:

| Control | Defined In | Enforcement Status |
|---------|-----------|-------------------|
| `max_active_clients` | TIER_LIMITS dict | ❌ Not checked on client creation |
| `max_staff` | TIER_LIMITS dict | ❌ Not checked on staff creation |
| `max_monthly_notifications` | TIER_LIMITS dict | ⚠️ Quota exists but uses hardcoded key pattern |
| `max_monthly_bookings` | TIER_LIMITS dict | ❌ Not checked on booking creation |
| `google_calendar_enabled` | TIER_LIMITS dict | ❌ Calendar syncs regardless |
| `export_enabled` | TIER_LIMITS dict | ❌ Export works for all |
| `custom_branding_enabled` | TIER_LIMITS dict | N/A (branding not built) |
| `video_evidence_enabled` | TIER_LIMITS dict | N/A (video not built) |
| `subscription_status` blocking login | TenantEntitlement class | ❌ Login not gated by subscription |

### What Must Be Built for Real Entitlement

1. **Middleware/decorator**: `@require_entitlement(feature='booking_create')` on handlers
2. **Usage counters**: monthly booking count, active client count, staff count per tenant
3. **Limit check on write**: before creating a booking/client/staff, check against tier limit
4. **Login gate**: check `subscription_status` during session bootstrap
5. **Feature flag UI**: show/hide features based on tier (web + mobile)

---

## 5. Web vs Phone/Tablet Strategy

### Recommended Split

| Action | Web | Phone | Tablet |
|--------|-----|-------|--------|
| **Full admin dashboard** | ✅ Primary | ❌ Too complex | ⚠️ Possible with layout |
| **Generate payment link** | ✅ Only | ❌ | ❌ |
| **Send payment email** | ✅ Only | ❌ | ❌ |
| **Billing/subscription management** | ✅ Only | ❌ | ❌ |
| **Staff/client management** | ✅ Primary | ❌ | ⚠️ Read-only possible |
| **Export data** | ✅ Only | ❌ | ❌ |
| **Branding/settings** | ✅ Only | ❌ | ❌ |
| **View daily schedule** | ✅ | ✅ Primary | ✅ |
| **View visit details** | ✅ | ✅ Primary | ✅ |
| **Mark visit complete** | ✅ | ✅ Primary | ✅ |
| **Add visit notes** | ✅ | ✅ Primary | ✅ |
| **View payment status (read-only)** | ✅ | ✅ | ✅ |
| **Approve/decline requests** | ✅ Primary | ✅ Quick action | ✅ |
| **Assign staff** | ✅ Primary | ⚠️ Simple picker | ✅ |
| **Client booking/request** | ✅ | ✅ (simplified) | ✅ |

### Progressive Disclosure Model

- **Phone (staff default)**: Schedule → today's visits → tap for detail → complete + notes
- **Phone (admin)**: Quick approve/decline queue + schedule view
- **Tablet (admin)**: Split-pane: list on left, detail on right (already partially built in 8P)
- **Web (admin)**: Full dashboard, all settings, billing, exports, payment generation

### Owner/Admin Mobile Safety

| Capability | Safe for Phone? | Reason |
|------------|-----------------|--------|
| View requests/schedule | ✅ | Read-only context |
| Approve/decline | ✅ | Simple binary action with confirmation |
| Assign staff | ⚠️ | Needs careful picker UI to avoid mistakes |
| Generate payment link | ❌ | Too easy to fat-finger amounts; web-only |
| Send payment email | ❌ | Accidental sends; web-only |
| Manage staff accounts | ❌ | Complex CRUD; web-only |
| Billing/subscription | ❌ | Financial actions; web-only |

---

## 6. Business-Owner Maintainability

### What a Non-Technical Business Owner Needs to Manage Alone

| Task | Currently Possible? | Simplification Needed? |
|------|---------------------|------------------------|
| View daily bookings/schedule | ✅ (web + mobile) | No |
| Approve/decline requests | ✅ (web + mobile) | No |
| Assign staff to visits | ✅ (web + mobile) | Minor (picker UX) |
| Generate payment link | ✅ (web only) | No |
| Send payment email | ✅ (web only) | No |
| Add new client (manual) | ✅ (web) | Could be simpler wizard |
| Add new staff | ✅ (web) | OK |
| View/edit pet care cards | ✅ (web + mobile) | No |
| Google Calendar reconnect | ⚠️ (web, requires OAuth flow) | Needs clear docs/guide |
| Manage subscription/billing | ❌ (not built) | Needs Stripe Customer Portal link |
| Customize branding | ❌ (not built) | Future |
| View analytics/reports | ❌ (not built) | Future |

### What Requires usmissionhero Support Today

| Task | Reason | Fix Priority |
|------|--------|--------------|
| Create a new tenant | No self-service provisioning | High (before 2nd tenant) |
| Create Cognito user accounts | Manual Cognito admin action | High |
| Reset passwords beyond self-service | Cognito admin API | Low (self-service exists) |
| Data corrections in DynamoDB | No admin data editor | Low |
| Stripe configuration changes | Terraform/Dashboard access required | Medium |
| Google Calendar reauthorization (complex cases) | OAuth flow understanding | Low (docs exist) |

### Docs/Training/Checklists Needed Before Real Business Owner Onboarding

1. ✅ Payment operations quick reference (14D — exists)
2. ✅ Emergency response checklist (exists)
3. ✅ Admin quick reference (exists)
4. ⚠️ "Getting Started as a Business Owner" guide — NOT built
5. ⚠️ "How to add your first staff member" — NOT built
6. ⚠️ "How to manage your subscription" — NOT built (Stripe Portal not integrated)
7. ⚠️ "How to set up Google Calendar" — partially exists (reauth guide)
8. ❌ Self-service troubleshooting FAQ — NOT built

---

## 7. Recommended Pre-Ryan Roadmap

### Before Ryan External TestFlight Invitation

| Priority | Release | Scope | Blocker? |
|----------|---------|-------|----------|
| 1 | Apple Beta Review approval | Wait for Apple (~24-48h) | ⏳ Submitted (15J) |
| 2 | Data review | Ensure Ryan's test data is appropriate | Matthew review |
| 3 | Ryan credentials | Provide staff login securely | Matthew action |

### Before First Real Client Payment (EIN-Dependent)

| Priority | Release | Scope |
|----------|---------|-------|
| 1 | Obtain EIN | Matthew/IRS |
| 2 | Complete Stripe verification | Matthew in Dashboard |
| 3 | Live secret wiring (Terraform) | 13E |
| 4 | Live webhook validation | 13F |
| 5 | Internal $1 live test + refund | 13G |
| 6 | Payment terms published | Matthew/attorney |
| 7 | First real client payment | 13H |

### Before Second Business Owner Onboarding

| Priority | Release | Scope |
|----------|---------|-------|
| 1 | Entitlement enforcement wired into handlers | High effort |
| 2 | Usage metering (bookings/month, clients, staff) | Medium effort |
| 3 | Tenant provisioning automation (or admin tool) | High effort |
| 4 | Cognito `custom:company_id` attribute enforcement | Medium effort |
| 5 | Pricing/signup page + Stripe subscription Checkout | High effort |
| 6 | Business owner dashboard (billing, settings) | Medium effort |
| 7 | Per-tenant branding | Medium effort |
| 8 | Self-service staff/client invite | Low effort |
| 9 | "Getting Started" documentation for new owners | Low effort |

---

## 8. Recommended Release Sequence (Post-16A)

| Release | Scope | Dependency |
|---------|-------|------------|
| **16B** | Ryan External TestFlight invite (after Apple approval) | Apple Beta Review |
| **16C** | Ryan staff workflow smoke validation | Ryan availability |
| **17A** | Entitlement enforcement planning | None |
| **17B** | Entitlement enforcement implementation (wire checks into handlers) | 17A |
| **17C** | Usage metering (booking/client/staff count per tenant) | 17B |
| **17D** | Subscription lifecycle management (Stripe Customer Portal) | EIN resolved |
| **17E** | Tenant provisioning tool/workflow | 17B + 17D |
| **17F** | Pricing/signup page | 17E |
| **17G** | Per-tenant branding (logo/colors/name) | 17E |
| **17H** | Business owner "Getting Started" guide | 17E |
| **18A** | Second tenant pilot onboarding | All of 17 series |

---

## 9. What This Document Does NOT Authorize

- ❌ Code changes
- ❌ Deployments
- ❌ AWS/Terraform changes
- ❌ Stripe/payment actions
- ❌ DynamoDB writes
- ❌ Cognito changes
- ❌ Mobile builds or submissions
- ❌ Adding Ryan
- ❌ Creating a second tenant

This is an audit/planning document only.
