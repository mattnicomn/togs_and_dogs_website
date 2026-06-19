# Release 15A: Mobile TestFlight and Staff Workflow Readiness Plan

**Status:** Planning
**Priority:** Medium-High (can proceed independently of EIN/live payments)
**Risk to Production:** None (planning only)
**Terraform Required:** No
**Code Changes:** None
**Scope:** Plan mobile/TestFlight readiness and staff workflow polish

---

## 1. Current Mobile/TestFlight Baseline

### iOS Build Status

| Item | Value |
|------|-------|
| Last TestFlight build | 1.0.0 (3) |
| EAS Project | `@mattnicomn/tog-and-dogs` (ID: `6b77d541-ec62-4950-8375-aef7d21c12ea`) |
| iOS Bundle ID | `com.usmissionhero.toganddogs` |
| ASC App ID | `6778488478` |
| Apple Team ID | `2RA84Y5HZ3` |
| Platform | Expo / React Native |

### Tester Status

| Tester | Type | Status |
|--------|------|--------|
| Matthew | Internal TestFlight | ✅ Active (can install builds) |
| Ernest | Internal TestFlight (if ASC access) | ⏳ Unknown / needs confirmation |
| Ryan | External TestFlight | ❌ Not yet added — planned for future |

### Known Mobile App Capabilities (from 8G–10K)

| Feature | Status |
|---------|--------|
| Cognito auth + SecureStore | ✅ |
| Role-based navigation (admin/staff/client) | ✅ |
| Admin request list | ✅ |
| Admin request approval | ✅ |
| Staff assigned visits / schedule view | ✅ |
| Staff mark completed | ✅ |
| Staff visit notes | ✅ |
| Client/pet detail (stack navigation) | ✅ |
| Tablet layout polish | ✅ |
| Staff daily workflow view | ✅ |
| Per-visit/per-day completion | ✅ |
| API health banner | ✅ |

### Known Gaps / Unknowns

| Gap | Impact | Priority |
|-----|--------|----------|
| Mobile does not show payment status (paid/pending/etc.) | Staff/admin unaware of payment state on mobile | Medium |
| No payment link generation from mobile | Admin must use web for payment actions | Low (web-first is correct) |
| Staff cannot see payment-related info | May need "Payment Received" indicator | Medium |
| Ryan has not been added as External tester | Cannot validate real staff workflow | High |
| Build may be stale (1.0.0 build 3 is from earlier releases) | Recent backend changes may need fresh build | Medium |
| Apple Beta App Review not submitted | Required for External TestFlight | High (for Ryan) |

---

## 2. Staff Workflow Readiness

### What Staff Should Be Able to Do from Mobile

| Capability | Current Status | Notes |
|------------|----------------|-------|
| See today's assigned visits | ✅ | Daily schedule view |
| See upcoming visits | ✅ | Schedule list |
| View visit details (client, pet, address, notes) | ✅ | Stack navigation |
| Mark visit as completed | ✅ | Per-visit completion |
| Add visit notes | ✅ | Text input on completion |
| See which visits are paid (read-only indicator) | ❌ Missing | New — needs implementation |
| Generate payment links | ❌ Not planned | Web-only is correct for now |
| Send payment emails | ❌ Not planned | Web-only is correct for now |
| Contact client (phone/text link) | ⚠️ Partial | Client phone shown if available |
| View pet care instructions | ✅ | Pet detail view |
| Report issues/escalate | ❌ No in-app mechanism | Use phone/text to Matthew for now |

### Staff Workflow Gaps to Address

| # | Gap | Priority | Fix Type |
|---|-----|----------|----------|
| 1 | No payment status indicator on mobile visits | Medium | Frontend (mobile) |
| 2 | No "visit confirmed/paid" badge in schedule | Medium | Frontend (mobile) |
| 3 | Fresh build needed to pick up any recent API changes | High | EAS build |
| 4 | Ryan not on External TestFlight | High | Apple setup |

---

## 3. Client Workflow Readiness (Mobile)

### What Clients See on Mobile

| Capability | Status | Notes |
|------------|--------|-------|
| View upcoming bookings | ✅ | Client appointments view |
| View booking status | ✅ | Status labels |
| View payment status (paid/pending) | ❌ Missing | Would be helpful indicator |
| Pay from mobile | ❌ Not planned | Client pays via email link → web Checkout |
| Contact support | ❌ No in-app mechanism | Email/phone outside app |
| View pet details | ✅ | If client profile is linked |

### Client Mobile Gaps

- Payment status visibility would be nice-to-have but not blocking
- Payment itself remains web-only (Stripe Checkout link from email)
- No mobile payment actions planned for v1

