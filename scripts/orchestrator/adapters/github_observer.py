"""Read-only GitHub observation (A2-A G1 — fixture-backed, fully offline).

This module defines WHAT the orchestrator may observe about a pull request and
its CI, and a fixture-backed implementation used by tests and the offline CLI.

Authority boundary (enforced structurally, not by convention):
  * :class:`GitHubReadObserver` exposes ONLY ``get_*`` read methods. There is no
    method to create, update, comment on, label, mark ready, or merge anything.
    A live implementation in a later, separately-approved milestone must satisfy
    this same read-only protocol and must use a read-only credential.
  * Everything an observer returns is UNTRUSTED data (PR titles, bodies and CI
    logs are attacker-influenced text). It is validated strictly here, and is
    never interpreted as authorization anywhere in the orchestrator.

G1 has NO network code: the only implementation reads local fixture files.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .. import errors

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_REPO = re.compile(r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+$")
_PATH = re.compile(r"^[A-Za-z0-9_./\-]+$")

PR_STATES = frozenset({"OPEN", "CLOSED", "MERGED"})
RUN_STATUSES = frozenset({"queued", "in_progress", "completed", "pending", "waiting", "requested"})

MAX_FILES = 300
MAX_RUNS = 50
MAX_JOBS_PER_RUN = 100
MAX_TEXT = 20_000
MAX_NAME = 200


@dataclass(frozen=True)
class PullRequestObservation:
    repository: str
    number: int
    state: str
    is_draft: bool
    base_ref: str
    head_ref: str
    head_sha: str
    base_sha: str
    title: str  # UNTRUSTED
    body: str  # UNTRUSTED (used only for injection scanning, never forwarded)
    files: tuple[str, ...]


@dataclass(frozen=True)
class JobObservation:
    job_id: int
    name: str
    status: str
    conclusion: str | None


@dataclass(frozen=True)
class WorkflowRunObservation:
    run_id: int
    workflow: str
    event: str
    status: str
    conclusion: str | None
    head_sha: str
    jobs: tuple[JobObservation, ...]


@runtime_checkable
class GitHubReadObserver(Protocol):
    """Read-only view of GitHub. Deliberately has no write/merge/ready method."""

    def get_pull_request(self, repository: str, number: int) -> PullRequestObservation: ...

    def get_workflow_runs(self, repository: str, head_sha: str) -> tuple[WorkflowRunObservation, ...]: ...

    def get_job_log(self, repository: str, job_id: int, *, max_bytes: int) -> str: ...


# --- strict parsing helpers -------------------------------------------------


def _bad(msg: str) -> errors.EvidenceInvalid:
    return errors.EvidenceInvalid(msg)


def _need_obj(value: Any, what: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _bad(f"{what} must be an object")
    return value


def _need_str(obj: dict[str, Any], key: str, *, max_len: int = MAX_NAME, allow_empty: bool = False) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise _bad(f"field {key} must be a non-empty string")
    if len(value) > max_len:
        raise _bad(f"field {key} exceeds {max_len} characters")
    return value


def _need_int(obj: dict[str, Any], key: str) -> int:
    value = obj.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise _bad(f"field {key} must be a positive integer")
    return value


def _need_sha(obj: dict[str, Any], key: str) -> str:
    value = _need_str(obj, key, max_len=40)
    if not _SHA40.match(value):
        raise _bad(f"field {key} must be a 40-char lowercase hex SHA")
    return value


def _opt_conclusion(obj: dict[str, Any]) -> str | None:
    value = obj.get("conclusion")
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 40:
        raise _bad("conclusion must be a short string or null")
    return value


def _read_json_file(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise errors.EvidenceIncomplete(f"missing fixture file: {path.name}") from None
    except OSError as exc:
        raise _bad(f"unreadable fixture file {path.name}: {exc.__class__.__name__}") from None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise _bad(f"fixture file {path.name} is not valid JSON") from None


def parse_pull_request(raw: Any) -> PullRequestObservation:
    obj = _need_obj(raw, "pull request")
    repository = _need_str(obj, "repository")
    if not _REPO.match(repository):
        raise _bad("repository must be owner/name")
    state = _need_str(obj, "state", max_len=10)
    if state not in PR_STATES:
        raise _bad(f"unknown PR state: {state!r}")
    is_draft = obj.get("is_draft")
    if not isinstance(is_draft, bool):
        raise _bad("is_draft must be a boolean")
    files_raw = obj.get("files")
    if not isinstance(files_raw, list):
        raise _bad("files must be a list")
    if len(files_raw) > MAX_FILES:
        raise errors.EvidenceTooLarge(f"PR file list exceeds {MAX_FILES}")
    files: list[str] = []
    for item in files_raw:
        if not isinstance(item, str) or not item or len(item) > 300 or not _PATH.match(item):
            raise _bad("PR file path is malformed")
        if item.startswith("/") or ".." in item.split("/"):
            raise _bad("PR file path must be repository-relative without traversal")
        files.append(item)
    return PullRequestObservation(
        repository=repository,
        number=_need_int(obj, "number"),
        state=state,
        is_draft=is_draft,
        base_ref=_need_str(obj, "base_ref"),
        head_ref=_need_str(obj, "head_ref"),
        head_sha=_need_sha(obj, "head_sha"),
        base_sha=_need_sha(obj, "base_sha"),
        title=_need_str(obj, "title", max_len=MAX_TEXT, allow_empty=True),
        body=_need_str(obj, "body", max_len=MAX_TEXT, allow_empty=True),
        files=tuple(files),
    )


def parse_workflow_runs(raw: Any) -> tuple[WorkflowRunObservation, ...]:
    obj = _need_obj(raw, "workflow runs document")
    runs_raw = obj.get("runs")
    if not isinstance(runs_raw, list):
        raise _bad("runs must be a list")
    if len(runs_raw) > MAX_RUNS:
        raise errors.EvidenceTooLarge(f"more than {MAX_RUNS} workflow runs")
    runs: list[WorkflowRunObservation] = []
    for r in runs_raw:
        ro = _need_obj(r, "workflow run")
        status = _need_str(ro, "status", max_len=20)
        if status not in RUN_STATUSES:
            raise _bad(f"unknown run status: {status!r}")
        jobs_raw = ro.get("jobs")
        if not isinstance(jobs_raw, list):
            raise _bad("jobs must be a list")
        if len(jobs_raw) > MAX_JOBS_PER_RUN:
            raise errors.EvidenceTooLarge(f"more than {MAX_JOBS_PER_RUN} jobs in a run")
        jobs: list[JobObservation] = []
        for j in jobs_raw:
            jo = _need_obj(j, "job")
            jstatus = _need_str(jo, "status", max_len=20)
            if jstatus not in RUN_STATUSES:
                raise _bad(f"unknown job status: {jstatus!r}")
            jobs.append(
                JobObservation(
                    job_id=_need_int(jo, "job_id"),
                    name=_need_str(jo, "name"),
                    status=jstatus,
                    conclusion=_opt_conclusion(jo),
                )
            )
        ids = [j.job_id for j in jobs]
        if len(set(ids)) != len(ids):
            raise _bad("duplicate job ids within a run")
        runs.append(
            WorkflowRunObservation(
                run_id=_need_int(ro, "run_id"),
                workflow=_need_str(ro, "workflow"),
                event=_need_str(ro, "event"),
                status=status,
                conclusion=_opt_conclusion(ro),
                head_sha=_need_sha(ro, "head_sha"),
                jobs=tuple(jobs),
            )
        )
    return tuple(runs)


# --- fixture-backed implementation -----------------------------------------


class FixtureGitHubObserver:
    """Reads observations from a local fixture directory. No network, ever.

    Layout::

        pull_request.json          # first get_pull_request call
        pull_request_after.json    # (optional) returned from the 2nd call on,
                                   # used to simulate the head moving mid-run
        workflow_runs.json
        job_logs/<job_id>.txt
    """

    def __init__(self, fixture_dir: Path | str) -> None:
        self._dir = Path(fixture_dir)
        self._pr_calls = 0

    def get_pull_request(self, repository: str, number: int) -> PullRequestObservation:
        self._pr_calls += 1
        name = "pull_request.json"
        after = self._dir / "pull_request_after.json"
        if self._pr_calls > 1 and after.is_file():
            name = "pull_request_after.json"
        pr = parse_pull_request(_read_json_file(self._dir / name))
        if pr.repository != repository or pr.number != number:
            raise _bad("fixture PR does not match the requested repository/number")
        return pr

    def get_workflow_runs(self, repository: str, head_sha: str) -> tuple[WorkflowRunObservation, ...]:
        doc = _read_json_file(self._dir / "workflow_runs.json")
        if _need_obj(doc, "workflow runs document").get("repository") != repository:
            raise _bad("fixture workflow runs do not match the requested repository")
        return parse_workflow_runs(doc)

    def get_job_log(self, repository: str, job_id: int, *, max_bytes: int) -> str:
        if not isinstance(job_id, int) or isinstance(job_id, bool) or job_id <= 0:
            raise _bad("job_id must be a positive integer")
        path = self._dir / "job_logs" / f"{job_id}.txt"
        try:
            with path.open("rb") as fh:
                data = fh.read(max_bytes + 1)
        except FileNotFoundError:
            raise errors.EvidenceIncomplete(f"no log available for job {job_id}") from None
        if len(data) > max_bytes:
            raise errors.EvidenceTooLarge(f"job {job_id} log exceeds {max_bytes} bytes")
        return data.decode("utf-8", errors="replace")
