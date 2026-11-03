"""Finding 3 — side-effect recovery (adversarial regressions).

Simulates a crash (a) before the external call, (b) after external success but
before confirmation, and (c) after persisted completion. On restart the
uncertain result is reconciled against the mock GitHub adapter by idempotency
key: a completed operation is never duplicated, and if reconciliation is
impossible the run STOPS instead of retrying blindly.
"""

from __future__ import annotations

import pytest

from scripts.orchestrator import errors
from scripts.orchestrator.adapters.base import Task
from scripts.orchestrator.adapters.github_adapter import MockGitHubAdapter
from scripts.orchestrator.adapters.kiro_adapter import MockKiroAdapter
from scripts.orchestrator.adapters.openai_adapter import MockOpenAIReviewer
from scripts.orchestrator.checkpoint import CheckpointStore
from scripts.orchestrator.loop import Orchestrator
from scripts.orchestrator.manifest import TaskRequest, load_manifest
from scripts.orchestrator.state import RunState

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


def _orch(config, manifest, github):
    return Orchestrator(
        config=config, manifest=manifest,
        kiro=MockKiroAdapter(fixture_path=FIXTURES / "kiro_reject_then_fix.jsonl"),
        reviewer=MockOpenAIReviewer(fixture_path=FIXTURES / "openai_reject_then_accept.json"),
        github=github,
    )


def _accepted_checkpoint(config, manifest):
    """Persist a checkpoint at the ACCEPTED phase (about to open the PR), with
    authorization fingerprints AND a complete usage snapshot recorded — exactly
    what a real run's ``_persist`` writes — so resume authorization (F2) and
    budget restore (F4) both pass."""

    from scripts.orchestrator.loop import task_fingerprint
    from .conftest import complete_usage_snapshot
    st = RunState(
        scope_id=manifest.scope_id, repository=manifest.repository,
        base_sha=manifest.base_sha, target_branch=manifest.target_branch,
        phase="ACCEPTED",
    )
    st.manifest_fingerprint = manifest.fingerprint()
    st.task_fingerprint = task_fingerprint(_task(manifest))
    st.usage = complete_usage_snapshot()
    CheckpointStore(config.checkpoint_path).save(st)
    return st


# --- crash (a): before the external call -----------------------------------


def test_crash_before_external_call_then_clean_retry(config, write_manifest):
    """Adapter raises BEFORE recording the PR (nothing happened server-side).
    The operation is left pending; a restart reconciles (finds nothing) and
    performs the call exactly once."""

    manifest = load_manifest(write_manifest(), config)
    _accepted_checkpoint(config, manifest)

    gh_fail = MockGitHubAdapter(fail_before_record=True)
    orch1 = _orch(config, manifest, gh_fail)
    with pytest.raises(RuntimeError):
        orch1.run(_request(manifest), _task(manifest))
    # Nothing was recorded server-side; operation is pending.
    assert len(gh_fail.by_key) == 0
    assert orch1.state_store.load().operation_status(f"draft_pr:{manifest.scope_id}") == "pending"

    # Restart with a healthy adapter sharing the same server-side store state
    # (empty) -> reconcile finds nothing -> performs exactly one PR.
    gh_ok = MockGitHubAdapter()
    orch2 = _orch(config, manifest, gh_ok)
    with pytest.raises(errors.MilestoneOwnerStop):
        orch2.run(_request(manifest), _task(manifest))
    assert len(gh_ok.opened) == 1
    assert orch2.logger.events_of("draft_pr_opened_after_reconcile")


# --- crash (b): after external success, before confirmation -----------------


