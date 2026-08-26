# Platform Tenant Management Control Plane Architecture and Backlog Specification

**Document Version:** 1.0.0  
**Status:** Approved Architectural Specification / Implementation Deferred  
**Owner:** Matthew / Platform Engineering  
**Created:** 2026-08-25  
**Authoritative Reference:** `docs/planning/platform-tenant-management-control-plane.md`  

---

## 1. Executive Summary

This document establishes the formal architecture, data model, security boundary, and phased implementation backlog for the **Platform Tenant Management Control Plane** (`PTM`) of the Togs & Dogs / USMissionHero SaaS platform.

As the platform matures beyond single-tenant operations and the initial internal validation tenant (`test_tenant_alpha`), tenant administrative workflows must transition away from direct AWS console inspection, manual DynamoDB item edits, and command-line provisioning scripts into a governed, audited, and secure **Platform Admin Control Plane**.

This specification defines the control-plane vs. tenant-plane boundaries, Cognito group/identity rules, app-client policies, canonical tenant lifecycle states, and a 13-stage backlog (`PTM-0` through `PTM-12`).

---

## 2. Audit of Existing Platform Admin Capabilities

The repository contains an existing foundational Platform Admin implementation deployed on the shared compatibility surface (`/platform-admin/*`).

### 2.1 Existing Routes and Frontend Components
* **`/platform-admin/tenants`** (`web/src/components/PlatformAdmin.jsx`): Global listing of registered business entities with search (by company ID or display name), status/tier badges, and direct navigation to detailed tenant records.
* **`/platform-admin/tenants/:companyId`** (`web/src/components/PlatformTenantDetail.jsx`): Single tenant detail view rendering tenant profile metadata, subscription tier/status, entitlement usage limits, Google Calendar integration status, notes, admin overrides, and status modification controls (`active`, `disabled`, `paused`, `trialing`).
* **`/platform-admin/onboarding`** (`web/src/components/PlatformAdminOnboarding.jsx`): Read-only Platform Admin Tenant-Onboarding Orchestrator V1 preview component providing input validation, conflict checks, metadata previews, tier limit projections, and onboarding checklists.
* **`/platform-admin/audit`** (`web/src/components/PlatformAuditLog.jsx`): Paginated platform audit log viewer displaying `PLATFORM_AUDIT` records.

### 2.2 Existing Backend Endpoints and Handlers
* **`GET /platform/tenants`** (`src/backend/handlers/platform_handler.py`): Scans `PK=TENANT#<id>`, `SK=METADATA` records and returns basic tenant summaries.
* **`GET /platform/tenants/{company_id}`** (`platform_handler.py`): Returns detailed tenant profile, subscription, entitlement calculation, active staff count, active client count, monthly booking count, and per-tenant Google Calendar metadata config.
* **`PATCH /platform/tenants/{company_id}`** (`platform_handler.py`): Updates allowed tenant metadata attributes (`display_name`, `subscription_tier`, `subscription_status`, `admin_override_until`, `notes`), invalidates entitlement caches, and appends a `PLATFORM_AUDIT` record.
* **`GET /platform/audit`** (`platform_handler.py`): Returns paginated platform audit records (`PK=PLATFORM_AUDIT`, `SK=ACTION#...`).
* **`POST /platform/onboarding/validate`** (`src/backend/handlers/platform_onboarding_handler.py`): Validates proposed tenant inputs against conflict/syntax rules.
* **`POST /platform/onboarding/preview`** (`platform_onboarding_handler.py`): Generates preview tenant metadata and audit templates without database writes.

### 2.3 Existing Sources of Truth and Security Boundaries
* **Tenant Registry**: DynamoDB table items `PK=TENANT#<company_id>`, `SK=METADATA`.
* **Tenant Identity**: Cognito custom attribute `custom:company_id` (e.g., `tog_and_dogs`, `test_tenant_alpha`).
* **Role/Security Boundary**: Enforced via `is_platform_admin(event)` in `src/backend/common/auth.py`. Requires Cognito user membership in the `platform_admin` group.
* **Tenant Route Slug**: Currently resolved via backend bridge in `src/backend/common/tenant_route.py` (`test-tenant-alpha` $\rightarrow$ `test_tenant_alpha`, `tog-and-dogs` $\rightarrow$ `tog_and_dogs`).

---

