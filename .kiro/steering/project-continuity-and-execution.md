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

- Planning/audit only. No source implementation has been approved.
- Preserve React/Vite (web) and Expo/React Native (mobile).
- Do not recommend rewriting the website in React Native Web without new technical evidence.
- Start future implementation with shared tokens and constants, followed by
  a bounded My Pets mobile pilot only after prerequisite approval.
- Mobile pet editing depends on the customer pet API being available
  (requires Phase 1B.5C-A deployment decision first).
- No EAS, TestFlight, App Store, Google Play, Ryan-testing, or
  mobile-distribution changes are approved.

### Phase 1B.5C-A (Customer Pet Editing)

- Status: READY FOR MATTHEW DEPLOYMENT DECISION / NOT DEPLOYED.
- Saved Terraform plan exists and has not been applied.
- No new work may alter, replace, or combine with that saved plan.
- Kiro re-review is complete. Deployment preparation awaits Matthew approval.