def test_crash_after_success_before_confirmation_reconciles_no_duplicate(config, write_manifest):
    """Adapter records the PR, THEN raises before the caller confirms. On
    restart, the SAME adapter (server-side record persists) is reconciled by
    idempotency key -> the existing PR is adopted, NOT duplicated."""

    manifest = load_manifest(write_manifest(), config)
    _accepted_checkpoint(config, manifest)

    gh = MockGitHubAdapter(fail_after_record=True)
    orch1 = _orch(config, manifest, gh)
    with pytest.raises(RuntimeError):
        orch1.run(_request(manifest), _task(manifest))
    # Server-side the PR EXISTS (recorded before the simulated crash).
    assert len(gh.by_key) == 1
    assert len(gh.opened) == 1
    assert orch1.state_store.load().operation_status(f"draft_pr:{manifest.scope_id}") == "pending"

    # Restart: clear the failure flag on the SAME adapter (same server store).
    gh.fail_after_record = False
    orch2 = _orch(config, manifest, gh)
    with pytest.raises(errors.MilestoneOwnerStop):
        orch2.run(_request(manifest), _task(manifest))
    # Reconciled to the existing PR: still exactly ONE PR, no duplicate.
    assert len(gh.opened) == 1
    assert orch2.logger.events_of("draft_pr_reconciled_existing")
    assert orch2.state_store.load().operation_status(f"draft_pr:{manifest.scope_id}") == "completed"


# --- crash (c): after persisted completion ----------------------------------


def test_crash_after_persisted_completion_never_replays(config, write_manifest):
    """Operation already completed+persisted: restart must not call the adapter
    again at all."""

    manifest = load_manifest(write_manifest(), config)
    gh1 = MockGitHubAdapter()
    orch1 = _orch(config, manifest, gh1)
    with pytest.raises(errors.MilestoneOwnerStop):
        orch1.run(_request(manifest), _task(manifest))
    assert len(gh1.opened) == 1
    assert orch1.state_store.load().operation_status(f"draft_pr:{manifest.scope_id}") == "completed"

    # Restart with a FRESH adapter; it must never be called.
    gh2 = MockGitHubAdapter()
    orch2 = _orch(config, manifest, gh2)
    with pytest.raises(errors.MilestoneOwnerStop):
        orch2.run(_request(manifest), _task(manifest))
    assert len(gh2.opened) == 0


# --- reconciliation impossible -> STOP, never blind retry -------------------


def test_reconciliation_impossible_stops_fail_closed(config, write_manifest):
    """If the reconciliation lookup itself cannot be performed, the run STOPS
    (SideEffectReconciliationFailed) rather than retrying blindly."""

    manifest = load_manifest(write_manifest(), config)
    _accepted_checkpoint(config, manifest)

    # Pre-mark the operation pending with the CORRECT authorized idempotency
    # key (so the F3 identity guard passes and the reconcile path is reached),
    # then make the reconciliation lookup itself fail.
    st = CheckpointStore(config.checkpoint_path).load()
    _tmp = _orch(config, manifest, MockGitHubAdapter())
    correct_key = _tmp._draft_pr_idempotency_key(st)
    st.begin_operation(f"draft_pr:{manifest.scope_id}", correct_key)
    CheckpointStore(config.checkpoint_path).save(st)

    class BrokenGitHub(MockGitHubAdapter):
        def find_by_idempotency_key(self, idempotency_key):
            raise RuntimeError("reconciliation backend unreachable")

    orch = _orch(config, manifest, BrokenGitHub())
    with pytest.raises(errors.SideEffectReconciliationFailed):
        orch.run(_request(manifest), _task(manifest))
    assert orch.state_store.load().stop_reason == "SIDE_EFFECT_RECONCILIATION_FAILED"


# --- A1.2 F3 hardening: operation identity + reconciled-result compatibility

from scripts.orchestrator.adapters.base import DraftPRResult  # noqa: E402


def test_pending_op_with_mismatched_idempotency_key_refused(config, write_manifest):
    """A persisted PENDING op whose idempotency key != the authorized key is
    rejected fail-closed BEFORE any reconciliation/lookup."""

    manifest = load_manifest(write_manifest(), config)
    _accepted_checkpoint(config, manifest)
    st = CheckpointStore(config.checkpoint_path).load()
    st.begin_operation(f"draft_pr:{manifest.scope_id}", "FORGED-WRONG-KEY")
    CheckpointStore(config.checkpoint_path).save(st)

    gh = MockGitHubAdapter()
    orch = _orch(config, manifest, gh)
    with pytest.raises(errors.OperationRecordInvalid):
        orch.run(_request(manifest), _task(manifest))
    # Never touched the adapter.
    assert len(gh.opened) == 0
    assert orch.state_store.load().stop_reason == "OPERATION_RECORD_INVALID"


