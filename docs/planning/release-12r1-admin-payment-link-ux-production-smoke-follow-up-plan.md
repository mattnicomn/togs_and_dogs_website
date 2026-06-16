# Release 12R.1: Admin Payment Link UX Production Smoke Follow-up Plan

**Status:** Awaiting Manual Smoke Validation
**Type:** Read-only visual smoke checkpoint (no actions)
**Risk to Production:** None (observation only)
**Code Changes:** None
**Deployment:** None (12R frontend already deployed)
**Scope:** Confirm 12R payment controls render correctly in production

---

## 1. Context

| Item | Status |
|------|--------|
| 12R implementation commit | `b421424` |
| 12R closeout commit | `cf86c77` |
| 12R deployment addendum | `941b527` |
| Frontend deployed to S3 | ✅ |
| CloudFront invalidation | ✅ `I2D17GAGMTR04V` |
| AG production smoke | ⚠️ Incomplete (token limit reached) |
| Payment link generation tested | ❌ Not attempted (correct — read-only only) |
| CareCard/detail panel confirmed opening | ⚠️ Unconfirmed |

---

## 2. Manual UI Smoke Steps for Matthew

### Prerequisites

- Browser: Chrome or Safari (desktop)
- Logged in as: `mattnicomn10@gmail.com` (admin)
- Site: https://toganddogs.usmissionhero.com

### Step-by-Step

| # | Action | What to Look For |
|---|--------|-----------------|
| 1 | Navigate to https://toganddogs.usmissionhero.com/admin | Admin dashboard loads without errors |
| 2 | Confirm request list loads | Requests visible, no blank screen |
| 3 | Look for any payment status badges in the request list | 🟡 or 🟢 dots next to test requests (if visible in list view) |
| 4 | Click on a **paid** test request (e.g., `test_payment_validation_12k`) | Detail card/CareCard opens |
| 5 | Navigate to the "Meet & Greet / Quote" tab (or equivalent section) | Tab renders without error |
| 6 | Scroll to "Pricing & Payment" section | Section is visible |
| 7 | **Verify paid state:** Green "✅ Paid" badge, amount shown, no Generate button | Read-only display, no action buttons |
| 8 | Close the detail card | Card closes cleanly |
| 9 | Click on a request with `payment_link_sent` status (if one exists) | Detail card opens |
| 10 | Scroll to "Pricing & Payment" section | "Copy Link" or "Resend" controls visible |
| 11 | Close the detail card | Card closes cleanly |
| 12 | Click on an **unpaid** request (no payment_status) | Detail card opens |
| 13 | Scroll to "Pricing & Payment" section | Amount input field + "Generate Payment Link" button visible |
| 14 | **Verify sandbox label:** Look for "SANDBOX" or test-mode indicator near payment controls | Visible if implemented |
| 15 | Close the detail card without clicking Generate | No action taken |

### Time Required

~3-5 minutes. No typing, no form submissions, no button clicks beyond opening/closing cards.

---

## 3. Expected UI Results

| Request State | Expected Pricing & Payment Section |
|---------------|------------------------------------|
| `payment_status = paid` | 🟢 "Paid — $XX.XX" badge, payment date, read-only, NO generate button |
| `payment_status = payment_link_sent` | 🟡 "Payment Pending" badge, "Copy Link" button, "Resend" option |
| `payment_status = null` (unpaid) | Amount input ($), "Generate Payment Link" button, sandbox label |
| `payment_status = payment_failed` | 🔴 "Payment Failed", "Generate Payment Link" button (retry) |

---

## 4. Things Matthew Must NOT Click

| ❌ Do NOT | Reason |
|-----------|--------|
| Click "Generate Payment Link" | Creates a real Stripe Checkout Session (sandbox, but unnecessary) |
| Submit any payment form | Not a validation step |
| Click "Resend" on payment_link_sent requests | Creates new Checkout Session |
| Send any emails/SMS | No client communication during smoke |
| Approve/reject/assign any request | Unrelated to 12R validation |
| Edit any request fields | Read-only observation only |

**The entire smoke is visual observation only.** Open cards, look at sections, close cards.

---

## 5. Debug Checklist (If CareCard/Detail Does Not Open)

If clicking a request does NOT open the detail card:

| # | Check | How |
|---|-------|-----|
| 1 | Browser console errors | Right-click → Inspect → Console tab — look for red errors |
| 2 | Network errors | Inspect → Network tab — look for failed API calls (4xx/5xx) |
| 3 | Auth/session expired | Check if page shows "Session expired" or redirects to login |
| 4 | JavaScript bundle error | Console may show "Uncaught TypeError" or "Cannot read property" |
| 5 | API returns empty/null | Network tab → check if GET /admin/requests returns data |
| 6 | CloudFront cache stale | Hard refresh: Ctrl+Shift+R (or Cmd+Shift+R on Mac) |
| 7 | Route not matching | Check URL bar — does it change when clicking a request? |
| 8 | Modal/overlay conflict | Is another modal or overlay blocking the click? |

### Quick Fixes to Try

1. **Hard refresh** the page (Ctrl+Shift+R)
2. **Clear site data**: DevTools → Application → Storage → Clear site data
3. **Log out and back in** to refresh the Cognito token
4. **Try a different browser** (Chrome vs Safari vs Edge)

### If None of the Above Works

Report to Matthew/AG:
- Browser name and version
- Console error text (screenshot or copy)
- Whether the request list loads at all
- Whether other admin features (assign, review) still work

---

## 6. Recommendation: Manual vs AG Smoke

### Option A: Matthew Manual Smoke (Preferred)

- Takes 3-5 minutes
- Provides real browser confirmation
- No AG token cost
- Matthew can spot UX issues (spacing, colors, labels) that automated checks miss

### Option B: AG Browser Smoke After Token Refresh

- AG can perform programmatic validation after credits refresh
- Useful if Matthew is unavailable or wants technical detail
- Can capture screenshots and DOM state
- Recommended only if Matthew finds an issue and needs AG to debug

### Recommendation

**Matthew does the manual smoke (Option A).** It's fast, free, and the most reliable confirmation. AG resumes only if an issue is found that needs debugging.

---

## 7. Pass/Fail Criteria

### Pass (12R.1 Complete)

- ✅ Admin dashboard loads
- ✅ Request list shows requests
- ✅ CareCard/detail opens when clicking a request
- ✅ "Pricing & Payment" section is visible
- ✅ Paid request shows read-only paid state
- ✅ Unpaid request shows Generate Payment Link button
- ✅ No console errors related to payment components

### Fail (Needs Investigation)

- ❌ CareCard does not open (blank/error)
- ❌ "Pricing & Payment" section is missing
- ❌ Payment controls show for paid request (guard not working in UI)
- ❌ JavaScript errors in console
- ❌ API calls failing (network errors)

---

## 8. Recommended Next Release

**After 12R.1 passes:** **12S — Client Payment Email Notification Plan**

Scope:
- Postmark template for payment request email
- Automated send after payment-session creation
- Template includes: amount, service description, Pay Now button → Checkout URL
- Audit trail in notification ledger

---

## 9. What This Document Does NOT Authorize

- ❌ Code changes
- ❌ Frontend deployment
- ❌ AWS/Terraform changes
- ❌ Stripe API calls or Checkout Sessions
- ❌ Payments
- ❌ DynamoDB writes
- ❌ Email/SMS sending
- ❌ Cognito changes
- ❌ Mobile/EAS/TestFlight changes
- ❌ Clicking "Generate Payment Link" in production

This is a read-only visual smoke checkpoint. No production actions should be taken.
