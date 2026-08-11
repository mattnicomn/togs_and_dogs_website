# Phase 24A: Cross-Platform Design System and Mobile Workflow Alignment

**Status:** 📋 PLANNING COMPLETE (Revised) — Implementation phases 24A-1A–1C, 24A-2A, 24A-2B.1–2B.2B, 24A-2C.1A–1C, 24A-2C.2A–2D.4, and 24A-3–8 are locally complete, committed, and pushed. Phases 24A-9A, 9B, 9B.4, and 9C.1 are complete. Phase 24A-9C.2 paired remediation builds are complete, and Phase 24A-9C remediation revalidation is complete/pass against iOS `1.0.0 (6)` and Android `1.0.0` versionCode `4`, both from `bf9f80d95c1846f197bab24d96463906bc26bfce`. Phase 24A is not publicly released; formal Phase 24A-9D production-write validation remains separately gated.
**Date:** 2026-07-24 (revised 2026-08-11)
**Starting HEAD:** `2fbfba9` (planning), `bc73408` (revision)
**Depends on:** Phase 1B.5C-A deployment (for mobile pet editing only)

---

## 1. Purpose

Make the React/Vite website and Expo/React Native mobile application feel like one coherent Togs & Dogs product by aligning shared design tokens, terminology, validation rules, API contracts, and workflow behavior — while preserving separate platform-specific presentation components.

**Not in scope:** React Native Web migration, website rewrite, EAS builds, mobile distribution, TestFlight changes, App Store submission, Ryan testing changes.

---

## 2. Authentication Parity (Corrected)

### 2.1 Web — Forgot-Password Status: **Locally Complete / Not Deployed**

| Capability | Status | Evidence |
|---|---|---|
| Forgot-password entry point | ✅ Locally complete | Keyboard-accessible action in the existing `AdminDashboard.jsx` login shell |
| Reset initiation (`forgotPassword`) | ✅ Locally complete | `web/src/api/auth.js` uses the existing customer user pool and standard self-service SDK operation |
| Verification-code handling | ✅ Locally complete | Dedicated code/new-password confirmation state |
| New-password submission | ✅ Locally complete | `confirmForgotPassword(email, code, newPassword)` with required, eight-character, and password-match validation |
| Success/error states | ✅ Locally complete | Safe generic request errors, code mismatch/expiry copy, success status, and return to sign-in |
| Complete flow usable | ✅ Locally | Not deployed to production |
| Tests | ✅ Complete | 13 focused; 24 relevant AdminDashboard/auth; 251 Vitest; 99 legacy / 350 combined web tests |

The web auth module now exposes `forgotPassword` and `confirmForgotPassword` alongside the existing sign-in/session helpers. Implementation commit `c85a7860c706f38ab2da7998fb7ee8621e8fcfa6` is pushed and independently reviewed (`IMPLEMENTATION_CORRECT`). No Cognito configuration, backend, infrastructure, mobile, or production change occurred.

The admin-initiated `resetStaffPassword` and `resetClientPassword` API functions exist for staff/client account management — these are **not** self-service forgot-password flows.

### 2.2 Mobile — Forgot-Password Status: **Complete**

| Capability | Status | Evidence |
|---|---|---|
| Forgot-password entry point | ✅ Present | "Forgot password?" link in LoginScreen login mode |
| Reset initiation (`forgotPassword`) | ✅ Complete | `mobile/src/auth/cognito.ts` exports `forgotPassword(email)` calling `cognitoUser.forgotPassword()` |
| Verification-code handling | ✅ Complete | LoginScreen `forgotResetPassword` mode with 6-digit code input |
| New-password submission | ✅ Complete | `confirmForgotPassword(email, code, newPassword)` with confirm-password match validation |
| Success state | ✅ Present | Green success banner with "Back to Sign In" button |
| Error states | ✅ Comprehensive | Code mismatch, expiry, generic failure, validation (8-char min, password match) |
| Complete flow usable | ✅ Yes | Three-mode LoginScreen: login → forgotSendCode → forgotResetPassword |
| Tests | ❌ None | No automated tests exist for the mobile app |

### 2.3 Disposition

- Web self-service forgot-password parity is locally complete, committed, pushed, and not deployed.
- Mobile served as the behavioral reference while the web retained its platform-specific presentation.
- Production deployment remains a separate approval gate and is not authorized by local completion.

---

## 3. Current Technology Baseline

