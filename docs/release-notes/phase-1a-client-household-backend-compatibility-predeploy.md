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
- `account_status` (derived from existing fields)

Removes:
- `PK`, `SK` (internal DynamoDB keys)
- `cognito_sub` (internal identity detail)

Preserves all other existing fields.

## 3. Account Status Model

| Status | Derivation |
|--------|-----------|
| `profile_only` | No email, no Cognito link |
| `invite_available` | Has email, no Cognito link |
| `invitation_sent` | Cognito user in FORCE_CHANGE_PASSWORD |
| `linked_active` | Cognito CONFIRMED + is_active + portal_enabled |
| `linked_disabled` | Cognito linked but is_active=false |
| `orphaned_identity` | Cognito sub set but status is DELETED/unknown |
| `unlinked` | Previously linked, explicitly unlinked |

## 4. Query Performance

- GET /admin/clients uses a bounded DynamoDB query (`PK = COMPANY#{id}, SK begins_with CLIENT#`)
- No unbounded scans
- No per-client N+1 sub-queries
- `pet_count` and `request_count` are **deferred** — they would require per-client queries or a GSI/aggregation not currently available

## 5. Tests (17 new)

- 9 account-status derivation tests (all states)
- 8 response normalization tests (household_id, key removal, missing fields, no DB writes)

## 6. Rollback

Remove `common/client_view.py` and any handler references. Existing behavior is unchanged since this is an additive normalization layer.

## 7. Next Release

Phase 1B: Frontend Client Management parity using this normalized response.

## 8. What Was NOT Changed

- ❌ No DynamoDB schema change
- ❌ No migration
- ❌ No new entities
- ❌ No Terraform changes
- ❌ No frontend changes
- ❌ No Cognito changes
- ❌ No production data modification
