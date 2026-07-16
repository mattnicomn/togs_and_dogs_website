# Phase 1A: Client/Household Backend Compatibility Layer (Pre-Deploy)

**Date:** 2026-07-15
**Status:** Pre-Deploy (awaiting deployment approval)
**Type:** Backend compatibility layer (no schema migration)
**Scope:** Normalize client records into household-compatible view model

---

## 1. Canonical Data Decision

- Existing `CLIENT#` records remain the canonical household records
- `household_id = client_id` — no separate HOUSEHOLD entity
- No DynamoDB migration, backfill, or dual writes
- No new PK/SK patterns introduced
- All existing routes and client behavior remain backward compatible
- This is a compatibility layer, not the final key schema

## 2. Response Contract

`normalize_client_response(client)` adds:
- `household_id` (= client_id)
- `account_status` (derived)

Preserves ALL existing fields for backward compatibility:
- `PK`, `SK` (used by frontend for record operations)
- `cognito_sub` (used by frontend for account-status display)
- `cognito_status`, `portal_enabled`, `is_active`, `cognito_enabled`
- All display fields (display_name, email, phone, address, notes, etc.)

This is an additive normalization — no fields are removed.

## 3. Profile State vs Account Status — Semantic Distinction

### Profile State (admin-managed, stored on DynamoDB CLIENT record)

| Field | Meaning |
|-------|---------|
| `is_active = true` | Client profile is active |
| `is_active = false` | Client profile is archived/inactive |

### Account Status (identity-derived, computed at read time)

| Status | Derivation |
|--------|-----------|
| `profile_only` | No email, no Cognito link |
| `invite_available` | Has email, no Cognito link |
| `invitation_sent` | Cognito user in FORCE_CHANGE_PASSWORD |
| `linked_active` | Cognito linked + cognito_enabled=true |
| `linked_disabled` | Cognito linked + cognito_enabled=false |
| `orphaned_identity` | cognito_sub set but Cognito status is DELETED/COMPROMISED/UNKNOWN/empty |
| `unlinked` | Previously linked, explicitly unlinked (legacy marker) |

### Key Identity Fields After Merge

| Field | Source | Meaning |
|-------|--------|---------|
| `is_active` | DynamoDB CLIENT record | Profile active/archived (admin action) |
| `cognito_enabled` | Cognito user `Enabled` field (merged during GET) | Identity enabled/disabled |
| `cognito_status` | Cognito user `UserStatus` field (merged during GET) | Lifecycle state (CONFIRMED, FORCE_CHANGE_PASSWORD, etc.) |
| `cognito_sub` | DynamoDB or Cognito merge | Cognito identity link |
| `portal_enabled` | Set to true when Cognito match found | Client portal access |
| `is_virtual` | Set to true for Cognito-only users (no DynamoDB profile) | Virtual user marker |

### Critical Semantic Rules

- `linked_disabled` means the **Cognito identity** is disabled — NOT that the profile is archived
- An archived profile (`is_active=false`) with an enabled Cognito account remains `linked_active`
- For virtual Cognito-only users (no DynamoDB profile), `is_active` carries the Cognito `Enabled` value
- No browser-provided or client-supplied value may determine account status
- Account status is derived exclusively from trusted server-side merged data

## 4. Account-Status Precedence (Decision Order)

```
1. cognito_status == 'UNLINKED' or cognito_sub == 'unlinked'
   → unlinked

2. is_virtual == true
   → linked_active (if is_active) or linked_disabled (if not is_active)
   [For virtual users, is_active carries Cognito Enabled]

3. cognito_sub exists and != 'unlinked':
   a. cognito_status == 'FORCE_CHANGE_PASSWORD'
      → invitation_sent
   b. cognito_status in (CONFIRMED, RESET_REQUIRED, EXTERNAL_PROVIDER):
      - cognito_enabled == false → linked_disabled
      - otherwise → linked_active
   c. cognito_status in (DELETED, COMPROMISED, UNKNOWN, ''):
      → orphaned_identity
   d. Any other status:
      - cognito_enabled == false → linked_disabled
      - otherwise → linked_active

4. No cognito_sub:
   a. Has email → invite_available
   b. No email → profile_only
```

## 5. Semantic Defect in Commit 77a273a (Corrected)

Commit `77a273a` incorrectly derived `linked_disabled` from the profile `is_active` field. This conflated profile-archived state with Cognito-disabled state. An archived client with an enabled Cognito account would have been incorrectly labeled `linked_disabled`.

**Correction (Phase 1A.1):**
- The handler now merges `cognito_enabled` from the matched Cognito user's `Enabled` field
- `derive_account_status` uses `cognito_enabled` (not `is_active`) for the `linked_disabled` derivation
- Profile state and identity state remain separate concerns

## 6. Handler Integration

