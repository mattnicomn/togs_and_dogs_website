"""A2-A G1 runner: observe -> package evidence -> advisory review -> OWNER STOP.

Everything here is offline. The runner composes the A1 control plane (owner
manifest, fingerprints, HMAC checkpoint, budget governor, redacting logger)
with the read-only observer, the deterministic evidence packet and the advisory
reviewer. It can only ever END in the mandatory owner gate (or a typed stop):

  CREATED -> OBSERVED -> PACKETED -> REVIEWED -> OWNER_STOP     (any -> STOPPED)

Authority model:
  * Authorization comes ONLY from the owner-controlled manifest (same trust
    boundary as A1). PR titles/bodies, CI logs and reviewer output are untrusted
    data and are never read as approval.
  * The runner holds no write capability: the observer protocol is read-only and
    there is no merge / ready / deploy / comment operation anywhere.
  * The reviewer's verdict is advisory metadata. It cannot change a phase, widen
    scope, or skip the owner gate; a reviewer request to widen scope is itself a
    deterministic stop.

Crash safety: a review call is recorded as ``pending`` BEFORE it is sent. If the
process dies mid-call, a resume finds the pending record and STOPS
(``REVIEW_CALL_UNCERTAIN``) rather than risk a second billed call.
"""

from __future__ import annotations

import hmac
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from . import checkpoint as _checkpoint
from . import errors, evidence
from .adapters.github_observer import (
    GitHubReadObserver,
    JobObservation,
    PullRequestObservation,
    WorkflowRunObservation,
)
from .adapters.openai_evidence_reviewer import OpenAIEvidenceReviewer
from .acl_guard import ApprovalGuard, ApprovedFileSnapshot, BoundaryReport, ProductionApprovalGuard
from .adapters.github_observer import FixtureGitHubObserver
from .budgets import BudgetGovernor, restore_governor
from .config import Config
from .logging_events import EventLogger
from .manifest import ApprovalManifest, ApprovedPullRequest, TaskRequest
from .state import atomic_write_json

BACKEND_JOB_NAME = "backend (pytest)"
WEB_JOB_NAME = "web (lint, test, build)"

PHASES = ("CREATED", "OBSERVED", "PACKETED", "REVIEWED", "OWNER_STOP", "STOPPED")
_ALLOWED: dict[str, frozenset[str]] = {
    "CREATED": frozenset({"OBSERVED"}),
    "OBSERVED": frozenset({"PACKETED"}),
    "PACKETED": frozenset({"REVIEWED"}),
    "REVIEWED": frozenset({"OWNER_STOP"}),
    "OWNER_STOP": frozenset(),
    "STOPPED": frozenset(),
}
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class EvidenceRequest:
    """What the caller asks to be observed. Authorized only via the manifest."""

    scope_id: str
    repository: str
    base_sha: str
    target_branch: str
    pr_number: int
    expected_head_sha: str

    def fingerprint(self, approval: ApprovedPullRequest) -> str:
        return evidence.sha256_hex(
            evidence.canonical_json(
                {
                    "scope_id": self.scope_id,
                    "repository": self.repository,
                    "base_sha": self.base_sha,
                    "target_branch": self.target_branch,
                    "pr_number": self.pr_number,
                    "expected_head_sha": self.expected_head_sha,
                    "approval": approval.canonical(),
                }
            )
        )


@dataclass
class ReviewRunState:
    scope_id: str
    repository: str
    pr_number: int
    head_sha: str
    base_sha: str
    target_branch: str
    phase: str = "CREATED"
    manifest_fingerprint: str | None = None
    request_fingerprint: str | None = None
    packet_fingerprint: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    call: dict[str, Any] | None = None
    stop_reason: str | None = None
    schema_version: int = SCHEMA_VERSION

    def advance_to(self, phase: str) -> None:
        if phase not in _ALLOWED:
            raise ValueError(f"unknown phase: {phase}")
        if phase == "STOPPED":
            self.phase = phase
            return
        if phase == self.phase:
            return
        if phase not in _ALLOWED[self.phase]:
            raise ValueError(f"illegal transition {self.phase} -> {phase}")
        self.phase = phase

    def mark_stopped(self, reason_code: str) -> None:
        self.phase = "STOPPED"
        self.stop_reason = reason_code

    def is_terminal_stopped(self) -> bool:
        return self.phase == "STOPPED"

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}  # type: ignore[attr-defined]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewRunState":
        known = {f: data[f] for f in cls.__dataclass_fields__ if f in data}  # type: ignore[attr-defined]
        state = cls(**known)
        if state.phase not in PHASES:
            raise ValueError("unknown phase in checkpoint")
        return state


