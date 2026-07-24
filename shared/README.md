# Shared Design-Token Contract

**Status:** Contract defined — not consumed by either application
**Phase:** 24A-1A (architecture and token contract)
**Created:** 2026-07-24

---

## Purpose

This directory contains the canonical design-token contract for the Togs & Dogs
cross-platform product. It defines the single source of truth for color palette,
spacing, radii, typography, and semantic constants that both the React/Vite
website and the Expo/React Native mobile application should eventually derive
their rendered values from.

---

## Current Status

- ✅ Token contract defined (`tokens/colors.json`)
- ✅ Validation script available (`validate-tokens.mjs`)
- ❌ Web application does NOT import from this directory
- ❌ Mobile application does NOT import from this directory
- ❌ No build configuration references this directory
- ❌ No visual behavior has changed

The contract records both platforms' current values and identifies where they
differ. It does not yet impose a unified canonical value for misaligned tokens.

---

## Phase Boundaries

| Phase | Scope | Approved? |
|-------|-------|-----------|
| **24A-1A** (this phase) | Define contract schema, document architecture | ✅ Complete |
| **24A-1B** | Wire platform adapters (Vite alias or generated CSS, Metro watchFolders or generated theme) without visual changes | ❌ Separately gated |
| **24A-1C** | Resolve misaligned values (user-visible color changes, requires deployment) | ❌ Separately gated |

---

## Architecture: Candidate Consumption Approaches

The final approach for how `web/` and `mobile/` consume these tokens is deferred
to Phase 24A-1B. The following options are documented for evaluation:

### Option A — Direct Cross-Root Imports

Both apps import directly from `../shared/tokens/colors.json`.

- **Vite:** Requires `resolve.alias` in `vite.config.js` (e.g., `'@shared': '../shared'`).
  Vitest config must mirror the alias.
- **Metro (Expo):** Requires `watchFolders` in `metro.config.js` pointing to `shared/`.
  May also need `resolver.nodeModulesPaths` adjustment.
- **TypeScript:** Requires `compilerOptions.paths` in tsconfig (mobile) or JSDoc typing (web).
- **EAS Build:** Must include `shared/` in the Expo build context.
- **Pros:** Single source, no generation step, immediate consistency.
- **Cons:** Build-tool changes required on both platforms; EAS context complexity.

### Option B — Generated Platform Adapters

A build-time script reads `shared/tokens/colors.json` and generates:
- `web/src/generated/tokens.css` (CSS custom properties)
- `mobile/src/generated/theme.ts` (TypeScript COLORS export)

Generated files are committed and imported like normal application code.

- **Pros:** No build-tool configuration changes; standard imports; EAS-safe.
- **Cons:** Must regenerate after token changes; risk of drift if generation is forgotten.

### Option C — npm Workspace / Local Package

`shared/` gets a `package.json` and is referenced as a workspace dependency.

- **Pros:** Clean package boundary; standard resolution; shareable types.
- **Cons:** Monorepo tooling overhead; may conflict with Expo's expectations.

### Recommendation

Do not select an approach without testing actual import resolution during 24A-1B.
This document records the options; the implementation phase makes the decision.

---

## Constraints

- Application imports must NOT change during Phase 24A-1A.
- Build configuration must NOT change during Phase 24A-1A.
- Visual rendered values must NOT change during Phase 24A-1A or 24A-1B.
- User-visible alignment changes are restricted to Phase 24A-1C.

---

## Token Schema

Tokens are stored in JSON files under `tokens/`.

Each color token includes:

```json
{
  "tokenName": {
    "semantic": "Brief description of the token's role",
    "web": "#hexvalue (current web CSS value)",
    "mobile": "#hexvalue (current mobile COLORS value)",
    "aligned": true | false,
    "decision": "aligned" | "requires-24A-1C"
  }
}
```

- `aligned: true` — Both platforms use the same value. No decision needed.
- `aligned: false, decision: "requires-24A-1C"` — Values differ. Phase 24A-1C
  will select the canonical value after visual review.

---

## Adding Future Tokens

1. Add the token to the appropriate `tokens/*.json` file following the schema.
2. Run `node shared/validate-tokens.mjs` to verify the contract is valid.
3. Do not change rendered application values without a separately approved phase.

---

## Validation

Run from the repository root:

```
node shared/validate-tokens.mjs
```

This validates:
- JSON parses successfully
- All required token names are present
- Color values match expected hex format (`#` + 3, 4, 6, or 8 hex digits)
- Alignment status uses the defined allowlist (`aligned`, `requires-24A-1C`)
- No duplicate token names exist
- Tokens requiring future decisions are clearly marked