GET /admin/clients (in `admin_handler.py`):
- Performs one bounded DynamoDB query (`PK = COMPANY#{id}, SK begins_with CLIENT#`)
- Fetches and merges Cognito group users (filtered by `custom:company_id` in multi mode)
- Merges `cognito_status`, `cognito_username`, `cognito_enabled`, `cognito_sub`, `portal_enabled`
- Applies `normalize_client_response` to every merged client
- Returns `{"clients": [...]}` with household_id and account_status on each record

## 7. Query Performance

- One bounded DynamoDB query for client records
- One bounded Cognito group lookup per client group
- No per-client pet query
- No per-client request query
- No table scan
- No N+1 behavior
- `pet_count` and `request_count` are **deferred**

## 8. Test Coverage

### Compatibility Helper Tests (17 tests)
- 9 account-status derivation tests (all states including corrected linked_disabled)
- 8 response normalization tests (household_id, field preservation, missing fields, no DB writes)

### Handler Integration Tests (27 tests)
- household_id presence and equals client_id
- account_status presence
- PK, SK, cognito_sub preserved
- Display fields preserved
- Legacy/minimal records serialize safely
- linked_active (enabled Cognito, active profile)
- linked_disabled (disabled Cognito — NOT archived profile)
- Archived profile with enabled Cognito is NOT linked_disabled
- invitation_sent (FORCE_CHANGE_PASSWORD)
- orphaned_identity (missing Cognito)
- profile_only (no email)
- invite_available (has email)
- profile_only vs invite_available distinct
- unlinked status
- Virtual Cognito user (active and disabled)
- Tenant isolation (Tenant A cannot see Tenant B)
- No DynamoDB writes
- No HOUSEHOLD records created
- Single query (no N+1)
- No per-client pet or request queries
- Pagination structure intact
- cognito_enabled merged correctly (true and false)

### Test-Isolation Defect (Corrected)

The original handler-integration test file used module-level `os.environ.setdefault('TENANT_RESOLUTION_MODE', 'multi')`. This leaked process-wide during pytest collection, causing 69 otherwise-passing tests to fail with `TenantDisabled` errors in the same pytest session.

**Root cause:** Module-level `os.environ.setdefault` persists for the lifetime of the Python process. Tests collected after the handler-integration module inherited `TENANT_RESOLUTION_MODE=multi` without mocking `require_active_tenant`.

**Correction:** Replaced module-level environment assignment with a function-scoped `autouse` fixture using `monkeypatch.setenv()`, which automatically restores the original environment after each test completes.

**Minimal reproduction:**
- Handler-integration tests alone: 27 passed
- Handler-integration tests followed by previously affected tests: 32 passed (no pollution)

### Full Backend Suite Comparison

| Metric | Baseline (5c296e7) | Corrected Candidate (3c2efb9 + isolation fix) |
|--------|--------------------|--------------------------------------------|
| Collected | 685 | 712 |
| Passed | 614 | 641 |
| Failed | 71 | 71 |
| Warnings | 94 | 94 |

- Candidate adds 27 tests (handler-integration) and 27 additional passes
- Exact failing node-ID sets match between baseline and candidate
- **Candidate-only failures: 0**
- No production application behavior was changed by the test-isolation correction

### Bounded Validation Totals
- Phase 1A focused tests: **44 passed, 0 failed**
- Broader relevant suite (identity, orphaned, tenant isolation, client limits): **63 passed, 5 failed**
- All 5 failures are baseline-confirmed (same node IDs fail at 5c296e7):
  - 3 in test_r11e: missing require_active_tenant mock (from Release 20E)
  - 2 in test_r18l: booking counter mock assertion mismatch
- Python compile: both changed backend files compile cleanly

## 9. Rollback

Remove `common/client_view.py` and the `cognito_enabled` merge line in admin_handler. Existing behavior is unchanged since this is an additive normalization layer.

## 10. Deployment Scope (Read-Only Audit)

Expected deployment when approved:
- Backend code-package update only (shared Lambda archive)
- All 13 Lambda functions share one deployment archive — a future Terraform apply will refresh all 13 Lambda resources in-place even though only GET /admin/clients behavior changed
- No API Gateway route changes
- No environment-variable changes
- No IAM policy changes
- No Cognito configuration changes
- No DynamoDB schema or migration changes
- No frontend deployment required

## 11. Next Steps

- Deployment-readiness documentation update (broader continuity documents)
- Terraform plan (requires separate explicit Matthew approval)
- Production deployment (requires separate explicit Matthew approval)
- Production smoke validation
- Phase 1B: Frontend Client Management parity using this normalized response

## 12. What Was NOT Changed

- ❌ No DynamoDB schema change
- ❌ No migration
- ❌ No new entities
- ❌ No Terraform changes
- ❌ No frontend changes
- ❌ No Cognito changes
- ❌ No production data modification
- ❌ No deployment
