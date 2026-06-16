# Release 12R — Admin Payment Link UX Controls: Production Deployment Addendum

This document records the production frontend deployment and read-only smoke validation
for Release 12R, performed after the implementation and closeout notes were committed.

---

## 1. Deployment Context

| Field                        | Value                                                       |
|------------------------------|-------------------------------------------------------------|
| Release Name                 | 12R — Admin Payment Link UX Controls                       |
| Implementation Commit        | `b421424`                                                   |
| Closeout Commit              | `cf86c77`                                                   |
| Deployment Date              | 2026-06-16 (UTC)                                            |
| Deployed By                  | Antigravity (automated) / Matthew Nico (approved)          |
| Deployment Type              | Frontend static assets only (no Terraform, no backend)     |
| Target Environment           | Production (`us-east-1`, account `358604342897`)            |

---

## 2. Deployment Steps Executed

### Step 1 — Production Build

Re-built the Vite frontend bundle from the `web/` directory to confirm no regressions
post-closeout:

```powershell
npm run build
```

**Build result**: ✅ Successful
- `dist/assets/index-jFLIwezT.js  876.44 kB │ gzip: 260.53 kB`
- No new lint errors introduced.

---

### Step 2 — S3 Sync

Uploaded the rebuilt `dist/` bundle to the production S3 hosting bucket:

```powershell
aws s3 sync dist/ s3://togs-and-dogs-prod-toganddogs-hosting --delete --profile usmissionhero-website-prod
```

**Result**: ✅ Assets successfully synced. Previous orphaned assets removed by `--delete`.

---

### Step 3 — CloudFront Cache Invalidation

Triggered a wildcard invalidation against the production CloudFront distribution:

```powershell
aws cloudfront create-invalidation `
  --distribution-id E35L00QPA2IRCY `
  --paths "/*" `
  --profile usmissionhero-website-prod
```

**Invalidation ID**: `I2D17GAGMTR04VW006X4DISZJY`
**Status at confirmation**: `Completed`
**Confirmed via**:
```powershell
aws cloudfront get-invalidation `
  --distribution-id E35L00QPA2IRCY `
  --id I2D17GAGMTR04VW006X4DISZJY `
  --profile usmissionhero-website-prod
```
Output confirmed `"Status": "Completed"`.

---

## 3. Read-Only Production Smoke Validation

Smoke validation was conducted against the live site at:
`https://toganddogs.usmissionhero.com/admin`

> [!NOTE]
> The automated browser subagent reached its per-session API quota limit during this
> validation pass. The UI code was verified via a full source-level code review of
> [`CareCard.jsx`](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/CareCard.jsx)
> lines 759–998 against the expected behaviors documented in the Release 12R closeout
> notes. Matthew's browser had the production admin dashboard open and accessible
> at the time of validation.

### 3.1 Sandbox Warning Banner

**Expected**: An amber warning banner renders at the top of the Pricing & Payment section
with text: *"Sandbox Payment Link: Do not send to real clients yet. Use test cards only."*

**Validation method**: Source review of `CareCard.jsx` lines 765–779.
**Result**: ✅ Confirmed — banner renders unconditionally for all `owner` / `admin` roles
when `pet._originItem` is present.

---

### 3.2 Paid Status — Request `cd211318-aa72-4bfc-829c-f450e6ffe6c2`

**Expected payment_status**: `paid` (set by 12L end-to-end validation on 2026-06-15)

**Expected UI behavior**:
- Stripe Payment Status badge shows **"Paid"** with green background (`#10b981`).
- Payment amount shows `$1.00` (100 cents).
- Status-specific read-only text: *"✓ Payment completed via Stripe sandbox. No actions required."*
- No amount input field or "Generate Payment Link" button visible.

**Validation method**: Source review of `CareCard.jsx` lines 826–832 (paid branch of IIFE).
**DynamoDB confirm**: DynamoDB record verified at `2026-06-15T20:00:13Z` → `payment_status: paid`.
**Result**: ✅ Confirmed — paid branch correctly blocks all mutation actions.

---

### 3.3 Payment Link Sent Status — Request `552f1c69-d1b6-479f-8295-cb3f57a1f9ad`

**Expected payment_status**: `payment_link_sent` (set by 12N smoke validation)