| Property | Web | Mobile |
|----------|-----|--------|
| Framework | React 19 (Vite 8) | React Native 0.81 (Expo 54) |
| Language | JavaScript (JSX) | TypeScript (TSX) |
| Styling | CSS custom properties + component CSS files | React Native StyleSheet (inline) |
| Routing | React Router 7 (createBrowserRouter) | React Navigation 7 (stack + bottom tabs) |
| Auth | Cognito SDK (browser localStorage) | Cognito SDK (Expo SecureStore) |
| Tests | Vitest 4 + RTL (209 passing) + Node test runner (legacy) | None configured |
| Build | Vite production build | Expo EAS (not currently active) |
| Module format | ESM (`"type": "module"`) | Metro bundler (CommonJS interop) |

---

## 4. Design Token Comparison

### 4.1 Color Alignment

| Token | Web Value | Mobile Value | Aligned? |
|-------|-----------|--------------|----------|
| Primary | `#c28b1e` | `#c28b1e` | ✅ Exact |
| Primary Hover | `#f08c3a` | `#a37213` | ❌ Different |
| Background | `#faf7f2` | `#faf7f2` | ✅ Exact |
| Card | `#ffffff` | `#ffffff` | ✅ Exact |
| Text | `#3c3c3b` | `#3c3c3b` | ✅ Exact |
| Text Muted | `#6a6a66` | `#7f8c8d` | ❌ Different |
| Border | `#e2dfd9` | `#e2e8f0` | ❌ Different |
| Border Soft | `#e2dfd9` (alias) | `#edf2ee` | ❌ Different |
| Success | `#4a7c59` | `#10b981` | ❌ Different |
| Danger/Warning | `#d64933` | `#ef4444` | ❌ Different |

**Five tokens require visual alignment** (primaryHover, textMuted, border, success, danger). Each represents a user-visible color change and must be reviewed individually.

### 4.2 Spacing, Radii, Typography

No formal shared scale exists on either platform. Both use ad-hoc pixel/dp values inline.

---

## 5. Screen and Workflow Parity Matrix

| Workflow | Web | Mobile | Aligned | Disposition |
|----------|-----|--------|---------|-------------|
| Sign-in | `/admin` inline login | `LoginScreen` dedicated | ✅ Functional | Align error messages |
| Forgot password | ✅ Locally complete / not deployed | ✅ Complete | ✅ Aligned locally | Separate web deployment gate |
| Session refresh | Cognito SDK auto (browser) | SecureStore + pre-request refresh | ✅ Both maintain | Platform-appropriate |
| My Pets (list) | `/my-pets` ✅ | ❌ Missing | — | **Pilot target** |
| Pet editing | ✅ (Phase 1B.5C-A) | ❌ Missing | — | After 1B.5C-A deployment |
| Care request intake | `/book` ✅ (4-step) | ❌ Missing | — | Second-stage target |
| My Bookings | `/my-bookings` ✅ | `BookingsScreen` ✅ | ✅ Functional | Align labels |
| Request detail (admin) | CareCard ✅ | `RequestDetailScreen` ✅ | ✅ Actions match | Align labels |
| Request list (admin) | Dashboard tab ✅ | `RequestListScreen` ✅ | ✅ Filter + list | Align filter labels |
| Schedule | `MasterScheduler` ✅ | `ScheduleScreen` ✅ | ⚠️ Different approach | Intentional |
| Staff/Client management | ✅ Full CRUD | ❌ | — | Intentionally web-only |
| Platform admin | ✅ | ❌ | — | Intentionally web-only |
| Google Calendar | ✅ | ❌ | — | Intentionally web-only |
| Payments | ✅ | ❌ | — | Intentionally web-only |
| Dark mode | ✅ | ❌ Missing | — | Future |

---

## 6. Design-System Structure

### 6.1 Recommended: Shared Tokens + Contracts, Separate Presentation

A root-level `shared/` directory containing platform-neutral data only:

```
shared/
├── tokens/
│   ├── colors.json
│   ├── spacing.json
│   ├── radii.json
│   └── typography.json
├── constants/
│   ├── statuses.ts
│   ├── services.ts
│   ├── petFields.ts
│   └── errors.ts
├── contracts/
│   ├── api-paths.ts
│   └── config.ts
├── validation/
│   ├── pet.ts
│   └── intake.ts
└── types/
    ├── pet.ts
    ├── request.ts
    ├── auth.ts
    └── client.ts
```

