# Release 8U: Staff Profile Duplicate/Test Account Cleanup — Planning Document

> **Status: PLANNING ONLY — DO NOT IMPLEMENT UNTIL MATTHEW APPROVES**
> No DynamoDB mutations, Cognito mutations, backend, web, mobile, Terraform, AWS, S3, CloudFront, Postmark, or Google Calendar changes during this planning phase.

---

## 1. Background & Motivation

During **Release 8T** validation, the staff mobile Upcoming schedule showed zero visits despite records appearing assigned on the web Admin Dashboard. Root cause investigation revealed:

1. A **typo staff profile** (`mattnicomn10@yahoocom`, missing the dot) existed in DynamoDB with `is_assignable = True` and `cognito_sub = None`. It had no corresponding Cognito user.
2. The **correct staff profile** (`mattnicomn10@yahoo.com`) had `is_assignable = False`, hiding it from the web assignment dropdown.
3. New test bookings were therefore assigned to the typo profile's email as `worker_id`.
4. The mobile backend uses **exact string matching** on `worker_id` against the authenticated staff user's Cognito email claim — so the typo `worker_id` never matched, returning zero records.

The typo profile (`staff_test_user` / `mattnicomn10@yahoocom`) has since been **removed from DynamoDB** (confirmed by production inventory run on 2026-06-06), but:

- **Orphaned `REQ#` and `JOB#` records** still reference `worker_id = 'mattnicomn10@yahoocom'`.
- **No backend guardrail** currently prevents staff profiles with invalid email formats or no Cognito sub from appearing in the assignment dropdown.
- The cleanup and guardrail gap need to be formally addressed to prevent recurrence.

---

## 2. Production Inventory (Read-Only, Run 2026-06-06)

### 2A. Current DynamoDB Staff Profiles

| SK | Display Name | Email | Valid Email | is_assignable | is_active | cognito_sub |
|---|---|---|---|---|---|---|
| `STAFF#cognito_admin@toganddogs.com` | Admin_Root | `admin@toganddogs.com` | ✅ Yes | True | True | `74b86488-...` |
| `STAFF#cognito_mattnicomn10@gmail.com` | Matthew Nico | `mattnicomn10@gmail.com` | ✅ Yes | True | True | `b4a89428-...` |
| `STAFF#cognito_mattnicomn10@yahoo.com` | Staff Test User | `mattnicomn10@yahoo.com` | ✅ Yes | True | True | `f4485448-...` |
| `STAFF#cognito_ryanwyork@gmail.com` | Ryan York | `ryanwyork@gmail.com` | ✅ Yes | True | True | `249884e8-...` |
| `STAFF#staff_829e01ba` | USmissionhero | `mbn@usmissionhero.com` | ✅ Yes | True | True | `e4f84428-...` |

**Finding:** The typo profile (`staff_test_user` / `mattnicomn10@yahoocom`) is **no longer present** in DynamoDB. All 5 remaining profiles have valid email formats. No profiles are missing a `cognito_sub`.

### 2B. Current Cognito User Pool (`us-east-1_counlsXGU` — `togs-and-dogs-prod-admin-pool`)

| Group | Username | Email | Status | Enabled |
|---|---|---|---|---|
| `Staff` | `mattnicomn10@yahoo.com` | `mattnicomn10@yahoo.com` | CONFIRMED | ✅ |
| `Staff` | `mattnicomn10@gmail.com` | `mattnicomn10@gmail.com` | CONFIRMED | ✅ |
| `Admin` | (admin users) | — | — | — |
| `owner` | (owner users) | — | — | — |

**Finding:** No unexpected users in Cognito. `mattnicomn10@yahoo.com` is the only valid staff test account.

### 2C. Orphaned Records Referencing Typo `worker_id`

| Record Type | PK | SK | status | start_date | service_type | client_name |
|---|---|---|---|---|---|---|
| `REQ#` | `REQ#d9c4d980-bf21-4cc3-a08b-2a4628dad112` | `CLIENT#client_1697162f` | ASSIGNED | 2026-06-30 | WALK_30MIN | Justbeingbrea |
| `JOB#` | `JOB#21d63d97-26a5-4585-bdae-c1573e615e15` | `REQ#d9c4d980-...` | ASSIGNED | 2026-06-30 | — | — |

