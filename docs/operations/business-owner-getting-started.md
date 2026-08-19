# Togs & Dogs Business Owner Getting Started

**Status:** LOCALLY COMPLETE / INDEPENDENTLY REVIEWED (`GUIDE_CORRECT`) / COMMITTED AND PUSHED / REPOSITORY DOCUMENTATION ONLY / NOT PUBLIC

**Primary audience:** A new Togs & Dogs business owner/operator who is not a developer

**Secondary audience:** Matthew or another authorized platform administrator assisting with onboarding

**Last updated:** 2026-08-11

This internal guide describes the product and onboarding process that exist today. It is not a public signup page, a promise of future features, or authorization to create a tenant, user, integration, payment account, or mobile release.

---

## 1. What Togs & Dogs Does

Togs & Dogs is a tenant-aware pet-care operations platform. Its current production web experience supports:

- client profiles, including portal-enabled and staff-managed offline clients;
- pet profiles and care details;
- customer care requests and staff-created visits;
- request review, approval, assignment, completion, cancellation, archive, and restore workflows;
- single-day and multi-day scheduling;
- staff profiles and login-account administration;
- a shared business-calendar integration when it has been configured for the tenant;
- transactional email notifications;
- a validated Stripe sandbox booking-payment workflow; and
- an internally distributed iOS and Android mobile app.

The core operating system is live, but onboarding a new business is not self-service. Live payments, subscription billing, public mobile distribution, pricing/signup, analytics, and multi-location management are not available as normal production capabilities.

## 2. Who Does What

### Business Owner Actions

After the business and owner account have been set up, an owner can normally use the web Operations Portal to:

- review requests, approve or decline work, and manage cancellations;
- create visits for existing or offline clients;
- assign staff and monitor the schedule;
- create and maintain staff, client, and pet profiles;
- invite or link staff and client login accounts within the existing tenant;
- disable normal staff or client access while preserving records;
- use tenant-level Calendar connect or reconnect controls when the tenant has an enabled provider; and
- review operational status and export data.

### Platform Admin / Setup Actions

Matthew or another authorized platform administrator is currently required to:

- approve and create a new business tenant;
- choose the internal tenant identifier and set tenant metadata;
- configure the tier, entitlements, limits, and active/disabled state;
- create the first owner login with the correct tenant assignment and role;
- set or change the tenant display name used by the admin shell;
- configure Calendar provider metadata and any provider-specific prerequisites;
- configure notification-provider and payment-provider settings;
- grant internal mobile tester access; and
- investigate cross-tenant, protected-account, identity, integration, or runtime problems.

### Developer / Infrastructure Actions

Developer or infrastructure work is still required for changes to application behavior, AWS/Cognito configuration, tenant provisioning tooling, provider secrets, Terraform-managed settings, deployments, public mobile releases, live Stripe activation, or data repair outside normal UI workflows. A business owner should not run repository, AWS, Terraform, database, Cognito, Stripe, or mobile-distribution commands.

## 3. Current Onboarding Model

Onboarding is approval-controlled and assisted. There is no public business signup, tenant-creation wizard, automatic subscription checkout, or automatic integration setup.

| Onboarding step | Current owner action | Current setup owner | Automated today? |
|---|---|---|---|
| Approve the business, scope, and operating model | Provide business requirements and approved account information privately | Matthew / product decision | No |
| Create tenant metadata | Review the business display name and intended tier | Platform admin / developer | Provisioning tooling exists, but execution is gated |
| Assign business data scope | None | Platform admin / Cognito setup | No; tenant assignment must be set correctly |
| Create the first owner account | Receive the private invitation | Platform admin | Assisted Cognito creation |
| Assign owner role | Confirm expected access | Platform admin | No owner self-service |
| Complete first login | Set a new private password on web | Business owner | Yes, after setup |
| Configure branding | Approve the display name | Platform admin | No owner settings screen |
| Configure tier and limits | Confirm expected operating needs | Platform admin | Enforcement is automated after configuration |
| Configure Calendar | Complete OAuth only when instructed and enabled | Platform admin plus owner/admin | Partially automated |
| Configure email notifications | Confirm intended recipients and operating policy | Platform admin / developer | No owner-wide setup wizard |
| Configure payments | None during normal onboarding | Deferred | No; live payments are blocked |
| Grant mobile access | Accept an internal testing invitation if approved | Platform admin | No public download |
| Add staff, clients, and pets | Use normal web UI after setup | Business owner/admin | Yes within the active tenant and its limits |

