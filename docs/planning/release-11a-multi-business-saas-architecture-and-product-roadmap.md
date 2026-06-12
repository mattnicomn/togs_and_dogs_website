# Release 11A: Multi-Business SaaS Architecture & Product Roadmap

**Status:** Planning / Architecture Decision Document
**Priority:** Strategic (defines next 6-12 months of product direction)
**Risk to Production:** None (planning-only)
**Terraform Required:** No (planning)
**Backend Changes:** None (planning)
**Scope:** Product vision, architecture decisions, phased roadmap

---

## 1. Product Vision

### From Single-Business to Multi-Business SaaS

**Today:** Tog & Dogs is a single-business pet-sitting operations portal. Ryan is the sole business owner. All data lives in one DynamoDB table under one tenant (`tog_and_dogs`). The mobile app serves Ryan's staff and clients.

**Future:** The platform becomes a white-label SaaS product where multiple independent pet-sitting business owners can:
- Sign up and onboard their business
- Choose a service tier/package
- Customize branding (logo, name, colors)
- Manage their own staff, clients, pets, and bookings
- Operate via mobile (primary) and web (desktop admin)
- Pay a monthly subscription for platform access

**Positioning:** "Powered by US Mission Hero" — the platform serves business owners, not end consumers. Ryan is the first customer, not the only target.

---

## 2. Tenant Model

### Entity Hierarchy

```
PLATFORM (US Mission Hero)
└── BUSINESS OWNER (tenant)
    ├── Business Profile (name, logo, colors, settings)
    ├── Subscription (tier, billing, entitlements)
    ├── Staff Members
    │   └── Cognito users (staff group, scoped to tenant)
    ├── Clients
    │   └── Cognito users (client group, scoped to tenant)
    │   └── Pets
    │       └── Care instructions, vet info, emergency contacts
    └── Bookings / Visits
        ├── Service Requests (REQ#)
        ├── Jobs / Occurrences (JOB#)
        ├── Google Calendar events
        └── Notifications (Postmark)
```

### Current Single-Tenant Implementation

The existing system already has `company_id` on most records:
- `DEFAULT_COMPANY_ID = "tog_and_dogs"` (env var)
- `get_current_company_id(event)` resolves from JWT or defaults
- DynamoDB records include `company_id` field
- Some queries already filter by `company_id`

**This is a strong foundation.** Multi-tenancy doesn't require a full rewrite — it requires:
1. Making `company_id` truly dynamic (not hardcoded default)
2. Adding tenant provisioning
3. Adding billing/entitlement checks
4. Adding per-tenant branding
5. Ensuring data isolation is enforced everywhere

---

## 3. Landing Zone

### Public Business Owner Experience

```
usmissionhero.com (or saas.usmissionhero.com)
    └── Landing page: "Run your pet-sitting business from your phone"
        ├── Features showcase
        ├── Pricing tiers
        ├── "Start Free Trial" → Onboarding flow
        └── "I already have an account" → Login → Business selector
```

### Authenticated Business Owner Experience

```
After login (business owner role):
    └── Business Selector (if owner manages multiple businesses)
        └── Selected Business Dashboard
            ├── Operations (current admin dashboard)
            ├── Staff Management
            ├── Client Management
            ├── Billing & Subscription
            ├── Branding & Settings
            └── Analytics (future)
```

### "Powered by US Mission Hero"

- Every tenant's client-facing pages show "Powered by US Mission Hero" in footer
- Tenant's own branding (logo, colors, business name) is primary
- Platform branding is subtle/secondary

---

## 4. Package / Tier Model

### Proposed Tiers

| Tier | Monthly Price | Included |
|------|--------------|----------|
| **Starter** | $29/mo | 1 staff, 20 clients, 50 bookings/mo, email notifications, basic scheduling |
| **Professional** | $79/mo | 5 staff, 100 clients, unlimited bookings, Google Calendar, multi-day scheduling, mobile app, custom branding |
| **Premium** | $149/mo | Unlimited staff, unlimited clients, priority support, analytics, video visit evidence, API access |
| **Enterprise** | Custom | Multi-location, custom integrations, SLA, dedicated support |