def test_completed_op_with_mismatched_idempotency_key_refused(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)
    _accepted_checkpoint(config, manifest)
    st = CheckpointStore(config.checkpoint_path).load()
    key = f"draft_pr:{manifest.scope_id}"
    st.begin_operation(key, "FORGED-WRONG-KEY")
    st.complete_operation(key, {
        "number": 1, "url": "mock://pull/1", "is_draft": True, "is_open": True,
        "is_merged": False, "base": manifest.base_branch, "head": manifest.target_branch,
    })
    CheckpointStore(config.checkpoint_path).save(st)

    orch = _orch(config, manifest, MockGitHubAdapter())
    with pytest.raises(errors.OperationRecordInvalid):
        orch.run(_request(manifest), _task(manifest))


def test_malformed_operation_record_refused(config, write_manifest):
    """An operation record claiming a known status but missing its idempotency
    key is malformed and rejected."""

    manifest = load_manifest(write_manifest(), config)
    _accepted_checkpoint(config, manifest)
    st = CheckpointStore(config.checkpoint_path).load()
    st.operations[f"draft_pr:{manifest.scope_id}"] = {"status": "pending", "idempotency_key": None, "result": None}
    CheckpointStore(config.checkpoint_path).save(st)

    orch = _orch(config, manifest, MockGitHubAdapter())
    with pytest.raises(errors.OperationRecordInvalid):
        orch.run(_request(manifest), _task(manifest))


def _reconcile_with(config, manifest, found: DraftPRResult):
    """Set up a PENDING op with the correct key, and an adapter that returns
    ``found`` from reconciliation."""

    _accepted_checkpoint(config, manifest)
    st = CheckpointStore(config.checkpoint_path).load()
    tmp = _orch(config, manifest, MockGitHubAdapter())
    key = tmp._draft_pr_idempotency_key(st)
    st.begin_operation(f"draft_pr:{manifest.scope_id}", key)
    CheckpointStore(config.checkpoint_path).save(st)

    class ReturningGitHub(MockGitHubAdapter):
        def find_by_idempotency_key(self, idempotency_key):
            return found

    return _orch(config, manifest, ReturningGitHub())


def test_reconciled_result_wrong_head_not_adopted(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)
    bad = DraftPRResult(number=7, url="mock://pull/7", is_draft=True, is_open=True,
                        is_merged=False, base=manifest.base_branch, head="attacker/other-branch")
    orch = _reconcile_with(config, manifest, bad)
    with pytest.raises(errors.ReconciledResultIncompatible):
        orch.run(_request(manifest), _task(manifest))
    assert orch.state_store.load().stop_reason == "RECONCILED_RESULT_INCOMPATIBLE"


def test_reconciled_result_wrong_base_not_adopted(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)
    bad = DraftPRResult(number=7, url="mock://pull/7", is_draft=True, is_open=True,
                        is_merged=False, base="production", head=manifest.target_branch)
    orch = _reconcile_with(config, manifest, bad)
    with pytest.raises(errors.ReconciledResultIncompatible):
        orch.run(_request(manifest), _task(manifest))


def test_reconciled_result_merged_not_adopted(config, write_manifest):
    """A1 must never adopt a merged PR, even via reconciliation."""

    manifest = load_manifest(write_manifest(), config)
    bad = DraftPRResult(number=7, url="mock://pull/7", is_draft=False, is_open=False,
                        is_merged=True, base=manifest.base_branch, head=manifest.target_branch)
    orch = _reconcile_with(config, manifest, bad)
    with pytest.raises(errors.ReconciledResultIncompatible):
        orch.run(_request(manifest), _task(manifest))


def test_reconciled_result_not_draft_not_adopted(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)
    bad = DraftPRResult(number=7, url="mock://pull/7", is_draft=False, is_open=True,
                        is_merged=False, base=manifest.base_branch, head=manifest.target_branch)
    orch = _reconcile_with(config, manifest, bad)
    with pytest.raises(errors.ReconciledResultIncompatible):
        orch.run(_request(manifest), _task(manifest))


