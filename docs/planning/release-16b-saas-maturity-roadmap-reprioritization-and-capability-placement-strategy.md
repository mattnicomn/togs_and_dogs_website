# Release 16B: SaaS Maturity Roadmap Reprioritization and Capability Placement Strategy

**Status:** Planning / Strategic Decision
**Date:** 2026-06-19
**Priority:** Strategic (defines next 3–6 months of work order)
**Scope:** Reorder roadmap to prioritize SaaS maturity over Ryan invitation

---

## 1. Ryan Pause Decision

### Decision: Ryan Remains Paused

**Ryan should NOT be invited to External TestFlight until the platform is mature enough for a real pet business owner to operate independently.**

| Reason | Detail |
|--------|--------|
| Entitlement enforcement not active | Any user can access all features regardless of tier |
| No tenant provisioning | Cannot safely create Ryan's business as a distinct tenant with controls |
| Business-owner self-service missing | Ryan cannot manage billing, settings, or staff without Matthew |
| Payment not live | Live Stripe blocked on EIN; sandbox payments are developer-only |
| No onboarding documentation | Ryan would have no guide for getting started |
| Mobile is validated but not production-hardened | Internal smoke passed; not stress-tested with real daily use |

### Apple Beta App Review Status

If Apple approves the Beta App Review:
- This means external testing is **technically available** (Apple allows distribution)
- It does NOT mean Ryan should be invited
- The approval has no expiration pressure — the build remains available for external testing indefinitely
- Ryan can be invited at any point after approval without resubmitting

---

## 2. Pre-Ryan Readiness Gates

Ryan invitation requires ALL of the following gates to be marked Ready:

| Gate | Item | Status | Blocking? |
|------|------|--------|-----------|
| G1 | Entitlement enforcement active in production handlers | ❌ Not started | Yes |
| G2 | Tier feature gating working (limits check on booking/client/staff creation) | ❌ Not started | Yes |
| G3 | Tenant provisioning documented and testable | ❌ Not started | Yes |
| G4 | Owner/staff/client roles clear and enforced across web + mobile | ✅ Roles work | No |
| G5 | Sanitized test data or demo environment available for Ryan | ❌ Not prepared | Yes |
| G6 | Business-owner onboarding docs/checklist exists | ❌ Not written | Yes |
| G7 | Mobile owner/staff workflows pass end-to-end validation | ✅ 15H passed | No |
| G8 | Payment terms/refund policy published (or deferred with documented reason) | ⚠️ Draft only | Soft blocker |
| G9 | Live Stripe/EIN resolved (or Ryan uses sandbox-only with clear expectation) | ❌ Blocked | Soft blocker |
| G10 | Matthew explicitly approves Ryan invitation | ❌ Not given | Yes |

**Minimum required for invitation:** G1 + G2 + G3 + G5 + G6 + G10

G8 and G9 are soft blockers — Ryan could test with sandbox/no-payment if clearly communicated, but G1–G6 are hard blockers.

---

## 3. Web vs Phone/Tablet Capability Placement

### Design Principle

> **Web for configuration and finance. Mobile for field operations. Tablet bridges both.**

### Placement Matrix

| Capability | Web Desktop | Tablet | Phone | Rationale |
|------------|-------------|--------|-------|-----------|
| Full admin dashboard | ✅ Primary | ✅ Split-pane | ❌ | Complex data density needs screen space |
| Payment link generation | ✅ Only | ❌ | ❌ | Financial action — too easy to fat-finger on small screen |
| Send payment email | ✅ Only | ❌ | ❌ | Communication action with financial impact |
| Billing/subscription management | ✅ Only | ❌ | ❌ | Financial; Stripe Portal is web-optimized |
| Staff/client CRUD | ✅ Primary | ⚠️ Read + simple edits | ❌ | Complex forms don't work well on phone |
| Export data | ✅ Only | ❌ | ❌ | File download; web-native |
| Branding/settings | ✅ Only | ❌ | ❌ | Configuration rarely changes; web is fine |
| Approve/decline requests | ✅ | ✅ | ✅ Quick action | Binary decision — safe on any device |
| View daily schedule | ✅ | ✅ | ✅ Primary | Core field operation |
| View visit details | ✅ | ✅ | ✅ Primary | Core field operation |
| Mark visit complete | ✅ | ✅ | ✅ Primary | Core field operation |
| Add visit notes | ✅ | ✅ | ✅ Primary | Core field operation |
| View payment status | ✅ | ✅ | ✅ Read-only | Informational only |
| Assign staff | ✅ Primary | ✅ Simple picker | ⚠️ Simple only | Risk of wrong assignment on small screen |
| Client booking request | ✅ | ✅ | ✅ Simplified | Public intake form adapts to screen |
| Google Calendar reconnect | ✅ Only | ❌ | ❌ | OAuth flow requires browser context |

