# Release 7N: Terms & Privacy Policy Compliance Polish

**Status:** Planning
**Priority:** Low-Medium (compliance hygiene, not blocking operations)
**Risk to Production:** Very Low (content updates + optional backend validation)
**Terraform Required:** No
**Frontend Changes:** Yes (content polish)
**Backend Changes:** Optional (validation enforcement)

---

## 1. Current Findings

### What Already Exists (Implemented & Deployed)

| Component | Status | Location |
|-----------|--------|----------|
| `/terms` route + `TermsOfUse.jsx` | ✅ Live | `web/src/components/TermsOfUse.jsx` |
| `/privacy` route + `PrivacyPolicy.jsx` | ✅ Live | `web/src/components/PrivacyPolicy.jsx` |
| Policy constants (`v1.0`) | ✅ Live | `web/src/constants/policy.js` |
| Footer links (Privacy Policy, Terms of Service) | ✅ Live | `web/src/App.jsx` footer |
| Intake form acceptance checkbox (Step 3) | ✅ Live | `web/src/components/IntakeForm.jsx` |
| Submit disabled without acceptance | ✅ Live | `IntakeForm.jsx` disabled logic |
| Acceptance payload sent to backend | ✅ Live | `accepted_terms`, `accepted_privacy`, `terms_version`, `privacy_version` |
| Error boundary on Privacy page | ✅ Live | `PrivacyPolicy.jsx` ErrorBoundary |
| `TERMS_VERSION` / `PRIVACY_VERSION` constants | ✅ Live | `web/src/constants/policy.js` |

### What Is Missing / Incomplete

| Gap | Severity | Notes |
|-----|----------|-------|
| **Policy content is placeholder/generic** | Medium | Only 4 sections each, ~1 sentence per section. Not real legal language. |
| **Backend does NOT validate acceptance** | Low | `intake_handler.py` stores the fields but doesn't reject submissions without them. Frontend enforces, but curl/API bypass is possible. |
| **Admin CareCard does NOT show acceptance status** | Low | Spec planned this but it wasn't implemented. |
| **No mention of Postmark/email notifications in privacy policy** | Medium | Privacy policy doesn't disclose email sending via Postmark. |
| **No mention of Google Calendar data sharing** | Medium | Privacy policy doesn't disclose calendar integration. |
| **No mention of multi-day/selected-date booking data** | Low | Terms don't cover the scheduling model. |
| **No mention of offline client management** | Low | Terms don't cover admin-managed profiles without consent. |
| **No mention of DynamoDB data retention** | Low | Privacy policy doesn't specify retention periods. |
| **No `source: 'public_intake'` set on public submissions** | Low | The spec planned this but backend doesn't set it. |

### The Kiro Spec Folder (`.kiro/specs/terms-and-privacy-policy/`)

| File | Content | Assessment |
|------|---------|-----------|
| `requirements.md` | 10 detailed requirements with acceptance criteria | Well-written, mostly implemented except Req 6 (backend validation), Req 7 (admin visibility), Req 9 (Phase 2 auth modal) |
| `design.md` | Full architecture, component design, data model, testing strategy | Comprehensive. Most of Phase 1 is already implemented. |
| `tasks.md` | 10 implementation tasks with dependency graph | Tasks 1-5 are done. Tasks 6-10 are partially done or not started. |
| `.config.kiro` | Spec metadata | Standard Kiro config |

---

## 2. Recommendation: What to Do with `.kiro/specs/terms-and-privacy-policy/`

**Recommendation: Convert to a formal docs reference and leave untracked.**

Reasoning:
- The spec served its purpose — most of Phase 1 is implemented
- The remaining tasks (backend validation, admin visibility, Phase 2 auth modal) are future work
- Committing Kiro spec files adds noise to the repo without operational value
- The useful content (what's done, what's remaining) should be captured in the Release 7N plan

**Action:** Leave `.kiro/specs/terms-and-privacy-policy/` untracked (already gitignored). Reference it in this planning doc for context. Delete it after Release 7N is closed if desired.

---

## 3. Proposed Release 7N Scope (Small, Low-Risk)

### Phase 1: Policy Content Update (Frontend-Only)

Update `web/src/constants/policy.js` with production-appropriate content that reflects the actual system:

