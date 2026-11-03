"""Finding 4 — cumulative budget recovery (adversarial regressions).

Budgets (tokens, cost, corrections, rejections, elapsed) are restored on
resume; malformed or over-budget snapshots are rejected; a restart never
resets the task's budgets.
"""

from __future__ import annotations

import pytest

from scripts.orchestrator import errors
from scripts.orchestrator.budgets import BudgetGovernor, restore_governor
from scripts.orchestrator.config import Budgets, Config


def _budgets() -> Budgets:
    return Budgets(
        max_correction_retries=5,
        max_review_rejections=5,
        max_tokens=10_000,
        max_cost_usd=1.0,
        max_wall_clock_seconds=100.0,
    )


# --- restore carries cumulative state --------------------------------------


def test_restore_preserves_cumulative_counters():
    snap = {
        "tokens_used": 4000,
        "cost_used_usd": 0.4,
        "corrections_used": 2,
        "rejections_seen": 1,
        "elapsed_seconds": 30.0,
    }
    gov = restore_governor(_budgets(), snap, now=lambda: 0.0)
    assert gov.tokens_used == 4000
    assert gov.cost_used_usd == 0.4
    assert gov.corrections_used == 2
    assert gov.rejections_seen == 1
    assert gov.prior_elapsed_seconds == 30.0


def test_restore_then_continue_does_not_reset_budget():
    """After restore, additional usage accumulates ON TOP of restored usage and
    can still exhaust the budget (budgets are not reset)."""

    snap = {"tokens_used": 9_500, "cost_used_usd": 0.0,
            "corrections_used": 0, "rejections_seen": 0, "elapsed_seconds": 0.0}
    gov = restore_governor(_budgets(), snap, now=lambda: 0.0)
    gov.start()
    with pytest.raises(errors.BudgetExhausted):
        gov.add_usage(tokens=600)  # 9500 + 600 > 10000


def test_restore_preserves_elapsed_time_budget():
    """Elapsed time carries over: a resumed segment plus prior elapsed can
    exceed the wall-clock ceiling even though the new segment is short."""

    snap = {"tokens_used": 0, "cost_used_usd": 0.0, "corrections_used": 0,
            "rejections_seen": 0, "elapsed_seconds": 99.0}
    ticks = iter([0.0, 2.0])  # start() -> 0, check -> 2; 99 + 2 > 100
    gov = restore_governor(_budgets(), snap, now=lambda: next(ticks))
    gov.start()
    with pytest.raises(errors.BudgetExhausted):
        gov.check_time()


# --- malformed / over-budget snapshots rejected ----------------------------


def test_none_snapshot_yields_fresh_governor():
    gov = restore_governor(_budgets(), None, now=lambda: 0.0)
    assert gov.tokens_used == 0 and gov.prior_elapsed_seconds == 0.0


def test_malformed_snapshot_negative_tokens_rejected():
    snap = {"tokens_used": -1, "cost_used_usd": 0.0, "corrections_used": 0,
            "rejections_seen": 0, "elapsed_seconds": 0.0}
    with pytest.raises(errors.BudgetSnapshotInvalid):
        restore_governor(_budgets(), snap)


def test_malformed_snapshot_wrong_type_rejected():
    snap = {"tokens_used": "lots", "cost_used_usd": 0.0, "corrections_used": 0,
            "rejections_seen": 0, "elapsed_seconds": 0.0}
    with pytest.raises(errors.BudgetSnapshotInvalid):
        restore_governor(_budgets(), snap)


def test_over_budget_token_snapshot_rejected():
    snap = {"tokens_used": 10_001, "cost_used_usd": 0.0, "corrections_used": 0,
            "rejections_seen": 0, "elapsed_seconds": 0.0}
    with pytest.raises(errors.BudgetSnapshotInvalid):
        restore_governor(_budgets(), snap)


def test_over_budget_elapsed_snapshot_rejected():
    snap = {"tokens_used": 0, "cost_used_usd": 0.0, "corrections_used": 0,
            "rejections_seen": 0, "elapsed_seconds": 101.0}
    with pytest.raises(errors.BudgetSnapshotInvalid):
        restore_governor(_budgets(), snap)


