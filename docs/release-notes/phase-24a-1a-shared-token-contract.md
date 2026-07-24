# Phase 24A-1A: Shared Architecture and Design-Token Contract

**Status:** ✅ COMPLETE
**Date:** 2026-07-24
**Starting HEAD:** `f97800c`

---

## Summary

Defined the canonical cross-platform color token contract and architecture documentation for the Togs & Dogs shared design system. No application imports, build configuration, or visual rendering changed.

## Deliverables

| File | Purpose |
|------|---------|
| `shared/README.md` | Architecture documentation, phase boundaries, candidate consumption approaches, constraints |
| `shared/tokens/colors.json` | Canonical 13-token color contract with web/mobile current values and alignment status |
| `shared/validate-tokens.mjs` | Automated validation (9 tests) using Node.js built-in test runner |

## Token Contract Summary

| Token | Aligned? | Web | Mobile |
|-------|----------|-----|--------|
| `primary` | ✅ | `#c28b1e` | `#c28b1e` |
| `primaryHover` | ❌ | `#f08c3a` | `#a37213` |
| `background` | ✅ | `#faf7f2` | `#faf7f2` |
| `card` | ✅ | `#ffffff` | `#ffffff` |
| `textPrimary` | ✅ | `#3c3c3b` | `#3c3c3b` |
| `textMuted` | ❌ | `#6a6a66` | `#7f8c8d` |
| `border` | ❌ | `#e2dfd9` | `#e2e8f0` |
| `borderSoft` | ❌ | `#e2dfd9` | `#edf2ee` |
| `success` | ❌ | `#4a7c59` | `#10b981` |
| `danger` | ❌ | `#d64933` | `#ef4444` |
| `info` | ✅ | `#3b82f6` | `#3b82f6` |
| `warning` | ✅ | `#f59e0b` | `#f59e0b` |
| `white` | ✅ | `#ffffff` | `#ffffff` |

**7 tokens aligned, 6 require Phase 24A-1C visual decision.**

## Validation Results

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
— 9 tests passed, 0 failed
```

## No-Consumption Proof

- No web source file imports from `shared/`
- No mobile source file imports from `shared/`
- `web/vite.config.js` — unchanged
- `mobile/metro.config.js` — unchanged
- `mobile/tsconfig.json` — unchanged
- No `package.json` or lock file changed
- No rendered visual value changed

## Architecture Decision Deferred

The consumption approach (direct imports vs generated adapters vs workspace) is documented in `shared/README.md` but intentionally not selected. Phase 24A-1B will make that decision with implementation evidence.

## Next Steps

| Phase | Scope | Approval Required |
|-------|-------|-------------------|
| 24A-1B | Wire platform adapters (no visual change) | Separate Matthew approval |
| 24A-1C | Resolve 6 misaligned color tokens (user-visible) | Separate Matthew approval + deployment approval |