Do not begin client operations until the tenant is active, the owner can sign in, the correct business name is visible, the expected queues are empty or tenant-correct, and required integrations have an understood status.

## 4. Tenant / Business Setup

A **tenant** is one business's operating boundary inside the shared platform. It controls which clients, pets, staff, requests, jobs, settings, entitlements, and integration metadata an authenticated user can access.

Production uses strict multi-tenant resolution. Every authenticated request must resolve to the user's assigned business; unresolved or invalid tenant context is rejected rather than silently routed to a default business. Tenant-scoped database access, user listings, branding, disabled-tenant enforcement, and Calendar token resolution have been implemented and validated.

The repository records two current tenants:

- the active Togs & Dogs business tenant; and
- `test_tenant_alpha`, an internal isolation-validation tenant.

The internal test tenant is not a customer account, demo account, general sandbox, or template that an owner may reuse. Creating another tenant or repurposing the test tenant requires Matthew's explicit approval.

Business data is expected to remain separated by tenant. If an owner sees another business's name, client, pet, staff member, request, schedule, or integration state, stop work, sign out, and escalate immediately. Do not try to correct suspected cross-tenant data from the UI.

## 5. Account and Role Model

| Role | Practical capabilities | Important boundaries | How access starts |
|---|---|---|---|
| **Owner** | Full tenant operations: requests, assignment, staff/client administration, normal pet management, exports, and enabled tenant integrations | Not a platform administrator; cannot create tenants or change platform configuration. Privileged account changes remain guarded. | First owner is created by platform administration; additional privileged access should be approval-controlled |
| **Admin** | Day-to-day tenant administration similar to owner: requests, assignment, staff/client/pet management, account actions, and enabled integrations | Cannot access the Platform Admin console. Should not be used as a casual staff role. | Owner/admin can create an admin login in the existing tenant, but privileged role assignment should be reviewed |
| **Staff** | View assigned operational work and schedule, and complete assigned visits with supported notes | Normal navigation is schedule-focused. Staff cannot manage staff/client accounts, create administrative visits, export all data, assign workers, decide cancellations, or change Calendar connections. | Owner/admin creates a profile-only staff record or an invited login account |
| **Client** | View their own bookings and pets, submit care requests, request cancellation, and edit supported fields on existing pets | Cannot see other clients, use admin queues, assign staff, or administer the business. Mobile does not add/delete/archive pets. | Owner/admin can invite/link an account; a client may also be linked through supported intake/profile flows |
| **Platform admin** | View and manage tenant metadata, tiers/status, metrics, and platform audit history | Global operator role; never a substitute for tenant owner/admin and never assigned to a normal business owner | Created and controlled only by platform administration |

Account creation and profile creation are distinct. A profile can exist without a login. An invited login also needs the correct tenant assignment and Cognito group before it is safe to use.

## 6. First Login and Account Recovery

### First Login

1. Use the approved web sign-in route from the invitation or onboarding instructions.
2. Enter the invited email address and temporary password privately supplied through the approved invitation process.
3. When **Create New Password** appears, choose and confirm a new private password.
4. Confirm that the displayed business name and role are correct before viewing or changing records.
5. Sign out when finished, especially on a shared device.

The web Operations Portal supports Cognito's first-login new-password challenge. The internal mobile app does not currently provide a complete temporary-password challenge screen, so first login should be completed on web before mobile use.

### Normal Sign-In and Sessions

- Use only your own account; do not share owner/admin credentials.
- A valid session routes the user to role-appropriate features.
- Expired sessions require sign-in again.
- Use the visible **Log Out** action when leaving a device.
- Report a wrong business name, wrong role, unexpected access denial, or unexpected data immediately.

### Password Recovery

