"""Budget governor and loop-stop tests: retry, token, cost, time, and
repeated-review-failure exhaustion all stop fail-closed."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.orchestrator import errors
from scripts.orchestrator.adapters.base import Task
from scripts.orchestrator.adapters.github_adapter import MockGitHubAdapter
from scripts.orchestrator.adapters.kiro_adapter import MockKiroAdapter
from scripts.orchestrator.adapters.openai_adapter import MockOpenAIReviewer
from scripts.orchestrator.budgets import BudgetGovernor
from scripts.orchestrator.config import Budgets, Config
from scripts.orchestrator.loop import Orchestrator
from scripts.orchestrator.manifest import TaskRequest, load_manifest

from .conftest import FIXTURES


# --- unit-level governor tests ---------------------------------------------


def test_token_budget_exhaustion():
    gov = BudgetGovernor(budgets=Budgets(max_tokens=1000), now=lambda: 0.0)
    gov.start()
    with pytest.raises(errors.BudgetExhausted):
        gov.add_usage(tokens=1001)


def test_cost_budget_exhaustion():
    gov = BudgetGovernor(budgets=Budgets(max_cost_usd=0.50), now=lambda: 0.0)
    gov.start()
    with pytest.raises(errors.BudgetExhausted):
        gov.add_usage(cost_usd=0.51)


def test_wall_clock_budget_exhaustion():
    # start() consumes the first tick (t=0); check_time() consumes the second
    # tick (t=999) which is over the 10s budget and must raise.
    ticks = iter([0.0, 999.0])
    gov = BudgetGovernor(
        budgets=Budgets(max_wall_clock_seconds=10.0),
        now=lambda: next(ticks),
    )
    gov.start()
    with pytest.raises(errors.BudgetExhausted):
        gov.check_time()


def test_correction_budget_exhaustion():
    gov = BudgetGovernor(budgets=Budgets(max_correction_retries=1), now=lambda: 0.0)
    gov.start()
    gov.record_correction()  # 1 ok
    with pytest.raises(errors.BudgetExhausted):
        gov.record_correction()  # 2 > 1


def test_review_rejection_budget_exhaustion():
    gov = BudgetGovernor(budgets=Budgets(max_review_rejections=1), now=lambda: 0.0)
    gov.start()
    gov.record_rejection()
    with pytest.raises(errors.ReviewFailuresExhausted):
        gov.record_rejection()


# --- loop-level: repeated review failures stop the run ---------------------


def test_repeated_review_failures_stop_loop(config, write_manifest, approvals_dir, runtime_dir):
    """A reviewer that never accepts exhausts the retry budget and stops."""

    # All-reject reviewer fixture (3 rejects) with a correction budget of 1.
    reject_fixture = runtime_dir.parent / "openai_all_reject.json"
    reject_fixture.write_text(
        '{"reviews": ['
        '{"verdict": "REJECT", "findings": []},'
        '{"verdict": "REJECT", "findings": []},'
        '{"verdict": "REJECT", "findings": []}]}',
        encoding="utf-8",
    )
    # A kiro fixture that always lacks the marker, 3 iterations.
    kiro_fixture = runtime_dir.parent / "kiro_never_marks.jsonl"
    kiro_fixture.write_text(
        '{"iteration": 0, "changed_paths": ["scripts/orchestrator/x.py"], "markers": []}\n'
        '{"iteration": 1, "changed_paths": ["scripts/orchestrator/x.py"], "markers": []}\n'
        '{"iteration": 2, "changed_paths": ["scripts/orchestrator/x.py"], "markers": []}\n',
        encoding="utf-8",
    )

    config = Config(
        runtime_dir=config.runtime_dir,
        approvals_dir=config.approvals_dir,
        budgets=Budgets(max_correction_retries=1, max_review_rejections=5),
    )
    manifest = load_manifest(write_manifest(), config)
    request = TaskRequest(
        scope_id=manifest.scope_id,
        repository=manifest.repository,
        base_sha=manifest.base_sha,
        target_branch=manifest.target_branch,
    )
    task = Task(
        scope_id=manifest.scope_id,
        description="never accepted",
        target_paths=("scripts/orchestrator/x.py",),
        acceptance_key="needs_marker",
    )
    orch = Orchestrator(
        config=config,
        manifest=manifest,
        kiro=MockKiroAdapter(fixture_path=kiro_fixture),
        reviewer=MockOpenAIReviewer(fixture_path=reject_fixture),
        github=MockGitHubAdapter(),
    )
    with pytest.raises(errors.BudgetExhausted):
        orch.run(request, task)

    state = orch.state_store.load()
    assert state.phase == "STOPPED"
    assert state.stop_reason == "BUDGET_EXHAUSTED"
    # The run never reached a draft PR.
    assert not any(e["event"] == "draft_pr_opened" for e in orch.logger.events)