### 6.2 Module Resolution Considerations

| Concern | Current State | Resolution Required |
|---------|---------------|-------------------|
| **Vite** access to `../shared/` | No alias configured; Vite defaults to resolving relative imports from project root | Add `resolve.alias` in `vite.config.js` mapping `@shared` to `../shared` |
| **Metro** (Expo) watch folders | `metro.config.js` uses default config; does not watch outside `mobile/` | Add `watchFolders: [path.resolve(__dirname, '../shared')]` and resolver `nodeModulesPaths` |
| **TypeScript** (mobile) | `tsconfig.json` extends `expo/tsconfig.base`; no path aliases | Add `compilerOptions.paths` mapping `@shared/*` to `../shared/*` |
| **TypeScript** (web) | No tsconfig (JavaScript project) | JSON imports work natively; TS types would require adding a tsconfig or using JSDoc |
| **Vitest** | `vitest.config.js` has no alias | Must mirror the Vite alias for test resolution |
| **Jest** (future mobile) | Not configured | Must add `moduleNameMapper` for `@shared/` |
| **JSON imports** | Vite supports natively; Metro supports natively | ✅ No issue for token files |
| **Expo EAS** | Builds from `mobile/` directory | Must include `shared/` in the EAS build context (eas.json or monorepo config) |
| **Package boundary** | Neither `shared/` nor root has a `package.json` | Options: (A) direct relative imports, (B) npm workspace, (C) symlink. Recommend (A) for simplicity until complexity warrants (B) |
| **Generated adapters** | N/A currently | Consider a build-time script that generates `web/src/generated/tokens.css` and `mobile/src/generated/theme.ts` from JSON if direct cross-root imports prove problematic |

### 6.3 Decision: Direct Imports vs Generated Adapters

This decision requires implementation-time evidence. The planning document records both options:

**Option A — Direct cross-root imports:** Simpler, fewer files, but requires build-tool configuration changes on both sides. Risk: EAS build context may not include `shared/` without additional config.

**Option B — Generated adapters:** A script reads `shared/tokens/colors.json` and outputs `web/src/generated/tokens.css` (CSS custom properties) and `mobile/src/generated/theme.ts` (COLORS object). No build-tool changes needed; generated files are committed. Risk: must remember to regenerate after token changes.

**Recommendation:** Evaluate both during Phase 24A-1A (architecture decision). Do not pre-select without testing actual import resolution.

---

## 7. Revised Release Sequence

### Phase 24A-1A — Shared Architecture and Token Contract

| Property | Value |
|---|---|
| **Scope** | Decide directory structure, module resolution approach, token schema format. Create `shared/tokens/colors.json` with canonical palette. Document import strategy. |
| **Prerequisites** | None |
| **Source files likely affected** | New: `shared/tokens/colors.json`, `shared/README.md` |
| **Expected tests** | Schema validation test (JSON valid, all required keys present) |
| **Expected build validation** | None (no application imports change yet) |
| **User-visible impact** | None |
| **Production deployment needed** | No |
| **EAS build needed** | No |
| **Required Matthew approval** | Standard implementation approval |
| **Rollback** | Delete `shared/` directory |
| **Continuity update** | Record architecture decision |

### Phase 24A-1B — Platform Adapters and No-Visual-Change Wiring

| Property | Value |
|---|---|
| **Scope** | Configure Vite alias and/or generate `web/src/generated/tokens.css`. Configure Metro watchFolders and/or generate `mobile/src/generated/theme.ts`. Wire adapters but do NOT change any rendered color values. |
| **Prerequisites** | 24A-1A complete |
| **Source files likely affected** | `web/vite.config.js` OR `web/src/generated/tokens.css`; `mobile/metro.config.js` and/or `mobile/src/generated/theme.ts`; possibly `web/vitest.config.js` |
| **Expected tests** | Web: existing 209 tests pass. Mobile: TypeScript type check passes. Builds succeed. |
| **Expected build validation** | `npm run build` (web) succeeds. Expo type check succeeds. |
| **User-visible impact** | None — all rendered values identical |
| **Production deployment needed** | No (web build unchanged; no mobile distribution) |
| **EAS build needed** | No |
| **Required Matthew approval** | Standard implementation approval |
| **Rollback** | Revert config changes; remove generated files |
| **Continuity update** | Record wiring approach chosen |

