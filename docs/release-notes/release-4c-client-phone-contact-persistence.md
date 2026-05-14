# Release 4C: Client Phone / Contact Persistence

**Deployed:** 2026-05-13  
**Environment:** Production  
**CloudFront Invalidation:** I47W7BZ58HR0YXEXVFRDA73ICU  
**Status:** Fully Accepted — Production Validated

---

## Files Deployed

### Backend (Lambda code update via Terraform)
| File | Change |
|------|--------|
| `src/backend/handlers/intake_handler.py` | Stores `client_phone` on REQ record |
| `src/backend/common/client_profile.py` | Sets phone on new profiles + fills blank phone on existing profiles |

### Frontend (S3 + CloudFront)
| File | Change |
|------|--------|
| `web/src/components/IntakeForm.jsx` | Optional phone field in Contact Info step |

---

## Behavior Changed

### 1. Intake Phone Collection
- **Before:** No phone field on intake form. Phone only entered manually in Client Management.
- **After:** Optional phone field in Step 1 (Contact Info). Submitted as `client_phone`.

### 2. REQ Record Storage
- **Before:** No `client_phone` field on request records.
- **After:** `client_phone` stored on REQ record (trimmed, null if empty).

### 3. Client Profile Phone Propagation
- **Before:** Auto-created profiles had `phone: None`. Existing profiles never received phone from intake.
- **After:**
  - New auto-created profiles: `phone` set from `client_phone`
  - Existing profiles with blank phone: filled from `client_phone`
  - Existing profiles with phone already set: NOT overwritten

### 4. Display
- Client Management cards already display phone (📞 icon) — no change needed
- Client Management search already includes phone — no change needed
- Export already references `r.client_phone || r.phone` — no change needed

---

## Live Validation Checklist

**Status: ALL PASS — Production validated 2026-05-13.**

| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | Phone field visible on intake | Optional input in Step 1 | ✅ Pass |
| 2 | Submit with phone | REQ stores `client_phone` | ✅ Pass |
| 3 | Submit without phone | Succeeds, `client_phone` null | ✅ Pass |
| 4 | Approve new customer with phone | Profile phone populated | ✅ Pass |
| 5 | Link to existing (blank phone) | Phone filled | Code-verified (no live test profile available) |
| 6 | Link to existing (has phone) | Phone NOT overwritten | Code-verified (no live test profile available) |
| 7 | Client Management shows phone | 📞 icon visible | ✅ Pass |
| 8 | Search by phone (555-0140) | Finds client | ✅ Pass |
| 9 | Old records without phone | Clean display | ✅ Pass |
| 10 | No console/API errors | Clean | ✅ Pass |

### Test Records

| Record | Email | Phone | Status |
|--------|-------|-------|--------|
| R4C Phone Validation One | r4c.phone.validation.one@example.com | 555-0140 | Archived via Admin UI |
| R4C No Phone Validation | r4c.no.phone.validation@example.com | (none) | Archived via Admin UI |

Cleanup completed through normal Admin UI behavior.

---

## Known Limitations

1. **No phone formatting/validation** — accepts free text. International formats vary.
2. **Phone not displayed in CareCard** — visible in Client Management cards. CareCard display is a minor follow-up.
3. **Phone not used for matching** — only email auto-links. Phone is informational.

---

## Rollback Instructions

```bash
# Backend
git checkout HEAD~1 -- src/backend/handlers/intake_handler.py src/backend/common/client_profile.py
terraform apply -auto-approve

# Frontend
git checkout HEAD~1 -- web/src/components/IntakeForm.jsx
npm run build
aws s3 sync web/dist/ s3://togs-and-dogs-prod-toganddogs-hosting --delete --profile usmissionhero-website-prod
aws cloudfront create-invalidation --distribution-id E35L00QPA2IRCY --paths "/*" --profile usmissionhero-website-prod
```

Records with `client_phone` already stored are harmless if field is removed.
