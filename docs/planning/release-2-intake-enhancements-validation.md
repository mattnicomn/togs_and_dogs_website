# Release 2: Intake Enhancements — Validation Report

**Date:** 2026-05-11  
**Status:** Validated — Ready for Deploy  
**Reviewer:** Kiro (code review + build validation)

---

## 1. Files Changed

| File | Lines | Change |
|------|-------|--------|
| `src/backend/handlers/intake_handler.py` | +88/-1 | Staff-options endpoint, visit_windows array, preferred_sitter, normalize helper |
| `src/backend/handlers/job_handler.py` | +3 | Copy visit_windows, preferred_sitter, preferred_sitter_name to JOB |
| `web/src/components/IntakeForm.jsx` | +130/-3 | Multi-select checkboxes, preferred sitter dropdown, staff options loading |
| `web/src/components/AdminDashboard.jsx` | +8/-1 | Multi-window display, preferred sitter badge |
| `web/src/components/CareCard.jsx` | +9/-1 | Multi-window display, preferred sitter in scheduling tab |
| `web/src/components/MasterScheduler.jsx` | +5/-1 | "Has Sitter Preference" filter option |
| `web/src/api/client.js` | +4 | `getStaffOptions()` API call |

---

## 2. Validation Results

| Check | Result |
|-------|--------|
| `npm run build` | ✅ 90 modules, 303ms, no errors |
| `py -m py_compile` (intake_handler, job_handler) | ✅ ALL PASS |
| Bundle hash changed (index-BWn5aBcw.js) | ✅ Confirms new code included |

---

## 3. Staff-Options Security Review

### Endpoint: `POST /requests` with `{ action: "staff-options" }`

| Security Check | Status | Notes |
|----------------|--------|-------|
| Returns only sanitized fields | ✅ | Only `id` (staff_id) and `name` (display_name) |
| Does NOT expose email | ✅ | Email field not included in response |
| Does NOT expose phone | ✅ | Phone field not included |
| Does NOT expose Cognito username | ✅ | Not included |
| Does NOT expose role/permissions | ✅ | Not included |
| Does NOT expose protected account flags | ✅ | Not included |
| Does NOT expose internal metadata | ✅ | No PK, SK, company_id, cognito_sub, notes, etc. |
| Does NOT create a request record | ✅ | Returns immediately before any record creation |
| Does NOT trigger notifications | ✅ | Returns before notification logic |
| Does NOT trigger calendar/job creation | ✅ | Returns before Step Function trigger |
| Does NOT require authentication | ✅ | Handled before auth checks in handler |
| Handles empty staff list gracefully | ✅ | Returns `{"staff_options": []}` on error or empty |
| Returns only active/assignable staff | ✅ | Filters `is_active == True` and `is_assignable != False` |

### staff_id Safety Assessment

The `staff_id` field format is `staff_<8-char-uuid>` (e.g., `staff_a1b2c3d4`). This is:
- ✅ Randomly generated (UUID-based)
- ✅ Not derived from email
- ✅ Not a Cognito identifier
- ✅ Not an internal DynamoDB key (PK/SK use `COMPANY#` and `STAFF#` prefixes)
- ✅ Opaque — reveals no information about the staff member
- ✅ Safe for public exposure

**Verdict: staff_id is safe as a public identifier.**

---

## 4. Backward Compatibility Review

### Old records with only `visit_window` (string)

| Display Location | Handling | Status |
|-----------------|----------|--------|
| Admin Request List | `(item.visit_windows \|\| [item.visit_window \|\| 'ANYTIME']).join(', ')` | ✅ Falls back to array wrapping legacy string |
| CareCard Visit tab | `(pet.visit_windows \|\| [pet.visit_window \|\| 'ANYTIME']).join(', ')` | ✅ Same fallback |
| MasterScheduler | Uses `start_date` for filtering, not visit_window | ✅ Unaffected |
| Backend normalization | `_normalize_visit_windows()` handles both formats | ✅ |

### New records with `visit_windows` array

| Scenario | Stored Value | Display |
|----------|-------------|---------|
| ANYTIME only | `["ANYTIME"]` | "ANYTIME" |
| Morning + Evening | `["MORNING", "EVENING"]` | "MORNING, EVENING" |
| All specific | `["MORNING", "MIDDAY", "AFTERNOON", "EVENING"]` | "MORNING, MIDDAY, AFTERNOON, EVENING" |

---

## 5. Intake Submission Behavior Review