### Phase 24A-1C — Visual Token Alignment

| Property | Value |
|---|---|
| **Scope** | Resolve the five misaligned tokens (primaryHover, textMuted, border, success, danger). Each change reviewed independently. Update both platform adapters to use canonical values. |
| **Prerequisites** | 24A-1B complete and verified |
| **Source files likely affected** | `shared/tokens/colors.json`, web CSS variables in `index.css`, `mobile/src/theme/colors.ts` (or generated equivalent) |
| **Expected tests** | Web: existing tests pass. Visual regression review (manual screenshots). |
| **Expected build validation** | Web production build. Mobile type check. |
| **User-visible impact** | Yes — color changes visible to users on both platforms |
| **Production deployment needed** | Yes (web S3/CloudFront sync for color changes to appear) |
| **EAS build needed** | No (mobile colors only appear to TestFlight testers after a future build) |
| **Required Matthew approval** | Deployment approval (user-visible change) |
| **Rollback** | Revert token values; redeploy web |
| **Continuity update** | Record aligned palette |

### Phase 24A-2 — Shared Constants and API Contracts

| Property | Value |
|---|---|
| **Scope** | Create `shared/constants/statuses.ts`, `shared/constants/services.ts`, `shared/constants/petFields.ts`, `shared/contracts/api-paths.ts`, `shared/types/`. Wire imports in web and mobile where currently hardcoded inline. |
| **Prerequisites** | 24A-1B complete |
| **Source files likely affected** | New shared files + modifications to web components and mobile screens that currently hardcode status labels |
| **Expected tests** | Shared module unit tests. Web: existing tests pass with updated imports. Mobile: type check passes. |
| **Expected build validation** | Both builds succeed |
| **User-visible impact** | None if labels are unchanged; alignment if labels differ |
| **Production deployment needed** | Only if web label rendering changes |
| **EAS build needed** | No |
| **Required Matthew approval** | Standard implementation approval |
| **Rollback** | Revert shared imports; restore inline values |
| **Continuity update** | Record constants extracted |

### Phase 24A-3 — Mobile Test Foundation

