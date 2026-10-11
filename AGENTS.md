# AGENTS

Thin pointer for any agent (ChatGPT, Codex, Kiro Desktop, Kiro Web, Antigravity/AG, or any other authorized agent, from any device). This file does not define policy — it points to the authoritative documents below. Read them before suggesting or making any change.

## Authoritative policy documents

- **Canonical policy:** [`docs/project-continuity/guardrails.md`](docs/project-continuity/guardrails.md) — the single canonical PetCare Hero governance policy. It wins over any shorter copy.
- **Always-on critical subset + session init:** [`.kiro/steering/project-continuity-and-execution.md`](.kiro/steering/project-continuity-and-execution.md) — session initialization, the always-on Absolute Prohibitions subset, and the execution fallback model.
- **Roles + cross-device model:** [`docs/project-continuity/agent-operating-model.md`](docs/project-continuity/agent-operating-model.md) — role definitions, cross-device authorization, development/review/handoff, and desktop reconciliation.
- **Live state:** [`docs/project-continuity/current-state.md`](docs/project-continuity/current-state.md) — what is deployed, blocked, and gated right now.
- **Index/map:** [`docs/project-continuity/document-map.md`](docs/project-continuity/document-map.md) — where to find everything else.

## Top invariants

- No secrets, tokens, passwords, keys, or PII in any file — ever (this is a public repo).
- No production deployment, `terraform apply`, or AWS resource change without explicit Matthew approval.
- Mobile/web access (for example Kiro Web) is **not** additional deploy or implementation authority.
- Use targeted `git add <file>` only; never `git add .`.
- Integration into `main` is PR-only; never push directly to `main` and never self-merge.

## Note

The existing [`mobile/AGENTS.md`](mobile/AGENTS.md) stays as-is; it covers Expo versioned-docs guidance and is not superseded by this file.