- Owners/admins can use current Staff Management and Client Management actions to resend an invite, send a reset email, or set a temporary password for eligible non-protected users. Self-service changes to one's own protected/security settings are intentionally restricted.
- The current internal mobile app has a **Forgot Password** code flow for supported internal accounts.
- Web customer self-service password recovery is deployed in production and passed Matthew's live Cognito E2E validation on 2026-08-15.
- Protected, orphaned, duplicate, or unusual identity states that the normal recovery flow cannot complete still require owner or platform help.

Never send passwords in ordinary chat, tickets, documents, or screenshots.

## 7. Business Profile and Branding

The admin experience can display the tenant's business name in the shell and profile context. Administrative routes use a tenant-aware header and a minimal tenant-aware footer; public/client marketing routes continue to use the Togs & Dogs public brand.

Current limits:

- the business display name is managed through Platform Admin, not an owner settings page;
- there is no owner self-service branding editor;
- there is no general tenant logo-upload workflow documented as supported;
- public/client route branding is not a fully white-labeled tenant site; and
- tier, status, limits, and Calendar-provider metadata are also platform-managed.

If branding is wrong, do not compensate by entering a different company name in staff or client profiles. Escalate the tenant metadata correction.

## 8. Staff Setup

Use **Staff Management** on the web Operations Portal.

### Create a Staff Profile

Choose the profile-only option when a worker needs to appear in scheduling but does not yet need a login. Enter a clear display name, the operational role, availability/assignability state, and a distinct scheduling color where offered.

### Create an Invited Staff Login

Choose the onboarding/login option, provide the staff member's business-approved email, and normally choose the **Staff** role. The system creates a tenant-scoped login, sends the branded invitation, and leaves the account in a first-login state until the temporary password is changed.

Use Owner or Admin roles only for genuinely privileged operators and after reviewing that decision. Do not assign the Platform Admin role.

### Maintain Staff Access

- Edit profile details and assignment settings in Staff Management.
- Disable a departing staff member rather than deleting history.
- Resend an invitation only when the account is still awaiting first login.
- Use password reset or temporary-password actions only for the intended user.
- Protected, self, orphaned, and certain invited-account states intentionally disable risky actions.
- Active staff count toward the tenant's staff entitlement; disabled staff do not consume an active slot.

If the UI reports an orphaned login, protected account, missing identity, duplicate account, or tier limit, stop and escalate instead of creating a second profile as a workaround.

## 9. Client Setup

Use **Client Management** on the web Operations Portal.

### Portal-Enabled Client

Create a login and profile when the client will use the web portal or approved internal mobile app. A valid email is required. The system creates a tenant-scoped client login, sends a branded invitation with temporary credentials, and links the profile for client-only access.

Owners/admins can edit client information, resend eligible invitations, trigger supported password actions, link an existing login, and disable access. A disabled client remains available for historical records but cannot use the portal.

### Offline or Staff-Managed Client

Choose **Create Profile Only (No Login)** for a client who will book by phone, text, or staff assistance. Email is optional. An email-less offline client:

- has no Cognito login;
- cannot use web or mobile self-service;
- can still have pets, requests, jobs, assignments, and Calendar-synced visits; and
- requires staff to communicate updates manually.

If the client later wants portal access, add and verify an email, then use the normal login-link/onboarding action. Do not create a duplicate client profile.

See the [Offline Client Management guide](./offline-client-management-guide.md) for the detailed workflow.

## 10. Pet Management

Pet records hold identity and care information such as name, species, breed, age, health/behavior notes, care and feeding instructions, and veterinarian contact details where supplied.

- **Owner/admin:** Can manage tenant-authorized pet records through Client Management, including creating, editing, archiving, and restoring supported records.
- **Staff:** Backend pet actions are role-authorized for supported staff workflows, but the normal staff UI is schedule-focused and does not expose full Client Management. Do not rely on a general staff pet-administration screen.
- **Web client:** Can view their pets and edit the supported customer-owned fields on existing pet records.
- **Internal mobile client:** Can view and edit supported fields on existing pets in **My Pets**.
- **Mobile boundary:** Mobile does not provide pet creation, deletion, archive, or restore.

Archive is the normal reversible action when a pet should no longer appear as active. Avoid permanent deletion when bookings or historical records still reference the pet. If a booking shows a deleted/unavailable pet warning, preserve the booking and escalate the record issue rather than inventing replacement data.