| Property | Value |
|---|---|
| **Scope** | Establish mobile automated test infrastructure. |
| **Prerequisites** | 24A-1B complete (so metro config is settled) |
| **Source files likely affected** | `mobile/package.json` (devDependencies), `mobile/jest.config.js` or `package.json` jest field, test setup files, `mobile/__tests__/` or `mobile/tests/` directory, mock files |
| **Planned infrastructure** | |
| - Jest preset | `jest-expo` (Expo's supported preset) |
| - Component testing | `@testing-library/react-native` |
| - API-client mocking | Manual `fetch` mock or `msw` |
| - Navigation mocking | `@react-navigation/native` mock via `jest.mock` |
| - SecureStore mocking | Mock `expo-secure-store` module |
| - Auth context mocking | Custom test wrapper providing `AuthContext` |
| - Type checking | `tsc --noEmit` as a test script |
| - CI-compatible command | `npm test` (Jest) + `npm run typecheck` |
| - Initial smoke tests | LoginScreen renders, BookingsScreen renders, DashboardScreen renders, AppNavigator role routing |
| **Expected tests** | ≥5 initial smoke tests for existing screens |
| **Expected build validation** | `jest --passWithNoTests` succeeds |
| **User-visible impact** | None |
| **Production deployment needed** | No |
| **EAS build needed** | No |
| **Required Matthew approval** | Standard implementation approval |
| **Rollback** | Remove test config and devDependencies |
| **Continuity update** | Record test infrastructure established |

### Phase 24A-4 — Mobile My Pets (Read-Only)

| Property | Value |
|---|---|
| **Scope** | New `MyPetsScreen` for client role. List active pets from `GET /client/pets`. Pet card with name, species, breed, age. |
| **Prerequisites** | 24A-3 complete (tests exist); deployed `GET /client/pets` contract confirmed operational |
| **Source files likely affected** | New: `mobile/src/screens/MyPetsScreen.tsx`; modified: `mobile/src/navigation/AppNavigator.tsx` (add tab) |
| **Expected tests** | Component test for MyPetsScreen (renders, shows loading, shows pets, shows empty state) |
| **Expected build validation** | Mobile type check + Jest pass |
| **User-visible impact** | New screen visible only to internal TestFlight testers (after future EAS build) |
| **Production deployment needed** | No |
| **EAS build needed** | Not until 24A-9 |
| **Required Matthew approval** | Standard implementation approval |
| **Rollback** | Remove screen; revert navigation change |
| **Continuity update** | Record My Pets read-only complete |

### Phase 24A-5 — Mobile My Pets (Editing)

| Property | Value |
|---|---|
| **Scope** | Inline edit form in MyPetsScreen using `PUT /client/pets/{petId}`. Shared validation from `shared/validation/pet.ts`. Duplicate name detection, toast notifications, dirty-state navigation blocker. |
| **Prerequisites** | 24A-4 complete; **Phase 1B.5C-A explicitly approved, deployed, authenticated production validated, and recorded as completed** |
| **Source files likely affected** | `mobile/src/screens/MyPetsScreen.tsx`, `shared/validation/pet.ts` |
| **Expected tests** | Edit form validation tests, save success/error tests, dirty-state tests |
| **Expected build validation** | Mobile type check + Jest pass |
| **User-visible impact** | New editing capability (visible after future EAS build) |
| **Production deployment needed** | No (API already deployed via 1B.5C-A) |
| **EAS build needed** | Not until 24A-9 |
| **Required Matthew approval** | Standard implementation approval |
| **Rollback** | Remove edit mode; restore read-only |
| **Continuity update** | Record mobile pet editing complete |

### Phase 24A-6 — Mobile Care-Request Intake

| Property | Value |
|---|---|
| **Scope** | Multi-step intake form on mobile matching web's `/book` flow. Steps: client info → service/dates → pet details → review/submit. |
| **Prerequisites** | 24A-3 complete; 24A-2 (shared constants) complete |
| **Source files likely affected** | New: `mobile/src/screens/IntakeScreen.tsx` (or multi-file); modified: navigation |
| **Expected tests** | Per-step validation tests, submission tests, error recovery tests |
| **Expected build validation** | Mobile type check + Jest pass |
| **User-visible impact** | New capability (visible after future EAS build) |
| **Production deployment needed** | No |
| **EAS build needed** | Not until 24A-9 |
| **Required Matthew approval** | Standard implementation approval |
| **Rollback** | Remove intake screen; revert navigation |
| **Continuity update** | Record mobile intake complete |

### Phase 24A-7 — Visual Consistency Polish

| Property | Value |
|---|---|
| **Scope** | Align badge styles, card radii, button hierarchy, typography scale, spacing between web and mobile using shared tokens. |
| **Prerequisites** | 24A-1C (visual token alignment) + 24A-2 (constants) complete |
| **Source files likely affected** | Mobile StyleSheet values, web CSS refinements |
| **Expected tests** | Existing tests pass; manual visual comparison |
| **User-visible impact** | Yes (visual polish) |
| **Production deployment needed** | Yes (web changes) |
| **EAS build needed** | Not until 24A-9 |
| **Required Matthew approval** | Deployment approval for web visual changes |
| **Rollback** | Revert style values |
| **Continuity update** | Record visual alignment complete |

### Phase 24A-8 — Accessibility Validation

| Property | Value |
|---|---|
| **Scope** | Web: verify WCAG 2.1 AA compliance of changed colors. Mobile: verify React Native accessibility props (accessibilityLabel, accessibilityRole, accessibilityState). |
| **Prerequisites** | 24A-7 complete |
| **Source files likely affected** | Accessibility prop additions; possible color contrast adjustments |
| **Expected tests** | Accessibility lint; manual screen-reader testing expectations documented |
| **User-visible impact** | Improved accessibility |
| **Production deployment needed** | Yes if web changes |
| **EAS build needed** | Not until 24A-9 |
| **Required Matthew approval** | Standard for props; deployment approval for web changes |
| **Rollback** | Revert accessibility additions |
| **Continuity update** | Record accessibility pass |

### Phase 24A-9 — Mobile Build, Internal Distribution, and Validation (Separately Approved)

| Property | Value |
|---|---|
| **Scope** | Paired EAS builds, internal distribution, Matthew validation on device, and bounded defect remediation |
| **Prerequisites** | All prior 24A phases complete and reviewed |
| **Source files likely affected** | `mobile/app.json` version bump, possibly `eas.json` |
| **Expected tests** | All mobile Jest tests pass; type check clean |
| **Expected build validation** | EAS build succeeds |
| **User-visible impact** | New TestFlight build available |
| **Production deployment needed** | No (API already deployed) |
| **EAS build needed** | **Yes** |
| **Required Matthew approval** | **Separate explicit Matthew approval for EAS build and TestFlight** |
| **Rollback** | Do not distribute; previous TestFlight build remains active |
| **Current state** | 9A, 9B, 9B.4, and 9C.1 complete; 9C.2 paired remediation builds complete; 9C remediation revalidation complete/pass. iOS physical validation passed; Android remediation validation passed with physical-device status unconfirmed. Public release and 9D remain separately gated. |
| **Continuity update** | Record source SHA, build identifiers, internal distribution, findings, remediation, and physical validation status |

---

## 8. My Pets Dependencies (Corrected)

| Dependency | Required For | Status |
|---|---|---|
| Shared tokens and constants (24A-1, 24A-2) | All mobile feature work | Not started |
| Mobile test infrastructure (24A-3) | Any new mobile screen | Not started |
| `GET /client/pets` API | Mobile My Pets read-only (24A-4) | ✅ Already deployed and operational |
| `PUT /client/pets/{petId}` API (Phase 1B.5C-A) | Mobile My Pets editing (24A-5) | ✅ Deployed 2026-07-28 & Validated 2026-07-30 |

**Critical distinction:**
- Planning may proceed at any time.
- Mobile My Pets **read-only** (24A-4) is locally complete.
- Mobile My Pets **editing** (24A-5) is 100% locally complete, committed (`93fe98a5c2f28481cd53a85a9479567c413a534d`), and pushed to `origin/main`.
- Client edit scope remains edit-only (no pet creation, deletion, archive, or restore).
- The original paired internal artifacts were built from `8a1ce46c0a8bd0d02f4000188b21e115b370281c`; physical-iPhone findings were remediated locally in `2c3e22a95e0062bed5e40f42e39e4669f94a1d43`.
- A new paired iOS and Android remediation build from the corrected SHA remains separately approval-gated; public distribution remains unapproved.

---

## 9. Care-Request Intake Comparison

### Web Intake Flow (Current — 4 Steps)

| Step | Fields |
|------|--------|
| 1 | Client name, email (pre-filled if authenticated) |
| 2 | Service type, date picker (calendar grid + range helper), visit windows (multi-select), preferred sitter, timing notes |
| 3 | Multi-pet array (name, species, breed, age, feeding/medication/behavior notes), household vet info, emergency contact |
| 4 | Review summary, terms/privacy acceptance checkbox, submit |

### Mobile Adaptation Notes

- Multi-step wizard via scrollable stack or swipeable pager
- Date selection: RN calendar component or date-range picker
- Visit windows: chip-toggle multi-select
- Multi-pet: expandable accordion cards
- Terms: checkbox + link to production URL (not in-app rendering)
- Pre-fill from SecureStore session data
- Future: select saved pets from My Pets list
- Validation: shared rules via `shared/validation/intake.ts`
- Draft/resume behavior: not currently on either platform (future consideration)

---

## 10. Testing Strategy

### Shared Package
- Unit tests for JSON schema validity, constant completeness, validation rule correctness
- Runnable by both Vitest (web context) and Jest (mobile context)

### Web (Existing — Must Remain Passing)
- 96 legacy tests (Node test runner) + 113 component tests (Vitest + RTL) = 209 total
- Production build (`npm run build`) must succeed
- Shared imports must not break existing test mocks

### Mobile (To Be Established in Phase 24A-3)
- `jest-expo` preset
- `@testing-library/react-native`
- API-client mock (mock `fetch` globally)
- Navigation mock (`@react-navigation/native` jest mock)
- SecureStore mock (`expo-secure-store` jest mock)
- Auth context mock (wrapper providing `AuthProvider` with controllable state)
- Type checking: `tsc --noEmit`
- CI command: `npm test` + `npm run typecheck`
- Initial smoke tests: screen renders for LoginScreen, BookingsScreen, DashboardScreen, role-based navigation routing

---

## 11. What This Document Does NOT Authorize

- ❌ Source code changes (web, mobile, backend, or Terraform)
- ❌ Build tool configuration changes
- ❌ Dependency installation
- ❌ Test infrastructure setup
- ❌ EAS builds or mobile distribution
- ❌ TestFlight or App Store Connect changes
- ❌ React Native Web migration
- ❌ Phase 1B.5C-A deployment
- ❌ Any AWS, Cognito, Stripe, or production mutation
