# Release 7B: Admin Data Cleanup & UX Hardening — Plan

## Objective
Clean up test records from Release 7A validation, fix "Pet 1 (loading failed)" display issues, and polish the Client Management UX for offline/no-login clients.

---

## Phase 1: Test Record Cleanup (~1-2 hours)

### Scope
Identify and safely remove test records created during Release 7A validation.

### Safe Cleanup Approach
1. **Identify test records** by scanning for:
   - Client profiles with names like "Offline Test", "Manual Test", "7A Test", or similar test patterns
   - REQ records with `source: "admin_created"` and test client names
   - PET records linked to test client_ids
   - JOB records linked to test request_ids
2. **Verify each record is NOT real customer data** by checking:
   - `created_at` timestamp matches the 7A validation window
   - Client email is a test/internal address (e.g., `@usmissionhero.com`, `@example.com`)
   - No real booking history or payment data
3. **Cleanup order** (preserves referential integrity):
   - First: Move REQ records to DELETED status (soft-delete via Admin Dashboard)
   - Second: Purge REQ records (permanent delete via Trash → Purge)
   - Third: Archive or delete orphaned PET records
   - Fourth: Disable/delete test CLIENT profiles
4. **Do NOT use direct DynamoDB deletes** — use the Admin Dashboard UI or admin API to ensure cascade, audit, and notification behavior

### Acceptance Criteria
- [ ] All test records identified and listed
- [ ] No real customer data affected
- [ ] Cleanup performed via Admin Dashboard (not direct DB)
- [ ] DynamoDB scan confirms no orphaned test records remain
- [ ] Notification ledger entries for test records are acceptable (historical audit)

---

## Phase 2: Fix "Pet 1 (loading failed)" Display (~1-2 hours)

### Root Cause Analysis
The "Pet 1 (loading failed)" message appears in `AdminDashboard.jsx` line ~1928:
```javascript
return { pet_id: pid, client_id: ..., name: `Pet ${idx + 1} (loading failed)`, _fetchFailed: true };
```

This triggers when `getPet(pid, clientId)` fails. Likely causes:

| Cause | How to Verify | Fix |
|-------|--------------|-----|
| Pet record deleted but `pet_ids` still references it | Scan for REQ records with `pet_ids` containing non-existent PET# records | Remove orphaned pet_id from REQ record |
| Client_id mismatch | PET record has `SK: CLIENT#{X}` but REQ record uses `CLIENT#{Y}` | Fix the client_id reference |
| Test pet from 7A validation not cleaned up | Check if pet_id belongs to a test client | Delete the test pet |
| Backend returns 400/404 for valid pet | Check pet_handler response for edge cases | Fix backend if needed |

### Implementation
1. **AG scans** for REQ records where `pet_ids` contains IDs that don't resolve to PET# records
2. **Fix orphaned references** by removing invalid pet_ids from REQ records
3. **Optionally improve frontend** to show a clearer message: "Pet record not found — may have been deleted" instead of generic "loading failed"

### Acceptance Criteria
- [ ] No "Pet 1 (loading failed)" appears for any active/valid record
- [ ] Orphaned pet_id references cleaned from REQ records
- [ ] Frontend gracefully handles missing pet records without confusing the admin

---

## Phase 3: Client Management UX Polish for Offline Clients (~1-2 hours)

### Current State
The `getAccessStatus()` function already handles offline clients:
- `cognito_status === 'not_linked'` → shows "No Login" badge
- `portal_enabled === false` → client cannot access portal
- Creation mode "Create Profile Only (No Login)" exists in the UI

### Recommended Polish

| Improvement | Type | Effort |
|-------------|------|--------|
| Show "Offline Client" label instead of just "No Login" for clients with no email | Frontend | 30 min |
| Add "(no email)" indicator on client cards when email is blank/missing | Frontend | 15 min |
| Clarify "Link Login Account" button — only show when client has email | Frontend | 30 min |
| Add tooltip explaining what "No Login" means for new admins | Frontend | 15 min |
| Show `source: admin_created` badge on bookings created offline | Frontend | 30 min |

### Acceptance Criteria
- [ ] Offline clients are clearly distinguishable from portal-enabled clients
- [ ] "Link Login Account" is not confusingly shown for clients without email
- [ ] Admin understands at a glance which clients are offline vs. portal-enabled

---

## Phase 4: Operational Documentation (~30 min)

### Scope
Document the offline client management workflow in the operational guide.

**Create or update:** `docs/operations/offline-client-management.md`

**Contents:**
- How to create an offline client profile
- How to add pets for an offline client
- How to create a booking for an offline client
- How notifications work (or don't) for no-email clients
- How to later upgrade an offline client to portal access
- How to clean up test records safely

---

## Recommended AG Implementation Prompt

```
AG — begin Release 7B Phase 1: Test Record Cleanup.

1. Scan DynamoDB for records created during Release 7A validation:
   - CLIENT# records with test names or @example.com/@usmissionhero.com test emails created after [7A validation date]
   - REQ# records with source: "admin_created" linked to those test clients
   - PET# records linked to those test client_ids
   - JOB# records linked to those test request_ids

2. List all identified test records with PK/SK/status/client_name.

3. For each test record, verify it is NOT real customer data.

4. Clean up via Admin Dashboard:
   - Cancel active test bookings
   - Move test REQ records to Trash
   - Purge from Trash
   - Disable/delete test client profiles
   - Delete test pet records

5. After cleanup, scan to confirm no orphaned test records remain.

6. Check for any REQ records with pet_ids referencing non-existent PET# records (causes "Pet 1 loading failed").

Do not delete any record where client_name, email, or booking details suggest real customer data.
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Accidentally deleting real customer data | Very Low | High | Verify each record before deletion; use Admin Dashboard (not direct DB) |
| Orphaned references after cleanup | Low | UX confusion | Scan for orphans after cleanup |
| Frontend changes break existing views | Very Low | Medium | `npm run build` + browser validation |

---

## Files Likely Involved

| File | Phase | Change |
|------|-------|--------|
| DynamoDB (production data) | 1, 2 | Record cleanup via Admin Dashboard |
| `web/src/components/AdminDashboard.jsx` | 2, 3 | Pet loading fallback message + client UX polish |
| `docs/operations/offline-client-management.md` | 4 | NEW operational guide |

---

## Estimated Effort

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1: Test record cleanup | ~1-2 hours | Low |
| Phase 2: Fix pet loading failed | ~1-2 hours | Low |
| Phase 3: Client Management UX polish | ~1-2 hours | Very Low |
| Phase 4: Operational documentation | ~30 min | None |
| **Total** | **~4-6 hours** | |
