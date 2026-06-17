# Release 12R.2: Admin CareCard Blank Screen Hotfix

**Status:** Deployed
**Type:** Frontend hotfix
**Priority:** Urgent (admin request detail was broken)
**Commit:** `97a9619`
**Deployed:** Yes (S3 sync + CloudFront invalidation)

---

## Root Cause

Release 12R introduced a `useEffect` hook near the top of `CareCard.jsx` (line 38) that referenced `activePet` and `activePetIndex`. However, `activePet` is derived from `_normalizePets()` which is declared much later in the component body (line 169).

In JavaScript, referencing a `const`/`let` variable before its declaration causes a **temporal dead zone ReferenceError**. This crashed the entire CareCard component on render, causing a blank screen when clicking any request card.

```javascript
// BEFORE (broken — activePet not yet declared at this point):
useEffect(() => {
  const initialAmount = originItem.payment_amount_cents
    ? (originItem.payment_amount_cents / 100).toFixed(2)
    : activePet.quote_amount  // ← ReferenceError: activePet is not defined
      ? parseFloat(activePet.quote_amount).toFixed(2)
      : '';
  ...
}, [pet, activePetIndex]);  // ← activePetIndex also not yet declared
```

## Fix

Replaced `activePet.quote_amount` with `pet.quote_amount` (the `pet` prop is always available) and removed `activePetIndex` from the dependency array:

```javascript
// AFTER (fixed — uses pet prop directly):
useEffect(() => {
  const initialAmount = originItem.payment_amount_cents
    ? (originItem.payment_amount_cents / 100).toFixed(2)
    : (pet.quote_amount ? parseFloat(pet.quote_amount).toFixed(2) : '');
  ...
}, [pet]);
```

## Files Changed

| File | Change |
|------|--------|
| `web/src/components/CareCard.jsx` | Replace `activePet` reference with `pet` prop in useEffect |

## Validation

- Frontend build: ✅ Passed (`vite build` — 94 modules, 329ms)
- Only 1 file changed, 4 insertions, 5 deletions
- No backend/Terraform/Stripe/DynamoDB changes

## Deployment

| Step | Result |
|------|--------|
| S3 sync | ✅ 4 files uploaded, 1 old JS bundle deleted |
| CloudFront invalidation | ✅ `IBS9GGMG6ULAW0195DFSBNYUWT` |
| Matthew manual verification | ✅ Passed |

## Production Validation (Matthew, 2026-06-16)

- Admin page loaded: ✅
- Request card opens CareCard/detail modal: ✅
- Blank screen resolved: ✅
- "Pricing & Payment (Stripe Sandbox)" section visible: ✅
- Sandbox warning visible: ✅
- Payment status displayed as "Unpaid / Not Set": ✅
- Amount input visible: ✅
- "Generate Payment Link" button visible: ✅
- Generate Payment Link clicked: ❌ (not clicked — correct)
- No Checkout Session created: ✅
- No payment run: ✅
- No DynamoDB mutation: ✅

## What Was NOT Done

- ❌ No Terraform changes
- ❌ No Stripe API calls
- ❌ No DynamoDB writes
- ❌ No Cognito changes
- ❌ No backend deployment
- ❌ No mobile/EAS/TestFlight changes
- ❌ No secrets committed
