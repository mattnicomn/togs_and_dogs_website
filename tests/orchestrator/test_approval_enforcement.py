"""Loop-level authorization enforcement: the orchestrator refuses to execute
any work when the request is not authorized by the manifest, and no side
effects occur on refusal."""

from __future__ import annotations

import pytest

from scripts.orchestrator import errors
from scripts.orchestrator.adapters.base import Task
from scripts.orchestrator.adapters.github_adapter import MockGitHubAdapter
from scripts.orchestrator.adapters.kiro_adapter import MockKiroAdapter
from scripts.orchestrator.adapters.openai_adapter import MockOpenAIReviewer
from scripts.orchestrator.loop import Orchestrator
from scripts.orchestrator.manifest import TaskRequest, load_manifest

from .conftest import FIXTURES


def _orch(config, manifest):
    return Orchestrator(
        config=config,
        manifest=manifest,
        kiro=MockKiroAdapter(fixture_path=FIXTURES / "kiro_reject_then_fix.jsonl"),
        reviewer=MockOpenAIReviewer(fixture_path=FIXTURES / "openai_reject_then_accept.json"),
        github=MockGitHubAdapter(),
    )


def _task(manifest):
    return Task(
        scope_id=manifest.scope_id,
        description="x",
        target_paths=("scripts/orchestrator/example.py",),
        acceptance_key="needs_marker",
    )


def test_sha_mismatch_request_refuses_before_any_implementation(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)
    orch = _orch(config, manifest)
    bad_request = TaskRequest(
        scope_id=manifest.scope_id,
        repository=manifest.repository,
        base_sha="1" * 40,  # wrong SHA
        target_branch=manifest.target_branch,
    )
    with pytest.raises(errors.ShaMismatch):
        orch.run(bad_request, _task(manifest))

    # Fail-closed: STOPPED recorded, and NO implementation/review/PR happened.
    state = orch.state_store.load()
    assert state.phase == "STOPPED"
    assert state.stop_reason == "SHA_MISMATCH"
    assert not orch.logger.events_of("implemented")
    assert not orch.logger.events_of("draft_pr_opened")


def test_unknown_branch_request_refuses(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)
    orch = _orch(config, manifest)
    bad_request = TaskRequest(
        scope_id=manifest.scope_id,
        repository=manifest.repository,
        base_sha=manifest.base_sha,
        target_branch="feature/unauthorized",
    )
    with pytest.raises(errors.UnknownBranch):
        orch.run(bad_request, _task(manifest))
    assert orch.state_store.load().stop_reason == "UNKNOWN_BRANCH"


def test_scope_mismatch_request_refuses(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)
    orch = _orch(config, manifest)
    bad_request = TaskRequest(
        scope_id="DIFFERENT",
        repository=manifest.repository,
        base_sha=manifest.base_sha,
        target_branch=manifest.target_branch,
    )
    with pytest.raises(errors.ScopeMismatch):
        orch.run(bad_request, _task(manifest))
    assert orch.state_store.load().stop_reason == "SCOPE_MISMATCH"


def test_task_touches_unauthorized_path_refuses(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)
    orch = _orch(config, manifest)
    request = TaskRequest(
        scope_id=manifest.scope_id,
        repository=manifest.repository,
        base_sha=manifest.base_sha,
        target_branch=manifest.target_branch,
    )
    bad_task = Task(
        scope_id=manifest.scope_id,
        description="out of scope",
        target_paths=("infra/prod/main.tf",),  # outside allowlist
        acceptance_key="needs_marker",
    )
    with pytest.raises(errors.UnauthorizedPath):
        orch.run(request, bad_task)
    assert orch.state_store.load().stop_reason == "UNAUTHORIZED_PATH"
    assert not orch.logger.events_of("implemented")
