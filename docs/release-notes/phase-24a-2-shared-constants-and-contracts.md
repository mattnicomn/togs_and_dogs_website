# Phase 24A-2: Shared Constants and API Contracts

**Status:** ✅ COMPLETE (contracts defined; not yet consumed by applications)
**Date:** 2026-07-25
**Starting HEAD:** `fc937b2`

---

## Summary

Defined shared, platform-neutral contracts for request statuses, service types, pet fields, and API paths. These contracts are authoritative references for future Phase 24A consumption, but no existing application imports were replaced in this phase because the contracts serve as reference rather than runtime dependencies. The discrepancies discovered between web and mobile (particularly role mapping) are documented for separate resolution.

## Deliverables

| File | Purpose |
|------|---------|
| `shared/constants/request-statuses.json` | Backend-authoritative request status machine identifiers with categories and metadata |
| `shared/constants/service-types.json` | Backend-authoritative service type identifiers with labels and durations |
| `shared/constants/pet-fields.json` | Client read/write field lists and validation limits (backend-authoritative) |
| `shared/contracts/api-paths.json` | Relative API endpoint paths (no hostnames or secrets) |
| `shared/validate-constants.mjs` | 17-test validation suite for all constant/contract files |

## Backend Authority Sources

| Contract | Backend Source |
|----------|---------------|
| Request statuses | `src/backend/common/status.py` — `RequestStatus` enum |
| Service types | `src/backend/common/google_calendar.py` — `SERVICE_DURATIONS`, `FRIENDLY_SERVICE_NAMES` |
| Pet fields | `src/backend/handlers/pet_handler.py` — client PUT allowlist |
| API paths | `modules/api/main.tf` — API Gateway resource definitions |

## Values NOT Shared (Discrepancies Requiring Separate Approval)

| Item | Discrepancy | Disposition |
|------|-------------|-------------|
| Role mapping (`getEffectiveRole`) | Web: `admin` group → `'admin'` role. Mobile: `admin` group → `'owner'` role. | **Critical behavioral difference** — requires separate design review |
| Status display labels | Web uses workflow-context-sensitive labels (e.g., "New Request" vs "New Registration"). Mobile uses simplified static labels. | Platform-specific — not safe to unify without UX review |
| Service labels in CareCard | Uses non-backend identifiers (`WALKING`, `OTHER`) | Web-specific legacy — requires separate cleanup |
| Account-status labels | Web and backend use different keys and labels | Web-specific admin concern — not shared to mobile |
| Status badge colors | Web uses CSS class logic. Mobile uses inline hex colors. | Deferred to Phase 24A-1C (visual alignment) |

## Phase 1B.5C-A Boundary

The `pet-fields.json` contract documents the `PUT /client/pets/{petId}` allowlist as defined in committed backend source. The field `clientPetEditApiAvailability` is explicitly set to `"pending-phase-1B5C-A-deployment"` — the endpoint is not production-available until that deployment occurs.

## Validation Results

```
✔ request-statuses.json parses as valid JSON
✔ status identifiers use UPPER_SNAKE_CASE
✔ status identifiers are unique
✔ status categories use the allowlist
✔ status synonyms reference existing statuses or are known legacy values
✔ required status properties exist
✔ service-types.json parses as valid JSON
✔ service identifiers use UPPER_SNAKE_CASE
✔ service identifiers are unique
✔ services have required properties
✔ pet-fields.json parses as valid JSON
✔ pet field names are unique within each list
✔ pet field limits reference valid write fields
✔ api-paths.json parses as valid JSON
✔ API paths are relative and contain no hostname
✔ API paths contain no secrets or environment data
✔ contract metadata is present in all files
— 17 tests passed, 0 failed
```

Existing validations also confirmed passing: color contract (9/9), color adapters (7/7), web tests (209/209).

## Next Steps

| Phase | Scope | Approval |
|-------|-------|----------|
| 24A-3 | Mobile test foundation (Jest, RNTL, mocks) | Standard implementation approval |
| 24A-1C | Visual token alignment (6 mismatched colors) | Separate approval + deployment approval |
