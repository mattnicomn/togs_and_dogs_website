# ADR proposal: Kiro Crew for development coordination, with an independent governance layer

**Status:** PROPOSED. This is documentation only and does not authorize implementation.
**Issue:** #94. **Date:** 2026-11-20. **Owner / decider:** Matthew.
**Scope:** autonomy of the software-development workflow only (plan → implement → test → review → Draft PR → human approval). This is not booking or business automation, and it is separate from the Togs & Dogs pilot milestones (December 11 checkpoint §19). Pilot work continues unaffected.

This ADR authorizes none of the following: installing or running Kiro Crew, activating unattended agents, reading secrets, changing AWS/GitHub settings, or merging any orchestrator PR.

## 1. Context: existing PetCare Orchestrator work (verified 2026-11-20)

None of the orchestrator code is on `main`. It all lives on an open stack of Draft PRs:

| PR | Branch → base | State | What it holds |
|---|---|---|---|
| #60 `[A1] Isolated offline AI development orchestrator prototype` | `codex/ai-dev-orchestrator-a1` → `main` (head `f480f3e`) | Draft, open; +5,521 lines, 40 files | `scripts/orchestrator/` (state machine with side-effect ledger, owner approval-manifest parser with untrusted-source boundary, mock Kiro/OpenAI/GitHub adapters, deterministic acceptance, bounded corrective loop, budget governor, redacted JSONL logging, HMAC tamper-evident checkpoints, owner-stop gate, CLI, milestone report); `tests/orchestrator/` (offline; sockets and subprocess blocked); `docs/planning/petcare-hero-ai-dev-orchestrator-a0-architecture.md` (A0 architecture plus the A0.1 `kiro-cli` check) |
| #61 `[Track 3] Dedicated offline orchestrator CI workflow` | merged into the #60 branch on 2026-11-03 (not into `main`) | Merged into stack | `.github/workflows/orchestrator-ci.yml` (`orchestrator (offline pytest)`, `contents: read`, no secrets) and `tests/orchestrator/requirements-ci.txt` |
| #63 `A2-A G1 offline CI-evidence observation + advisory review` | → #60 branch (head `3f438fe`) | Draft | Read-only GitHub observer protocol, deterministic size-bounded evidence packet with owner-bound baseline, advisory reviewer with strict JSON/schema checks and spend cap (mock transport) |
| #64 `G1.6-B offline Windows-ACL approval-boundary enforcement` | → #63 (head `e39009d`) | Draft | `acl_guard.py`, `acl_windows.py`; the approval guard is required before any lock, authorization or provider call |
| #65 `G1.6-C2 offline hardening of the approval-boundary guard` | → #64 (head `a6b6c66`) | Draft | Token-privilege, path-form, volume-binding and executing-identity checks |
| #66 `G1.6-C3-G0 offline cross-account test harness` | → #65 (head `e84584e`) | Draft; **NOT security-approved** | Cross-account probe harness. Two independent reviews returned NEEDS_CHANGES (29 issues: 10 High, 16 Medium, 3 Low); the fixes were never re-reviewed |

"Level-2 scoped Kiro workflows" refers to the Kiro IDE workflow capability already used in this repository's sessions: planner, coder, code-reviewer, design-reviewer, semantic-reviewer, review-aggregator and PR-submitter agents, with owner-approved steps. This ADR treats it as an existing, in-use capability, separate from Kiro Crew.

**Known risk carried forward (G1.6):** on this Windows workstation the agent and the owner run as the same OS identity. Filesystem or ACL permissions therefore cannot stop the agent from writing "owner-only" approval files. New tooling does not remove this risk automatically.

## 2. Decision (proposed)

Prefer **Kiro Crew as the development-agent coordination layer**, paired with a **small, independently enforced governance layer**, over finishing a fully custom Python orchestration platform. The preference holds only if the capability and security checks in §7 pass.

