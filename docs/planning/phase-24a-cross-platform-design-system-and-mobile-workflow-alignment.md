# Phase 24A: Cross-Platform Design System and Mobile Workflow Alignment

**Status:** 📋 PLANNING COMPLETE — Implementation not approved
**Date:** 2026-07-24
**Starting HEAD:** `2fbfba9`
**Depends on:** Phase 1B.5C-A deployment (for mobile pet editing)

---

## 1. Purpose

Make the React/Vite website and Expo/React Native mobile application feel like one coherent Togs & Dogs product by aligning shared design tokens, terminology, validation rules, API contracts, and workflow behavior — while preserving separate platform-specific presentation components.

**Not in scope:** React Native Web migration, website rewrite, EAS builds, mobile distribution, TestFlight changes, App Store submission, Ryan testing changes.

---

## 2. Current Technology Baseline

| Property | Web | Mobile |
|----------|-----|--------|
| Framework | React 19 (Vite) | React Native 0.81 (Expo 54) |
| Language | JavaScript (JSX) | TypeScript (TSX) |
| Styling | CSS custom properties + component CSS | React Native StyleSheet |
| Routing | React Router (createBrowserRouter) | React Navigation (stack + bottom tabs) |
| Auth | Cognito (amazon-cognito-identity-js, browser storage) | Cognito (amazon-cognito-identity-js, SecureStore) |
| API Client | `web/src/api/client.js` | `mobile/src/api/client.ts` |
| Config | Same API URL, same Cognito pool, same Client ID | Same values |
| State | Local component state (no global store) | Context + local state |
| Tests | Vitest + React Testing Library (209 passing) | None configured |
| Build | Vite production build | Expo EAS (not active) |

---

## 3. Design Token Comparison

### 3.1 Color Alignment

| Token | Web CSS Variable | Web Value | Mobile COLORS.* | Mobile Value | Aligned? |
|-------|-----------------|-----------|-----------------|--------------|----------|
| Primary | `--primary` | `#c28b1e` | `primary` | `#c28b1e` | ✅ Exact |
| Primary Hover | `--primary-hover` | `#f08c3a` | `primaryHover` | `#a37213` | ❌ Different |
| Background | `--page-bg` | `#faf7f2` | `background` | `#faf7f2` | ✅ Exact |
| Card | `--card-bg` | `#ffffff` | `cardBg` | `#ffffff` | ✅ Exact |
| Text | `--text-primary` | `#3c3c3b` | `text` | `#3c3c3b` | ✅ Exact |
| Text Muted | `--text-muted` | `#6a6a66` | `textMuted` | `#7f8c8d` | ❌ Different |
| Border | `--border-color` | `#e2dfd9` | `border` | `#e2e8f0` | ⚠️ Similar, not identical |
| Border Soft | `--border-soft` (alias) | `#e2dfd9` | `borderSoft` | `#edf2ee` | ❌ Different |
| Success | `--success-color` | `#4a7c59` | `success` | `#10b981` | ❌ Different (muted green vs emerald) |
| Warning/Danger | `--warning-color` | `#d64933` | `danger` | `#ef4444` | ❌ Different |
| Info | N/A (no explicit) | — | `info` | `#3b82f6` | N/A (mobile-only) |
| Secondary | `--secondary` | `#b8a890` | N/A | — | Web-only |
| Accent | `--accent` | `#e17c80` | N/A | — | Web-only |

### 3.2 Spacing, Radii, Typography

| Token | Web | Mobile | Status |
|-------|-----|--------|--------|
| Radius small | `--radius-sm: 10px` | Inline `8` or `12` | ⚠️ No shared standard |
| Radius medium | `--radius-md: 20px` | Inline `12` or `16` | ⚠️ No shared standard |
| Radius pill | `--radius-pill: 99px` | Inline `99` | ✅ Convention matches |
| Font family | System sans-serif stack | React Native system default | ✅ Acceptable platform difference |
| Base font size | 18px (16px mobile) | 14–16px body text | ⚠️ Scale differs slightly |
| Spacing scale | Not defined as tokens | Not defined as tokens | ❌ Both use ad-hoc values |

### 3.3 Status Colors (In-Use, Not Formalized)

