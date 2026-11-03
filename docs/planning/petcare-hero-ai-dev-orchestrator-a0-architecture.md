# PetCare Hero — AI Development Orchestrator (A0 architecture + A1 prototype)

**Status:** A0 architecture accepted; A0.1 Kiro-CLI verification complete; **A1
isolated offline prototype implemented** (this branch). A2+ remain separately
owner-gated.
**Owner / sole approval authority:** Matthew.
**Scope of this document:** architecture, readiness findings, and the A1
prototype contract. This is planning/engineering documentation only. It changes
no application, infrastructure, mobile, or continuity behavior.

> Canonical governance remains `docs/project-continuity/guardrails.md`. Nothing
> in this document or the orchestrator prototype weakens any gate there. The
> orchestrator is a *supervisor* whose entire purpose is to make those gates
> harder to bypass, not a new authority.

---

## 1. Mission

A supervised development system connecting **Kiro** (implementation agent),
**OpenAI** (independent reviewer), **GitHub** (shared evidence / PR repository),
and **Matthew** (final approval authority), automating:

```
APPROVED task -> Kiro implementation -> OpenAI independent review
 -> Kiro corrections -> offline tests -> Draft PR -> milestone summary
 -> MANDATORY OWNER STOP
```

The system must survive session restarts and retain a durable, auditable state.

---

## 2. Readiness findings (A0 + A0.1, read-only)

- **Canonical repo:** `mattnicomn/togs_and_dogs_website` (public). Main checkout
  `C:\USMISSIONHERO\products\petcare-hero`; the primary checkout is frequently
  NOT on `main`. Many feature worktrees exist under the codex worktrees root.
- **Branch protection:** ruleset `protect-main-mvp` (active on `refs/heads/main`):
  PR required, force-push and deletion blocked, no bypass. Secret scanning +
  push protection enabled. No `.github/workflows/` CI yet.
- **Toolchain:** Python 3.13.3 + pytest 9.0.2, gh 2.101.0 (authenticated as the
  **owner** identity — so any delegated merge is procedural, not independent),
  git 2.54, Terraform 1.14.8, aws-cli 2.22.18, node 26 / npm 11.
- **Kiro CLI (A0.1 correction):** two distinct binaries exist.
  - IDE launcher `kiro` / `kiro.cmd` — VS Code-derived, window-attached, no
    headless flags. NOT an automation surface.
  - **Dedicated `kiro-cli` 2.24.0** (`...\AppData\Local\Kiro-Cli\kiro-cli.exe`,
    on PATH) — the real automation surface. `chat` supports `--no-interactive`,
    `--output-format text|stream-json` (stream-json = the run's ACP events as
    JSON Lines on stdout, implies `--no-interactive`), `--trust-tools`,
    `--trust-all-tools`, `--agent`, `--model`, `--effort`, `--agent-engine
    v1|v2|v3` (v2 default), `--mode default|spec`, `--require-mcp-startup`.
    There is **no** literal `--sandbox` flag; the only sandbox concept is
    `chat --cloud` (V3/KAS cloud sandbox), not a local OS sandbox.
  - **Prerequisite gap:** `kiro-cli whoami` = *Not logged in*. A headless run
    requires an owner-approved `kiro-cli login` (Builder ID / Identity Center /
    social OAuth). Login is an owner-gated A2 action.
- **OpenAI:** no SDK installed, no key configured. Reviewer integration is new
  work, gated to A2.

---

## 3. Architecture & data flow

```
                 Matthew (sole approval authority)
     signs APPROVAL MANIFEST (per scope) + future MERGE AUTHORIZATION (SHA-bound)
                              |
                    OWNER-CONTROLLED APPROVALS DIR
                    (outside agent-writable paths)
                              |  read-only
   +--------------------------v-----------------------------+
   |              LOCAL PYTHON ORCHESTRATOR                  |
   |  manifest verifier · budget governor · acceptance       |
   |  engine · corrective-loop driver · durable state ·      |
   |  tamper-evident checkpoints · sanitized logger          |
   +----+-----------------+--------------------+-------------+
        | implement        | independent review | draft PR (mock in A1)
        v                  v                     v
   +---------+       +------------+        +--------------+
   |  KIRO   |       |  OPENAI    |        |   GITHUB     |
   | adapter |       | reviewer   |        |  adapter     |
   +---------+       +------------+        +--------------+
```

The orchestrator holds **no** production AWS/Stripe credentials and performs no
production action. The merge step is never part of the loop; it is a separate,
SHA-bound, owner-authorized, integration-only action (per the canonical
guardrails PR/MR Integration section).

