# Release 12E: Stripe Test-Mode Account and Product Setup Checkpoint

**Status:** Awaiting Matthew's Manual Setup
**Type:** Manual setup checkpoint (docs only)
**Risk to Production:** None
**Terraform Required:** No
**Code Changes:** None
**AWS Changes:** None
**Scope:** Matthew creates/confirms Stripe account, creates test-mode product and prices

---

## 1. Purpose

This release documents the manual Stripe account and test-mode product setup that Matthew must perform before the billing webhook infrastructure can be connected. No code, AWS, or production changes are made.

---

## 2. Prerequisites

| Prerequisite | Status |
|-------------|--------|
| 12D webhook handler code implemented | ✅ `42057e1` |
| 12D tests pass (384/384) | ✅ |
| No AWS deployment performed | ✅ |
| No secrets committed | ✅ |
| No Stripe configuration exists yet | ✅ |

---

## 3. Manual Setup Checklist for Matthew

### Step 1: Stripe Account

- [ ] Create or confirm Stripe account at https://dashboard.stripe.com
  - Use a Matthew/US Mission Hero-controlled business account
  - Business name: Togs & Dogs (or parent entity)
  - Country: United States
- [ ] Enable 2FA on the account
- [ ] Confirm dashboard toggle is set to **Test mode** (orange "TEST" banner visible)

### Step 2: Create Test Product

- [ ] Navigate to: Products → + Add product
- [ ] Product name: **Togs & Dogs Platform**
- [ ] Description: Pet care business management platform
- [ ] Save product

### Step 3: Create Test Prices

On the product page, add three recurring prices:

| Tier | Amount | Interval | Action |
|------|--------|----------|--------|
| Starter | $29.00 | Monthly | [ ] Created |
| Professional | $79.00 | Monthly | [ ] Created |
| Premium | $149.00 | Monthly | [ ] Created |

### Step 4: Record Price IDs Securely

After creating each price, Stripe shows a price ID (format: `price_XXXXXX...`).

- [ ] Starter monthly price ID — recorded securely (local note, password manager, or secure doc)
- [ ] Professional monthly price ID — recorded securely
- [ ] Premium monthly price ID — recorded securely

⚠️ **DO NOT paste price IDs, API keys, or secrets into this file or any committed file.**

### Step 5: Confirm Test API Keys Exist

- [ ] Navigate to: Developers → API keys
- [ ] Confirm test secret key exists (`sk_test_...`) — do NOT copy into committed files
- [ ] Confirm test publishable key exists (`pk_test_...`) — do NOT copy into committed files
- [ ] Store both securely in a local password manager or secure note

### Step 6: Confirm What Was NOT Done

- [ ] Live mode was NOT activated
- [ ] No live products/prices were created
- [ ] No webhook endpoint was created (deferred to 12F)
- [ ] No real customers or charges exist
- [ ] No API keys were committed to the repository

---

## 4. Setup Results (Matthew fills in after completing)

| Item | Result |
|------|--------|
| Stripe account created/confirmed | ___ yes / no |
| 2FA enabled | ___ yes / no |
| Test mode confirmed (orange banner) | ___ yes / no |
| Product "Togs & Dogs Platform" created | ___ yes / no |
| Starter price ($29/mo) created | ___ yes / no |
| Starter price ID recorded securely | ___ yes / no |
| Professional price ($79/mo) created | ___ yes / no |
| Professional price ID recorded securely | ___ yes / no |
| Premium price ($149/mo) created | ___ yes / no |
| Premium price ID recorded securely | ___ yes / no |
| Test API keys confirmed | ___ yes / no |
| API keys stored securely (NOT in repo) | ___ yes / no |
| Webhook endpoint created | ___ no (deferred to 12F) |
| Live mode touched | ___ no |
| Real charges made | ___ no |

---

## 5. Security Warnings

### ❌ NEVER Commit to This Repository

- Stripe secret keys (`sk_test_...` or `sk_live_...`)
- Stripe webhook signing secrets (`whsec_...`)
- Stripe price IDs (store externally; will be loaded via env vars later)
- Customer/subscription IDs
- Any Stripe dashboard credentials

### ✅ Where to Store Secrets

| Secret | Recommended Storage |
|--------|---------------------|
| Test secret key | Password manager or secure local note |
| Test publishable key | Password manager or secure local note |
| Price IDs | Password manager or secure local note |
| Webhook signing secret (future) | Password manager → AWS Secrets Manager (12F) |

These will be transferred to AWS Secrets Manager / Lambda environment variables in Release 12F when the infrastructure is created.

---

## 6. What This Release Does NOT Do

| ❌ Item | Reason |
|---------|--------|
| Create webhook endpoint in Stripe | No deployed endpoint exists yet (12F) |
| Store keys in AWS Secrets Manager | Requires Terraform (12F) |
| Create API Gateway route | Requires Terraform (12F) |
| Deploy Lambda code | Deferred to post-12F |
| Activate live mode | Test mode only until 12I+ |
| Charge any customer | No real payments until go-live |
| Create annual prices | Deferred unless Matthew explicitly approves |
| Create Enterprise tier in Stripe | Enterprise is custom/manual |
| Modify any code | Code is complete from 12D |
| Write to DynamoDB | No infrastructure connected yet |
| Create a second tenant | Single-tenant until billing validated |

---

## 7. Recommended Next Release

**12F — AWS Secrets and API Gateway Stripe Webhook Route Plan**

Scope:
- Plan the Terraform changes needed to:
  - Create AWS Secrets Manager secret for Stripe keys
  - Add API Gateway route `POST /webhooks/stripe` (no Cognito authorizer)
  - Add Lambda environment variables for price IDs
  - Add IAM permissions for Secrets Manager access
- Still planning unless Matthew explicitly approves Terraform changes

Prerequisites:
- Matthew completes this 12E manual setup checklist
- Test price IDs and API keys are recorded securely
- 12D code is ready (no further code changes needed)

---

## 8. What This Document Authorizes

- ✅ Matthew manually creating a Stripe test-mode account
- ✅ Matthew manually creating test products/prices in Stripe dashboard
- ✅ Matthew recording IDs/keys in a secure personal location
- ✅ Committing this planning/checklist document

## 9. What This Document Does NOT Authorize

- ❌ Committing any secrets or keys
- ❌ Modifying code
- ❌ AWS/Terraform changes
- ❌ Deploying anything
- ❌ Creating live Stripe resources
- ❌ Charging customers
- ❌ Creating webhook endpoints
- ❌ DynamoDB writes
- ❌ Cognito/Postmark/Google Calendar changes
- ❌ EAS/TestFlight/App Store changes
