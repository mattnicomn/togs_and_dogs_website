# Release 3: Client Management Automation — Validation Report

**Date:** 2026-05-12  
**Status:** Fully Accepted — live production validation passed 2026-05-13  
**Reviewer:** Kiro (code review + build validation + idempotency fix)

---

## 1. Files Changed

| File | Status | Lines |
|------|--------|-------|
| `src/backend/common/client_profile.py` | **NEW** (untracked) | 230 lines |
| `src/backend/handlers/review_handler.py` | Modified | +79/-17 vs baseline |
| `web/src/components/AdminDashboard.jsx` | Modified | +91/-5 vs baseline |

### Untracked Files (all releases, expected)

| File | Release | Purpose |
|------|---------|---------|
| `src/backend/common/cascade.py` | R1 | REQ → JOB cascade utility |
| `src/backend/common/client_profile.py` | R3 | Auto-profile creation/linking |
| `docs/planning/` | R1-R3 | Planning documents |
| `docs/release-notes/release-1-scheduling-record-integrity.md` | R1 | Release notes |

All untracked files are expected and should be included in deployment.

---

## 2. Validation Results

| Check | Result |
|-------|--------|
| `py -m py_compile` (client_profile.py, review_handler.py) | ✅ ALL PASS |
| `npm run build` | ✅ 90 modules, 849ms, no errors |
| Bundle hash: `index-BsqhmnrN.js` | ✅ Confirms changes included |

---

## 3. Auto-Profile Trigger Review

### Confirmed: Only triggers when ALL conditions are met

| Condition | Enforced By | Status |
|-----------|-------------|--------|
| `new_status == 'APPROVED'` | review_handler.py line check | ✅ |
| `workflow_type == WorkflowType.CUSTOMER_INTAKE` | review_handler.py line check | ✅ |
| Request NOT already linked (`linked_client_profile_id` absent) | Idempotency guard | ✅ |
| Caller is owner/admin | review_handler.py RBAC (line ~70) | ✅ |

### Confirmed: Does NOT trigger for

| Scenario | Why | Status |
|----------|-----|--------|
| VISIT_BOOKING approval | `workflow_type != CUSTOMER_INTAKE` | ✅ |
| Staff assignment | `new_status != 'APPROVED'` | ✅ |
| Quote changes | `new_status != 'APPROVED'` | ✅ |
| Cancellation | `new_status != 'APPROVED'` | ✅ |
| Archive/Trash | `new_status != 'APPROVED'` | ✅ |
| Restore to Approved (already linked) | Idempotency guard skips | ✅ |

### Idempotency on Restore to Approved

**Issue found during review:** The original implementation did NOT check if the request was already linked. Repeated approvals (e.g., Cancel → Restore to Approved) would re-run auto-profile, potentially duplicating `intake_request_ids` entries and incrementing `request_count`.

**Fix applied:** Added `already_linked = request_item.get('linked_client_profile_id')` guard. If the request already has a linked profile, auto-profile is skipped with `ALREADY_LINKED` status.

---

## 4. Email Normalization and Matching Review

| Check | Status | Implementation |
|-------|--------|----------------|
| Email normalized to lowercase | ✅ | `.lower().strip()` |
| Exact match only | ✅ | `==` comparison on normalized values |
| Phone match does NOT auto-link | ✅ | Phone not checked in matching logic |
| Name match does NOT auto-link | ✅ | Name not checked in matching logic |
| Missing email → skip | ✅ | Returns `SKIPPED_NO_EMAIL` |
| Multiple email matches → NEEDS_REVIEW | ✅ | Returns without linking |

---

## 5. Client Profile ID Safety Review

### Confirmed: IDs are explicitly separate

