# Release 13D.1: Payment Terms and Refund Cancellation Policy Draft

**Status:** Draft Complete — Awaiting Matthew Review
**Type:** Content/documentation only
**Risk to Production:** None
**Scope:** Draft customer-facing payment, refund, and cancellation policy language

---

## 1. Purpose

Prepare customer-facing payment terms, refund policy, and cancellation policy content so the business is ready before live Stripe payments are enabled. This is a draft for Matthew's review — not legal advice.

---

## 2. Deliverables

| File | Purpose |
|------|---------|
| `docs/policies/payment-terms-refund-cancellation-draft.md` | Full draft policy content |
| This file | Planning context and open-decision checklist |

---

## 3. Website Placement Recommendation

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| Add to existing Terms of Service page | Single location, less navigation | May make ToS very long | ✅ If ToS is short |
| Standalone `/payment-terms` page | Clean separation, linkable | Extra page to maintain | ✅ Preferred |
| Footer link "Payment & Refund Policy" | Standard e-commerce pattern | Requires new route | ✅ Best UX |

**Recommendation:** Create a standalone page at `/payment-terms` (or `/policies/payments`) linked from the footer. Reference it from the payment email template.

---

## 4. Open Policy Decisions for Matthew

Matthew must confirm these before publishing. Marked with `[DECISION]` in the draft.

| # | Decision | Options | Default Placeholder |
|---|----------|---------|---------------------|
| 1 | Payment due window | Immediate / 24h / 48h / before service | "before scheduled service date" |
| 2 | Late cancellation window | 24h / 48h / none | "24 hours before scheduled visit" |
| 3 | Late cancellation fee | None / 50% / full charge / flat fee | "may apply at provider's discretion" |
| 4 | Refund processing time | 5–10 / 7–14 business days | "5–10 business days" |
| 5 | Refund eligibility | Before service only / case-by-case | "case-by-case review" |
| 6 | Weather/emergency cancellation | Full refund / reschedule / credit | "reschedule or full refund" |
| 7 | No-show policy (client) | Charge / partial charge / none | "full charge may apply" |
| 8 | No-show policy (provider) | Full refund / reschedule | "full refund or reschedule" |
| 9 | Cash/check accepted? | Yes as alternate / no | "online card payment only" |
| 10 | Support email for billing | Confirm address | `support@usmissionhero.com` |
| 11 | Attorney/accountant review | Before or after publish | Before live payments |

---

## 5. Admin/Client Workflow Notes

### What Admin/Staff Should Tell Clients

Before sending a payment link:
- "You'll receive an email with a secure payment link"
- "Payment is processed through Stripe — we never see your card number"
- "The link expires in 30 minutes — if it expires, we can send a new one"
- "After payment, you'll receive a confirmation receipt from Stripe"

### Payment and Scheduling Relationship

**Recommendation for v1:** Payment does NOT gate scheduling. Ryan can schedule/assign staff before payment is received. This matches current workflow where Ryan quotes and schedules independently.

**Future option:** Add a "require payment before scheduling" toggle per-tenant. Not needed for initial launch.

---

## 6. What This Document Does NOT Do

- ❌ Publish any policy
- ❌ Modify the website
- ❌ Deploy code
- ❌ Constitute legal advice
- ❌ Finalize any business policy without Matthew's review

---

## 7. Recommended Next Step

1. Matthew reviews the draft policy in `docs/policies/payment-terms-refund-cancellation-draft.md`
2. Matthew makes decisions on the 11 open items above
3. Attorney/accountant reviews if desired
4. Publish to website in a future frontend release (after live payments are enabled)