### Why this over a fully custom orchestrator
- **Scope and maintenance.** The custom stack has grown to about 18,600 added lines across five stacked Draft PRs (#60, #63, #64, #65, #66), none merged to `main`. Most of that effort went into coordination plumbing (agent loops, adapters, retries, CI polling), which a managed coordination layer may already provide.
- **The custom work is strongest where governance is needed.** Approval manifests, evidence packets, budgets, stop control and tamper-evident records are small, testable and independent of the coding agent. Keeping these and dropping the coordination plumbing narrows our own security-critical code.
- **Independence.** A governance layer that the coordinator cannot edit is easier to reason about than one embedded inside our own orchestrator loop.
- **Reversibility.** If Kiro Crew fails validation, the governance components still work with the Kiro IDE workflows in use today.

## 3. Proposed roles (logical roles, not provisioned bots)

| Role | Responsibility | May not |
|---|---|---|
| Conductor | Splits a milestone into tasks, assigns workers, tracks retries and budget, opens Draft PRs | Approve, merge, deploy, edit governance policy or manifests |
| Development | Implements within the manifest's allowed paths on an isolated branch | Touch paths outside the manifest, read secrets, push to protected branches |
| QA | Runs the declared tests; produces machine-generated evidence bound to the commit SHA | Edit the code under test in the same task, waive failures |
| Security | Reviews diff and dependencies against the threat checklist; flags credential, IAM or OAuth impact | Approve its own findings as resolved |
| Independent review | A model and context separate from the developer; issues-only verdict | See or edit the developer's private reasoning; approve merges |
| CI / evidence monitor | Reads GitHub checks and logs (read-only) into the evidence packet | Re-run, edit or dismiss checks |
| **Human owner (Matthew)** | Signs authorization manifests; approves Ready, merge and each deployment separately | — |

## 4. Python governance components to keep (evaluate for reuse; do not delete)

Keep and adapt from the stack (paths as on the #66 branch):
- `manifest.py`: owner approval manifests with scope, SHA and branch binding, plus the untrusted-source boundary.
- `budgets.py`: retry, token, cost and time governor; concurrency caps.
- `checkpoint.py`, `state.py`: crash-safe, HMAC tamper-evident state and the side-effect ledger (no replay of a completed Draft PR).
- `acceptance.py`: deterministic acceptance that a reviewer's ACCEPT can never override.
- `evidence.py`, `evidence_review.py`, `adapters/github_observer.py`: read-only CI-evidence packets with an owner-bound baseline.
- `redaction.py`, `logging_events.py`: redacted, append-only JSONL audit.
- `reports/milestone_report.py`: the human-readable milestone report.
- `.github/workflows/orchestrator-ci.yml`: the offline CI gate for the governance package.

Likely to retire once Kiro Crew is validated (keep until then): `loop.py` corrective-loop driver, `adapters/kiro_adapter.py`, `adapters/openai_adapter.py`, `adapters/github_adapter.py`, `cli.py` run paths.

Defer: `acl_guard.py`, `acl_windows.py`, `c3_*` (G1.6). They solve local same-identity isolation on Windows, and a separate worker identity, VM or container (§5) may make them unnecessary. They stay unmerged and are not security-approved (#66 NEEDS_CHANGES).

## 5. Enforcement model

- **Credential isolation:**
  - Workers run under a disposable identity in a separate VM, container or OS account, never as Matthew's interactive user.
  - They have no AWS production profile, Stripe keys, Google OAuth secrets or Postmark tokens.
  - The only GitHub token is fine-grained and repository-scoped: contents and pull requests write on non-protected branches, checks read. It has no admin, workflow-write or secrets scope.
- **Approvals:**
  - Approval manifests are signed or stored where the worker identity cannot write: a separate account, or a protected GitHub environment or branch the token cannot push to.
  - Each manifest names the exact SHA, branch, allowed paths and operation.
  - Merge and deployment are separate approvals.
  - No agent approves its own work or edits its own guards.
- **GitHub controls:**
  - Branch protection on `main`: required checks, no force push, no bypass for the worker token.
  - Draft PRs only.
  - The evidence packet and the review verdict must reference the head SHA.
- **Audit evidence:**
  - Append-only JSONL plus HMAC checkpoints, stored outside the worker's writable roots.
  - The evidence packet is generated by QA/CI, not by the developer.
- **Spend and stop:**
  - Per-milestone budget, retry cap and wall-clock cap.
  - An owner kill switch checked before every side effect.

## 6. Migration phases and acceptance criteria

| Phase | Work | Exit criteria |
|---|---|---|
| M0 Record (this PR) | ADR, decision-log row, scoped steering file | Owner reviews the Draft PR; nothing installed |
| M1 Capability verification | Read official Kiro Crew docs and terms (no install) | Written answers to every §7 unknown, with sources; go / no-go to M2 |
| M2 Governance extraction design | Map the §4 keep-list onto a standalone package; plan the PR stack | Reuse map approved; #60–#66 stay untouched until then |
| M3 Isolated non-production pilot | One small milestone, isolated identity, repo-scoped token, Draft PR only | The Draft PR passes CI; evidence is SHA-bound; zero secret reads; a human-reviewed report states actual cost |
| M4 Go / no-go | Owner decision on supervised (not unattended) use | Signed decision; unattended mode remains separately gated |

## 7. Unknowns requiring validation

1. Current Kiro Crew availability, licensing or terms, pricing and usage metering.
2. Interfaces: CLI, ACP or headless mode, and whether it runs on Windows, Linux or a remote sandbox.
3. Where its agents run and under which OS or cloud identity, and whether credentials can be scoped per worker.
4. Whether the conductor can be prevented from editing governance files, manifests or CI configuration.
5. Data handling: where repository content and prompts are sent and retained.
6. How it reports retries, failures and cost, and whether that can feed our evidence packet.
7. Whether GitHub branch protection and required checks can be enforced against its token with no bypass.
8. Whether a separate worker identity resolves the G1.6 same-identity risk, or whether G1.6 controls are still needed.

## 8. Consequences

- Togs & Dogs product milestones, including the current Google OAuth recovery, proceed unchanged.
- Orchestrator PRs #60–#66 stay open and unmerged as reference until M2 decides reuse.
- No live agent, credential or infrastructure change happens without a new, explicit authorization.
