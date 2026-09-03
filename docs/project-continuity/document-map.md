# Document Map

**Where to find detailed docs by topic.**

---

## Core Invariants

### BUSINESS / BRAND OWNERSHIP BOUNDARY
Togs & Dogs is Ryan's individual pet-care business/tenant. It is NOT the USMissionHero platform brand and must not be used as the namespace, branding, default identity, or implied business owner for unrelated tenants. USMissionHero LLC is the platform/operator layer. Tenant business identity must remain isolated per tenant.

---

## Release Notes & History

| Topic | Location |
|-------|----------|
| Release notes index | `docs/release-notes/index.md` |
| Individual release notes | `docs/release-notes/release-*.md` |
| PTM0-S1 production deployment and acceptance (complete; PTM-0 incomplete) | `docs/release-notes/ptm0-s1-production-deployment-acceptance.md` |
| PTM0-S1 local implementation and cursor-confidentiality history | `docs/release-notes/ptm0-s1-legacy-record-read-isolation-local.md` |
| B1A real Web/API write-path validation result (PASS; not full E2E) | `docs/release-notes/b1a-real-web-api-write-path-validation.md` |
| B1A real Web/API write-path validation plan (executed once; historical) | `docs/planning/b1a-real-web-api-write-path-validation-plan.md` |
| P1 Decimal entitlement serialization local fix | `docs/release-notes/p1-decimal-entitlement-serialization-local-fix.md` |
| P1 Decimal entitlement backend RC | `docs/release-notes/p1-decimal-entitlement-serialization-backend-rc.md` |
| P1 Decimal entitlement backend deployment plan and applied-plan reconciliation | `docs/release-notes/p1-decimal-entitlement-serialization-backend-deployment-plan.md` |
| P1 Decimal entitlement production acceptance plan | `docs/release-notes/p1-decimal-entitlement-serialization-production-acceptance-plan.md` |
| P1 Decimal entitlement production acceptance result | `docs/release-notes/p1-decimal-entitlement-serialization-production-acceptance.md` |
| API semantic fingerprint infrastructure RC | `docs/release-notes/api-gateway-semantic-deployment-fingerprint-infrastructure-rc.md` |
| Failed INFRA-GATE-A and line-ending remediation | `docs/release-notes/api-gateway-semantic-fingerprint-line-ending-remediation.md` |
| API semantic fingerprint migration v2 state-509 plan | `docs/release-notes/api-gateway-semantic-fingerprint-migration-v2-plan.md` |
| API semantic fingerprint migration v2 production deployment | `docs/release-notes/api-gateway-semantic-fingerprint-migration-v2-deployment.md` |
| DOMAIN-1 backend v2 RC validation hard stop | `docs/release-notes/domain-1-b1a-route-backend-v2-rc.md` |
| DOMAIN-1 test-harness baseline triage and correction | `docs/release-notes/domain-1-b1a-route-test-harness-triage.md` |
| DOMAIN-1 backend v3 RC and state-510 saved plan | `docs/release-notes/domain-1-b1a-route-backend-v3-rc.md` |
| DOMAIN-1 backend v3 production deployment / ROUTE-GATE-A closeout | `docs/release-notes/domain-1-b1a-route-backend-v3-deployment.md` |
| DOMAIN-1 Web v2 RC / ROUTE-GATE-B review | `docs/release-notes/domain-1-b1a-route-web-v2-rc.md` |
| DOMAIN-1 Web v2 production deployment / ROUTE-GATE-B closeout | `docs/release-notes/domain-1-b1a-route-web-v2-deployment.md` |
| Historical, permanently invalid semantic-fingerprint migration plan | `docs/release-notes/api-gateway-semantic-fingerprint-migration-plan.md` |
| Web customer self-service password recovery (production deployed, Cognito E2E pass) | `docs/release-notes/release-web-customer-self-service-password-recovery.md` |
| Preview V1 tenant onboarding orchestrator | `docs/release-notes/release-platform-admin-tenant-onboarding-preview-v1.md` |
| Ryan Slice A canonical service/time-window contract | `docs/release-notes/ryan-slice-a-canonical-service-time-window-contract.md` |
| Ryan Slice B Check-In booking/job/Calendar semantics | `docs/release-notes/ryan-slice-b-check-in-booking-job-calendar-semantics.md` |
| Ryan Slice C Web Check-In intake parity | `docs/release-notes/ryan-slice-c-web-check-in-intake-parity.md` |
| Ryan Slice C1 Admin Check-In creation parity | `docs/release-notes/ryan-slice-c1-admin-check-in-creation-parity.md` |
| Ryan Slice D1 mobile dashboard navigation | `docs/release-notes/ryan-slice-d1-mobile-dashboard-navigation.md` |
| Ryan Slice D2 mobile Check-In intake parity | `docs/release-notes/ryan-slice-d2-mobile-check-in-intake-parity.md` |
| Ryan release-readiness hardening R1 | `docs/release-notes/ryan-release-readiness-hardening-r1.md` |
| Ryan W1 20-Minute Walk canonical scheduling windows | `docs/release-notes/ryan-w1-walk-canonical-scheduling-windows.md` |
| Ryan O1 Overnight fixed 9PM–7AM scheduling | `docs/release-notes/ryan-o1-overnight-fixed-scheduling.md` |
| Ryan Slice E1 Web Admin guided assignment and Calendar actions | `docs/release-notes/ryan-slice-e1-web-admin-guided-actions.md` |
| Ryan Slice E2 intake approval to Scheduler handoff | `docs/release-notes/ryan-slice-e2-intake-approval-scheduler-handoff.md` |
| Ryan Slice E3A child Start contract and occurrence read model | `docs/release-notes/ryan-slice-e3a-child-start-contract-occurrence-read-model.md` |
| Ryan Slice E3B Mobile occurrence-safe Start/Complete | `docs/release-notes/ryan-slice-e3b-mobile-occurrence-start-complete.md` |
| Ryan Slice E3B.1 Mobile visit workflow safety remediation | `docs/release-notes/ryan-slice-e3b1-mobile-visit-workflow-safety-remediation.md` |