def test_over_budget_corrections_snapshot_rejected():
    snap = {"tokens_used": 0, "cost_used_usd": 0.0, "corrections_used": 6,
            "rejections_seen": 0, "elapsed_seconds": 0.0}
    with pytest.raises(errors.BudgetSnapshotInvalid):
        restore_governor(_budgets(), snap)


def test_bool_is_not_accepted_as_int():
    """bool is a subclass of int in Python; the validator must reject it."""

    snap = {"tokens_used": True, "cost_used_usd": 0.0, "corrections_used": 0,
            "rejections_seen": 0, "elapsed_seconds": 0.0}
    with pytest.raises(errors.BudgetSnapshotInvalid):
        restore_governor(_budgets(), snap)


# --- snapshot round-trips elapsed ------------------------------------------


def test_snapshot_includes_elapsed_seconds():
    ticks = iter([0.0, 5.0])
    gov = BudgetGovernor(budgets=_budgets(), now=lambda: next(ticks))
    gov.start()
    snap = gov.snapshot()
    assert "elapsed_seconds" in snap
    assert snap["elapsed_seconds"] == pytest.approx(5.0)


# --- A1.2 F4 hardening: require_complete on resume + NaN/inf + restart ------


def test_require_complete_rejects_empty_snapshot():
    """A resumed authorized run with an empty snapshot is rejected (no
    missing-field-defaults-to-zero)."""

    with pytest.raises(errors.BudgetSnapshotInvalid):
        restore_governor(_budgets(), {}, require_complete=True)


def test_require_complete_rejects_none_snapshot():
    with pytest.raises(errors.BudgetSnapshotInvalid):
        restore_governor(_budgets(), None, require_complete=True)


def test_require_complete_rejects_partial_snapshot():
    """Missing even one cumulative field is rejected under require_complete."""

    partial = {
        "tokens_used": 10, "cost_used_usd": 0.1,
        "corrections_used": 0, "rejections_seen": 0,
        # elapsed_seconds intentionally absent
    }
    with pytest.raises(errors.BudgetSnapshotInvalid):
        restore_governor(_budgets(), partial, require_complete=True)


def test_fresh_run_allows_empty_snapshot():
    """A genuinely fresh CREATED run (require_complete=False) still accepts an
    empty/None snapshot as a zeroed governor."""

    g = restore_governor(_budgets(), {}, require_complete=False)
    assert g.tokens_used == 0
    g2 = restore_governor(_budgets(), None, require_complete=False)
    assert g2.tokens_used == 0


def test_require_complete_accepts_full_snapshot():
    snap = {"tokens_used": 5, "cost_used_usd": 0.2, "corrections_used": 1,
            "rejections_seen": 0, "elapsed_seconds": 3.0}
    g = restore_governor(_budgets(), snap, require_complete=True, now=lambda: 0.0)
    assert g.tokens_used == 5 and g.prior_elapsed_seconds == 3.0


def test_nan_cost_rejected():
    snap = {"tokens_used": 0, "cost_used_usd": float("nan"), "corrections_used": 0,
            "rejections_seen": 0, "elapsed_seconds": 0.0}
    with pytest.raises(errors.BudgetSnapshotInvalid):
        restore_governor(_budgets(), snap)


def test_infinity_elapsed_rejected():
    snap = {"tokens_used": 0, "cost_used_usd": 0.0, "corrections_used": 0,
            "rejections_seen": 0, "elapsed_seconds": float("inf")}
    with pytest.raises(errors.BudgetSnapshotInvalid):
        restore_governor(_budgets(), snap)


def test_negative_infinity_cost_rejected():
    snap = {"tokens_used": 0, "cost_used_usd": float("-inf"), "corrections_used": 0,
            "rejections_seen": 0, "elapsed_seconds": 0.0}
    with pytest.raises(errors.BudgetSnapshotInvalid):
        restore_governor(_budgets(), snap)


# --- restart behavior through the full loop (F4 end-to-end) ----------------