---

## 4. Admin/Mobile Alignment

### Tenant/Company Model

- Mobile uses same `get_current_company_id()` + Cognito auth as web
- Same `tog_and_dogs` company_id
- Same tenant enforcement (11E) applies to mobile API calls
- No additional tenant work needed for mobile

### Payment Status on Mobile

| Decision | Recommendation |
|----------|---------------|
| Show payment status on mobile? | Yes — read-only indicator (badge/label) |
| Allow payment actions from mobile? | No — web-only for v1 |
| Show payment amount on mobile? | Optional — admin/staff may benefit from seeing amount |

If payment status is added to mobile:
- Staff sees: "Payment: Pending" / "Payment: Received" / no badge
- Admin sees: same as staff (no generate/send from mobile)
- Read-only — no buttons, no modals

---

## 5. TestFlight Plan

### Internal Validation (Matthew/Ernest)

| Step | Action |
|------|--------|
| 1 | Build fresh iOS build via EAS (`eas build --platform ios --profile production`) |
| 2 | Submit to TestFlight via EAS (`eas submit --platform ios`) |
| 3 | Wait for App Store Connect processing (~5–15 min) |
| 4 | Install via TestFlight on Matthew's device |
| 5 | Smoke test: login, schedule view, visit details, mark complete, notes |
| 6 | Verify no crashes or auth issues |
| 7 | Confirm API connectivity (health banner green) |
| 8 | If Ernest has ASC access, add as Internal tester |

### External Validation (Ryan — Future)

| Step | Action | Blocker |
|------|--------|---------|
| 1 | Add Ryan's Apple ID as External TestFlight tester | Requires Beta App Review |
| 2 | Submit build for Beta App Review | Apple review (~24–48h) |
| 3 | Ryan installs via TestFlight invitation | Ryan's availability |
| 4 | Ryan smoke tests: daily schedule, visit completion, notes | Ryan's engagement |
| 5 | Collect feedback | Iteration based on findings |

### Apple Beta App Review Considerations

| Requirement | Status |
|-------------|--------|
| App description/metadata in ASC | ⚠️ May need review |
| Screenshots | ⚠️ May need update for current UI |
| Privacy policy URL | ✅ Published |
| Contact info | ✅ Available |
| Test account credentials (for Apple reviewer) | ⚠️ Need a demo/test account |
| App does not crash on launch | Must verify with fresh build |

---

## 6. Recommended Release Breakdown

| Release | Scope | Priority | EIN Needed? |
|---------|-------|----------|-------------|
| **15B** | Mobile readiness audit: verify current build compiles, identify stale deps | High | ❌ No |
| **15C** | Staff schedule/dispatch polish: payment status read-only indicator | Medium | ❌ No |
| **15D** | Fresh EAS build + Internal TestFlight submission | High | ❌ No |
| **15E** | Internal TestFlight smoke validation (Matthew) | High | ❌ No |
| **15F** | Ryan External TestFlight readiness (Apple metadata, Beta Review) | Medium | ❌ No |
| **15G** | Ryan onboarding and first external TestFlight install | Medium | ❌ No |

All releases in this track are independent of the EIN/live-payment blocker.

---

## 7. Risks and Blockers

| Risk | Impact | Mitigation |
|------|--------|------------|
| Build fails due to stale Expo/RN dependencies | Cannot produce new TestFlight build | Run `npx expo-doctor` and resolve before build |
| Apple Beta App Review rejection | Cannot add Ryan as External tester | Ensure screenshots/metadata/privacy are current |
| Ryan availability | Cannot validate real staff workflow | Schedule specific testing window with Ryan |
| Auth token issues on mobile | Login failures | Verify Cognito pool config matches mobile app |
| Mobile API calls hit payment endpoints accidentally | Unintended DynamoDB writes | Mobile has no payment UI — risk is near-zero |
| Fresh build needed after backend changes | Stale cached behavior | Always build from latest `main` |

### Not Blocked By

- ❌ EIN (no dependency)
- ❌ Live Stripe (no dependency)
- ❌ Payment track (read-only status only)
- ❌ Second tenant (single-tenant mobile)

---

## 8. What This Document Does NOT Authorize

- ❌ Running EAS build
- ❌ Submitting to TestFlight
- ❌ Adding testers
- ❌ Modifying mobile code
- ❌ Deploying anything
- ❌ Stripe/payment actions
- ❌ AWS/Terraform changes
- ❌ DynamoDB/Cognito changes
- ❌ Sending emails/SMS

This is a planning document only. Each follow-up release (15B–15G) requires separate approval.