## 11. Care Request, Booking, and Job Workflow

### Terms

- A **request** is the parent record for what the client asked for, including client/pet context, service, dates, windows, notes, and lifecycle status.
- A **booking** is the operational meaning of an approved or scheduled request. The UI may use “request,” “visit,” and “booking” based on context, but the parent record remains the request.
- A **job** is an individual service occurrence created from an approved request. A single-day request normally has one job; a multi-day request has a child job for each selected date.

### End-to-End Flow

1. **Customer request/intake:** A customer submits the public or authenticated care form and accepts the required terms/privacy acknowledgements. The request enters **Pending Review**. An owner/admin may instead create a visit for an existing client; that staff-created visit begins **Approved**.
2. **Request review:** The owner/admin verifies client, pet, service, date, visit-window, and notes. Depending on the case, the request may move through Meet & Greet, profile, quote, or ready-for-approval steps.
3. **Approval or decline:** Approval confirms the request can enter operations and triggers job creation. Decline ends the request. A customer approval email may be sent when an eligible email recipient exists.
4. **Job creation:** The system creates the service job or per-date child jobs. The parent keeps the overall customer request; jobs carry the individual service dates used by scheduling and completion.
5. **Staff assignment:** An owner/admin assigns an active, assignable worker. Assignment moves the work to **Assigned/Scheduled**, syncs configured Calendar events, and sends eligible client/staff notifications.
6. **Service delivery and completion:** Staff see their assigned work and can complete their own visits with supported notes. Owner/admin can monitor and correct the overall workflow.
7. **Cancellation:** A client may request cancellation. An owner/admin approves or denies the request. Approved cancellation changes the parent and child workflow, removes synchronized Calendar events where present, and sends eligible cancellation notifications.
8. **Archive or trash:** Completed history can be archived. Trash and permanent purge are different actions; purge is irreversible and should not be part of ordinary daily cleanup.

Use the portal for scheduling and lifecycle changes. Do not edit synchronized Calendar events directly as a substitute for changing the booking.

The [Admin Operations Quick Reference](./admin-quick-reference.md) provides the current operator-oriented queue and lifecycle walkthrough. When an older guide's label differs, follow the label and available action shown by the current production UI; the canonical core states include Pending Review, Approved, Assigned, Completed, Cancelled, Archived, and Deleted.

## 12. Google Calendar

Calendar integration is tenant/business-scoped, not a personal connection for each staff member.

- Token storage and resolution are tenant-scoped.
- Togs & Dogs currently has one configured Google provider connection.
- The internal test tenant reports provider **none** and status **not configured**.
- A future tenant does not automatically receive Google Calendar access. Provider metadata and prerequisites must be configured first.
- Owners/admins may see Connect or Reconnect only when the tenant metadata enables that capability.
- Staff can see shared-calendar status for awareness but cannot connect, reconnect, or disconnect it.
- The tenant-wide Disconnect control is intentionally absent from the normal UI as a safeguard.

When configured, assignment/reassignment creates or updates the relevant service events, multi-day requests use per-date child-job events, and approved cancellations remove known events. If Calendar is not configured, the business can still use core request and scheduling records, but no Google event sync should be expected.

If connection fails, verify the tenant's Calendar status and escalate. Do not repeatedly authorize different Google accounts, delete tokens, or manually edit synchronized events. The [Google Calendar reauthorization runbook](./google-calendar-reauthorization.md) is **platform-admin-only** and may contain technical troubleshooting context not intended as a normal owner procedure.

## 13. Notifications

Postmark transactional email is active. Current event coverage includes:

- new request notice to the configured admin recipient;
- approval notice to an eligible client;
- scheduled-visit notice to an eligible client;
- assignment notice to the assigned staff member;
- cancellation notices to eligible client, staff, and admin recipients;
- staff/client welcome invitations; and
- sandbox payment-link email when deliberately used in the internal payment workflow.

Multi-day assignment/scheduling notices are deduplicated to avoid one email per child job. Missing email, disabled event flags, suppression, quota controls, duplicate protection, or a non-email offline client can cause an intentional skip.

Do not test notifications using real client addresses casually. Do not repeatedly resend invitations or payment emails. For delivery problems, verify the profile address and spam folder, then escalate with the request type and approximate time—never include passwords, tokens, or payment links.

