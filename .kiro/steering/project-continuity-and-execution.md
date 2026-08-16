---
inclusion: always
---

# Project Continuity and Execution Fallback

## Session Initialization

Before recommending or making any changes, every Kiro session must:

1. Read the project-continuity files in order:
   - `docs/project-continuity/README.md`
   - `docs/project-continuity/current-state.md`
   - `docs/project-continuity/guardrails.md`
   - `docs/project-continuity/master-handoff-prompt.md`
   - `docs/project-continuity/document-map.md`
   - `docs/backlog/saas-maturity-and-multi-business-owner-readiness.md`
   - `docs/release-notes/index.md`

2. Verify repository state:
   - Current branch
   - Full HEAD commit
   - Synchronization with `origin/main`
   - Working-tree status
   - Stash status

3. Use repository documents as authoritative over remembered chat context.

4. Identify and state:
   - Latest completed production release
   - Current active release and exact deployment status
   - Next approved or recommended action
   - Approval gates and blockers

5. Ask for the latest AG or Kiro output only when repository documentation
   does not contain the current result.

## Normal Operating Model (AG Available)

- Kiro: planning, organization, investigation, continuity, technical review, and validation.
- Prepare bounded implementation instructions for AG.
- AG: approved execution, implementation, testing, packaging, Terraform planning, and deployment preparation.
- Matthew: final approval for all production changes.

## Temporary Execution Fallback (AG Unavailable)

When Google Antigravity is unavailable:

- Kiro may perform an explicitly Matthew-approved bounded execution task.
- Kiro must NOT treat general project continuation as blanket approval.
- Kiro must state the exact scope before making changes.
- Kiro must keep production actions behind separate explicit approval.
- Kiro must run appropriate tests when making code changes.
- Kiro must use targeted `git add <specific-file>` staging only.
- Kiro must document the completed work and next resume point.

When AG becomes available again, return to the normal operating model.

## Absolute Prohibitions

- Never use `git add .` or wildcard staging.
- Never expose or request secrets, tokens, passwords, raw private data.
- Never deploy, apply Terraform, enable strict or multi-tenant resolution,
  create a second tenant, publish mobile apps, alter tester access,
  activate Stripe live mode, or create production test data without
  explicit Matthew approval.
- Preserve the saved Phase 1B.5C-A plan unless Matthew explicitly approves replacing it.

## Email Provider Guardrail

- Postmark is the approved production transactional email provider.
- AWS SES production sending was NOT approved (sandbox-only); do not pursue
  SES production access without explicit Matthew reversal.
- Do not switch Cognito or application notifications to SES.
- For Cognito-originated email (password reset), the approved architecture is:
  Cognito → Custom Email Sender Lambda → Postmark delivery.
- Never expose Postmark tokens or Secrets Manager values.
- Existing verified Postmark sender: `support@usmissionhero.com`.
- Existing Postmark message stream: `outbound`.

## Task Completion Protocol

Before ending any bounded task, update continuity documentation when the
repository state, active task, release status, blockers, or next action
has materially changed. Leave a resume block containing:

- Ending commit
- Files changed
- Tests run (if any)
- Deployment status
- Deferred items
- Exact next recommended action
- Required approval

---

## Workstream Resume Points

### AWS Tagging (Phase 23A)

- Evidence audit completed at commit `7243de2`.
- No current Terraform tagging remediation is required.
- Do not add redundant resource-level `tags` where provider `default_tags` already apply.
- Do not migrate SES to SESv2 merely for tagging without a separate approved design review.
- Do not assume cost-allocation activation status can be read from the linked account.
- Optional remediation remains deferred until Matthew chooses an item.
- Preserve `Client=TogAndDogs` because the current Budget depends on it.
- Preserve current `CostCenter`, `BillingModel`, and `Repo` semantics unless
  a separately approved migration plan addresses reporting continuity.

### AWS Budget and Cost Visibility (Phase 23B)

