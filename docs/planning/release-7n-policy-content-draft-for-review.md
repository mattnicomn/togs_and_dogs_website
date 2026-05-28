# Release 7N: Proposed Policy Content — For Matthew's Review

**Status:** Draft — awaiting Matthew's approval before implementation
**Target file:** `web/src/constants/policy.js`
**Scope:** Content update only. No backend, Terraform, or infrastructure changes.

> **Note:** This content is written in plain language appropriate for a local pet sitting business. It is NOT legal advice. Matthew should review and adjust any sections that don't match his business practices or local requirements. If formal legal review is desired, consult a local attorney before publishing.

---

## Terms of Use (Proposed)

### Section 1: About These Terms

These Terms of Use govern your use of the Tog and Dogs operations portal at toganddogs.usmissionhero.com. By submitting a service request or using the client portal, you agree to these terms. If you do not agree, please do not submit a request or use the portal.

### Section 2: Services Provided

Tog and Dogs provides in-home pet care services including dog walking, drop-in visits, overnight care, and pet sitting. All services are performed at the client's home or a designated location. Services are subject to staff availability, scheduling, and approval by Tog and Dogs management.

### Section 3: Booking and Scheduling

- Service requests are submitted through the online intake form or created by Tog and Dogs staff on behalf of clients.
- All requests are reviewed and must be approved before scheduling.
- Approved bookings are assigned to available staff and added to the operational schedule.
- Multi-day and selected-date bookings create individual visit records for each scheduled day.
- Tog and Dogs reserves the right to decline, reschedule, or cancel visits due to weather, safety concerns, staffing, or other operational reasons.

### Section 4: Cancellations

- Clients may request cancellation of scheduled visits by contacting Tog and Dogs directly or through the portal.
- Cancellation requests are reviewed by staff and may be approved or denied based on timing and circumstances.
- Tog and Dogs may cancel visits at any time for safety or operational reasons and will make reasonable efforts to notify the client.

### Section 5: Client Responsibilities

- Provide accurate and complete information about your pets, including health conditions, behavioral issues, medications, and care instructions.
- Ensure safe and accessible entry to your home, including working locks, secure gates, and current access codes or key locations.
- Notify Tog and Dogs promptly of any changes to pet health, behavior, household access, or emergency contacts.
- Maintain current contact information so staff can reach you if needed during a visit.

### Section 6: Offline Client Management

- Tog and Dogs staff may create and manage client profiles on behalf of clients who prefer not to use the online portal.
- These profiles are managed entirely by staff. Offline clients do not have self-service portal access unless they later choose to create an account.
- Offline client records are subject to the same care and data handling standards as portal users.

### Section 7: Communication

- Tog and Dogs sends email notifications for booking confirmations, staff assignments, schedule updates, and cancellations to the email address on file.
- Clients without an email address on file will not receive automated notifications. Staff will communicate with these clients directly.
- By providing your email address, you consent to receiving service-related communications.

### Section 8: Limitation of Liability

- Tog and Dogs takes reasonable care in providing services but cannot guarantee against all risks associated with pet care.
- Tog and Dogs is not liable for injuries, property damage, or pet behavior that is beyond reasonable control, including undisclosed health conditions or behavioral issues.
- Clients are responsible for disclosing known risks, aggressive behavior, escape tendencies, or medical conditions before services begin.

### Section 9: Changes to These Terms

- Tog and Dogs may update these terms from time to time. The current version number is displayed on this page.
- Continued use of services or the portal after changes are published constitutes acceptance of the updated terms.
- Material changes will be communicated to active clients.

---

## Privacy Policy (Proposed)

### Section 1: Information We Collect

We collect information you provide when requesting services or using the portal:

- **Contact information:** Name, email address, phone number, home address
- **Pet information:** Pet names, species, breed, age, feeding instructions, medication details, behavioral notes, vet and emergency contact details
- **Booking information:** Requested service dates, time preferences, service type, scheduling notes, preferred staff
- **Account information:** Login credentials (managed through AWS Cognito authentication)

We also collect information created during service delivery:
- Visit records, staff assignments, scheduling history, cancellation records
- Communication records (notification delivery status)

### Section 2: How We Use Your Information

We use your information to:
- Schedule and deliver pet care services
- Assign appropriate staff to your visits
- Send booking confirmations, schedule updates, and cancellation notices
- Maintain care records so staff have accurate pet information during visits
- Contact you or your emergency contact if an issue arises during a visit
- Improve our services and operational processes

### Section 3: Third-Party Services

We use the following third-party services to operate the portal:

| Service | Purpose | Data Shared |
|---------|---------|-------------|
| **Postmark** | Sending email notifications | Recipient email, notification content |
| **Google Calendar** | Staff scheduling and visit coordination | Visit dates, times, client name, pet name, service type |
| **Amazon Web Services (AWS)** | Application hosting, data storage, authentication | All portal data (encrypted at rest) |
| **AWS Cognito** | User login and authentication | Email, login credentials |

We do not sell, rent, or share your personal information with unrelated third parties for marketing or advertising purposes.

