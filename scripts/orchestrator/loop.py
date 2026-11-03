"""The supervised execution loop (state-machine driver).

Wires manifest verification, the three (mock) adapters, acceptance, budgets,
durable state, checkpoints, and sanitized logging into one fail-closed flow:

    APPROVED TASK
      -> MOCK KIRO IMPLEMENTATION
      -> MOCK OPENAI REVIEW
      -> STRUCTURED REJECTION  (bounded)
      -> MOCK CORRECTION
      -> ACCEPTANCE EVALUATION
      -> MOCK DRAFT PR         (idempotent: skipped if already performed)
      -> MILESTONE REPORT
      -> MANDATORY OWNER STOP

Every phase saves state + checkpoint before proceeding, so a crash resumes at
the right place and already-performed side effects are never replayed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import hashlib
import json

from . import acceptance, errors
from .adapters.base import (
    DraftPRResult,
    GitHubAdapter,
    ImplementationAdapter,
    ImplementationResult,
    ReviewAdapter,
    ReviewFinding,
    Task,
)
from .budgets import BudgetGovernor, restore_governor
from .checkpoint import CheckpointStore
from .config import Config
from .logging_events import EventLogger
from .manifest import ApprovalManifest, TaskRequest
from .state import RunState, StateStore

# Stable side-effect key for the Draft-PR step (idempotency ledger).
EFFECT_DRAFT_PR = "draft_pr"


def _pr_to_dict(pr: DraftPRResult) -> dict[str, Any]:
    return {
        "number": pr.number,
        "url": pr.url,
        "is_draft": pr.is_draft,
        "is_open": pr.is_open,
        "is_merged": pr.is_merged,
        "base": pr.base,
        "head": pr.head,
    }


def _dict_to_pr(d: dict[str, Any]) -> DraftPRResult:
    return DraftPRResult(
        number=int(d["number"]),
        url=str(d["url"]),
        is_draft=bool(d["is_draft"]),
        is_open=bool(d["is_open"]),
        is_merged=bool(d["is_merged"]),
        base=str(d["base"]),
        head=str(d["head"]),
    )


def _is_sha256_hex(value: str) -> bool:
    """True iff ``value`` is a 64-char lowercase hex SHA-256 digest."""

    if len(value) != 64:
        return False
    return all(c in "0123456789abcdef" for c in value)


def task_fingerprint(task: Task) -> str:
    """Stable digest of the task identity + path scope (Finding 2).

    Persisted at authorize time and re-checked on every resume so a resumed run
    cannot be pointed at a different task, acceptance key, or path set than the
    one originally authorized.
    """

    canonical = json.dumps(
        {
            "scope_id": task.scope_id,
            "description": task.description,
            "target_paths": sorted(task.target_paths),
            "acceptance_key": task.acceptance_key,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class LoopResult:
    """Terminal outcome of a run for reporting."""

    state: RunState
    draft_pr: DraftPRResult | None
    usage: dict[str, Any]
    milestone_complete: bool
    stop_reason: str


class Orchestrator:
    """Owns the loop for a single task/milestone run."""

    def __init__(
        self,
        *,
        config: Config,
        manifest: ApprovalManifest,
        kiro: ImplementationAdapter,
        reviewer: ReviewAdapter,
        github: GitHubAdapter,
        governor: BudgetGovernor | None = None,
        logger: EventLogger | None = None,
    ) -> None:
        self.config = config
        self.manifest = manifest
        self.kiro = kiro
        self.reviewer = reviewer
        self.github = github
        # Governor may be injected (tests) or built fresh here; on resume it is
        # REPLACED by one restored from the persisted snapshot (Finding 4).
        self._injected_governor = governor
        self.governor = governor or BudgetGovernor(budgets=config.budgets)
        self.logger = logger or EventLogger(log_path=config.log_path)
        self.state_store = StateStore(config.state_path)
        self.checkpoint_store = CheckpointStore(config.checkpoint_path)
        self._draft_pr: DraftPRResult | None = None
        # Set when a checkpoint is loaded, so a stop raised during resume
        # authorization/budget restore can still persist a STOPPED record.
        self._loaded_state: RunState | None = None

    # --- persistence helpers ----------------------------------------------

    def _persist(self, state: RunState) -> None:
        state.usage = self.governor.snapshot()
        self.state_store.save(state)
        self.checkpoint_store.save(state)

    def _load_or_init(self, request: TaskRequest, task: Task) -> RunState:
        """Resume from a verified checkpoint, else start fresh.

        Resuming always goes through the tamper-evident checkpoint loader (so a
        tampered/corrupt checkpoint halts before any work) AND then re-runs full
        resume authorization (Finding 2) and restores cumulative budgets
        (Finding 4) before any further work.
        """

        if self.checkpoint_store.exists():
            state = self.checkpoint_store.load()  # raises on tamper/corruption
            # Expose the loaded state so a stop DURING resume authorization /
            # budget restore can still be persisted as a STOPPED record.
            self._loaded_state = state
            self.logger.emit("resume", phase=state.phase, scope_id=state.scope_id)
            self._authorize_resume(state, request, task)   # Finding 2
            self.governor = self._restore_budgets(state)    # Finding 4
            return state

        # Fresh run: budgets start empty; authorization is checked in _drive at
        # the CREATED phase and the fingerprints are recorded there.
        self.governor = (
            self._injected_governor
            if self._injected_governor is not None
            else BudgetGovernor(budgets=self.config.budgets)
        )
        state = RunState(
            scope_id=request.scope_id,
            repository=request.repository,
            base_sha=request.base_sha,
            target_branch=request.target_branch,
        )
        self._persist(state)
        return state

    def _authorize_resume(self, state: RunState, request: TaskRequest, task: Task) -> None:
        """Re-verify ALL authorization bindings on resume (Finding 2 / F2).

        Any changed, missing, or malformed binding is a hard stop; STOPPED work
        is never auto-resumed.

        F2 hardening: once a run has advanced past CREATED, both
        ``manifest_fingerprint`` and ``task_fingerprint`` MUST be present,
        nonempty, correctly typed, and match freshly derived values before any
        adapter work. A missing/empty/malformed fingerprint on a past-CREATED
        resume is itself a ``ResumeAuthorizationChanged`` (fail-closed) rather
        than being skipped.
        """

        # 1. Never auto-resume terminal STOPPED work.
        if state.is_terminal_stopped():
            raise errors.ResumeOfStoppedWork(
                f"run for {state.scope_id} is STOPPED ({state.stop_reason}); "
                "re-authorization required"
            )

        # 2. Scope identity verified against the live manifest + request.
        self.manifest.verify(request)  # ScopeMismatch / UnknownBranch / ShaMismatch

        # 3. Persisted scope identity must match the request.
        if (
            state.scope_id != request.scope_id
            or state.repository != request.repository
            or state.base_sha != request.base_sha
            or state.target_branch != request.target_branch
        ):
            raise errors.ResumeAuthorizationChanged(
                "persisted scope identity differs from request"
            )

        live_manifest_fp = self.manifest.fingerprint()
        live_task_fp = task_fingerprint(task)

        # 4. Fingerprint binding.
        #    A resume at phase CREATED is a pre-authorization checkpoint (the
        #    fingerprints are recorded when _drive first authorizes), so it is
        #    the ONLY phase allowed to carry empty fingerprints. Every phase
        #    past CREATED must carry valid, matching fingerprints.
        past_created = state.phase != "CREATED"

        self._verify_resume_fingerprint(
            label="manifest",
            persisted=state.manifest_fingerprint,
            live=live_manifest_fp,
            required=past_created,
        )
        self._verify_resume_fingerprint(
            label="task",
            persisted=state.task_fingerprint,
            live=live_task_fp,
            required=past_created,
        )

        # 5. Re-assert path scope and allowed actions against the live manifest.
        self.manifest.assert_paths_allowed(list(task.target_paths))
        self.manifest.assert_action_allowed("implement")

        self.logger.emit("resume_authorized", scope_id=state.scope_id, phase=state.phase)

    @staticmethod
    def _verify_resume_fingerprint(*, label: str, persisted: object, live: str, required: bool) -> None:
        """Fail-closed validation of one persisted fingerprint field (F2).

        ``required`` is True for any phase past CREATED. When required, the
        persisted value must be a nonempty 64-char lowercase hex string equal to
        ``live``. When not required (CREATED), a ``None`` is tolerated, but a
        present value must still be well-formed and match.
        """

        if persisted is None:
            if required:
                raise errors.ResumeAuthorizationChanged(
                    f"{label} fingerprint missing on a past-CREATED resume"
                )
            return  # CREATED: no fingerprint recorded yet -> legitimate.

        if not isinstance(persisted, str) or not _is_sha256_hex(persisted):
            raise errors.ResumeAuthorizationChanged(
                f"{label} fingerprint is malformed"
            )
        if persisted != live:
            raise errors.ResumeAuthorizationChanged(
                f"{label} fingerprint changed since authorization"
            )

    def _restore_budgets(self, state: RunState) -> BudgetGovernor:
        """Rebuild the governor from the persisted snapshot (Finding 4 / F4).

        This is only ever called on RESUME (a checkpoint already existed), so a
        complete cumulative snapshot is required: every persisted checkpoint —
        including one at phase CREATED — was written by ``_persist`` with a full
        ``governor.snapshot()``, so a missing/partial snapshot here means a
        corrupted/forged record and is rejected fail-closed. Budgets are never
        reset; an injected governor's clock is preserved for deterministic tests.
        """

        restored = restore_governor(
            self.config.budgets,
            state.usage,
            now=self._injected_governor.now if self._injected_governor else None,
            require_complete=True,
        )
        return restored

    # --- public entry ------------------------------------------------------

    def run(self, request: TaskRequest, task: Task) -> LoopResult:
        """Execute (or resume) the run. Returns a terminal :class:`LoopResult`.

        All fail-closed conditions raise an ``OrchestratorStop`` subclass, which
        this method catches to record a STOPPED terminal state and re-raise, so
        callers get both the typed error and a persisted stop record.
        """

        state: RunState | None = None
        try:
            state = self._load_or_init(request, task)
            # start() times only the NEW segment; prior elapsed is carried in
            # the restored governor (Finding 4).
            self.governor.start()
            return self._drive(state, request, task)
        except errors.MilestoneOwnerStop as gate:
            # The mandatory owner gate is a *successful* terminal state. Keep
            # the MILESTONE_COMPLETE phase (do NOT overwrite with STOPPED);
            # record the reason separately for auditability.
            if state is not None:
                state.stop_reason = gate.reason_code
                self._persist(state)
            self.logger.emit("owner_gate", reason=gate.reason_code, detail=gate.detail)
            raise
        except errors.OrchestratorStop as stop:
            # Any other fail-closed halt records a STOPPED terminal state.
            if state is not None:
                # Stop raised during the ACTIVE run (e.g. budget exhaustion):
                # the governor already reflects the exhausting accounted usage,
                # so snapshot it into the terminal STOPPED checkpoint. This is
                # Correction B (A1.3): usage evidence is preserved, never reset.
                if not state.is_terminal_stopped():
                    state.mark_stopped(stop.reason_code)
                    self._persist(state)  # _persist() refreshes usage from the governor
            else:
                # Stop raised DURING _load_or_init (resume authorization /
                # budget restore): the governor may be pre-restore, so fall back
                # to the loaded checkpoint state and PRESERVE its persisted usage
                # snapshot rather than overwriting it with an unrestored governor.
                record = self._loaded_state
                if record is not None and not record.is_terminal_stopped():
                    record.mark_stopped(stop.reason_code)
                    self.state_store.save(record)
                    self.checkpoint_store.save(record)
            self.logger.emit("stop", reason=stop.reason_code, detail=stop.detail)
            raise

    # --- the state machine -------------------------------------------------

    def _drive(self, state: RunState, request: TaskRequest, task: Task) -> LoopResult:
        # AUTHORIZE: verify the manifest against the request (fail-closed).
        if state.phase == "CREATED":
            self.manifest.verify(request)  # ScopeMismatch / UnknownBranch / ShaMismatch
            # The task's declared target paths must also be in scope up front.
            self.manifest.assert_action_allowed("implement")
            self.manifest.assert_paths_allowed(list(task.target_paths))
            # Bind the authorization: persist fingerprints re-checked on resume.
            state.manifest_fingerprint = self.manifest.fingerprint()
            state.task_fingerprint = task_fingerprint(task)
            self.logger.emit("authorized", scope_id=state.scope_id, base_sha=state.base_sha)
            state.advance_to("AUTHORIZED")
            self._persist(state)

        # IMPLEMENT + REVIEW + bounded CORRECTION loop.
        if state.phase in ("AUTHORIZED", "IMPLEMENTING", "REVIEWING", "CORRECTING"):
            self._implement_review_correct(state, task)

        # DRAFT PR (idempotent via side-effect ledger).
        if state.phase == "ACCEPTED":
            self._open_draft_pr(state, task)

        # MILESTONE complete -> mandatory owner stop.
        if state.phase == "DRAFT_PR_OPENED":
            state.advance_to("MILESTONE_COMPLETE")
            self._persist(state)
            self.logger.emit("milestone_complete", scope_id=state.scope_id)
            # The mandatory gate: completing a milestone unconditionally halts.
            raise errors.MilestoneOwnerStop(
                f"milestone {state.scope_id} complete; fresh owner approval required to continue"
            )

        if state.phase == "MILESTONE_COMPLETE":
            # Resumed after the gate already fired: re-assert the stop.
            raise errors.MilestoneOwnerStop(
                f"milestone {state.scope_id} already complete; owner gate stands"
            )

        # Should be unreachable; fail closed if we somehow fall through.
        raise errors.OrchestratorStop(f"unexpected phase fallthrough: {state.phase}")

    def _implement_review_correct(self, state: RunState, task: Task) -> None:
        prior_findings: tuple[ReviewFinding, ...] = ()

        while True:
            self.governor.check_time()

            # IMPLEMENT (or CORRECT on later iterations).
            state.advance_to("IMPLEMENTING")
            self._persist(state)
            result = self.kiro.implement(task, prior_findings)
            self._account(state, result.usage)
            # Independent scope enforcement on whatever the agent claims to touch.
            self.manifest.assert_paths_allowed(list(result.changed_paths))
            self.logger.emit(
                "implemented",
                iteration=state.iteration,
                changed_paths=list(result.changed_paths),
            )

            # REVIEW.
            state.advance_to("REVIEWING")
            self._persist(state)
            review = self.reviewer.review(task, result)
            self._account(state, review.usage)
            decision = acceptance.evaluate(task, result, review, self.manifest)
            self.logger.emit(
                "reviewed",
                iteration=state.iteration,
                verdict=review.verdict,
                accepted=decision.accepted,
                reason=decision.reason_code,
                finding_count=len(review.findings),
            )

            if decision.accepted:
                state.advance_to("ACCEPTED")
                self._persist(state)
                return

            # Not accepted -> count a rejection (may exhaust review budget).
            self.governor.record_rejection()

            # CORRECT: bounded by the correction-retry budget.
            self.governor.record_correction()
            state.iteration += 1
            state.advance_to("CORRECTING")
            self._persist(state)
            prior_findings = review.findings
            self.logger.emit("correcting", iteration=state.iteration)

    def _draft_pr_idempotency_key(self, state: RunState) -> str:
        """Stable idempotency key bound to the authorized scope (Finding 3).

        Deterministic across restarts so a replay reconciles to the SAME PR.
        """

        material = f"{EFFECT_DRAFT_PR}|{state.scope_id}|{state.base_sha}|{state.target_branch}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]

    def _open_draft_pr(self, state: RunState, task: Task) -> None:
        effect_key = f"{EFFECT_DRAFT_PR}:{state.scope_id}"
        idem = self._draft_pr_idempotency_key(state)

        # Correction A (A1.3): before ANY reconciliation, rehydration, skip, or
        # new side effect, fully validate whatever the ledger already holds for
        # this effect. This fail-closed gate covers EVERY pre-existing record —
        # including unknown/invalid statuses and performed_effects/operations
        # inconsistencies — so an invalid record can never (a) slip through to
        # the fresh-operation path, (b) be overwritten by a new pending op, or
        # (c) drive a reconcile/skip. It returns the validated status, or None
        # when there is genuinely no prior record of any kind.
        status = self._validate_existing_operation(state, effect_key, idem)

        # Already completed (confirmed + persisted): never replay. Rehydrate the
        # result for reporting (validated), and advance.
        if status == "completed":
            self._draft_pr = self._rehydrate_draft_pr(state, effect_key, idem)
            self._assert_result_compatible(state, self._draft_pr, context="rehydrate")
            self.logger.emit("draft_pr_skipped_idempotent", scope_id=state.scope_id)
            state.advance_to("DRAFT_PR_OPENED")
            self._persist(state)
            return

        # Pending (a prior attempt crashed in an uncertain window): RECONCILE
        # against the adapter using the idempotency key before doing anything.
        if status == "pending":
            self._reconcile_pending_draft_pr(state, effect_key, idem)
            return

        # status is None here: no prior record exists, so starting a fresh
        # operation cannot overwrite anything.
        self.manifest.assert_action_allowed("draft_pr")

        # Durable pending BEFORE the external call (Finding 3 step 1).
        state.begin_operation(effect_key, idem)
        self._persist(state)
        self.logger.emit("draft_pr_pending", scope_id=state.scope_id)

        pr = self.github.open_draft_pr(
            base=self.manifest.base_branch,
            head=state.target_branch,
            title=f"[A1][mock] {state.scope_id}",
            body="Synthetic A1 Draft PR (mock adapter). Not a real PR.",
            idempotency_key=idem,
        )

        # Confirmed success -> mark completed + record effect (step 3).
        state.complete_operation(effect_key, _pr_to_dict(pr))
        self._draft_pr = pr
        self._persist(state)
        self.logger.emit("draft_pr_opened", number=pr.number, is_draft=pr.is_draft)
        state.advance_to("DRAFT_PR_OPENED")
        self._persist(state)

    def _validate_existing_operation(self, state: RunState, effect_key: str, expected_idem: str) -> str | None:
        """Correction A (A1.3): fully validate any pre-existing ledger trace.

        Returns the validated status (``"pending"`` or ``"completed"``) when a
        well-formed, identity-matching record exists, or ``None`` when there is
        genuinely no prior record of any kind. Raises ``OperationRecordInvalid``
        (fail-closed, before any adapter work) for:

          * an operation record that is not a dict,
          * an unknown/invalid ``status`` (anything other than pending/completed),
          * a missing/malformed/mismatched ``idempotency_key``,
          * a ``completed`` record lacking a usable result payload,
          * inconsistency between ``performed_effects`` and ``operations``
            (effect marked done without a completed record, or a completed
            record whose effect was not recorded in the ledger).

        Crucially, an invalid existing record is NEVER overwritten with a fresh
        pending op — this method raises instead of returning ``None``.
        """

        # Distinguish a GENUINELY ABSENT key from a PRESENT key whose value is
        # None (or otherwise malformed). ``dict.get`` returns None in both
        # cases, which would wrongly let a present-but-None record fall through
        # to fresh execution; use membership to tell them apart (A1.3 edge).
        key_present = effect_key in state.operations
        record = state.operations.get(effect_key)
        effect_marked = state.effect_done(effect_key)

        # (1) No trace at all (key truly absent AND not in the effect ledger)
        #     -> a genuinely fresh operation.
        if not key_present and not effect_marked:
            return None

        # (2) performed_effects says "done" but there is no operations record at
        #     all: inconsistent ledger, fail closed (do not fabricate/skip).
        if not key_present and effect_marked:
            raise errors.OperationRecordInvalid(
                f"operation {effect_key} is marked performed but has no operation record"
            )

        # (3) The key EXISTS. A None (or any non-dict) value is a malformed
        #     record and must fail closed BEFORE any adapter work — it is never
        #     treated as "absent" and never overwritten with a fresh pending op.
        if not isinstance(record, dict):
            raise errors.OperationRecordInvalid(
                f"operation {effect_key} record is present but not an object ({record!r})"
            )
        status = record.get("status")
        if status not in ("pending", "completed"):
            raise errors.OperationRecordInvalid(
                f"operation {effect_key} has unknown/invalid status {status!r}"
            )
        self._assert_operation_identity(state, effect_key, expected_idem)

        # (4) Cross-check the performed_effects ledger against the status.
        if status == "completed":
            if not effect_marked:
                raise errors.OperationRecordInvalid(
                    f"operation {effect_key} is completed but not recorded in performed_effects"
                )
            if not isinstance(record.get("result"), dict):
                raise errors.OperationRecordInvalid(
                    f"operation {effect_key} is completed but carries no result payload"
                )
        else:  # pending
            if effect_marked:
                raise errors.OperationRecordInvalid(
                    f"operation {effect_key} is pending but already in performed_effects"
                )

        return status

    def _assert_operation_identity(self, state: RunState, effect_key: str, expected_idem: str) -> None:
        """F3: validate the persisted operation record before trusting it.

        The record must exist, be a dict with a known status, and carry an
        ``idempotency_key`` that exactly equals ``expected_idem`` (derived from
        the authorized scope identity). Anything else is a hard stop so a forged
        or corrupted record can never drive a reconcile/lookup/skip.
        """

        record = state.operations.get(effect_key)
        if not isinstance(record, dict):
            raise errors.OperationRecordInvalid(f"operation {effect_key} record is not an object")
        if record.get("status") not in ("pending", "completed"):
            raise errors.OperationRecordInvalid(f"operation {effect_key} has unknown status")
        persisted_key = record.get("idempotency_key")
        if not isinstance(persisted_key, str) or not persisted_key:
            raise errors.OperationRecordInvalid(f"operation {effect_key} idempotency key missing/malformed")
        if persisted_key != expected_idem:
            raise errors.OperationRecordInvalid(
                f"operation {effect_key} idempotency key does not match authorized identity"
            )

    def _assert_result_compatible(self, state: RunState, pr: DraftPRResult | None, *, context: str) -> None:
        """F3: a reconciled/rehydrated PR must match authorized identity + A1
        draft/open/unmerged semantics before it is adopted."""

        if pr is None:
            raise errors.ReconciledResultIncompatible(
                f"{context}: no result available to validate"
            )
        problems: list[str] = []
        if pr.base != self.manifest.base_branch:
            problems.append(f"base {pr.base!r} != authorized {self.manifest.base_branch!r}")
        if pr.head != state.target_branch:
            problems.append(f"head {pr.head!r} != authorized {state.target_branch!r}")
        if not pr.is_draft:
            problems.append("not a draft")
        if not pr.is_open:
            problems.append("not open")
        if pr.is_merged:
            problems.append("is merged (A1 must never adopt a merged PR)")
        if problems:
            raise errors.ReconciledResultIncompatible(f"{context}: " + "; ".join(problems))

    def _reconcile_pending_draft_pr(self, state: RunState, effect_key: str, idem: str) -> None:
        """Reconcile an uncertain (pending) Draft-PR op after a crash.

        Look the PR up by its idempotency key. If found, the prior call DID
        succeed: adopt it (never duplicate). If not found, it is safe to perform
        the call exactly once now. If reconciliation itself cannot be performed,
        STOP rather than retry blindly.
        """

        self.logger.emit("draft_pr_reconcile", scope_id=state.scope_id)
        try:
            found = self.github.find_by_idempotency_key(idem)
        except Exception as exc:  # reconciliation impossible -> fail closed
            raise errors.SideEffectReconciliationFailed(
                f"could not reconcile pending draft PR: {exc}"
            ) from exc

        if found is not None:
            # F3: before adopting a reconciled result, verify it matches the
            # authorized base/head and the required draft/open/unmerged
            # semantics. An incompatible result is NOT adopted (fail-closed).
            self._assert_result_compatible(state, found, context="reconcile")
            # The earlier call had already succeeded server-side.
            state.complete_operation(effect_key, _pr_to_dict(found))
            self._draft_pr = found
            self._persist(state)
            self.logger.emit("draft_pr_reconciled_existing", number=found.number)
            state.advance_to("DRAFT_PR_OPENED")
            self._persist(state)
            return

        # Not found: the prior attempt never reached the server. Perform once.
        self.manifest.assert_action_allowed("draft_pr")
        pr = self.github.open_draft_pr(
            base=self.manifest.base_branch,
            head=state.target_branch,
            title=f"[A1][mock] {state.scope_id}",
            body="Synthetic A1 Draft PR (mock adapter). Not a real PR.",
            idempotency_key=idem,
        )
        state.complete_operation(effect_key, _pr_to_dict(pr))
        self._draft_pr = pr
        self._persist(state)
        self.logger.emit("draft_pr_opened_after_reconcile", number=pr.number)
        state.advance_to("DRAFT_PR_OPENED")
        self._persist(state)

    def _rehydrate_draft_pr(self, state: RunState, effect_key: str, idem: str) -> DraftPRResult | None:
        """Rebuild the DraftPRResult for a completed op (for reporting)."""

        result = state.operation_result(effect_key)
        if result:
            return _dict_to_pr(result)
        # Fall back to an adapter lookup if the persisted result is absent.
        try:
            return self.github.find_by_idempotency_key(idem)
        except Exception:  # pragma: no cover - defensive
            return None

    def _account(self, state: RunState, usage: Any) -> None:
        """Account one mock adapter response and persist the cumulative usage.

        Correction B (A1.3): the governor adds the reported usage BEFORE any
        budget-ceiling check (so the exhausting usage is already reflected), and
        this method persists the cumulative snapshot IMMEDIATELY after a
        successful accounting — before the next operation — so an inter-operation
        crash can never lose already-accounted usage. If ``add_usage`` raises
        ``BudgetExhausted``, the governor still holds the accounted usage; the
        STOPPED checkpoint written by ``run``'s handler then preserves that
        evidence (the exhausting usage is included, not reset).
        """

        self.governor.add_usage(
            tokens=getattr(usage, "tokens", 0),
            cost_usd=getattr(usage, "cost_usd", 0.0),
        )
        # Durable usage checkpoint at the post-accounting boundary.
        self._persist(state)

    # --- result assembly ---------------------------------------------------

    def build_result(self, state: RunState, stop_reason: str) -> LoopResult:
        return LoopResult(
            state=state,
            draft_pr=self._draft_pr,
            usage=self.governor.snapshot(),
            milestone_complete=state.phase == "MILESTONE_COMPLETE",
            stop_reason=stop_reason,
        )
