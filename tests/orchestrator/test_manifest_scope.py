"""Negative security tests for approval, scope, SHA, branch, path, and action.

These prove the fail-closed authorization properties required for A1:
  * No approval       -> refusal
  * Untrusted source  -> refusal (AI-writable path can never authorize)
  * Invalid manifest  -> refusal
  * Wrong scope       -> refusal
  * Wrong SHA         -> refusal
  * Unknown branch    -> refusal
  * Unexpected path   -> stop
  * Unauthorized op   -> stop
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.orchestrator import errors
from scripts.orchestrator.manifest import (
    ApprovalManifest,
    TaskRequest,
    load_manifest,
)


def _load(config, path: Path) -> ApprovalManifest:
    return load_manifest(path, config)


# --- approval presence / source / structure -------------------------------


def test_missing_manifest_refuses(config, approvals_dir):
    with pytest.raises(errors.ApprovalMissing):
        load_manifest(approvals_dir / "does_not_exist.json", config)


def test_manifest_in_runtime_dir_is_untrusted(config, write_manifest, runtime_dir):
    """A manifest written into the agent-writable runtime dir is refused."""

    # Write a structurally valid manifest INTO the untrusted runtime dir.
    path = write_manifest(filename="forged.json", directory=runtime_dir)
    with pytest.raises(errors.ApprovalUntrustedSource):
        load_manifest(path, config)


def test_malformed_json_refuses(config, approvals_dir):
    bad = approvals_dir / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(errors.ApprovalInvalid):
        load_manifest(bad, config)


def test_missing_required_field_refuses(config, approvals_dir):
    data = {"scope_id": "x"}  # missing everything else
    p = approvals_dir / "incomplete.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(errors.ApprovalInvalid):
        load_manifest(p, config)


def test_bad_sha_format_refuses(config, write_manifest):
    p = write_manifest(base_sha="not-a-sha")
    with pytest.raises(errors.ApprovalInvalid):
        load_manifest(p, config)


# --- scope / SHA / branch verification -------------------------------------


def test_scope_mismatch_refuses(config, write_manifest):
    manifest = _load(config, write_manifest())
    req = TaskRequest(
        scope_id="WRONG_SCOPE",
        repository=manifest.repository,
        base_sha=manifest.base_sha,
        target_branch=manifest.target_branch,
    )
    with pytest.raises(errors.ScopeMismatch):
        manifest.verify(req)


def test_repository_mismatch_refuses(config, write_manifest):
    manifest = _load(config, write_manifest())
    req = TaskRequest(
        scope_id=manifest.scope_id,
        repository="someone/else",
        base_sha=manifest.base_sha,
        target_branch=manifest.target_branch,
    )
    with pytest.raises(errors.ScopeMismatch):
        manifest.verify(req)


def test_sha_mismatch_refuses(config, write_manifest):
    manifest = _load(config, write_manifest())
    req = TaskRequest(
        scope_id=manifest.scope_id,
        repository=manifest.repository,
        base_sha="0" * 40,
        target_branch=manifest.target_branch,
    )
    with pytest.raises(errors.ShaMismatch):
        manifest.verify(req)


def test_unknown_branch_refuses(config, write_manifest):
    manifest = _load(config, write_manifest())
    req = TaskRequest(
        scope_id=manifest.scope_id,
        repository=manifest.repository,
        base_sha=manifest.base_sha,
        target_branch="feature/not-authorized",
    )
    with pytest.raises(errors.UnknownBranch):
        manifest.verify(req)


# --- path / action scope ----------------------------------------------------


def test_unexpected_path_refuses(config, write_manifest):
    manifest = _load(config, write_manifest())
    with pytest.raises(errors.UnauthorizedPath):
        manifest.assert_paths_allowed(["src/backend/admin_handler.py"])


def test_allowed_path_accepted(config, write_manifest):
    manifest = _load(config, write_manifest())
    # Should not raise.
    manifest.assert_paths_allowed(
        ["scripts/orchestrator/loop.py", "tests/orchestrator/test_x.py"]
    )


def test_unauthorized_action_refuses(config, write_manifest):
    manifest = _load(config, write_manifest(allowed_actions=["implement"]))
    with pytest.raises(errors.UnauthorizedOperation):
        manifest.assert_action_allowed("draft_pr")


def test_path_traversal_outside_scope_refuses(config, write_manifest):
    manifest = _load(config, write_manifest())
    with pytest.raises(errors.UnauthorizedPath):
        manifest.assert_paths_allowed(["scripts/orchestrator/../../infra/prod/main.tf"])