| Check | Status |
|-------|--------|
| Legacy `visit_window` string still stored | ✅ |
| New `visit_windows` array stored | ✅ |
| ANYTIME mutually exclusive (backend) | ✅ `_normalize_visit_windows` enforces |
| ANYTIME mutually exclusive (frontend) | ✅ Checkbox logic clears others |
| Invalid window values rejected | ✅ Filtered against `VALID_VISIT_WINDOWS` |
| `preferred_sitter` stored as informational | ✅ |
| `preferred_sitter_name` stored for display | ✅ |
| Does NOT set `worker_id` | ✅ No worker_id in record creation |
| Does NOT assign staff | ✅ No assignment logic triggered |
| Does NOT alter lifecycle/status | ✅ Status remains PENDING_REVIEW |
| Step Function still triggered | ✅ Unchanged |
| Notifications still triggered | ✅ Unchanged |

---

## 6. JOB Propagation Review

Fields copied from REQ to JOB on creation (`job_handler.py`):

| Field | Copied | Status |
|-------|--------|--------|
| `start_date` | ✅ | Pre-existing |
| `end_date` | ✅ | Release 1 |
| `visit_window` | ✅ | Release 1 |
| `visit_windows` | ✅ | Release 2 (new) |
| `preferred_sitter` | ✅ | Release 2 (new) |
| `preferred_sitter_name` | ✅ | Release 2 (new) |
| `service_type` | ✅ | Pre-existing |
| `client_name` | ✅ | Pre-existing |
| `client_email` | ✅ | Pre-existing |
| `pet_info` | ✅ | Pre-existing |

---

## 7. Frontend Behavior Review

### IntakeForm

| Check | Status |
|-------|--------|
| Checkbox group replaces single dropdown | ✅ |
| ANYTIME clears specific windows | ✅ |
| Selecting specific windows clears ANYTIME | ✅ |
| Supports Morning + Evening multi-select | ✅ |
| "No preference" default for sitter | ✅ |
| Staff-options API failure handled gracefully | ✅ Returns empty array, hides dropdown |
| Submission not blocked if staff-options fails | ✅ Preferred sitter is optional |
| Preferred sitter dropdown hidden if no options | ✅ `staffOptions.length > 0` guard |

### Admin Visibility

| Check | Status |
|-------|--------|
| Request List shows multi-window | ✅ `visit_windows.join(', ')` with fallback |
| Preferred sitter badge shows separately | ✅ Only when `preferred_sitter_name` exists |
| CareCard Visit tab shows all windows | ✅ |
| CareCard Scheduling tab shows preferred sitter | ✅ "Client Prefers: [name]" |
| MasterScheduler "Has Sitter Preference" filter | ✅ Filters by `!!i.preferred_sitter` |
| Filter doesn't hide normal visits when not active | ✅ Only applies when `__HAS_PREFERENCE__` selected |

---

## 8. Bug Found and Fixed During Review

**Issue:** CareCard had a comparison `pet.preferred_sitter !== pet.worker_id` to show "(different from assigned)". Since `preferred_sitter` uses `staff_id` format and `worker_id` uses email format, they would NEVER match — the indicator would always show even when the preferred sitter IS the assigned worker.

**Fix:** Removed the comparison logic. CareCard now simply shows "Client Prefers: [name]" without attempting cross-identifier comparison. This is correct because the two ID systems (staff_id vs email) are not directly comparable.

**Impact:** Display-only. No data or logic affected.

---

## 9. Known Limitations

1. **Preferred sitter uses staff_id, assignment uses email** — These are different identifier systems. The preferred sitter is purely informational and displayed by name. No cross-system matching is attempted.

2. **No "different from assigned" indicator** — Removed due to ID mismatch. Future enhancement could add a lookup to resolve staff_id → email for comparison, but this is low priority since the admin can visually compare names.

3. **Staff-options endpoint shares the POST /requests path** — Uses `{action: "staff-options"}` to avoid Terraform changes. This is slightly unconventional but safe since the action check happens before any validation or record creation.

4. **No rate limiting on staff-options** — The endpoint is public. For a small business with low traffic this is acceptable. If abuse is a concern, API Gateway throttling can be configured later.

5. **Timing notes field** — Added to the form but was already supported by the payload structure (field existed in the backend). This is a low-risk UX improvement.

---

## 10. Deployment Recommendation

**READY FOR DEPLOY.**

All validation passes. One bug was found and fixed during review (CareCard ID comparison). The staff-options endpoint is secure — only exposes opaque staff_id and display_name. No lifecycle, RBAC, or infrastructure changes.

### Deployment Steps
1. `terraform apply` — updates Lambda code (backend zip hash changes)
2. `aws s3 sync web/dist/ s3://...` — updates frontend
3. CloudFront invalidation
4. Manual smoke test: submit intake with multi-window + preferred sitter

### Post-Deploy Verification
- Submit public intake with MORNING + EVENING → confirm stored as array
- Submit with preferred sitter selected → confirm displays in admin list
- View old record → confirm legacy visit_window still renders
- Confirm staff-options response contains no sensitive data (browser Network tab)