### Why Avoid Mobile Complexity

| Risk | Impact | Prevention |
|------|--------|------------|
| Fat-finger wrong amount on payment | Client overcharged | Keep payment generation web-only |
| Accidental email send while walking dog | Unprofessional communication | Keep email sends web-only |
| Assign wrong staff on small screen | Visit goes to wrong person | Only allow simple picker with confirmation |
| Delete/archive while multitasking | Data loss | Destructive actions web-only |
| Complex forms on 4.7" screen | Data entry errors | Keep CRUD forms web-primary |

---

## 4. Mobile Progressive Disclosure Model

### Phone Default View (Staff)

```
┌─────────────────────────────┐
│ 🐾 Tog & Dogs              │
│ Today's Visits (3)          │
├─────────────────────────────┤
│ 9:00 AM  Luna - Dog Walk    │
│ 11:00 AM Max - Drop-in     │
│ 2:00 PM  Bella - Walk      │
├─────────────────────────────┤
│ [Schedule] [Visits] [More]  │
└─────────────────────────────┘
```

### Phone Default View (Owner/Admin)

```
┌─────────────────────────────┐
│ 🐾 Tog & Dogs              │
│ Pending (2) │ Today (5)     │
├─────────────────────────────┤
│ ⚡ 2 requests need review   │
│ [Quick Approve/Decline]     │
├─────────────────────────────┤
│ Today's Schedule            │
│ 9:00  Luna  │ Staff: Ryan  │
│ 11:00 Max   │ Staff: Ryan  │
├─────────────────────────────┤
│ [Requests] [Schedule] [More]│
└─────────────────────────────┘
```

### "More" Menu (Progressive Disclosure)

```
┌─────────────────────────────┐
│ More                        │
├─────────────────────────────┤
│ 👥 Staff List               │
│ 🐕 Clients & Pets          │
│ 💳 Payment Status (view)   │
│ 📊 Quick Stats             │
│ ⚙️ → Open Web Dashboard    │
│ 📞 Support                 │
└─────────────────────────────┘
```

### Tier-Based Visibility

| Feature | Starter | Professional | Premium |
|---------|---------|--------------|---------|
| Schedule view | ✅ | ✅ | ✅ |
| Multi-day badges | ❌ | ✅ | ✅ |
| Payment status badges | ✅ (basic) | ✅ | ✅ |
| Google Calendar indicator | ❌ | ✅ | ✅ |
| Staff list view | ❌ (solo) | ✅ | ✅ |
| Quick stats | ❌ | ❌ | ✅ |
| Export link | ❌ | ✅ (→ web) | ✅ (→ web) |

Features above a tenant's tier are hidden (not grayed out). Clean, uncluttered experience per tier.

---

## 5. Tier/Capability Model

### Feature-to-Tier Mapping

| Feature | Starter ($29) | Professional ($79) | Premium ($149) | Enterprise |
|---------|:---:|:---:|:---:|:---:|
| **Limits** | | | | |
| Staff accounts | 1 | 5 | 15 | Unlimited |
| Active clients | 20 | 100 | 500 | Unlimited |
| Bookings/month | 50 | 250 | 1,000 | Unlimited |
| Monthly notifications | 100 | 500 | 2,000 | Unlimited |
| **Core Operations** | | | | |
| Intake form + approval | ✅ | ✅ | ✅ | ✅ |
| Staff assignment | ✅ | ✅ | ✅ | ✅ |
| Visit completion + notes | ✅ | ✅ | ✅ | ✅ |
| Multi-day scheduling | ✅ | ✅ | ✅ | ✅ |
| Cancellation workflow | ✅ | ✅ | ✅ | ✅ |
| **Mobile** | | | | |
| Staff mobile app | ✅ | ✅ | ✅ | ✅ |
| Owner/admin mobile | ✅ (basic) | ✅ | ✅ | ✅ |
| Client mobile app | ❌ | ✅ | ✅ | ✅ |
| Tablet optimized layout | ❌ | ✅ | ✅ | ✅ |
| **Integrations** | | | | |
| Google Calendar sync | ❌ | ✅ | ✅ | ✅ |
| Email notifications | ✅ | ✅ | ✅ | ✅ |
| Push notifications | ❌ | ✅ | ✅ | ✅ |
| **Payments** | | | | |
| Payment link generation | ✅ | ✅ | ✅ | ✅ |
| Payment email sending | ✅ | ✅ | ✅ | ✅ |
| Payment status tracking | ✅ | ✅ | ✅ | ✅ |
| **Data & Reporting** | | | | |
| Export data | ❌ | ✅ | ✅ | ✅ |
| Analytics dashboard | ❌ | ❌ | ✅ | ✅ |
| **Branding** | | | | |
| Custom branding | ❌ | ❌ | ✅ | ✅ |
| White-label | ❌ | ❌ | ❌ | ✅ |
| **Advanced** | | | | |
| Video visit evidence | ❌ | ❌ | ✅ | ✅ |
| Multi-location | ❌ | ❌ | ❌ | ✅ |
| API access | ❌ | ❌ | ❌ | ✅ |
| Dedicated support | ❌ | ❌ | ✅ | ✅ |