**Note:** A second REQ (`REQ#c1631d01`, the Jun 20–21 overnight) also previously referenced the typo `worker_id`, but it appears to have been corrected or superseded during 8T validation setup. The inventory confirms only 1 REQ and 1 JOB remain with the typo `worker_id` as of 2026-06-06.

**These are test records** created by `mattnicomn10@gmail.com` during 8T validation. They reference a non-existent staff profile. They are **not client-facing production bookings**.

---

## 3. Risk Assessment

| Risk | Severity | Likelihood | Notes |
|---|---|---|---|
| Orphaned REQ/JOB records mislead future admin dashboard views | Low | Medium | Status is ASSIGNED but staff profile is gone — confusing but not breaking |
| Mobile staff scoping returns these records for no user | None | Certain | `worker_id` doesn't match any real login |
| Accidental deletion of a real client booking | **High** | Low if scoped carefully | Must scope delete to test records only |
| Guardrail gap allows new invalid profiles in the dropdown | Medium | Medium | No email validation on staff creation |
| Backend changes for guardrails break existing assignment flow | Medium | Low | Additive validation only |

---

## 4. Proposed Actions

### Action 1: Archive/Deactivate the Orphaned Test REQ & JOB Records

**Scope:** The 2 orphaned test records (`REQ#d9c4d980` and `JOB#21d63d97`) created during 8T validation.

