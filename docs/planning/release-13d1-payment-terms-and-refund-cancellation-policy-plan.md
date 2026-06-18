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

Matthew must confirm these before publishing. Defaults have been filled in as of Release 13D.2 — marked `[PENDING MATTHEW]` in the draft policy.

| # | Decision | Recommended Default | Status |
|---|----------|--------------------| -------|
| 1 | Payment due window | 24h / before service | Default filled |
| 2 | Late cancellation window (standard) | 24 hours | Default filled |
| 3 | Late cancellation window (overnight/multi-day) | 48 hours | Default filled |
| 4 | Late cancellation fee | Up to 50%, discretionary during rollout | Default filled |
| 5 | Refund processing time | 5–10 business days | Default filled |
| 6 | Refund eligibility | Full before service; partial/case-by-case otherwise | Default filled |
| 7 | Weather/emergency policy | Reschedule or refund, fees waived | Default filled |
| 8 | Client no-show/no-access | Fee may apply | Default filled |
| 9 | Provider no-show | Full refund or reschedule | Default filled |
| 10 | Cash/check accepted? | No — card only during initial rollout | Default filled |
| 11 | Support email | [PENDING MATTHEW — needs confirmed address] | ⏳ Pending |
| 12 | Business hours | Mon–Fri, 9 AM – 5 PM Eastern | Default filled |
| 13 | Response time | 1 business day | Default filled |
| 14 | Attorney/accountant review | Required before live payments | ⏳ Pending |
| 15 | Effective date | Same as live payment activation | ⏳ Pending |

**Remaining decisions requiring Matthew:** Items 11, 14, 15 (support email confirmation, attorney review timeline, effective date).

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