## Planning Documents

| Topic | Key Files |
|-------|-----------|
| SaaS architecture roadmap | `docs/planning/release-11a-multi-business-saas-architecture-and-product-roadmap.md` |
| Platform Tenant Management Control Plane specification (PTM-0 through PTM-13) | `docs/planning/platform-tenant-management-control-plane.md` |
| PTM-0 source-of-truth reconciliation audit (C; F01 closed by completed S1; F02 and later findings remain) | `docs/planning/ptm-0-source-of-truth-reconciliation-audit.md` |
| Tenant-Aware Mobile Presentation Architecture & Cross-Platform Branding Model | `docs/planning/tenant-aware-mobile-presentation-architecture.md` |
| DOMAIN-1 tenant access routing ADR | `docs/planning/adr-domain-1-tenant-access-routing.md` |
| Tenant access, client onboarding, Visit Requests, Request List, and Mobile operations alignment (authoritative 2026-08-23 reconciliation) | `docs/planning/tenant-access-client-onboarding-operational-workflow-alignment.md` |
| Client/Household foundation plan | `docs/planning/client-household-pet-management-foundation-plan.md` |
| Phase 1A production closeout | `docs/release-notes/phase-1a-client-household-backend-production-deployment-closeout.md` |
| Phase 1B.1 manual validation closeout | `docs/release-notes/phase-1b1-client-management-manual-validation-closeout.md` |
| Phase 1B.1 production deployment closeout | `docs/release-notes/phase-1b1-client-management-frontend-production-deployment-closeout.md` |
| Phase 1B.2 planning audit | `docs/planning/phase-1b2-client-write-workflows-and-pet-lifecycle-audit.md` |
| Phase 1B.2A pet read-path audit | `docs/release-notes/phase-1b2a-pet-read-path-and-client-inventory-predeploy.md` |
| Phase 1B.2A ClientPetIndex plan | `docs/release-notes/phase-1b2a-client-pet-index-terraform-plan.md` |
| Phase 1B.2A plan scope mismatch | `docs/release-notes/phase-1b2a-client-pet-index-plan-scope-mismatch-review.md` |
| Phase 1B.2A deployment sequencing | `docs/planning/phase-1b2a-backend-and-gsi-deployment-sequencing.md` |
| Phase 1B.2A packaging readiness review | `docs/release-notes/phase-1b2a-backend-packaging-readiness-review.md` |
| Phase 1B.2A query cutover plan | `docs/planning/phase-1b2a-client-pet-index-query-cutover.md` |
| Phase 1B.2A GSI deployment review closeout | `docs/release-notes/phase-1b2a-client-pet-index-deployment-review-closeout.md` |
| Phase 1B.2A packaging correction pre-plan | `docs/release-notes/phase-1b2a-backend-packaging-correction-preplan.md` |
| Phase 1B.2A backend-only Terraform plan | `docs/release-notes/phase-1b2a-backend-only-terraform-plan.md` |
| Phase 1B.2A backend deployment closeout | `docs/release-notes/phase-1b2a-backend-production-deployment-closeout.md` |
| Phase 1B.2A ClientPetIndex GSI-only plan | `docs/release-notes/phase-1b2a-client-pet-index-gsi-only-terraform-plan.md` |
| Phase 1B.2A ClientPetIndex deployment closeout | `docs/release-notes/phase-1b2a-client-pet-index-production-deployment-closeout.md` |
| Phase 1B.2A ClientPetIndex query cutover local closeout | `docs/release-notes/phase-1b2a-client-pet-index-query-cutover-local-closeout.md` |
| Phase 1B.2A ClientPetIndex query cutover backend deployment | `docs/release-notes/phase-1b2a-client-pet-index-query-cutover-production-deployment.md` |
| Phase 1B.2A ClientPetIndex query cutover validation closeout | `docs/release-notes/phase-1b2a-client-pet-index-query-cutover-validation-closeout.md` |
| Phase 1B.3 client pet inventory and management detail UX plan | `docs/planning/phase-1b3-client-pet-inventory-and-management-detail-ux.md` |
| Phase 1B.3 component test review | `docs/release-notes/phase-1b3-component-test-review.md` |
| Phase 1B.3 component test hardening | `docs/release-notes/phase-1b3-component-test-hardening.md` |
| Phase 1B.3 authenticated validation closeout | `docs/release-notes/phase-1b3-authenticated-production-validation-closeout.md` |
| Phase 1B.4 drawer editor consolidation plan | `docs/planning/phase-1b4-client-staff-drawer-editor-consolidation.md` |
| Phase 1B.4A–E implementation review | `docs/release-notes/phase-1b4a-e-client-drawer-editor-implementation-review.md` |
| Phase 1B.4A–E validation closeout | `docs/release-notes/phase-1b4a-e-authenticated-production-validation-closeout.md` |
| Phase 1B.5 pet management plan | `docs/planning/phase-1b5-pet-management-and-client-pet-association.md` |
| Phase 1B.5A & 1B.5A.1 validation closeout | `docs/release-notes/phase-1b5a-and-1b5a1-authenticated-production-validation-closeout.md` |
| Phase 1B.5B staff pet management plan | `docs/planning/phase-1b5b-staff-pet-management-in-client-management.md` |
| Phase 1B.5B-A staff pet editor release notes | `docs/release-notes/phase-1b5b-a-staff-pet-editor-implementation.md` |
| Phase 1B.5B-A PUT correction release notes | `docs/release-notes/phase-1b5b-a-put-validation-order-correction.md` |
| Phase 1B.5B-A staff pet editor deployment readiness | `docs/release-notes/phase-1b5b-a-staff-pet-editor-deployment-readiness.md` |
| Phase 1B.5B-A staff pet editor production deployment | `docs/release-notes/phase-1b5b-a-staff-pet-editor-production-deployment.md` |
| Phase 1B.5B-A.1 staff pet editor hotfix deployment readiness | `docs/release-notes/phase-1b5b-a1-pet-edit-save-hotfix-deployment-readiness.md` |
| Phase 1B.5B-A.1 staff pet editor hotfix production deployment | `docs/release-notes/phase-1b5b-a1-pet-edit-save-hotfix-production-deployment.md` |
| Phase 1B.5B-A.1 Google Calendar access control remediation | `docs/release-notes/phase-1b5b-a1-google-calendar-access-control-remediation.md` |
| Phase 1B.5B-A.1 Google Calendar RBAC deployment readiness | `docs/release-notes/phase-1b5b-a1-google-calendar-rbac-deployment-readiness.md` |
| Phase 1B.5B-A.1 Google Calendar RBAC production deployment | `docs/release-notes/phase-1b5b-a1-google-calendar-rbac-production-deployment.md` |
| Phase 1B.5C-A customer pet editing release notes | `docs/release-notes/phase-1b5c-a-customer-pet-editing-local-implementation.md` |
| Phase 1B.5C-A customer pet editing audit | `docs/release-notes/phase-1b5c-a-customer-pet-editing-audit.md` |
| Phase 24A-1C cross-platform visual token alignment | `docs/release-notes/phase-24a-1c-visual-token-alignment.md` |
| Phase 24A-2A shared contract adapter foundation & API path wiring | `docs/release-notes/phase-24a-2a-api-path-wiring.md` |
| Phase 24A-2B pet field & validation wiring plan | `docs/planning/phase-24a-2b-pet-field-and-validation-wiring.md` |
| Phase 24A-2B.1 web pet read allowlist wiring | `docs/release-notes/phase-24a-2b1-web-pet-read-allowlist.md` |
| Phase 24A-2B.2A web pet top-level validation limits | `docs/release-notes/phase-24a-2b2a-web-pet-top-level-limits.md` |
| Phase 24A-2B.2B customer veterinarian-field limits | `docs/release-notes/phase-24a-2b2b-veterinarian-field-limits.md` |
| Phase 24A-2C.1 request-status contract & display wiring plan | `docs/planning/phase-24a-2c1-request-status-contract-display-wiring.md` |
| Phase 24A-2C.1A request-status label metadata & parity hardening (locally complete, committed, and pushed) | `docs/release-notes/phase-24a-2c1a-request-status-label-metadata-parity-hardening.md` |
| Phase 24A-2C.1B web request-status display compatibility wiring (locally complete, committed, and pushed) | `docs/release-notes/phase-24a-2c1b-web-request-status-display-compatibility-wiring.md` |
| Phase 24A-2C.1C mobile request-status display compatibility wiring (locally complete, committed, and pushed) | `docs/release-notes/phase-24a-2c1c-mobile-request-status-display-compatibility-wiring.md` |
| Phase 24A roadmap continuity reconciliation & Phase 2C contract stream local closeout | `docs/release-notes/phase-24a-roadmap-continuity-reconciliation.md` |
| Phase 24A-2C.2 cross-platform service-type contract wiring plan | `docs/planning/phase-24a-2c2-service-type-contract-wiring.md` |
| Phase 24A-2C.2A web admin service-type display labels | `docs/release-notes/phase-24a-2c2a-web-admin-service-labels.md` |
| Phase 24A-2C.2B selector membership and noncanonical compatibility plan | `docs/planning/phase-24a-2c2b-selector-normalization-design.md` |
| Phase 24A-2C.2B.1 web service-type display compatibility (locally validated and independently reviewed) | `docs/release-notes/phase-24a-2c2b1-web-display-compatibility.md` |
| Phase 24A-2C.2B.2A customer intake canonical service options | `docs/release-notes/phase-24a-2c2b2a-intake-canonical-service-options.md` |
| Phase 24A-2C.2B.2B CareCard service-type correction (locally validated and independently reviewed) | `docs/release-notes/phase-24a-2c2b2b-carecard-service-type-correction.md` |
| Phase 24A-2C.2B.2C MasterScheduler canonical service-filter correction (locally validated and independently reviewed) | `docs/release-notes/phase-24a-2c2b2c-masterscheduler-canonical-service-filter.md` |
| Phase 24A-2C.2C mobile service-type display-label wiring plan | `docs/planning/phase-24a-2c2c-mobile-service-label-wiring.md` |
| Phase 24A-2C.2C mobile service-type display labels | `docs/release-notes/phase-24a-2c2c-mobile-service-labels.md` |
| Phase 24A-2C.2D.1 service-duration parity and validator hardening (locally validated and independently reviewed; no runtime behavior change) | `docs/release-notes/phase-24a-2c2d1-service-duration-parity-validator-hardening.md` |
| Phase 24A-2C.2D.2 generated backend service-metadata adapter (locally validated and independently reviewed; no runtime consumption) | `docs/release-notes/phase-24a-2c2d2-generated-backend-service-metadata-adapter.md` |
| Phase 24A-2C.2D.3 generated calendar duration and friendly-name wiring (locally validated and independently reviewed; exact behavior preserved) | `docs/release-notes/phase-24a-2c2d3-generated-calendar-duration-friendly-name-wiring.md` |
| Phase 24A-2C.2D.4 optional calendar color metadata design & value assessment (no implementation recommended; Phase 2D stream locally complete) | `docs/release-notes/phase-24a-2c2d4-calendar-color-metadata-assessment.md` |




