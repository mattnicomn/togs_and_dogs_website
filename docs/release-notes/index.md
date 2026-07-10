# Project Release Notes & History

This index tracks the evolution of the Tog and Dogs application, including structural changes, security hardening, and operational remediation.

## 🌟 Featured / Recent
- [**Release 22O: Pending Cancellation Records Review and Cleanup/Processing Plan**](../planning/release-22o-pending-cancellation-records-review-and-cleanup-plan.md) (2026-07-10) — ✅ **Planning Complete** — Decision framework for handling 2 visible pending cancellation records (Joey Rockwell, TestPet_ScenarioB); defines classification tree, safe handling procedures, cleanup/retention policy, and Matthew validation checklist.
- [**Release 22N: Production Release State Reconciliation After 22M Hotfix**](../operations/release-22m-production-state-reconciliation.md) (2026-07-10) — ✅ **Documentation** — Documents production/main divergence, deployed bundle reference, and 22J paused state after 22M hotfix deployment.
- [**Release 22M: Pending Cancellation Visibility Hotfix Production Deployment**](release-22m-pending-cancellation-visibility-hotfix-production-deployment.md) (2026-07-10) — ✅ **PASS** — Deploy Release 22L pending cancellation visibility fix to production via a temporary hotfix branch `hotfix/22m-cancellation-visibility-hotfix` based on Release 22I (`48874f0`), ensuring Release 22J remains paused and un-deployed.
- [**Release 22L: Pending Cancellation Request Admin Visibility Fix Pre-Deploy**](release-22l-pending-cancellation-admin-visibility-fix-predeploy.md) (2026-07-10) — ✅ **PASS (Pre-Deploy)** — Resolve the visibility gap for client pending cancellation requests by refactoring status helpers, active list inclusion predicates, and action dropdown configurations in the admin portal frontend; pending cancellations are now correctly visible, countable, and actionable under the Needs Action queue.
- [**Release 22J: Centralized Profile Editor MVP Pre-Deploy**](release-22j-centralized-profile-editor-mvp-predeploy.md) (2026-07-10) — ✅ **PASS (Pre-Deploy)** — Implement centralized Profile Editor side drawer (modal layout with unsaved-changes guard, responsive panel, and 7 structured sections) and simplify staff cards in the Active Staff List; enforce protected account and USmissionhero safeguards and defer platform admin governance.
- [**Release 22I: Orphaned Identity Detection Production Deployment and Validation**](release-22i-orphaned-identity-detection-production-deployment-validation.md) (2026-07-10) — ✅ **PASS** — Deploy Release 22H orphaned identity detection and safe display logic to the production environment; verify display states and button-disabling safeguards.
- [**Release 22H: Orphaned Identity Detection Backend/Frontend Pre-Deploy**](release-22h-orphaned-identity-detection-predeploy.md) (2026-07-09) — ✅ **PASS (Pre-Deploy)** — Implement read-only backend and frontend support to safely detect and display staff login identity states in Staff Management; disable security/unlink actions for orphaned accounts and add warning banner.
- [**Release 22E: Care Request Validation UX Polish Production Deployment**](release-22e-care-request-validation-ux-polish-production-deployment.md) (2026-07-09) — ✅ **PASS (Manually Validated)** — Deployed Release 22D frontend validation UX polish in production; verify top summary, context-aware range error, select dates button, required visit windows error, and S3/CloudFront sync
- [**Release 22D: Care Request Date Validation Copy and Auto-Fill UX Polish**](release-22d-care-request-date-validation-ux-polish.md) (2026-07-09) — ✅ **PASS (Manually Validated)** — Refine /book Step 2 validation: context-aware date error copy, visually distinct Auto-fill button (renamed to "Select Dates from Range"), separate Preferred Visit Windows inline error, simplified top summary — frontend-only
- [**Release 22C: Immediate Identity Action and Care Request Validation Fixes Production Deployment**](release-22c-immediate-identity-action-and-care-request-validation-production-deployment.md) (2026-07-09) — ⚠️ **PARTIALLY VALIDATED** — Staff resend invite PASS (Ryan York); /book validation UX resolved by 22D/22E; staff disabled button bubbling validation pending
- [**Release 22B: Immediate Identity Action and Care Request Validation Fixes**](release-22b-immediate-identity-action-and-care-request-validation-fixes.md) (2026-07-09) — ✅ **PASS (Pre-Deploy / Deployed via 22C)** — Implement backend and frontend fixes for triaged defects: resolve resend-invite UnboundLocalError, add missing staff account security API Gateway resources to Terraform config, stop card bubbling on staff action buttons, and improve intake form date/required-field validation UX
- [**Release 21H: Google Per-Tenant Token Isolation Production Deployment and Validation**](release-21h-google-per-tenant-token-isolation-production-validation.md) (2026-07-09) — ✅ **PASS (Manually Validated)** — Deployed and validated Release 21G Google per-tenant token isolation backend Lambdas in production; verify compatibility fallback for tog_and_dogs, isolated unconfigured status for test_tenant_alpha, and credential shielding
- [**Release 21G: Google Per-Tenant Token Isolation Implementation**](release-21g-google-per-tenant-token-isolation-implementation.md) (2026-07-02) — ✅ **PASS** — Implement backend per-tenant Google token secret resolution and scoped token storage callback, protect legacy global fallback from disconnect deletions, gate non-configured tenants, and verify with 8 new unit tests

