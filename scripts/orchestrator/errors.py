"""Typed stop/refusal errors for the orchestrator.

Every fail-closed condition raises one of these. They all carry a stable
``reason_code`` so that logs, reports, and tests can assert on an exact machine
code rather than a human string.

Design rule: the orchestrator NEVER swallows one of these to "keep going". A
raised ``OrchestratorStop`` always ends the current run and is recorded.
"""

from __future__ import annotations


class OrchestratorStop(Exception):
    """Base class for every fail-closed halt.

    ``reason_code`` is a stable, screaming-snake identifier used by reports,
    logs, and tests. ``detail`` is a human-readable, already-sanitized string
    (callers must not place secrets/PII in it).
    """

    reason_code: str = "ORCHESTRATOR_STOP"

    def __init__(self, detail: str = "") -> None:
        self.detail = detail
        super().__init__(f"{self.reason_code}: {detail}" if detail else self.reason_code)


# --- Authorization / manifest failures -------------------------------------


class ApprovalMissing(OrchestratorStop):
    """No approval manifest was provided for the requested scope."""

    reason_code = "APPROVAL_MISSING"


class ApprovalInvalid(OrchestratorStop):
    """The manifest exists but is malformed, incomplete, or ambiguous."""

    reason_code = "APPROVAL_INVALID"


class ApprovalUntrustedSource(OrchestratorStop):
    """The manifest resolved to an agent-writable (untrusted) location.

    Also raised when a symlink (or any path component) escapes into an
    untrusted tree after full real-path resolution.
    """

    reason_code = "APPROVAL_UNTRUSTED_SOURCE"


class ApprovalSourceNotConfigured(OrchestratorStop):
    """No owner-controlled approval source was explicitly configured.

    The orchestrator refuses to invent a default approvals directory (doing so
    could place the approval source under the repo or an agent-writable path).
    An explicit, owner-controlled source must be configured.
    """

    reason_code = "APPROVAL_SOURCE_NOT_CONFIGURED"


class ResumeAuthorizationChanged(OrchestratorStop):
    """On resume, the persisted authorization no longer matches the manifest
    and request (identity, scope, SHA, branch, path scope, or actions)."""

    reason_code = "RESUME_AUTHORIZATION_CHANGED"


class ResumeOfStoppedWork(OrchestratorStop):
    """A resume was attempted against a run already in a terminal STOPPED
    state. Stopped work is never silently resumed."""

    reason_code = "RESUME_OF_STOPPED_WORK"


class SideEffectReconciliationFailed(OrchestratorStop):
    """A side effect was left in an uncertain (pending) state and could not be
    reconciled against the external adapter, so the run halts rather than
    risk a duplicate."""

    reason_code = "SIDE_EFFECT_RECONCILIATION_FAILED"


class OperationRecordInvalid(OrchestratorStop):
    """A persisted pending/completed operation record is malformed, or its
    idempotency key does not match the key derived from the authorized
    identity. Fail-closed before any reconciliation/lookup/side effect."""

    reason_code = "OPERATION_RECORD_INVALID"


class ReconciledResultIncompatible(OrchestratorStop):
    """A reconciled/rehydrated external result does not match the authorized
    base/head or the required draft/open/unmerged semantics, so it is not
    adopted (fail-closed)."""

    reason_code = "RECONCILED_RESULT_INCOMPATIBLE"


class BudgetSnapshotInvalid(OrchestratorStop):
    """A restored budget snapshot is malformed or already over budget."""

    reason_code = "BUDGET_SNAPSHOT_INVALID"


class ScopeMismatch(OrchestratorStop):
    """Task id / repository / branch does not match the authorized manifest."""

    reason_code = "SCOPE_MISMATCH"


class ShaMismatch(OrchestratorStop):
    """The base SHA does not match the authorized manifest SHA."""

    reason_code = "SHA_MISMATCH"


class UnknownBranch(OrchestratorStop):
    """The target/base branch is not the authorized branch."""

    reason_code = "UNKNOWN_BRANCH"


# --- Execution / scope-of-change failures ----------------------------------


class UnauthorizedPath(OrchestratorStop):
    """A produced change touches a path outside the authorized allowlist."""

    reason_code = "UNAUTHORIZED_PATH"


class UnauthorizedOperation(OrchestratorStop):
    """An agent attempted an operation outside the authorized action set."""

    reason_code = "UNAUTHORIZED_OPERATION"


# --- Budget failures --------------------------------------------------------


class BudgetExhausted(OrchestratorStop):
    """A retry / token / cost / time budget was exhausted."""

    reason_code = "BUDGET_EXHAUSTED"


class ReviewFailuresExhausted(OrchestratorStop):
    """The reviewer rejected the work more times than the retry budget allows."""

    reason_code = "REVIEW_FAILURES_EXHAUSTED"


# --- Checkpoint / idempotency failures -------------------------------------


class CheckpointTampered(OrchestratorStop):
    """The checkpoint integrity digest does not match its contents."""

    reason_code = "CHECKPOINT_TAMPERED"


class CheckpointCorrupt(OrchestratorStop):
    """The checkpoint file could not be parsed as a valid checkpoint."""

    reason_code = "CHECKPOINT_CORRUPT"


# --- Mandatory gate ---------------------------------------------------------


class MilestoneOwnerStop(OrchestratorStop):
    """A milestone completed; the mandatory owner gate halts the run.

    This is a *success* terminal state, not an error, but it is modeled as a
    stop because it must unconditionally halt execution and require a fresh,
    separate owner approval before any further scope runs.
    """

    reason_code = "MILESTONE_OWNER_STOP"
