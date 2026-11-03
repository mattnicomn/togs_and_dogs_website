"""Durable task/milestone state machine with a side-effect ledger.

The state captures where a run is, what has already happened, and — critically
for idempotency — which irreversible side effects have ALREADY been performed,
so a restart never replays them.

Phases (a task advances strictly forward through these)::

    CREATED -> AUTHORIZED -> IMPLEMENTING -> REVIEWING
            -> (CORRECTING -> REVIEWING)*            # bounded loop
            -> ACCEPTED -> DRAFT_PR_OPENED -> MILESTONE_COMPLETE
    (any phase) -> STOPPED

The side-effect ledger records a stable key for each performed effect (e.g.
``draft_pr:<scope_id>``). The loop checks the ledger BEFORE performing an
effect, so after a crash+resume the effect is recognized as done and skipped.

Persistence is atomic (write temp + ``os.replace``) and fsync'd so a crash
mid-write cannot corrupt the live state file.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

PHASES = (
    "CREATED",
    "AUTHORIZED",
    "IMPLEMENTING",
    "REVIEWING",
    "CORRECTING",
    "ACCEPTED",
    "DRAFT_PR_OPENED",
    "MILESTONE_COMPLETE",
    "STOPPED",
)

# Explicit allowed transitions. The implement -> review -> correct -> implement
# cycle is a legitimate bounded loop (the correction retry), so it is encoded
# here rather than treated as "going backward". STOPPED is reachable from any
# phase (handled specially in ``advance_to``). Transitions NOT listed here are
# rejected fail-closed.
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "CREATED": frozenset({"AUTHORIZED"}),
    "AUTHORIZED": frozenset({"IMPLEMENTING"}),
    "IMPLEMENTING": frozenset({"REVIEWING"}),
    # REVIEWING may also re-enter IMPLEMENTING to support crash-resume in the
    # middle of a review (the mock/deterministic re-implement is idempotent).
    "REVIEWING": frozenset({"ACCEPTED", "CORRECTING", "IMPLEMENTING"}),
    "CORRECTING": frozenset({"IMPLEMENTING"}),
    "ACCEPTED": frozenset({"DRAFT_PR_OPENED"}),
    "DRAFT_PR_OPENED": frozenset({"MILESTONE_COMPLETE"}),
    "MILESTONE_COMPLETE": frozenset(),
    "STOPPED": frozenset(),
}


@dataclass
class RunState:
    """Serializable state for one orchestrated task/milestone run."""

    scope_id: str
    repository: str
    base_sha: str
    target_branch: str
    phase: str = "CREATED"
    iteration: int = 0
    # Stable keys of side effects already performed (idempotency ledger).
    performed_effects: list[str] = field(default_factory=list)
    # Terminal stop reason code, if the run stopped.
    stop_reason: str | None = None
    # Sanitized usage snapshot, updated as the run proceeds.
    usage: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    # --- phase transitions -------------------------------------------------

    def advance_to(self, phase: str) -> None:
        if phase not in _ALLOWED_TRANSITIONS:
            raise ValueError(f"unknown phase: {phase}")
        # STOPPED is always reachable (fail-closed halt from anywhere).
        if phase == "STOPPED":
            self.phase = phase
            return
        # Idempotent self-transition is a no-op (resume may re-enter a phase).
        if phase == self.phase:
            return
        if phase not in _ALLOWED_TRANSITIONS[self.phase]:
            raise ValueError(f"illegal transition {self.phase} -> {phase}")
        self.phase = phase

    def mark_stopped(self, reason_code: str) -> None:
        self.phase = "STOPPED"
        self.stop_reason = reason_code

    # --- side-effect ledger ------------------------------------------------

    def effect_done(self, key: str) -> bool:
        return key in self.performed_effects

    def record_effect(self, key: str) -> None:
        if key not in self.performed_effects:
            self.performed_effects.append(key)

    # --- (de)serialization -------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunState":
        known = {f: data[f] for f in cls.__dataclass_fields__ if f in data}  # type: ignore[attr-defined]
        return cls(**known)


def atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    """Write ``obj`` as JSON atomically (temp file + fsync + os.replace)."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, sort_keys=True, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    finally:
        # If replace succeeded the temp is gone; clean up on any failure path.
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


class StateStore:
    """Loads/saves :class:`RunState` to the runtime state file."""

    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path

    def exists(self) -> bool:
        return self.state_path.is_file()

    def load(self) -> RunState:
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        return RunState.from_dict(data)

    def save(self, state: RunState) -> None:
        atomic_write_json(self.state_path, state.to_dict())
