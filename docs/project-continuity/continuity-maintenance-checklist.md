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

---

## AI Handoff Checklist

When starting a new AI chat/session:

| # | Step |
|---|------|
| 1 | New session reads `docs/project-continuity/` first |
| 2 | New session summarizes current state before proposing action |
| 3 | New session asks for latest AG/Kiro output if unclear |
| 4 | Do NOT paste huge chat history — use continuity docs instead |
| 5 | If continuity docs seem outdated, ask Matthew to confirm current state |

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
