# Production State Reconciliation After Release 22M Hotfix

**Date:** 2026-07-10
**Purpose:** Document production/main divergence and prevent accidental 22J deployment

---

## Current Production State

| Item | Value |
|------|-------|
| Deployed from branch | `hotfix/22m-cancellation-visibility-hotfix` |
| Baseline commit | `48874f0` (Release 22I) |
| Hotfix commit | `1215700` |
| Production JS bundle | `/assets/index-BU-WCL8y.js` |
| Production CSS bundle | `/assets/index-fLn3j3dM.css` |
| CloudFront invalidation | `I4ABCENFFCX5937IMJAH9LN89T` (Completed) |
| Manual validation | ✅ PASS (Matthew confirmed) |

## What Is Live in Production

- ✅ Pending cancellation visibility (22L/22M fix)
- ✅ Needs Action queue shows CANCELLATION_REQUESTED records
- ✅ Sidebar counts include pending cancellations
- ✅ Review Cancellation action available in row dropdown
- ✅ Cancelled tab shows only terminal cancellations

## What Is NOT Live in Production

- ❌ Release 22J Profile Editor MVP (paused/not deployed)
- ❌ Simplified staff cards with "Manage" button
- ❌ Profile Editor side drawer
- ❌ Protected account/orphaned identity UI banners

---

## Production/Main Divergence

### WARNING: `main` Contains Undeployed 22J Code

| Branch | Contains | Deployed? |
|--------|----------|-----------|
| `main` | All commits through 22J + 22L + 22M docs | ⚠️ 22J is NOT deployed |
| `hotfix/22m-cancellation-visibility-hotfix` | 22I baseline + 22L fix only | ✅ Currently in production |

### Risk

If someone runs `npm run build` from `main` and deploys to S3, they will accidentally deploy Release 22J (Profile Editor) without approval.

### Prevention

- ❌ Do NOT deploy from `main` without explicitly confirming 22J is approved
- ✅ Future frontend deployments MUST be from an approved branch
- ✅ Before any deploy: verify branch + confirm with Matthew which features are included
- ✅ If 22J is later approved: deploy from `main` after explicit go-ahead
- ✅ If 22J remains paused: create new hotfix branches from the 22M hotfix branch for any future frontend fixes

---

## Matthew Manual Validation (2026-07-10)

| Check | Result |
|-------|--------|
| Admin dashboard loads | ✅ PASS |
| Needs Action shows 2 pending cancellation records | ✅ PASS |
| Sidebar count: Needs Action (2) | ✅ PASS |
| Row action menu includes "Review Cancellation" | ✅ PASS |
| Cancelled (0) shows terminal-only | ✅ PASS |
| No cancellation approved/denied | ✅ Correct — no action taken |
| 22J Profile Editor NOT present | ✅ Correct — no Manage button visible |

---

## Visible Cancellation Records

The 2 records showing CANCELLATION_REQUESTED in Needs Action are likely test/stale records from earlier validation work. Options:
- Leave as-is (harmless — clearly visible in admin queue)
- Clean up via normal admin cancellation workflow (approve/deny) only if Matthew approves
- Do NOT delete DynamoDB records directly

---

## Recommended Next Actions

| Option | Description | Requires |
|--------|-------------|----------|
| A | Approve 22J deployment → deploy from `main` | Matthew explicit approval |
| B | Continue from hotfix branch → plan next fix without 22J | Branch management |
| C | Clean up test cancellation records → approve/deny through admin UI | Matthew approval |
| D | Pause and focus on other priorities (calendar, Stripe, etc.) | No deployment needed |