### Included Capabilities by Tier

| Capability | Starter | Professional | Premium | Enterprise |
|-----------|---------|-------------|---------|-----------|
| Staff accounts | 1 | 5 | Unlimited | Unlimited |
| Client profiles | 20 | 100 | Unlimited | Unlimited |
| Monthly bookings | 50 | Unlimited | Unlimited | Unlimited |
| Email notifications | ✅ | ✅ | ✅ | ✅ |
| Push notifications | ❌ | ✅ | ✅ | ✅ |
| Google Calendar sync | ❌ | ✅ | ✅ | ✅ |
| Multi-day scheduling | ❌ | ✅ | ✅ | ✅ |
| Mobile app (staff) | ✅ | ✅ | ✅ | ✅ |
| Mobile app (client) | ❌ | ✅ | ✅ | ✅ |
| Custom branding | ❌ | ✅ | ✅ | ✅ |
| Video visit evidence | ❌ | ❌ | ✅ | ✅ |
| Analytics dashboard | ❌ | ❌ | ✅ | ✅ |
| API access | ❌ | ❌ | ❌ | ✅ |
| Multi-location | ❌ | ❌ | ❌ | ✅ |

---

## 5. Billing / Payment Strategy

### Recommended Approach

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Payment provider | **Stripe** | Industry standard for SaaS; handles subscriptions, invoices, trials |
| Billing target | **Business owner** (not end clients) | Clients don't pay for the app — the business owner pays the platform |
| App download | **Free** | App Store apps are free; subscription unlocks features server-side |
| Billing surface | **Web-first** | Stripe Checkout / Customer Portal via web; mobile links to web billing |
| Entitlement enforcement | **Backend** | Lambda checks subscription status before allowing actions |
| Trial period | 14 days free (Professional tier) | Standard SaaS trial |
| Payment failure | Grace period (7 days) → restrict to read-only → suspend | Graduated degradation |

### Entitlement Check Architecture

```python
# In Lambda handlers, before allowing write operations:
def check_entitlement(company_id, feature):
    subscription = get_subscription(company_id)
    if not subscription or subscription.status != 'active':
        return error(403, "Subscription required")
    if feature not in subscription.tier_features:
        return error(403, f"Upgrade to access {feature}")
```

This is a backend enforcement model — the mobile/web app calls the same APIs, and the backend gates features based on the tenant's subscription tier.

---

## 6. Self-Service Provisioning Roadmap

### Short Term (Releases 11B-11D): Manual/Admin-Assisted

- Matthew manually creates tenant records in DynamoDB
- Matthew creates Cognito user for business owner
- Matthew configures initial settings
- Business owner invited via email

### Medium Term (Release 12+): Templated Onboarding

- Business owner fills out onboarding form (business name, email, service types)
- System generates tenant record from template
- Cognito user auto-created with owner role
- Default settings applied (modifiable later)
- Stripe subscription created (trial starts)

### Long Term (Release 13+): Fully Automated

- Public signup page
- Self-service tenant creation
- Automated billing setup
- Templated branding configuration
- No Matthew intervention required for standard onboarding

---

## 7. Branding & Templating

### Per-Tenant Customization

| Element | Scope | Storage |
|---------|-------|---------|
| Business name | All screens, emails, calendar events | Tenant profile record |
| Logo (icon + wordmark) | App header, emails, invoices | S3 bucket per tenant |
| Primary color | App theme, buttons, accents | Tenant settings |
| Secondary color | Backgrounds, borders | Tenant settings |
| Service types | Booking options | Tenant configuration |
| Visit windows | Scheduling options | Tenant configuration |
| Notification templates | Email content | Tenant overrides or defaults |
| Terms / Privacy URLs | Legal pages | Tenant settings |

