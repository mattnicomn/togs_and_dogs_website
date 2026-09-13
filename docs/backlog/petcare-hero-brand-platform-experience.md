# PetCare Hero — Brand, Platform Experience, and SaaS Frontend

**Status:** PLANNED (program/epic definition only — no implementation has occurred)
**Owner:** Matthew
**Priority:** Strategic (multi-business SaaS commercialization)
**Created:** 2026-09-12
**Type:** DOCUMENTATION / PLANNING ONLY
**Program ID:** `PCH` (PetCare Hero)

> This document is the canonical master tracker for the PetCare Hero initiative.
> Creating it is planning, not a software release. No frontend, backend,
> infrastructure, tenant, Stripe, mobile-distribution, or production change has
> been made. Every task below is PLANNED/APPROVAL-REQUIRED unless an existing
> cross-referenced item is already marked otherwise.

---

## 0. How this relates to existing work (read first)

PetCare Hero is a **branding/product-experience layer name** for the multi-business
SaaS platform. It does **not** replace or duplicate the existing platform/tenant
engineering program. The authoritative technical programs remain:

- Platform Tenant Management Control Plane — `docs/planning/platform-tenant-management-control-plane.md` (PTM-0..PTM-13)
- SaaS maturity / multi-business readiness — `docs/backlog/saas-maturity-and-multi-business-owner-readiness.md`
- Tenant access / control-plane URL architecture — `docs/planning/tenant-access-client-onboarding-operational-workflow-alignment.md` (DOMAIN-1..7)
- Tenant-aware mobile presentation — `docs/planning/tenant-aware-mobile-presentation-architecture.md`
- Cross-platform design system — `docs/planning/phase-24a-cross-platform-design-system-and-mobile-workflow-alignment.md`

PetCare Hero tasks **reference and depend on** those programs; they must not
re-specify or fork them. Where a requirement is already tracked (PTM, DOMAIN,
Phase 24A, SaaS backlog items), the PCH task cross-references it rather than
creating a competing item.

---

## 1. Vision

PetCare Hero is the canonical working name for the multi-business pet-care SaaS
platform operated by **USMISSIONHERO LLC**. The vision is a platform where many
independent pet-care businesses (each an isolated tenant) run their operations —
clients, pets, staff, scheduling, requests, notifications, integrations, and
billing — under their **own** brand, while the platform provides a coherent,
accessible, secure product experience and a neutral platform surface where no
tenant brand applies.

PetCare Hero success is defined by tenant isolation, authoritative tenant
resolution, self-service maturity, and neutral-vs-tenant brand correctness — not
by the existence of a polished frontend alone.

---

## 2. Brand hierarchy (canonical)

```
USMISSIONHERO LLC            (company / operator)
  └── PetCare Hero           (SaaS platform / product)
        └── individual pet-care businesses / tenants
              └── Togs & Dogs (first / current tenant brand)
```

Canonical terminology:

