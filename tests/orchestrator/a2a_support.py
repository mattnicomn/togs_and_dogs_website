"""Shared helpers for the A2-A G1 offline tests (fixtures, builders, mutators).

Everything here is offline. The PR #62 fixture is sanitized public metadata and
test ids; it contains no credentials, tenant data or customer data.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable

from scripts.orchestrator import evidence
from scripts.orchestrator.acl_guard import OfflineFixtureApprovalGuard
from scripts.orchestrator.adapters.github_observer import FixtureGitHubObserver
from scripts.orchestrator.adapters.openai_evidence_reviewer import (
    DeterministicMockTransport,
    OpenAIEvidenceReviewer,
    ReviewerConfig,
)
from scripts.orchestrator.evidence_review import EvidenceRequest, EvidenceReviewRunner
from scripts.orchestrator.manifest import ApprovedPullRequest

FIX = Path(__file__).parent / "fixtures" / "a2a" / "pr62"

REPO = "mattnicomn/togs_and_dogs_website"
PR = 62
HEAD = "057de19c01fbe24883192da3c68fbfda3bfadf1f"
MAIN = "8fe7fa78ad707ac67a05d29059d2771a9aa256c8"
BRANCH = "test/c3-1-combined-backend-test-isolation"
BACKEND_JOB = 126691735549
WEB_JOB = 126691735906
BACKEND_RUN = 41863562592

# Independently computed (original A1 formula) fingerprint of the A1 synthetic
# manifest: proves the A2-A manifest extension did not change A1 fingerprints.
A1_MANIFEST_GOLDEN_FINGERPRINT = "301a8ae8e9076deb3e619ad9969c93c8437c24bfaaf2e719aa72e7f89a9599cd"
BASELINE_GOLDEN_COUNT = 74
BASELINE_GOLDEN_SHA256 = "794e45018c4c35ca07e9c051b14007c56f5b3d94c3574cc0aca6eed657e35f96"

FAILED_6 = [
    "tests/backend/test_r18l_client_booking_limits.py::test_booking_limit_below_limit_allowed",
    "tests/backend/test_r18l_client_booking_limits.py::test_entitlement_enforcement_flag_behavior",
    "tests/backend/test_r7a_optional_email.py::test_duplicate_and_protected_checks_work_when_email_present",
    "tests/backend/test_r7a_optional_email.py::test_profile_only_client_can_be_created_without_email",
    "tests/backend/test_r7a_optional_email.py::test_public_intake_still_requires_email",
    "tests/backend/test_r7e_multi_day_jobs.py::test_multi_day_jobs_inherit_visit_window",
]

PLATFORM_OLD = (
    "tests/backend/test_platform_preview_iam.py::TestPlatformPreviewIAMStaticAnalysis::"
    "test_api_gateway_exposes_only_authenticated_validate_and_preview_routes"
)
PLATFORM_NEW = [
    "tests/backend/test_platform_preview_iam.py::TestPlatformPreviewIAMStaticAnalysis::"
    "test_api_gateway_onboarding_routes_are_deferred_not_in_active_graph",
    "tests/backend/test_platform_preview_iam.py::TestPlatformPreviewIAMStaticAnalysis::"
    "test_deferred_preview_lambda_scopes_invoke_only_to_validate_and_preview",
]
CALLBACK_OLD = (
    "tests/backend/test_r19k_tenant_isolation.py::TestGoogleCalendarTenantGate::"
    "test_non_default_tenant_callback_blocked"
)
CALLBACK_NEW = [
    "tests/backend/test_r19k_tenant_isolation.py::TestGoogleCalendarTenantGate::"
    "test_non_default_tenant_callback_malformed_state_rejected",
    "tests/backend/test_r19k_tenant_isolation.py::TestGoogleCalendarTenantGate::"
    "test_non_default_tenant_callback_valid_state_unbound_denied",
]
REPLACEMENTS = {PLATFORM_OLD: PLATFORM_NEW, CALLBACK_OLD: CALLBACK_NEW}


def baseline_ids() -> list[str]:
    text = (FIX / "baseline_failed_ids.txt").read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def make_approval(baseline: list[str] | None = None, replacements: dict[str, list[str]] | None = None) -> ApprovedPullRequest:
    ids = baseline if baseline is not None else baseline_ids()
    repl = REPLACEMENTS if replacements is None else replacements
    return ApprovedPullRequest(
        number=PR,
        head_sha=HEAD,
        baseline_ids_sha256=evidence.ids_sha256(ids),
        declared_replacements=tuple(sorted((k, tuple(v)) for k, v in repl.items())),
    )


def pr_overrides(**extra: Any) -> dict[str, Any]:
    """Overrides for the conftest ``write_manifest`` factory: a PR #62 manifest."""

    data: dict[str, Any] = dict(
        scope_id="A2A_G1_PR62_REVIEW",
        repository=REPO,
        base_sha=MAIN,
        target_branch=BRANCH,
        base_branch="main",
        allowed_paths=["tests/backend/**"],
        allowed_actions=["observe_pr", "review_evidence"],
        approved_pull_requests=[
            {
                "number": PR,
                "head_sha": HEAD,
                "baseline_ids_sha256": evidence.ids_sha256(baseline_ids()),
                "declared_replacements": REPLACEMENTS,
            }
        ],
    )
    data.update(extra)
    return data


