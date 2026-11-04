"""A2-A G1: static + behavioral proof of the safety envelope.

These tests prove properties of the NEW modules by inspecting their source and
behavior: no network or process capability, no credential handling, no
merge/ready/deploy surface, a closed approval vocabulary, and unchanged A1
manifest fingerprints.
"""

from __future__ import annotations

import ast
import re
import socket
import subprocess
from pathlib import Path

import pytest

from scripts.orchestrator import errors, evidence, manifest as manifest_mod
from scripts.orchestrator.manifest import KNOWN_ACTIONS, load_manifest

from tests.orchestrator import a2a_support as s

PKG = Path(__file__).resolve().parents[2] / "scripts" / "orchestrator"
NEW_MODULES = [
    PKG / "evidence.py",
    PKG / "evidence_review.py",
    PKG / "adapters" / "github_observer.py",
    PKG / "adapters" / "openai_evidence_reviewer.py",
]

ALLOWED_IMPORTS = {
    "__future__", "dataclasses", "typing", "json", "re", "hashlib", "hmac", "os", "time", "pathlib",
}
FORBIDDEN_IMPORTS = {
    "socket", "ssl", "subprocess", "urllib", "http", "requests", "httpx", "aiohttp", "openai",
    "boto3", "botocore", "asyncio", "multiprocessing", "ctypes", "ftplib", "smtplib", "webbrowser",
}
FORBIDDEN_SOURCE_TOKENS = [
    "os.environ", "getenv", "OPENAI_API_KEY", "KIRO_API_KEY", "GITHUB_TOKEN", "Authorization:",
    "Bearer ", "api_key", "subprocess", "socket.", "urlopen",
]
FORBIDDEN_NAME_WORDS = ("merge", "mark_ready", "ready_for", "deploy", "approve", "grant", "push", "comment", "terraform")


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _imported_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(_source(path))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("path", NEW_MODULES, ids=lambda p: p.name)
def test_new_modules_import_only_the_standard_library_allowlist(path):
    roots = _imported_roots(path)
    assert not roots & FORBIDDEN_IMPORTS, roots & FORBIDDEN_IMPORTS
    assert roots <= ALLOWED_IMPORTS, roots - ALLOWED_IMPORTS


@pytest.mark.parametrize("path", NEW_MODULES, ids=lambda p: p.name)
def test_new_modules_contain_no_credential_or_network_handling(path):
    text = _source(path)
    for token in FORBIDDEN_SOURCE_TOKENS:
        assert token not in text, f"{path.name} contains {token!r}"