- Planning document complete: `docs/planning/phase-23b-aws-budget-coverage-and-cost-visibility-dashboard.md`
- Step 1 read-only verification complete: `docs/release-notes/phase-23b-step-1-budget-coverage-verification.md`
- Steps 2A–2C implementation complete: `docs/release-notes/phase-23b-cost-visibility-dashboard-and-budget-alerts.md`
- Operating guide: `docs/operations/aws-cost-visibility-operating-guide.md`
- All 9 standard user-defined cost-allocation tags are now ACTIVE.
- Budget alerts: 80% actual (original), 80% forecasted (new), 100% actual (new).
- Budget limit: $20, filter: `Client=TogAndDogs` — unchanged.
- Coverage classification: SUBSTANTIALLY COMPLETE WITH DOCUMENTED EXCLUSIONS (92–97%).
- Excluded: CloudWatch alarm monitoring ($0.45/month — AWS billing limitation) and Terraform state bucket ($0.01/month — untagged).
- Cost Explorer saved report requires manual console creation by Matthew (CLI unsupported).
- Terraform drift: two new budget notifications exist outside Terraform. Reconciliation deferred.
- Newly activated tags (Project, Application, CostCenter, Company, BillingModel) will begin appearing in Cost Explorer within 24–48 hours of 2026-07-26.
- Do not deactivate any active cost-allocation tag without Matthew approval.
- Do not change the budget limit, filter, or remove existing alerts.
- Phase 23B is not blocked by or blocking Phase 1B.5C-A.

### Cross-Platform UI Alignment

- Planning document complete: `docs/planning/phase-24a-cross-platform-design-system-and-mobile-workflow-alignment.md`
- No source implementation has been approved.
- Preserve React/Vite (web) and Expo/React Native (mobile).
- Do not recommend rewriting the website in React Native Web without new technical evidence.
- Revised release sequence: 24A-1A (architecture) → 24A-1B (wiring) → 24A-1C (visual alignment)
  → 24A-2 (constants) → 24A-3 (mobile test foundation) → 24A-4 (My Pets read)
  → 24A-5 (My Pets edit) → 24A-6 (intake) → 24A-7 (polish) → 24A-8 (a11y) → 24A-9 (build/dist).
- Mobile test infrastructure (24A-3) must be established BEFORE new mobile feature screens.
- Phase 24A-1 is split into architecture decision (1A), no-visual-change wiring (1B),
  and user-visible color alignment (1C).
- Mobile pet editing (24A-5) depends on Phase 1B.5C-A being deployed AND validated.
- Mobile pet read-only (24A-4) may proceed once 24A-3 is complete (GET /client/pets is already deployed).
- First recommended bounded implementation: Phase 24A-4 (Mobile My Pets read-only screen).
- Phase 24A-3 mobile test foundation: jest-expo@54.0.17, Jest 29.7.0, RNTL 14.0.1, test-renderer@1.1.0. 18 tests passing across 4 suites. Zero act() warnings.
- Mobile test commands: `npm test`, `npm run test:ci`, `npm run typecheck`.
- Transitive jest-expo renderer: react-test-renderer@19.1.0 exists only inside jest-expo (unavoidable preset dependency).
- Phase 24A-4 requires explicit Matthew approval.
- Mobile pet editing remains blocked by Phase 1B.5C-A deployment and validation.
- No mobile distribution is approved.
- No EAS, TestFlight, App Store, Google Play, Ryan-testing, or
  mobile-distribution changes are approved.
- EAS build and distribution (24A-9) is a separately approved release.
- Web forgot-password is missing (mobile has it complete). This is documented
  but not a blocking dependency for design-system work.

### Phase 1B.5C-A (Customer Pet Editing)

- Status: READY FOR MATTHEW DEPLOYMENT DECISION / NOT DEPLOYED.
- Saved Terraform plan exists and has not been applied.
- No new work may alter, replace, or combine with that saved plan.
- Kiro re-review is complete. Deployment preparation awaits Matthew approval.

### Cross-Platform Services, Scheduling & Workflow Alignment

- Ryan operational field-feedback assessment complete (2026-08-15).
- Ryan physical Android internal-testing install confirmed (2026-08-15).
- Target services: 20-Minute Walk, Check-In (30 min, 1–3 visits/day), Overnight.
- Time windows: Morning (06:30–09:30), Mid-day (10:30–15:30), Evening (18:00–21:30).
- Operational business rules must remain aligned across web, mobile, shared
  contracts, backend, calendar, and notifications.
- Shared contracts (`shared/constants/`) are the preferred source of truth.
- Do not create one-platform-only service definitions.
- Expose one obvious primary next action per workflow phase where safe.
- Preserve RBAC, review, payment, and tenant safety gates.
- Open decisions: Check-In 1/3-visit pricing, Overnight hours, Walk window rules.
- Slice A: COMMITTED / PUSHED / NOT DEPLOYED (`53818bc`).
- Slice B: COMMITTED / PUSHED / NOT DEPLOYED (`37bb806`). Both independently reviewed (Kiro: IMPLEMENTATION_CORRECT).
- Next recommended implementation: Slice D — Mobile parity + dashboard navigation.
- Slices C–F and any deployment remain separately gated.
- Nonblocking hardening: add explicit simulated mid-batch partial-write/retry test for Check-In occurrences.
