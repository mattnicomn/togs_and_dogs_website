"""Finding 1 — owner approval trust (adversarial regressions).

Proves the approval source must be an explicitly configured owner-controlled
location, symlink/path boundaries are enforced, authorized_by text is never
treated as proof, and an OS-permission boundary hook exists for A2.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.orchestrator import errors
from scripts.orchestrator.config import ENV_APPROVALS_DIR, load_config
from scripts.orchestrator.manifest import load_manifest


# --- no silent default to a repo/agent-writable approvals source -----------


def test_load_config_refuses_unconfigured_approvals(monkeypatch):
    monkeypatch.delenv(ENV_APPROVALS_DIR, raising=False)
    with pytest.raises(errors.ApprovalSourceNotConfigured):
        load_config(runtime_dir="whatever")  # no approvals_dir, no env


def test_load_config_accepts_explicit_approvals(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_APPROVALS_DIR, raising=False)
    cfg = load_config(runtime_dir=tmp_path / "rt", approvals_dir=tmp_path / "owner")
    assert cfg.approvals_dir == (tmp_path / "owner").resolve()


def test_load_config_honors_env_approvals(tmp_path, monkeypatch):
    owner = tmp_path / "ownerenv"
    monkeypatch.setenv(ENV_APPROVALS_DIR, str(owner))
    cfg = load_config(runtime_dir=tmp_path / "rt")
    assert cfg.approvals_dir == owner.resolve()


def test_status_path_allows_unconfigured_approvals(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_APPROVALS_DIR, raising=False)
    # require_approvals=False must NOT raise (status reads local state only).
    cfg = load_config(runtime_dir=tmp_path / "rt", require_approvals=False)
    assert "DO_NOT_TRUST" in str(cfg.approvals_dir)


# --- positive containment + symlink boundary -------------------------------


def test_manifest_outside_approvals_dir_refused(config, write_manifest, tmp_path):
    # Write a structurally valid manifest OUTSIDE the configured approvals dir.
    outside = tmp_path / "elsewhere"
    path = write_manifest(filename="stray.json", directory=outside)
    with pytest.raises(errors.ApprovalUntrustedSource):
        load_manifest(path, config)


def test_symlinked_manifest_into_untrusted_tree_refused(config, write_manifest, runtime_dir, approvals_dir):
    """A symlink living in the approvals dir but pointing into the agent-
    writable runtime tree must be refused (realpath escapes containment)."""

    # Real manifest content lives in the untrusted runtime dir.
    real = write_manifest(filename="real.json", directory=runtime_dir)
    link = approvals_dir / "link.json"
    try:
        os.symlink(real, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported in this environment")
    with pytest.raises(errors.ApprovalUntrustedSource):
        load_manifest(link, config)


# --- authorized_by is never proof ------------------------------------------


def test_authorized_by_text_is_not_trusted_as_proof(config, write_manifest):
    """A manifest claiming authorized_by='attacker' still loads purely on its
    owner-controlled LOCATION; the text is audit metadata, not authorization,
    and is excluded from the integrity fingerprint."""

    m1 = load_manifest(write_manifest(filename="a.json", authorized_by="Matthew"), config)
    m2 = load_manifest(write_manifest(filename="b.json", authorized_by="attacker"), config)
    # Same scope => same fingerprint regardless of authorized_by text.
    assert m1.fingerprint() == m2.fingerprint()


# --- OS permission boundary hook (advisory in A1, enforceable in A2) --------


def test_owner_source_permission_check_advisory_does_not_raise(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)
    warnings = manifest.assert_owner_source_permissions(enforce=False)
    assert isinstance(warnings, list)  # advisory: returns, never raises in A1


def test_owner_source_permission_check_enforced_raises_when_group_writable(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)
    p = manifest.source_path
    try:
        os.chmod(p, 0o666)  # group/other writable
        made_writable = (os.stat(p).st_mode & 0o022) != 0
    except OSError:
        made_writable = False
    if not made_writable:
        pytest.skip("filesystem does not honor POSIX group/other write bits")
    with pytest.raises(errors.ApprovalUntrustedSource):
        manifest.assert_owner_source_permissions(enforce=True)