@pytest.mark.parametrize("path", NEW_MODULES, ids=lambda p: p.name)
def test_new_modules_define_no_merge_ready_deploy_or_write_operations(path):
    names = [
        node.name
        for node in ast.walk(ast.parse(_source(path)))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    for name in names:
        lowered = name.lower()
        assert not any(word in lowered for word in FORBIDDEN_NAME_WORDS), name


def test_the_test_environment_really_blocks_network_and_processes():
    with pytest.raises(RuntimeError):
        socket.create_connection(("example.com", 443))
    with pytest.raises(RuntimeError):
        subprocess.run(["git", "--version"])


# --- manifest vocabulary + backward compatibility ---------------------------


def test_known_actions_are_a_closed_set_without_merge_style_actions():
    assert KNOWN_ACTIONS == {"implement", "review", "correct", "draft_pr", "observe_pr", "review_evidence"}


@pytest.mark.parametrize(
    "bad_action",
    ["merge", "mark_ready", "ready_for_review", "deploy", "terraform_apply", "approve", "grant_permission", "push_main", "OBSERVE_PR", "observe"],
)
def test_forbidden_or_unknown_actions_cannot_be_authorized(config, write_manifest, bad_action):
    path = write_manifest(**s.pr_overrides(allowed_actions=["observe_pr", bad_action]))
    with pytest.raises(errors.ApprovalInvalid):
        load_manifest(path, config)


def test_a1_manifest_fingerprint_is_unchanged_by_the_a2a_extension(config, write_manifest):
    loaded = load_manifest(write_manifest(), config)
    assert loaded.approved_pull_requests == ()
    assert loaded.fingerprint() == s.A1_MANIFEST_GOLDEN_FINGERPRINT


def test_pr_approvals_are_bound_into_the_fingerprint(config, write_manifest):
    base = load_manifest(write_manifest(**s.pr_overrides()), config).fingerprint()
    assert base != s.A1_MANIFEST_GOLDEN_FINGERPRINT

    def fp(**entry_changes):
        entry = dict(s.pr_overrides()["approved_pull_requests"][0])
        entry.update(entry_changes)
        path = write_manifest(filename="x.json", **s.pr_overrides(approved_pull_requests=[entry]))
        return load_manifest(path, config).fingerprint()

    assert fp() == base
    assert fp(head_sha="1" * 40) != base
    assert fp(baseline_ids_sha256="2" * 64) != base
    assert fp(declared_replacements={}) != base
    assert fp(number=63) != base


BAD_APPROVALS = {
    "empty_list": [],
    "not_a_list": {"number": 62},
    "entry_not_object": ["62"],
    "unknown_key": [{"number": 62, "head_sha": s.HEAD, "approve": True}],
    "bool_number": [{"number": True, "head_sha": s.HEAD}],
    "zero_number": [{"number": 0, "head_sha": s.HEAD}],
    "duplicate_number": [{"number": 62, "head_sha": s.HEAD}, {"number": 62, "head_sha": s.HEAD}],
    "short_head": [{"number": 62, "head_sha": "abc"}],
    "upper_head": [{"number": 62, "head_sha": "A" * 40}],
    "bad_baseline_hash": [{"number": 62, "head_sha": s.HEAD, "baseline_ids_sha256": "xyz"}],
    "bad_replacements_type": [{"number": 62, "head_sha": s.HEAD, "declared_replacements": ["a"]}],
    "empty_replacement_targets": [{"number": 62, "head_sha": s.HEAD, "declared_replacements": {"a::b": []}}],
    "non_string_replacement": [{"number": 62, "head_sha": s.HEAD, "declared_replacements": {"a::b": [1]}}],
    "too_many": [{"number": n, "head_sha": s.HEAD} for n in range(1, 52)],
}


@pytest.mark.parametrize("name", sorted(BAD_APPROVALS))
def test_malformed_pull_request_approvals_are_rejected(config, write_manifest, name):
    path = write_manifest(**s.pr_overrides(approved_pull_requests=BAD_APPROVALS[name]))
    with pytest.raises(errors.ApprovalInvalid):
        load_manifest(path, config)


def test_manifest_exposes_no_way_to_approve_a_head_other_than_the_pinned_one(config, write_manifest):
    loaded = load_manifest(write_manifest(**s.pr_overrides()), config)
    assert loaded.assert_pull_request_approved(s.PR, s.HEAD).number == s.PR
    with pytest.raises(errors.ObservedHeadChanged):
        loaded.assert_pull_request_approved(s.PR, "1" * 40)
    with pytest.raises(errors.PullRequestNotApproved):
        loaded.assert_pull_request_approved(99, s.HEAD)


# --- fixture hygiene --------------------------------------------------------


def test_fixtures_contain_no_secrets_or_personal_data():
    secret_like = re.compile(r"sk-|ghp_|gho_|ghs_|github_pat_|AKIA|ASIA|eyJ|xox[bap]-|-----BEGIN|ya29\.")
    count = 0
    for path in s.FIX.rglob("*"):
        if path.is_file():
            count += 1
            text = path.read_text(encoding="utf-8")
            assert not secret_like.search(text), path.name
            assert "@" not in text, f"{path.name} contains an '@' (possible email)"
    assert count >= 5


def test_baseline_fixture_ids_are_all_valid_and_unique():
    ids = s.baseline_ids()
    assert len(ids) == len(set(ids)) == s.BASELINE_GOLDEN_COUNT
    assert all(evidence.is_valid_node_id(i) for i in ids)
