"""Mock Kiro implementation adapter (A1 — fully offline).

This adapter does NOT run ``kiro-cli``. It replays clearly-labeled SYNTHETIC
JSONL fixtures that stand in for a future headless run. The fixture line shape
is the orchestrator's OWN synthetic contract, NOT a verified live Kiro ACP
event schema — see the ``_synthetic`` flag on every parsed line and the
module-level warning constant.

Interface for A2:
    A live adapter would invoke, roughly::

        kiro-cli chat <prompt> --no-interactive \
            --output-format stream-json \
            --trust-tools=fs_read,fs_write \
            --agent <scoped-profile>

    capture the JSON-Lines on stdout, and map the terminal event(s) into an
    :class:`ImplementationResult`. The mapping function :func:`events_to_result`
    is written against the synthetic schema so the A2 work is "point it at real
    stdout and adjust the field names once the live schema is confirmed".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .base import ImplementationResult, ReviewFinding, Task, Usage

# Loud, explicit disclaimer carried in code so no reader mistakes the fixtures
# for a verified live schema.
SYNTHETIC_SCHEMA_WARNING = (
    "A1 SYNTHETIC FIXTURE: this JSONL shape is the orchestrator's own mock "
    "contract, NOT a verified live kiro-cli ACP event schema."
)


@dataclass
class MockKiroAdapter:
    """Replays per-iteration synthetic results from a JSONL fixture file.

    Fixture format: one JSON object per line. Each object represents the
    terminal outcome of one synthetic implementation iteration::

        {"_synthetic": true, "iteration": 0,
         "changed_paths": ["scripts/orchestrator/example.py"],
         "diff_text": "+ added marker",
         "markers": ["needs_marker"],
         "usage": {"tokens": 1200, "cost_usd": 0.0},
         "responds_to_findings": false}

    The adapter returns the line whose ``iteration`` matches the call index:
    first ``implement`` call -> iteration 0, the next -> iteration 1, etc. This
    lets a fixture script a "bad first attempt, good correction" sequence.
    """

    fixture_path: Path
    _lines: list[dict[str, Any]] | None = None
    _calls: int = 0

    def _load(self) -> list[dict[str, Any]]:
        if self._lines is None:
            self._lines = list(load_jsonl(self.fixture_path))
        return self._lines

    def implement(
        self, task: Task, prior_findings: tuple[ReviewFinding, ...] = ()
    ) -> ImplementationResult:
        lines = self._load()
        idx = self._calls
        self._calls += 1
        if idx >= len(lines):
            # Deterministic fallback: no further scripted iterations.
            raise IndexError(
                f"mock kiro fixture {self.fixture_path} has no iteration {idx}"
            )
        return events_to_result(lines[idx], default_iteration=idx)


def load_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    """Parse a synthetic JSONL fixture into dict rows (skips blank lines)."""

    text = Path(path).read_text(encoding="utf-8")
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError(f"fixture line is not a JSON object: {raw!r}")
        yield obj


def events_to_result(row: dict[str, Any], *, default_iteration: int = 0) -> ImplementationResult:
    """Map one synthetic JSONL row into an :class:`ImplementationResult`.

    This is the function A2 would adapt to the confirmed live schema. It is
    intentionally tolerant of missing optional fields and strict about types.
    """

    changed = tuple(str(p) for p in row.get("changed_paths", []))
    markers = frozenset(str(m) for m in row.get("markers", []))
    usage_raw = row.get("usage", {}) or {}
    usage = Usage(
        tokens=int(usage_raw.get("tokens", 0)),
        cost_usd=float(usage_raw.get("cost_usd", 0.0)),
    )
    return ImplementationResult(
        changed_paths=changed,
        diff_text=str(row.get("diff_text", "")),
        markers=markers,
        usage=usage,
        iteration=int(row.get("iteration", default_iteration)),
    )