- [**Release 21E: Calendar Metadata Defaults Production Deployment and Validation**](release-21e-calendar-metadata-defaults-production-deployment-validation.md) (2026-07-02) — ✅ **PASS (Manually Validated)** — Deploy Release 21D calendar provider metadata defaults backend Lambdas and frontend assets in production; verify safe derived config defaults, unconfigured UI fallbacks, and Platform Admin details

- [**Release 21D: Tenant Calendar Provider Metadata Defaults Implementation**](release-21d-tenant-calendar-provider-metadata-defaults-implementation.md) (2026-07-02) — ✅ **PASS** — Implement code-level tenant calendar provider metadata defaults, expose safe metadata fields in tenant-info and Platform Admin API responses, update frontend to check provider, and verify with 7 new tests
- [**Release 21B: Calendar UI Unconfigured-State Cleanup**](release-21b-calendar-ui-unconfigured-state-cleanup.md) (2026-07-02) — ✅ **PASS (Manually Validated)** — Deployed and validated frontend-only calendar UI unconfigured-state cleanup in production; verify unconfigured status cards, blocked connection triggers, and hidden health banners for non-default tenants
- [**Release 20F: Disabled Tenant Backend Access Enforcement Production Deployment and Validation**](release-20f-disabled-tenant-backend-access-enforcement-production-validation.md) (2026-07-02) — ✅ **PASS** — Deploy and validate Release 20E backend gating changes in production; verify 403 TenantDisabled blocks, minimal tenant-info responses, active tenant isolation, and audit logging
- [**Release 20E: Disabled Tenant Backend Access Enforcement Implementation**](release-20e-disabled-tenant-backend-access-enforcement-implementation.md) (2026-06-28) — ✅ **PASS** — Implement centralized require_active_tenant helper, protect 8 tenant-scoped handlers, handle tenant-info minimal status specially, and add 14 new backend tests
- [**Release 20C: Controlled Tenant Disable and Restore Validation**](release-20c-controlled-tenant-disable-restore-validation.md) (2026-06-28) — ✅ **PASS** — Execute and validate tenant disable/restore lifecycle operations, audit logging, and document backend access enforcement findings
- [**Release 19N: Tenant Branding Model Cleanup**](release-19n-tenant-branding-model-cleanup.md) (2026-06-27) — ✅ **PASS** — Dynamic shell logo, conditional admin footer, platform attribution updated to `usmissionhero`; manual validation complete (both tenants)
- [**Release 19M: Production Deployment and Tenant Isolation Revalidation**](release-19m-production-deployment-and-tenant-isolation-revalidation.md) (2026-06-27) — ✅ **PASS** — Deploy backend calendar gates, Cognito filters, tenant-info endpoint, and frontend dynamic display updates; data/access isolation and tenant display branding verified (display fix completed by Release 19N)
- [**Release 19L: Frontend Tenant Display Remediation (Pre-Deploy)**](release-19l-frontend-tenant-display-remediation-predeploy.md) (2026-06-27) — ✅ **Complete** — Integrate with GET /admin/tenant-info to dynamically display tenant brand names in header shell and profile labels
- [**Release 19K: Backend Tenant Isolation Remediation Plan (Pre-Deploy)**](release-19k-backend-tenant-isolation-remediation-predeploy.md) (2026-06-27) — ✅ **Complete** — Implement backend Google Calendar tenant gate, Cognito user group/company filtering, and safe tenant-info endpoint
- [**Release 19J: Second-Tenant Owner Login Isolation Remediation Planning**](../planning/release-19j-second-tenant-owner-login-isolation-remediation-plan.md) (2026-06-27) — ✅ **Complete** — Plan backend filters for Cognito, isolate Google Calendar, and design dynamic UI elements
- [**Release 19I: Second-Tenant Owner Login Isolation Defect Triage**](release-19i-second-tenant-owner-login-isolation-defect-triage.md) (2026-06-27) — ⚠️ **PARTIAL PASS (Data Remediated)** — Diagnose tenant isolation defects; data isolation is remediated, display branding remains pending
- [**Release 19H: Controlled Second-Tenant Owner Cognito User Creation**](release-19h-controlled-second-tenant-owner-cognito-user-creation.md) (2026-06-26) — ⚠️ **PARTIAL PASS (Data Remediated)** — Create Cognito owner user for test_tenant_alpha; data isolation is verified, display branding remains pending
- [**Release 19G: Second-Tenant Owner Cognito User Creation Approval Checkpoint and Runbook**](release-19g-second-tenant-owner-cognito-approval-runbook.md) (2026-06-26) — ✅ **Complete** — Define temporary password parameters, group mappings, verification commands, and approval gates for test_tenant_alpha owner creation
- [**Release 19F: Second-Tenant Owner Cognito User Creation Planning**](../planning/release-19f-second-tenant-owner-cognito-user-creation-planning.md) (2026-06-25) — ✅ **Complete** — Planning Cognito owner user configuration, group roles, and welcome email suppression settings for test_tenant_alpha
- [**Release 19E: Platform Admin Second-Tenant Visibility Validation**](release-19e-platform-admin-second-tenant-visibility-validation.md) (2026-06-26) — ✅ **Complete** — Read-only validation verifying platform admin console correctly displays and audits test_tenant_alpha without affecting tog_and_dogs
- [**Release 19D: Controlled Second-Tenant Metadata Creation**](release-19d-controlled-second-tenant-metadata-creation.md) (2026-06-26) — ✅ **Complete** — Execute provision_tenant.py in apply mode to create test_tenant_alpha metadata and audit records in production DynamoDB
- [**Release 19C: Matthew Approval Checkpoint for Controlled Second-Tenant Metadata Creation**](release-19c-second-tenant-approval-checkpoint.md) (2026-06-26) — ✅ **Complete** — Establish parameters, safety boundaries, and exact CLI command for future metadata-only second test tenant creation
- [**Release 19B: Tenant Provisioning Script Dry Run**](release-19b-tenant-provisioning-script-dry-run.md) (2026-06-26) — ✅ **Complete** — Run scripts/provision_tenant.py in dry-run mode for test_tenant_alpha and verify proposed DynamoDB records and Cognito instructions
- [**Release 19A: Second-Tenant Provisioning Dry-Run Planning**](../planning/release-19a-second-tenant-provisioning-dry-run-planning.md) (2026-06-25) — ✅ **Complete** — Planning second-tenant provisioning dry run parameters and safety guards
- [**Release 18U: Strict Mode Post-Enable Monitoring Checkpoint**](release-18u-strict-mode-post-enable-monitoring-checkpoint.md) (2026-06-26) — ✅ **Complete** — Read-only post-enable monitoring checkpoint to verify 0.0 fallbacks/failures and check alarm status after strict-mode apply
- [**Release 18S: Strict Mode Enablement Plan and Terraform Plan-Only Checkpoint**](release-18s-strict-mode-enable-plan-checkpoint.md) (2026-06-26) — ✅ **Complete** — Prepare minimal environment configuration change to set TENANT_RESOLUTION_MODE=multi for all 13 backend Lambdas and generate plan
- [**Release 18R: Early Strict Mode Readiness Review**](release-18r-early-strict-mode-readiness-review.md) (2026-06-26) — ✅ **Complete** — Read-only check of Cognito user company IDs, DynamoDB tenant records, fallback metrics, and CloudWatch alarms
- [**Release 18P: Calendar Cancellation Cascade Defensive Fix**](release-18p-calendar-cancellation-cascade-defensive-fix.md) (2026-06-24) — ✅ **Complete** — Defensive calendar cancellation cascade to ensure event cleanup even under timing race conditions
- [**Release 18N: Phase 2 Entitlement Controlled Validation Execution**](release-18n-phase-2-entitlement-controlled-validation-execution.md) (2026-06-24) — ✅ **Complete** — Validate Professional tier client and booking limit gates using controlled test client and bookings
- [**Release 18M: Phase 2 Entitlement Controlled Validation Plan**](../planning/release-18m-phase-2-entitlement-controlled-validation-plan.md) (2026-06-23) — ✅ **Complete** — Design and obtain approval for controlled validation of client/booking entitlement gates
- [**Release 18L: Monthly Booking Counter and Client Limit Implementation**](release-18l-monthly-booking-counter-and-client-limit-implementation.md) (2026-06-23) — ✅ **Complete** — Gate client creation on active/disabled client limit and track/gate monthly bookings atomically in DynamoDB
- [**Release 18I: Post-Reconnect Calendar Sync Controlled Validation Execution**](release-18i-post-reconnect-calendar-sync-controlled-validation.md) (2026-06-23) — ✅ **Complete** — Create controlled test booking, verify Google Calendar event, and cancel booking using standard cancellation flow
- [**Release 18H: Post-Reconnect Calendar Sync Validation Plan**](../planning/release-18h-post-reconnect-calendar-sync-validation-plan.md) (2026-06-23) — ✅ **Complete** — Planning safe controlled calendar sync validation without customer-facing side effects
- [**Release 18G: Matthew-Approved Google Calendar Reconnect Execution and Validation**](release-18g-google-calendar-reconnect-execution-and-validation.md) (2026-06-23) — ✅ **Complete** — Reconnect Google Calendar account via manual OAuth and verify connection is healthy
- [**Release 18F: Google Calendar Reconnect and Scheduler Sync Reliability Review**](../planning/release-18f-google-calendar-reconnect-and-scheduler-sync-reliability-review.md) (2026-06-23) — ✅ **Complete** — Review degraded connection state, risks, and validation checklists
- [**Release 18E: Strict Mode Enablement Gate Review**](release-18e-strict-mode-enablement-gate-review.md) (2026-06-23) — ⏳ **Interim Checkpoint** — Interim read-only check of fallback/failed metrics; final review after June 30
- [**Release 18D: Tenant Resolution Fallback Metric Observation Period Kickoff**](release-18d-tenant-resolution-fallback-metric-observation-kickoff.md) (2026-06-23) — ⏳ **In Progress** — Start 7+ day read-only observation of fallback/failed metrics
- [**Release 18C: Manual Cognito User Company ID Backfill Closeout**](release-18c-manual-cognito-user-company-id-backfill-closeout.md) (2026-06-22) — ✅ **Complete** — All users have custom:company_id set
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
*   [Release 18C: Manual Cognito User Company ID Backfill Closeout](release-18c-manual-cognito-user-company-id-backfill-closeout.md)
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
*   [Release 18P: Calendar Cancellation Cascade Defensive Fix](release-18p-calendar-cancellation-cascade-defensive-fix.md)
*   [Release 18G: Matthew-Approved Google Calendar Reconnect Execution and Validation](release-18g-google-calendar-reconnect-execution-and-validation.md)
*   [Release 18F: Google Calendar Reconnect and Scheduler Sync Reliability Review](../planning/release-18f-google-calendar-reconnect-and-scheduler-sync-reliability-review.md)
*   [Google Calendar Approved Trigger](calendar/google-calendar-approved-trigger.md)

