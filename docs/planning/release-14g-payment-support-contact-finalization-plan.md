# Release 14G: Payment Support Contact Finalization Plan

**Status:** Planning
**Priority:** Medium (must resolve before live payments)
**Risk to Production:** None (planning only)
**Terraform Required:** No
**Code Changes:** None
**Scope:** Plan consistent support contact wiring across all payment surfaces

---

## 1. Problem

Multiple customer-facing surfaces currently display placeholder or inconsistent support/billing contact information:

- Some show `[billing/support email to be confirmed]`
- Some hardcode `support@toganddogs.com`
- Some use the Postmark template variable `{business_email}`

Before live payments go active, all surfaces must show a single confirmed, monitored email address.

---

## 2. All Locations Where Support Contact Appears

### Frontend (Customer-Facing Pages)

| File | Current Value | Type |
|------|---------------|------|
| `web/src/components/PaymentSuccess.jsx` | `[billing/support email to be confirmed]` or placeholder text | Hardcoded string |
| `web/src/components/PaymentCancel.jsx` | `support@toganddogs.com` (hardcoded) | Hardcoded string |

### Backend (Email Template)

| File | Current Value | Type |
|------|---------------|------|
| `src/backend/common/notifications/templates.py` (`payment_link_email`) | `{business_email}` variable, default: `support@toganddogs.com` | Template variable |

### Documentation

| File | Current Value |
|------|---------------|
| `docs/policies/payment-terms-refund-cancellation-draft.md` | `[PENDING MATTHEW: billing/support email to be confirmed]` |
| `docs/operations/payment-workflow-quick-reference.md` | References "contact us" without specific address |
| `docs/planning/release-12s-client-payment-link-email-notification-plan.md` | References `support@usmissionhero.com` as possible |

### Stripe Dashboard (Future)

| Setting | Current | Needed |
|---------|---------|--------|
| Support email (Settings → Account details → Public details) | Unknown | Must match chosen address |

---

## 3. Recommended Support Contact Strategy

### Option A: `support@usmissionhero.com` (Recommended)

| Aspect | Detail |
|--------|--------|
| Domain | `usmissionhero.com` — the parent company domain |
| Already used for | Postmark sender address (`support@usmissionhero.com`) |
| Consistency | Matches existing notification From address |
| Monitoring | Must confirm mailbox exists and is monitored |
| Pros | Professional, already in use, single brand domain |
| Cons | Not the `toganddogs.com` brand specifically |

### Option B: `support@toganddogs.com`

| Aspect | Detail |
|--------|--------|
| Domain | `toganddogs.com` — the client-facing brand |
| Currently | Referenced in PaymentCancel.jsx (hardcoded) |
| Monitoring | Must confirm mailbox exists or is forwarded |
| Pros | Matches client-facing brand name |
| Cons | May not be configured as a real inbox; `toganddogs.com` DNS/email may not be fully set up |

### Option C: `billing@toganddogs.com` or `billing@usmissionhero.com`

| Aspect | Detail |
|--------|--------|
| Purpose-specific | Clearly for payment/billing inquiries only |
| Monitoring | Must be configured and monitored |
| Pros | Clear purpose; separates billing from general support |
| Cons | Extra mailbox to maintain; low volume may not justify separation |

### Recommendation

**Use `support@usmissionhero.com`** unless Matthew specifically wants the `toganddogs.com` domain for client communications. Rationale:
- Already the Postmark sender address
- Known to be on a managed domain
- Consistent across all notification types
- Single inbox to monitor

---

## 4. Open Decision for Matthew

| # | Decision | Options | Default |
|---|----------|---------|---------|
| 1 | Final billing/support email address | `support@usmissionhero.com` / `support@toganddogs.com` / other | `support@usmissionhero.com` |
| 2 | Is the chosen inbox actively monitored? | Yes / No / Needs setup | Must be Yes before live |
| 3 | Who monitors it? | Matthew / Ryan / shared | Matthew (initially) |
| 4 | Expected response time? | Same-day / 1 business day / 2 days | 1 business day |
| 5 | Should reply-to on payment emails go to this address? | Yes / No | Yes |

**Matthew must confirm decision #1 before implementation can proceed.**

---

## 5. Implementation Plan (Release 14H)

Once Matthew confirms the email address:

| Step | File | Change |
|------|------|--------|
| 1 | `web/src/components/PaymentSuccess.jsx` | Replace placeholder with confirmed address |
| 2 | `web/src/components/PaymentCancel.jsx` | Replace hardcoded `support@toganddogs.com` with confirmed address |
| 3 | `src/backend/common/notifications/templates.py` | Update default for `business_email` variable if different |
| 4 | `docs/policies/payment-terms-refund-cancellation-draft.md` | Replace all `[PENDING MATTHEW]` placeholders |
| 5 | `docs/operations/payment-workflow-quick-reference.md` | Add confirmed address in escalation section |
| 6 | Stripe Dashboard (future, during 13E) | Set support email to confirmed address |

### Deployment

- Frontend: `npm run build` → S3 sync → CloudFront invalidation
- Backend: Only if template default changes (would require Lambda redeploy via Terraform)
- Docs: commit and push

### Validation

- Visual check: success page shows correct email
- Visual check: cancel page shows correct email
- Email test: sandbox payment email shows correct contact in body
- Click `mailto:` link on cancel page to confirm it opens correctly

---

## 6. Consistency Checklist (Post-Implementation)

After 14H is complete, verify ALL of these show the same address:

| Surface | Shows Correct Address? |
|---------|------------------------|
| PaymentSuccess.jsx | ___ |
| PaymentCancel.jsx | ___ |
| Payment email template body | ___ |
| Payment email From/Reply-To | ___ |
| Payment terms draft | ___ |
| Operations quick reference | ___ |
| Stripe Dashboard support email (when configured) | ___ |

---

## 7. What This Document Does NOT Authorize

- ❌ Writing code
- ❌ Deploying anything
- ❌ Modifying templates
- ❌ Sending emails
- ❌ Configuring Postmark or Stripe
- ❌ AWS/Terraform changes
- ❌ DynamoDB writes
- ❌ Cognito changes
- ❌ Mobile/EAS/TestFlight changes
- ❌ Committing secrets

This is a planning document only. Implementation (Release 14H) requires Matthew's confirmed email address decision and separate approval.