| Field | Location | Format | Purpose |
|-------|----------|--------|---------|
| `client_id` on REQ record | REQ SK: `CLIENT#<uuid>` | UUID generated at submission | Intake/submission identifier |
| `client_id` on Client Profile | Profile SK: `CLIENT#client_<8char>` | `client_<uuid[:8]>` | Profile identifier |
| `linked_client_profile_id` on REQ | New R3 field | `client_<uuid[:8]>` | Links REQ → Profile |

The auto-profile utility generates a NEW `client_id` for the profile (`client_{uuid[:8]}`) that is completely independent of the REQ record's `client_id`. The linkage is stored in the separate `linked_client_profile_id` field.

**No reuse of request-level client_id as profile ID.** ✅

---

## 6. Existing Profile Update Behavior Review

| Check | Status | Notes |
|-------|--------|-------|
| Existing active profile linked, not duplicated | ✅ | `len(matches) == 1` and `is_active == True` → link only |
| Inactive profile reactivated if not manually disabled | ✅ | Checks `cognito_status == 'deleted'` or `admin_disabled == True` |
| Manually disabled profile NOT reactivated | ✅ | Returns `SKIPPED_MANUALLY_DISABLED` |
| `source_request_id` preserved once set | ✅ | Only set on creation, not on subsequent links |
| `latest_request_id` updates correctly | ✅ | Updated via `_update_profile_request_metadata` |
| `request_count` increments safely | ✅ | Uses DynamoDB `ADD` (atomic increment) |
| `intake_request_ids` idempotency | ⚠️ See below | Uses `list_append` — could duplicate on re-link |

### Idempotency Note on `intake_request_ids`