Technical notification inspection belongs to platform operations. See the [Emergency Response Checklist](./emergency-response-checklist.md) for owner-safe escalation steps.

## 14. Payments

**Payments and live subscriptions are not part of normal production onboarding.**

The booking-payment workflow has been built and validated in Stripe sandbox mode, including admin payment-link controls, payment email, Checkout redirect, webhook updates, and payment-status display. That does not authorize real charges.

Current boundaries:

- Stripe remains sandbox-only.
- Live Stripe activation is blocked by the business EIN and additional business approval/readiness steps.
- No live SaaS subscription Checkout exists for new tenants.
- No business-owner subscription billing dashboard exists.
- No self-service pricing, plan purchase, or plan change flow exists.
- Owners must not enter or request live card or bank details during onboarding.
- Real client payment links and real charges are not approved.

The [Payment Workflow Quick Reference](./payment-workflow-quick-reference.md) is for authorized internal sandbox operations only until Matthew explicitly confirms a later live-mode release.

## 15. Mobile App

Mobile access is controlled internal distribution, not public store availability.

### iOS

- Version: `1.0.0 (6)`
- Distribution: internal TestFlight
- Physical-iPhone remediation validation: passed
- Public Apple App Store: not released

### Android

- Version: `1.0.0`, versionCode `4`
- Distribution: Google Play Internal Testing
- Remediation validation: passed in the reported environment
- Ryan's physical Android install and operational review: confirmed 2026-08-15; the full historical remediation smoke matrix was not rerun
- Google Play Production: not released

Owners/admins can use internal mobile dashboards, requests, and schedule views. Staff receive an assigned-work schedule. Clients can view bookings, submit a care request, and view/edit existing pets. Staff/client/user administration, Calendar connection management, and notification settings remain web-only.

Tester access must be approved and granted by platform administration. Ryan completed the documented Android operational review, but any additional build, distribution change, tester-access change, or production-write testing requires explicit approval. Do not promise a public download link or add testers without approval.

## 16. Typical Business-Owner Day

1. Sign in to the web Operations Portal and confirm the correct business name.
2. Review **Pending Review**, **Needs Action**, or the current intake queue for new requests and cancellation requests.
3. Verify client, pet, service, dates, visit windows, care notes, and any Meet & Greet or quote needs.
4. Approve or decline requests using the guided action available for the current state.
5. Review the Scheduler and assign active, appropriate staff to approved work.
6. Check that assigned work appears correctly and that the Calendar status has no warning when Calendar is expected.
7. Review staff progress, completed visits, cancellations, and any data or notification warnings.
8. Handle client follow-up manually for offline clients and escalate payment/configuration matters rather than attempting live payment work.
9. Archive completed history when appropriate; avoid purge as routine housekeeping.
10. Log out on shared devices.

## 17. Operational Checklists

### Initial Setup

- [ ] Business onboarding and tenant creation explicitly approved.
- [ ] Owner account created with the correct tenant and Owner role.
- [ ] First web login and new-password challenge completed.
- [ ] Correct business name visible in the admin shell and profile.
- [ ] No other tenant's data visible.
- [ ] Tier, active status, and expected limits confirmed by platform administration.
- [ ] Calendar shows the expected configured or not-configured state.
- [ ] Mobile/tester access treated as optional and separately approved.
- [ ] Payments understood to be sandbox-only and outside normal onboarding.

### Before Taking the First Client

- [ ] Staff profiles, roles, assignability, and contact details reviewed.
- [ ] At least one appropriate worker can be selected for assignment.
- [ ] Client profile strategy chosen: portal-enabled or offline.
- [ ] Notification addresses reviewed; no test uses a real recipient without approval.
- [ ] Calendar expectations and manual fallback understood.
- [ ] Emergency escalation process available.

### Before the First Booking

- [ ] Client and pet records are complete enough for safe care.
- [ ] Service, dates, visit windows, access/care notes, and emergency details verified.
- [ ] Meet & Greet or quote requirement resolved when applicable.
- [ ] Staff assignment and schedule capacity checked.
- [ ] No live payment link or card detail requested.

### Daily