---

## 4. Approval security model (enforced in code, not prose)

1. **Owner-controlled source.** Authorization comes only from an approval
   manifest file in an owner-controlled directory
   (`PETCARE_ORCH_APPROVALS_DIR`), ideally outside the repository. The manifest
   loader **refuses** any manifest that resolves inside an agent-writable
   (runtime) root. An AI-generated file, PR comment, repo document, or mock
   result can therefore never be authorization.
2. **Per-scope, non-transferable.** A manifest authorizes exactly one
   `scope_id` + repository + branch + immutable base SHA + explicit path
   allowlist + explicit action set. No "continue" and no prior milestone
   approval authorizes new scope.
3. **Fail-closed everywhere.** Missing / invalid / untrusted-source approval,
   scope mismatch, SHA mismatch, unknown branch, unexpected path, unauthorized
   action, budget exhaustion, repeated review failure, tampered/corrupt
   checkpoint, and **every milestone completion** each raise a typed stop and
   halt the run.
4. **Independent scope enforcement.** Even when the reviewer returns ACCEPT, the
   orchestrator independently re-checks that every changed path is inside the
   allowlist; the reviewer's opinion never overrides scope.

---

## 5. A1 prototype — what was built (fully offline, mocked)

Package `scripts/orchestrator/` + tests `tests/orchestrator/`:

| Area | Module |
|------|--------|
| Typed fail-closed stops | `errors.py` |
| Budgets / paths / trust boundary | `config.py` |
| Owner approval manifest + verification | `manifest.py` |
| Budget governor (retry/token/cost/time) | `budgets.py` |
| Deterministic acceptance criteria | `acceptance.py` |
| Durable state machine + side-effect ledger | `state.py` |
| Crash-safe, HMAC tamper-evident checkpoints | `checkpoint.py` |
| Sanitized structured JSONL logging | `logging_events.py` |
| Secret / PII redaction | `redaction.py` |
| Execution loop (state-machine driver) | `loop.py` |
| Mock adapters (Kiro / OpenAI / GitHub) | `adapters/*` |
| Milestone report + owner gate | `reports/milestone_report.py` |
| Local CLI (dry-run / status / resume) | `cli.py` |

**Mock adapters replay clearly-labeled SYNTHETIC fixtures.** The Kiro fixture
JSONL shape is the orchestrator's *own* synthetic contract and is **NOT** a
verified live `kiro-cli` ACP event schema — this is stated in code
(`SYNTHETIC_SCHEMA_WARNING`) and in every fixture line. `events_to_result()` is
the single function A2 would adapt once the live schema is confirmed.

**No network, no subprocess, no installs.** The test suite actively blocks
sockets and subprocess spawning (autouse fixtures), so the suite *proves* it
cannot reach the internet, production, or a real agent.

---

## 6. Loop (state machine)

```
CREATED -> AUTHORIZED -> IMPLEMENTING -> REVIEWING
        -> (CORRECTING -> IMPLEMENTING -> REVIEWING)*   # bounded by budget
        -> ACCEPTED -> DRAFT_PR_OPENED -> MILESTONE_COMPLETE
(any)   -> STOPPED
```

State + checkpoint are persisted (atomic write + fsync) after every phase. The
Draft-PR side effect is recorded in an idempotency ledger *before* advancing, so
a crash+resume recognizes it as done and never replays it. Checkpoints are
signed with an HMAC over canonical JSON; any edit without re-signing (including
erasing the effect ledger to force a replay) is detected on load and halts.

---

## 7. A2 prerequisites (separately owner-gated)

1. Owner-approved `kiro-cli login` (choose `--license` / identity).
2. Decision on `--agent-engine` (v2 vs v3), `--model`, and `--effort` pins.
3. Confirm the live `stream-json` ACP event schema and finalize
   `events_to_result()` mapping.
4. OpenAI reviewer: key via environment at call time only (never logged),
   model id pinned, per-call + per-task cost ceilings enforced by the existing
   budget governor. (No SDK installed until A2 is approved.)
5. Confirm `--trust-tools` allowlist as the per-run tool gate.
6. GitHub adapter stays Draft-PR + evidence only; merge remains a separate,
   SHA-bound, owner-authorized, integration-only step.

---

## 8. Milestone / approval structure

A0 architecture → A0.1 CLI verification → **A1 isolated prototype (this branch)**
→ A2 live local adapter integration → A3 supervised pilot → A4 Ryan Android
MVP continuation.

