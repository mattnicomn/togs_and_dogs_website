# Agent Operating Model

**How ChatGPT, Kiro, and AG/Antigravity work together on this project.**

---

## Role Definitions

| Agent | Role | Owns |
|-------|------|------|
| **ChatGPT** | Strategy, decision support, guardrail enforcement, reviews | Conversations, recommendations, context transfer |
| **Kiro** | Planning, design, documentation, checklists | All `docs/planning/`, release notes, backlog updates |
| **AG (Antigravity)** | Implementation, tests, builds, deployment | Code, tests, Terraform, Lambda, frontend deploys |
| **Matthew** | Final authority, approvals, manual actions | Production approvals, Cognito manual ops, Stripe manual ops |

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
