"""Mock OpenAI independent-reviewer adapter (A1 — fully offline).

NO OpenAI SDK import, NO API key read, NO network. The adapter replays scripted
verdicts from a synthetic JSON fixture so the orchestrator's reject -> correct
-> accept loop is exercised deterministically.

The reviewer is an INDEPENDENT checker, never an authority: its ACCEPT verdict
lets the loop proceed to the Draft-PR step, but it can never authorize a merge
or a deployment (those are separate, owner-gated, and not part of A1 at all).

Interface for A2:
    A live adapter would send the diff + acceptance criteria to the OpenAI API
    (key from the environment at call time only, never logged), cost-capped by
    the budget governor, and parse the structured JSON response into a
    :class:`ReviewResult`. Signature is identical to this mock.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import ImplementationResult, ReviewFinding, ReviewResult, Task, Usage


@dataclass
class MockOpenAIReviewer:
    """Replays scripted review verdicts from a synthetic JSON fixture.

    Fixture format: a JSON object with a ``reviews`` list, one entry per review
    call in order::

        {"reviews": [
           {"verdict": "REJECT",
            "findings": [{"severity": "high", "message": "missing marker"}],
            "usage": {"tokens": 800, "cost_usd": 0.0}},
           {"verdict": "ACCEPT", "findings": [], "usage": {"tokens": 600}}
        ]}

    If calls exceed the scripted list, a deterministic ACCEPT with zero usage
    is returned only when ``default_accept`` is True; otherwise it raises.
    """

    fixture_path: Path
    default_accept: bool = False
    _reviews: list[dict[str, Any]] | None = None
    _calls: int = 0

    def _load(self) -> list[dict[str, Any]]:
        if self._reviews is None:
            raw = json.loads(Path(self.fixture_path).read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or not isinstance(raw.get("reviews"), list):
                raise ValueError("openai fixture must be {'reviews': [...]}")
            self._reviews = list(raw["reviews"])
        return self._reviews

    def review(self, task: Task, result: ImplementationResult) -> ReviewResult:
        reviews = self._load()
        idx = self._calls
        self._calls += 1
        if idx >= len(reviews):
            if self.default_accept:
                return ReviewResult(verdict="ACCEPT")
            raise IndexError(
                f"mock openai fixture {self.fixture_path} has no review {idx}"
            )
        return _row_to_review(reviews[idx])


def _row_to_review(row: dict[str, Any]) -> ReviewResult:
    verdict = str(row.get("verdict", "")).upper()
    if verdict not in ("ACCEPT", "REJECT"):
        raise ValueError(f"review verdict must be ACCEPT or REJECT, got {verdict!r}")
    findings = tuple(
        ReviewFinding(
            severity=str(f.get("severity", "info")),
            message=str(f.get("message", "")),
        )
        for f in row.get("findings", [])
    )
    usage_raw = row.get("usage", {}) or {}
    usage = Usage(
        tokens=int(usage_raw.get("tokens", 0)),
        cost_usd=float(usage_raw.get("cost_usd", 0.0)),
    )
    return ReviewResult(verdict=verdict, findings=findings, usage=usage)
