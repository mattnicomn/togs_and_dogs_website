"""Proves the suite's own isolation (no network, no subprocess) and that the
local CLI runs the full mocked loop to the owner stop with exit code 0."""

from __future__ import annotations

import socket
import subprocess
from pathlib import Path

import pytest

from scripts.orchestrator import cli

from .conftest import FIXTURES


# --- isolation self-tests ---------------------------------------------------


def test_network_is_blocked():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(RuntimeError):
        s.connect(("example.com", 80))


def test_create_connection_is_blocked():
    with pytest.raises(RuntimeError):
        socket.create_connection(("example.com", 80))


def test_subprocess_run_is_blocked():
    with pytest.raises(RuntimeError):
        subprocess.run(["git", "status"])


def test_subprocess_popen_is_blocked():
    with pytest.raises(RuntimeError):
        subprocess.Popen(["kiro-cli", "--version"])


# --- CLI end-to-end (mocked) ------------------------------------------------


def _common_args(manifest_path: Path, runtime_dir: Path, approvals_dir: Path) -> list[str]:
    return [
        "--runtime-dir",
        str(runtime_dir),
        "--approvals-dir",
        str(approvals_dir),
        "dry-run",
        "--manifest",
        str(manifest_path),
        "--kiro-fixture",
        str(FIXTURES / "kiro_reject_then_fix.jsonl"),
        "--openai-fixture",
        str(FIXTURES / "openai_reject_then_accept.json"),
        "--target-path",
        "scripts/orchestrator/example.py",
        "--acceptance-key",
        "needs_marker",
    ]


def test_cli_dry_run_reaches_owner_stop(capsys, write_manifest, runtime_dir, approvals_dir):
    manifest_path = write_manifest()
    rc = cli.main(_common_args(manifest_path, runtime_dir, approvals_dir))
    assert rc == 0
    out = capsys.readouterr().out
    assert "MANDATORY OWNER STOP" in out
    assert "MILESTONE SUMMARY" in out


def test_cli_status_reports_state(capsys, write_manifest, runtime_dir, approvals_dir):
    manifest_path = write_manifest()
    cli.main(_common_args(manifest_path, runtime_dir, approvals_dir))
    rc = cli.main(
        [
            "--runtime-dir",
            str(runtime_dir),
            "--approvals-dir",
            str(approvals_dir),
            "status",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "MILESTONE_COMPLETE" in out


def test_cli_refuses_missing_manifest(capsys, runtime_dir, approvals_dir):
    rc = cli.main(
        [
            "--runtime-dir",
            str(runtime_dir),
            "--approvals-dir",
            str(approvals_dir),
            "dry-run",
            "--manifest",
            str(approvals_dir / "nope.json"),
            "--kiro-fixture",
            str(FIXTURES / "kiro_reject_then_fix.jsonl"),
            "--openai-fixture",
            str(FIXTURES / "openai_reject_then_accept.json"),
        ]
    )
    # Missing approval -> no execution -> nonzero exit.
    assert rc != 0