### Implementation Approach

The mobile app reads tenant branding from the API at login time:
```json
GET /tenant/config
→ { name, logo_url, primary_color, secondary_color, services: [...], windows: [...] }
```

App applies these dynamically. Default theme used if no customization exists.

---

## 8. AI/ML Automation Ideas (Future)

| Feature | Phase | Value |
|---------|-------|-------|
| **AI-assisted onboarding** | 13A | "Describe your business" → auto-generates service packages, visit windows, notification templates |
| **Suggested pricing** | 13A | Based on service type, location, competitor data |
| **Generated intake descriptions** | 13B | Auto-write client-facing service descriptions from structured data |
| **Support assistant** | 13C | AI chatbot for business owner FAQs (scheduling, billing, features) |
| **Admin analytics summaries** | 13D | "This week: 23 visits completed, 2 cancellations, $1,840 estimated revenue" |
| **Scheduling optimization** | 14+ | AI suggests optimal staff assignments based on location, availability, client preferences |

---

## 9. Video Visit Evidence Roadmap (Future)

| Phase | Scope | Infrastructure |
|-------|-------|---------------|
| 14A | Staff uploads short video clips after visit completion | S3 upload from mobile, metadata on JOB record |
| 14B | Client views visit clips in their portal | Presigned S3 URLs, time-limited access |
| 14C | Retention policy (auto-delete after 30/60/90 days) | S3 lifecycle rules |
| 14D | Storage management per tenant (quota by tier) | Per-tenant S3 prefix + metering |

### Considerations
- Privacy: videos contain client homes/pets — strict access control
- Storage cost: video is expensive — tier-gated
- Upload size: limit to 60-second clips (staff constraint)
- Compression: client-side before upload (Expo ImageManipulator)

---

## 10. Required Architecture Decisions

### Tenant Isolation Model

| Option | Pros | Cons | Recommendation |
|--------|------|------|---------------|
| Shared table with `company_id` filter | Simple, current approach, low cost | Noisy neighbor risk, complex authorization | ✅ **Recommended for now** |
| Table-per-tenant | Strong isolation | Expensive, complex management, Terraform per tenant | ❌ Defer |
| Separate AWS accounts per tenant | Ultimate isolation | Extreme complexity, cost | ❌ Not appropriate |

**Decision: Continue shared-table approach.** Add strict `company_id` enforcement on all queries. Add row-level security via backend authorization checks.

### Cognito Identity Strategy

| Option | Pros | Cons | Recommendation |
|--------|------|------|---------------|
| Single user pool, tenant in custom attribute | Simple, current approach | All users in one pool; harder to isolate | ✅ **Recommended for now** |
| User pool per tenant | Strong isolation | Expensive, complex rotation, multiple configs | ❌ Defer until 50+ tenants |

**Decision: Keep single user pool.** Add `custom:company_id` attribute to Cognito users. Resolve tenant from JWT claim at API level.

### DynamoDB Key Design Evolution

Current: `PK: COMPANY#{company_id}`, `SK: STAFF#{id}` / `CLIENT#{id}`

This already supports multi-tenancy for staff/client profiles. REQ# and JOB# records need `company_id` (already present on most). Enforce it consistently.

### API Authorization Model

Current: `get_effective_role(event)` + `get_current_company_id(event)` + `validate_tenant_ownership(item, event)`

This is the correct pattern. Ensure ALL endpoints enforce tenant scoping. Add billing entitlement checks at the same layer.

---

## 11. Release Roadmap

### Phase 11: Foundation (Architecture + Billing)

| Release | Scope | Effort |
|---------|-------|--------|
| **11A** | Architecture planning (this document) | ✅ Done |
| **11B** | Tenant data model design + DynamoDB key audit | 1-2 days |
| **11C** | Billing/entitlement design (Stripe integration planning) | 1-2 days |
| **11D** | Owner landing zone design (web) | 1 day |
| **11E** | Branding/template design (per-tenant config) | 1 day |