def make_request(**kw: Any) -> EvidenceRequest:
    values: dict[str, Any] = dict(
        scope_id="A2A_G1_PR62_REVIEW",
        repository=REPO,
        base_sha=MAIN,
        target_branch=BRANCH,
        pr_number=PR,
        expected_head_sha=HEAD,
    )
    values.update(kw)
    return EvidenceRequest(**values)


def default_reviewer_config(**kw: Any) -> ReviewerConfig:
    values: dict[str, Any] = dict(
        model="mock-model-pinned",
        price_in_per_mtok=1.0,
        price_out_per_mtok=4.0,
        timeout_s=30.0,
        max_attempts=2,
        max_output_tokens=1000,
    )
    values.update(kw)
    return ReviewerConfig(**values)


def make_runner(
    config: Any,
    manifest: Any,
    fixture_dir: Path = FIX,
    *,
    transport: Any = None,
    reviewer_cfg: ReviewerConfig | None = None,
    baseline: list[str] | None = None,
    governor: Any = None,
    sleep: Callable[[float], None] | None = None,
    clock: Callable[[], float] | None = None,
    approval_guard: Any = None,
):
    transport = transport if transport is not None else DeterministicMockTransport()
    kwargs: dict[str, Any] = {"sleep": sleep or (lambda s: None)}
    if clock is not None:
        kwargs["clock"] = clock
    reviewer = OpenAIEvidenceReviewer(transport, reviewer_cfg or default_reviewer_config(), **kwargs)
    runner = EvidenceReviewRunner(
        config=config,
        manifest=manifest,
        observer=FixtureGitHubObserver(fixture_dir),
        reviewer=reviewer,
        baseline_ids=baseline if baseline is not None else baseline_ids(),
        approval_guard=approval_guard if approval_guard is not None else OfflineFixtureApprovalGuard(),
        governor=governor,
    )
    return runner, transport


# --- log / packet builders --------------------------------------------------


def make_backend_log(failed_ids: list[str], *, passed: int = 2141, skipped: int = 0, extra_lines: tuple[str, ...] = ()) -> str:
    n = len(failed_ids)
    total = n + passed + skipped
    ts = "2026-01-01T00:00:00.0000000Z"
    lines = [f"{ts} ============================= test session starts ==============================",
             f"{ts} collected {total} items",
             f"{ts} =========================== short test summary info ============================"]
    lines += [f"{ts} FAILED {i} - assert 1 == 2" for i in failed_ids]
    lines += list(extra_lines)
    parts = f"{n} failed, {passed} passed" + (f", {skipped} skipped" if skipped else "")
    lines.append(f"{ts} ================ {parts}, 3 warnings in 1.00s ================")
    return "\n".join(lines) + "\n"


def build_fixture_packet(
    *,
    failed_ids: list[str] | None = None,
    backend_log: str | None = None,
    pr: Any = None,
    baseline: list[str] | None = None,
    approval: ApprovedPullRequest | None = None,
    fixture_dir: Path = FIX,
) -> dict[str, Any]:
    obs = FixtureGitHubObserver(fixture_dir)
    pr = pr or obs.get_pull_request(REPO, PR)
    runs = obs.get_workflow_runs(REPO, HEAD)
    run = runs[0]
    backend_job = next(j for j in run.jobs if j.job_id == BACKEND_JOB)
    if backend_log is None:
        if failed_ids is not None:
            backend_log = make_backend_log(failed_ids)
        else:
            backend_log = obs.get_job_log(REPO, BACKEND_JOB, max_bytes=evidence.MAX_LOG_BYTES)
    web_log = obs.get_job_log(REPO, WEB_JOB, max_bytes=evidence.MAX_LOG_BYTES)
    base = baseline if baseline is not None else baseline_ids()
    return evidence.build_packet(
        pr=pr,
        approval=approval or make_approval(base),
        runs=runs,
        backend=(run, backend_job),
        backend_log=backend_log,
        web_log=web_log,
        baseline_ids=base,
        observer_name="fixture",
    )


# --- fixture mutators -------------------------------------------------------


def fixture_copy(tmp_path: Path) -> Path:
    dst = tmp_path / "fx"
    shutil.copytree(FIX, dst)
    return dst


def edit_json(fx: Path, name: str, fn: Callable[[Any], None]) -> None:
    path = fx / name
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def edit_text(fx: Path, rel: str, fn: Callable[[str], str]) -> None:
    path = fx / rel
    path.write_text(fn(path.read_text(encoding="utf-8")), encoding="utf-8")


class SimulatedCrash(BaseException):
    """Stands in for the process dying mid-call (not caught by the orchestrator)."""
