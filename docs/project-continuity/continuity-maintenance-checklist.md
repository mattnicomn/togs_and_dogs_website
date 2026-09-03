# Continuity Documentation Maintenance Checklist

**Keep the project continuity hub accurate. Stale docs are worse than no docs.**

---

## When to Update Continuity Docs

Update after any of the following:

- ✅ Production release deployed
- ✅ Terraform apply completed
- ✅ Major planning release committed
- ✅ New blocker identified or resolved
- ✅ Key decision made or changed
- ✅ New lesson learned (bug, process issue, anti-pattern)
- ✅ Strict-mode status changes
- ✅ Second-tenant status changes
- ✅ Stripe/payment status changes (sandbox → live, EIN resolved, etc.)
- ✅ Ryan/tester status changes
- ✅ App Store / TestFlight status changes
- ✅ Mobile build status changes
- ✅ Agent workflow or guardrail changes

---

## Which Docs to Update by Change Type

| Change Type | Update This File |
|-------------|------------------|
| Production state changed (deployed, enabled, blocked) | `current-state.md` |
| New release milestone closed | `release-timeline.md` |
| New architectural/business decision | `decision-log.md` |
| Bug found, process mistake, or pattern discovered | `lessons-learned.md` |
| New document category or file created | `document-map.md` |
| Agent collaboration workflow changed | `agent-operating-model.md` |
| New safety rule or guardrail added/changed | `guardrails.md` |
| New-session startup instructions need update | `master-handoff-prompt.md` |
| This checklist itself needs a new trigger | `continuity-maintenance-checklist.md` |

---

## Release Closeout Checklist

After every release (planning or implementation), verify:

| # | Check | Done? |
|---|-------|-------|
| 1 | Release notes created/updated | ___ |
| 2 | Backlog updated (if applicable) | ___ |
| 3 | Monitoring checklist updated (if applicable) | ___ |
| 4 | `current-state.md` still accurate | ___ |
| 5 | `release-timeline.md` includes new milestone (if major) | ___ |
| 6 | `decision-log.md` includes any new decisions | ___ |
| 7 | `lessons-learned.md` includes any new lessons | ___ |
| 8 | `master-handoff-prompt.md` current-state summary still correct | ___ |
| 9 | Next recommended action documented | ___ |
| 10 | Paused/deferred items documented | ___ |
| 11 | Guardrails still accurate | ___ |
| 12 | A completed sub-slice is explicitly distinguished from its incomplete parent program | ___ |

For PTM closeouts, record finding, slice, and parent status separately. For
example, `F01 / PTM0-S1 COMPLETE` must not be shortened to `PTM-0 COMPLETE` while
F02 or later PTM-0 work remains unresolved.

---

## AI Handoff Checklist

When starting a new AI chat/session:

| # | Step |
|---|------|
| 1 | New session reads `docs/project-continuity/` first |
| 2 | New session verifies repository Git state (branch, HEAD, working tree) |
| 3 | New session summarizes current state and latest completed milestone |
| 4 | New session identifies next recommended action |
| 5 | New session states blockers and approval gates |
| 6 | New session asks for latest Kiro/Codex output if unclear |
| 7 | Do NOT paste huge chat history — use continuity docs instead |
| 8 | Provide only the latest relevant Kiro/Codex output, not entire previous conversations |
| 9 | If continuity docs seem outdated, ask Matthew to confirm current state |

---

## ChatGPT Session Rollover Checkpoint

Starting a fresh ChatGPT session is normal project hygiene, not a loss of continuity. The repository documentation is the source of truth — not any single conversation.

### When to roll over to a new session

- ✅ A major implementation milestone is completed (e.g., a slice or group of slices committed)
- ✅ An independent review or major audit/closeout is completed
- ✅ A major release-planning phase is completed
- ✅ The current conversation has become large, sluggish, or error-prone
- ✅ Responses are noticeably slower or large copy/pastes fail
- ✅ Context is becoming difficult to manage or navigate
- ✅ The chat has covered several major releases or implementation slices
- ✅ A clean milestone creates a natural handoff point

### Rollover process

1. Finish the current bounded task or establish a safe stopping point
2. Ensure relevant release notes and continuity docs accurately reflect current state
3. Verify Git state and record the latest committed SHA
4. Record in continuity docs:
   - Latest completed release/milestone
   - Current candidate or next task
   - Deployment/build/distribution state
   - Blockers and approval gates
   - Any pending Kiro/Codex output reference
5. Start a fresh ChatGPT conversation in the same project
6. Have the new session read the continuity docs before recommending actions
7. Provide only the latest relevant Kiro/Codex output when needed (not the full old conversation)
8. Have the new session verify repository state before proceeding

### What NOT to do at rollover

- ❌ Do NOT paste the entire previous conversation into the new session
- ❌ Do NOT rely on the new session remembering prior context
- ❌ Do NOT skip updating continuity docs before rolling over
- ❌ Do NOT leave uncommitted work without documenting its state

---

## Staleness Warning

> If continuity docs and the latest release notes disagree, **the latest release notes win.**

When a mismatch is found:
1. Treat release notes as the source of truth
2. Update the affected continuity doc immediately
3. Note the fix in the commit message

---

## Update Frequency Guide

| Doc | Update Frequency |
|-----|------------------|
| `current-state.md` | Every production release or major status change |
| `release-timeline.md` | Every 5–10 releases (batch update) |
| `decision-log.md` | When a new decision is made |
| `lessons-learned.md` | When a bug/issue teaches something |
| `document-map.md` | When a new doc category/file is created |
| `guardrails.md` | When a new rule is established |
| `master-handoff-prompt.md` | When current-state summary drifts |
| `agent-operating-model.md` | Rarely (workflow is stable) |
| This checklist | When a new trigger type is identified |
