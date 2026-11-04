"""A2-A G1: the read-only, fixture-backed GitHub observer."""

from __future__ import annotations

import inspect

import pytest

from scripts.orchestrator import errors
from scripts.orchestrator.adapters.github_observer import (
    FixtureGitHubObserver,
    GitHubReadObserver,
    PullRequestObservation,
)

from tests.orchestrator import a2a_support as s


def test_fixture_observer_returns_typed_untrusted_records():
    obs = FixtureGitHubObserver(s.FIX)
    pr = obs.get_pull_request(s.REPO, s.PR)
    assert isinstance(pr, PullRequestObservation)
    assert (pr.number, pr.state, pr.is_draft) == (62, "OPEN", True)
    assert pr.head_sha == s.HEAD and pr.base_sha == s.MAIN
    assert pr.head_ref == s.BRANCH and pr.base_ref == "main"
    assert len(pr.files) == 13 and all(p.startswith("tests/backend/") for p in pr.files)

    runs = obs.get_workflow_runs(s.REPO, s.HEAD)
    assert len(runs) == 1 and runs[0].run_id == s.BACKEND_RUN
    names = {j.name: j for j in runs[0].jobs}
    assert names["backend (pytest)"].job_id == s.BACKEND_JOB
    assert names["backend (pytest)"].conclusion == "failure"
    assert names["mobile (typecheck, test)"].conclusion == "success"

    log = obs.get_job_log(s.REPO, s.BACKEND_JOB, max_bytes=1_000_000)
    assert "6 failed, 2141 passed" in log


def test_observer_protocol_is_read_only():
    methods = {
        name
        for name, member in inspect.getmembers(GitHubReadObserver, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    assert methods == {"get_pull_request", "get_workflow_runs", "get_job_log"}
    assert all(name.startswith("get_") for name in methods)
    assert isinstance(FixtureGitHubObserver(s.FIX), GitHubReadObserver)


def test_fixture_observer_exposes_no_write_surface():
    forbidden = ("merge", "ready", "comment", "create", "update", "delete", "post", "write", "push", "label", "approve")
    public = [n for n in dir(FixtureGitHubObserver) if not n.startswith("_")]
    assert public, "observer should expose its read methods"
    for name in public:
        assert not any(word in name for word in forbidden), name
        assert name.startswith("get_"), name


@pytest.mark.parametrize(
    "edit, exc",
    [
        (lambda d: d.update(head_sha="not-a-sha"), errors.EvidenceInvalid),
        (lambda d: d.update(head_sha="ABCDEF" + "0" * 34), errors.EvidenceInvalid),
        (lambda d: d.update(state="WEIRD"), errors.EvidenceInvalid),
        (lambda d: d.update(is_draft="yes"), errors.EvidenceInvalid),
        (lambda d: d.update(number=True), errors.EvidenceInvalid),
        (lambda d: d.update(number=-1), errors.EvidenceInvalid),
        (lambda d: d.update(files="tests/backend/x.py"), errors.EvidenceInvalid),
        (lambda d: d.update(files=["../etc/passwd"]), errors.EvidenceInvalid),
        (lambda d: d.update(files=["tests/backend/x y.py"]), errors.EvidenceInvalid),
        (lambda d: d.update(files=["a/b.py"] * 301), errors.EvidenceTooLarge),
        (lambda d: d.update(title=123), errors.EvidenceInvalid),
        (lambda d: d.update(repository="not a repo"), errors.EvidenceInvalid),
        (lambda d: d.pop("base_sha"), errors.EvidenceInvalid),
    ],
)
def test_malformed_pull_request_is_rejected(tmp_path, edit, exc):
    fx = s.fixture_copy(tmp_path)
    s.edit_json(fx, "pull_request.json", edit)
    with pytest.raises(exc):
        FixtureGitHubObserver(fx).get_pull_request(s.REPO, s.PR)


def test_pull_request_identity_must_match_the_request(tmp_path):
    with pytest.raises(errors.EvidenceInvalid):
        FixtureGitHubObserver(s.FIX).get_pull_request(s.REPO, 63)
    with pytest.raises(errors.EvidenceInvalid):
        FixtureGitHubObserver(s.FIX).get_pull_request("someone/else", s.PR)


@pytest.mark.parametrize(
    "edit, exc",
    [
        (lambda d: d["runs"][0].update(status="exploded"), errors.EvidenceInvalid),
        (lambda d: d["runs"][0]["jobs"].append(dict(d["runs"][0]["jobs"][0])), errors.EvidenceInvalid),
        (lambda d: d["runs"][0].update(head_sha="zz"), errors.EvidenceInvalid),
        (lambda d: d.update(runs="none"), errors.EvidenceInvalid),
        (lambda d: d["runs"][0]["jobs"][0].update(job_id=0), errors.EvidenceInvalid),
        (lambda d: d.update(runs=[d["runs"][0]] * 51), errors.EvidenceTooLarge),
        (lambda d: d.update(repository="other/repo"), errors.EvidenceInvalid),
    ],
)
def test_malformed_workflow_runs_are_rejected(tmp_path, edit, exc):
    fx = s.fixture_copy(tmp_path)
    s.edit_json(fx, "workflow_runs.json", edit)
    with pytest.raises(exc):
        FixtureGitHubObserver(fx).get_workflow_runs(s.REPO, s.HEAD)


def test_missing_and_non_json_fixture_files_fail_closed(tmp_path):
    fx = s.fixture_copy(tmp_path)
    (fx / "pull_request.json").unlink()
    with pytest.raises(errors.EvidenceIncomplete):
        FixtureGitHubObserver(fx).get_pull_request(s.REPO, s.PR)
    (fx / "workflow_runs.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(errors.EvidenceInvalid):
        FixtureGitHubObserver(fx).get_workflow_runs(s.REPO, s.HEAD)


def test_job_log_missing_oversize_and_bad_id(tmp_path):
    obs = FixtureGitHubObserver(s.FIX)
    with pytest.raises(errors.EvidenceIncomplete):
        obs.get_job_log(s.REPO, 999, max_bytes=1000)
    with pytest.raises(errors.EvidenceTooLarge):
        obs.get_job_log(s.REPO, s.BACKEND_JOB, max_bytes=10)
    for bad in ("../x", 0, -5, True, 1.5):
        with pytest.raises(errors.EvidenceInvalid):
            obs.get_job_log(s.REPO, bad, max_bytes=1000)  # type: ignore[arg-type]


def test_second_pull_request_read_can_return_a_moved_head(tmp_path):
    fx = s.fixture_copy(tmp_path)
    s.edit_json(fx, "pull_request.json", lambda d: None)
    after = fx / "pull_request_after.json"
    after.write_text((fx / "pull_request.json").read_text(encoding="utf-8").replace(s.HEAD, "1" * 40), encoding="utf-8")
    obs = FixtureGitHubObserver(fx)
    assert obs.get_pull_request(s.REPO, s.PR).head_sha == s.HEAD
    assert obs.get_pull_request(s.REPO, s.PR).head_sha == "1" * 40
