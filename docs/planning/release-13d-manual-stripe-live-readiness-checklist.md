# Release 13D: Manual Stripe Live Readiness Checklist

**Status:** Awaiting Matthew's Manual Completion
**Type:** Manual checklist (docs only)
**Risk to Production:** None
**Scope:** Matthew verifies Stripe Dashboard and business readiness before live keys are wired

---

## Instructions

Matthew: Complete each item below. Mark status as one of:
- ✅ **Ready** — verified and good to go
- ⏳ **Not Started** — not yet checked
- ❌ **Blocked** — issue found, must be resolved before go-live
- ➖ **N/A** — not applicable

**Recommended order:** Work through sections 1–7 top to bottom. Do NOT proceed to Release 13E (live secret wiring) until all Critical items are marked Ready.

---

## 1. Account & Business Verification

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1.1 | Business/legal entity verified in Stripe | ___ | Settings → Account details |
| 1.2 | Business name: "usmissionhero LLC" (or correct entity) | ___ | |
| 1.3 | Representative identity verification complete | ___ | Settings → People |
| 1.4 | Tax ID / EIN on file | ___ | Settings → Business details |
| 1.5 | Country: United States | ___ | |
| 1.6 | Live charges enabled (no "restricted" banner) | ___ | Dashboard header |
| 1.7 | No outstanding Stripe account requirements | ___ | Check for any alert banners |

---

## 2. Payout Readiness

| # | Item | Status | Notes |
|---|------|--------|-------|
| 2.1 | Bank account connected for payouts | ___ | Settings → Payouts → Bank accounts |
| 2.2 | Payout schedule understood (standard = 2-day rolling) | ___ | |
| 2.3 | Payout currency: USD | ___ | |
| 2.4 | Matthew understands processing/payout timelines | ___ | Funds available ~2 business days after charge |
| 2.5 | Payout destination is the correct business bank account | ___ | Confirm last 4 digits match expected |

---

## 3. Live Payment Method Settings

| # | Item | Status | Notes |
|---|------|--------|-------|
| 3.1 | Dashboard toggled to **Live mode** for this section | ___ | Toggle in Dashboard header |
| 3.2 | Card payments: Enabled | ___ | Settings → Payment methods (Live) |
| 3.3 | Link (Stripe wallet): Understood — appears as "save info" checkbox | ___ | Cannot fully disable; cosmetic only |
| 3.4 | Klarna: Disabled | ___ | Settings → Payment methods |
| 3.5 | Afterpay: Disabled | ___ | |
| 3.6 | Bank transfers: Disabled | ___ | |
| 3.7 | All other non-card methods: Disabled or N/A | ___ | |

---

## 4. Customer-Facing Payment Settings

| # | Item | Status | Notes |
|---|------|--------|-------|
| 4.1 | Statement descriptor set (≤22 chars) | ___ | e.g., "TOG AND DOGS" |
| 4.2 | Shortened descriptor set (≤10 chars) | ___ | e.g., "TOG DOGS" |
| 4.3 | Customer support email configured | ___ | e.g., support@usmissionhero.com |
| 4.4 | Customer support phone (optional) | ___ | Business phone or blank |
| 4.5 | Support URL configured | ___ | https://toganddogs.usmissionhero.com |
| 4.6 | Successful payment receipt emails: Enabled | ___ | Settings → Customer emails |
| 4.7 | Refund receipt emails: Enabled | ___ | Settings → Customer emails |
| 4.8 | Business logo/branding uploaded (optional) | ___ | Appears on Stripe Checkout page |

---

## 5. Webhook Readiness

| # | Item | Status | Notes |
|---|------|--------|-------|
| 5.1 | Plan: Create SEPARATE live webhook endpoint | ___ | Do not modify sandbox endpoint |
| 5.2 | Endpoint URL confirmed | ___ | `https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod/webhooks/stripe` |
| 5.3 | Events planned: `checkout.session.completed` | ___ | |
| 5.4 | Events planned: `checkout.session.expired` | ___ | |
| 5.5 | Live webhook NOT created yet (wait for 13E) | ___ | Will be created during 13E/13F |
| 5.6 | Understand: signing secret will go in local terraform.tfvars only | ___ | |

---

## 6. Local Secret Handling Verification

| # | Item | Status | Notes |
|---|------|--------|-------|
| 6.1 | No live keys have been pasted in chat | ___ | |
| 6.2 | No live keys have been committed to git | ___ | |
| 6.3 | No live keys are in screenshots | ___ | |
| 6.4 | No live keys are in log files | ___ | |
| 6.5 | `infra/prod/terraform.tfvars` is in .gitignore | ___ | Verify: `git check-ignore infra/prod/terraform.tfvars` |
| 6.6 | Live `sk_live_` and `whsec_` values will be entered ONLY in ignored terraform.tfvars | ___ | |
| 6.7 | Matthew has a secure storage location for backup of live keys | ___ | Password manager or similar |

---

## 7. Website / Legal Readiness

| # | Item | Status | Notes |
|---|------|--------|-------|
| 7.1 | Payment terms: published or approved for publication | ___ | On website or in service agreement |
| 7.2 | Refund/cancellation policy: published or approved | ___ | |
| 7.3 | Privacy policy: still accessible and up to date | ___ | Covers payment data processing |
| 7.4 | Terms of service: still accessible | ___ | |
| 7.5 | Customer support contact clear on website | ___ | Email/phone visible |

---

## 8. Go / No-Go Gates

### Critical Gates (ALL must be Ready)

| Gate | Item | Status |
|------|------|--------|
| G1 | Account verification complete (1.1–1.7) | ___ |
| G2 | Bank account connected (2.1) | ___ |
| G3 | Card-only payment methods (3.2–3.7) | ___ |
| G4 | Statement descriptor set (4.1) | ___ |
| G5 | No live keys exposed (6.1–6.4) | ___ |
| G6 | terraform.tfvars in .gitignore (6.5) | ___ |

### Recommended Gates (Should be Ready)

| Gate | Item | Status |
|------|------|--------|
| G7 | Receipt emails enabled (4.6–4.7) | ___ |
| G8 | Payment terms published (7.1) | ___ |
| G9 | Refund policy published (7.2) | ___ |

### Stop Condition

**Do NOT proceed to Release 13E (live secret wiring) until ALL Critical Gates (G1–G6) are marked Ready.**

If any Recommended Gate (G7–G9) is Blocked, Matthew may choose to proceed at his discretion with documented acceptance of the risk.

---

## 9. Matthew's Notes

_Use this space for any findings, questions, or decisions during checklist completion:_

```
Notes:




```

---

## 10. Final Approval

| Field | Value |
|-------|-------|
| All Critical Gates Ready? | ___ yes / no |
| Matthew approves proceeding to 13E (live secret wiring)? | ___ yes / no |
| Approval date | ___ |
| Rollback plan reviewed? | ___ yes / no |
| First live test limited to internal $1 payment? | ___ yes / no |
| First live test refund plan approved? | ___ yes / no |

---

## 11. What This Document Does NOT Authorize

- ❌ Creating live webhook endpoints
- ❌ Generating or copying live API keys into any system
- ❌ Running terraform plan or apply
- ❌ Deploying anything
- ❌ Charging any card
- ❌ Sending emails to clients
- ❌ Writing code
- ❌ DynamoDB/Cognito/Postmark changes
- ❌ Mobile/EAS/TestFlight changes

This is a readiness checklist only. Live key wiring requires separate Release 13E approval after all Critical Gates pass.
