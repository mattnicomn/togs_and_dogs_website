# Phase 24A-1B: Platform Token Adapters and No-Visual-Change Wiring

**Status:** ✅ COMPLETE
**Date:** 2026-07-24
**Starting HEAD:** `37f31f0`

---

## Summary

Implemented a deterministic token-adapter generator that reads the shared contract (`shared/tokens/colors.json`) and produces platform-local generated files consumed by web and mobile. No visual rendering changed. No build configuration, package manifests, or dependencies changed.

## Architecture Decision: Generated Platform-Local Adapters

Selected generated adapters over direct cross-root imports because:
- No Vite alias, Metro watchFolders, TypeScript path aliases, or Babel changes required.
- No npm workspace or monorepo configuration needed.
- Generated files live inside the existing source tree — standard imports, EAS-safe.
- Trade-off: must regenerate after contract changes (acceptable for this project scale).

## Deliverables

| File | Purpose |
|------|---------|
| `shared/generate-adapters.mjs` | Deterministic generator (Node.js built-in modules only) |
| `web/src/generated/color-tokens.css` | Generated CSS custom properties (web values) |
| `mobile/src/theme/generatedColors.ts` | Generated TypeScript COLORS export (mobile values) |
| `shared/validate-adapters.mjs` | 7-test adapter validation suite |
| `web/src/index.css` | Added `@import` for generated tokens (values identical to existing) |
| `mobile/src/theme/colors.ts` | Re-exports from generated adapter |

## Token Mapping

### Web: Contract Token → CSS Variable

| Token | CSS Variable | Value |
|-------|-------------|-------|
| primary | `--primary` | `#c28b1e` |
| primaryHover | `--primary-hover` | `#f08c3a` |
| background | `--page-bg` | `#faf7f2` |
| card | `--card-bg` | `#ffffff` |
| textPrimary | `--text-primary` | `#3c3c3b` |
| textMuted | `--text-muted` | `#6a6a66` |
| border | `--border-color` | `#e2dfd9` |
| borderSoft | `--border-soft` | `#e2dfd9` |
| success | `--success-color` | `#4a7c59` |
| danger | `--warning-color` | `#d64933` |
| info | `--info-color` | `#3b82f6` |
| warning | `--caution-color` | `#f59e0b` |
| white | `--white` | `#ffffff` |

### Mobile: Contract Token → COLORS Property

| Token | Property | Value |
|-------|----------|-------|
| primary | `primary` | `#c28b1e` |
| primaryHover | `primaryHover` | `#a37213` |
| background | `background` | `#faf7f2` |
| card | `cardBg` | `#ffffff` |
| textPrimary | `text` | `#3c3c3b` |
| textMuted | `textMuted` | `#7f8c8d` |
| border | `border` | `#e2e8f0` |
| borderSoft | `borderSoft` | `#edf2ee` |
| success | `success` | `#10b981` |
| danger | `danger` | `#ef4444` |
| info | `info` | `#3b82f6` |
| warning | `warning` | `#f59e0b` |
| white | `white` | `#ffffff` |

## Unmapped Web Variables (Not in Contract)

These existing web CSS variables are NOT represented in the shared contract and remain untouched in `index.css`:

- `--secondary`, `--accent`, `--accent-soft` (brand palette — web-specific)
- `--card-bg-muted`, `--text-secondary` (additional theme tiers)
- `--input-bg`, `--button-bg`, `--button-text` (component-level aliases)
- `--accent-color`, `--accent-hover` (alias refs)
- `--header-bg` (rgba value)
- `--radius-*`, `--shadow-*` (spacing/elevation — separate future tokens)
- `--staff-*` (operational palette)
- `--bp-*` (breakpoints)
- `--sans`, `--serif` (typography)
- Dark-mode overrides

These will be addressed in future token contract expansions (Phase 24A-2 or later).

## Validation Results

### Contract Validation (9/9 passed)
```
✔ colors.json parses as valid JSON
✔ all required token names exist
✔ no duplicate token names
✔ all color values follow hex format
✔ alignment status uses defined allowlist
✔ aligned tokens have matching web and mobile values
✔ misaligned tokens are marked requires-24A-1C
✔ all tokens have a semantic description
✔ contract metadata is present
```

### Adapter Validation (7/7 passed)
```
✔ load contract and generated files
✔ web adapter contains all contract tokens with web values
✔ mobile adapter contains all contract tokens with mobile values
✔ mismatched tokens remain different between platforms
✔ generated files carry the required warning header
✔ generator is deterministic (running twice produces identical output)
✔ generator fails on invalid contract
```

### Web Tests (209/209 passed)
- Legacy: 96 passed
- Component: 113 passed
- Production build: SUCCESS (424ms)

### Mobile TypeScript
- `tsc --noEmit`: zero errors

## Generated-File Policy

- Source of truth: `shared/tokens/colors.json`
- Generator command: `node shared/generate-adapters.mjs`
- Generated files are committed to Git (required at build time; no build hook added)
- Verify freshness: run generator and check `git diff` — if output differs, regenerate and commit
- Do not manually edit generated files
- Future CI can enforce: `node shared/generate-adapters.mjs && git diff --exit-code`

## No-Visual-Change Evidence

- Web generated CSS declares identical values to existing `index.css` declarations
- Existing `index.css` declarations still present (override order preserved)
- Mobile `colors.ts` re-exports from `generatedColors.ts` which has identical values
- All 209 web tests pass without modification
- Mobile TypeScript compiles without error
- Mismatched tokens (6) remain different between platforms

## Next Steps

| Phase | Scope | Approval |
|-------|-------|----------|
| 24A-1C | Resolve 6 misaligned color tokens (user-visible) | Separate Matthew approval + deployment approval |
| 24A-2 | Shared constants and API contracts | Standard implementation approval |
| 24A-3 | Mobile test foundation | Standard implementation approval |
