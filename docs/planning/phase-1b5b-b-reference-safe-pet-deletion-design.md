# Phase 1B.5B-B — Reference-Safe Pet Deletion Design Audit

**Date:** 2026-07-23
**Status:** DESIGN_ONLY_THEN_DEFER
**Type:** Design analysis and backlog sequencing

---

## Current State

- Phase 1B.5B-A and A.1 are CLOSED (deployed, validated 2026-07-22)
- Archive/Restore is operational (PUT with is_active toggle)
- **No DELETE pet route exists** in `pet_handler.py`
- No pet record has ever been permanently deleted in production
- Archived pets are hidden from new bookings but visible in admin with badge

---

## Complete Pet Reference Map

| Reference Source | Entity / Key | Relationship | If Pet Archived | If Pet Permanently Deleted | Safe to Leave? | Preferred Handling |
|-----------------|-------------|-------------|-----------------|---------------------------|----------------|-------------------|
| PET record itself | `PK=PET#<id>, SK=CLIENT#<cid>` | Authoritative | is_active=false | Record removed | — | Tombstone or delete |
| ClientPetIndex GSI | Partition=client_id, Sort=pet_id | Derived from PET item | Excluded by is_active filter | Entry disappears | — | Automatic |
| Client profile `pet_names_summary` | `COMPANY#<cid>, CLIENT#<cid>` | Cached/derived | Rebuilt by `_rebuild_pet_summary` (excludes archived) | Summary rebuilt without pet | ✅ | Auto-rebuild |
| Client profile `pet_breeds_summary` | Same | Cached/derived | Same | Same | ✅ | Auto-rebuild |
| REQ record `pet_ids` array | `REQ#<id>, CLIENT#<cid>` | Historical reference | Array unchanged | **Dangling reference** | ⚠️ | Block or tombstone |
| REQ record `pet_id` (legacy single) | Same | Historical reference | Unchanged | **Dangling reference** | ⚠️ | Block or tombstone |
| REQ record `pet_names` string | Same | Copy (human-readable) | Unchanged | Intact (name copy) | ✅ | No action needed |
| JOB record `pet_id` | `JOB#<id>, REQ#<rid>` | Copied reference | Unchanged | **Dangling reference** | ⚠️ | Block or tombstone |
| JOB record `pet_name` | Same | Copy (human-readable) | Unchanged | Intact (name copy) | ✅ | No action needed |
| Review handler M&G update | Direct GetItem on PET | Runtime lookup | Returns archived item | **GetItem fails (404)** | ⚠️ | Guard before access |
| Google Calendar event | External (no pet_id stored) | Indirect via booking | Unaffected | Unaffected | ✅ | No action |
| Payment/Stripe metadata | REQ-level only | No direct pet reference | Unaffected | Unaffected | ✅ | No action |
| Notification ledger | REQ-level | Includes pet_names copy | Unaffected | Intact (copy) | ✅ | No action |
| Export/offline backup | Full scan | Includes all records | Archived records included | Record absent | ⚠️ | Tombstone preferred |
| Audit log (REQ audit_log) | PET_PROFILE_WARNINGS entries | pet_id in log | Unchanged | Dangling but safe (log) | ✅ | No action |
| CareCard / frontend getPet | Direct GetItem | Runtime lookup | Returns item | **404** | ⚠️ | Handle gracefully |
| Admin client drawer | listAdminClientPets | Query-based | Excluded by is_active filter | Not returned | ✅ | Automatic |
| Client /my-pets | getClientPets | Query-based | Excluded | Not returned | ✅ | Automatic |
| New Visit modal | listAdminClientPets (active-only) | Query-based | Excluded | Not returned | ✅ | Automatic |

---

## Deletion-Policy Analysis

### Option A: Archive/Restore Only (RECOMMENDED)

- No permanent deletion ever
- Archived pets invisible in booking selection and client portal
- Historical references remain valid
- Zero dangling-reference risk
- Zero compliance/audit concern
- Zero recovery-window need
- Simplest to implement (already done)
- **Covers 99%+ of real business needs** — when would a pet care business need to permanently erase a pet record?

### Option B: Hard Delete When Zero References

- Check REQ.pet_ids and JOB.pet_id for the pet_id
- This requires a **Scan** or **Query across all REQs** — expensive and potentially incomplete
- Race condition: a booking could be approved between the reference check and deletion
- Adds backend complexity for a rarely-needed operation
- Benefit: frees DynamoDB storage (negligible for this scale)