| Term | Meaning |
|------|---------|
| **USMISSIONHERO LLC** | Company / operator / legal entity |
| **PetCare Hero** | SaaS platform / product name |
| **Togs & Dogs** | Existing independent tenant/business brand (Ryan's business) |
| **Pet Hero** | Optional shorthand / marketing phrase ONLY; NOT a second canonical platform name unless Matthew explicitly approves that change later |

Rules:

- **Do NOT rename Togs & Dogs to PetCare Hero.** Togs & Dogs is a tenant, not the platform.
- PetCare Hero branding must **never overwrite** a tenant's own customer-facing brand where tenant branding should control the experience.
- The platform must support future businesses with entirely different names, logos, colors, contact info, staff, clients, services, and configuration.
- This extends (does not replace) the existing **BUSINESS / BRAND OWNERSHIP BOUNDARY** invariant in `docs/project-continuity/guardrails.md`: Togs & Dogs is a tenant; USMISSIONHERO LLC is the operator; PetCare Hero is the product/platform brand layer between them.

---

## 3. Castle / Kingdom internal architecture glossary

These are **product/architecture-development terms only**. They are conceptual and
must **not** trigger renames of runtime resources, APIs, DynamoDB keys, IAM/Terraform
resources, Lambda functions, environment variables, or existing contracts. Canonical
technical identifiers remain stable unless a separately reviewed implementation task
explicitly determines a rename is safe and valuable.

| Friendly name | Friendly meaning | Technical responsibility (existing/authoritative) |
|---|---|---|
| **The Castle** | Overall PetCare Hero platform architecture | The whole multi-tenant SaaS system (all programs above) |
| **The Keep** | Platform/operator control plane | Platform Admin control-plane (PTM control plane; `/platform-admin`, `/platform/*`) |
| **The Gatehouse** | Authentication + tenant resolution | Establishes authenticated identity, determines authoritative tenant context, prevents tenant spoofing/fallback (Cognito authorizer + strict `TENANT_RESOLUTION_MODE=multi` resolver + DOMAIN-1 route bridge) |
| **The Realm** | An individual tenant/business | A tenant `COMPANY#<company_id>` operational space (e.g. `tog_and_dogs`, `test_tenant_alpha`) |
| **The Vault** | Secrets / configuration | Secrets Manager provider tokens, ownership-bound `calendar_secret_ref`, config; never exposes raw secrets |
| **The Registry** | Tenant metadata | `TENANT#<company_id>/METADATA` records, slug/registry, lifecycle/plan/branding metadata |
| **The Watchtower** | Monitoring / auditing | CloudWatch observability, platform audit trail, tenant-isolation/security events |
| **The Herald** | Notifications / messaging | Notification service (Postmark = approved production email provider), templates, delivery status |
| **The Marketplace** | Future integrations | Google Calendar (existing) + future integration catalog with tenant-safe credential ownership |
| **The Crown** | Platform-owner administrative authority | `platform_admin` control-plane authority; distinct from tenant-owner authority |

Conceptual tree (terminology only — do not modify infrastructure to reproduce it):

```
USMISSIONHERO LLC
  └── PetCare Hero
        └── The Castle
              ├── The Keep            (platform/operator management)
              │     ├── The Gatehouse (auth + authoritative tenant resolution)
              │     ├── The Registry  (tenant metadata)
              │     ├── The Vault      (secrets/configuration)
              │     ├── The Watchtower (monitoring/auditing)
              │     ├── The Herald     (notifications/messaging)
              │     ├── The Marketplace(integrations)
              │     └── The Crown      (platform-owner authority)
              └── Realms
                    ├── Togs & Dogs
                    ├── test_tenant_alpha (internal validation tenant)
                    └── future independently branded pet-care businesses
```

---

## 4. Program phases / workstreams (IDs)

Program ID `PCH`. Workstreams `PCH-A` … `PCH-R`. Each workstream lists its tasks
`PCH-<letter><n>`. All are PLANNED unless a cross-referenced existing item is
already delivered.

| Workstream | Title | Domain | Priority | Primary dependencies |
|---|---|---|---|---|
| PCH-A | Brand Foundation | Docs/Brand | P1 | — |
| PCH-B | Design System | Frontend (web+mobile) | P1 | PCH-A; extends Phase 24A design tokens |
| PCH-C | Public PetCare Hero Website | Frontend (web) | P2 | PCH-A, PCH-B; brand approval |
| PCH-D | Platform Application Shell (neutral) | Frontend (web+mobile) | P1 | PCH-B; PTM-3D.1; strict tenant resolution |
| PCH-E | The Keep (operator control plane UI) | Frontend (web) | P2 | PCH-D; PTM-1/2/4/5/6/7; The Crown/RBAC |
| PCH-F | The Realm (tenant owner/admin UX) | Frontend (web+mobile) | P2 | PCH-D; existing admin/tenant features |
| PCH-G | The Gatehouse (auth/resolution UX) | Frontend + UX | P1 | Gatehouse security model (unchanged); DOMAIN-1 |
| PCH-H | The Registry (tenant metadata UX) | Frontend | P2 | PCH-E; PTM-1/2/3B; safe-vs-secret split |
| PCH-I | The Vault (secrets/config UX) | Frontend + Arch | P2 | PCH-E/PCH-F; provider ownership (S2A.3/S2B) |
| PCH-J | The Watchtower (observability UX) | Frontend | P2 | PCH-E; CloudWatch/audit; PTM-7 |
| PCH-K | The Herald (notifications UX) | Frontend + Arch | P2 | Notification service; Postmark |
| PCH-L | The Marketplace (integrations) | Cross-cutting | P3 | Google Calendar (existing); tenant-safe credentials |
| PCH-M | Mobile PetCare Hero Experience | Mobile | P2 | tenant-aware mobile presentation arch; PTM-3C |
| PCH-N | Tenant Onboarding Experience | Cross-cutting | P2 | Preview V1; PTM-6/8; onboarding gates |
| PCH-O | Billing / Commercial Experience | Frontend + Billing | P2 | EIN + Stripe live (BLOCKED); entitlements |
| PCH-P | Documentation / Help / Customer Success | Docs | P2 | business-owner Getting Started (existing) |
| PCH-Q | Quality / Acceptance | Cross-cutting | P1 | all above; tenant-isolation priority |
| PCH-R | Commercial Launch Readiness | Program gate | P3 | ALL prerequisites + Matthew approval |

---

## 5. Workstream tasks

Status legend: PLANNED / ACTIVE / READY / BLOCKED / DEFERRED / APPROVAL REQUIRED / COMPLETE.
"Prod impact" = whether eventual implementation touches production.

### PCH-A — Brand Foundation (Docs/Brand, P1, PLANNED)
- PCH-A1 Canonical PetCare Hero naming + brand hierarchy (this doc §2) — PLANNED
- PCH-A2 Relationship to USMISSIONHERO LLC and to Togs & Dogs; tenant-brand vs platform-brand boundaries — PLANNED
- PCH-A3 "Pet Hero" shorthand policy (marketing shorthand only; not canonical) — PLANNED
- PCH-A4 Brand voice, positioning statement, elevator pitch, target-audience definition — PLANNED
- PCH-A5 Tagline exploration — PLANNED
- PCH-A6 Visual identity direction: typography, color system, iconography — PLANNED (extends PCH-B tokens)
- PCH-A7 Logo, favicon, app-icon requirements — PLANNED
- PCH-A8 Imagery/illustration direction — PLANNED
- PCH-A9 Accessible color-contrast requirements (WCAG); light/dark mode considerations — PLANNED
- PCH-A10 Co-branding rules, "Powered by PetCare Hero" policy (if adopted), white-label + tenant-customization boundaries, future enterprise/co-branding — PLANNED
- PCH-A11 Formal brand-name validation BEFORE commercial adoption: trademark/conflict research, domain availability, social handles, Apple App Store name conflicts, Google Play name conflicts, existing pet-care/software competitor scan — PLANNED / APPROVAL REQUIRED (no registrations/purchases in this workstream)

Acceptance (PCH-A): brand hierarchy documented and consistent with the guardrails
ownership invariant; PetCare Hero never overwrites tenant brand; name validation
completed and reviewed before any commercial/public adoption.

### PCH-B — Design System (Frontend web+mobile, P1, PLANNED)
- PCH-B0 **Inventory-first**: catalog reusable components/tokens already present in React/Vite (`web/src/generated/color-tokens.css`, existing admin/global CSS design system) and Expo/React Native (`mobile/src/theme/generatedColors.ts`), and the shared token contract from **Phase 24A-1A** (`docs/release-notes/phase-24a-1a-shared-token-contract.md`, `shared/tokens/`). Do not duplicate. — PLANNED
- PCH-B1 Design tokens: semantic colors, typography scale, spacing, borders, radius, elevation/shadows — PLANNED (extend Phase 24A tokens)
- PCH-B2 Layout: responsive breakpoints, grid/layout rules — PLANNED
- PCH-B3 Controls: buttons, inputs, selects, textareas, checkboxes/radios, toggles — PLANNED
- PCH-B4 Navigation: nav, tabs, breadcrumbs, pagination, search/filter controls, mobile nav, desktop nav — PLANNED
- PCH-B5 Data display: tables, cards, badges, charts/metrics presentation — PLANNED
- PCH-B6 Overlays: dialogs, drawers, alerts, banners, toasts — PLANNED
- PCH-B7 System states: empty, loading, skeletons, error, permission-denied, tenant-not-found, service-unavailable — PLANNED
- PCH-B8 Forms + validation feedback — PLANNED
- PCH-B9 Accessibility patterns + WCAG acceptance criteria (keyboard nav, screen-reader semantics, contrast) — PLANNED

Acceptance (PCH-B): reusable components inventoried before new ones are built;
WCAG AA contrast and keyboard/screen-reader semantics met; web/mobile parity where
applicable; no unnecessary duplication of existing components.

### PCH-C — Public PetCare Hero Website (Frontend web, P2, PLANNED)
- PCH-C1 Marketing pages: Home, Product/Platform, Features, Who It's For, Pet Sitters, Dog Walkers, Boarding/Daycare (only if in product scope), How It Works — PLANNED
- PCH-C2 Pricing page (placeholder/strategy only; **do not publish unapproved pricing**) — PLANNED / APPROVAL REQUIRED
- PCH-C3 Integrations, Security/Trust, About, Contact, Request Demo — PLANNED
- PCH-C4 Login, Start/Get Started, Help/Support entry points — PLANNED (auth via PCH-G)
- PCH-C5 Legal: Privacy, Terms, Accessibility; Status link/strategy only if later justified — PLANNED
- PCH-C6 SEO/frontend: titles, descriptions, OpenGraph, social cards, canonical URLs, sitemap, robots, structured data where appropriate, performance/Core Web Vitals, responsive behavior, accessible semantic HTML — PLANNED

Acceptance (PCH-C): no unapproved pricing published; no paid Stripe activation; SEO
+ Core Web Vitals + accessibility criteria met; responsive.

### PCH-D — Platform Application Shell / neutral presentation (Frontend web+mobile, P1, PLANNED)
Builds on **PTM-3D.1 Neutral Platform Presentation Boundary** (`NEUTRAL_PLATFORM_PRESENTATION`, `web/src/utils/tenantPresentation.js`).
- PCH-D1 Neutral loading screen, neutral login, logout, expired session — PLANNED
- PCH-D2 Invalid tenant, unauthorized, forbidden, service-unavailable, platform-level errors, maintenance state — PLANNED
- PCH-D3 Account recovery, support/contact surfaces — PLANNED (web recovery already deployed; reference)
- PCH-D4 Platform navigation, footer, legal links — PLANNED
- PCH-D5 Tenant discovery/selection surface — DEFERRED / APPROVAL REQUIRED (only if ever approved; must not weaken tenant resolution)

Critical rule: never leak Togs & Dogs branding into a context where no authoritative
Togs & Dogs tenant has been established; do not weaken strict tenant resolution to
simplify presentation.

Acceptance (PCH-D): neutral surfaces show `NEUTRAL_PLATFORM_PRESENTATION`, never a
tenant brand, in unauthenticated/logout/invalid-tenant contexts; strict tenant
resolution unchanged.

### PCH-E — The Keep (operator control plane UI) (Frontend web, P2, PLANNED)
Cross-references PTM-1/2/4/5/6/7 (read-only visibility) and PTM-8/9/9B (mutations, approval-gated).
- PCH-E1 Platform dashboard; tenant/Realm inventory + status (PTM-1) — PLANNED
- PCH-E2 Tenant details / onboarding status / plan+entitlement overview / owner+account status / tenant health / integration status (PTM-2/5) — PLANNED
- PCH-E3 Support/admin notes (privacy-controlled); audit/event visibility (PTM-7) — PLANNED
- PCH-E4 Feature flags; lifecycle controls; suspension/reactivation concepts (PTM-9) — PLANNED / APPROVAL REQUIRED
- PCH-E5 Billing state visibility; platform announcements; platform configuration — PLANNED
- PCH-E6 Operator RBAC (The Crown), privileged-action confirmation, audit trails — PLANNED
- PCH-E7 Safe impersonation/support concepts — DEFERRED / APPROVAL REQUIRED (only if separately approved)

Rule: do not implement operator mutation now unless separately authorized. The Crown
(platform-owner authority) must not be conflated with tenant-owner authority.

### PCH-F — The Realm (tenant owner/admin UX) (Frontend web+mobile, P2, PLANNED)
Cross-references existing admin dashboard, client/staff/pet management (Phase 1B.*), scheduling/requests, Google Calendar, entitlements — reference, do not duplicate.
- PCH-F1 Business dashboard; business profile (logo, colors/branding, contact, locations/service area, timezone, business hours) — PLANNED (branding mutation gated: PTM-9B)
- PCH-F2 Booking rules, cancellation rules, services, pricing/configuration — PLANNED
- PCH-F3 Staff, roles/permissions, clients, pets, scheduling, requests, notifications — PLANNED (mostly existing; reference)
- PCH-F4 Integrations; billing/subscription visibility; entitlement/usage visibility — PLANNED
- PCH-F5 Audit/history where appropriate; settings; data-export concepts; business lifecycle/offboarding concepts — PLANNED

### PCH-G — The Gatehouse (auth/resolution UX) (Frontend + UX, P1, PLANNED)
Frontend/UX only — **security model unchanged**.
- PCH-G1 Login, signup/onboarding entry, password recovery (recovery already deployed; reference), invite acceptance — PLANNED
- PCH-G2 Tenant-aware authentication; platform-vs-tenant context; safe redirect behavior — PLANNED
- PCH-G3 OAuth connection UX, expired OAuth UX, authorization failures, cross-tenant denial behavior — PLANNED
- PCH-G4 Session expiration, tenant mismatch, EventBridge/non-HTTP identity distinctions where relevant to UX — PLANNED

Rule: the Gatehouse remains subordinate to strict authoritative tenant identity;
never reintroduce unsafe default-tenant fallback (see S2B strict-authority work).

### PCH-H — The Registry (tenant metadata UX) (Frontend, P2, PLANNED)
- PCH-H1 View/manage safe tenant metadata: tenant ID, display name, slug, branding, contact info, timezone, lifecycle/status, plan, entitlements, feature configuration, integration configuration metadata, onboarding state — PLANNED (mutations gated per PTM-9/9B)
- PCH-H2 Enforce safe-metadata-vs-secret separation: **no secret values in the Registry** (secrets live in The Vault) — PLANNED

### PCH-I — The Vault (secrets/config UX + arch) (Frontend + Arch, P2, PLANNED)
- PCH-I1 Provider connection state; secret-reference ownership (builds on S2A.3 ownership-bound `calendar_secret_ref`) — PLANNED
- PCH-I2 Credential rotation UX; reconnect flows; revoked/expired connection states — PLANNED
- PCH-I3 Least-privilege visibility; safe operator diagnostics — PLANNED
- PCH-I4 Never expose raw secrets/tokens/OAuth codes/JWTs/session data/tfvars/private data — PLANNED (invariant)

### PCH-J — The Watchtower (observability UX) (Frontend, P2, PLANNED)
- PCH-J1 System health, Realm health, integration health — PLANNED
- PCH-J2 Job failures, notification failures, authentication anomalies, audit events — PLANNED
- PCH-J3 Error rates, latency, usage, entitlement-limit events, operational alerts, tenant-isolation/security events — PLANNED
- PCH-J4 Separate platform-operator telemetry from tenant-owner reporting; a tenant must never see another Realm's data — PLANNED (invariant)

### PCH-K — The Herald (notifications UX) (Frontend + Arch, P2, PLANNED)
- PCH-K1 Channels: email (Postmark, existing), SMS (if supported later), push, in-app — PLANNED (no unselected provider assumed)
- PCH-K2 Templates, tenant branding, notification preferences, delivery status, failures/retries, quiet hours — PLANNED
- PCH-K3 Owner/staff/client notification distinctions; platform-vs-Realm communications — PLANNED

### PCH-L — The Marketplace (integrations) (Cross-cutting, P3, PLANNED)
- PCH-L1 Integration catalog + categories: Google Calendar (existing — reference 21H/S2A.3/S2B, do not recreate), accounting, payment/billing, communications, mapping, CRM, payroll/workforce, pet-care ecosystem, AI capabilities — PLANNED
- PCH-L2 Tenant-safe credential ownership for every future integration (The Vault ownership model) — PLANNED (invariant)

### PCH-M — Mobile PetCare Hero Experience (Mobile, P2, PLANNED)
Cross-references `docs/planning/tenant-aware-mobile-presentation-architecture.md` (PTM-3C) and Phase 24A. Preserve the single shared Expo/React Native app (zero per-tenant builds).
- PCH-M1 PetCare Hero platform identity + tenant-aware presentation (tenant logo/colors); neutral auth/loading/error surfaces — PLANNED
- PCH-M2 App icon/name strategy; deep links; push notifications — PLANNED (no distribution change)
- PCH-M3 Owner/staff/client role experiences; accessibility — PLANNED
- PCH-M4 Tenant switching — DEFERRED / APPROVAL REQUIRED (only if later authorized)
- PCH-M5 White-label mobile — DEFERRED / APPROVAL REQUIRED (enterprise exception; PTM-13)

IMPORTANT: the mobile app is not publicly available. No App Store, TestFlight,
Google Play, tester, build, or distribution changes. Public publishing deferred
until Matthew explicitly approves.

### PCH-N — Tenant Onboarding Experience (Cross-cutting, P2, PLANNED)
Cross-references Preview V1 onboarding orchestrator, PTM-6 (orchestrator integration), PTM-8 (controlled creation, approval-gated), and SaaS backlog onboarding items.
- PCH-N1 Onboarding flow: create business/account, establish owner, establish Realm identity, business info, branding, service configuration, staff setup, integrations, billing/plan selection — PLANNED / provisioning APPROVAL REQUIRED
- PCH-N2 Training/getting-started, readiness checklist, launch checklist — PLANNED
Rule: do not create a second real tenant; provisioning/write-capable onboarding remains separately gated.

### PCH-O — Billing / Commercial Experience (Frontend + Billing, P2, PLANNED/BLOCKED)
Cross-references SaaS backlog billing items (EIN + Stripe live are BLOCKED).
- PCH-O1 Plans, feature comparison, trials (if approved), subscription state — PLANNED
- PCH-O2 Invoices/receipts, payment-method management, usage/limits — PLANNED
- PCH-O3 Upgrade/downgrade, cancellation, failed payment, grace periods, entitlements, plan-enforcement UX — PLANNED
Rule: Stripe remains sandbox-only unless Matthew explicitly authorizes live work; no live Stripe, no production billing data.

### PCH-P — Documentation / Help / Customer Success (Docs, P2, PLANNED)
Cross-references existing business-owner Getting Started (`docs/operations/business-owner-getting-started.md`) — extend, do not duplicate.
- PCH-P1 PetCare Hero Getting Started; business-owner guide; staff guide; client guide (where appropriate) — PLANNED
- PCH-P2 Onboarding checklist; integration guides; troubleshooting; FAQs — PLANNED
- PCH-P3 Security/trust documentation; support process; release notes; tenant-admin help; platform-admin runbooks; terminology/glossary — PLANNED

### PCH-Q — Quality / Acceptance (Cross-cutting, P1, PLANNED)
- PCH-Q1 Unit, component, integration, end-to-end tests — PLANNED
- PCH-Q2 Tenant-branding tests; neutral-presentation tests; **cross-tenant isolation tests**; RBAC tests — PLANNED
- PCH-Q3 Responsive; keyboard nav; screen-reader semantics; contrast/accessibility — PLANNED
- PCH-Q4 Error-state, loading-state tests; performance; SEO for public pages — PLANNED
- PCH-Q5 Mobile/web consistency; browser coverage; visual-regression strategy (if appropriate) — PLANNED
Critical acceptance principle: **Realm A must never display Realm B's private data or unauthorized configuration. Tenant isolation has priority over visual convenience.**

### PCH-R — Commercial Launch Readiness (Program gate, P3, PLANNED)
Dependent on earlier security/platform work; a frontend alone does not make PetCare Hero launch-ready.
- PCH-R1 Prerequisites: tenant-isolation acceptance; authoritative tenant resolution; onboarding maturity; neutral platform presentation; PetCare Hero brand approval; public website; business-owner UX; billing maturity; support documentation; monitoring; legal pages; backup/recovery maturity; operational runbooks; incident handling; commercial pricing approval; customer onboarding process; support/contact model — PLANNED / APPROVAL REQUIRED

---

## 6. Existing tasks cross-referenced (NOT duplicated)

| Requirement | Existing owner (authoritative) |
|---|---|
| Control-plane architecture, tenant authority model, lifecycle | PTM-0..PTM-2, PTM-4/5/7 |
| Neutral platform presentation boundary | PTM-3D.1 (`NEUTRAL_PLATFORM_PRESENTATION`) |
| Tenant-aware web presentation | PTM-3D (deployed) |
| Tenant-aware mobile presentation | PTM-3C / `tenant-aware-mobile-presentation-architecture.md` |
| Generated tenant subdomains / hostnames | PTM-10, DOMAIN-1..7 |
| Controlled tenant creation / lifecycle / branding mutation | PTM-6/8/9/9B (approval-gated) |
| Tenant onboarding orchestrator (Preview V1) | `release-platform-admin-tenant-onboarding-preview-v1.md`, PTM-6 |
| Strict tenant resolution / no default fallback | `TENANT_RESOLUTION_MODE=multi` (18T/18U); S2B strict HTTP authority |
| Google Calendar per-tenant token isolation / ownership | 21H, S2A.3, S2B (The Vault/Marketplace) |
| Design tokens / cross-platform components | Phase 24A-1A + `shared/tokens/`, generated web/mobile tokens |
| Business-owner Getting Started | `docs/operations/business-owner-getting-started.md` |
| Billing / Stripe / pricing / signup | SaaS backlog items (EIN + Stripe live BLOCKED) |
| Web password recovery | deployed (reference in PCH-D3/PCH-G1) |

---

## 7. Dependency model & critical path

Broad dependency order (refined against authoritative docs; the existing Tier-1/2/3
customer-tenant gate and PTM sequencing take precedence):

```
Current approved PTM / S2 acceptance work (F02 + PTM-0 remainder)
  → tenant authority / isolation hardening (S2B/S2C deployed; acceptance in progress)
  → neutral platform presentation boundary (PTM-3D.1)
  → PetCare Hero brand + design foundation (PCH-A, PCH-B)
  → PetCare Hero neutral application shell (PCH-D)
  → Realm owner experience (PCH-F) + Gatehouse UX (PCH-G)
  → Keep / operator experience (PCH-E) [+ PTM-1/2/4/5]
  → public marketing frontend (PCH-C)
  → onboarding / commercial UX (PCH-N, PCH-O) [gated: provisioning, EIN/Stripe]
  → controlled second-business readiness (Tier-1 PTM gate)
  → commercial launch readiness (PCH-R)
```

Relationship to existing sequencing: this does NOT reorder the PTM Tier-1/2/3 gate or
the DOMAIN-# host work. PetCare Hero branding/frontend is **not** the immediate next
engineering task; the tenant-hardening/acceptance critical path (F02, PTM-0 remainder,
S2 acceptance tiers) comes first.

---

## 8. Approval gates that remain in force

- Production changes require Matthew's explicit approval.
- `TENANT_RESOLUTION_MODE=multi` is ACTIVE and validated (18T/18U); do not change it without explicit approval.
- Stripe remains sandbox-only unless explicitly approved; no live Stripe / production billing data.
- Ryan testing remains paused unless explicitly approved.
- Do not create a second real tenant unless explicitly approved (only `tog_and_dogs` + internal `test_tenant_alpha` exist).
- No public App Store / TestFlight / Google Play distribution changes unless explicitly approved.
- No production test data unless explicitly approved.
- Do not weaken tenant isolation or tenant authority; no default-tenant fallback.
- Do not expose secrets/tokens/private auth data.
- No unrelated refactors; targeted git operations only (never `git add .`).

---

## 9. Deferred items

PCH-D5 (tenant discovery/selection), PCH-E7 (safe impersonation/support), PCH-M4
(tenant switching), PCH-M5 (white-label mobile / PTM-13), PCH-O trials/live billing
(EIN/Stripe), PCH-C2 published pricing, PCH-A11 registrations/purchases. Enterprise
SSO/white-label track PTM-12/PTM-13.

---

## 10. Definition of PetCare Hero commercial readiness

PetCare Hero is commercially launch-ready only when ALL hold:
1. Tenant isolation acceptance passed (cross-tenant leakage impossible; PCH-Q2).
2. Authoritative tenant resolution enforced (no default fallback; Gatehouse).
3. Onboarding maturity (governed, reviewed provisioning; PCH-N + PTM-8).
4. Neutral platform presentation correct (PTM-3D.1 / PCH-D).
5. PetCare Hero brand approved (PCH-A incl. name validation).
6. Public website live (PCH-C).
7. Business-owner UX complete (PCH-F).
8. Billing maturity (PCH-O; EIN + Stripe live unblocked and approved).
9. Support documentation (PCH-P).
10. Monitoring (PCH-J / Watchtower).
11. Legal pages (PCH-C5).
12. Backup/recovery maturity, operational runbooks, incident handling.
13. Commercial pricing approved; customer onboarding + support/contact model defined.
14. Tier-1/2/3 PTM customer-tenant gates satisfied.

A frontend existing is NOT sufficient. This document is planning only; nothing here
asserts implementation has occurred.
