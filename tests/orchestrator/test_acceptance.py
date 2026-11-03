"""Deterministic acceptance-engine and state-machine unit tests."""

from __future__ import annotations

import pytest

from scripts.orchestrator import acceptance
from scripts.orchestrator.adapters.base import (
    ImplementationResult,
    ReviewFinding,
    ReviewResult,
    Task,
)
from scripts.orchestrator.manifest import load_manifest
from scripts.orchestrator.state import RunState


def _task() -> Task:
    return Task(
        scope_id="S",
        description="d",
        target_paths=("scripts/orchestrator/x.py",),
        acceptance_key="needs_marker",
    )


def _manifest(config, write_manifest):
    return load_manifest(write_manifest(), config)


def test_accept_when_review_ok_scope_ok_marker_present(config, write_manifest):
    manifest = _manifest(config, write_manifest)
    result = ImplementationResult(
        changed_paths=("scripts/orchestrator/x.py",),
        diff_text="+x",
        markers=frozenset({"needs_marker"}),
    )
    review = ReviewResult(verdict="ACCEPT")
    decision = acceptance.evaluate(_task(), result, review, manifest)
    assert decision.accepted
    assert decision.reason_code == "ACCEPTED"


def test_reject_when_reviewer_rejects(config, write_manifest):
    manifest = _manifest(config, write_manifest)
    result = ImplementationResult(
        changed_paths=("scripts/orchestrator/x.py",),
        diff_text="+x",
        markers=frozenset({"needs_marker"}),
    )
    review = ReviewResult(verdict="REJECT", findings=(ReviewFinding("high", "nope"),))
    decision = acceptance.evaluate(_task(), result, review, manifest)
    assert not decision.accepted
    assert decision.reason_code == "REVIEW_REJECTED"


def test_reject_when_marker_missing_even_if_reviewer_accepts(config, write_manifest):
    manifest = _manifest(config, write_manifest)
    result = ImplementationResult(
        changed_paths=("scripts/orchestrator/x.py",),
        diff_text="+x",
        markers=frozenset(),  # marker missing
    )
    review = ReviewResult(verdict="ACCEPT")
    decision = acceptance.evaluate(_task(), result, review, manifest)
    assert not decision.accepted
    assert decision.reason_code == "ACCEPTANCE_MARKER_MISSING"


def test_reject_when_changed_path_out_of_scope_even_if_reviewer_accepts(config, write_manifest):
    """The reviewer's ACCEPT never overrides the orchestrator's own scope check."""

    manifest = _manifest(config, write_manifest)
    result = ImplementationResult(
        changed_paths=("infra/prod/main.tf",),  # outside allowlist
        diff_text="+x",
        markers=frozenset({"needs_marker"}),
    )
    review = ReviewResult(verdict="ACCEPT")
    decision = acceptance.evaluate(_task(), result, review, manifest)
    assert not decision.accepted
    assert decision.reason_code == "CHANGED_PATH_OUTSIDE_SCOPE"


# --- state machine ----------------------------------------------------------


def test_state_cannot_move_backward():
    st = RunState(scope_id="S", repository="r", base_sha="a" * 40, target_branch="b")
    st.advance_to("AUTHORIZED")
    st.advance_to("IMPLEMENTING")
    with pytest.raises(ValueError):
        st.advance_to("AUTHORIZED")  # backward


def test_state_can_always_stop():
    st = RunState(scope_id="S", repository="r", base_sha="a" * 40, target_branch="b")
    st.advance_to("AUTHORIZED")
    st.advance_to("IMPLEMENTING")
    # STOPPED must be reachable directly from a mid-run phase.
    st.advance_to("STOPPED")
    assert st.phase == "STOPPED"
    st2 = RunState(scope_id="S", repository="r", base_sha="a" * 40, target_branch="b")
    st2.mark_stopped("SOME_REASON")
    assert st2.phase == "STOPPED"
    assert st2.stop_reason == "SOME_REASON"


def test_effect_ledger_is_idempotent():
    st = RunState(scope_id="S", repository="r", base_sha="a" * 40, target_branch="b")
    assert not st.effect_done("k")
    st.record_effect("k")
    st.record_effect("k")  # dedup
    assert st.performed_effects == ["k"]
    assert st.effect_done("k")
