"""End-to-end mocked loop: dispatch -> reject -> correct -> accept -> draft PR
-> milestone owner stop. Covers the positive-path required scenarios."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.orchestrator import errors
from scripts.orchestrator.adapters.base import Task
from scripts.orchestrator.adapters.github_adapter import MockGitHubAdapter
from scripts.orchestrator.adapters.kiro_adapter import MockKiroAdapter
from scripts.orchestrator.adapters.openai_adapter import MockOpenAIReviewer
from scripts.orchestrator.config import Config
from scripts.orchestrator.loop import Orchestrator
from scripts.orchestrator.manifest import TaskRequest, load_manifest

from .conftest import FIXTURES


def _make(config: Config, manifest_path: Path) -> tuple[Orchestrator, TaskRequest, Task]:
    manifest = load_manifest(manifest_path, config)
    request = TaskRequest(
        scope_id=manifest.scope_id,
        repository=manifest.repository,
        base_sha=manifest.base_sha,
        target_branch=manifest.target_branch,
    )
    task = Task(
        scope_id=manifest.scope_id,
        description="synthetic",
        target_paths=("scripts/orchestrator/example.py",),
        acceptance_key="needs_marker",
    )
    orch = Orchestrator(
        config=config,
        manifest=manifest,
        kiro=MockKiroAdapter(fixture_path=FIXTURES / "kiro_reject_then_fix.jsonl"),
        reviewer=MockOpenAIReviewer(fixture_path=FIXTURES / "openai_reject_then_accept.json"),
        github=MockGitHubAdapter(),
    )
    return orch, request, task


def test_full_loop_reject_correct_accept_draftpr_then_owner_stop(config, write_manifest):
    manifest_path = write_manifest()
    orch, request, task = _make(config, manifest_path)

    # Reaching the milestone raises the mandatory owner stop.
    with pytest.raises(errors.MilestoneOwnerStop):
        orch.run(request, task)

    state = orch.state_store.load()
    assert state.phase == "MILESTONE_COMPLETE"
    assert state.stop_reason == "MILESTONE_OWNER_STOP"
    # One correction happened (reject -> correct -> accept).
    assert state.iteration == 1

    # The event log proves the sequence: authorized, implemented, reviewed
    # (reject), correcting, implemented, reviewed (accept), draft_pr, milestone.
    types = [e["event"] for e in orch.logger.events]
    assert "authorized" in types
    assert types.count("implemented") == 2
    assert types.count("reviewed") == 2
    assert "correcting" in types
    assert "draft_pr_opened" in types
    assert "milestone_complete" in types

    # Draft PR is a draft, open, NOT merged.
    assert orch._draft_pr is not None
    assert orch._draft_pr.is_draft is True
    assert orch._draft_pr.is_open is True
    assert orch._draft_pr.is_merged is False


def test_dispatch_first_iteration_rejected_then_second_accepted(config, write_manifest):
    """Reviewer rejects the first implementation, accepts the corrected one."""

    manifest_path = write_manifest()
    orch, request, task = _make(config, manifest_path)
    with pytest.raises(errors.MilestoneOwnerStop):
        orch.run(request, task)
    reviewed = orch.logger.events_of("reviewed")
    assert reviewed[0]["accepted"] is False
    assert reviewed[0]["verdict"] == "REJECT"
    assert reviewed[1]["accepted"] is True
    assert reviewed[1]["verdict"] == "ACCEPT"