**Decision:** Do **not** hard-delete these records. Instead, update their `status` to `ARCHIVED` or `CANCELLED` (matching the backend's existing filter exclusion logic) so they are excluded from all list views and mobile scoping queries without losing audit history.

**Why not delete:**
- DynamoDB hard deletes are irreversible.
- The records are test artifacts but still part of the audit trail.
- The backend already excludes `DELETED` and `ARCHIVED` status records from `GET /admin/requests`.

**Command (DO NOT RUN UNTIL APPROVED — see Section 9):**
```python
# Archive orphaned test REQ
table.update_item(
    Key={'PK': 'REQ#d9c4d980-bf21-4cc3-a08b-2a4628dad112', 'SK': 'CLIENT#client_1697162f'},
    UpdateExpression='SET #s = :s, updated_at = :ts, archived_reason = :reason',
    ExpressionAttributeNames={'#s': 'status'},
    ExpressionAttributeValues={
        ':s': 'ARCHIVED',
        ':ts': '<timestamp>',
        ':reason': 'Test record created during R8T validation - worker_id references removed typo profile'
    }
)

# Archive orphaned test JOB
table.update_item(
    Key={'PK': 'JOB#21d63d97-26a5-4585-bdae-c1573e615e15', 'SK': 'REQ#d9c4d980-bf21-4cc3-a08b-2a4628dad112'},
    UpdateExpression='SET #s = :s, updated_at = :ts, archived_reason = :reason',
    ExpressionAttributeNames={'#s': 'status'},
    ExpressionAttributeValues={
        ':s': 'ARCHIVED',
        ':ts': '<timestamp>',
        ':reason': 'Test record created during R8T validation - worker_id references removed typo profile'
    }
)
```

### Action 2: Add Backend Guardrail — Exclude Invalid Profiles from Assignment Dropdown

**Scope:** `src/backend/handlers/admin_handler.py` — the `GET /admin/staff` handler that populates the assignment dropdown.

**Current behavior:** Returns all profiles where `is_assignable = True`, regardless of whether the email is a valid format or whether a matching Cognito user exists.

**Proposed behavior:** When returning the staff list for assignment, additionally filter to profiles where:
1. `email` matches a basic email format regex (`[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}`).
2. `cognito_sub` is not `None` and not the `'unlinked'` sentinel (established in R8S).

This prevents profiles without a real Cognito account from ever appearing in the dropdown.

**Risk:** Additive filter only — existing valid profiles are unaffected. The filter is applied only at query time; no DynamoDB records are modified.

### Action 3: Add Backend Guardrail — Validate `worker_id` on Assignment Write

**Scope:** `src/backend/handlers/assignment_handler.py` — the `POST /admin/assign` handler.

**Proposed behavior:** Before writing `worker_id` to the REQ/JOB record, verify that a staff profile exists in DynamoDB with `email = worker_id` and `is_assignable = True`. If no matching profile is found, return a `400 Bad Request` with a descriptive error. This prevents a typo or stale ID from being persisted as `worker_id`.

**Risk:** Additive validation — valid assignments are unaffected. Invalid assignments are rejected at write time instead of silently persisted.

### Action 4: No Cognito Changes Required

All current Cognito users are clean and correctly configured. No Cognito mutations are needed.

### Action 5: No Frontend Changes Required

The web Admin Dashboard assignment dropdown already reads from `GET /admin/staff` — if Action 2's backend guardrail filters invalid profiles, the dropdown is automatically clean. No frontend-only changes needed.

---

## 5. What We Are Explicitly NOT Doing

| Action | Decision | Reason |
|---|---|---|
| Hard-delete `REQ#d9c4d980` | ❌ Not doing | Irreversible; archive is safer |
| Hard-delete `JOB#21d63d97` | ❌ Not doing | Irreversible; archive is safer |
| Migrate/reassign orphaned records to real staff | ❌ Not doing | These are test records, not real client bookings |
| Delete any Cognito user | ❌ Not doing | No invalid Cognito users exist |
| Add a migration to retroactively fix all historical `worker_id` values | ❌ Not doing | Only 1 orphaned test record remains — not worth a migration |
| Add a DynamoDB constraint or TTL | ❌ Not doing | DynamoDB doesn't support column-level constraints; guardrail belongs in the application layer |

---

## 6. Files to Change (Implementation Phase Only)

| File | Change |
|---|---|
| `src/backend/handlers/admin_handler.py` | Add email format + cognito_sub validation filter to `GET /admin/staff` staff list for assignment dropdown |
| `src/backend/handlers/assignment_handler.py` | Add `worker_id` profile existence validation before writing assignment |
| `tests/backend/test_r8u_staff_cleanup.py` | New test file covering guardrail behavior |
| *(no web, mobile, Terraform, or infra changes)* | — |

---

## 7. Validation Checklist

All steps use the test staff account `mattnicomn10@yahoo.com`.

### Automated
- [ ] `pytest tests/backend/test_r8u_staff_cleanup.py` — all pass
- [ ] `pytest tests/backend/` — full suite, no regressions
- [ ] `npm run build` — web build passes

### Manual — Web Admin Dashboard
- [ ] Open Staff Management. Confirm `mattnicomn10@yahoo.com` (Staff Test User) is listed with Active status.
- [ ] Open an APPROVED booking. Click Assign Staff. Confirm the dropdown contains `mattnicomn10@yahoo.com` and all other valid staff.
- [ ] Confirm the dropdown does NOT contain any profile with an invalid email format or no Cognito login.
- [ ] Assign the booking to `mattnicomn10@yahoo.com`. Confirm assignment succeeds.
- [ ] Confirm the orphaned `REQ#d9c4d980` record no longer appears in the ASSIGNED list (status is ARCHIVED).

### Manual — Mobile (Staff User)
- [ ] Sign into Expo Go as `mattnicomn10@yahoo.com`.
- [ ] Confirm the newly assigned booking appears in Upcoming.
- [ ] Tap the booking — Booking Details opens without logout.
- [ ] Mark Completed — succeeds, visit disappears from Upcoming.
- [ ] Confirm no other staff visits are affected.

### Negative / Regression
- [ ] Admin Approve, Assign Staff, Change Staff — all unaffected.
- [ ] `GET /admin/staff` called by admin — returns all valid assignable profiles.
- [ ] `POST /admin/assign` with a valid `worker_id` — succeeds.
- [ ] `POST /admin/assign` with a typo `worker_id` (e.g., `mattnicomn10@yahoocom`) — returns `400 Bad Request`.

---

## 8. Rollback / No-Change Plan

If any step fails or validation cannot be completed:

1. **Orphaned record archive step:** If archiving the test REQ/JOB records causes any unexpected side effects, the status can be reverted to `ASSIGNED` with a second `update_item` call. No data is lost.
2. **Backend guardrail for `GET /admin/staff`:** The filter is additive. Removing it restores the previous behavior exactly. No data is changed.
3. **Backend guardrail for `POST /admin/assign`:** Removing the validation check restores previous behavior. No data is changed.
4. **If in doubt:** Do nothing. The current state (typo profile removed, orphaned records still `ASSIGNED` but unreachable) is stable and non-breaking. No client-facing functionality is impaired.

---

## 9. AG Implementation Prompt

> ⚠️ **DO NOT RUN UNTIL MATTHEW APPROVES**

---

AG, approved to proceed with Release 8U implementation.

Scope:
- Archive orphaned test records only — do not hard-delete any DynamoDB records.
- Add backend validation guardrails to `admin_handler.py` and `assignment_handler.py`.
- Write new automated tests in `tests/backend/test_r8u_staff_cleanup.py`.
- No mobile changes.
- No web frontend changes.
- No Terraform changes.
- No Cognito mutations.
- No S3/CloudFront changes.

Step 1 — Archive orphaned test records:
- Update `REQ#d9c4d980-bf21-4cc3-a08b-2a4628dad112` / `CLIENT#client_1697162f` → `status = ARCHIVED`, add `archived_reason`.
- Update `JOB#21d63d97-26a5-4585-bdae-c1573e615e15` / `REQ#d9c4d980-...` → `status = ARCHIVED`, add `archived_reason`.
- Re-run the inventory script to confirm both records now show `ARCHIVED`.

Step 2 — Backend guardrail for `GET /admin/staff` (assignment dropdown):
- In `admin_handler.py`, after fetching staff profiles for the list, additionally filter out profiles where:
  - `email` does not match a basic email format.
  - `cognito_sub` is `None` or the string `'unlinked'`.
- This filter applies only to the assignment dropdown context, not to the full Staff Management list view (which should still show all profiles for admin visibility).

Step 3 — Backend guardrail for `POST /admin/assign`:
- In `assignment_handler.py`, before writing `worker_id`, query DynamoDB for a staff profile with `email = worker_id` and `is_assignable = True`.
- If no matching profile is found, return `400 Bad Request` with error: `"No assignable staff profile found for worker_id: <worker_id>"`.

Step 4 — Tests:
- Write `tests/backend/test_r8u_staff_cleanup.py` covering:
  - `GET /admin/staff` excludes profiles with invalid email.
  - `GET /admin/staff` excludes profiles with `cognito_sub = None`.
  - `POST /admin/assign` with valid `worker_id` succeeds.
  - `POST /admin/assign` with typo `worker_id` returns `400`.
- Run `pytest tests/backend/test_r8u_staff_cleanup.py` and `pytest tests/backend/` — all must pass.

Step 5 — Web build:
- Run `npm run build` — must pass.

Step 6 — Stage and commit only:
- `src/backend/handlers/admin_handler.py`
- `src/backend/handlers/assignment_handler.py`
- `tests/backend/test_r8u_staff_cleanup.py`

Commit: `fix(admin): add staff assignment guardrails and archive typo test records`

Pause for Matthew's validation before deploying.

---

## 10. Open Questions for Matthew

1. **`mattnicomn10@yahoo.com` display name:** The Cognito profile name is `Staff Test User` and the DynamoDB display name is `Staff Test User`. Is this the intended display name for the real staff test account, or should it be renamed to something more descriptive (e.g., `Matthew (Staff Test)`)?
2. **`Admin_Root` profile (`admin@toganddogs.com`):** This profile has `is_assignable = True`. Should it remain assignable, or should it be set to `is_assignable = False` since it is an administrative/system account?
3. **`USmissionhero` profile (`mbn@usmissionhero.com`):** SK is `STAFF#staff_829e01ba` (opaque ID, not `cognito_`-prefixed). Should this profile's SK be reviewed for consistency with the `STAFF#cognito_<email>` pattern used by all other profiles?
4. **Scope of the `GET /admin/staff` filter:** Should the invalid-profile filter apply only to the assignment dropdown (i.e., only when `is_assignable = True` is checked), or also to the full Staff Management list view used by the admin dashboard?