@dataclass
class ReviewCheckpointStore(_checkpoint.CheckpointStore):
    """HMAC-signed checkpoint for :class:`ReviewRunState` (same scheme as A1)."""

    def load(self) -> ReviewRunState:  # type: ignore[override]
        if not self.key_path.is_file():
            raise errors.CheckpointTampered("integrity key missing; cannot verify checkpoint")
        key = self.key_path.read_bytes()
        try:
            envelope = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise errors.CheckpointCorrupt(f"checkpoint unreadable: {exc.__class__.__name__}") from exc
        if (
            not isinstance(envelope, dict)
            or _checkpoint._PAYLOAD_FIELD not in envelope
            or _checkpoint._DIGEST_FIELD not in envelope
        ):
            raise errors.CheckpointCorrupt("checkpoint envelope malformed")
        payload = envelope[_checkpoint._PAYLOAD_FIELD]
        stored = envelope[_checkpoint._DIGEST_FIELD]
        if not isinstance(payload, dict) or not isinstance(stored, str):
            raise errors.CheckpointCorrupt("checkpoint fields wrong type")
        if not hmac.compare_digest(self._digest(payload, key), stored):
            raise errors.CheckpointTampered("checkpoint digest mismatch")
        try:
            return ReviewRunState.from_dict(payload)
        except (TypeError, ValueError) as exc:
            raise errors.CheckpointCorrupt("checkpoint payload invalid") from exc


