# Project Release Notes & History

This index tracks the evolution of the Tog and Dogs application, including structural changes, security hardening, and operational remediation.

## 🌟 Featured / Recent
- [**Release 18B: Cognito Company ID Custom Attribute Schema Addition Implementation**](release-18b-cognito-company-id-custom-attribute-schema-addition.md) (2026-06-23) — ✅ **Complete** — Add custom:company_id custom attribute to Cognito user pool schema via Terraform; configure client app read/write permissions
- [**Release 17Y: Company ID Resolution Hardening Implementation**](release-17y-company-id-resolution-hardening-implementation.md) (2026-06-22) — ✅ **Complete** — TENANT_RESOLUTION_MODE environment toggle, structured logging, CloudWatch metric filters/alarms
- [**Release 17W: Tenant Provisioning Script Implementation and Company ID Resolution Verification**](release-17w-tenant-provisioning-script-implementation.md) (2026-06-21) — ✅ **Complete** — Provisioning script, 72 new tests, DEFAULT_COMPANY_ID risk documented
- [**Release 17U: Credential Security Cleanup Closeout**](release-17u-credential-security-cleanup-closeout.md) (2026-06-21) — ✅ **Complete** — All shared dev passwords rotated
- [**Release 17R: Safe Tenant Metadata Edit Smoke and Audit Validation**](release-17r-safe-tenant-metadata-edit-smoke-and-audit-validation.md) (2026-06-21) — ✅ **Completed** — Safe production edit verification and audit trail validation
- [**Release 17P-Fix2: Platform Admin Edit Flow Review/Confirmation Fix**](release-17p-fix2-platform-admin-edit-review-flow.md) (2026-06-21) — ✅ **Completed** — Single state-driven modal flow, risky change style, no-change safeguards
- [**Release 17P-Fix1: Platform Admin UI CORS Preflight Remediation**](release-17p-fix1-platform-admin-fetch-cors-remediation.md) (2026-06-21) — ✅ **Completed** — API Gateway OPTIONS/CORS redeployed, preflight issues resolved
- [**Release 17P: Platform Management UI MVP Implementation**](release-17p-platform-management-ui-mvp-closeout.md) (2026-06-21) — ✅ **Completed** — platform_admin Console UI built, guarded, and deployed
- [**Release 17N: Platform Admin Access Bootstrap and Authorized API Smoke**](release-17n-platform-admin-access-bootstrap-and-authorized-api-smoke.md) (2026-06-21) — ✅ **Completed** — platform_admin group bootstrapped, 401/403 enforcement confirmed, 454/454 tests passed
- [**Release 17L: Platform Admin Backend APIs**](release-17l-platform-admin-backend-apis-closeout.md) (2026-06-21) — ✅ **Completed** — Secure platform admin Cognito group and backend routes
- [**Release 17J: Entitlement Structured Logging Remediation**](release-17j-entitlement-structured-logging-remediation-closeout.md) (2026-06-21) — ✅ **Completed** — Fixed logging level configuration so structured events propagate to CloudWatch
- [**Release 17I: Phase 1 Entitlement Enforcement Alarm Readiness and Enablement**](release-17i-entitlement-alarm-readiness-and-enable-plan.md) (2026-06-21) — ✅ **Completed** — Enabled Phase 1 entitlement enforcement in production and added alarm alerting
- [**Release 17E: Phase 1 Entitlement Gate Wiring Deployment and Smoke Validation**](release-17e-phase-1-entitlement-gate-wiring-deployment-and-smoke-validation.md) (2026-06-20) — ✅ **Completed** — Deployed and verified in production
- [**Release 17D: Phase 1 Entitlement Gate Wiring Implementation**](release-17d-phase-1-entitlement-gate-wiring-implementation.md) (2026-06-20) — ✅ **Completed** — Phase 1 entitlement gates wired and tested
- [**Release 17B: Entitlement Enforcement Core Helpers**](release-17b-entitlement-enforcement-core-helpers.md) (2026-06-20) — ✅ **Completed** — Core helpers & tests implementation
- [**Release 15J: Apple Beta App Review Submission**](release-15j-apple-beta-app-review-submission.md) (2026-06-19) — ⏳ **Submitted — Awaiting Apple Review**
- [**Release 15H: Matthew Multi-Role Internal TestFlight Smoke Validation**](release-15h-matthew-multi-role-internal-testflight-smoke-validation-closeout.md) (2026-06-19) — ✅ **All Roles Passed** — Admin, Staff, Client validated
- [**Release 15E: Internal TestFlight Smoke Validation**](release-15e-internal-testflight-smoke-validation-closeout.md) (2026-06-19) — ✅ **Passed** — Build 1.0.0 (4), Matthew admin/staff smoke
- [**Release 15D: Fresh Internal TestFlight Build**](release-15d-fresh-internal-testflight-build.md) (2026-06-19) — ✅ **Build & Submission Completed**
- [**Release 15C: Mobile Read-Only Payment Status Indicator**](release-15c-mobile-read-only-payment-status-indicator.md) (2026-06-19) — ✅ **Completed**
- [**Release 15B: Mobile Readiness Audit**](release-15b-mobile-readiness-audit.md) (2026-06-19) — ✅ **Completed**
- [**Release 11F: Tenant Enforcement Production Deployment & Smoke Validation**](release-11f-tenant-enforcement-production-deployment-and-smoke-validation.md) (2026-06-14) — ✅ **Deployed & Production Validated**
- [**Release 11E: Tenant Enforcement Hardening Implementation**](release-11e-tenant-enforcement-hardening-implementation.md) (2026-06-14) — ✅ **All Backend Changes Implemented & 340/340 Tests Green**
- [**Release 7T: Matthew Production Monitoring Checklist**](release-7t-validation-closeout.md) (2026-05-29) — ✅ **Accepted & Closed** — Docs only
- [**Release 7S: Internal Hardening Tests**](release-7s-validation-closeout.md) (2026-05-29) — ✅ **Accepted & Closed** — Tests + gitignore cleanup, 28/28 passed
- [**Release 7Q: Production Operations Readiness**](release-7q-validation-closeout.md) (2026-05-28) — ✅ **Accepted & Closed** — Docs only
- [**Release 7P: Admin/Mobile UX Polish**](release-7p-validation-closeout.md) (2026-05-28) — ✅ **Deployed & Production Validated**
- [**Release 7N: Terms & Privacy Policy Content**](release-7n-validation-closeout.md) (2026-05-28) — ✅ **Deployed & Production Validated**
- [**Release 7M: Planning & Strategy Consolidation**](release-7m-validation-closeout.md) (2026-05-28) — ✅ **Accepted & Closed** — Docs only
- [**Release 7L: Admin Request List Compact Date Display**](release-7l-admin-request-list-compact-date-display-polish-validation.md) (2026-05-27) — ✅ **Deployed & Production Validated**
- [**Release 7K: Staff Assigned Multi-Day Email Hotfix**](release-7k-staff-assigned-multi-day-email-display-hotfix-validation.md) (2026-05-27) — ✅ **Deployed & Production Validated**
- [**Release 7J: Notification Content Polish**](release-7j-notification-content-polish-validation.md) (2026-05-27) — ✅ **Deployed & Production Validated**
- [**Release 7H: Admin Request List UI Polish**](release-7h-admin-request-list-ui-polish-validation.md) (2026-05-26) — ✅ **Deployed & Production Validated**
- [**Release 7G: Multi-Day Assignment Handler Fix**](release-7g-multi-day-assignment-handler-fix-validation.md) (2026-05-26) — ✅ **Deployed & Production Validated**
- [**Release 7F: Notification Dedup Stabilization**](release-7f-production-notifications-stabilization-validation.md) (2026-05-26) — ✅ **Deployed & Production Validated**
- [**Release 7E: Multi-Day Visit Scheduling**](release-7e-multi-day-jobs-validation.md) (2026-05-25) — ✅ **Deployed & Production Validated**
- [**Release 7D: Google Calendar Hardening**](release-7d-calendar-hardening-validation.md) (2026-05-25) — ✅ **Deployed & Production Validated**
- [**Release 7C: Push Notification Backend Readiness**](release-7c-phase1-validation.md) (2026-05-24) — ✅ **Deployed & Production Validated**
- [**Release 7B: Admin Data Cleanup & UX Hardening**](release-7b-phase-2-frontend-fallback-hardening-validation.md) (2026-05-24) — ✅ **Deployed & Production Validated**
- [**Release 7A: Admin Offline Client Manual Booking**](release-7a-admin-offline-client-manual-booking-validation.md) (2026-05-23) — ✅ **Deployed & Production Validated**
- [**Release 6H: Configurable Protected Admin Accounts**](release-6h-configurable-protected-admin-accounts.md) (2026-05-22) — ✅ **Deployed & Production Validated**
- [**Release 6G: Staff Calendar Sync Reliability**](release-6g-staff-calendar-sync-reliability.md) (2026-05-22) — ✅ **Deployed & Production Validated**
- [**Release 6F: Repeat Customer / Offline Client Booking**](release-6f-repeat-customer-offline-booking.md) (2026-05-22) — ✅ **Deployed & Production Validated**
- [**Release 6E: User Permissions & Identity Alignment**](release-6e-user-permissions-identity.md) (2026-05-21) — ✅ **Deployed & Production Validated**
- [**Release 6D: Admin Filter Integrity & Safe Delete Guardrails**](release-6d-admin-filter-integrity.md) (2026-05-21) — ✅ **Deployed & Production Validated**
- [**Release 6C: Postmark Production Readiness**](release-6c-postmark-production-readiness.md) (2026-05-21) — ✅ **Validated — External Delivery Confirmed**
- [**Release 6B: Notification Coverage Expansion**](release-6b-notification-coverage-expansion.md) (2026-05-19) — ✅ **Accepted — Production Validated**
- [**Release 6A: Client Approval Email Template**](release-6a-approval-email-template.md) (2026-05-18) — ✅ **Live — Production Validated**
- [**Release 5F: Archived Pets Visibility & Restore**](release-5f-archived-pets-visibility-restore.md) (2026-05-15) — ✅ **Accepted**
- [**Release 5D: Client Management Pet Visibility**](release-5d-client-pet-visibility.md) (2026-05-15) — ✅ **Accepted**
- [**Release 5C: Archive Pet from CareCard**](release-5c-archive-pet.md) (2026-05-15) — ✅ **Accepted**
- [**Release 5B: Add New Pet from CareCard**](release-5b-add-pet-from-carecard.md) (2026-05-15) — ✅ **Accepted**
- [**Release 5A: Multi-Pet Independent Editing**](release-5a-multi-pet-editing-logic.md) (2026-05-15) — ✅ **Accepted (after Hotfix 2)**
- [**Release 4E: Staff Assignment & Scheduling Logic**](release-4e-staff-assignment-logic.md) (2026-05-14)
- [**Consolidated Workflow & Data Integrity Summary**](workflow/workflow-cleanup-and-data-integrity-summary.md) (2026-05-04)
- [Request List Filter Count Hotfix](admin-dashboard/request-list-filter-count-hotfix.md) (2026-05-04)
- [Workflow Cleanup & Separation](workflow/workflow_cleanup.md) (2026-05-03)

