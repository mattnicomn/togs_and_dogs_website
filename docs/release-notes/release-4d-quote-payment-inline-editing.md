# Release 4D: Quote & Payment Inline Editing

**Deployed:** 2026-05-14  
**Environment:** Production  
**Status:** Fully Accepted — Production Validated After Hotfix  
**Type:** Frontend-only (no backend/Terraform changes)

---

## Files Deployed

| File | Change |
|------|--------|
| `web/src/components/CareCard.jsx` | Quoting tab: editable quote_amount, payment_status, deposit toggles, quote_notes |

---

## Behavior Changed

### 1. Pricing & Quote Tab — Now Editable
- **Before:** Quote amount and payment status were read-only display fields in CareCard.
- **After:** When admin clicks "Edit Record", the Pricing & Quote tab shows editable controls:
  - Quote amount: number input ($)
  - Payment status: dropdown with 9 options
  - Deposit required: checkbox
  - Deposit paid: checkbox
  - Quote notes: textarea

### 2. Payment Status Options
| Status | Satisfies Approval Gate? |
|--------|--------------------------|
| Not Requested | ❌ |
| Quote Sent | ❌ |
| Payment Pending | ❌ |
| Accepted | ✅ |
| Deposit Paid | ✅ |
| Paid in Full | ✅ |
| Partially Paid | ❌ |
| Refunded | ❌ |
| Waived | ❌ |

### 3. Save Flow
Uses existing `handleSave` → `updatePet()` → `PUT /admin/pets/{petId}`. No new API endpoints.

### 4. RBAC
- Owner/Admin: full edit access
- Staff: backend strips sensitive pricing fields (existing behavior)
- Client: no access

---

## Live Validation Checklist

| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | Edit quote_amount | Saves and displays | ☑ |
| 2 | Edit payment_status | Saves and displays | ☑ |
| 3 | Edit quote_notes | Saves and displays | ☑ |
| 4 | Toggle deposit_required | Saves | ☑ |
| 5 | Toggle deposit_paid | Saves | ☑ |
| 6 | Reopen shows saved values | Persisted | ☑ |
| 7 | Old records render cleanly | Defaults shown | ☑ |
| 8 | Approval gate unchanged | Works correctly | ☑ |
| 9 | No console errors | Clean | ☑ |

---

## Known Limitations

1. **No audit trail for quote/payment changes** — relies on PET# `updated_at` timestamp. Full audit deferred.
2. **Staff can see edit button but backend strips sensitive fields** — existing behavior, not a regression.
3. **Multi-pet editing still first-pet only** — quote/payment edits apply to the first pet's PET# record.

---

## Rollback

```bash
git checkout HEAD~1 -- web/src/components/CareCard.jsx
npm run build
aws s3 sync web/dist/ s3://togs-and-dogs-prod-toganddogs-hosting --delete --profile usmissionhero-website-prod
aws cloudfront create-invalidation --distribution-id E35L00QPA2IRCY --paths "/*" --profile usmissionhero-website-prod
```