def test_restart_accumulates_budget_not_reset(config, write_manifest):
    """Across a real crash+restart the cumulative token usage carries over and
    is not reset to zero."""

    import dataclasses
    from scripts.orchestrator import errors as e
    from scripts.orchestrator.adapters.base import Task
    from scripts.orchestrator.adapters.github_adapter import MockGitHubAdapter
    from scripts.orchestrator.adapters.kiro_adapter import MockKiroAdapter
    from scripts.orchestrator.adapters.openai_adapter import MockOpenAIReviewer
    from scripts.orchestrator.loop import Orchestrator
    from scripts.orchestrator.manifest import TaskRequest, load_manifest

    from .conftest import FIXTURES

    manifest = load_manifest(write_manifest(), config)
    req = TaskRequest(scope_id=manifest.scope_id, repository=manifest.repository,
                      base_sha=manifest.base_sha, target_branch=manifest.target_branch)
    task = Task(scope_id=manifest.scope_id, description="synthetic",
                target_paths=("scripts/orchestrator/example.py",), acceptance_key="needs_marker")

    def orch():
        return Orchestrator(
            config=config, manifest=manifest,
            kiro=MockKiroAdapter(fixture_path=FIXTURES / "kiro_reject_then_fix.jsonl"),
            reviewer=MockOpenAIReviewer(fixture_path=FIXTURES / "openai_reject_then_accept.json"),
            github=MockGitHubAdapter(),
        )

    o1 = orch()
    with pytest.raises(e.MilestoneOwnerStop):
        o1.run(req, task)
    usage = o1.state_store.load().usage
    # The reject_then_fix + reject_then_accept fixtures report synthetic tokens
    # (1200 + 800 + 900 + 600 = 3500) across the run.
    assert usage["tokens_used"] == 3500

    # Restart (resume at MILESTONE_COMPLETE): restored snapshot preserves usage.
    o2 = orch()
    with pytest.raises(e.MilestoneOwnerStop):
        o2.run(req, task)
    assert o2.governor.tokens_used == 3500  # NOT reset to zero


# --- A1.3 Correction B: cumulative usage persisted at post-accounting boundary


def _b_setup(config, write_manifest, kiro_fixture_text, openai_fixture_text):
    """Helper: write custom kiro/openai fixtures and return (orch_factory,
    request, task, effect_key) for Correction-B loop tests."""

    from scripts.orchestrator.adapters.base import Task
    from scripts.orchestrator.adapters.github_adapter import MockGitHubAdapter
    from scripts.orchestrator.adapters.kiro_adapter import MockKiroAdapter
    from scripts.orchestrator.adapters.openai_adapter import MockOpenAIReviewer
    from scripts.orchestrator.loop import Orchestrator
    from scripts.orchestrator.manifest import TaskRequest, load_manifest

    manifest = load_manifest(write_manifest(), config)
    kf = config.runtime_dir.parent / "b_kiro.jsonl"
    of = config.runtime_dir.parent / "b_openai.json"
    kf.write_text(kiro_fixture_text, encoding="utf-8")
    of.write_text(openai_fixture_text, encoding="utf-8")

    req = TaskRequest(scope_id=manifest.scope_id, repository=manifest.repository,
                      base_sha=manifest.base_sha, target_branch=manifest.target_branch)
    task = Task(scope_id=manifest.scope_id, description="synthetic",
                target_paths=("scripts/orchestrator/example.py",), acceptance_key="needs_marker")

    def factory(**kw):
        return Orchestrator(
            config=config, manifest=manifest,
            kiro=MockKiroAdapter(fixture_path=kf),
            reviewer=MockOpenAIReviewer(fixture_path=of),
            github=MockGitHubAdapter(),
            **kw,
        )

    return factory, req, task