If the same request is linked to the same profile twice (shouldn't happen with the idempotency guard, but theoretically possible if `linked_client_profile_id` is manually cleared), `list_append` would add the request_id again. This is acceptable for MVP — the list is informational and the guard prevents normal duplicate scenarios.

**Risk: LOW.** The idempotency guard on the review_handler prevents this in normal operation.

---

## 7. Fail-Safe Behavior Review

| Scenario | Approval Succeeds? | Request Marked? | Status |
|----------|-------------------|-----------------|--------|
| Profile query fails (DynamoDB error) | ✅ Yes | `FAILED` | ✅ |
| Profile creation fails (put_item error) | ✅ Yes | `FAILED` | ✅ |
| Profile link update fails | ✅ Yes | Warning logged | ✅ |
| Entire auto-profile throws exception | ✅ Yes | `FAILED` | ✅ |
| Audit append fails | ✅ Yes | Warning logged | ✅ |

The outer try/except in review_handler catches ANY exception from the auto-profile call and marks the request as FAILED without blocking the approval response.

---

## 8. Audit Trail Review

| Event | Logged To | Status |
|-------|-----------|--------|
| Profile auto-created | REQ audit_log + CloudWatch | ✅ `CLIENT_PROFILE_AUTO_CREATED` |
| Profile linked (existing) | REQ audit_log + CloudWatch | ✅ `CLIENT_PROFILE_LINKED` |
| Profile reactivated | REQ audit_log + CloudWatch | ✅ `CLIENT_PROFILE_REACTIVATED` |
| Multiple matches detected | REQ audit_log + CloudWatch | ✅ `CLIENT_PROFILE_MULTIPLE_MATCHES` |
| Skipped (no email) | CloudWatch only | ✅ (no audit entry, just print) |
| Failed | REQ audit_log + CloudWatch | ✅ `CLIENT_PROFILE_FAILED` |

### Audit Log Size Concern

Each auto-profile event adds one entry to the REQ `audit_log` list. Since auto-profile only runs once per request (idempotency guard), this adds at most 1 entry per request. Combined with existing status change entries (~5-10 per request lifecycle), the audit_log will not grow unbounded.

**Risk: NONE** for normal use.

---

## 9. Client Management UI Search Review

### Implemented Search Fields

| Field | Covered | Notes |
|-------|---------|-------|
| Client name (`display_name`) | ✅ | |
| Email | ✅ | |
| Phone | ✅ | |
| Notes | ✅ | |
| Pet name | ❌ | Not on client profile record — requires PET# join |
| Breed | ❌ | Not on client profile record — requires PET# join |

### Known Limitation: Pet Name/Breed Search

Pet data lives in separate `PET#` records (different PK/SK). The client list only loads `COMPANY#/CLIENT#` records. Searching by pet name or breed would require either:
- Loading all PET records alongside clients (expensive scan)
- A server-side search endpoint with cross-entity join
- A denormalized `pet_names` field on the client profile

**Recommendation:** Defer pet name/breed search to Release 4 when multi-pet restructuring is addressed. The current search covers the most common lookup patterns (name, email, phone).

### UI Behavior

| Check | Status |
|-------|--------|
| Search input renders | ✅ |
| Filters client list in real-time | ✅ |
| Shows result count when filtering | ✅ |
| Empty search shows all clients | ✅ |
| No match shows empty grid (no error) | ✅ |
| Auto-created badge shows only when `auto_created == true` | ✅ |
| Request count badge handles 0/null cleanly | ✅ (`c.request_count > 0` guard) |
| Existing card layout preserved | ✅ |

---

## 10. Cognito Non-Change Confirmation

| Check | Status |
|-------|--------|
| No `cognito.admin_create_user` calls in client_profile.py | ✅ |
| New profiles have `cognito_sub: None` | ✅ |
| New profiles have `cognito_status: 'not_linked'` | ✅ |
| New profiles have `portal_enabled: False` | ✅ |
| No Cognito SDK imports in client_profile.py | ✅ |
| No welcome emails sent by auto-profile | ✅ |

---

## 11. Edge Cases Reviewed

| Edge Case | Handling | Status |
|-----------|----------|--------|
| Restore to Approved (already linked) | Idempotency guard skips auto-profile | ✅ |
| Same client submits multiple intakes | First approval creates profile, subsequent link to it | ✅ |
| Admin manually creates profile before approval | Auto-profile finds by email, links (no duplicate) | ✅ |
| Client uses different email for new intake | Creates new profile (email is primary key) | ✅ Acceptable |
| Email field is whitespace-only | Treated as empty → SKIPPED_NO_EMAIL | ✅ |
| Company has no client profiles yet | Empty query result → creates new | ✅ |
| DynamoDB throttling during query | Exception caught → FAILED, approval continues | ✅ |

---

## 12. Known Limitations

1. **Pet name/breed search not implemented** — requires cross-entity data loading. Deferred to Release 4.
2. **`intake_request_ids` not deduplicated** — uses `list_append`. Idempotency guard prevents normal duplicates. Edge case: manual clearing of `linked_client_profile_id` could cause re-append.
3. **Phone matching not surfaced** — phone is not collected on the current intake form, so phone-based duplicate warnings are not triggered. Future enhancement when intake collects phone.
4. **No admin UI for link_status warnings** — `NEEDS_REVIEW` and `FAILED` statuses are stored on the REQ record but not prominently displayed in the admin list. The approval response message includes the warning text. Future enhancement: add a visual indicator in the request list.

---

## 13. Deployment Recommendation

**READY FOR DEPLOY.**

One bug was found and fixed during review (idempotency on Restore to Approved). All validation passes after the fix. The implementation is fail-safe, does not modify Cognito, does not grant portal access, and preserves all existing RBAC.

### Deployment Steps
1. `terraform apply` — updates Lambda code (backend zip hash changes)
2. `aws s3 sync web/dist/ s3://...` — updates frontend
3. CloudFront invalidation
4. Manual smoke test: approve a test CUSTOMER_INTAKE and verify profile appears in Client Management

### Post-Deploy Verification
- Approve a new customer intake → confirm profile auto-created
- Check Client Management → new profile visible with "Auto-created" badge
- Check profile fields → `portal_enabled: false`, `cognito_sub: null`
- Search by name → filters correctly
- Approve same email again (if test available) → links, doesn't duplicate