---

## 📂 Categories

### 🔄 Workflow & Status Lifecycle
*   [Workflow Cleanup & Separation](workflow/workflow_cleanup.md)
*   [Process Workflow Guided Actions](workflow/process-workflow-guided-actions.md)
*   [Intake Process Next Step Modal Fix](workflow/intake-process-next-step-modal-fix.md)
*   [Intake Process M&G Workflow Fix](workflow/intake-process-mg-workflow-fix.md)
*   [Workflow Status Map Hotfix](workflow/workflow-status-map-hotfix.md)
*   [Workflow Calendar Sync Fix](workflow/workflow-calendar-sync-and-message-fix.md)
*   [Dispatcher Timeline Status Update](workflow/dispatcher-timeline-status-update.md)

### 📊 Admin Dashboard & UI
*   [Release 5A: Multi-Pet Independent Editing](release-5a-multi-pet-editing-logic.md) (✅ Accepted after Hotfix 2)
*   [Release 4E: Staff Assignment & Scheduling Logic](release-4e-staff-assignment-logic.md)
*   [Request List Filter Count Hotfix](admin-dashboard/request-list-filter-count-hotfix.md)
*   [Admin Data Issue Quick Filter](admin-dashboard/admin-data-issue-quick-filter.md)
*   [Admin Staff Assignment Dropdown Fix](admin-dashboard/admin-staff-assignment-dropdown-fix.md)
*   [Admin Quick Filter Simplification](admin-dashboard/admin-quick-filter-simplification.md)
*   [Admin Bulk Status Move Fix](admin-dashboard/admin-bulk-status-move-fix.md)
*   [Admin Audit Logging](admin-dashboard/admin-audit-logging.md)
*   [Admin Lifecycle Action Visibility](admin-dashboard/admin-lifecycle-action-visibility.md)
*   [Admin Soft Delete & Archive Filtering](admin-dashboard/admin-soft-delete-archive-filtering.md)