### Phase 12: Implementation (Core Multi-Tenancy)

| Release | Scope | Effort |
|---------|-------|--------|
| 12A | Backend tenant enforcement audit + fixes | 2-3 days |
| 12B | Cognito custom attribute + tenant resolution | 1-2 days |
| 12C | Stripe integration (subscription creation, webhook) | 3-5 days |
| 12D | Owner onboarding flow (web) | 2-3 days |
| 12E | Billing portal + entitlement enforcement | 2-3 days |

### Phase 13: Experience (Branding + AI)

| Release | Scope | Effort |
|---------|-------|--------|
| 13A | Per-tenant branding (logo, colors, name) | 2-3 days |
| 13B | AI-assisted onboarding | 3-5 days |
| 13C | Tenant-specific notification templates | 1-2 days |

### Phase 14: Advanced (Video + Scale)

| Release | Scope | Effort |
|---------|-------|--------|
| 14A | Video upload (staff mobile) | 3-5 days |
| 14B | Client video viewing | 2-3 days |
| 14C | Analytics dashboard | 3-5 days |

---

## 12. Immediate Next Practical Work

### Before Multi-Tenancy (Finalize Single-Tenant)

1. ✅ Mobile TestFlight P0 fixes complete (10H/10K)
2. ⏳ Add Ryan as External TestFlight tester (Gate D — when he's ready)
3. ⏳ Ryan validates production workflows on mobile
4. ⏳ First real-client operations with real bookings
5. ⏳ Feedback cycle → fix remaining UX issues

### Multi-Tenancy Starting Point (Release 11B)

Once Ryan is actively using the system and confirms the workflow is correct:
1. Audit all DynamoDB access patterns for `company_id` enforcement
2. Audit all API endpoints for tenant isolation
3. Design the tenant provisioning data model
4. Plan Stripe integration architecture
5. Begin implementation

---

## 13. Risks and Open Questions

| Risk / Question | Impact | Resolution |
|----------------|--------|-----------|
| Multi-tenancy breaks existing single-tenant workflow | High | Audit carefully; Ryan's tenant is the first and must remain stable |
| Stripe integration complexity | Medium | Use Stripe's hosted checkout/portal to minimize custom code |
| Cognito user pool limits (50,000 MAU free tier) | Low for now | Monitor; upgrade Cognito plan when nearing limit |
| Video storage costs | High at scale | Tier-gate; set retention policies; compress before upload |
| AI feature expectations vs reality | Medium | Start simple (templates); avoid promising intelligence too early |
| App Store review for subscription apps | Low | Apple allows free download + in-app subscription; follow their guidelines |
| Ryan's workflow must not break during multi-tenant migration | High | Keep `tog_and_dogs` as first tenant; all existing data stays |
| Business owner churn if pricing is wrong | Medium | Start with generous trial; adjust pricing based on early feedback |

---

## 14. What This Document Does NOT Authorize

- ❌ Any code changes
- ❌ Any infrastructure changes
- ❌ Any billing/payment implementation
- ❌ Creating new AWS resources
- ❌ Modifying DynamoDB schema
- ❌ Creating new Cognito configurations
- ❌ Starting Stripe integration
- ❌ Building landing pages
- ❌ Running EAS builds
- ❌ Deploying anything

This is a strategic planning document. Each phase requires separate explicit approval.

---

## 15. Recommended Next Release

**Release 11B: Tenant Data Model & DynamoDB Key Audit**

Scope: Audit every DynamoDB access pattern across all Lambda handlers. Document which already enforce `company_id` correctly and which have gaps. Design the formal tenant profile record structure. Plan the migration path from hardcoded `tog_and_dogs` to dynamic tenant resolution.

This is the smallest, safest first step toward multi-tenancy — pure analysis, no code changes.