def test_usage_checkpointed_immediately_after_accounting(config, write_manifest):
    """After the first implement-accounting, the on-disk checkpoint already
    reflects the accounted tokens — before the next operation runs."""

    factory, req, task = _b_setup(
        config, write_manifest,
        # One implement iteration reporting 1500 tokens, with the marker so the
        # single review accepts.
        '{"iteration": 0, "changed_paths": ["scripts/orchestrator/example.py"], '
        '"markers": ["needs_marker"], "usage": {"tokens": 1500, "cost_usd": 0.0}}\n',
        '{"reviews": [{"verdict": "ACCEPT", "findings": [], "usage": {"tokens": 500}}]}',
    )

    captured = {}
    orch = factory()
    real_account = orch._account

    def spy_account(state, usage):
        real_account(state, usage)
        # Immediately after the FIRST accounting, read the on-disk state.
        if "after_first" not in captured:
            from scripts.orchestrator.state import StateStore
            captured["after_first"] = StateStore(config.state_path).load().usage["tokens_used"]

    orch._account = spy_account
    with pytest.raises(errors.MilestoneOwnerStop):
        orch.run(req, task)

    # The checkpoint written inside _account reflects the 1500 implement tokens
    # at the post-accounting boundary (before the review operation).
    assert captured["after_first"] == 1500


def test_budget_exhaustion_preserves_accounted_usage_in_stopped_checkpoint(config, write_manifest):
    """When accounting a response exhausts the token budget, the terminal
    STOPPED checkpoint still contains the exhausting accounted usage."""

    from scripts.orchestrator.config import Budgets
    # Tight token ceiling so the first implement's usage exhausts it.
    config = Config(runtime_dir=config.runtime_dir, approvals_dir=config.approvals_dir,
                    budgets=Budgets(max_tokens=1000, max_cost_usd=1.0,
                                    max_correction_retries=2, max_review_rejections=2,
                                    max_wall_clock_seconds=300.0))
    factory, req, task = _b_setup(
        config, write_manifest,
        '{"iteration": 0, "changed_paths": ["scripts/orchestrator/example.py"], '
        '"markers": ["needs_marker"], "usage": {"tokens": 1500, "cost_usd": 0.0}}\n',
        '{"reviews": [{"verdict": "ACCEPT", "findings": []}]}',
    )
    orch = factory()
    with pytest.raises(errors.BudgetExhausted):
        orch.run(req, task)

    st = orch.state_store.load()
    assert st.phase == "STOPPED"
    assert st.stop_reason == "BUDGET_EXHAUSTED"
    # The exhausting accounted usage (1500) is preserved, NOT reset to zero.
    assert st.usage["tokens_used"] == 1500


def test_resume_cannot_reset_checkpointed_cumulative_usage(config, write_manifest):
    """A crash after accounting leaves usage checkpointed; a resume restores and
    continues from it — it can never silently reset to zero."""

    import json as _json

    factory, req, task = _b_setup(
        config, write_manifest,
        # Two iterations available (reject-then-accept) so a mid-run crash has a
        # resume path; implement reports 1200 tokens on iteration 0.
        '{"iteration": 0, "changed_paths": ["scripts/orchestrator/example.py"], '
        '"markers": [], "usage": {"tokens": 1200, "cost_usd": 0.0}}\n'
        '{"iteration": 1, "changed_paths": ["scripts/orchestrator/example.py"], '
        '"markers": ["needs_marker"], "usage": {"tokens": 800, "cost_usd": 0.0}}\n',
        '{"reviews": ['
        '{"verdict": "REJECT", "findings": []},'
        '{"verdict": "ACCEPT", "findings": []}]}',
    )

    # Crash: make the reviewer unavailable on the FIRST review by replacing the
    # orchestrator's reviewer with one that raises after implement-accounting.
    orch1 = factory()

    class Boom:
        def review(self, *a, **k):
            raise RuntimeError("injected crash after implement accounting")

    orch1.reviewer = Boom()
    with pytest.raises(RuntimeError):
        orch1.run(req, task)

    # The implement accounting (1200) was checkpointed before the crash.
    mid = orch1.state_store.load().usage["tokens_used"]
    assert mid == 1200

    # Restart with a healthy orchestrator; usage must NOT reset — it restores
    # 1200 and continues accumulating to the owner gate.
    orch2 = factory()
    with pytest.raises(errors.MilestoneOwnerStop):
        orch2.run(req, task)
    assert orch2.governor.tokens_used >= 1200  # carried over, never reset