### Option C: Tombstone/Anonymize

- Replace name/breed/notes with "Deleted Pet" but preserve pet_id
- Historical references resolve to a placeholder
- More complex than archive, similar benefit profile
- Useful for GDPR-style erasure if ever required

### Option D: Delayed Deletion with Recovery

- Mark for deletion → 30-day window → permanent removal
- Adds scheduled Lambda, state management, recovery UI
- Significant complexity for minimal operational value

### Option E: Platform/Support-Only Workflow

- Only platform_admin can permanently delete via a controlled tool
- Not tenant-facing
- Appropriate if rare cleanup is ever needed (e.g., test-data removal)

---

## Role-Policy Recommendation

| Role | Archive | Restore | Permanent Delete |
|------|---------|---------|-----------------|
| owner | ✅ | ✅ | ❌ (not recommended at this stage) |
| admin | ✅ | ✅ | ❌ |
| staff | ✅ | ✅ | ❌ |
| client | ❌ (request-based) | ❌ | ❌ |
| platform_admin | ✅ | ✅ | Future Option E if needed |

**Permanent deletion should NOT be available to any tenant-facing role at this time.** The operational value is near zero while the data-integrity risk is significant.

---

## Safety Requirements (If Ever Implemented)

These would be required for Options B–E:

1. Typed confirmation: "DELETE <pet_name>" to proceed
2. Explicit visual distinction from Archive
3. Reference check (all REQ.pet_ids, JOB.pet_id) before proceeding
4. Race-condition guard: conditional delete with version check
5. Idempotent repeat behavior (second DELETE of same ID returns success)
6. Authorization before any data access
7. Tenant isolation (PET must belong to caller's company)
8. Audit record: actor, timestamp, pet snapshot, reason
9. `_rebuild_pet_summary` called after deletion
10. 30-day soft-delete window before permanent removal (Option D)
11. Graceful frontend handling when getPet returns 404 after deletion
12. Historical bookings display pet_name copy, not live lookup

---

## Proposed API Contract (Design Only — NOT for implementation)

```
DELETE /admin/pets/{petId}?clientId={clientId}
Authorization: owner, admin
Request body: { "confirm_name": "Buddy", "reason": "duplicate" }
```

**Responses:**
- 200: `{ "deleted": true, "pet_id": "...", "archived_snapshot": true }`
- 409: `{ "blocked": true, "references": 3, "message": "Pet has 3 booking references. Archive instead." }`
- 403: Unauthorized role
- 404: Pet not found
- 400: Missing confirmation or mismatched name

---

## Backlog Sequencing Assessment

| Item | Priority | Value | Risk of Deferral |
|------|----------|-------|-----------------|
| Phase 1B.5B-A.1 pet-edit hotfix deployment | ✅ DONE | High | — |
| Google Calendar RBAC | ✅ DONE | Security | — |
| Customer pet editing (1B.5C) | Medium | User self-service | Low |
| Pet deletion (1B.5B-B) | **Low** | Rare operational need | **Near zero** |
| Staff email-field corrections | Medium | Data quality | Low |
| Booking saved-pet selection (1B.5E) | Medium-High | Booking UX | Medium |

**Archive already solves the real business problem.** A pet care business archives pets that are deceased, rehomed, or no longer serviced. Permanent deletion adds complexity without proportional business value.

---

## Recommendation: **DESIGN_ONLY_THEN_DEFER**

Phase 1B.5B-B should remain a documented design but NOT be implemented at this time because:

1. **Archive covers the business need.** Archived pets are hidden from bookings, client portal, and new-visit selection.
2. **Permanent deletion risks data integrity.** Dangling references in REQ.pet_ids, JOB.pet_id, and review_handler M&G lookups.
3. **Implementation cost is disproportionate.** Reference-checking requires scanning REQ records — expensive and race-prone.
4. **No user has requested permanent deletion.** No operational scenario requires it today.
5. **Higher-value work exists.** Customer pet editing (1B.5C) and booking saved-pet selection (1B.5E) deliver more user value.

If permanent deletion is ever needed (e.g., for test-data cleanup or GDPR), **Option E (platform-admin-only controlled workflow)** is the safest starting point.

---

## Next Approval Gate

**Matthew acknowledges the DESIGN_ONLY_THEN_DEFER recommendation** and confirms the next priority (e.g., Phase 1B.5C customer pet editing, Phase 1B.5E booking integration, or another backlog item).

No implementation approval is requested.
