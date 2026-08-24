# Multi-Tenant URL, Identity, Client, and Pet Architecture Plan

**Status:** Planning (Architecture Decision Record)
**Date:** 2026-07-13
**Priority:** High (gates public-intake deployment and second-tenant readiness)
**Scope:** Platform surfaces, domain routing, identity, client/pet model, and phased delivery

---

## 2026-08-24 DOMAIN-1 Decision and Local Bridge Note

Manual UI review confirmed that active internal tenant `test_tenant_alpha` has no normal tenant-specific owner application landing URL. The identity itself is enabled and tenant-mapped; the newly documented blocker is the authenticated tenant bootstrap/surface.

For the Togs & Dogs product namespace, the authoritative staged recommendation is now:

- control plane: `platform.toganddogs.usmissionhero.com`;
- tenant plane: `<tenant-slug>.toganddogs.usmissionhero.com`;
- existing `toganddogs.usmissionhero.com`: temporary compatibility alias for the primary tenant;
- host or route context is an expected-tenant constraint only and must agree with authenticated `custom:company_id` plus strict tenant resolution;
- Platform Admin moves out of ordinary tenant navigation;
- DOMAIN-1 is accepted in `docs/planning/adr-domain-1-tenant-access-routing.md`;
- `/t/:tenantSlug/admin` and its fail-closed expected-tenant bootstrap are implemented and validated locally but not deployed;
- Gate B1A remains blocked until separately approved deployment and independent login-only isolation validation.

See `docs/planning/tenant-access-client-onboarding-operational-workflow-alignment.md`. That document is authoritative where its product-specific hostname phasing or Gate B1A status is more recent than the generic examples below.

---

## A. Platform Surfaces

### Surface Definitions

| Surface | Audience | Authentication | Tenant Context |
|---------|----------|---------------|----------------|
| Platform Management Console | platform_admin | Required (Cognito + platform_admin group) | Cross-tenant (platform-scoped) |
| Business Owner/Admin/Staff Portal | owner, admin, staff | Required (Cognito + role group) | Authenticated claim (custom:company_id) |
| Tenant-Branded Public Intake | Anonymous visitors | None required | Domain-mapped (server-side) |
| Tenant-Branded Client Portal | Authenticated clients | Required (Cognito + client group) | Authenticated claim |
| Mobile App | All authenticated roles | Required | Claim-based with tenant selector for multi-membership |

### Authorization Boundaries

- Platform admin can read/manage all tenants; cannot act as a business user without a separate membership
- Business owner/admin/staff operate within their single tenant boundary
- Clients operate within their tenant membership
- Anonymous visitors interact only with the specific tenant served by the domain they accessed
- No surface allows a user to select or switch tenants via browser-controlled input

---

## B. URL and Domain Strategy

### Recommended Structure

| Pattern | Purpose | Example |
|---------|---------|---------|
| `platform.<platform-domain>` | Platform admin console | `platform.usmissionhero.com` |
| `portal.<platform-domain>` | Shared business portal | `portal.usmissionhero.com` |
| `<tenant-slug>.<platform-domain>` | Tenant public + client | `toganddogs.usmissionhero.com` |
| `<verified-custom-domain>` | Tenant vanity domain | `book.toganddogs.com` |

### Domain-to-Tenant Registry

A DynamoDB or Terraform-managed mapping:

```
DOMAIN#toganddogs.usmissionhero.com → company_id: tog_and_dogs
DOMAIN#book.toganddogs.com → company_id: tog_and_dogs
DOMAIN#alpha.usmissionhero.com → company_id: test_tenant_alpha
```

