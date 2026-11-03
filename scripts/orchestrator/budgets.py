"""Budget governor: retries, tokens, cost, and wall-clock ceilings.

The governor accumulates synthetic usage reported by the (mock) adapters and
raises :class:`errors.BudgetExhausted` the moment any ceiling is crossed. It is
deliberately simple and has no I/O, so it is trivially testable and
deterministic. Wall-clock uses an injectable clock for determinism in tests.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

from . import errors
from .config import Budgets


@dataclass
class BudgetGovernor:
    """Tracks cumulative usage for a single task run against :class:`Budgets`.

    Finding 4 (cumulative budget recovery): cumulative counters and elapsed
    time survive a restart. ``snapshot()`` serializes them and
    :func:`restore_governor` rebuilds a governor so a resumed run continues to
    spend against the SAME budgets rather than starting fresh.
    """

    budgets: Budgets
    now: Callable[[], float] = field(default=None)  # type: ignore[assignment]
    tokens_used: int = 0
    cost_used_usd: float = 0.0
    corrections_used: int = 0
    rejections_seen: int = 0
    # Elapsed seconds carried over from prior run segments (Finding 4).
    prior_elapsed_seconds: float = 0.0
    _start: float | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.now is None:
            import time

            self.now = time.monotonic

    def start(self) -> None:
        self._start = self.now()

    # --- usage accounting --------------------------------------------------

    def add_usage(self, *, tokens: int = 0, cost_usd: float = 0.0) -> None:
        """Add reported usage and enforce token/cost/time ceilings."""

        self.tokens_used += max(0, int(tokens))
        self.cost_used_usd += max(0.0, float(cost_usd))
        self._check_tokens_cost_time()

    def record_correction(self) -> None:
        """Count one corrective iteration; stop if over the retry budget."""

        self.corrections_used += 1
        if self.corrections_used > self.budgets.max_correction_retries:
            raise errors.BudgetExhausted(
                f"corrections {self.corrections_used} > "
                f"max {self.budgets.max_correction_retries}"
            )

    def record_rejection(self) -> None:
        """Count one reviewer rejection; stop if over the rejection budget."""

        self.rejections_seen += 1
        if self.rejections_seen > self.budgets.max_review_rejections:
            raise errors.ReviewFailuresExhausted(
                f"rejections {self.rejections_seen} > "
                f"max {self.budgets.max_review_rejections}"
            )

    # --- ceiling checks ----------------------------------------------------

    def elapsed_seconds(self) -> float:
        """Total elapsed = prior carried-over segments + this segment.

        ELAPSED SEMANTICS (documented per F4): this is **active run time** — the
        sum of wall-clock time spent while the orchestrator process is actually
        running the task, accumulated across restarts. It deliberately does NOT
        include the gap between a crash and the next restart (downtime while the
        process is not running is not counted). ``prior_elapsed_seconds`` is the
        active time recorded by earlier segments; this segment adds
        ``now() - _start`` since ``start()`` was called in the current process.
        """

        segment = 0.0 if self._start is None else (self.now() - self._start)
        return self.prior_elapsed_seconds + segment

    def check_time(self) -> None:
        elapsed = self.elapsed_seconds()
        if elapsed > self.budgets.max_wall_clock_seconds:
            raise errors.BudgetExhausted(
                f"wall-clock {elapsed:.3f}s > max {self.budgets.max_wall_clock_seconds}s"
            )

    def _check_tokens_cost_time(self) -> None:
        if self.tokens_used > self.budgets.max_tokens:
            raise errors.BudgetExhausted(
                f"tokens {self.tokens_used} > max {self.budgets.max_tokens}"
            )
        if self.cost_used_usd > self.budgets.max_cost_usd:
            raise errors.BudgetExhausted(
                f"cost ${self.cost_used_usd:.4f} > max ${self.budgets.max_cost_usd:.4f}"
            )
        self.check_time()

    def snapshot(self) -> dict[str, float | int]:
        """A sanitized, serializable view of usage for reports/checkpoints.

        Includes cumulative ``elapsed_seconds`` so a resumed run does not reset
        its wall-clock budget (Finding 4).
        """

        return {
            "tokens_used": self.tokens_used,
            "cost_used_usd": round(self.cost_used_usd, 6),
            "corrections_used": self.corrections_used,
            "rejections_seen": self.rejections_seen,
            "elapsed_seconds": round(self.elapsed_seconds(), 6),
        }


# --- Finding 4: cumulative budget recovery on resume -----------------------

_SNAPSHOT_INT_FIELDS = ("tokens_used", "corrections_used", "rejections_seen")
_SNAPSHOT_FLOAT_FIELDS = ("cost_used_usd", "elapsed_seconds")


_SNAPSHOT_ALL_FIELDS = _SNAPSHOT_INT_FIELDS + _SNAPSHOT_FLOAT_FIELDS


def restore_governor(
    budgets: Budgets,
    snapshot: dict[str, Any] | None,
    *,
    now: Callable[[], float] | None = None,
    require_complete: bool = False,
) -> BudgetGovernor:
    """Rebuild a :class:`BudgetGovernor` from a persisted snapshot.

    Validates the snapshot fail-closed (Finding 4 / F4):
      * ``require_complete=False`` (a genuinely fresh CREATED run): a ``None`` /
        empty snapshot yields a fresh zeroed governor.
      * ``require_complete=True`` (a RESUMED authorized run): the snapshot MUST
        be present and contain ALL cumulative fields, each nonempty and
        correctly typed. There are **no missing-field-defaults-to-zero** — a
        missing or empty snapshot on a resume is ``BudgetSnapshotInvalid``.
      * In both modes: NaN / infinity / bool-as-number / negative / wrong-typed
        values are rejected, and a snapshot already at/over any ceiling is
        rejected (a resumed run may not continue past an exhausted budget).

    The restored governor carries prior cumulative counters and **active** run
    time (see :meth:`BudgetGovernor.elapsed_seconds`) so ``start()`` only times
    the new segment; budgets are never reset.
    """

    if not snapshot:
        if require_complete:
            raise errors.BudgetSnapshotInvalid(
                "resumed authorized run requires a complete usage snapshot; got empty/missing"
            )
        return BudgetGovernor(budgets=budgets, now=now) if now else BudgetGovernor(budgets=budgets)

    if not isinstance(snapshot, dict):
        raise errors.BudgetSnapshotInvalid("snapshot is not an object")

    # When completeness is required, every field must be explicitly present.
    if require_complete:
        missing = [k for k in _SNAPSHOT_ALL_FIELDS if k not in snapshot]
        if missing:
            raise errors.BudgetSnapshotInvalid(
                f"resumed snapshot missing required field(s): {', '.join(missing)}"
            )

    values: dict[str, float] = {}
    for key in _SNAPSHOT_INT_FIELDS:
        raw = snapshot.get(key, 0)
        if not isinstance(raw, int) or isinstance(raw, bool) or raw < 0:
            raise errors.BudgetSnapshotInvalid(f"field {key} must be a non-negative int")
        values[key] = raw
    for key in _SNAPSHOT_FLOAT_FIELDS:
        raw = snapshot.get(key, 0.0)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise errors.BudgetSnapshotInvalid(f"field {key} must be a non-negative number")
        if math.isnan(raw) or math.isinf(raw):
            raise errors.BudgetSnapshotInvalid(f"field {key} must be finite (no NaN/infinity)")
        if raw < 0:
            raise errors.BudgetSnapshotInvalid(f"field {key} must be a non-negative number")
        values[key] = float(raw)

    # Reject a snapshot that is already at/over any ceiling.
    if values["tokens_used"] > budgets.max_tokens:
        raise errors.BudgetSnapshotInvalid("restored tokens already over budget")
    if values["cost_used_usd"] > budgets.max_cost_usd:
        raise errors.BudgetSnapshotInvalid("restored cost already over budget")
    if values["corrections_used"] > budgets.max_correction_retries:
        raise errors.BudgetSnapshotInvalid("restored corrections already over budget")
    if values["rejections_seen"] > budgets.max_review_rejections:
        raise errors.BudgetSnapshotInvalid("restored rejections already over budget")
    if values["elapsed_seconds"] > budgets.max_wall_clock_seconds:
        raise errors.BudgetSnapshotInvalid("restored elapsed time already over budget")

    kwargs: dict[str, Any] = dict(
        budgets=budgets,
        tokens_used=int(values["tokens_used"]),
        cost_used_usd=float(values["cost_used_usd"]),
        corrections_used=int(values["corrections_used"]),
        rejections_seen=int(values["rejections_seen"]),
        prior_elapsed_seconds=float(values["elapsed_seconds"]),
    )
    if now is not None:
        kwargs["now"] = now
    return BudgetGovernor(**kwargs)
