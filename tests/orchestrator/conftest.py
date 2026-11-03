"""Shared pytest fixtures + hard isolation guards for the orchestrator tests.

Isolation guarantees enforced here for EVERY test in this package:
  * Sockets are blocked: any attempt to open a network connection raises, so a
    test can never reach the internet or a real service.
  * subprocess spawning is blocked: a test can never invoke real git / gh /
    kiro-cli / any external process.

These guards make the "no production, no internet, no real agent" requirement a
property the suite proves about itself, not just a convention.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

# Make the repository root importable so ``scripts.orchestrator`` resolves no
# matter how pytest is invoked (rootdir, cwd, or -p). The repo root is three
# levels up from this file: tests/orchestrator/conftest.py -> repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest  # noqa: E402

from scripts.orchestrator.config import Budgets, Config  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


# --- hard isolation guards (autouse, package-wide) -------------------------


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any real socket connection raise."""

    def _blocked(*args: Any, **kwargs: Any):  # noqa: ANN401
        raise RuntimeError("network access is blocked in A1 orchestrator tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked, raising=True)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked, raising=True)
    monkeypatch.setattr(socket, "create_connection", _blocked, raising=True)


@pytest.fixture(autouse=True)
def _block_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any attempt to spawn an external process raise."""

    def _blocked(*args: Any, **kwargs: Any):  # noqa: ANN401
        raise RuntimeError("subprocess spawning is blocked in A1 orchestrator tests")

    monkeypatch.setattr(subprocess, "Popen", _blocked, raising=True)
    monkeypatch.setattr(subprocess, "run", _blocked, raising=True)
    monkeypatch.setattr(subprocess, "call", _blocked, raising=True)
    monkeypatch.setattr(subprocess, "check_call", _blocked, raising=True)
    monkeypatch.setattr(subprocess, "check_output", _blocked, raising=True)


# --- directory + config fixtures -------------------------------------------


@pytest.fixture
def runtime_dir(tmp_path: Path) -> Path:
    """Agent-writable runtime dir (never a trusted approval source)."""

    d = tmp_path / "runtime" / ".orchestrator"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def approvals_dir(tmp_path: Path) -> Path:
    """Owner-controlled approvals dir, deliberately OUTSIDE the runtime tree."""

    d = tmp_path / "owner-approvals"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def config(runtime_dir: Path, approvals_dir: Path) -> Config:
    return Config(
        runtime_dir=runtime_dir,
        approvals_dir=approvals_dir,
        budgets=Budgets(max_correction_retries=2, max_review_rejections=2),
    )


# --- manifest helpers ------------------------------------------------------


def _base_manifest_dict() -> dict[str, Any]:
    task = json.loads((FIXTURES / "synthetic_task.json").read_text(encoding="utf-8"))
    return {
        "scope_id": task["scope_id"],
        "repository": task["repository"],
        "base_sha": task["base_sha"],
        "target_branch": task["target_branch"],
        "base_branch": task["base_branch"],
        "allowed_paths": task["allowed_paths"],
        "allowed_actions": task["allowed_actions"],
        "authorized_by": "Matthew",
        "authorized_at": "2026-11-03T00:00:00Z",
    }


@pytest.fixture
def write_manifest(approvals_dir: Path):
    """Factory: write a manifest into the owner-controlled dir, return its path.

    Accepts keyword overrides to mutate individual fields for negative tests.
    """

    def _write(filename: str = "a1.json", directory: Path | None = None, **overrides: Any) -> Path:
        data = _base_manifest_dict()
        data.update(overrides)
        target_dir = directory or approvals_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / filename
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def synthetic_task_dict() -> dict[str, Any]:
    return json.loads((FIXTURES / "synthetic_task.json").read_text(encoding="utf-8"))