### Technical Controls Required Per Tier

| Control | Mechanism |
|---------|-----------|
| Staff limit | Check count before `POST /admin/staff/onboard` |
| Client limit | Check count before client profile creation |
| Booking limit | Monthly counter, check before `POST /requests` |
| Notification limit | Existing quota mechanism (parameterize per tenant) |
| Feature flags | `get_tenant_entitlement().limits` / `feature_flags` dict |
| Mobile access | Backend checks tier; app shows/hides based on entitlement response |

---

## 6. Revised Roadmap (SaaS Maturity First)

### Phase 17: Entitlement and Tenant Foundation

| Release | Scope | EIN Needed? | Effort |
|---------|-------|-------------|--------|
| **17A** | Entitlement enforcement design (which handlers, which checks) | ❌ | Planning |
| **17B** | Wire `check_entitlement()` into all gated handlers | ❌ | Medium |
| **17C** | Usage metering: monthly booking/client/staff counts per tenant | ❌ | Medium |
| **17D** | Tenant provisioning workflow plan (admin tool or script) | ❌ | Planning |
| **17E** | Tenant provisioning implementation | ❌ | High |
| **17F** | Business-owner onboarding UX plan | ❌ | Planning |
| **17G** | Owner dashboard simplification (billing link, settings, stats) | ❌* | Medium |

*17G billing link requires live Stripe, but the dashboard structure doesn't.

### Phase 18: Owner Experience and Documentation

| Release | Scope | EIN Needed? | Effort |
|---------|-------|-------------|--------|
| **18A** | "Getting Started" documentation for new business owners | ❌ | Low |
| **18B** | Mobile owner/tablet capability expansion plan | ❌ | Planning |
| **18C** | Sanitized demo/test data strategy | ❌ | Low |
| **18D** | Second-tenant dry run (create test tenant, validate isolation) | ❌ | Medium |
| **18E** | Payment terms + refund policy published | ❌ | Low (content) |

### Phase 19: Ryan Re-Evaluation

| Release | Scope | Depends On |
|---------|-------|------------|
| **19A** | Ryan external TestFlight readiness re-evaluation | 17B + 18A + 18C |
| **19B** | Ryan invitation (if gates G1–G6 + G10 pass) | 19A approved |
| **19C** | Ryan staff workflow external smoke validation | 19B |

### EIN-Dependent Track (Resumes When Available)

| Release | Scope |
|---------|-------|
| 13E | Live Stripe secret wiring |
| 13F | Live webhook validation |
| 13G | Internal $1 live test + refund |
| 13H | First real client payment |
| 17G+ | Stripe Customer Portal integration |

---

## 7. What Can Proceed While EIN Is Pending

| Work | Type | Safe? |
|------|------|-------|
| Entitlement enforcement design (17A) | Planning | ✅ |
| Entitlement enforcement implementation (17B) | Code | ✅ |
| Usage metering (17C) | Code | ✅ |
| Tenant provisioning planning (17D) | Planning | ✅ |
| Tenant provisioning implementation (17E) | Code | ✅ |
| Owner dashboard structure (17G, minus billing link) | Code | ✅ |
| "Getting Started" docs (18A) | Content | ✅ |
| Mobile capability plan (18B) | Planning | ✅ |
| Demo data strategy (18C) | Planning | ✅ |
| Second-tenant dry run (18D) | Code + test | ✅ |
| Payment terms published (18E) | Content | ✅ |
| Any admin/mobile UX polish | Code | ✅ |

**Everything except live Stripe and real client charges can proceed.**

---

## 8. What This Document Does NOT Authorize

- ❌ Inviting Ryan
- ❌ Code changes
- ❌ Deployments
- ❌ AWS/Terraform changes
- ❌ Stripe/payment actions
- ❌ DynamoDB writes
- ❌ Cognito changes
- ❌ Mobile builds or submissions
- ❌ Creating a second tenant
- ❌ Apple Beta Review resubmission

This is a strategic planning document. Each release in the 17/18/19 series requires separate approval.