| Phase 24A-4 mobile My Pets read-only screen | `docs/release-notes/phase-24a-4-mobile-my-pets-read-only-screen.md` |
| Phase 24A-4.1 mobile My Pets session-expiration test hardening | `docs/release-notes/phase-24a-41-mobile-my-pets-session-expiration-test-hardening.md` |
| Phase 1B.5C-A customer pet editing re-review | `docs/release-notes/phase-1b5c-a-bounded-correction-rereview.md` |
| Phase 1B.5C-A customer pet editing deployment readiness | `docs/release-notes/phase-1b5c-a-customer-pet-editing-deployment-readiness.md` |
| Phase 1B.5C-A artifact reconstruction and plan reaffirmation | `docs/release-notes/phase-1b5c-a-deployment-preparation-addendum.md` |
| Phase 1B.5C-A production deployment record | `docs/release-notes/phase-1b5c-a-customer-pet-editing-production-deployment.md` |
| Phase 1B.5C-A.1 admin pet care field visibility hotfix | `docs/release-notes/phase-1b5c-a1-admin-pet-care-field-visibility-hotfix.md` |
| Phase 1B.5C-B staff limit active-count entitlement fix | `docs/release-notes/phase-1b5c-b-staff-limit-active-count-entitlement-fix.md` |
| Phase 1B.5C-C staff edit double-click correction | `docs/release-notes/phase-1b5c-c-staff-edit-double-click-correction.md` |
| Phase 1B.5C-D.1 platform-managed protected admin controls | `docs/release-notes/phase-1b5c-d1-platform-managed-protected-admin-controls.md` |
| Phase 1B.5C-D.2 remove legacy config protection | `docs/release-notes/phase-1b5c-d2-remove-legacy-config-protection.md` |
| Phase 1B.5A pet loading release notes | `docs/release-notes/phase-1b5a-authoritative-client-pet-loading.md` |
| Phase 1B.5A pet loading review | `docs/release-notes/phase-1b5a-authoritative-client-pet-loading-review.md` |
| Phase 1B.5A production deployment | `docs/release-notes/phase-1b5a-authoritative-client-pet-loading-production-deployment.md` |
| Phase 1B.5A.1 pet hotfix release notes | `docs/release-notes/phase-1b5a1-my-pets-list-and-status-hotfix-implementation.md` |
| Phase 1B.5A.1 pet hotfix review | `docs/release-notes/phase-1b5a1-my-pets-list-and-status-hotfix-review.md` |
| Phase 1B.5A.1 pet hotfix deployment plan | `docs/release-notes/phase-1b5a1-my-pets-hotfix-deployment-readiness.md` |
| Phase 1B.5A.1 pet hotfix deployment record | `docs/release-notes/phase-1b5a1-my-pets-hotfix-production-deployment.md` |
| Phase 1B.4A–E test hardening release notes | `docs/release-notes/phase-1b4a-e-client-drawer-test-hardening.md` |
| Phase 1B.4A–E test hardening review | `docs/release-notes/phase-1b4a-e-client-drawer-test-hardening-review.md` |
| Phase 1B.4A–E frontend production deployment | `docs/release-notes/phase-1b4a-e-client-drawer-frontend-production-deployment.md` |
| Phase 1B.3 frontend production deployment | `docs/release-notes/phase-1b3-frontend-production-deployment.md` |
| Phase 1B.3 admin hook-order hotfix pre-deploy | `docs/release-notes/phase-1b3-admin-hook-order-production-hotfix-predeploy.md` |
| Phase 1B.3 admin hook-order hotfix deployment | `docs/release-notes/phase-1b3-admin-hook-order-production-hotfix-deployment.md` |
| Phase 1B.2A backend archive audit | `docs/release-notes/phase-1b2a-backend-archive-delta-audit.md` |
| Phase 1B.2A AG execution handoff | `docs/project-continuity/phase-1b2a-pet-read-path-ag-execution-handoff.md` |
| Phase 1B.2A.2 legacy normalization plan | `docs/planning/phase-1b2a2-pet-legacy-normalization-and-creation-hardening.md` |
| Phase 1B.2A.2 legacy remediation release notes | `docs/release-notes/phase-1b2a2-pet-creation-hardening-and-remediation-tool-predeploy.md` |
| Phase 1B.2A.2 remediation classifier correction notes | `docs/release-notes/phase-1b2a2-remediation-classifier-correction-predeploy.md` |
| Billing & entitlement architecture | `docs/planning/release-12a-billing-and-entitlement-architecture-plan.md` |
| Stripe webhook/data model | `docs/planning/release-12c-stripe-webhook-and-billing-data-model-implementation-plan.md` |
| Booking payment architecture | `docs/planning/release-12f-stripe-checkout-booking-payment-architecture-plan.md` |
| Live Stripe readiness | `docs/planning/release-13a-payments-production-readiness-and-live-mode-cutover-plan.md` |
| Mobile/TestFlight readiness | `docs/planning/release-15a-mobile-testflight-and-staff-workflow-readiness-plan.md` |
| SaaS maturity audit | `docs/planning/release-16a-repository-readiness-and-saas-maturity-audit.md` |
| Roadmap reprioritization | `docs/planning/release-16b-saas-maturity-roadmap-reprioritization-and-capability-placement-strategy.md` |
| Entitlement enforcement design | `docs/planning/release-17a-entitlement-enforcement-design.md` |
| Platform Management Console | `docs/planning/release-17k-platform-management-console-design.md` |
| Platform Admin UI MVP | `docs/planning/release-17o-platform-management-ui-mvp.md` |
| Tenant provisioning design | `docs/planning/release-17v-tenant-provisioning-runbook-seed-tool-design.md` |
| Company ID hardening | `docs/planning/release-17x-company-id-resolution-hardening-design.md` |
| Phase 2 entitlement gates | `docs/planning/release-18k-phase-2-entitlement-gate-design-client-booking-limits.md` |
| Calendar cancellation fix | `docs/planning/release-18o-google-calendar-event-id-propagation-cancellation-race-remediation-plan.md` |
| Strict-mode gate review | `docs/planning/release-18q-strict-mode-final-gate-review-preparation-plan.md` |
| Web/mobile UI parity | `docs/planning/release-18ui-a-web-mobile-ui-parity-review-plan.md` |
| Identity & Care Request triage | `docs/planning/release-22a-identity-profile-and-care-request-validation-defect-triage.md` |
| Smoke test plan & triage | `docs/planning/release-22x-controlled-core-workflow-smoke-test-plan.md`, `docs/planning/release-22y-smoke-test-identity-actions-and-google-calendar-disconnect-triage.md` |
| Mobile responsive UX plan | `docs/planning/release-22z-mobile-responsive-ux-polish-detailed-plan.md` |
| AWS tagging evidence audit | `docs/planning/phase-23a-aws-tagging-evidence-audit-and-minimal-remediation.md` |
| AWS budget coverage and cost visibility dashboard | `docs/planning/phase-23b-aws-budget-coverage-and-cost-visibility-dashboard.md` |
| Phase 23B Step 1 budget coverage verification | `docs/release-notes/phase-23b-step-1-budget-coverage-verification.md` |
| Cross-platform design system and mobile alignment | `docs/planning/phase-24a-cross-platform-design-system-and-mobile-workflow-alignment.md` |
| Ryan cross-platform services, scheduling & workflow alignment | `docs/planning/ryan-cross-platform-services-scheduling-workflow-alignment.md` |
| Phase 24A-1A shared token contract | `docs/release-notes/phase-24a-1a-shared-token-contract.md` |
| Phase 24A-1B platform token adapters | `docs/release-notes/phase-24a-1b-platform-token-adapters.md` |
| Phase 24A-2 shared constants and contracts | `docs/release-notes/phase-24a-2-shared-constants-and-contracts.md` |
| Phase 24A-3 mobile test foundation | `docs/release-notes/phase-24a-3-mobile-test-foundation.md` |
| Phase 24A-6 mobile care-request intake flow (locally complete, committed, and pushed) | `docs/release-notes/phase-24a-6-mobile-care-request-intake-flow.md` |
| Phase 24A-7 mobile visual consistency polish (locally complete, committed, and pushed) | `docs/release-notes/phase-24a-7-visual-consistency-polish.md` |
| Phase 24A-8 mobile accessibility validation (locally complete, committed, and pushed) | `docs/release-notes/phase-24a-8-accessibility-validation.md` |
| Phase 24A-9C cross-platform remediation revalidation (complete/pass) | `docs/release-notes/phase-24a-9c-cross-platform-nonwrite-smoke-validation.md` |
| Phase 24A-9C.1 iOS physical smoke defect remediation (complete and revalidated) | `docs/release-notes/phase-24a-9c1-ios-physical-smoke-defect-remediation.md` |
| Phase 24A-9C.2 paired remediation builds and revalidation closeout (complete/pass) | `docs/release-notes/phase-24a-9c2-paired-remediation-revalidation-closeout.md` |


