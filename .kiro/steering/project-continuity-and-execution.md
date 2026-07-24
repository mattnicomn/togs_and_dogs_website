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
- First recommended bounded implementation: Phase 24A-1A (shared architecture decision and token contract).
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
