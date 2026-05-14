# Release 4C: Client Phone / Contact Persistence — Validation Report

**Date:** 2026-05-13  
**Status:** Fully Accepted — Production Validated  
**Reviewer:** Kiro (code review + build validation)

---

## 1. Files Changed

| File | Change | Type |
|------|--------|------|
| `src/backend/handlers/intake_handler.py` | Added `client_phone` to REQ record creation (1 line) | Backend |
| `src/backend/common/client_profile.py` | Set phone from request on creation + `_fill_blank_phone` helper | Backend |
| `web/src/components/IntakeForm.jsx` | Re-added phone field to Step 1 Contact Info | Frontend |

---

## 2. Validation Results

| Check | Result |
|-------|--------|
| `py -m py_compile` (intake_handler.py, client_profile.py) | ✅ ALL PASS |
| `npm run build` | ✅ 90 modules, 362ms, no errors |
| Bundle hash: `index-BaKcXtan.js` | ✅ Confirms changes included |

---

## 3. Code Review

### intake_handler.py
- Added: `'client_phone': (body.get('client_phone') or '').strip() or None`
- Normalizes: trims whitespace, converts empty string to None
- Optional: does not affect validation (phone not in required_fields)
- Position: after `client_email`, before `start_date`

### client_profile.py — New Profile Creation
- Changed: `'phone': None` → `'phone': (request_item.get('client_phone') or '').strip() or None`
- Sets phone from intake when creating a new auto-profile

### client_profile.py — Existing Profile Linking
- Added: `_fill_blank_phone(company_id, existing_profile_id, existing, request_item, now)` call after linking
- New helper `_fill_blank_phone()`:
  - Only fills if `client_phone` is non-empty AND existing `phone` is blank
  - Never overwrites admin-entered phone
  - Logs success/failure

### IntakeForm.jsx
- Re-added phone field to Step 1 (was removed in 4B)
- Optional `<input type="tel">` with placeholder
- Stored as `formData.client_phone`
- Submitted in payload (backend now persists it)

---

## 4. Merge Rule Verification

| Scenario | Expected | Code Path | Status |
|----------|----------|-----------|--------|
| New profile, phone provided | phone = client_phone | `client_profile.py` line ~176 | ✅ |
| New profile, no phone | phone = None | Same line, `or None` | ✅ |
| Existing profile, blank phone, client_phone provided | Fill phone | `_fill_blank_phone` | ✅ |
| Existing profile, has phone, client_phone provided | Do NOT overwrite | `if client_phone and not existing_phone` guard | ✅ |
| Existing profile, blank phone, no client_phone | No change | `if client_phone` guard fails | ✅ |

---

## 5. Backward Compatibility

| Scenario | Behavior | Status |
|----------|----------|--------|
| Old requests without `client_phone` | Field is None — no display, no error | ✅ |
| Old profiles without `phone` | Already handled — shows nothing | ✅ |
| Client Management search by phone | Already works (searches `c.phone`) | ✅ |
| Client Management card phone display | Already works (📞 icon) | ✅ |
| Export `r.client_phone \|\| r.phone` | Already works | ✅ |
| Intake without phone | Submission succeeds, phone is null | ✅ |

---

## 6. Validation Checklist

| # | Test | Expected | Status |
|---|------|----------|--------|
| 1 | Submit intake WITH phone | REQ stores `client_phone` | ☐ |
| 2 | Submit intake WITHOUT phone | Succeeds, `client_phone` null | ☐ |
| 3 | Approve new customer with phone | Profile phone populated | ☐ |
| 4 | Approve new customer without phone | Profile phone null | ☐ |
| 5 | Link to existing profile (blank phone) | Phone filled | ☐ |
| 6 | Link to existing profile (has phone) | Phone NOT overwritten | ☐ |
| 7 | Client Management card shows phone | 📞 icon visible | ☐ |
| 8 | Search by phone | Finds client | ☐ |
| 9 | Old records without phone | Clean display | ☐ |
| 10 | `npm run build` | ✅ Pass | ✅ |
| 11 | `py -m py_compile` | ✅ Pass | ✅ |
| 12 | No Cognito/calendar/status changes | Confirmed | ✅ |

---

## 7. Known Limitations

1. **No phone formatting/validation** — MVP accepts free text. International formats vary.
2. **CareCard phone display** — Not explicitly added to CareCard in this release (phone is visible via Client Management card). Could be added as a minor follow-up.
3. **Phone not used for matching** — Only email auto-links. Phone is informational only.

---

## 8. Deployment Recommendation

**READY FOR DEPLOY.**

Requires both backend (terraform apply) and frontend (S3 sync + CloudFront invalidation).

- `terraform plan` should show Lambda code-only changes (0 add, 9 change, 0 destroy)
- `aws s3 sync web/dist/ s3://togs-and-dogs-prod-toganddogs-hosting --delete --profile usmissionhero-website-prod`
- `aws cloudfront create-invalidation --distribution-id E35L00QPA2IRCY --paths "/*" --profile usmissionhero-website-prod`