### 🛡️ RBAC, Auth & Security
*   [Release 18B: Cognito Company ID Custom Attribute Schema Addition Implementation](release-18b-cognito-company-id-custom-attribute-schema-addition.md)
*   [Release 17Y: Company ID Resolution Hardening Implementation](release-17y-company-id-resolution-hardening-implementation.md)
*   [Release 17R: Safe Tenant Metadata Edit Smoke and Audit Validation](release-17r-safe-tenant-metadata-edit-smoke-and-audit-validation.md)
*   [Release 17P-Fix2: Platform Admin Edit Flow Review/Confirmation Fix](release-17p-fix2-platform-admin-edit-review-flow.md)
*   [Release 17P-Fix1: Platform Admin UI CORS Preflight Remediation](release-17p-fix1-platform-admin-fetch-cors-remediation.md)
*   [Release 17P: Platform Management UI MVP Implementation](release-17p-platform-management-ui-mvp-closeout.md)
*   [Release 17N: Platform Admin Access Bootstrap and Authorized API Smoke](release-17n-platform-admin-access-bootstrap-and-authorized-api-smoke.md)
*   [Release 11F: Tenant Enforcement Production Deployment & Smoke Validation](release-11f-tenant-enforcement-production-deployment-and-smoke-validation.md)
*   [Release 11E: Tenant Enforcement Hardening Implementation](release-11e-tenant-enforcement-hardening-implementation.md)
*   [Staff Protected Admin Guardrails](rbac-auth/staff-protected-admin-guardrails.md)
*   [Staff Profile Sync Security Controls](rbac-auth/staff-profile-sync-security-controls.md)
*   [RBAC Staff/Client Least Privilege](rbac-auth/rbac-staff-client-least-privilege.md)
*   [Backend RBAC Purge Safety Tests](rbac-auth/backend-rbac-purge-safety-tests.md)
*   [Profile Dropdown Auth Context](rbac-auth/profile-dropdown-auth-context.md)
*   [RBAC Owner/Client Access](rbac-auth/rbac-owner-client-access.md)
*   [Tenant Hardening Phase 4](rbac-auth/tenant-hardening-phase-4.md)

### 💾 Data Integrity
*   [Request Record Data Integrity Cleanup](data-integrity/request-record-data-integrity-cleanup.md)
*   [Permanent Delete Records](data-integrity/permanent-delete-records.md)
*   [Permanent Delete Key Resolution Hotfix](data-integrity/permanent-delete-key-resolution-hotfix.md)

### 📅 Calendar & Integrations
*   [Google Calendar Approved Trigger](calendar/google-calendar-approved-trigger.md)

### 👤 Client Portal
*   [Client Portal Ownership Boundaries](client-portal/client-portal-ownership-boundaries-phase-5c.md)
*   [Client Access Management Phase 5a](client-portal/client-access-management-phase-5a.md)

### 🚀 Deployment & Operations
*   [Production UAT Validation](deployment/production-uat-staff-client-workflow-validation.md)
*   [Production Audit Remediation](deployment/production-audit-remediation.md)
*   [Backend Intake Validation Tests](deployment/backend-intake-validation-tests.md)
*   [Backend Quoted Status Transition](deployment/backend-quoted-status-transition.md)

---

## 🗄️ Archive
Historical notes, branding updates, and superseded documentation can be found in the [**Archive Folder**](archive/).