| Status | Web (CSS / inline) | Mobile (inline) | Aligned? |
|--------|-------------------|-----------------|----------|
| Pending | Amber/gold inline | `#f59e0b` | ⚠️ Similar intent |
| Approved | Blue inline | `#3b82f6` | ⚠️ Similar intent |
| Assigned/Scheduled | Green inline | `#10b981` | ⚠️ Similar intent |
| Completed | Gray inline | `#6b7280` | ⚠️ Similar intent |
| Cancelled | Red inline | `#ef4444` | ⚠️ Similar intent |

---

## 4. Screen and Workflow Parity Matrix

| Workflow | Web | Mobile | Functionally Aligned | Visually Aligned | Disposition |
|----------|-----|--------|---------------------|-----------------|-------------|
| **Sign-in** | `/admin` login form in AdminDashboard | `LoginScreen` (dedicated) | ✅ Same Cognito flow | ⚠️ Different layout, same brand | Align copy/error messages |
| **Forgot password** | Not implemented on web | ✅ Full flow (send code + confirm) | ❌ Web lacks this | — | Add to web eventually |
| **Session refresh** | Browser session (auto via Cognito SDK) | SecureStore + silent refresh before API calls | ✅ Both maintain sessions | N/A | Mobile has better offline resilience |
| **Customer profile** | No dedicated profile screen | No profile screen | — | — | Future: both platforms |
| **My Pets (list)** | `/my-pets` — card list with edit | ❌ Not implemented | ❌ Missing on mobile | — | **Pilot target** |
| **Pet viewing** | Inline in My Pets cards | ❌ Not implemented | ❌ Missing on mobile | — | Part of My Pets pilot |
| **Pet editing** | Inline editor in My Pets (Phase 1B.5C-A) | ❌ Not implemented | ❌ Missing on mobile | — | Depends on 1B.5C-A deployment |
| **Care request intake** | `/book` — 4-step form | ❌ Not implemented | ❌ Missing on mobile | — | Second-stage pilot |
| **My Bookings** | `/my-bookings` (ClientPortal) | `BookingsScreen` | ✅ Both show client bookings | ⚠️ Layout differs (table vs cards) | Align status labels |
| **Request detail** | CareCard within AdminDashboard | `RequestDetailScreen` | ✅ Core actions match | ⚠️ Layout differs | Align action labels |
| **Request list (admin)** | Tab in AdminDashboard | `RequestListScreen` | ✅ Both filter by status | ⚠️ Different filter UX | Align filter labels |
| **Schedule view** | `MasterScheduler` in AdminDashboard | `ScheduleScreen` | ⚠️ Different granularity | ❌ Different approaches | Intentional: web is dispatcher view |
| **Staff dashboard** | Stats in AdminDashboard | `DashboardScreen` (mobile) | ✅ Same stat categories | ⚠️ Different layout | Align terminology |
| **Client management** | Full CRUD in AdminDashboard | ❌ Not implemented | — | — | Intentionally web-only |
| **Staff management** | Full CRUD in AdminDashboard | ❌ Not implemented | — | — | Intentionally web-only |
| **Platform admin** | `/platform-admin` (guarded) | ❌ Not implemented | — | — | Intentionally web-only |
| **Google Calendar** | Connect/disconnect/status in admin | ❌ Not implemented | — | — | Intentionally web-only |
| **Payment actions** | Payment session + email sending | ❌ Not implemented | — | — | Intentionally web-only (fat-finger risk) |
| **Export** | CSV download from admin | ❌ Not implemented | — | — | Intentionally web-only |
| **Dark mode** | ✅ ThemeToggle (CSS dark class) | ❌ Not implemented | ❌ Missing on mobile | — | Future: mobile dark mode |
| **Terms / Privacy** | `/terms`, `/privacy` | ❌ Not implemented (privacy URL in app.json) | — | — | Linked from app, rendered on web |

### 4.1 Intentionally Web-Only Features

- Client/staff CRUD management (complex forms, keyboard-heavy)
- Platform Admin console (multi-tenant governance)
- Google Calendar OAuth management
- Payment session creation and email sending
- Data export (file downloads)
- Full-page Terms/Privacy rendering

### 4.2 Features That Should Eventually Exist on Both

