# Tenant-Aware Mobile Presentation Architecture and Cross-Platform Branding Model

**Document Version:** 1.0.0  
**Status:** Approved Architectural Specification / Implementation Deferred  
**Owner:** Matthew / Platform Engineering  
**Created:** 2026-08-25  
**Authoritative Reference:** `docs/planning/tenant-aware-mobile-presentation-architecture.md`  

---

## 1. Executive Summary & Alpha Validation Finding

During Alpha validation of multi-tenant infrastructure, DOMAIN-1 successfully established backend tenant routing and data isolation (`5BD46E19...` Lambda package & `/t/:tenantSlug/admin` Web route bridge). However, validation revealed a key UX gap: authenticated presentation across Web and Mobile defaults to global Togs & Dogs branding in unconfigured areas such as client/staff portals, intake forms, notification headers, and mobile shells.

This issue is classified as a **PRESENTATION ISOLATION GAP** (a UX branding gap), **NOT** a proven data-isolation failure. Data isolation remains strictly enforced by server-side `custom:company_id` claims and database query predicates.

This specification establishes the formal **Tenant-Aware Mobile Presentation Architecture**, extending the Platform Tenant Management (PTM) control plane so that Web and Mobile share a single, coherent, server-authoritative presentation model without fragmenting mobile binary distribution or compromising security boundaries.

---

## 2. Mobile Architecture Rule: Default SaaS Shared App Model

```
================================================================================
MANDATORY MOBILE ARCHITECTURE PRINCIPLE: SINGLE SHARED APPLICATION BINARY
================================================================================
```

The platform mandates a single, multi-tenant mobile application architecture for all standard SaaS tenants.

### 2.1 Canonical Mobile Model
* **One Shared Mobile Application:** All standard business tenants, owners, admins, sitters, and pet owners operate within **one single Expo/React Native mobile application** distributed via Apple TestFlight / App Store and Google Play.
* **Runtime Multi-Tenancy:** Tenant identity, branding, navigation, and data scope are established dynamically at runtime post-authentication.

### 2.2 Forbidden Anti-Patterns (Default SaaS Model)
Do **NOT** create any of the following for standard SaaS tenants:
* ❌ One mobile repository per tenant
* ❌ One Expo project per tenant
* ❌ One bundle identifier / application ID per tenant (e.g., `com.toganddogs.tenantx`)
* ❌ One Apple App Store or Google Play Store listing per tenant
* ❌ One Cognito app client per tenant

Tenant authority and identity remain strictly server-authoritative via Cognito token claims (`custom:company_id`) and server-side tenant registry verification.

---

## 3. Tenant-Aware Mobile Bootstrap Sequence & Security Model

Mobile presentation components MUST NOT infer tenant access or data authority from client-side cached metadata alone. All tenant UI configurations are resolved via a strict, fail-closed bootstrap sequence.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   TENANT-AWARE MOBILE BOOTSTRAP SEQUENCE                   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
  1. Authenticated Identity  ────────► Cognito JWT (sub, email, custom:company_id)
                                       │
  2. Tenant Claim Check      ────────► Extract custom:company_id
                                       │
  3. Server Registry Lookup  ────────► GET /t/:tenantSlug/bootstrap
                                       │ (Server verifies tenant active state & slug)
                                       │
  4. Active Entitlement      ────────► Verify subscription_status & is_access_allowed
                                       │
  5. Role Authorization      ────────► Verify Cognito Role Group (owner/admin/staff/client)
                                       │
  6. Presentation Payload    ────────► Receive Canonical Presentation Metadata
                                       │ (display_name, brand_color, logo_url, etc.)
                                       │
  7. UI Render               ────────► Render Tenant Dashboard & Role Navigation
```

### Security Boundary Principles
* **Presentation Metadata is Non-Authoritative:** Receiving tenant branding metadata (e.g., `brand_name` or `logo_url`) grants **ZERO** data access authority.
* **Server-Side Enforcement:** Every subsequent API request from the mobile app attaches the Cognito JWT. Backend Lambda handlers independently enforce tenant isolation via `custom:company_id` and server-side role checks.
* **Fail-Closed Bootstrapping:** If tenant bootstrap returns `403 TenantDisabled`, `404 TenantNotFound`, or invalid claims, the mobile app MUST immediately clear operational context and display a sanitized suspension/error screen.

---

## 4. Shared Canonical Presentation Metadata Contract

To prevent divergence between Web and Mobile, the platform defines **one canonical presentation metadata payload** stored in the server-side tenant registry (`PK=TENANT#<id>`, `SK=METADATA`) and delivered via standard bootstrap endpoints.