Registry fields:
- `domain`: the hostname
- `company_id`: the mapped tenant
- `verified`: boolean (verified ownership)
- `is_primary`: boolean (the tenant's primary domain)
- `public_intake_enabled`: boolean (can serve public intake form)
- `status`: active | pending_verification | disabled
- `created_at`, `updated_at`

### Trusted Resolution Mechanism

**Preferred:** Use `event.requestContext.domainName` from API Gateway.

This field is set by API Gateway from the actual custom-domain mapping configuration. It cannot be spoofed by the browser (unlike Host headers). The resolver:

1. Reads `requestContext.domainName` from the Lambda event
2. Looks up the domain in the tenant-domain registry
3. Validates: domain is verified, active, and public_intake_enabled
4. Validates: the mapped tenant is active
5. Returns the `company_id`
6. Fails closed if any validation fails

**Direct execute-api access:** Requests to the raw `*.execute-api.amazonaws.com` URL will have that as their `domainName`. This should either be:
- Denied for public intake (no domain mapping exists), or
- Mapped to a default tenant only if explicitly configured in the registry

**Authenticated-claim/domain mismatch:**
- If a user is authenticated with `custom:company_id = tenant_A` but hits a domain mapped to `tenant_B`, deny the request
- This prevents a second-tenant user from accidentally submitting intake to the wrong business

### What Is NOT Trusted

- ❌ Request body `company_id`
- ❌ Query string tenant parameters
- ❌ `Origin` or `Referer` headers
- ❌ Local storage values
- ❌ Arbitrary custom headers
- ❌ `DEFAULT_COMPANY_ID` fallback in multi mode

---

## C. Public Intake Correction

### Issues with Commit 00338f2

| Issue | Problem |
|-------|---------|
| Falls back to DEFAULT_COMPANY_ID | Does not truly fail closed in multi mode |
| Single env-var tenant | Cannot support multiple branded domains |
| No domain-to-tenant validation | No proof the request came from the correct branded site |
| No active-tenant check | Could route to a disabled tenant |
| No authenticated-domain mismatch check | A second-tenant user could submit to the wrong business |

### Required Corrections

The resolver must:
1. **Remove** the `DEFAULT_COMPANY_ID` fallback in multi mode
2. **Add** domain-to-tenant lookup via `requestContext.domainName`
3. **Validate** the mapped tenant is active
4. **Deny** authenticated-claim vs domain-tenant mismatches
5. **Fail closed** when no valid mapping exists

### What Can Be Retained from 00338f2

| Part | Keep? | Reason |
|------|:-----:|--------|
| `resolve_public_intake_tenant()` function signature | ✅ | Good separation from global resolver |
| Authenticated-claim-first resolution order | ✅ | Correct priority |
| Never reads body/query/headers | ✅ | Correct security boundary |
| Route-scoped (only intake handler uses it) | ✅ | Doesn't weaken global resolver |
| Falls back to DEFAULT_COMPANY_ID | ❌ | Must be removed in multi mode |
| No domain validation | ❌ | Must add domain lookup |
| No active-tenant check | ❌ | Must validate tenant status |
| Tests for body-rejection, fail-closed, auth-precedence | ✅ | Core tests are valid |
| Tests need additions for domain, inactive, mismatch | ➕ | New test cases required |

### Smallest Secure First Implementation for Togs & Dogs

**Phase 1 (immediate, no Terraform domain changes needed):**

Use a Terraform-managed JSON map in Lambda environment:
```
PUBLIC_INTAKE_DOMAIN_MAP = {"toganddogs.usmissionhero.com": "tog_and_dogs"}
```

The resolver:
1. If authenticated: use claim
2. Read `requestContext.domainName`
3. Look up in the configured domain map
4. Validate tenant is active
5. If authenticated claim differs from domain tenant: deny
6. If no mapping: deny

This supports adding future tenants by updating the env-var map — no code changes needed.

**Phase 2 (DynamoDB domain registry):**
Move the mapping to DynamoDB for dynamic domain management via Platform Admin.

---

## D. Identity and Membership Evolution

### Current Limitation

One `custom:company_id` per Cognito user = one tenant membership per identity.

### Target Design

```
UserIdentity (Cognito user)
├── sub: unique identity
├── email
├── email_verified
└── TenantMemberships[]
    ├── company_id: "tog_and_dogs"
    ├── role: "owner"
    ├── status: "active"
    ├── joined_at
    └── company_id: "test_tenant_alpha"
        ├── role: "staff"
        ├── status: "active"
        └── joined_at
```

### Membership Model

| Field | Type | Description |
|-------|------|-------------|
| PK | `IDENTITY#{cognito_sub}` | User identity |
| SK | `MEMBERSHIP#{company_id}` | Tenant membership |
| company_id | string | Target tenant |
| role | enum | owner/admin/staff/client |
| status | enum | active/invited/disabled/removed |
| joined_at | ISO timestamp | When membership was created |
| invited_by | string | Admin who created the membership |

### Tenant Selector

For multi-membership users, the frontend presents a tenant selector after login. The selected tenant is validated server-side against the user's active memberships — never trusted from the browser alone.

### Migration Path from custom:company_id

1. Deploy membership-based resolution alongside claim-based (backward compatible)
2. For existing users: their single `custom:company_id` implicitly maps to one membership
3. New memberships are created through admin invitation
4. Eventually: `custom:company_id` becomes the "primary" or "last-used" tenant hint, but server validates against membership records

### No Implementation Now

This requires:
- Membership DynamoDB records
- Server-side membership validation
- Frontend tenant selector
- Token refresh or session context switching
- Migration tooling

---

## E. Client/Household and Pet Model

### Entity Design

```
Household (PK: COMPANY#{company_id}, SK: HOUSEHOLD#{household_id})
├── household_id: unique
├── company_id: tenant ownership
├── display_name: "The Rockwell Family"
├── status: active | archived
├── created_at, updated_at
│
├── HouseholdContacts[]
│   ├── contact_id
│   ├── name, email, phone
│   ├── relationship: primary | secondary | emergency
│   ├── is_billing_contact: bool
│   └── cognito_sub: optional (linked user)
│
├── ServiceAddresses[]
│   ├── address_id
│   ├── label: "Home", "Vacation House"
│   └── street, city, state, zip
│
├── EmergencyContact
│   ├── name, phone, relationship
│
├── VeterinaryClinic
│   ├── name, phone, address
│
└── Pets[]
    ├── pet_id
    ├── household_id (parent)
    ├── company_id (tenant)
    ├── name, species, breed, age, weight
    ├── health notes, medications, allergies
    ├── status: active | archived
    ├── archived_at: timestamp (if archived)
    └── created_at, updated_at
```

### Rules

| Rule | Enforcement |
|------|-------------|
| Clients may exist without Cognito accounts | household_contact.cognito_sub is optional |
| One household may have multiple contacts and pets | 1:N relationship |
| Pets belong to a household and tenant | pet.household_id + pet.company_id |
| Pet management available inside Client Management | UI path: Client → Household → Pets |
| Global pet search links back to household | Index on pet name/species |
| Persisted pets are archived, not hard-deleted | status = archived, preserved for history |
| Unsaved inline pets can be removed from request form | Frontend-only, not persisted until saved |
| Requests reference household_id and pet_ids | Foreign key references |
| Requests preserve immutable snapshots | RequestClientSnapshot, RequestPetSnapshot |
| Email matching never auto-merges profiles | Explicit admin link required |
| Tenant isolation on every entity | company_id PK prefix |

### Request Snapshots

```
ServiceRequest
├── request_id
├── company_id
├── household_id (reference)
├── pet_ids[] (references)
├── RequestClientSnapshot (immutable at submission time)
│   ├── client_name, email, phone
│   └── address snapshot
└── RequestPetSnapshots[] (immutable at submission time)
    ├── pet_name, species, breed
    └── health/medication notes at time of request
```

---

## F. UX by Role

### Platform Owner (platform_admin)
- Tenant lifecycle (create, disable, restore, archive)
- Domain configuration and verification
- Subscription management
- Cross-tenant audit logs
- Support tooling

### Business Owner/Admin
- Dashboard (intake queue, needs assignment, scheduled, alerts)
- Client/Household Management (CRUD, contacts, addresses)
- Pet Management (within household context)
- Staff Management (profiles, identity, scheduling)
- Request/Booking Management
- Payments and invoicing
- Google Calendar integration
- Settings and branding

### Staff
- Assigned visits schedule
- Household/pet details needed for service delivery
- Care notes and visit completion
- Cannot manage clients, pets, or business settings

### Client (Authenticated)
- Household profile and contacts
- Pet profiles (view/edit own pets)
- Request care (with saved pets from household)
- View bookings and status
- Payments and invoices
- Messages and notifications

### Anonymous Visitor
- Tenant-branded public intake form only
- No account required
- No profile or pet data saved beyond the request snapshot
- Cannot view existing bookings or household data

---

## G. Phased Release Plan

### Phase 1: Trusted Domain-to-Tenant Public Intake

**Scope:** Revise `resolve_public_intake_tenant` to use domain mapping
**Data migrations:** None (env-var JSON map)
**API changes:** Intake resolver reads `requestContext.domainName`
**UI changes:** None
**Tests:** Domain mapping, inactive tenant, direct-API denial, authenticated mismatch
**Security risks:** Low (fail-closed design)
**Approval gates:** Terraform plan review (add env-var), Matthew apply approval
**Rollback:** Remove env-var, revert code
**Deferred:** DynamoDB domain registry, custom domain verification

### Phase 2: Staff Email-Field and Management Consistency

**Scope:** Ensure staff email is consistently stored/displayed; fix display inconsistencies
**Data migrations:** None
**API changes:** Minor validation
**UI changes:** Staff card/editor consistency
**Tests:** Email validation, display
**Approval gates:** Standard pre-deploy validation
**Deferred:** Multi-membership staff

### Phase 3: Client/Household Management Parity

**Scope:** Introduce Household model; migrate existing clients to household records
**Data migrations:** Create HOUSEHOLD records for existing CLIENT records
**API changes:** New CRUD endpoints for households, contacts, addresses
**UI changes:** Client Management → Household Management UI
**Tests:** Household CRUD, contact management, tenant isolation
**Security risks:** Migration must preserve tenant isolation
**Approval gates:** Migration script dry-run, Matthew approval
**Deferred:** Pet management within households

### Phase 4: Pet Lifecycle and Archive Behavior

**Scope:** Pet CRUD within household context; archive instead of delete
**Data migrations:** Existing pets linked to households
**API changes:** Pet CRUD scoped to household
**UI changes:** Pet management within Client/Household Management
**Tests:** Pet lifecycle, archive, tenant isolation
**Approval gates:** Standard
**Deferred:** Global pet search

### Phase 5: Repeat-Client Intake and Immutable Snapshots

**Scope:** Authenticated clients submit requests with saved household/pet data; immutable snapshots
**Data migrations:** None (new requests use snapshot pattern)
**API changes:** Request creation captures snapshots
**UI changes:** Client portal request form pre-fills from saved data
**Tests:** Snapshot immutability, no auto-merge, tenant isolation
**Approval gates:** Standard
**Deferred:** Recurring bookings

### Phase 6: Multi-Membership Identity

**Scope:** TenantMembership records; tenant selector; server validation
**Data migrations:** Create membership records from existing custom:company_id
**API changes:** Membership CRUD, tenant-switch validation
**UI changes:** Tenant selector in nav
**Tests:** Multi-membership resolution, cross-tenant isolation, selector validation
**Security risks:** Identity confusion between tenants
**Approval gates:** Security review, Matthew approval
**Deferred:** Second real tenant onboarding

### Phase 7: Custom-Domain Onboarding and Verification

**Scope:** Platform Admin domain management; DNS verification; DynamoDB domain registry
**Data migrations:** Move from env-var map to DynamoDB
**API changes:** Domain CRUD in platform handler
**UI changes:** Platform Admin domain configuration
**Tests:** Verification flow, DNS check, status transitions
**Approval gates:** Platform admin review
**Deferred:** Automatic SSL certificate provisioning

---

## H. Evaluation of Commit 00338f2

### What Can Be Retained

| Component | Retain | Notes |
|-----------|:------:|-------|
| `resolve_public_intake_tenant()` function structure | ✅ | Route-scoped, separate from global resolver |
| Authenticated-claim-first priority | ✅ | Correct security model |
| Body/query/header rejection | ✅ | Must never trust browser input |
| Intake handler uses route-specific resolver | ✅ | Doesn't weaken global |
| 11 existing tests (helper + handler) | ✅ | Core test patterns valid |
| Staff-options uses same resolver | ✅ | Consistent |

### What Must Be Revised

| Component | Issue | Required Change |
|-----------|-------|-----------------|
| DEFAULT_COMPANY_ID fallback | Not fail-closed in multi mode | Replace with domain mapping lookup |
| PUBLIC_INTAKE_TENANT_ID env var | Single-value, no domain validation | Replace with domain map or remove |
| No domain validation | Doesn't verify request origin | Add requestContext.domainName lookup |
| No active-tenant check | Could route to disabled tenant | Add require_active_tenant validation |
| No auth-domain mismatch check | Cross-tenant risk | Deny if authenticated claim ≠ domain tenant |

### Can a Follow-Up Commit Correct It Before Deployment?

**Yes.** Since `00338f2` was never deployed, a follow-up commit can safely revise `resolve_public_intake_tenant()` before the next Terraform apply. The function signature and test structure are sound — only the resolution logic and a Terraform env-var addition are needed.

### Additional Tests Required

- Domain mapping resolves correctly
- Unmapped domain is denied
- Inactive tenant in mapping is denied
- Direct execute-api domain is denied (or explicitly configured)
- Authenticated claim ≠ domain tenant is denied
- Authenticated claim = domain tenant succeeds
- Domain map missing from env fails closed
- Invalid JSON in domain map fails closed

---

## What This Document Does NOT Authorize

- ❌ Implementation of any phase
- ❌ Deployment of 00338f2 or any follow-up
- ❌ Terraform apply
- ❌ DynamoDB schema changes
- ❌ Cognito configuration changes
- ❌ Second tenant creation
- ❌ Custom domain provisioning
- ❌ Identity/membership migration
- ❌ Client/household model creation
- ❌ Frontend changes
- ❌ Mobile changes
- ❌ Stripe or Google Calendar changes

Each phase requires separate planning, implementation, testing, and deployment approval.