def test_reconciled_result_compatible_is_adopted(config, write_manifest):
    """A compatible reconciled result IS adopted (positive control)."""

    manifest = load_manifest(write_manifest(), config)
    good = DraftPRResult(number=7, url="mock://pull/7", is_draft=True, is_open=True,
                         is_merged=False, base=manifest.base_branch, head=manifest.target_branch)
    orch = _reconcile_with(config, manifest, good)
    with pytest.raises(errors.MilestoneOwnerStop):
        orch.run(_request(manifest), _task(manifest))
    assert orch.logger.events_of("draft_pr_reconciled_existing")


# --- A1.3 Correction A: operation-status fail-closed -----------------------
#
# A pre-existing ledger record with an unknown/invalid status, or a
# performed_effects/operations inconsistency, must stop the run fail-closed
# BEFORE any adapter call, and must never be overwritten by a fresh pending op.


class _CountingGitHub(MockGitHubAdapter):
    """Mock that records every open_draft_pr / find_by_idempotency_key call so a
    test can assert the adapter was never touched."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.open_calls = 0
        self.lookup_calls = 0

    def open_draft_pr(self, **kwargs):
        self.open_calls += 1
        return super().open_draft_pr(**kwargs)

    def find_by_idempotency_key(self, idempotency_key):
        self.lookup_calls += 1
        return super().find_by_idempotency_key(idempotency_key)


def _accepted_with_operation(config, manifest, record):
    """ACCEPTED checkpoint whose operations ledger holds exactly ``record`` for
    the draft-PR effect (plus fingerprints + complete usage)."""

    st = _accepted_checkpoint(config, manifest)  # writes fingerprints + usage
    st = CheckpointStore(config.checkpoint_path).load()
    st.operations[f"draft_pr:{manifest.scope_id}"] = record
    CheckpointStore(config.checkpoint_path).save(st)
    return st


def test_unknown_status_record_stops_before_any_adapter_call(config, write_manifest):
    manifest = load_manifest(write_manifest(), config)
    tmp = _orch(config, manifest, MockGitHubAdapter())
    idem = tmp._draft_pr_idempotency_key(CheckpointStore(config.checkpoint_path).load()
                                          if CheckpointStore(config.checkpoint_path).exists() else
                                          _accepted_checkpoint(config, manifest))
    # Ensure checkpoint exists, then install an unknown-status record.
    _accepted_with_operation(config, manifest, {
        "status": "quantum-superposition", "idempotency_key": idem, "result": None,
    })
    gh = _CountingGitHub()
    orch = _orch(config, manifest, gh)
    with pytest.raises(errors.OperationRecordInvalid):
        orch.run(_request(manifest), _task(manifest))
    assert gh.open_calls == 0 and gh.lookup_calls == 0
    assert orch.state_store.load().stop_reason == "OPERATION_RECORD_INVALID"


def test_inconsistent_ledger_effect_done_without_record_stops(config, write_manifest):
    """performed_effects claims done, but operations has no record -> stop, no
    adapter call, and the invalid state is not 'completed'-skipped."""

    manifest = load_manifest(write_manifest(), config)
    _accepted_checkpoint(config, manifest)
    st = CheckpointStore(config.checkpoint_path).load()
    st.record_effect(f"draft_pr:{manifest.scope_id}")  # ledger says done
    # operations deliberately left empty for this effect
    CheckpointStore(config.checkpoint_path).save(st)

    gh = _CountingGitHub()
    orch = _orch(config, manifest, gh)
    with pytest.raises(errors.OperationRecordInvalid):
        orch.run(_request(manifest), _task(manifest))
    assert gh.open_calls == 0 and gh.lookup_calls == 0


def test_completed_record_not_in_performed_effects_stops(config, write_manifest):
    """A 'completed' operation record whose effect is absent from
    performed_effects is inconsistent -> stop, no adapter call."""

    manifest = load_manifest(write_manifest(), config)
    _accepted_checkpoint(config, manifest)
    st = CheckpointStore(config.checkpoint_path).load()
    tmp = _orch(config, manifest, MockGitHubAdapter())
    idem = tmp._draft_pr_idempotency_key(st)
    st.operations[f"draft_pr:{manifest.scope_id}"] = {
        "status": "completed", "idempotency_key": idem,
        "result": {"number": 1, "url": "mock://pull/1", "is_draft": True,
                   "is_open": True, "is_merged": False,
                   "base": manifest.base_branch, "head": manifest.target_branch},
    }
    # performed_effects intentionally does NOT contain the effect.
    CheckpointStore(config.checkpoint_path).save(st)

    gh = _CountingGitHub()
    orch = _orch(config, manifest, gh)
    with pytest.raises(errors.OperationRecordInvalid):
        orch.run(_request(manifest), _task(manifest))
    assert gh.open_calls == 0 and gh.lookup_calls == 0


def test_invalid_record_is_not_overwritten_by_fresh_pending(config, write_manifest):
    """An invalid existing record must NOT be replaced with a new pending op:
    after the stop, the original invalid record is still present unchanged."""

    manifest = load_manifest(write_manifest(), config)
    tmp = _orch(config, manifest, MockGitHubAdapter())
    idem = tmp._draft_pr_idempotency_key(_accepted_checkpoint(config, manifest))
    bad = {"status": "bogus", "idempotency_key": idem, "result": None}
    _accepted_with_operation(config, manifest, dict(bad))

    gh = _CountingGitHub()
    orch = _orch(config, manifest, gh)
    with pytest.raises(errors.OperationRecordInvalid):
        orch.run(_request(manifest), _task(manifest))
    # The persisted operation record is unchanged (still the invalid one),
    # NOT replaced by a fresh {"status": "pending", ...}.
    persisted = orch.state_store.load().operations[f"draft_pr:{manifest.scope_id}"]
    assert persisted["status"] == "bogus"
    assert gh.open_calls == 0


def test_completed_record_missing_result_stops(config, write_manifest):
    """A 'completed' record with no result payload is malformed -> stop."""

    manifest = load_manifest(write_manifest(), config)
    _accepted_checkpoint(config, manifest)
    st = CheckpointStore(config.checkpoint_path).load()
    tmp = _orch(config, manifest, MockGitHubAdapter())
    idem = tmp._draft_pr_idempotency_key(st)
    key = f"draft_pr:{manifest.scope_id}"
    st.operations[key] = {"status": "completed", "idempotency_key": idem, "result": None}
    st.record_effect(key)
    CheckpointStore(config.checkpoint_path).save(st)

    gh = _CountingGitHub()
    orch = _orch(config, manifest, gh)
    with pytest.raises(errors.OperationRecordInvalid):
        orch.run(_request(manifest), _task(manifest))
    assert gh.open_calls == 0 and gh.lookup_calls == 0


# --- A1.3 edge: an EXISTING operation key whose value is None --------------


def test_existing_operation_key_with_none_value_rejected(config, write_manifest):
    """An operations entry that EXISTS but is None (as opposed to a genuinely
    absent key) is a malformed record: it must raise OperationRecordInvalid
    before any adapter open/lookup, and must NOT be overwritten with a fresh
    pending op."""

    manifest = load_manifest(write_manifest(), config)
    _accepted_checkpoint(config, manifest)
    st = CheckpointStore(config.checkpoint_path).load()
    effect_key = f"draft_pr:{manifest.scope_id}"
    st.operations[effect_key] = None  # present-but-None, not absent
    CheckpointStore(config.checkpoint_path).save(st)

    # Precondition: the key is present (not absent) and its value is None, and
    # it is NOT in the performed-effects ledger (so the only thing that could
    # misroute it to fresh execution is the present-vs-None distinction).
    reloaded = CheckpointStore(config.checkpoint_path).load()
    assert effect_key in reloaded.operations
    assert reloaded.operations[effect_key] is None
    assert not reloaded.effect_done(effect_key)

    gh = _CountingGitHub()
    orch = _orch(config, manifest, gh)
    with pytest.raises(errors.OperationRecordInvalid):
        orch.run(_request(manifest), _task(manifest))

    # No adapter call of any kind.
    assert gh.open_calls == 0 and gh.lookup_calls == 0
    # The invalid record was NOT overwritten by a fresh pending op: the key is
    # still present with value None (the run stopped before begin_operation).
    persisted = orch.state_store.load()
    assert effect_key in persisted.operations
    assert persisted.operations[effect_key] is None
    assert orch.state_store.load().stop_reason == "OPERATION_RECORD_INVALID"