- [ ] Review new requests and cancellation requests.
- [ ] Assign approved work.
- [ ] Review today's and upcoming schedule.
- [ ] Check Calendar/integration warnings.
- [ ] Follow up on offline-client communication.
- [ ] Review incomplete, cancelled, and completed work.

### Weekly

- [ ] Review staff access and assignability.
- [ ] Review disabled/duplicate/data-issue warnings without purging real records.
- [ ] Archive appropriate completed history.
- [ ] Check notification or Calendar issues that recurred during the week.
- [ ] Export operational data if the business process calls for it.

### When Adding Staff

- [ ] Choose profile-only versus invited login intentionally.
- [ ] Use Staff for normal worker access.
- [ ] Confirm email, role, tenant, and assignability before sending an invitation.
- [ ] Ask the user to complete first login on web.
- [ ] Verify the user sees only the intended business and role.
- [ ] Escalate protected/orphaned/duplicate identity warnings.

### When Something Goes Wrong

- [ ] Stop before repeating writes, invitations, charges, or integration actions.
- [ ] Record the page, action, time, visible error, role, and affected record type.
- [ ] Do not include passwords, tokens, private payment links, or unnecessary client details.
- [ ] Try safe browser/session checks only when appropriate.
- [ ] Preserve records and escalate cross-tenant, auth, Calendar, notification, payment, or runtime issues.

## 18. Known Limitations

- New-business onboarding is not fully self-service.
- Tenant creation, first-owner setup, tenant assignment, branding, tier/limits, provider metadata, and infrastructure configuration require platform help.
- Pricing, business signup, subscription Checkout, billing dashboard, and plan changes are not self-service.
- Live Stripe payments and subscriptions are blocked; only the internal sandbox workflow is validated.
- Mobile is internal-only on TestFlight and Google Play Internal Testing; neither public store has a production release.
- Ryan's physical Android install and operational review are confirmed; the full historical remediation smoke matrix was not rerun, and further build/distribution/production-write testing remains approval-gated.
- Web customer self-service password recovery is production deployed and passed live Cognito E2E validation; protected or unusual identity states can still require platform support.
- Some work on the current repository main branch is not necessarily part of the latest validated web production baseline; only explicit deployment records establish production availability.
- A Calendar connection is not automatically available to each tenant and requires provider configuration.
- Staff/client account actions exist, but protected, orphaned, duplicate, or unusual Cognito states can still require platform support.
- Analytics dashboard is not implemented.
- Multi-location support is not implemented.
- Public white-label branding and owner-controlled logo/settings are not implemented.

## 19. Support and Escalation Boundary

Contact platform/developer support when:

- the tenant, business name, role, limits, active status, or visible data is wrong;
- the first owner account or tenant assignment must be created or corrected;
- normal UI cannot resolve an invitation, password, protected-account, or orphaned-identity issue;
- Calendar is unavailable, connected to the wrong account, repeatedly failing, or not enabled for the tenant;
- notifications stop broadly, an address is suppressed, or provider settings require inspection;
- any payment configuration, live-mode request, refund, webhook issue, or subscription question arises;
- the site/API is unavailable or repeatedly returns server errors;
- a data repair, irreversible purge, tenant disable/restore, or infrastructure change is considered; or
- mobile tester access, a new build, or public distribution is requested.

When escalating, provide the affected feature, approximate time, user role, what you expected, what appeared, and safe steps already tried. Include only the minimum client/record detail required. Never include passwords, verification codes, tokens, full payment links, card details, credentials, or session data.

For incident triage, use the [Emergency Response Checklist](./emergency-response-checklist.md).

## 20. Self-Service Gap Matrix

This internal-facing matrix distinguishes existing tenant operations from new-business productization.

