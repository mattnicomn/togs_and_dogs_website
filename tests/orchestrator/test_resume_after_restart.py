"""Crash-safe resume, duplicate side-effect prevention, and checkpoint tamper
detection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.orchestrator import errors
from scripts.orchestrator.adapters.base import Task
from scripts.orchestrator.adapters.github_adapter import MockGitHubAdapter
from scripts.orchestrator.adapters.kiro_adapter import MockKiroAdapter
from scripts.orchestrator.adapters.openai_adapter import MockOpenAIReviewer
from scripts.orchestrator.checkpoint import CheckpointStore
from scripts.orchestrator.config import Config
from scripts.orchestrator.loop import Orchestrator
from scripts.orchestrator.manifest import TaskRequest, load_manifest
from scripts.orchestrator.state import RunState

from .conftest import FIXTURES


def _request(manifest) -> TaskRequest:
    return TaskRequest(
        scope_id=manifest.scope_id,
        repository=manifest.repository,
        base_sha=manifest.base_sha,
        target_branch=manifest.target_branch,
    )


def _task(manifest) -> Task:
    return Task(
        scope_id=manifest.scope_id,
        description="synthetic",
        target_paths=("scripts/orchestrator/example.py",),
        acceptance_key="needs_marker",
    )


def _orch(config, manifest, github: MockGitHubAdapter | None = None) -> Orchestrator:
    return Orchestrator(
        config=config,
        manifest=manifest,
        kiro=MockKiroAdapter(fixture_path=FIXTURES / "kiro_reject_then_fix.jsonl"),
        reviewer=MockOpenAIReviewer(fixture_path=FIXTURES / "openai_reject_then_accept.json"),
        github=github or MockGitHubAdapter(),
    )


def test_resume_after_restart_reaches_owner_stop(config, write_manifest):
    """A completed run persists MILESTONE_COMPLETE; a fresh orchestrator
    resuming from the checkpoint re-asserts the mandatory owner stop."""

    manifest = load_manifest(write_manifest(), config)
    orch1 = _orch(config, manifest)
    with pytest.raises(errors.MilestoneOwnerStop):
        orch1.run(_request(manifest), _task(manifest))

    # A brand-new orchestrator instance (simulating a process restart) resumes
    # from the persisted checkpoint and halts again at the owner gate.
    orch2 = _orch(config, manifest)
    with pytest.raises(errors.MilestoneOwnerStop):
        orch2.run(_request(manifest), _task(manifest))


def test_restart_does_not_replay_draft_pr_side_effect(config, write_manifest):
    """The Draft-PR side effect is recorded in the ledger and never repeated
    on resume."""

    manifest = load_manifest(write_manifest(), config)
    gh1 = MockGitHubAdapter()
    orch1 = _orch(config, manifest, github=gh1)
    with pytest.raises(errors.MilestoneOwnerStop):
        orch1.run(_request(manifest), _task(manifest))
    assert len(gh1.opened) == 1  # opened exactly once

    # Resume with a FRESH github adapter; it must NOT be called again.
    gh2 = MockGitHubAdapter()
    orch2 = _orch(config, manifest, github=gh2)
    with pytest.raises(errors.MilestoneOwnerStop):
        orch2.run(_request(manifest), _task(manifest))
    assert len(gh2.opened) == 0  # NOT replayed after restart

    state = orch2.state_store.load()
    assert f"draft_pr:{manifest.scope_id}" in state.performed_effects


def test_resume_from_accepted_phase_skips_draft_pr_idempotently(config, write_manifest):
    """Crash exactly AFTER acceptance but BEFORE the PR advance: on resume the
    Draft-PR effect is in the ledger, so it is skipped (idempotent) and the
    skip event is emitted, then the owner gate fires."""

    manifest = load_manifest(write_manifest(), config)

    # Hand-craft a checkpoint in the ACCEPTED phase with the PR operation
    # already COMPLETED (simulating a crash right after the effect was
    # persisted) — exactly what a real run records: a complete operation entry
    # with the authorized idempotency key + a valid, authorized-compatible
    # result, plus fingerprints and a complete usage snapshot (F2/F3/F4).
    from scripts.orchestrator.checkpoint import CheckpointStore
    from scripts.orchestrator.loop import Orchestrator, task_fingerprint

    from .conftest import complete_usage_snapshot

    state = RunState(
        scope_id=manifest.scope_id,
        repository=manifest.repository,
        base_sha=manifest.base_sha,
        target_branch=manifest.target_branch,
        phase="ACCEPTED",
    )
    state.manifest_fingerprint = manifest.fingerprint()
    state.task_fingerprint = task_fingerprint(_task(manifest))
    state.usage = complete_usage_snapshot()
    effect_key = f"draft_pr:{manifest.scope_id}"
    _tmp = _orch(config, manifest)
    idem = _tmp._draft_pr_idempotency_key(state)
    state.begin_operation(effect_key, idem)
    state.complete_operation(effect_key, {
        "number": 4242, "url": "mock://pull/4242",
        "is_draft": True, "is_open": True, "is_merged": False,
        "base": manifest.base_branch, "head": manifest.target_branch,
    })
    CheckpointStore(config.checkpoint_path).save(state)

    gh = MockGitHubAdapter()
    orch = _orch(config, manifest, github=gh)
    with pytest.raises(errors.MilestoneOwnerStop):
        orch.run(_request(manifest), _task(manifest))

    # Effect was NOT replayed, and the idempotent-skip event was emitted.
    assert len(gh.opened) == 0
    assert orch.logger.events_of("draft_pr_skipped_idempotent")
    assert orch.state_store.load().phase == "MILESTONE_COMPLETE"


def test_tampered_checkpoint_stops_fail_closed(config, write_manifest):
    """Editing checkpoint contents without re-signing is detected on load."""

    manifest = load_manifest(write_manifest(), config)
    orch1 = _orch(config, manifest)
    with pytest.raises(errors.MilestoneOwnerStop):
        orch1.run(_request(manifest), _task(manifest))

    # Tamper: flip a field in the checkpoint payload, leave the digest intact.
    cp_path = config.checkpoint_path
    envelope = json.loads(cp_path.read_text(encoding="utf-8"))
    envelope["state"]["phase"] = "CREATED"  # pretend nothing happened
    cp_path.write_text(json.dumps(envelope), encoding="utf-8")

    orch2 = _orch(config, manifest)
    with pytest.raises(errors.CheckpointTampered):
        orch2.run(_request(manifest), _task(manifest))


def test_tampered_checkpoint_effect_ledger_detected(config, write_manifest):
    """Forging away a performed effect in the checkpoint is detected (this is
    the attack idempotency must resist: 'forget' the PR to replay it)."""

    manifest = load_manifest(write_manifest(), config)
    orch1 = _orch(config, manifest)
    with pytest.raises(errors.MilestoneOwnerStop):
        orch1.run(_request(manifest), _task(manifest))

    cp_path = config.checkpoint_path
    envelope = json.loads(cp_path.read_text(encoding="utf-8"))
    envelope["state"]["performed_effects"] = []  # try to erase the ledger
    cp_path.write_text(json.dumps(envelope), encoding="utf-8")

    orch2 = _orch(config, manifest)
    with pytest.raises(errors.CheckpointTampered):
        orch2.run(_request(manifest), _task(manifest))


def test_corrupt_checkpoint_stops_fail_closed(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)
    orch1 = _orch(config, manifest)
    with pytest.raises(errors.MilestoneOwnerStop):
        orch1.run(_request(manifest), _task(manifest))

    config.checkpoint_path.write_text("{garbage", encoding="utf-8")
    orch2 = _orch(config, manifest)
    with pytest.raises((errors.CheckpointCorrupt, errors.CheckpointTampered)):
        orch2.run(_request(manifest), _task(manifest))


def test_missing_integrity_key_refuses_checkpoint(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)
    orch1 = _orch(config, manifest)
    with pytest.raises(errors.MilestoneOwnerStop):
        orch1.run(_request(manifest), _task(manifest))

    # Remove the integrity key; the checkpoint can no longer be trusted.
    store = CheckpointStore(config.checkpoint_path)
    store.key_path.unlink()
    orch2 = _orch(config, manifest)
    with pytest.raises(errors.CheckpointTampered):
        orch2.run(_request(manifest), _task(manifest))
