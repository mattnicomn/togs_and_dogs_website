# Release 14D: Payment Operations Quick Reference

**Status:** Complete
**Type:** Documentation only
**Risk to Production:** None
**Scope:** Admin/staff operations guide for the payment workflow

---

## Summary

Created `docs/operations/payment-workflow-quick-reference.md` — a practical guide for admin/staff covering:

- Payment flow overview (10-step lifecycle)
- When to generate payment links (pre-checks, safe/unsafe scenarios)
- When to send payment email (timing, resend rules)
- What never to do (security, repeated sends, card data)
- Payment status definitions and expected admin actions per status
- Troubleshooting common issues (email not received, card declined, not showing paid, expired links, wrong amount, no email on file)
- Admin UI instructions (filters, search, CareCard navigation)
- Sandbox/live mode reminder with current blocker status
- Escalation checklist (what to capture before contacting Matthew)

---

## Files Created

| File | Purpose |
|------|---------|
| `docs/operations/payment-workflow-quick-reference.md` | Admin/staff operations guide |
| `docs/release-notes/release-14d-payment-operations-quick-reference.md` | This file |

---

## What This Release Does NOT Do

- ❌ No code changes
- ❌ No deployments
- ❌ No Stripe/AWS/Terraform changes
- ❌ No live payments enabled
- ❌ No client communication