class RunLock:
    """Exclusive runtime-dir lock. A stale lock is a stop, not auto-cleared."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def __enter__(self) -> "RunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise errors.RunLocked(
                "another run holds the lock (or a stale lock remains); the owner must clear it"
            ) from None
        try:
            os.write(fd, str(os.getpid()).encode("ascii"))
        finally:
            os.close(fd)
        return self

    def __exit__(self, *exc: object) -> None:
        try:
            os.unlink(self.path)
        except FileNotFoundError:  # pragma: no cover
            pass


class EvidenceReviewRunner:
    def __init__(
        self,
        *,
        config: Config,
        manifest: ApprovalManifest,
        observer: GitHubReadObserver,
        reviewer: OpenAIEvidenceReviewer,
        baseline_ids: Sequence[str],
        approval_guard: ApprovalGuard,
        approved_snapshot: ApprovedFileSnapshot | None = None,
        observer_name: str = "fixture",
        governor: BudgetGovernor | None = None,
        logger: EventLogger | None = None,
    ) -> None:
        # The guard is REQUIRED (no default): there is no silent way to skip the
        # OS approval-boundary check.
        if not callable(getattr(approval_guard, "verify", None)) or not isinstance(
            getattr(approval_guard, "mode", None), str
        ):
            raise TypeError("approval_guard must provide verify() and a mode")
        self.approval_guard = approval_guard
        self.approved_snapshot = approved_snapshot
        self.boundary_report: BoundaryReport | None = None
        self.config = config
        self.manifest = manifest
        self.observer = observer
        self.reviewer = reviewer
        self.baseline_ids = tuple(baseline_ids)
        self.observer_name = observer_name
        self._injected_governor = governor
        self.governor = governor or BudgetGovernor(budgets=config.budgets)
        self.logger = logger or EventLogger(log_path=config.log_path)
        self.store = ReviewCheckpointStore(config.runtime_dir / "a2a_checkpoint.json")
        self._approval: ApprovedPullRequest | None = None
        self._loaded_state: ReviewRunState | None = None
        self.packet: dict[str, Any] | None = None
        self.state: ReviewRunState | None = None

    # --- persistence ------------------------------------------------------

    def _persist(self, state: ReviewRunState) -> None:
        state.usage = self.governor.snapshot()
        self.store.save(state)  # type: ignore[arg-type]
        atomic_write_json(self.config.runtime_dir / "a2a_state.json", state.to_dict())

    # --- authorization ----------------------------------------------------

    def _authorize(self, request: EvidenceRequest) -> ApprovedPullRequest:
        self.manifest.verify(
            TaskRequest(
                scope_id=request.scope_id,
                repository=request.repository,
                base_sha=request.base_sha,
                target_branch=request.target_branch,
            )
        )
        self.manifest.assert_action_allowed("observe_pr")
        self.manifest.assert_action_allowed("review_evidence")
        approval = self.manifest.assert_pull_request_approved(request.pr_number, request.expected_head_sha)
        if approval.baseline_ids_sha256 is None:
            raise errors.EvidenceIncomplete("the manifest does not bind a baseline hash for this PR")
        self._approval = approval
        return approval

    def _verify_resume(self, state: ReviewRunState, request: EvidenceRequest, approval: ApprovedPullRequest) -> None:
        if (
            state.scope_id != request.scope_id
            or state.repository != request.repository
            or state.pr_number != request.pr_number
            or state.head_sha != request.expected_head_sha
            or state.base_sha != request.base_sha
            or state.target_branch != request.target_branch
        ):
            raise errors.ResumeAuthorizationChanged("persisted scope identity differs from the request")
        required = state.phase != "CREATED"
        for label, persisted, live in (
            ("manifest", state.manifest_fingerprint, self.manifest.fingerprint()),
            ("request", state.request_fingerprint, request.fingerprint(approval)),
        ):
            if persisted is None:
                if required:
                    raise errors.ResumeAuthorizationChanged(f"{label} fingerprint missing on a past-CREATED resume")
                continue
            if not isinstance(persisted, str) or persisted != live:
                raise errors.ResumeAuthorizationChanged(f"{label} fingerprint changed since authorization")
        self.manifest.assert_action_allowed("observe_pr")

    def _load_or_init(self, request: EvidenceRequest) -> ReviewRunState:
        if self.store.exists():
            state = self.store.load()  # raises on tamper/corruption
            self._loaded_state = state
            self.logger.emit("resume", phase=state.phase, scope_id=state.scope_id)
            if state.is_terminal_stopped():
                raise errors.ResumeOfStoppedWork(
                    f"run for {state.scope_id} is STOPPED ({state.stop_reason}); re-authorization required"
                )
            approval = self._authorize(request)
            self._verify_resume(state, request, approval)
            self.governor = restore_governor(
                self.config.budgets,
                state.usage,
                now=self._injected_governor.now if self._injected_governor else None,
                require_complete=True,
            )
            return state
        self._authorize(request)
        self.governor = self._injected_governor or BudgetGovernor(budgets=self.config.budgets)
        state = ReviewRunState(
            scope_id=request.scope_id,
            repository=request.repository,
            pr_number=request.pr_number,
            head_sha=request.expected_head_sha,
            base_sha=request.base_sha,
            target_branch=request.target_branch,
        )
        self._persist(state)
        return state

    # --- approval boundary (G1.6-B) -----------------------------------------

    def _verify_boundary(self) -> None:
        guard = self.approval_guard
        try:
            if getattr(guard, "offline_only", False):
                if not isinstance(self.observer, FixtureGitHubObserver) or not getattr(
                    self.reviewer, "is_offline_mock", False
                ):
                    raise errors.ApprovalBoundaryViolation(
                        "the offline-fixture approval guard may only be used with "
                        "fixture observers and mock reviewer transports"
                    )
            if not getattr(guard, "offline_only", False):
                # Only the built-in production guard may claim ENFORCED: it reads
                # the genuine process token and cannot be handed mocked data.
                if type(guard) is not ProductionApprovalGuard:
                    raise errors.ApprovalBoundaryViolation(
                        "only the built-in production approval guard can attest an enforced boundary"
                    )
                snap = self.approved_snapshot
                if snap is None:
                    raise errors.ApprovalBoundaryUnverifiable(
                        "an enforced run requires the approval file to be read through a pinned snapshot"
                    )
                if self.manifest.source_sha256 is None or self.manifest.source_sha256 != snap.sha256:
                    raise errors.ApprovalBoundaryViolation(
                        "the loaded manifest is not the pinned approval file that was verified"
                    )
                snap.revalidate()  # same bytes, same file identity, path still names it
            report = guard.verify(self.manifest.source_path, self.config.approvals_dir)
            if not isinstance(report, BoundaryReport):
                raise errors.ApprovalBoundaryUnverifiable("approval guard returned no report")
            if not report.enforced and not getattr(guard, "offline_only", False):
                raise errors.ApprovalBoundaryUnverifiable("non-offline guard did not enforce the boundary")
        except errors.OrchestratorStop as stop:
            self.logger.emit("approval_boundary_refused", reason=stop.reason_code, detail=stop.detail)
            raise
        self.boundary_report = report
        self.logger.emit("approval_boundary", **report.to_dict())

    # --- public entry -----------------------------------------------------

    def run(self, request: EvidenceRequest) -> None:
        """Run (or resume). Always ends by raising: ``MilestoneOwnerStop`` is the
        successful terminal state; any other ``OrchestratorStop`` is a fail-closed halt."""

        # G1.6-B: the OS approval boundary is proven BEFORE the lock, authorization,
        # checkpoint load, observer call or provider call. A failure here performs
        # no external operation and writes no run state.
        self._verify_boundary()

        with RunLock(self.config.runtime_dir / "a2a.lock"):
            state: ReviewRunState | None = None
            try:
                state = self._load_or_init(request)
                self.state = state
                self.governor.start()
                self._drive(state, request)
            except errors.MilestoneOwnerStop as gate:
                if state is not None:
                    state.stop_reason = gate.reason_code
                    self._persist(state)
                self.logger.emit("owner_gate", reason=gate.reason_code)
                raise
            except errors.OrchestratorStop as stop:
                if state is not None:
                    if not state.is_terminal_stopped():
                        state.mark_stopped(stop.reason_code)
                        self._persist(state)
                elif self._loaded_state is not None and not self._loaded_state.is_terminal_stopped():
                    # Stop during resume authorization: keep the persisted usage evidence.
                    self._loaded_state.mark_stopped(stop.reason_code)
                    self.store.save(self._loaded_state)  # type: ignore[arg-type]
                self.logger.emit("stop", reason=stop.reason_code, detail=stop.detail)
                raise

    def run_to_gate(self, request: EvidenceRequest) -> dict[str, Any]:
        """Convenience: run and return the summary when the owner gate is reached."""

        try:
            self.run(request)
        except errors.MilestoneOwnerStop:
            return self.summary()
        raise errors.OrchestratorStop("run ended without reaching the owner gate")  # pragma: no cover

    # --- state machine ----------------------------------------------------

    def _drive(self, state: ReviewRunState, request: EvidenceRequest) -> None:
        approval = self._approval
        assert approval is not None

        if state.phase == "OWNER_STOP":
            raise errors.MilestoneOwnerStop(
                f"review of PR #{state.pr_number} already complete; owner gate stands"
            )

        if state.phase == "CREATED":
            state.manifest_fingerprint = self.manifest.fingerprint()
            state.request_fingerprint = request.fingerprint(approval)
            self.logger.emit("authorized", scope_id=state.scope_id, pr_number=state.pr_number)
            self.packet = self._collect(request, approval)
            state.packet_fingerprint = self.packet["fingerprint"]
            state.advance_to("OBSERVED")
            self._persist(state)
            state.advance_to("PACKETED")
            self._write_packet()
            self._persist(state)
        else:
            self.packet = self._collect(request, approval)
            if self.packet["fingerprint"] != state.packet_fingerprint:
                raise errors.EvidenceInvalid(
                    "evidence changed since this run began; a fresh authorized run is required"
                )
            if state.phase == "OBSERVED":
                state.advance_to("PACKETED")
                self._persist(state)

        if state.phase == "PACKETED":
            self._review(state)
            state.advance_to("REVIEWED")
            self._persist(state)

        if state.phase == "REVIEWED":
            state.advance_to("OWNER_STOP")
            self._persist(state)
            self.logger.emit("review_complete", scope_id=state.scope_id)
            raise errors.MilestoneOwnerStop(
                f"advisory review of PR #{state.pr_number} complete; fresh owner decision required"
            )

        raise errors.OrchestratorStop(f"unexpected phase fallthrough: {state.phase}")

    # --- observation ------------------------------------------------------

    def _collect(self, request: EvidenceRequest, approval: ApprovedPullRequest) -> dict[str, Any]:
        repo = request.repository
        pr = self.observer.get_pull_request(repo, request.pr_number)
        self._check_pr(pr, request, approval)

        runs = self.observer.get_workflow_runs(repo, pr.head_sha)
        backend = self._pick_job(runs, pr.head_sha, BACKEND_JOB_NAME)
        if backend is None:
            raise errors.EvidenceIncomplete("no backend CI job exists for the approved head")
        if backend[1].status != "completed":
            raise errors.EvidenceIncomplete("the backend CI job has not completed")
        backend_log = self.observer.get_job_log(repo, backend[1].job_id, max_bytes=evidence.MAX_LOG_BYTES)

        web_log: str | None = None
        web = self._pick_job(runs, pr.head_sha, WEB_JOB_NAME)
        if web is not None and web[1].status == "completed":
            web_log = self.observer.get_job_log(repo, web[1].job_id, max_bytes=evidence.MAX_LOG_BYTES)

        # Time-of-check/time-of-use: the head must not have moved while we read.
        again = self.observer.get_pull_request(repo, request.pr_number)
        if again.head_sha != pr.head_sha:
            raise errors.ObservedHeadChanged("the PR head moved while evidence was being collected")

        packet = evidence.build_packet(
            pr=pr,
            approval=approval,
            runs=runs,
            backend=backend,
            backend_log=backend_log,
            web_log=web_log,
            baseline_ids=self.baseline_ids,
            observer_name=self.observer_name,
        )
        self.logger.emit(
            "evidence_collected",
            pr_number=pr.number,
            head_sha=pr.head_sha,
            fingerprint=packet["fingerprint"],
            counts=packet["comparison"]["counts"],
        )
        return packet

    def _check_pr(self, pr: PullRequestObservation, request: EvidenceRequest, approval: ApprovedPullRequest) -> None:
        if pr.repository != self.manifest.repository or pr.number != request.pr_number:
            raise errors.ScopeMismatch("observed PR is not the authorized repository/number")
        if pr.head_sha != approval.head_sha:
            raise errors.ObservedHeadChanged("observed head differs from the owner-approved head")
        if pr.base_sha != self.manifest.base_sha:
            raise errors.ShaMismatch("observed PR base differs from the authorized base SHA")
        if pr.head_ref != self.manifest.target_branch:
            raise errors.UnknownBranch("observed PR head branch is not the authorized branch")
        if pr.state != "OPEN":
            raise errors.PullRequestStateUnexpected(f"PR is {pr.state}, not OPEN")
        # Scope enforcement on the OBSERVED content, independent of any verdict.
        self.manifest.assert_paths_allowed(list(pr.files))

    @staticmethod
    def _pick_job(
        runs: Sequence[WorkflowRunObservation], head_sha: str, name: str
    ) -> tuple[WorkflowRunObservation, JobObservation] | None:
        found = [
            (run, job)
            for run in runs
            if run.head_sha == head_sha
            for job in run.jobs
            if job.name == name
        ]
        if not found:
            return None
        found.sort(key=lambda rj: rj[0].run_id)
        return found[-1]  # latest attempt for this head

    def _write_packet(self) -> None:
        if self.packet is not None:
            atomic_write_json(self.config.runtime_dir / "a2a_packet.json", self.packet)

    # --- review -----------------------------------------------------------

    def _review(self, state: ReviewRunState) -> None:
        assert self.packet is not None
        call = state.call
        if call is not None:
            if call.get("status") == "completed" and isinstance(call.get("result"), dict):
                self._enforce_advisory_only(call["result"])
                return
            raise errors.ReviewCallUncertain(
                "a previous review call is pending or unresolved; it may have been billed"
            )
        request_sha = evidence.sha256_hex(evidence.canonical_json(self.reviewer.build_request(self.packet)))
        state.call = {"status": "pending", "request_sha256": request_sha, "attempts": 0}
        self._persist(state)  # durable BEFORE the external call
        review = self.reviewer.review_evidence(
            self.packet,
            governor=self.governor,
            checkpoint=lambda: self._persist(state),
        )
        result = review.to_dict()
        state.call = {
            "status": "completed",
            "request_sha256": review.request_sha256,
            "attempts": review.attempts,
            "result": result,
        }
        self._persist(state)
        self._enforce_advisory_only(result)

    @staticmethod
    def _enforce_advisory_only(result: dict[str, Any]) -> None:
        for finding in result.get("findings", ()):
            if finding.get("category") == "scope_widening_request":
                raise errors.UnauthorizedOperation(
                    "the reviewer asked for a wider scope; ignored, and the run is stopped"
                )

    # --- reporting --------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        state = self.state
        if state is None:
            state = self.store.load()  # type: ignore[assignment]
        call = state.call or {}
        return {
            "phase": state.phase,
            "owner_gate_required": True,
            "approval_boundary": self.boundary_report.to_dict() if self.boundary_report else None,
            "pull_request": {"repository": state.repository, "number": state.pr_number, "head_sha": state.head_sha},
            "packet_fingerprint": state.packet_fingerprint,
            "comparison_counts": (self.packet or {}).get("comparison", {}).get("counts"),
            "advisory_review": call.get("result"),
            "usage": {
                "usage_units": state.usage.get("tokens_used"),
                "cost_used_usd": state.usage.get("cost_used_usd"),
                "elapsed_seconds": state.usage.get("elapsed_seconds"),
            },
        }