```json
{
  "company_id": "test_tenant_alpha",
  "tenant_slug": "test-tenant-alpha",
  "display_name": "Alpha Pet Care",
  "brand_name": "Alpha Pet Care",
  "logo_url": "https://assets.toganddogs.com/tenants/test-tenant-alpha/logo.png",
  "mobile_logo_url": "https://assets.toganddogs.com/tenants/test-tenant-alpha/mobile-logo.png",
  "brand_color": "#1E3A8A",
  "secondary_color": "#3B82F6",
  "accent_color": "#F59E0B",
  "theme_mode": "light",
  "support_email": "support@alphapetcare.com",
  "support_phone": "+1-555-019-2831",
  "portal_title": "Alpha Pet Care Portal",
  "client_portal_label": "Pet Parent Portal",
  "staff_portal_label": "Sitter Portal",
  "intake_label": "New Client Onboarding",
  "intake_config": {
    "require_vet_info": true,
    "require_vaccine_records": true,
    "custom_notes_prompt": "Special feeding or medication instructions"
  },
  "notification_display_name": "Alpha Pet Care",
  "help_support_links": {
    "help_center": "https://alphapetcare.com/help",
    "contact_us": "https://alphapetcare.com/contact"
  },
  "terms_privacy_metadata": {
    "terms_url": "https://alphapetcare.com/terms",
    "privacy_url": "https://alphapetcare.com/privacy"
  }
}
```

---

## 5. Mobile Presentation Scope & UI Mapping

The mobile application dynamically applies presentation metadata across the following UI surfaces:

| Surface | Presentation Behavior |
|---------|-----------------------|
| **App Shell & Header** | Renders tenant `brand_name` or `mobile_logo_url` in top navigation bar; header background uses `brand_color`. |
| **Dashboard Cards** | Tappable summary cards adopt tenant accent colors; labels mirror `client_portal_label` / `staff_portal_label`. |
| **Request Care / Intake** | Intake forms display tenant-configured intake prompts (`intake_label`, `intake_config`). |
| **My Bookings** | Schedule items, status badges, and booking headers reflect tenant branding colors and display title. |
| **Staff / Sitter Portal** | Sitter visit execution screen displays tenant business name and support contact details. |
| **Buttons & Controls** | Primary action buttons (`Book Visit`, `Start Visit`, `Complete Visit`) use `brand_color`. |
| **Support Drawer** | Contact Us modal renders tenant `support_email`, `support_phone`, and `help_center` links. |
| **Profile & Settings** | Account screen displays active tenant business identity and legal terms links (`terms_url`, `privacy_url`). |
| **Loading & Error States** | Spinners, empty states, and offline notices use tenant primary branding with graceful platform fallback. |

---

## 6. Stale-State, Session Safety, and Cache Clearing Rules

To prevent cross-tenant data leaks or visual artifact contamination on shared devices:

1. **Logout Safety:** Executing logout MUST immediately purge all cached presentation metadata, JWT tokens, tenant state, and operational data from mobile local storage (`AsyncStorage` / Secure Store).
2. **Account / Context Switch:** Switching accounts or tenant contexts MUST purge prior presentation state before mounting the new dashboard.
3. **Auth Failure Cleanup:** Any unhandled 401/403 API response or session expiration MUST immediately clear tenant operational screens and redirect to the unauthenticated login boundary.
4. **Suspended Tenant Guard:** If tenant bootstrap returns `subscription_status = disabled` or `lifecycle_state = SUSPENDED`, the mobile app MUST purge operational data and display a sanitized status screen ("Account Suspended").
5. **App Cold Launch:** Every cold launch of the mobile app MUST re-validate session tokens and execute a fresh server bootstrap.

---

## 7. Mobile Navigation & Role Alignment

The mobile application navigation structure remains strictly role-driven while incorporating tenant-aware presentation:

