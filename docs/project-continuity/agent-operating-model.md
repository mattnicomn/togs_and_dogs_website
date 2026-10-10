# Agent Operating Model

**How ChatGPT, Kiro, and authorized implementation agents (AG/Antigravity) work together on this project.**

> The canonical governance policy is `docs/project-continuity/guardrails.md`. This document describes roles and collaboration; it does not override any gate in the canonical policy.

---

## Role Definitions

The role model is **device-independent**. A role is defined by what it does and what it may approve, not by the device or client it is exercised from.

| Agent | Role | Owns |
|-------|------|------|
| **ChatGPT** | Strategy, decision support, guardrail enforcement, reviews | Conversations, recommendations, context transfer |
| **Kiro** | Planning, design, documentation, checklists | All `docs/planning/`, release notes, backlog updates |
| **Authorized implementation agent (AG / Antigravity)** | Implementation, tests, builds, deployment | Code, tests, Terraform, Lambda, frontend deploys |
| **Matthew** | Final authority, approvals, manual actions | Production approvals, Cognito manual ops, Stripe manual ops |

- The **Kiro** role is exercised from **both Kiro Desktop and Kiro Web** with the **same authority and the same limits**. Mobile (Kiro Web) is **not** extra authority.
- **"Authorized implementation agent"** generalizes AG/Antigravity: it is any implementation agent Matthew has authorized to execute approved code/deploy work. The authority model is unchanged — only Matthew approves production changes.

---

## Normal Workflow

```
1. Matthew or ChatGPT identifies next work item
2. ChatGPT recommends approach and scope
3. Kiro creates planning/design document
4. ChatGPT/Matthew reviews plan
5. AG implements code + tests (after plan approval)
6. AG reports results (tests pass, diff summary)
7. Matthew approves deployment (if applicable)
8. AG deploys (terraform apply, frontend sync, etc.)
9. AG/Matthew validates in production
10. Kiro documents closeout
```

---

## When to Use Each Agent

### Use ChatGPT When

- Deciding what to do next
- Evaluating trade-offs between options
- Reviewing AG output or Kiro plans
- Transferring context to a new session
- Understanding project history
- Making strategic decisions

### Use Kiro When

- Creating planning/design documents
- Writing release notes and closeout docs
- Updating backlog and document maps
- Creating operational checklists
- Documenting validation results
- Updating the project continuity hub

### Use AG When

- Writing/modifying code (Python, JavaScript, Terraform)
- Running tests (`pytest`, `npm run build`)
- Deploying to production (S3 sync, terraform apply)
- Running read-only AWS queries (CloudWatch, DynamoDB reads)
- Creating EAS builds
- Inspecting infrastructure state

### Matthew Handles Directly

- AWS Console manual actions (Cognito user management)
- Stripe Dashboard manual actions
- App Store Connect manual actions
- Final deployment approvals ("terraform apply approved")
- Production data decisions ("create this test record: approved")
- Business policy decisions

---

## Cross-Device Authorization, Development, Review & Handoff

This section makes the role model explicitly device-independent and defines how isolated work is developed, reviewed, and integrated across devices. It does **not** change who approves what: **Matthew remains the final authority** for all production, deploy, Terraform-apply, tenant, Stripe-live, and mobile-distribution actions.

### (a) Which role may do what, from which device

- **Kiro (Desktop or Web)**: planning, design, documentation, continuity, technical review, and validation. Same authority and same limits on both clients.
- **ChatGPT**: strategy, decision support, guardrail enforcement, reviews.
- **Authorized implementation agent (AG/Antigravity)**: approved code, tests, builds, Terraform planning, and deployment preparation.
- **Matthew**: final approval and all manual console/production actions.
- **Mobile is not extra authority.** Working from Kiro Web (or any mobile client) grants no deployment or implementation authority that the role does not already have from desktop. Every guardrail gate in `docs/project-continuity/guardrails.md` applies identically.

### (b) Isolated feature-branch development

- Develop every change on an **isolated feature branch** cut from the latest verified `main`. Never commit directly to `main`.
- Branch naming conventions:
  - `mobile/<task-id>-<slug>` for work originated from a mobile/Kiro Web session.
  - `governance/<slug>` for governance, continuity, and policy work.
  - Existing phase/release branch conventions remain valid for implementation streams.
- Keep each branch scoped to its stated task (consistent with the Git Discipline rules in the canonical guardrails).

### (c) PR-only integration

- Integration into `main` is **PR-only**. Never push directly to `main`.
- **Never self-merge.** Matthew approves and authorizes integration.
- A PR is a proposal for review, not an authorization to deploy; deployment remains separately gated.

### (d) Task-status tracking convention

- Track task status by reusing the existing **resume-block format** already defined in the steering file's Task Completion Protocol. For each tracked task record:
  - Ending commit
  - Files changed
  - Tests run (if any)
  - Deployment status
  - Deferred items
  - Exact next recommended action
  - Required approval
- This keeps mobile-originated and desktop-originated work legible to the next session regardless of which device resumes it.

### (e) Desktop reconciliation procedure

Before integrating remote or mobile-originated work:

1. `git fetch` and verify the remote state and branch divergence explicitly.
2. Verify there is **no conflict with desktop-local-only artifacts** — for example unpushed RCs, saved `.tfplan` files, and `terraform.tfvars` (these are gitignored and exist only on the desktop working copy).
3. **Never assume desktop-local files are clean or synchronized.** Confirm working-tree and stash status before acting; treat the desktop as potentially holding uncommitted or unpushed state.
4. Only after reconciliation is confirmed should integration proceed through the PR-only path with Matthew's approval.

---

## Handoff Protocol

### Starting a New Session

1. Read `docs/project-continuity/current-state.md`
2. Read `docs/project-continuity/guardrails.md`
3. Confirm understanding of blockers and next actions
4. Ask clarifying questions before proceeding

### Ending a Session

1. Document what was completed
2. Note what remains for the next session
3. Commit and push all documentation
4. Update `current-state.md` if project state changed materially

### Context Loss

If context is lost mid-session:
- Re-read `docs/project-continuity/` folder
- Check latest commits: `git log --oneline -10`
- Ask Matthew what was last approved/completed
- Do NOT guess or assume — ask first

---

## Safety Rules for All Agents

- Never act without understanding current guardrails
- Never deploy without approval
- Never commit secrets
- Never skip the plan step for non-trivial changes
- Always verify test results before claiming success
- Always use targeted git add
- Always document completion
