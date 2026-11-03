"""Finding 2 — resume authorization (adversarial regressions).

Every resume re-verifies manifest identity+integrity, scope/SHA/branch,
persisted task identity+path scope, allowed actions, and prior stop state.
STOPPED work is never auto-resumed.
"""

from __future__ import annotations

import pytest

from scripts.orchestrator import errors
from scripts.orchestrator.adapters.base import Task
from scripts.orchestrator.adapters.github_adapter import MockGitHubAdapter
from scripts.orchestrator.adapters.kiro_adapter import MockKiroAdapter
from scripts.orchestrator.adapters.openai_adapter import MockOpenAIReviewer
from scripts.orchestrator.config import Config
from scripts.orchestrator.loop import Orchestrator
from scripts.orchestrator.manifest import ApprovalManifest, TaskRequest, load_manifest
from scripts.orchestrator.state import RunState, StateStore

from .conftest import FIXTURES


def _request(m) -> TaskRequest:
    return TaskRequest(
        scope_id=m.scope_id, repository=m.repository,
        base_sha=m.base_sha, target_branch=m.target_branch,
    )


def _task(m) -> Task:
    return Task(
        scope_id=m.scope_id, description="synthetic",
        target_paths=("scripts/orchestrator/example.py",), acceptance_key="needs_marker",
    )


def _orch(config, manifest, github=None):
    return Orchestrator(
        config=config, manifest=manifest,
        kiro=MockKiroAdapter(fixture_path=FIXTURES / "kiro_reject_then_fix.jsonl"),
        reviewer=MockOpenAIReviewer(fixture_path=FIXTURES / "openai_reject_then_accept.json"),
        github=github or MockGitHubAdapter(),
    )


def _mutate(manifest: ApprovalManifest, **overrides) -> ApprovalManifest:
    import dataclasses
    return dataclasses.replace(manifest, **overrides)


def _run_to_milestone(orch, manifest):
    with pytest.raises(errors.MilestoneOwnerStop):
        orch.run(_request(manifest), _task(manifest))


def test_resume_of_stopped_work_is_refused(config, write_manifest):
    """A run that ended STOPPED must never auto-resume."""

    manifest = load_manifest(write_manifest(), config)

    # Hand-persist a STOPPED checkpoint.
    from scripts.orchestrator.checkpoint import CheckpointStore
    st = RunState(
        scope_id=manifest.scope_id, repository=manifest.repository,
        base_sha=manifest.base_sha, target_branch=manifest.target_branch,
        phase="STOPPED", stop_reason="BUDGET_EXHAUSTED",
    )
    CheckpointStore(config.checkpoint_path).save(st)

    orch = _orch(config, manifest)
    with pytest.raises(errors.ResumeOfStoppedWork):
        orch.run(_request(manifest), _task(manifest))


def test_resume_with_changed_manifest_fingerprint_refused(config, write_manifest):
    """Mid-run crash, then the manifest's authorized scope changed -> refuse."""

    manifest = load_manifest(write_manifest(), config)

    # Persist a mid-run checkpoint (AUTHORIZED) with the ORIGINAL fingerprint.
    from scripts.orchestrator.checkpoint import CheckpointStore
    st = RunState(
        scope_id=manifest.scope_id, repository=manifest.repository,
        base_sha=manifest.base_sha, target_branch=manifest.target_branch,
        phase="AUTHORIZED",
    )
    st.manifest_fingerprint = manifest.fingerprint()
    from scripts.orchestrator.loop import task_fingerprint
    st.task_fingerprint = task_fingerprint(_task(manifest))
    CheckpointStore(config.checkpoint_path).save(st)

    # Resume with a manifest whose allowed_actions changed (same scope/SHA/
    # branch so verify() passes, but the fingerprint differs).
    changed = _mutate(manifest, allowed_actions=frozenset({"implement"}))
    orch = _orch(config, changed)
    with pytest.raises(errors.ResumeAuthorizationChanged):
        orch.run(_request(changed), _task(changed))


def test_resume_with_changed_task_scope_refused(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)

    from scripts.orchestrator.checkpoint import CheckpointStore
    from scripts.orchestrator.loop import task_fingerprint
    st = RunState(
        scope_id=manifest.scope_id, repository=manifest.repository,
        base_sha=manifest.base_sha, target_branch=manifest.target_branch,
        phase="AUTHORIZED",
    )
    st.manifest_fingerprint = manifest.fingerprint()
    st.task_fingerprint = task_fingerprint(_task(manifest))
    CheckpointStore(config.checkpoint_path).save(st)

    # Resume with a DIFFERENT task (different acceptance key).
    orch = _orch(config, manifest)
    different_task = Task(
        scope_id=manifest.scope_id, description="synthetic",
        target_paths=("scripts/orchestrator/example.py",), acceptance_key="other_key",
    )
    with pytest.raises(errors.ResumeAuthorizationChanged):
        orch.run(_request(manifest), different_task)