### 👤 Client Portal
*   [Client Portal Ownership Boundaries](client-portal/client-portal-ownership-boundaries-phase-5c.md)
*   [Client Access Management Phase 5a](client-portal/client-access-management-phase-5a.md)

### 🚀 Deployment & Operations
*   [Release 21E: Calendar Metadata Defaults Production Deployment and Validation](release-21e-calendar-metadata-defaults-production-deployment-validation.md)
*   [Release 21D: Tenant Calendar Provider Metadata Defaults Implementation](release-21d-tenant-calendar-provider-metadata-defaults-implementation.md)
*   [Release 21B: Calendar UI Unconfigured-State Cleanup](release-21b-calendar-ui-unconfigured-state-cleanup.md)
*   [Release 20F: Disabled Tenant Backend Access Enforcement Production Deployment and Validation](release-20f-disabled-tenant-backend-access-enforcement-production-validation.md)
*   [Release 20E: Disabled Tenant Backend Access Enforcement Implementation](release-20e-disabled-tenant-backend-access-enforcement-implementation.md)
*   [Release 20C: Controlled Tenant Disable and Restore Validation](release-20c-controlled-tenant-disable-restore-validation.md)
*   [Release 19M: Production Deployment and Tenant Isolation Revalidation](release-19m-production-deployment-and-tenant-isolation-revalidation.md)
*   [Release 19L: Frontend Tenant Display Remediation (Pre-Deploy)](release-19l-frontend-tenant-display-remediation-predeploy.md)
*   [Release 19K: Backend Tenant Isolation Remediation Plan (Pre-Deploy)](release-19k-backend-tenant-isolation-remediation-predeploy.md)
*   [Release 19J: Second-Tenant Owner Login Isolation Remediation Planning](../planning/release-19j-second-tenant-owner-login-isolation-remediation-plan.md)
*   [Release 19I: Second-Tenant Owner Login Isolation Defect Triage](release-19i-second-tenant-owner-login-isolation-defect-triage.md)
*   [Release 19H: Controlled Second-Tenant Owner Cognito User Creation](release-19h-controlled-second-tenant-owner-cognito-user-creation.md)
*   [Release 19G: Second-Tenant Owner Cognito User Creation Approval Checkpoint and Runbook](release-19g-second-tenant-owner-cognito-approval-runbook.md)
*   [Release 19F: Second-Tenant Owner Cognito User Creation Planning](../planning/release-19f-second-tenant-owner-cognito-user-creation-planning.md)
*   [Release 19E: Platform Admin Second-Tenant Visibility Validation](release-19e-platform-admin-second-tenant-visibility-validation.md)
*   [Release 19D: Controlled Second-Tenant Metadata Creation](release-19d-controlled-second-tenant-metadata-creation.md)
*   [Release 19C: Matthew Approval Checkpoint for Controlled Second-Tenant Metadata Creation](release-19c-second-tenant-approval-checkpoint.md)
*   [Release 19B: Tenant Provisioning Script Dry Run](release-19b-tenant-provisioning-script-dry-run.md)
*   [Release 19A: Second-Tenant Provisioning Dry-Run Planning](../planning/release-19a-second-tenant-provisioning-dry-run-planning.md)
*   [Release 18U: Strict Mode Post-Enable Monitoring Checkpoint](release-18u-strict-mode-post-enable-monitoring-checkpoint.md)
*   [Release 18T: Strict Mode Enablement Apply and Smoke Validation](release-18t-strict-mode-enablement-apply-and-smoke-validation.md)
*   [Release 18S: Strict Mode Enablement Plan and Terraform Plan-Only Checkpoint](release-18s-strict-mode-enable-plan-checkpoint.md)
*   [Release 18R: Early Strict Mode Readiness Review](release-18r-early-strict-mode-readiness-review.md)
*   [Release 18E: Strict Mode Enablement Gate Review](release-18e-strict-mode-enablement-gate-review.md)
*   [Release 18D: Tenant Resolution Fallback Metric Observation Period Kickoff](release-18d-tenant-resolution-fallback-metric-observation-kickoff.md)
*   [Production UAT Validation](deployment/production-uat-staff-client-workflow-validation.md)
*   [Production Audit Remediation](deployment/production-audit-remediation.md)
*   [Backend Intake Validation Tests](deployment/backend-intake-validation-tests.md)
*   [Backend Quoted Status Transition](deployment/backend-quoted-status-transition.md)

---

## 🗄️ Archive
Historical notes, branding updates, and superseded documentation can be found in the [**Archive Folder**](archive/).
