# Backlog: Stripe Live Activation Blocked Pending EIN

**Status:** Blocked
**Owner:** Matthew
**Priority:** High (gates all live payment releases)
**Created:** 2026-06-18
**Dependency:** usmissionhero LLC Employer Identification Number (EIN)

---

## Problem

Stripe business verification requires Tax details (EIN) for usmissionhero LLC. The EIN is not yet available. Without completing business verification, Stripe will not enable live charges.

## Required Action

1. Obtain or locate EIN confirmation for usmissionhero LLC
2. Complete Stripe Dashboard → Settings → Account details → Tax details with EIN
3. Complete remaining Stripe business verification steps (Verify email, Verify business, Create profile)
4. Confirm live charges are enabled (no "restricted" banner)

## IRS Contact Status

- Matthew attempted to contact IRS for EIN assistance
- Could not complete due to high call volume
- May need to retry or use online IRS EIN application if eligible

## What This Blocks

| Release | Scope | Status |
|---------|-------|--------|
| 13E | Live Stripe secret wiring (Terraform) | ❌ Blocked |
| 13F | Live webhook validation | ❌ Blocked |
| 13G | Internal $1 live payment test | ❌ Blocked |
| 13H | First real client payment | ❌ Blocked |

## What Can Proceed While Blocked

| Work Item | Type | Safe? |
|-----------|------|-------|
| Draft/publish payment terms | Content | ✅ Yes |
| Draft/publish refund/cancellation policy | Content | ✅ Yes |
| Review customer support contact info | Content | ✅ Yes |
| Review statement descriptor wording | Planning | ✅ Yes (don't submit live) |
| Sandbox payment workflow re-validation | Testing | ✅ Yes |
| Admin/mobile UX improvements (non-payment) | Code | ✅ Yes |
| Multi-tenant architecture planning | Planning | ✅ Yes |
| TestFlight/mobile improvements | Code | ✅ Yes |

## Resume Point

Once EIN is available:
1. Complete Stripe Tax details in Dashboard
2. Complete remaining business verification
3. Return to `docs/planning/release-13d-manual-stripe-live-readiness-checklist.md`
4. Mark G1 as Ready
5. Proceed to Release 13E (live secret wiring)

## Risk

- Live payments cannot be enabled safely until Stripe account verification is complete
- Stripe may restrict the account or delay payouts if verification is incomplete
- No workaround exists — EIN is a hard requirement for US LLC payment processing

## Notes

- Stripe sandbox mode remains fully functional
- All sandbox payment testing is unaffected
- No urgency for live payments if no real client bookings are pending payment collection
- Matthew may revisit IRS during lower call-volume times or use online application
