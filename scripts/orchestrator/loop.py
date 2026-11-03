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
from .budgets import BudgetGovernor
from .checkpoint import CheckpointStore
from .config import Config
from .logging_events import EventLogger
from .manifest import ApprovalManifest, TaskRequest
from .state import RunState, StateStore

# Stable side-effect key for the Draft-PR step (idempotency ledger).
EFFECT_DRAFT_PR = "draft_pr"


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
        self.governor = governor or BudgetGovernor(budgets=config.budgets)
        self.logger = logger or EventLogger(log_path=config.log_path)
        self.state_store = StateStore(config.state_path)
        self.checkpoint_store = CheckpointStore(config.checkpoint_path)
        self._draft_pr: DraftPRResult | None = None

    # --- persistence helpers ----------------------------------------------

    def _persist(self, state: RunState) -> None:
        state.usage = self.governor.snapshot()
        self.state_store.save(state)
        self.checkpoint_store.save(state)

    def _load_or_init(self, request: TaskRequest) -> RunState:
        """Resume from a verified checkpoint, else start fresh.

        Resuming always goes through the tamper-evident checkpoint loader, so a
        tampered/corrupt checkpoint halts the run before any work.
        """

        if self.checkpoint_store.exists():
            state = self.checkpoint_store.load()  # raises on tamper/corruption
            self.logger.emit("resume", phase=state.phase, scope_id=state.scope_id)
            return state
        state = RunState(
            scope_id=request.scope_id,
            repository=request.repository,
            base_sha=request.base_sha,
            target_branch=request.target_branch,
        )
        self._persist(state)
        return state

    # --- public entry ------------------------------------------------------

    def run(self, request: TaskRequest, task: Task) -> LoopResult:
        """Execute (or resume) the run. Returns a terminal :class:`LoopResult`.

        All fail-closed conditions raise an ``OrchestratorStop`` subclass, which
        this method catches to record a STOPPED terminal state and re-raise, so
        callers get both the typed error and a persisted stop record.
        """

        self.governor.start()
        state = self._load_or_init(request)
        try:
            return self._drive(state, request, task)
        except errors.MilestoneOwnerStop as gate:
            # The mandatory owner gate is a *successful* terminal state. Keep
            # the MILESTONE_COMPLETE phase (do NOT overwrite with STOPPED);
            # record the reason separately for auditability.
            state.stop_reason = gate.reason_code
            self._persist(state)
            self.logger.emit("owner_gate", reason=gate.reason_code, detail=gate.detail)
            raise
        except errors.OrchestratorStop as stop:
            # Any other fail-closed halt records a STOPPED terminal state.
            state.mark_stopped(stop.reason_code)
            self._persist(state)
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
            self._account(result.usage)
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
            self._account(review.usage)
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

    def _open_draft_pr(self, state: RunState, task: Task) -> None:
        effect_key = f"{EFFECT_DRAFT_PR}:{state.scope_id}"
        if state.effect_done(effect_key):
            # Already performed before a crash; DO NOT replay. Advance only.
            self.logger.emit("draft_pr_skipped_idempotent", scope_id=state.scope_id)
            state.advance_to("DRAFT_PR_OPENED")
            self._persist(state)
            return

        self.manifest.assert_action_allowed("draft_pr")
        pr = self.github.open_draft_pr(
            base=self.manifest.base_branch,
            head=state.target_branch,
            title=f"[A1][mock] {state.scope_id}",
            body="Synthetic A1 Draft PR (mock adapter). Not a real PR.",
        )
        # Record the effect BEFORE advancing so a crash here still shows it done.
        state.record_effect(effect_key)
        self._draft_pr = pr
        self._persist(state)
        self.logger.emit("draft_pr_opened", number=pr.number, is_draft=pr.is_draft)
        state.advance_to("DRAFT_PR_OPENED")
        self._persist(state)

    def _account(self, usage: Any) -> None:
        self.governor.add_usage(tokens=getattr(usage, "tokens", 0), cost_usd=getattr(usage, "cost_usd", 0.0))

    # --- result assembly ---------------------------------------------------

    def build_result(self, state: RunState, stop_reason: str) -> LoopResult:
        return LoopResult(
            state=state,
            draft_pr=self._draft_pr,
            usage=self.governor.snapshot(),
            milestone_complete=state.phase == "MILESTONE_COMPLETE",
            stop_reason=stop_reason,
        )