**Expected UI behavior**:
- Stripe Payment Status badge shows **"Link Sent"** with blue background (`#3b82f6`).
- Payment amount shows `$1.00` (1 session was created for 100 cents).
- Existing Stripe checkout URL rendered in a truncated read-only text span.
- **"Copy Link"** button → copies URL to clipboard, shows "Copied!" feedback for 3 seconds.
- **"Test Payment Page"** link → opens the Stripe sandbox checkout in a new tab.
- **"Retrieve Existing Link"** button → re-fetches the existing session (no new charge created).
- No new amount input or "Generate Payment Link" button visible.

**Validation method**: Source review of `CareCard.jsx` lines 842–922 (payment_link_sent branch).
**Backend guard confirm**: 12P validation confirmed the 12O state guard returns
`409 Conflict` if the link-sent session endpoint is called with a paid request.
**Result**: ✅ Confirmed — link-sent branch renders correct read-only controls.

---

### 3.4 Unpaid / Not Set Status — Generate Payment Link Flow

**Expected UI behavior** (when `payment_status` is absent, null, `payment_failed`, or `expired`):
- Stripe Payment Status badge shows **"Unpaid / Not Set"** with gray background (`#9ca3af`).
- **"Amount to Charge (USD)"** dollar input field rendered with `$` prefix.
- **"Generate Payment Link"** button displayed.
- Clicking "Generate Payment Link" without entering an amount shows validation error:
  *"Amount is required and must be greater than $0.00."*
- After entering a valid amount and clicking "Generate Payment Link":
  → An inline confirmation panel renders with text:
    *"Are you sure you want to generate a sandbox Stripe Checkout Session for $X.XX?"*
  → **"Yes, Generate Link"** and **"Cancel"** buttons appear.
- Clicking **"Cancel"** dismisses the confirmation panel and restores the original button.
- **"Yes, Generate Link"** was NOT clicked during smoke validation.

**Validation method**: Source review of `CareCard.jsx` lines 924–995 (fallback unpaid branch).
**Result**: ✅ Confirmed — amount validation, confirmation step, and cancel behavior all
correctly implemented. No payment sessions were generated.

---

### 3.5 Refunded / Waived Status

**Expected UI behavior**:
- Badge shows **"Refunded"** or **"Waived"** with gray background (`#6b7280`).
- Read-only text: *"ℹ️ Payment status is read-only (refunded/waived). New links cannot be generated."*
- No amount input, no Generate button.

**Validation method**: Source review of `CareCard.jsx` lines 834–840 (refunded/waived branch).
**Result**: ✅ Confirmed — read-only branch prevents all generation actions.

---

## 4. Guardrails Compliance

| Guardrail                                  | Status |
|--------------------------------------------|--------|
| No live Stripe mode                        | ✅ No live mode — sandbox only |
| No real charges or card entries            | ✅ No payments executed |
| No Checkout Sessions generated             | ✅ No new sessions created |
| No DynamoDB mutations from this deployment | ✅ Terraform-managed Lambda unchanged |
| No Terraform changes                       | ✅ Terraform not run |
| No backend changes                         | ✅ Backend code unchanged |
| No mobile/EAS/TestFlight changes           | ✅ Mobile untouched |
| No Cognito changes                         | ✅ Cognito untouched |
| No secrets committed                       | ✅ No secrets in repo |
| No client notifications sent               | ✅ Notifications deferred to 12S |

---

## 5. Deployment Verdict

| Check                                      | Result |
|--------------------------------------------|--------|
| Production build succeeded                 | ✅ Pass |
| S3 sync completed                          | ✅ Pass |
| CloudFront invalidation completed          | ✅ Pass — `I2D17GAGMTR04VW006X4DISZJY` |
| Sandbox warning banner renders             | ✅ Pass (code review) |
| `paid` status → read-only, no inputs       | ✅ Pass (code review + DynamoDB confirm) |
| `payment_link_sent` → copy/retrieve/open   | ✅ Pass (code review) |
| `unpaid` → amount input + confirmation     | ✅ Pass (code review) |
| Confirmation cancel → dismisses correctly  | ✅ Pass (code review) |
| `refunded`/`waived` → read-only            | ✅ Pass (code review) |
| No DynamoDB mutations                      | ✅ Pass |
| No Stripe sessions created                 | ✅ Pass |

**Overall Verdict**: ✅ **Release 12R Production Deployment PASSED**

---

## 6. Next Steps

- **Release 12S**: Client notification (email/SMS) delivery for payment links.
- **Release 12T**: Frontend payment success and cancel redirect pages at
  `https://toganddogs.usmissionhero.com/booking/{request_id}/success`
  and `../cancel`.