def test_resume_with_sha_mismatch_refused(config, write_manifest):
    """Resume where the request base SHA no longer matches the manifest."""

    manifest = load_manifest(write_manifest(), config)
    from scripts.orchestrator.checkpoint import CheckpointStore
    st = RunState(
        scope_id=manifest.scope_id, repository=manifest.repository,
        base_sha=manifest.base_sha, target_branch=manifest.target_branch,
        phase="AUTHORIZED",
    )
    st.manifest_fingerprint = manifest.fingerprint()
    CheckpointStore(config.checkpoint_path).save(st)

    orch = _orch(config, manifest)
    bad_request = TaskRequest(
        scope_id=manifest.scope_id, repository=manifest.repository,
        base_sha="9" * 40, target_branch=manifest.target_branch,
    )
    with pytest.raises(errors.ShaMismatch):
        orch.run(bad_request, _task(manifest))


def test_legitimate_resume_still_reaches_owner_gate(config, write_manifest):
    """A valid resume (unchanged authorization) still completes to the gate."""

    manifest = load_manifest(write_manifest(), config)
    orch1 = _orch(config, manifest)
    _run_to_milestone(orch1, manifest)

    # Fresh instance, identical manifest/task -> resume authorized, gate holds.
    orch2 = _orch(config, manifest)
    with pytest.raises(errors.MilestoneOwnerStop):
        orch2.run(_request(manifest), _task(manifest))
    assert orch2.logger.events_of("resume_authorized")


# --- A1.2 F2 hardening: fingerprints fail-closed past CREATED --------------

from scripts.orchestrator.checkpoint import CheckpointStore  # noqa: E402
from scripts.orchestrator.loop import task_fingerprint  # noqa: E402
from .conftest import complete_usage_snapshot  # noqa: E402


def _past_created_checkpoint(config, manifest, *, manifest_fp, task_fp, phase="AUTHORIZED"):
    """Persist a past-CREATED checkpoint with the given (possibly bad)
    fingerprints plus a complete usage snapshot so only the fingerprint
    binding is under test."""

    st = RunState(
        scope_id=manifest.scope_id, repository=manifest.repository,
        base_sha=manifest.base_sha, target_branch=manifest.target_branch,
        phase=phase,
    )
    st.manifest_fingerprint = manifest_fp
    st.task_fingerprint = task_fp
    st.usage = complete_usage_snapshot()
    CheckpointStore(config.checkpoint_path).save(st)
    return st


def test_resume_missing_manifest_fingerprint_only_refused(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)
    _past_created_checkpoint(
        config, manifest,
        manifest_fp=None,                               # missing
        task_fp=task_fingerprint(_task(manifest)),      # present+valid
    )
    orch = _orch(config, manifest)
    with pytest.raises(errors.ResumeAuthorizationChanged):
        orch.run(_request(manifest), _task(manifest))
    assert orch.state_store.load().stop_reason == "RESUME_AUTHORIZATION_CHANGED"


def test_resume_missing_task_fingerprint_only_refused(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)
    _past_created_checkpoint(
        config, manifest,
        manifest_fp=manifest.fingerprint(),             # present+valid
        task_fp=None,                                   # missing
    )
    orch = _orch(config, manifest)
    with pytest.raises(errors.ResumeAuthorizationChanged):
        orch.run(_request(manifest), _task(manifest))


def test_resume_both_fingerprints_missing_refused(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)
    _past_created_checkpoint(config, manifest, manifest_fp=None, task_fp=None)
    orch = _orch(config, manifest)
    with pytest.raises(errors.ResumeAuthorizationChanged):
        orch.run(_request(manifest), _task(manifest))


def test_resume_malformed_fingerprint_refused(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)
    _past_created_checkpoint(
        config, manifest,
        manifest_fp="not-a-valid-hex-digest",           # malformed
        task_fp=task_fingerprint(_task(manifest)),
    )
    orch = _orch(config, manifest)
    with pytest.raises(errors.ResumeAuthorizationChanged):
        orch.run(_request(manifest), _task(manifest))


def test_resume_empty_string_fingerprint_refused(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)
    _past_created_checkpoint(
        config, manifest,
        manifest_fp="",                                 # empty
        task_fp=task_fingerprint(_task(manifest)),
    )
    orch = _orch(config, manifest)
    with pytest.raises(errors.ResumeAuthorizationChanged):
        orch.run(_request(manifest), _task(manifest))


def test_created_phase_resume_without_fingerprints_is_legitimate(config, write_manifest):
    """A checkpoint still at CREATED (pre-authorization) may carry no
    fingerprints; it resumes normally and runs to the owner gate."""

    manifest = load_manifest(write_manifest(), config)
    _past_created_checkpoint(
        config, manifest, manifest_fp=None, task_fp=None, phase="CREATED",
    )
    orch = _orch(config, manifest)
    with pytest.raises(errors.MilestoneOwnerStop):
        orch.run(_request(manifest), _task(manifest))
    assert orch.state_store.load().phase == "MILESTONE_COMPLETE"