**Terms of Use — Sections to Add/Update:**
1. Scope of Services (update: mention pet sitting, dog walking, drop-ins, overnight care)
2. Booking & Scheduling (new: describe request → approval → assignment flow, multi-day bookings, cancellation policy)
3. User Responsibilities (update: accurate pet info, access instructions, emergency contacts)
4. Offline Client Management (new: admin may create profiles on behalf of clients who don't use the portal)
5. Communication & Notifications (new: email notifications via Postmark for booking updates)
6. Limitation of Liability (keep existing)
7. Governing Law (keep existing)
8. Changes to Terms (new: version-tracked, re-acceptance may be required)

**Privacy Policy — Sections to Add/Update:**
1. Information We Collect (update: name, email, phone, address, pet details, vet info, emergency contacts, booking dates/times)
2. How We Use Your Information (update: service delivery, scheduling, staff assignment, notifications)
3. Third-Party Services (new: Postmark for email, Google Calendar for scheduling, AWS for hosting/storage, Cognito for authentication)
4. Data Sharing (update: staff see client/pet info for service delivery; no sale of data)
5. Data Storage & Security (new: AWS DynamoDB, encrypted at rest, access-controlled)
6. Data Retention (new: records retained for service history; deleted records purged on request)
7. Your Rights (new: request data export, request deletion, update contact info via portal or admin)
8. Cookies & Analytics (new: minimal — session cookies for auth only, no third-party tracking)
9. Changes to Policy (keep existing pattern)

### Phase 2: Backend Validation (Optional, Low Priority)

Add acceptance validation to `intake_handler.py` for `CUSTOMER_INTAKE` submissions:
- Reject if `accepted_terms` is not `True`
- Reject if `accepted_privacy` is not `True`
- Skip validation for admin-created bookings and portal submissions

This prevents API-level bypass of the consent requirement. Currently the frontend enforces it, but a direct API call could skip it.

### Phase 3: Admin Visibility (Optional, Deferred)

Add "Terms & Privacy" section to CareCard showing acceptance status. This is nice-to-have but not blocking.

---

## 4. Acceptance Criteria (Release 7N Phase 1)

- [ ] `TERMS_CONTENT` in `policy.js` updated with 8 production-appropriate sections
- [ ] `PRIVACY_CONTENT` in `policy.js` updated with 9 production-appropriate sections
- [ ] Content mentions: Postmark email, Google Calendar, AWS hosting, multi-day bookings, offline clients, cancellation policy
- [ ] Content does NOT include fake legal language or placeholder text
- [ ] `/terms` page renders all new sections correctly
- [ ] `/privacy` page renders all new sections correctly
- [ ] `npm run build` passes
- [ ] No backend, Terraform, or API changes
- [ ] Existing intake form acceptance flow unchanged
- [ ] Footer links still work

---

## 5. Files Affected

| File | Change | Phase |
|------|--------|-------|
| `web/src/constants/policy.js` | Update `TERMS_CONTENT` and `PRIVACY_CONTENT` arrays | 1 |
| `src/backend/handlers/intake_handler.py` | Add acceptance validation (optional) | 2 |
| `web/src/components/CareCard.jsx` | Add acceptance display section (optional) | 3 |

### Files NOT Changed

- `TermsOfUse.jsx` — already renders from constants (no change needed)
- `PrivacyPolicy.jsx` — already renders from constants (no change needed)
- `IntakeForm.jsx` — acceptance checkbox already works
- `App.jsx` — routes and footer already correct
- No Terraform
- No API client changes
- No Admin Dashboard changes

---

## 6. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Policy content not legally reviewed | Medium | Low | This is a small pet sitting business, not a regulated industry. Content should be reasonable but doesn't need a lawyer for v1.0. |
| Content update breaks page rendering | Very Low | Low | Same component structure, just more array items |
| Backend validation breaks existing submissions | Low | Medium | Only implement if Matthew approves; frontend already enforces |
| Ryan confused by new policy pages | Very Low | None | Pages already exist; just updating content |

---

## 7. Guardrails

- Do NOT implement backend validation without Matthew's explicit approval
- Do NOT change the acceptance checkbox behavior or payload structure
- Do NOT add Phase 2 (authenticated user modal) — that's a separate future release
- Do NOT add legal disclaimers that imply professional legal review occurred
- Keep language clear, honest, and appropriate for a local pet sitting business
- Do NOT change `TERMS_VERSION` or `PRIVACY_VERSION` — stay at `v1.0` until a real policy revision

---

## 8. AG Implementation Prompt (DO NOT RUN UNTIL MATTHEW APPROVES)

```
AG — implement Release 7N Phase 1: Terms & Privacy Policy Content Update.

Frontend-only change in web/src/constants/policy.js.

1. Update TERMS_CONTENT array with these sections (keep TERMS_VERSION as 'v1.0'):

   Section 1: "Scope of Services"
   - Tog and Dogs provides pet sitting, dog walking, drop-in visits, and overnight care services
   - Services are provided in the client's home or designated location
   - All services are subject to availability and staff scheduling

   Section 2: "Booking & Scheduling"
   - Clients may request services via the online intake form or through admin booking
   - Requests are reviewed and approved by Tog and Dogs staff before scheduling
   - Multi-day and selected-date bookings create individual visit records per day
   - Cancellations should be communicated as early as possible
   - Tog and Dogs reserves the right to cancel or reschedule visits due to weather, safety, or staffing

   Section 3: "User Responsibilities"
   - Provide accurate and complete information about your pets, including medical history, behavioral issues, and care instructions
   - Ensure safe access to your home (working locks, secure gates, clear access codes)
   - Notify Tog and Dogs of any changes to pet health, behavior, or household access
   - Maintain current contact and emergency information

   Section 4: "Offline Client Management"
   - Tog and Dogs staff may create and manage client profiles on behalf of clients who prefer not to use the online portal
   - Offline clients are managed entirely by staff and do not have self-service portal access
   - Offline client records are subject to the same data protection standards as portal users

   Section 5: "Communication & Notifications"
   - Tog and Dogs sends email notifications for booking confirmations, staff assignments, schedule changes, and cancellations
   - Notifications are sent to the email address on file
   - Clients without an email address on file will not receive automated notifications

   Section 6: "Limitation of Liability"
   - Tog and Dogs takes reasonable care in providing services but is not liable for unforeseeable injuries, property damage, or pet behavior beyond our control
   - Clients are responsible for disclosing known risks, aggressive behavior, or health conditions

   Section 7: "Governing Law"
   - These terms are governed by the laws of the state in which Tog and Dogs operates
   - Any disputes will be resolved through good-faith communication before legal action

   Section 8: "Changes to Terms"
   - Tog and Dogs may update these terms from time to time
   - The current version is displayed on this page
   - Continued use of services after changes constitutes acceptance of updated terms

2. Update PRIVACY_CONTENT array with these sections (keep PRIVACY_VERSION as 'v1.0'):

   Section 1: "Information We Collect"
   - Personal information: name, email, phone number, home address
   - Pet information: names, species, breed, age, medical history, care instructions, vet details
   - Emergency contact information
   - Booking details: service dates, times, preferences, notes

   Section 2: "How We Use Your Information"
   - To provide and schedule pet care services
   - To communicate booking confirmations, changes, and cancellations
   - To assign appropriate staff to your visits
   - To maintain care records and visit history
   - To contact you or your emergency contact in case of an issue during a visit

   Section 3: "Third-Party Services"
   - Email notifications are sent via Postmark (a transactional email service)
   - Staff scheduling may use Google Calendar for visit coordination
   - Data is stored on Amazon Web Services (AWS) infrastructure
   - User authentication is managed through AWS Cognito
   - No data is sold to third parties or used for advertising

   Section 4: "Data Sharing"
   - Your information is shared only with Tog and Dogs staff who need it to provide services
   - Staff can see your name, contact info, pet details, and care instructions for assigned visits
   - We do not sell, rent, or share your personal information with unrelated third parties

   Section 5: "Data Storage & Security"
   - Data is stored in encrypted databases on AWS
   - Access is restricted to authorized staff and administrators
   - We use industry-standard security practices including encrypted connections and access controls

   Section 6: "Data Retention"
   - Active client records are retained for the duration of the service relationship
   - Cancelled or completed booking records are retained for operational history
   - Deleted records are permanently removed upon request through the admin portal
   - You may request a copy of your data or request deletion by contacting us

   Section 7: "Your Rights"
   - You may request access to your personal data at any time
   - You may request correction of inaccurate information
   - You may request deletion of your data (subject to operational record-keeping needs)
   - Contact us at support@usmissionhero.com for any data requests

   Section 8: "Cookies & Tracking"
   - This portal uses session cookies for authentication only
   - We do not use third-party tracking, analytics cookies, or advertising pixels
   - No behavioral profiling or cross-site tracking is performed

   Section 9: "Changes to This Policy"
   - We may update this privacy policy from time to time
   - The current version is displayed on this page
   - Material changes will be communicated via email to active clients

3. Run: npm run build (in web/)
4. Confirm no errors.
5. Do NOT deploy until Matthew reviews the content.

Return: files changed, build result, word count of each section.
```

---

## 9. Commit Command (After Approval)

```bash
git add web/src/constants/policy.js
git commit -m "docs: Release 7N Phase 1 — production terms and privacy policy content"
```

---

## 10. Summary

| Question | Answer |
|----------|--------|
| Should `.kiro/specs/terms-and-privacy-policy/` be tracked? | **No** — leave untracked. It served its purpose. |
| Should it be converted to formal docs? | **No** — this planning doc captures what's relevant. |
| Is the feature already implemented? | **Mostly yes** — pages, routes, footer, checkbox, payload all work. |
| What's actually missing? | Real policy content (currently placeholder) + optional backend validation. |
| Is this blocking? | **No** — Ryan's testing is not affected. Clients see the checkbox and pages. |
| Recommended scope? | Update `policy.js` content only. Backend validation is optional Phase 2. |