## Backlog

| Topic | Location |
|-------|----------|
| SaaS maturity backlog | `docs/backlog/saas-maturity-and-multi-business-owner-readiness.md` |
| EIN blocker | `docs/backlog/stripe-live-activation-blocked-pending-ein.md` |

## Operations

| Topic | Location |
|-------|----------|
| Business Owner Getting Started (locally complete, independently reviewed, committed and pushed, not public) | `docs/operations/business-owner-getting-started.md` |
| Admin quick reference | `docs/operations/admin-quick-reference.md` |
| AWS cost visibility operating guide | `docs/operations/aws-cost-visibility-operating-guide.md` |
| Payment workflow guide | `docs/operations/payment-workflow-quick-reference.md` |
| Emergency response | `docs/operations/emergency-response-checklist.md` |
| Google Calendar reauth | `docs/operations/google-calendar-reauthorization.md` |
| Matthew monitoring checklist | `docs/operations/matthew-monitoring-checklist.md` |
| Email deliverability | `docs/operations/email-deliverability-controls.md` |

## Policies

| Topic | Location |
|-------|----------|
| Payment/refund/cancellation draft | `docs/policies/payment-terms-refund-cancellation-draft.md` |

## Architecture

| Topic | Location |
|-------|----------|
| System architecture overview | `ARCHITECTURE.md` |
| Data model | `docs/datamodel.md` |

## Project Continuity (This Folder)

| File | Purpose |
|------|---------|
| `README.md` | Start here |
| `current-state.md` | What's deployed/blocked now |
| `guardrails.md` | Safety rules |
| `agent-operating-model.md` | How agents collaborate |
| `decision-log.md` | Key decisions |
| `release-timeline.md` | Major milestones |
| `lessons-learned.md` | Patterns and anti-patterns |
| `master-handoff-prompt.md` | New-session prompt |
| `continuity-maintenance-checklist.md` | How to keep these docs accurate |