- My Pets (view + edit)
- Care request intake
- Dark mode / theme switching
- Forgot password (web currently lacks this)
- Push notifications (mobile has infra, web doesn't)

---

## 5. Shared Code Inventory (Current State)

| Category | Web | Mobile | Shared? |
|----------|-----|--------|---------|
| API base URL & config | `web/src/api/config.js` | `mobile/src/api/config.ts` | ❌ Duplicated (identical values) |
| API client functions | `web/src/api/client.js` (50+ functions) | `mobile/src/api/client.ts` (9 functions) | ❌ Duplicated subset |
| Auth logic | `web/src/api/auth.js` | `mobile/src/auth/cognito.ts` | ❌ Duplicated (different storage backends) |
| Role resolution | `getEffectiveRole()` in both | Same logic, both files | ❌ Duplicated |
| Color tokens | CSS variables in `index.css` | `mobile/src/theme/colors.ts` | ❌ Duplicated (partially misaligned) |
| Status labels | Inline in components | Inline in screens | ❌ Not shared |
| Pet field definitions | `web/src/utils/petHelpers.js` | N/A | Web-only |
| Client management utils | `web/src/utils/clientManagement.js` | N/A | Web-only (admin) |
| Service type labels | Inline | Inline | ❌ Not shared |
| Site content/branding | `web/src/config/siteContent.js` | N/A | Web-only |
| Type definitions | N/A (JavaScript) | `mobile/src/types/index.ts` | Mobile-only (TypeScript) |
| Validation schemas | Inline in IntakeForm | N/A | Web-only |

---

## 6. Recommended Design-System Structure

### 6.1 Approach: Shared Design Tokens + Contracts, Separate Presentation

Create a root-level `shared/` directory that both `web/` and `mobile/` can import from. This directory contains only platform-neutral data (JSON, TypeScript types, constant definitions) — never React DOM or React Native components.

```
shared/
├── tokens/
│   ├── colors.json          # Canonical color palette
│   ├── spacing.json         # Spacing scale (4, 8, 12, 16, 24, 32, 48)
│   ├── radii.json           # Border radius scale
│   └── typography.json      # Font size scale and weights
├── constants/
│   ├── statuses.ts          # Request status labels and colors
│   ├── services.ts          # Service type labels and metadata
│   ├── petFields.ts         # Pet field definitions and labels
│   └── errors.ts            # Shared error message templates
├── contracts/
│   ├── api-paths.ts         # API endpoint path constants
│   └── config.ts            # Shared config values (pool ID, region, API URL)
├── validation/
│   ├── pet.ts               # Pet field validation rules
│   └── intake.ts            # Intake form field validation rules
└── types/
    ├── pet.ts               # PetRequest, Pet, PetField types
    ├── request.ts           # ServiceRequest, RequestStatus types
    ├── auth.ts              # Role, Session types
    └── client.ts            # Client, Staff types
```

### 6.2 Technical Considerations

| Concern | Resolution |
|---------|------------|
| Vite import resolution | Vite supports relative imports outside `web/src/` via `resolve.alias` in `vite.config.js` |
| Metro bundler (Expo) | Metro requires `watchFolders` config in `metro.config.js` to resolve outside `mobile/` |
| TypeScript | Both can reference `shared/` via `tsconfig.json` paths or `references` |
| Package boundary | A root `package.json` workspaces config is optional but not required for a single `shared/` dir |
| Build isolation | `shared/` must contain only importable modules (no build step, no React components) |
| Testing | Shared modules need their own unit tests runnable by either Vitest or Jest |

### 6.3 Canonical Color Palette (Proposed)

The authoritative palette should resolve the current mismatches by adopting the web's warm brand palette (which is more intentionally designed) while keeping mobile's utility colors where they provide better contrast:

```json
{
  "brand": {
    "primary": "#c28b1e",
    "primaryHover": "#f08c3a",
    "secondary": "#b8a890",
    "accent": "#e17c80"
  },
  "semantic": {
    "success": "#4a7c59",
    "warning": "#f59e0b",
    "danger": "#d64933",
    "info": "#3b82f6"
  },
  "surface": {
    "background": "#faf7f2",
    "card": "#ffffff",
    "cardMuted": "#f3efe8",
    "input": "#ffffff"
  },
  "text": {
    "primary": "#3c3c3b",
    "secondary": "#5a5a58",
    "muted": "#6a6a66"
  },
  "border": {
    "default": "#e2dfd9",
    "soft": "#edf2ee"
  },
  "status": {
    "pendingReview": "#f59e0b",
    "approved": "#3b82f6",
    "assigned": "#10b981",
    "completed": "#6b7280",
    "cancelled": "#ef4444",
    "paid": "#10b981",
    "unpaid": "#6b7280"
  }
}
```

### 6.4 Shared Terminology

| Concept | Canonical Label | Notes |
|---------|----------------|-------|
| Request statuses | `PENDING_REVIEW` → "Pending Review", `APPROVED` → "Approved", `ASSIGNED`/`JOB_CREATED`/`SCHEDULED` → "Scheduled", `COMPLETED` → "Completed", `CANCELLED` → "Cancelled" | Both platforms must use identical labels |
| Service types | `PET_SITTING` → "Pet Sitting", `DOG_WALKING` → "Dog Walking", `OVERNIGHT` → "Overnight Stay" | Derive from shared constant |
| Pet fields | `name`, `species`, `breed`, `age`, `care_instructions`, `feeding_notes`, `medication_notes`, `behavior_notes` | Same allowlist on both |
| Error messages | "Your session expired. Please sign in again." | Already partially aligned |

---

## 7. My Pets Pilot Plan

### 7.1 Prerequisites

- Phase 1B.5C-A (Customer Pet Editing) must be **deployed and production-validated** before mobile editing can be implemented.
- Planning may proceed before deployment.
- Read-only pet listing depends only on `GET /client/pets` which is already deployed.

### 7.2 Staged Implementation

| Stage | Scope | Depends On | Approval |
|-------|-------|------------|----------|
| **24A-1** | Shared design tokens (`shared/tokens/`) and constants (`shared/constants/statuses.ts`, `shared/constants/petFields.ts`) | None | Standard implementation approval |
| **24A-2** | Mobile My Pets read-only screen — list active pets using `GET /client/pets` | 24A-1 complete; API already deployed | Standard implementation approval |
| **24A-3** | Mobile pet detail screen — expand card to show all fields | 24A-2 | Standard implementation approval |
| **24A-4** | Mobile pet editing — inline edit form using `PUT /client/pets/{petId}` | 24A-3 + Phase 1B.5C-A DEPLOYED and validated | Standard implementation approval |
| **24A-5** | Shared validation alignment — extract pet validation rules to `shared/validation/pet.ts` | 24A-4 | Standard implementation approval |
| **24A-6** | Accessibility and responsive polish | 24A-5 | Standard implementation approval |
| **24A-7** | Automated tests (Jest + RNTL for mobile, verify Vitest still passes for web) | 24A-6 | Standard implementation approval |
| **24A-8** | Manual iOS/Android validation | 24A-7 | Matthew visual review |

### 7.3 Mobile My Pets Screen Design Notes

- Role gate: only `client` role (same as web)
- API: `GET /client/pets` → list of active pets
- Card layout: pet name, species, breed badge, age
- Edit mode: inline form matching web's field allowlist
- Duplicate name detection: client-scoped, same logic as web
- Toast/banner notifications for success/error
- Dirty-state: navigation blocker via React Navigation's `beforeRemove` event
- No photo upload (matches web limitation)
- No archive/delete (matches web client limitation)

---

## 8. Care-Request Intake Second-Stage Plan

### 8.1 Web Intake Flow (Current)

| Step | Content |
|------|---------|
| 1 | Client info (name, email — pre-filled if authenticated) |
| 2 | Service selection, date picker (calendar grid + range), visit windows (multi-select), preferred sitter |
| 3 | Pet details (multi-pet array: name, species, breed, age, feeding/medication/behavior notes), household vet/emergency |
| 4 | Review + terms acceptance + submit |

### 8.2 Mobile Adaptation Considerations

| Aspect | Web Approach | Mobile Recommendation |
|--------|-------------|----------------------|
| Multi-step wizard | Tab-based steps | Scrollable stack or swipeable steps |
| Date picker | Custom DatePickerGrid (calendar) | React Native calendar component or date-range picker |
| Visit windows | Checkbox multi-select | Chip-toggle multi-select |
| Multi-pet input | Dynamic array with add/remove | Expandable accordion cards |
| Review screen | Summary table | Card-based summary |
| Terms acceptance | Checkbox + link to /terms | Checkbox + in-app WebView or link to production URL |
| Saved profile use | Pre-fill from Cognito session | Pre-fill from SecureStore session data |
| Pet selection from saved pets | Not currently integrated | Future: select from `GET /client/pets` |
| Draft/resume | Not implemented on either platform | Future consideration |
| Validation | Per-step inline errors | Per-step inline errors (same rules via shared/validation/) |

### 8.3 Mobile Intake Stages

| Stage | Scope |
|-------|-------|
| **24A-9** | Mobile intake — Step 1 (client info pre-fill from auth) |
| **24A-10** | Mobile intake — Step 2 (service type, date selection, visit windows) |
| **24A-11** | Mobile intake — Step 3 (pet details, vet/emergency) |
| **24A-12** | Mobile intake — Step 4 (review, terms, submit) |
| **24A-13** | Shared intake validation rules (`shared/validation/intake.ts`) |
| **24A-14** | Integration with saved pets (select existing pet from My Pets) |

---

## 9. Testing Strategy

### 9.1 Shared Package Testing

- Unit tests for all `shared/` modules (colors, constants, validation rules)
- Runnable by both Vitest (web) and Jest (mobile)
- Contract tests: validate that shared types match actual API response shapes

### 9.2 Web Testing (Existing — Must Remain Passing)

- 96 legacy tests + 113 component tests = 209 total (Vitest + React Testing Library)
- Production build must continue to succeed
- Any shared import changes must not break existing test mocks
- Accessibility lint (existing eslint-plugin-jsx-a11y)

### 9.3 Mobile Testing (To Be Established)

- Jest configuration needed (Expo default: `jest-expo` preset)
- React Native Testing Library for component tests
- Navigation flow tests (screen transitions, role-based routing)
- API client mocking (same pattern as web: mock fetch)
- Form validation unit tests (shared validation module)
- TypeScript strict-mode type checking via `tsc --noEmit`
- Manual validation: iOS simulator + physical device

### 9.4 No Test Infrastructure Changes During This Planning Task

All testing changes require separate implementation approval.

---

## 10. Recommended Release Sequence

| Release | Name | Scope | Dependencies | Approval |
|---------|------|-------|-------------|----------|
| **24A-1** | Design System Foundation | Create `shared/tokens/`, `shared/constants/`, configure Vite/Metro imports | None | Standard |
| **24A-2** | Shared Constants and Contracts | Status labels, service labels, pet fields, API paths, types | 24A-1 | Standard |
| **24A-3** | Mobile My Pets (Read) | MyPetsScreen, pet card, API integration | 24A-2 | Standard |
| **24A-4** | Mobile My Pets (Edit) | Pet edit form, validation, save flow | 24A-3 + **1B.5C-A deployed** | Standard |
| **24A-5** | Mobile Care Request Intake | Multi-step form, date selection, submission | 24A-2 | Standard |
| **24A-6** | Visual Consistency Polish | Align colors, badge styles, typography between web and mobile | 24A-1 | Standard |
| **24A-7** | Accessibility Validation | WCAG compliance check (web), RN accessibility props (mobile) | 24A-6 | Standard |
| **24A-8** | Mobile Test Infrastructure | Jest + RNTL setup, shared module tests | 24A-2 | Standard |
| **24A-9** | Mobile Build and Distribution | EAS build, TestFlight update, tester access | All above complete | **Separate Matthew approval** |

**24A-9 is explicitly separated** — no EAS build, TestFlight, App Store, or distribution action is included in any earlier release.

---

## 11. Approval Gates

| Action | Requires |
|--------|----------|
| Create `shared/` directory and configure build tools | Implementation approval |
| Modify `vite.config.js` or `metro.config.js` | Implementation approval |
| Add new mobile screen | Implementation approval |
| Phase 1B.5C-A deployment (prerequisite for mobile editing) | Matthew explicit deployment approval |
| EAS build | Separate Matthew approval |
| TestFlight update | Separate Matthew approval |
| App Store submission | Separate Matthew approval |
| Ryan tester access | Separate Matthew approval |

---

## 12. What This Document Does NOT Authorize

- ❌ Source code changes (web, mobile, backend, or Terraform)
- ❌ Build tool configuration changes
- ❌ Dependency installation
- ❌ EAS builds or mobile distribution
- ❌ TestFlight or App Store Connect changes
- ❌ Ryan or external tester additions
- ❌ React Native Web migration
- ❌ Website rewrite
- ❌ Phase 1B.5C-A deployment
- ❌ Any Terraform, AWS, Cognito, Stripe, or production mutation
