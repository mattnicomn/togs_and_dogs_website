"""Adapter protocols and shared data structures.

These define the boundary the orchestrator loop talks to. A1 ships only mock
implementations; A2 would add live implementations with the SAME signatures,
so the loop code never changes when the transport becomes real.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Task:
    """A unit of work dispatched to the implementation agent."""

    scope_id: str
    description: str
    # Repo-relative paths the task is expected to touch (checked vs manifest).
    target_paths: tuple[str, ...]
    # Opaque acceptance tag the acceptance engine keys on (e.g. "needs_marker").
    acceptance_key: str


@dataclass(frozen=True)
class Usage:
    """Synthetic usage reported by an adapter for budget accounting."""

    tokens: int = 0
    cost_usd: float = 0.0


@dataclass(frozen=True)
class ImplementationResult:
    """What the (mock) implementation agent produced for a task/iteration."""

    # Repo-relative paths the agent claims it changed.
    changed_paths: tuple[str, ...]
    # Synthetic unified-diff-ish text (never real repo content in A1).
    diff_text: str
    # Markers the acceptance engine inspects (mock proxy for "did it do X").
    markers: frozenset[str] = frozenset()
    usage: Usage = field(default_factory=Usage)
    # Iteration index this result belongs to (0 = first attempt).
    iteration: int = 0


@dataclass(frozen=True)
class ReviewFinding:
    """One structured reviewer finding."""

    severity: str  # "high" | "medium" | "low" | "info"
    message: str


@dataclass(frozen=True)
class ReviewResult:
    """Independent reviewer verdict for an implementation result."""

    verdict: str  # "ACCEPT" | "REJECT"
    findings: tuple[ReviewFinding, ...] = ()
    usage: Usage = field(default_factory=Usage)

    @property
    def accepted(self) -> bool:
        return self.verdict == "ACCEPT"


@dataclass(frozen=True)
class DraftPRResult:
    """What the (mock) GitHub adapter returns for a Draft-PR request."""

    number: int
    url: str
    is_draft: bool
    is_open: bool
    is_merged: bool
    base: str
    head: str


@runtime_checkable
class ImplementationAdapter(Protocol):
    """Implements a task, optionally given prior reviewer findings."""

    def implement(
        self, task: Task, prior_findings: tuple[ReviewFinding, ...] = ()
    ) -> ImplementationResult: ...


@runtime_checkable
class ReviewAdapter(Protocol):
    """Independently reviews an implementation result. Never an authority."""

    def review(self, task: Task, result: ImplementationResult) -> ReviewResult: ...


@runtime_checkable
class GitHubAdapter(Protocol):
    """Opens a Draft PR for an accepted result. Never merges, never deploys."""

    def open_draft_pr(
        self, *, base: str, head: str, title: str, body: str
    ) -> DraftPRResult: ...
