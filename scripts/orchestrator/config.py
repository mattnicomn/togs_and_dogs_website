"""Orchestrator configuration: budgets, runtime paths, and the trust boundary.

The single most important thing in this file is the *approval trust boundary*.
Authorization manifests must come from an owner-controlled location that the
AI agents cannot write to. In A1 we model this with two separate roots:

  * ``runtime_dir`` (``.orchestrator/``) — agent-writable scratch: state,
    checkpoints, logs. NOTHING here is ever trusted as authorization.
  * ``approvals_dir`` — the owner-controlled manifest source. By default it is
    taken from the ``PETCARE_ORCH_APPROVALS_DIR`` environment variable so it
    can be pointed at a path outside the repository (and outside any
    agent-writable tree). If unset, it falls back to a path that is validated
    at use time to ensure it is NOT inside the runtime/agent-writable tree.

This separation is what makes "an AI-generated file can never be authorization"
true in code: :mod:`manifest` refuses to load a manifest that resolves to a
path inside ``runtime_dir`` (or any configured agent-writable root).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import errors

# Environment variable the owner sets to point at their controlled approval
# directory (ideally outside the repository entirely).
ENV_APPROVALS_DIR = "PETCARE_ORCH_APPROVALS_DIR"
ENV_RUNTIME_DIR = "PETCARE_ORCH_RUNTIME_DIR"

# Finding 1 (owner approval trust): the approvals source must be an explicitly
# configured owner-controlled location. The orchestrator must NEVER silently
# default it to a path under the repository or any agent-writable directory,
# because such a default would let an AI-authored file masquerade as owner
# authorization. ``load_config`` therefore refuses to invent an approvals dir;
# the caller must pass one (A1 tests pass an explicit temp dir; a future A2
# deployment points it at an OS-permission-protected owner directory).


@dataclass(frozen=True)
class Budgets:
    """Hard ceilings. Any breach raises ``BudgetExhausted`` and stops the run.

    Token/cost budgets are modeled even though A1 is mocked: the mock adapters
    report synthetic usage so the governor logic is exercised end to end.
    """

    max_correction_retries: int = 2  # corrective iterations after first review
    max_review_rejections: int = 2   # reviewer rejections tolerated before stop
    max_tokens: int = 100_000        # synthetic token ceiling across a task
    max_cost_usd: float = 1.00       # synthetic cost ceiling across a task
    max_wall_clock_seconds: float = 300.0  # per-task wall-clock ceiling

    def __post_init__(self) -> None:  # pragma: no cover - trivial guards
        for name in (
            "max_correction_retries",
            "max_review_rejections",
            "max_tokens",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0")
        if self.max_cost_usd < 0:
            raise ValueError("max_cost_usd must be >= 0")
        if self.max_wall_clock_seconds <= 0:
            raise ValueError("max_wall_clock_seconds must be > 0")


@dataclass(frozen=True)
class Config:
    """Resolved runtime configuration for a single orchestrator invocation."""

    runtime_dir: Path
    approvals_dir: Path
    budgets: Budgets = field(default_factory=Budgets)
    # Default list of agent-writable roots that may NEVER be an approval source.
    # runtime_dir is always treated as untrusted; extra roots can be added.
    extra_untrusted_roots: tuple[Path, ...] = ()

    @property
    def state_path(self) -> Path:
        return self.runtime_dir / "state.json"

    @property
    def checkpoint_path(self) -> Path:
        return self.runtime_dir / "checkpoint.json"

    @property
    def log_path(self) -> Path:
        return self.runtime_dir / "events.log"

    @property
    def untrusted_roots(self) -> tuple[Path, ...]:
        """All roots from which an approval manifest must NOT be loaded."""

        roots = [self.runtime_dir, *self.extra_untrusted_roots]
        return tuple(_resolve(r) for r in roots)

    def with_budgets(self, budgets: Budgets) -> "Config":
        return replace(self, budgets=budgets)


def _resolve(path: Path | str) -> Path:
    """Resolve to an absolute path without requiring the path to exist."""

    return Path(path).expanduser().resolve()


def load_config(
    *,
    runtime_dir: Path | str | None = None,
    approvals_dir: Path | str | None = None,
    budgets: Budgets | None = None,
    require_approvals: bool = True,
) -> Config:
    """Build a :class:`Config`, honoring environment overrides.

    Precedence for the approvals source: explicit argument > environment
    variable (``PETCARE_ORCH_APPROVALS_DIR``). There is deliberately **no
    default** — an unset approvals source raises
    :class:`errors.ApprovalSourceNotConfigured` (Finding 1). This prevents the
    approval source from silently resolving to a path under the repository or
    any agent-writable directory.

    ``require_approvals=False`` is only for commands that read local state and
    never load a manifest (e.g. ``status``); in that case a non-authoritative
    placeholder approvals path is used and must never be trusted for approval.

    The runtime dir still has a safe default (it is explicitly agent-writable
    and never a trust anchor). No directories are created here; the approvals
    dir is NEVER created by the orchestrator — it belongs to the owner.
    """

    rt = runtime_dir or os.environ.get(ENV_RUNTIME_DIR) or Path.cwd() / ".orchestrator"

    ap_raw = approvals_dir or os.environ.get(ENV_APPROVALS_DIR)
    if ap_raw is None:
        if require_approvals:
            raise errors.ApprovalSourceNotConfigured(
                "no owner-controlled approvals source configured; set "
                f"{ENV_APPROVALS_DIR} or pass approvals_dir explicitly "
                "(the orchestrator refuses to default it under the repo)"
            )
        # Non-authoritative placeholder for manifest-free commands only.
        ap_raw = _resolve(rt) / "_UNCONFIGURED_APPROVALS_DO_NOT_TRUST"

    return Config(
        runtime_dir=_resolve(rt),
        approvals_dir=_resolve(ap_raw),
        budgets=budgets or Budgets(),
    )
