"""Deterministic task acceptance criteria.

Acceptance is a pure function of the implementation result, the reviewer
verdict, and the manifest scope. It has no I/O and no randomness, so a given
(result, review, manifest) always yields the same decision.

A task is ACCEPTED only when ALL hold:
  1. The reviewer verdict is ACCEPT.
  2. Every path the implementation claims to have changed is inside the
     manifest's allowed-path allowlist.
  3. The implementation result carries the task's required acceptance marker.

Any failure returns a structured, non-accepting :class:`AcceptanceDecision`
with a reason; the loop decides whether that means "correct and retry" or
"stop", but acceptance itself never raises.
"""

from __future__ import annotations

from dataclasses import dataclass

from .adapters.base import ImplementationResult, ReviewResult, Task
from .manifest import ApprovalManifest


@dataclass(frozen=True)
class AcceptanceDecision:
    accepted: bool
    reason_code: str
    detail: str = ""


def evaluate(
    task: Task,
    result: ImplementationResult,
    review: ReviewResult,
    manifest: ApprovalManifest,
) -> AcceptanceDecision:
    """Return the deterministic acceptance decision for one iteration."""

    if not review.accepted:
        return AcceptanceDecision(
            accepted=False,
            reason_code="REVIEW_REJECTED",
            detail=f"{len(review.findings)} finding(s)",
        )

    # Even on an ACCEPT verdict, the orchestrator independently enforces scope:
    # the reviewer's opinion never overrides the path allowlist.
    outside = [p for p in result.changed_paths if not manifest.path_allowed(p)]
    if outside:
        return AcceptanceDecision(
            accepted=False,
            reason_code="CHANGED_PATH_OUTSIDE_SCOPE",
            detail=f"{outside[0]}",
        )

    if task.acceptance_key and task.acceptance_key not in result.markers:
        return AcceptanceDecision(
            accepted=False,
            reason_code="ACCEPTANCE_MARKER_MISSING",
            detail=task.acceptance_key,
        )

    return AcceptanceDecision(accepted=True, reason_code="ACCEPTED")
