# Release 2: Intake Enhancements

**Deployed:** 2026-05-11  
**Environment:** Production  
**CloudFront Invalidation:** I2YA9IO9L93L65RLQBS563UJQN

---

## Files Deployed

### Backend (Lambda code update via Terraform)
| File | Change |
|------|--------|
| `src/backend/handlers/intake_handler.py` | Staff-options endpoint, visit_windows array, preferred_sitter fields |
| `src/backend/handlers/job_handler.py` | Copy visit_windows and preferred_sitter to JOB records |

### Frontend (S3 + CloudFront)
| File | Change |
|------|--------|
| `web/src/components/IntakeForm.jsx` | Multi-select checkboxes, preferred sitter dropdown |
| `web/src/components/AdminDashboard.jsx` | Multi-window display, preferred sitter badge |
| `web/src/components/CareCard.jsx` | Multi-window in Visit tab, preferred sitter in Scheduling tab |
| `web/src/components/MasterScheduler.jsx` | "Has Sitter Preference" filter option |
| `web/src/api/client.js` | `getStaffOptions()` API call |

---

## Behavior Changed

### 1. Preferred Visit Window — Multi-Select
- **Before:** Single dropdown (Morning, Midday, Afternoon, Evening, Anytime)
- **After:** Checkbox group allowing multiple selections (e.g., Morning + Evening)
- ANYTIME is mutually exclusive — selecting it clears specific windows, and vice versa
- Stored as `visit_windows: ["MORNING", "EVENING"]` array
- Legacy `visit_window` string preserved for backward compatibility

### 2. Preferred Sitter — New Optional Field
- **Before:** No way to express sitter preference on intake
- **After:** Optional dropdown on public intake form showing active/assignable sitter names
- Purely informational — does NOT auto-assign staff
- Admin retains full control over actual assignment
- Displayed as "Prefers: [name]" badge in admin views

### 3. Public Staff-Options Endpoint
- **Before:** Staff list only available to authenticated admin users
- **After:** Sanitized `POST /requests` with `{action: "staff-options"}` returns only display names
- Security: No email, phone, Cognito, role, or internal metadata exposed
- Returns only `id` (opaque staff_id) and `name` (display name)

### 4. Admin Display Enhancements
- Request List shows all selected visit windows (comma-separated)
- Request List shows preferred sitter badge when set
- CareCard Visit tab shows multi-window selections
- CareCard Scheduling tab shows "Client Prefers: [name]" alongside assigned staff
- MasterScheduler has "Has Sitter Preference" filter option

### 5. Timing Notes
- Optional timing notes field now visible on intake form Step 2
- Was already supported by backend payload structure — now exposed in UI

---

## Live Validation Results (AG Production Smoke Test — 2026-05-12)

**Status: ALL PASS**

| Category | Result | Notes |
|----------|--------|-------|
| Public Intake Form | ✅ PASS | Multi-select works, ANYTIME clears others, Morning + Evening works |
| Admin Dashboard | ✅ PASS | Multi-window displays, CareCard shows preference, no auto-assign |
| Security Audit | ✅ PASS | staff-options returns only `id` and `name`, no sensitive data |
| Master Scheduler | ✅ PASS | "Has Sitter Preference" filter live and functional |
| Release 1 Regression | ✅ PASS | No duplicate REQ/JOB rows, Data Issues clean |

### Test Records Created During Validation

| Record | Email | Windows | Sitter | Status |
|--------|-------|---------|--------|--------|
| Validation Test One | validation1@example.com | Morning + Evening | No preference | Archived (cleanup) |
| Validation Test Two | validation2@example.com | ANYTIME | Prefers: Matthew Nico | Archived (cleanup) |

These records were created for production smoke testing and have been archived via normal admin actions.

---

## Known Limitations

1. **Preferred sitter uses staff_id, assignment uses email** — Different identifier systems. The preferred sitter is displayed by name only. No cross-system matching attempted.

2. **No "match/mismatch" indicator** — CareCard shows preferred sitter and assigned staff separately without indicating whether they match. Future enhancement could add lookup.

3. **Staff-options shares POST /requests path** — Uses `{action: "staff-options"}` to avoid Terraform API Gateway changes. Unconventional but safe.

4. **No rate limiting on staff-options** — Public endpoint. Acceptable for low-traffic small business. API Gateway throttling available if needed.

5. **Timing notes field** — Exposed in UI but not prominently displayed in admin views yet. The data is stored and available for future admin display enhancement.

---

## Rollback Instructions

### Backend Rollback
```bash
git stash -- src/backend/handlers/intake_handler.py src/backend/handlers/job_handler.py
# Re-run terraform apply to deploy previous code
terraform apply -auto-approve
```

### Frontend Rollback
```bash
git stash -- web/src/components/IntakeForm.jsx web/src/components/AdminDashboard.jsx web/src/components/CareCard.jsx web/src/components/MasterScheduler.jsx web/src/api/client.js
npm run build  # in web/
aws s3 sync web/dist/ s3://togs-and-dogs-prod-toganddogs-hosting --delete --profile usmissionhero-website-prod
aws cloudfront create-invalidation --distribution-id E35L00QPA2IRCY --paths "/*" --profile usmissionhero-website-prod
```

### Risk Assessment
- **Rollback is safe.** No schema changes, no data migration.
- **Records created with visit_windows array** will still exist but display correctly via fallback logic even after rollback (falls back to `visit_window` string).
- **preferred_sitter fields** on records are harmless if frontend doesn't display them.

---

## Release 3 Readiness

**Release 3 can begin after live validation passes.**

Release 3 planned scope:
- Structured per-pet fields (breed, age, feeding, medication, behavior)
- Vet & emergency contact fields on intake
- Client profile automation (auto-create on approval)
- Quote/payment inline editing
- Multi-pet per owner support

None of these conflict with Release 2 changes.
