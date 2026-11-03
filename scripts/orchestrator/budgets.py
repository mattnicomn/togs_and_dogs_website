"""Budget governor: retries, tokens, cost, and wall-clock ceilings.

The governor accumulates synthetic usage reported by the (mock) adapters and
raises :class:`errors.BudgetExhausted` the moment any ceiling is crossed. It is
deliberately simple and has no I/O, so it is trivially testable and
deterministic. Wall-clock uses an injectable clock for determinism in tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from . import errors
from .config import Budgets


@dataclass
class BudgetGovernor:
    """Tracks cumulative usage for a single task run against :class:`Budgets`."""

    budgets: Budgets
    now: Callable[[], float] = field(default=None)  # type: ignore[assignment]
    tokens_used: int = 0
    cost_used_usd: float = 0.0
    corrections_used: int = 0
    rejections_seen: int = 0
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

    def check_time(self) -> None:
        if self._start is None:
            return
        elapsed = self.now() - self._start
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
        """A sanitized, serializable view of usage for reports/checkpoints."""

        return {
            "tokens_used": self.tokens_used,
            "cost_used_usd": round(self.cost_used_usd, 6),
            "corrections_used": self.corrections_used,
            "rejections_seen": self.rejections_seen,
        }
