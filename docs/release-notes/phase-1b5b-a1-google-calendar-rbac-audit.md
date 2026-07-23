# Phase 1B.5B-A.1 Google Calendar Tenant-Integration RBAC — Independent Audit

**Date:** 2026-07-23
**Reviewer:** Kiro
**Commit:** `9e522473` — remediation: secure tenant-level Google Calendar integration routes and frontend controls

---

## Repository State
- Branch: main, HEAD: `9e522473f4f20176fe8fe86f6ec1e5c107c7fad2`
- origin/main: synchronized
- Working tree: clean, stash: empty

## Files Changed (8efd153 → 9e52247)
| File | Type |
|------|------|
| `src/backend/handlers/google_auth_handler.py` | Backend RBAC enforcement |
| `tests/backend/test_google_auth_rbac.py` | Backend RBAC tests (new) |
| `web/src/components/AdminDashboard.jsx` | Frontend capability gate |
| `web/tests/GoogleCalendarRBAC.test.jsx` | Frontend RBAC tests (new) |
| `docs/release-notes/phase-1b5b-a1-google-calendar-access-control-remediation.md` | Documentation |
| `docs/project-continuity/current-state.md` | Continuity update |
| `docs/project-continuity/document-map.md` | Map update |
| `docs/release-notes/index.md` | Index update |

---

## Frontend Capability Audit: CORRECT ✅

New capability: `canManageGoogleCalendarIntegration: ['owner', 'admin'].includes(role)`

**Staff see:** Scheduler, calendar health banner (degraded-status text), integration status card — all read-only.
**Staff do NOT see:** Connect Calendar button, Reconnect Calendar button. Both locations gated by `capabilities.canManageGoogleCalendarIntegration`.
**Owner/admin retain:** Connect/Reconnect actions in both banner and integration card.
**Client/platform_admin:** Cannot reach `/admin` tenant-integration mutation controls through normal navigation.

Disconnect was already removed in a prior hotfix (intentional comment preserved).

---

## Backend Authorization Audit: CORRECT ✅

### GET /admin/auth/google (initiate_auth)
```python
role = get_effective_role(event)
if role not in ['owner', 'admin']:
    return error(403, "Forbidden: Insufficient permissions to manage calendar integration.", event)
```
Enforced BEFORE OAuth state creation, DynamoDB write, or authorization URL generation.

### DELETE /admin/auth/google (disconnect_auth)
Same role check enforced BEFORE token deletion, revocation, or any Secrets Manager mutation.

### GET /admin/auth/status and /health
NO role restriction — staff can read status. This is correct (read-only awareness).

### Callback (/admin/auth/callback)
Protected by one-time state token + tenant context. No interactive-role check needed (callback is triggered by Google's redirect after an authorized user initiated OAuth).

---

## Authorization-Helper Classification: INLINE_CHECK_EQUIVALENT_BUT_HELPER_PREFERRED

The implementation uses `get_effective_role(event)` + inline `if role not in ['owner', 'admin']` rather than a shared `require_owner_or_admin(event)` helper. This is functionally equivalent and secure. A shared helper would reduce future drift risk but is not a correctness issue. No bounded correction required.

---

## Test Results (Independently Reproduced)

### Frontend
- Legacy: **96 passed, 0 failed**
- Component/integration: **104 passed, 0 failed** (9 test files)
- Combined: **200 passed, 0 failed**

### Backend (focused RBAC)
- `test_google_auth_rbac.py`: **3 passed, 0 failed**

### Backend (full suite)
- Collected: **772**
- Passed: **703**
- Failed: **69** (established baseline)
- Warnings: 108
- **Correction-only regressions: ZERO** ✅

Comparison against pre-correction baseline (769/700/69/108): +3 collected, +3 passed — exactly the 3 new RBAC tests. Established 69 failures unchanged.

---

## Release-Sequencing Recommendation: C

This Google Calendar RBAC correction should remain a **separate documented security remediation** without renumbering. It is not part of the pet-edit hotfix scope (Phase 1B.5B-A.1 Option B). They address different production defects and should deploy together but are logically distinct for audit and closeout purposes.

---

## Recommendation: **READY_FOR_MATTHEW_DEPLOYMENT_PREPARATION_DECISION**

All criteria met:
- ✅ Staff blocked from Connect/Reconnect at both frontend locations
- ✅ Backend denies staff/client/platform_admin/unknown roles on mutation routes (403)
- ✅ Read-only status remains accessible to staff
- ✅ Callback remains protected by one-time state
- ✅ 200 frontend tests pass, 703 backend tests pass
- ✅ Zero correction-only regressions
- ✅ No OAuth, token, Secrets Manager, or production integration mutation occurred
- ✅ Correction is LOCAL ONLY / NOT DEPLOYED

### Next Gate
Matthew approves deployment preparation (this remediation deploys alongside the Phase 1B.5B-A.1 pet-edit hotfix in the same Lambda package + frontend bundle).