* **Role Groups:** Functional navigation is governed by Cognito user pool groups (`client`, `staff`, `admin`, `owner`).
* **Platform Admin Exclusion:** The Platform Admin control plane (`/platform-admin/*`) is **STRICTLY EXCLUDED** from mobile app navigation. Mobile is reserved for operational tenant-plane workflows.
* **Role Views:**
  * `client` $\rightarrow$ Pet Parent Dashboard (Bookings, Pet Profiles, Request Care, Invoices).
  * `staff` $\rightarrow$ Sitter Visit Dashboard (Today's Visits, Route Map, Start/Complete Visit, Care Logs).
  * `owner` / `admin` $\rightarrow$ Business Operational Dashboard (Daily Overview, Sitter Schedule, Request Approvals).

---

## 8. Push Notification Branding Strategy

* **Default Shared App Model:**
  * Push notifications dispatched to the shared mobile app dynamically include the tenant display name in the notification title or body (e.g., *"Alpha Pet Care: Walker Jane has started your 30-min Dog Walk"*).
  * Backend notification dispatch handlers scope push tokens strictly by `custom:company_id`.
* **Credential Model:**
  * The default shared app uses one set of platform APNs (Apple) and FCM (Firebase/Android) push credentials.
  * Per-tenant APNs/FCM credentials are **NOT** used in the shared mobile app.

---

## 9. White-Label / Enterprise Exception Model

A dedicated, tenant-specific mobile app build and store listing is permitted **ONLY** under an approved Enterprise White-Label Exception.

### 9.1 Exception Criteria
An enterprise tenant may qualify for a dedicated white-label mobile app IF and ONLY IF all of the following criteria are met:
1. Contractual requirement for a dedicated Apple App Store and Google Play Store listing.
2. Requirement for custom native app icon, splash screen, and standalone bundle ID (`com.enterprisebusiness.app`).
3. Requirement for dedicated APNs/FCM push notification certificates.
4. Requirement for enterprise SAML 2.0 / OIDC IdP federation or dedicated OAuth client secrets.

### 9.2 Governance Rule
White-label mobile builds are **NOT** the default SaaS model. Creating a white-label app requires a dedicated RFC, explicit Matthew approval, and separate architecture, security, cost, release pipeline, and maintenance reviews.

---

## 10. Customer Tenant #2 Release Readiness & Gating Rules

To ensure operational safety while enabling efficient internal validation, the platform establishes a two-tiered readiness gate for real customer tenant #2:

```
================================================================================
CUSTOMER TENANT #2 TWO-TIERED READINESS GATE
================================================================================
```

### Tier 1: Internal Provisioning & Admin Validation Gate
* **Prerequisite Capabilities:** `PTM-0` (Architecture), `PTM-1` (Directory), `PTM-2` (Details), `PTM-4` (Users), `PTM-5` (Entitlements).
* **Scope:** Allows Platform Admins to provision, configure, and inspect a second tenant record internally in staging/production tools.
* **Status:** Requirement for internal provisioning of Tenant #2.

### Tier 2: Customer End-User Production Launch Gate
* **Prerequisite Capabilities:** Tier 1 + **`PTM-3B` (Read-Only Branding Visibility)** + **`PTM-3C` (Tenant-Aware Mobile Presentation)** + **`PTM-9B` (Gated Branding Mutations)**.
* **Scope:** Required BEFORE real customer end-users (owners, sitters, pet parents) are granted access to production Web or Mobile portals.
* **Rationale:** Prevents customer end-users from encountering unbranded or cross-branded UI surfaces during live operations.

---

## 11. Cross-Platform Acceptance Criteria Matrix

| Test Scenario | Web Expectation | Mobile Expectation | Expected Outcome |
|---------------|-----------------|--------------------|------------------|
| **Tenant A Session (`tog_and_dogs`)** | Displays "Togs & Dogs" header, logo, theme colors, and Tenant A data only. | Displays "Togs & Dogs" header, accent colors, and Tenant A schedule/pets only. | PASS |
| **Tenant B Session (`test_tenant_alpha`)** | Displays "Alpha Pet Care" header, logo, theme colors, and Tenant B data only. | Displays "Alpha Pet Care" header, accent colors, and Tenant B schedule/pets only. | PASS |
| **Logout Execution** | Purges Web session; redirects to `/admin` login. | Purges `AsyncStorage` presentation metadata; redirects to Auth login. | PASS — Zero stale branding/data |
| **Account Switch (A $\rightarrow$ B)** | Re-boots Web bootstrap; renders Tenant B presentation. | Re-boots Mobile bootstrap; renders Tenant B presentation. | PASS — Zero cross-contamination |
| **Auth Failure / Expired JWT** | Fails closed; clears operational UI. | Fails closed; clears operational UI. | PASS — No stale UI retained |

---

## 12. Recommended Phased Implementation Sequence

The platform recommends the following logical sequence for presentation and SaaS maturity implementation (**DOCUMENTATION ONLY — No execution authorized in this task**):

```
  1. Canonical Presentation Metadata Contract & Schema (PK=TENANT#<id>, SK=METADATA)
  2. Platform Admin Read-Only Branding Visibility (PTM-3B)
  3. Tenant-Aware Web Presentation Engine
  4. Tenant-Aware Mobile Presentation Engine (PTM-3C)
  5. Cross-Platform Isolation & Branding Validation Matrix
  6. Controlled Administrative Branding Mutations (PTM-9B)
  7. Generated Tenant Subdomains (PTM-10 using DNS-safe slug test-tenant-alpha)
  8. Enterprise White-Label Mobile Exception Framework (PTM-13)
```

---

## 13. Non-Interference Verification & App Store Guardrails

* **Application / Mobile Source Code:** Unmodified (0 lines changed in `web/`, `mobile/`, `src/`, `shared/`, or `infra/`).
* **Mobile Builds / Expo / EAS:** Untouched. No builds generated.
* **App Store / TestFlight / Google Play:** Untouched. No submissions or tester changes.
* **Cognito / AWS / DNS / Tenant Data:** Untouched.

---

**End of Specification.**