| Capability | Owner self-service today? | Platform help required? | Future automation candidate |
|---|---|---|---|
| Tenant creation | No | Yes—approval, metadata, provisioning, validation | Gated Platform Admin onboarding workflow; later owner signup only after business/security decisions |
| First owner account | No | Yes—tenant assignment and Owner role | Tenant-scoped owner invitation with automatic validation |
| Branding | No | Yes—display name; public/advanced branding unsupported | Owner settings for approved display/logo fields with audit and preview |
| Staff invite | Yes, for normal users in an existing tenant | For protected, duplicate, orphaned, tier-limit, or failed identity states | Hardened invite lifecycle, status guidance, and least-privilege role templates |
| Client invite | Yes, for normal users in an existing tenant | For duplicate/linking, protected, or failed identity states | Guided invite/link/offline-upgrade workflow |
| Google Calendar connection | Partial—owner/admin can connect or reconnect only when enabled | Yes for provider metadata, prerequisites, or repair; disconnect is safeguarded | Provider onboarding, readiness checks, scoped OAuth, health, and rollback workflow |
| Subscription billing | No | Yes; currently unavailable | Stripe subscription Checkout after EIN, pricing, policy, and lifecycle approval |
| Pricing / plan changes | No | Yes; product decision required | Published plans plus controlled upgrade/downgrade workflow |
| Booking payment configuration | No | Yes; sandbox only | Live-mode readiness workflow after EIN and payment-policy approval |
| Mobile tester access | No | Yes—internal distribution only | Controlled tester invitation and release-channel management |
| Account recovery | Partial—production web customer self-service recovery, internal mobile forgot-password, and owner/admin actions for other eligible users | Yes for protected, orphaned, duplicate, or unusual states | Add consistent first-login/recovery status guidance and deploy the separately gated branded Cognito/Postmark sender |
| Analytics | No | Yes; feature not implemented | Tenant-scoped operational dashboard after metric/product definition |

## 21. Ranked Future Automation Opportunities

1. **Gated tenant onboarding orchestrator.** The highest-friction path spans approval, metadata, tier/limits, active state, validation, and rollback. Start as Platform Admin automation with a dry-run/review/apply boundary. True owner signup should wait for pricing, billing, support, and security decisions.
2. **First-owner identity provisioning and acceptance.** Manual tenant assignment and group mapping are high-risk because an error can create wrong-tenant or wrong-role access. Automate a tenant-scoped owner invitation, validation checklist, first-login completion state, and safe disable/reissue path.
3. **Calendar provider onboarding and health workflow.** Provider metadata, OAuth readiness, account selection, health checks, and recovery are split across platform and owner actions. Automate readiness checks and a guided owner connection only for enabled tenants; keep token handling and destructive disconnect protected.
4. **Commercial onboarding: plans, live subscriptions, and billing.** This is the largest business self-service gap, but it must follow EIN completion, approved pricing, subscription lifecycle rules, policies, support/rollback semantics, and live-payment validation. It is not safe to automate first.
5. **Unified access center for staff, clients, recovery, and mobile eligibility.** Existing invitations work, but identity states, linking, recovery, protected accounts, and tester access are fragmented. A guided access center could expose safe owner actions, route exceptional states to platform help, and prevent duplicate-profile workarounds.

A future onboarding wizard therefore needs, at minimum: approved plan/tier definitions; live-billing decision and lifecycle semantics; tenant and owner rollback rules; security-reviewed role/invite policies; configurable branding boundaries; per-tenant Calendar capability metadata; notification defaults; audit logging; idempotent retry; and an explicit human approval gate before any production tenant or owner is created.

## 22. Related Internal Documentation

### Business Owner / Operations

- [Admin Operations Quick Reference](./admin-quick-reference.md)
- [Offline Client Management](./offline-client-management-guide.md)
- [Payment Workflow Quick Reference — sandbox only](./payment-workflow-quick-reference.md)
- [Emergency Response Checklist](./emergency-response-checklist.md)

### Platform Admin / Technical Context

- [Current Project State](../project-continuity/current-state.md)
- [Project Guardrails](../project-continuity/guardrails.md)
- [SaaS Maturity and Multi-Business Readiness Backlog](../backlog/saas-maturity-and-multi-business-owner-readiness.md)
- [Google per-tenant token isolation validation](../release-notes/release-21h-google-per-tenant-token-isolation-production-validation.md)
- [Current internal mobile pair](../release-notes/phase-24a-9c2-paired-remediation-revalidation-closeout.md)
- [Web customer password recovery status](../release-notes/release-web-customer-self-service-password-recovery.md)

These links are internal repository documentation. Technical runbooks do not grant approval to change production systems.