### Section 4: Who Can See Your Information

- **Tog and Dogs staff** assigned to your visits can see your name, contact info, pet details, care instructions, and access information needed to perform the service.
- **Tog and Dogs administrators** can see all client, pet, and booking records for operational management.
- **No one else** has access to your information unless required by law.

### Section 5: Data Storage and Security

- Your data is stored in encrypted databases on Amazon Web Services (AWS) infrastructure.
- Access to client data is restricted to authorized Tog and Dogs staff and administrators.
- We use encrypted connections (HTTPS), access controls, and authentication to protect your information.
- No system is perfectly secure. We take reasonable precautions but cannot guarantee absolute security.

### Section 6: Data Retention

- Active client and pet records are retained for the duration of the service relationship.
- Completed and cancelled booking records are retained for operational history and reference.
- Records moved to "Trash" or "Archived" status may be permanently deleted by administrators.
- You may request a copy of your data or request deletion by contacting us.

### Section 7: Your Rights

You have the right to:
- Request access to the personal information we hold about you
- Request correction of inaccurate information
- Request deletion of your data (subject to reasonable operational recordkeeping needs)
- Withdraw consent for email notifications by contacting us

To exercise any of these rights, contact us at support@usmissionhero.com.

### Section 8: Cookies and Tracking

- This portal uses session cookies for authentication purposes only.
- We do not use third-party analytics, advertising cookies, or tracking pixels.
- No behavioral profiling or cross-site tracking is performed.

### Section 9: Changes to This Policy

- We may update this privacy policy from time to time. The current version is displayed on this page.
- Material changes will be communicated to active clients via email.
- Continued use of the portal after changes are published constitutes acceptance of the updated policy.

---

## Sections Intentionally NOT Included

| Topic | Reason |
|-------|--------|
| Payment processing / billing terms | The app does not currently handle payments or credit cards |
| HIPAA / medical data compliance | Not applicable — this is pet care, not human healthcare |
| GDPR-specific provisions | Business operates in the US; GDPR applies only if serving EU residents |
| CCPA-specific provisions | Only required for businesses meeting California revenue/data thresholds |
| Children's privacy (COPPA) | Portal is not directed at children under 13 |
| Arbitration / class action waiver | Overly aggressive for a local pet sitting business |
| Indemnification clause | Unnecessarily adversarial for the client relationship |
| Intellectual property / content ownership | No user-generated content beyond pet info |
| API / developer terms | No public API |

---

## Matthew Review Checklist

Before approving implementation, please confirm:

- [ ] **Services description is accurate** — Do you offer all listed services (walking, drop-in, overnight, pet sitting)?
- [ ] **Cancellation policy matches your practice** — Is the described cancellation flow how you actually handle it?
- [ ] **Offline client description is acceptable** — Are you comfortable with the language about creating profiles on behalf of clients?
- [ ] **Communication consent language is appropriate** — Is "by providing your email, you consent to service communications" sufficient?
- [ ] **Liability limitation is reasonable** — Does the limitation of liability section match your comfort level?
- [ ] **Third-party services are correct** — Postmark, Google Calendar, AWS, Cognito — are there others?
- [ ] **Data retention description is accurate** — Is the described retention approach how you actually manage records?
- [ ] **Contact email is correct** — Is support@usmissionhero.com the right contact for data requests?
- [ ] **No payment/billing language needed** — Confirm the app does NOT handle payments currently.
- [ ] **Governing law state** — Should the Terms specify a particular state? (Currently says "the state in which Tog and Dogs operates")
- [ ] **Legal review desired?** — Do you want a local attorney to review before publishing, or is this sufficient for now?

---

## AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 7N Phase 1: Terms & Privacy Policy Content Update.

Frontend-only change in web/src/constants/policy.js.
Do NOT change TERMS_VERSION or PRIVACY_VERSION (keep 'v1.0').
Do NOT change any other files.

1. Replace the TERMS_CONTENT array with the approved Terms of Use sections
   (9 sections as specified in the approved planning document).

2. Replace the PRIVACY_CONTENT array with the approved Privacy Policy sections
   (9 sections as specified in the approved planning document).

3. Each section should be an object: { title: "Section Title", body: "Section content..." }

4. For sections with bullet points, use newline characters (\n) between items
   within the body string. The rendering component will handle display.

5. For the Privacy Policy Section 3 (Third-Party Services), include the table
   content as a formatted string within the body field.

6. Run: npm run build (in web/)
7. Confirm no errors.
8. Do NOT deploy.

Return: files changed, build result, confirmation that /terms and /privacy
render correctly in local dev server.
```

---

## Deployment (After Approval + Implementation)

```bash
# Build
cd web && npm run build

# Deploy frontend only
aws s3 sync web/dist/ s3://togs-and-dogs-prod-toganddogs-hosting --delete --profile usmissionhero-website-prod
aws cloudfront create-invalidation --distribution-id <DIST_ID> --paths "/*" --profile usmissionhero-website-prod

# Commit
git add web/src/constants/policy.js
git commit -m "docs: Release 7N — production terms and privacy policy content"
```