## 3. Control Plane vs. Tenant Plane Architecture Model

The platform strictly separates **Control Plane** operations from **Tenant Plane** operations.

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │               USMISSIONHERO SAAS PLATFORM                  │
                    └──────────────────────────────┬──────────────────────────────┘
                                                   │
                   ┌───────────────────────────────┴───────────────────────────────┐
                   │                                                               │
     ┌─────────────▼──────────────┐                                  ┌─────────────▼──────────────┐
     │       CONTROL PLANE        │                                  │        TENANT PLANE        │
     ├────────────────────────────┤                                  ├────────────────────────────┤
     │ Hostname (Future):         │                                  │ Hostname (Future):         │
     │ platform.toganddogs.      │                                  │ <slug>.toganddogs.         │
     │ usmissionhero.com          │                                  │ usmissionhero.com          │
     │                            │                                  │                            │
     │ Route (Current):           │                                  │ Route (Current):           │
     │ /platform-admin/*          │                                  │ /t/:tenantSlug/*           │
     ├────────────────────────────┤                                  ├────────────────────────────┤
     │ Authority:                 │                                  │ Authority:                 │
     │ platform_admin group       │                                  │ custom:company_id claim +  │
     │                            │                                  │ owner/admin/staff/client   │
     ├────────────────────────────┤                                  ├────────────────────────────┤
     │ Responsibilities:          │                                  │ Responsibilities:          │
     │ • Global tenant directory  │                                  │ • Bookings & Schedule      │
     │ • Lifecycle & Onboarding   │                                  │ • Client & Pet Management  │
     │ • Subscriptions & Tiers    │                                  │ • Sitter Assignment        │
     │ • Global DNS / Domains     │                                  │ • Invoicing & Payments     │
     │ • Platform Audit & Health  │                                  │ • Operational Workflows    │
     └────────────────────────────┘                                  └────────────────────────────┘
```

### 3.1 Control Plane
* **Conceptual Hostname:** `platform.toganddogs.usmissionhero.com` (Current compatibility route: `/platform-admin/*`).
* **Authority:** Granted strictly to authenticated users with `platform_admin` Cognito group membership.
* **Scope:** Cross-tenant administration, tenant lifecycle, global directory, domain mappings, entitlement management, platform-wide metrics, and audit logging.
* **Isolation Rule:** Control-plane interfaces must never render operational tenant data (e.g., client names, pet medical notes, payment details) unless specifically required for an administrative audit, in which case data must be sanitized.

### 3.2 Tenant Plane
* **Conceptual Hostname:** `<tenant-slug>.toganddogs.usmissionhero.com` (Current compatibility route: `/t/:tenantSlug/*`).
* **Authority Agreement:** Granted ONLY when all 5 dimensions of the canonical DOMAIN-1 authorization model agree:
  1. **Identity Assertion:** Authenticated Cognito identity token claims.
  2. **Tenant Claim:** `custom:company_id` claim matches the requested/resolved tenant.
  3. **Tenant Resolution:** Server-owned registry maps route/host to an active tenant.
  4. **Entitlement State:** Active/eligible subscription and entitlement state (`is_access_allowed: true`).
  5. **Role Authorization:** Cognito role group (`owner`, `admin`, `staff`, `client`) authorizes the operation.
* **Scope:** Business operations, pet care scheduling, client management, staff assignments, and billing.
* **Isolation Rule:** A tenant-plane route or session must **NEVER** grant control-plane authority or allow cross-tenant data access. Navigation links to Platform Admin are strictly suppressed within tenant-plane views.

### 3.3 Tenant Presentation & Branding Architecture Model

During Alpha validation, a key tenant experience gap was identified: while DOMAIN-1 successfully establishes backend tenant routing and security isolation (`/t/:tenantSlug/admin`), the Web presentation layer defaults to global Togs & Dogs branding in unconfigured areas such as client/staff portals, intake forms, email headers, and shell navigation.

To address this gap while maintaining architectural purity, the platform adopts the following presentation principles:

1. **Preservation of One Single Shared React Application:**
   All tenants continue to run on the exact same single React/Vite web application bundle. Separate per-tenant frontend codebases, repositories, build targets, or custom S3 deployments are **STRICTLY FORBIDDEN**.
2. **Preservation of Shared Identity & Security Architecture:**
   * **Cognito App Client:** One single shared Web app client for all normal tenants.
   * **Cognito Groups:** Global functional role groups (`client`, `staff`, `admin`, `owner`, `platform_admin`). Creating per-tenant Cognito groups or per-tenant app clients remains forbidden.
3. **Dynamic Tenant Presentation Resolution:**
   The Web presentation layer dynamically resolves tenant branding from the server-owned tenant registry metadata (`GET /t/:tenantSlug/bootstrap` or `/platform/tenants/{id}`):
   * `display_name` & `brand_name`: Business display title in shell header, page title, and footers.
   * `brand_color` & `theme_palette`: CSS theme variable overrides (e.g. primary accent color).
   * `logo_url` & `favicon_url`: Asset URLs for header branding.
   * `support_email` & `contact_phone`: Tenant customer support details.
   * `intake_config`: Tenant-specific intake form rules, required fields, and client onboarding workflows.
4. **Graceful Fallback:**
   If a tenant has no custom branding configured or operates under default settings, the Web presentation layer falls back cleanly to standard platform defaults without throwing runtime errors or displaying missing assets.

---

## 4. Fundamental Identity, Authorization, and Security Rules

```
================================================================================
CANONICAL TENANT AUTHORIZATION MODEL (5-WAY AGREEMENT)
================================================================================
```

Tenant authorization is NOT derived from any single field or header. Access requires complete agreement across five distinct architectural dimensions:

| Dimension | Element | Mechanism / Source | Authority Classification |
|-----------|---------|-------------------|--------------------------|
| 1 | **Identity Assertion** | Authenticated Cognito User | Token Claims (`sub`, `email`, `custom:company_id`) |
| 2 | **Tenant Claim** | `custom:company_id` | Canonical Tenant Claim |
| 3 | **Tenant Resolution** | Server-owned Tenant Registry & Route Bridge | Server Lookup (`resolve_expected_tenant()`) |
| 4 | **Entitlement State** | Active Subscription & Overrides | Server Entitlement (`require_active_tenant()`) |
| 5 | **Role Authorization** | Cognito Role Groups | Group Claims (`client`, `owner`, `staff`, `admin`, `platform_admin`) |

### 4.1 Strict Authority Boundaries
* **Route Slugs Alone:** Route slugs (e.g., `/t/test-tenant-alpha/*`) are presentation/context signals and grant **ZERO** access authority.
* **Hostnames Alone:** Hostnames (e.g., `test-tenant-alpha.toganddogs.usmissionhero.com`) are routing signals requiring server verification and grant **ZERO** access authority.
* **`custom:company_id` Alone:** The `custom:company_id` claim is an identity assertion and is **NOT** independently sufficient authority. It must NEVER bypass server-side registry checks, entitlement checks, or role authorization checks.
* **Cognito Groups:** Cognito groups represent **ROLES ONLY** (`client`, `owner`, `staff`, `admin`, `platform_admin`), not tenant identities.
* **`platform_admin` Authority:** The `platform_admin` role provides control-plane administrative authority only. It does **NOT** grant implicit operational tenant-plane authority merely through a tenant route.
* **Fail-Closed Resolution:** Mismatched, missing, or inactive tenant context fails closed immediately with no fallback to the primary tenant (`tog_and_dogs`).

### 4.2 Cognito Group Architecture Rule
Cognito user pool groups in the platform represent **functional authorization roles**, not tenant identities.

* **Allowed Role Groups:**
  * `client` — Customer portal access
  * `staff` — Sitter / employee access
  * `admin` — Business admin access
  * `owner` — Business owner / primary tenant admin access
  * `platform_admin` — Global platform control-plane access

* **Tenant Identity Mechanism:**
  Tenant assignment is strictly governed by the Cognito user custom attribute:
  $$\text{custom:company\_id} = \text{<canonical\_tenant\_id>}$$

* **FORBIDDEN ANTI-PATTERN:**
  Do **NOT** create tenant-specific Cognito groups such as `test_tenant_alpha_owner`, `tenant_x_staff`, or `tenant_y_client`. Creating one Cognito group per tenant leads to group quota explosion, fragile policy evaluation, and broken RBAC boundaries.

### 4.3 Cognito App Client Architecture Rule
* **Default Single Shared App Client:**
  The platform uses **one shared production Web Cognito app client** for all standard Togs & Dogs tenants. Tenant context is established post-authentication via token claims (`custom:company_id`) and backend registry validation.
* **Exception Criteria for Dedicated App Clients:**
  Dedicated Cognito app clients (or dedicated user pool configurations) are explicitly deferred and permitted **ONLY** under approved enterprise requirements:
  1. Enterprise SAML / OIDC Single Sign-On (SSO) federation with custom IdPs.
  2. Contractually mandated dedicated OAuth client secret isolation.
  3. Custom branded mobile/native applications requiring distinct OAuth callback URIs.

---

## 5. Canonical Tenant Lifecycle Model

To prevent state ambiguity, tenant status is modeled using three distinct orthogonal dimensions:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TENANT STATE DIMENSIONS                           │
├──────────────────────────┬──────────────────────────┬───────────────────────┤
│ Lifecycle State          │ Subscription Status      │ Entitlement State     │
├──────────────────────────┼──────────────────────────┼───────────────────────┤
│ • PROSPECT               │ • trialing               │ • allowed             │
│ • ONBOARDING             │ • active                 │ • blocked             │
│ • ACTIVE                 │ • past_due               │ • overridden          │
│ • SUSPENDED              │ • canceled               │                       │
│ • ARCHIVED               │ • paused                 │                       │
│                          │ • disabled               │                       │
└──────────────────────────┴──────────────────────────┴───────────────────────┘
```

### 5.1 Lifecycle States
1. **`PROSPECT`**: Initial lead/inquiry. No database record or infrastructure provisioned.
2. **`ONBOARDING`**: Metadata record created; configuration, identity setup, and readiness checklists in progress. Access restricted to preview/staging.
3. **`ACTIVE`**: Fully provisioned, validated, and operational. Tenant users can log in and execute business workflows.
4. **`SUSPENDED`**: Administrative or billing hold. Access blocked (`403 TenantDisabled` / `is_blocked: true`); data preserved.
5. **`ARCHIVED`**: Permanently retired business entity. Read-only historical retention; access disabled.

### 5.2 Separation of Concerns
* **Lifecycle State** (`lifecycle_state`): Governs system availability (`ONBOARDING`, `ACTIVE`, `SUSPENDED`, `ARCHIVED`).
* **Subscription Status** (`subscription_status`): Governs billing state (`trialing`, `active`, `past_due`, `canceled`, `paused`, `disabled`).
* **Entitlement State** (`entitlement_state`): Governs metric limits and administrative overrides (`allowed`, `blocked`, `overridden` until `admin_override_until`).

---

## 6. Platform Tenant Directory and Tenant Details View Specifications

### 6.1 Tenant Directory (Platform Admin Control Plane)
The Tenant Directory listing view (`/platform-admin/tenants`) displays a governed inventory of all registered businesses.

* **Read-Only V1 Required Fields:**
  * Business Display Name (`display_name`)
  * Canonical Tenant ID (`company_id`)
  * Tenant Route Slug (`tenant_slug`)
  * Lifecycle State (`lifecycle_state`)
  * Subscription Tier (`subscription_tier`: `starter`, `professional`, `premium`, `enterprise`)
  * Subscription Status (`subscription_status`)
  * Entitlement State (`entitlement_state`)
  * Onboarding Readiness (`onboarding_state`)
  * Primary Owner Count (`owner_count`)
  * Active Staff Count (`active_staff`)
  * Active Client Count (`active_clients`)
  * Registration Date (`created_at`)
  * Last Updated Date (`updated_at`)
  * Routing / Domain Status (`domain_status`: `compatibility_host`, `subdomain_active`, `custom_domain_active`)

### 6.2 Tenant Details View (7 Logical Sections)
The Tenant Detail View (`/platform-admin/tenants/:companyId`) provides comprehensive visibility into a single business entity:

1. **Section A: Overview**
   * Display Name, Canonical ID, Route Slug, Lifecycle State, Subscription Tier/Status, Entitlement State, Creation/Update Timestamps.
2. **Section B: Routing & Hostnames**
   * Canonical Route Slug, Generated Subdomain (`<slug>.toganddogs.usmissionhero.com`), Custom Domain (if applicable), DNS Verification Status, SSL/TLS Certificate Health.
3. **Section C: Owners & Identity**
   * Sanitized listing of associated business owners and staff, Cognito `custom:company_id` claim status, identity verification state (`CONFIRMED` / `UNCONFIRMED`), role memberships.
4. **Section D: Subscriptions & Entitlements**
   * Plan tier details, active usage metrics vs. tier limits (active clients, monthly bookings, staff seats), administrative override expiration (`admin_override_until`), billing history links.
5. **Section E: Onboarding Status**
   * Onboarding phase, owner invitation status, business configuration completeness, Google Calendar integration readiness, operational launch checklist.
6. **Section F: Operational Health**
   * Database item health, tenant isolation health, auth claim agreement status, API response metrics, error rates.
7. **Section G: Audit History**
   * Filtered timeline of all `PLATFORM_AUDIT` actions associated with this tenant (creation, status changes, tier updates, admin overrides).
8. **Section H: Presentation & Branding**
   * Read-only view of business branding attributes (`display_name`, `brand_color`, `theme_palette`, `logo_url`, `support_email`, `portal_theme`, `intake_config_status`).

---

## 7. Onboarding Integration Strategy

The Platform Tenant Management Control Plane integrates directly with the existing **Preview-Only V1 Platform Admin Tenant-Onboarding Orchestrator** (`src/backend/handlers/platform_onboarding_handler.py`).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONTROL PLANE ONBOARDING FLOW                            │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
  1. Tenant Directory ───────► Click "Onboard New Tenant"
                                       │
  2. Input Validation ───────► POST /platform/onboarding/validate
                                       │ (Syntax, slug uniqueness, conflict check)
                                       │
  3. Metadata Preview ───────► POST /platform/onboarding/preview
                                       │ (Preview record, tier limits, checklist)
                                       │
  4. Approval Gate    ───────► Require Explicit Matthew Approval
                                       │
  5. Provisioning     ───────► Controlled Tenant Creation (PTM-8)
                                       │ (DynamoDB metadata, audit record)
                                       │
  6. Owner Invitation ───────► Owner User Provisioning & Identity Link
                                       │
  7. Activation       ───────► Lifecycle State -> ACTIVE
```

---

## 8. Auditability, Security Boundaries, and Deferred Features

### 8.1 Auditability Rules
Every control-plane operation must append an immutable `PLATFORM_AUDIT` record (`PK=PLATFORM_AUDIT`, `SK=ACTION#<ISO_TIMESTAMP>#<UUID>`).

* **Mandatory Audit Fields:**
  * `actor`: Email or username of the Platform Admin executing the action.
  * `action`: Standardized event name (e.g., `CREATE_TENANT`, `UPDATE_TENANT_STATUS`, `MODIFY_TIER`, `UPDATE_TENANT_BRANDING`).
  * `target_company_id`: Canonical tenant ID affected.
  * `timestamp`: ISO 8601 UTC timestamp.
  * `old_values` / `new_values`: Map of modified attributes.
  * `correlation_id`: Request correlation ID.

* **FORBIDDEN LOGGING PATTERNS:**
  Audit logs, Lambda execution logs, and API outputs must **NEVER** contain:
  * Passwords or temporary credentials.
  * JWT tokens or raw `Authorization` headers.
  * Payment card numbers, Stripe secret keys, or bank details.
  * Unsanitized PII beyond admin email addresses.

### 8.2 Security Boundaries
* Control-plane authority strictly requires `is_platform_admin(event) == True`.
* Tenant route slugs and hostnames are presentation/context signals; data access requires 5-way agreement among (1) authenticated Cognito identity token claims, (2) `custom:company_id` tenant claim, (3) server-owned route resolution, (4) active/eligible server-side tenant registry/entitlement state, and (5) role authorization.
* Control-plane interfaces must never expose tenant-plane operational data unless sanitized for platform auditing.

### 8.3 Deferred High-Risk Features
The following capabilities represent severe security risks and are **STRICTLY DEFERRED** from initial PTM phases. Each requires a dedicated, independently reviewed threat model:
1. **Platform Admin Impersonation** (logging into a tenant as a tenant owner/user).
2. **Cross-Tenant Session Switching** (hot-swapping tenant context within an active session).
3. **Direct Password Mutation / Management** from Platform Admin.
4. **Bulk Tenant Mutation** (batch updates across multiple businesses).
5. **Automated Tenant Deletion** (hard deletion of tenant DynamoDB data).
6. **Automated Production Fixture Generation**.

---

## 9. Phased Implementation Backlog (PTM-0 through PTM-12)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 PLATFORM TENANT MANAGEMENT PHASED ROADMAP                   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
   P0: Core Control Plane              │  PTM-0: Architecture & Source-of-Truth
   (Prerequisites for Tenant #2)       │  PTM-1: Read-Only Tenant Directory
                                       │  PTM-2: Read-Only Tenant Details View
                                       │  PTM-4: User & Role Membership Vis.
                                       │  PTM-5: Subscription & Entitlement Vis.
                                       │
   P1: Extended Governance             │  PTM-3: Routing & Domain Visibility
                                       │  PTM-3B: Read-Only Branding Visibility
                                       │  PTM-3C: Tenant-Aware Mobile Presentation
                                       │  PTM-3D: Tenant-Aware Web Presentation
                                       │  PTM-3E: Cross-Platform Presentation Validation
                                       │  PTM-6: Onboarding Orchestrator Integr.
                                       │  PTM-7: Enhanced Platform Audit History
                                       │
   P2: Controlled Mutations            │  PTM-8: Controlled Tenant Creation (Gated)
   (Separately Approval-Gated)         │  PTM-9: Lifecycle Mutation (Suspend/Restore)
                                       │  PTM-9B: Controlled Branding Mutations
                                       │  PTM-10: Generated Tenant Subdomains
                                       │  PTM-11: Custom Business Domains
                                       │  PTM-12: Enterprise SSO & IdP Extensions
                                       │  PTM-13: White-Label Mobile Exception Model
```

### Phase Details

#### `PTM-0`: Architecture & Source-of-Truth Reconciliation (P0 — Complete in Specification)
* **Goal:** Establish formal control-plane architecture, document 5-way tenant authorization model, Cognito identity vs. role group rules, define lifecycle states, and reconcile existing platform handlers.
* **Deliverable:** `docs/planning/platform-tenant-management-control-plane.md`.

#### `PTM-1`: Read-Only Tenant Directory Enhancement (P0 — Prerequisite for Customer Tenant #2)
* **Goal:** Extend `GET /platform/tenants` and `PlatformAdmin.jsx` to render complete tenant metadata (slug, lifecycle state, owner count, staff count, routing status).
* **Scope:** Read-only backend query expansion, UI table/card enhancements, search/filter refinements.

#### `PTM-2`: Read-Only Tenant Details View (P0 — Prerequisite for Customer Tenant #2)
* **Goal:** Upgrade `PlatformTenantDetail.jsx` and `_handle_get_tenant` into the 8-section detail layout (Overview, Routing, Owners/Users, Subscriptions, Onboarding, Health, Audit, Presentation & Branding).
* **Scope:** Aggregated read-only metadata rendering; zero write operations.

#### `PTM-3`: Routing & Domain Visibility (P1)
* **Goal:** Display tenant route slug mapping, generated subdomain status, custom domain verification state, and DNS health in Platform Admin.
* **Scope:** Read-only DNS/route status reporting; no DNS provisioning. (Does not block customer tenant #2 while route-based tenancy remains canonical).

#### `PTM-3B`: Read-Only Tenant Branding & Presentation Visibility (P1)
* **Goal:** Display tenant presentation and branding attributes (`display_name`, `brand_color`, `logo_url`, `support_email`, `portal_theme`, `intake_config_status`) in Platform Admin Tenant Details View.
* **Scope:** Read-only presentation metadata query and UI section rendering; zero write operations.

#### `PTM-3C`: Tenant-Aware Mobile Presentation Model (P1 — Cross-Platform Specification)
* **Goal:** Extend tenant presentation architecture so that Web and Mobile share a canonical server-authoritative presentation metadata contract (`docs/planning/tenant-aware-mobile-presentation-architecture.md`) without fragmenting the single shared Expo/React Native mobile app build.
* **Scope:** Cross-platform presentation specification, dynamic mobile bootstrap, stale-state session clearing rules, and push notification display rules.

#### `PTM-3D`: Tenant-Aware Web Presentation Implementation (P1 — Web Implementation)
* **Goal:** Implement dynamic, server-authoritative Web UI presentation for configured non-default tenants across client portals, staff portals, intake forms, email headers, and navigation shells while preserving a single shared React/Vite application.
* **Scope:** Dynamic title, logo, favicon, theme palette (`brand_color`), intake terminology, booking labels, and support links; fallback to platform defaults if unconfigured.

#### `PTM-3E`: Cross-Platform Presentation Isolation Validation (P1 — Validation Suite)
* **Goal:** Establish formal Web + Mobile presentation acceptance matrix and stale-state verification procedures ensuring logout, account switching, auth failure, and tenant suspension purge all cached branding assets and operational data without visual artifact retention.
* **Scope:** Automated test suite additions and manual cross-platform validation runbooks.

#### `PTM-4`: User & Role Membership Visibility (P0 — Prerequisite for Customer Tenant #2)
* **Goal:** Provide a sanitized view of users associated with a tenant by querying Cognito users with `custom:company_id == tenant_id`.
* **Scope:** Read-only listing of users, identity states (`CONFIRMED` / `FORCE_CHANGE_PASSWORD`), and assigned role groups (`owner`, `admin`, `staff`, `client`).

#### `PTM-5`: Subscription & Entitlement Visibility (P0 — Prerequisite for Customer Tenant #2)
* **Goal:** Display real-time entitlement metrics (active clients, monthly bookings, staff seats) against plan tier limits, including administrative override expiration indicators.
* **Scope:** Read-only usage calculation dashboard.

#### `PTM-6`: Onboarding Orchestrator Integration (P1)
* **Goal:** Connect `PlatformAdminOnboarding.jsx` preview UI to the Tenant Directory with structured transition from preview to approval checklist.
* **Scope:** Read-only onboarding workflow UI integration; creation step remains gated.

#### `PTM-7`: Enhanced Platform Audit History (P1)
* **Goal:** Add search, filtering by target tenant, filtering by actor, and date range selection to `PlatformAuditLog.jsx`.
* **Scope:** Backend query parameters and UI filter controls for `GET /platform/audit`.

#### `PTM-8`: Controlled Tenant Creation (P2 — Gated)
* **Goal:** Implement governed backend tenant creation endpoint `POST /platform/tenants` with strict schema validation, metadata initialization, and audit logging.
* **Scope:** Approval-gated backend write handler. Requires explicit Matthew approval per tenant.

#### `PTM-9`: Controlled Tenant Lifecycle Mutations (P2 — Gated)
* **Goal:** Formalize tenant activation, suspension (`SUSPENDED`), and restoration endpoints with entitlement cache invalidation and event auditing.
* **Scope:** Backend lifecycle state transition handler.

#### `PTM-9B`: Controlled Tenant Branding & Presentation Mutations (P2 — Gated)
* **Goal:** Implement governed administrative backend endpoint (`PATCH /platform/tenants/{id}/branding`) allowing Platform Admins to update tenant brand name, primary/accent theme colors, logo URLs, support email, and intake form settings with strict schema validation, cache invalidation, and audit logging.
* **Scope:** Approval-gated backend branding mutation handler. Requires explicit Matthew approval per tenant.

#### `PTM-10`: Generated Tenant Subdomains (P2 — Deferred Infrastructure)
* **Goal:** Automate generation and routing of `<tenant-slug>.toganddogs.usmissionhero.com` subdomains via Route53/CloudFront wildcard infrastructure (DOMAIN-3).
* **Hostname Rule:** Generated tenant subdomains MUST use the **DNS-safe hyphenated tenant route slug** (`test-tenant-alpha`), e.g., `test-tenant-alpha.toganddogs.usmissionhero.com`. They must **NEVER** use the canonical underscored tenant ID (`test_tenant_alpha`), because underscores (`_`) are invalid characters in DNS hostname labels under RFC 1123 / RFC 952.
* **Scope:** Infrastructure automation (requires separate RFC).

#### `PTM-11`: Custom Business Domains (P2 — Deferred Infrastructure)
* **Goal:** Support verified custom domain onboarding (e.g., `booking.citypetcare.com`) with ACM certificate issuance and domain verification.
* **Scope:** Advanced domain management (requires separate RFC).

#### `PTM-12`: Enterprise SSO & IdP Extensions (P2 — Deferred Enterprise)
* **Goal:** Support dedicated Cognito app clients, SAML 2.0 / OIDC enterprise identity providers, and custom OAuth callback configurations for enterprise tenants.
* **Scope:** Enterprise authentication architecture.

#### `PTM-13`: White-Label Mobile Exception Model (P2 — Deferred Enterprise Exception)
* **Goal:** Support an explicit governance framework for creating dedicated enterprise white-label mobile app builds, dedicated APNs/FCM credentials, and standalone App Store / Play Store listings for qualified enterprise contracts.
* **Scope:** Enterprise white-label mobile exception framework (requires separate RFC and explicit approval).

---

## 10. Release Gating and Customer Tenant #2 Policy

```
================================================================================
CRITICAL POLICY DIRECTIVE: SECOND CUSTOMER TENANT THREE-TIERED APPROVAL GATE
================================================================================
```

1. **Internal Validation Tenant Scope:**
   `test_tenant_alpha` is an internal validation tenant created for system isolation testing. It does **NOT** constitute approval or precedent for onboarding a second real customer business. It remains fully authorized for the controlled DOMAIN-1 / ROUTE-GATE-C / B1A validation sequence.
2. **Three-Tiered Readiness Gate:**
   * **Tier 1: Internal Provisioning & Admin Validation Gate (`PTM-0`, `PTM-1`, `PTM-2`, `PTM-4`, `PTM-5`):**
     Required BEFORE creation, provisioning, or staging setup of a **second real / customer business tenant record**. (Note: `test_tenant_alpha` is the existing internal validation tenant and remains fully authorized for controlled testing; Tier 1 does not retroactively block `test_tenant_alpha`). Platform Admin must centrally answer: (1) Which tenants exist & active lifecycle state (`PTM-1`, `PTM-2`), (2) Route/identity health (`PTM-0`, `PTM-2`), (3) Users and assigned role groups (`PTM-4`), and (4) Subscription tier and entitlement limits (`PTM-5`).
   * **Tier 2: Customer Web End-User Access Gate (Tier 1 + `PTM-3B` + `PTM-3D` + `PTM-3E`):**
     Required BEFORE real customer end-users (owners, sitters, pet parents) are granted access to production Web portals. Ensures customer end-users encounter tenant-branded Web presentation rather than unbranded platform defaults. `PTM-9B` (Controlled Branding Mutations) is NOT a launch blocker, as branding can initially be established during governed provisioning.
   * **Tier 3: Customer Mobile End-User Access Gate (Tier 2 + `PTM-3C` + `PTM-3E`):**
     Required IF and when mobile application access is offered to that customer's end-users. Ensures mobile users encounter tenant-branded mobile presentation with validated session safety.
3. **Approval Requirement:**
   Onboarding any additional customer tenant requires explicit, separate approval from Matthew, alongside verified product tier pricing, subscription terms, and operational readiness.

---

## 11. Workflow Relationship, Execution Path, and DOMAIN-1 Gate Status

* **Parallel Workstream Guarantee:**
  This Platform Tenant Management workstream is a parallel SaaS maturity planning task. It does **NOT** alter, delay, or interrupt the current operational critical path.
* **Current Operational Status:**
  * **ROUTE-GATE-A (Backend tenant routing):** **COMPLETE & DEPLOYED** (state 513).
  * **ROUTE-GATE-B (Web tenant routing v2):** **COMPLETE & DEPLOYED** (web artifact `440cab2` / `index-BpY_nxft.js`).
  * **Credential Recovery Gate:** **COMPLETE & DEPLOYED** (Matthew completed live Cognito recovery).
  * **ROUTE-GATE-C (Authenticated tenant owner login validation):** **COMPLETE & VALIDATED** (100% PASS on 2026-08-26; zero primary-tenant data leaks).
  * **PTM-3D (Tenant-Aware Web Presentation Implementation):** **IMPLEMENTED & VALIDATED LOCALLY** (`web/src/utils/tenantPresentation.js` + dynamic document.title + unit tests 321/321 pass; NOT DEPLOYED).
  * **B1A (Tenant-scoped booking & scheduling):** **SEPARATELY APPROVAL-GATED / NOT STARTED**.
* **Current Action Rule:**
  No gate action, login test, credential recovery execution, or production state modification is executed by this documentation task.

---

## 12. Verification and Integrity Check

* **Application / Runtime Code:** Unmodified (0 lines changed in `src/`, `web/`, `mobile/`, `shared/`, or `infra/`).
* **Production AWS Infrastructure:** Untouched.
* **Cognito / User Pools / App Clients:** Untouched.
* **DNS / Route53 / CloudFront:** Untouched.
* **Tenant Data / DynamoDB:** Untouched.

---

**End of Specification.**