**Ryan Android continuation checkpoint (continuity, not scheduled here):**
distributed internal Android versionCode 4 from `bf9f80d9…`; current source
substantially ahead; E3B/E3B.1 Start/Complete source-complete but not in the
internal build; admin review/approve/decline + M&G verification + assignment
substantially implemented; missing mobile quote create/edit/send and mobile
cancellation decision; gate-aware approval UX needs refinement; Google Calendar
health unverified; planning target Dec 11, 2026 (not a promise). A4 does not
divert into S0d-2 or extra SaaS hardening as an Android-launch prerequisite
absent documented dependency evidence.

---

## 9. A1.1 corrective maintenance (four findings, same branch/PR #60)

Four independently identified A1 gaps were corrected on the same branch; all
remained offline/mocked and preserved the 54-test baseline (now 83 tests;
1 skip where the OS does not support symlinks).

1. **Owner approval trust.** `load_config` no longer defaults the approvals
   source — an unset source raises `ApprovalSourceNotConfigured` (never a repo/
   agent-writable default). `load_manifest` now enforces **positive
   containment** inside the configured owner approvals dir plus full
   **symlink/real-path** resolution, so a symlink escaping into an
   agent-writable tree is refused. `authorized_by` is explicitly audit-only and
   excluded from the integrity fingerprint — it is never proof. An OS-permission
   boundary hook (`assert_owner_source_permissions`) is advisory in A1 and
   enforceable in A2.

2. **Resume authorization.** Every invocation/resume re-verifies manifest
   identity + integrity (persisted `manifest_fingerprint`), scope id +
   repository, base SHA + target branch, persisted task identity + path scope
   (`task_fingerprint`), and allowed actions. Any change raises
   `ResumeAuthorizationChanged`; a terminal STOPPED run raises
   `ResumeOfStoppedWork` and is never auto-resumed.

3. **Side-effect recovery.** Irreversible operations use a durable
   pending → completed model keyed by a stable idempotency key. A crash is
   simulated before the external call, after external success but before
   confirmation, and after persisted completion. On restart an uncertain
   (pending) operation is reconciled against the (mock) GitHub adapter by key:
   a completed-but-unconfirmed call is adopted (never duplicated); if
   reconciliation itself is impossible the run STOPS
   (`SideEffectReconciliationFailed`) rather than retrying blindly.

4. **Cumulative budget recovery.** The budget snapshot now includes
   `elapsed_seconds`; `restore_governor` rebuilds token/cost/correction/
   rejection/elapsed state on resume so budgets are never reset, and rejects a
   malformed or already-over-budget snapshot (`BudgetSnapshotInvalid`).

---

## 10. A1.3 corrective maintenance (two findings, same branch/PR #60)

Two further recovery gaps were hardened on the same branch; all offline/mocked,
preserving the baseline (now 114 tests; 1 skip where the OS lacks symlinks).

**Correction A — operation-status fail-closed.** Before any reconciliation,
rehydration, skip, or new side effect, `_validate_existing_operation` now fully
validates whatever the ledger already holds for the draft-PR effect: it rejects
an unknown/invalid `status`, a non-dict or malformed record, a missing/
mismatched idempotency key, a `completed` record with no result payload, and any
inconsistency between `performed_effects` and `operations` (effect marked done
without a completed record, completed record not in the ledger, pending record
already in the ledger). An invalid existing record is **never** overwritten with
a fresh pending op, and **no adapter call** occurs for an invalid status or
inconsistent ledger — the run stops `OPERATION_RECORD_INVALID`. All valid
crash-reconciliation scenarios and the mandatory owner stop are preserved.

**Correction B — cumulative usage persistence.** `_account` now persists the
cumulative budget snapshot **immediately after each successfully accounted mock
adapter response, before the next operation**, so an inter-operation crash
cannot lose already-accounted usage. On budget exhaustion the governor already
holds the exhausting usage, and the terminal STOPPED checkpoint snapshots it
(usage evidence preserved, never reset). Recovery restores cumulative usage and
never silently resets it. Active-runtime elapsed semantics are unchanged (sum of
wall-clock while the process runs, across restarts; downtime excluded).

**Honest limitation (do not over-claim).** This is best-effort, not exactly-once
*real* API accounting. A live adapter call whose response is never received
(network cut after the server did the work) leaves usage the client never saw,
so the persisted cumulative usage can under-count real provider-side
consumption. A2's live adapters must reconcile actual usage from provider
response metadata where available; the A1 mock accounts only responses the
orchestrator actually received.
