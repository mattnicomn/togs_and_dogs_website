"""G1.6-C3-G0: the credential-free probe, sacrificial-test specs, preflight and
cleanup - ALL OFFLINE and INERT. No agent execution, no task, no host change.

Filesystem tests run only inside pytest temp directories (never a host test dir).
"""

from __future__ import annotations

import ast
import dataclasses
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.orchestrator import acl_guard as g
from scripts.orchestrator import c3_package as pkg
from scripts.orchestrator import c3_probe as probe
from scripts.orchestrator import c3_runtime as rt
from scripts.orchestrator import errors

from tests.orchestrator import test_a2a_acl_guard as base
from tests.orchestrator import test_a2a_acl_hardening as hard
from tests.orchestrator import test_c3_runtime as rtt

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
OWNER, AGENT = base.OWNER, base.AGENT
VOL_GUID = base.VOL_GUID
PROD = {
    "root": "P:\\", "approvals": "P:\\approvals", "bin": "P:\\bin", "worktrees": "P:\\worktrees",
    "runtime": "P:\\runtime", "evidence": "P:\\evidence", "vault_dir": "D:\\PetCareVault",
    "vhdx": "D:\\PetCareVault\\PetCareAgent.vhdx",
}
CONTAINER = "P:\\_c3"
FILES = {"scripts/orchestrator/a.py": b"print('a')\n"}
COMMIT = "a6b6c66cef916eec4182053a398a9d2106eda5ff"
LISTING = f"100644 blob {pkg.git_blob_id(FILES['scripts/orchestrator/a.py'])}\tscripts/orchestrator/a.py\n"
MANIFEST = pkg.build_manifest(FILES, source_commit=COMMIT, tree_listing=LISTING)
OBSERVED_TREE = {f.path: (f.sha256, f.size) for f in MANIFEST.files}
# The synthetic trusted interpreter tree (from the runtime tests) and its owner-pinned digest.
INTERP_HASHES = dict(rtt.OBSERVED)
INTERP_DIGEST = rt.interpreter_tree_digest(INTERP_HASHES)
INTERP_SCAN = {k: (v, len(rtt.TREE[k])) for k, v in INTERP_HASHES.items()}


@pytest.fixture(autouse=True)
def _no_real_host_tree_reads(monkeypatch):
    """Hermetic: the ENFORCED live re-scan must never read the real P:/D: volumes
    from a test. Temp-directory scans (CLI tests) still use the real scanner."""

    real = pkg.scan_tree

    def guarded(root, **kw):
        if isinstance(root, str) and len(root) >= 2 and root[1] == ":" and root[0].upper() in "PD":
            raise errors.PackageIntegrityFailure("test isolation: host volume scan refused")
        return real(root, **kw)

    monkeypatch.setattr(pkg, "scan_tree", guarded)


def approval_doc(**over) -> dict:
    doc = {
        "schema": probe.APPROVAL_SCHEMA, "scope_id": probe.SCOPE_ID, "phase": "NEGATIVE",
        "authorized_by": "Matthew", "authorized_at": "2026-11-07T11:00:00Z", "expires_at": "2026-11-07T18:00:00Z",
        "expected_agent_sid": AGENT, "trusted_owner_sids": [OWNER, base.ADMINS],
        "trusted_volume": {"guid": VOL_GUID, "label": "PetCareAgent", "serial": 0xABCD1234},
        "container": CONTAINER, "production_paths": dict(PROD), "package_manifest_sha256": MANIFEST.digest(),
        "min_free_bytes": {"P:\\": 5 * 2**30}, "negative_authorized": True,
        "interpreter_tree_sha256": INTERP_DIGEST, "max_run_seconds": probe.MAX_RUN_SECONDS,
    }
    doc.update(over)
    return doc


def parse(**over) -> probe.ProbeApproval:
    return probe.parse_probe_approval(json.dumps(approval_doc(**over)).encode(), now=NOW)


# --- approval ------------------------------------------------------------------------------------------


def test_a_well_formed_approval_is_accepted_and_carries_typed_values():
    a = parse()
    assert a.phase == "NEGATIVE" and a.negative_authorized and a.trusted_volume.volume_guid == VOL_GUID
    assert a.phase_allows("PLAN") and a.phase_allows("READONLY") and a.phase_allows("NEGATIVE")
    assert not parse(phase="READONLY", negative_authorized=False).phase_allows("NEGATIVE")


def test_a_missing_approval_is_refused():
    with pytest.raises(errors.ApprovalMissing):
        probe.parse_probe_approval(None, now=NOW)


@pytest.mark.parametrize(
    "over,exc",
    [
        ({"scope_id": "OTHER"}, errors.ScopeMismatch),
        ({"schema": "x"}, errors.ApprovalInvalid),
        ({"phase": "EXECUTE"}, errors.ApprovalInvalid),
        ({"expires_at": "2026-11-07T11:59:59Z"}, errors.ApprovalInvalid),
        ({"expires_at": "2026-11-09T12:00:00Z"}, errors.ApprovalInvalid),
        ({"expires_at": "2026-11-07T18:00:00"}, errors.ApprovalInvalid),
        ({"expires_at": "tomorrow"}, errors.ApprovalInvalid),
        ({"phase": "READONLY"}, errors.ApprovalInvalid),                      # negative_authorized without NEGATIVE
        ({"negative_authorized": False}, errors.ApprovalInvalid),             # NEGATIVE without authorization
        ({"negative_authorized": "yes"}, errors.ApprovalInvalid),
        ({"expected_agent_sid": "alice"}, errors.ApprovalInvalid),
        ({"trusted_owner_sids": []}, errors.ApprovalInvalid),
        ({"trusted_owner_sids": ["nope"]}, errors.ApprovalInvalid),
        ({"trusted_volume": {"guid": "P:", "label": "x", "serial": 1}}, errors.ApprovalInvalid),
        ({"trusted_volume": {"guid": VOL_GUID}}, errors.ApprovalInvalid),
        ({"package_manifest_sha256": "xyz"}, errors.ApprovalInvalid),
        ({"min_free_bytes": {}}, errors.ApprovalInvalid),
        ({"min_free_bytes": {"P:\\": 0}}, errors.ApprovalInvalid),
        ({"authorized_by": " "}, errors.ApprovalInvalid),
        ({"production_paths": {k: v for k, v in PROD.items() if k != "approvals"}}, errors.ApprovalInvalid),
        ({"production_paths": dict(PROD, extra="C:\\x")}, errors.ApprovalInvalid),
        ({"unexpected": 1}, errors.ApprovalInvalid),
    ],
)
def test_malformed_expired_or_inconsistent_approvals_are_refused(over, exc):
    with pytest.raises(exc):
        parse(**over)


@pytest.mark.parametrize("raw", [b"\xff", b"nope", b"[]", b"{}"])
def test_non_object_approvals_are_refused(raw):
    with pytest.raises(errors.ApprovalInvalid):
        probe.parse_probe_approval(raw, now=NOW)


# --- target policy: production is untouchable ------------------------------------------------------------


def policy(**kw) -> probe.TargetPolicy:
    # The bare volume root is probed read-only by name but is not a "production root"
    # (it would contain the disposable container).
    roots = tuple(v for k, v in PROD.items() if k != "root")
    return probe.TargetPolicy(container=CONTAINER, production_roots=roots, **kw)


def test_target_classification():
    p = policy()
    assert p.classify("P:\\approvals\\x.json") is probe.TargetClass.PRODUCTION
    assert p.classify("P:\\") is probe.TargetClass.OUTSIDE
    assert p.is_probe_readable("P:\\") and p.is_probe_readable("P:\\approvals") and not p.is_probe_readable("C:\\Users\\mattn")
    assert not p.is_probe_readable("P:\\_c3\\twin") and not p.is_probe_readable("P:\\somewhere")
    assert p.classify("D:\\PetCareVault\\PetCareAgent.vhdx") is probe.TargetClass.PRODUCTION
    assert p.classify("P:\\_c3") is probe.TargetClass.CONTAINER
    assert p.classify("p:\\_C3\\twin\\approvals") is probe.TargetClass.DISPOSABLE
    assert p.classify("C:\\Users\\mattn") is probe.TargetClass.OUTSIDE


@pytest.mark.parametrize("rel", ["twin/approvals/x", "twin/worktrees/junction", "escape"])
def test_only_container_relative_paths_resolve_as_disposable(rel):
    assert policy().resolve_disposable(rel).lower().startswith("p:\\_c3\\")


@pytest.mark.parametrize(
    "rel",
    ["", "/abs", "\\abs", "..", "../approvals", "twin/../../approvals", "twin\\x", "P:\\approvals\\x", "twin/x:ads", "twin/x.",
     "twin/PROGRA~1", "../_c3-other/x", "twin/CON"],
)
def test_escapes_and_unsafe_forms_never_resolve_as_disposable(rel):
    with pytest.raises(errors.SacrificialTargetRefused):
        policy().resolve_disposable(rel)


def test_the_container_itself_and_its_siblings_are_not_disposable_targets():
    with pytest.raises(errors.SacrificialTargetRefused):
        policy().resolve_disposable("")
    assert policy().classify("P:\\_c3-other\\x") is probe.TargetClass.OUTSIDE


@pytest.mark.parametrize(
    "container,prods",
    [
        ("P:\\worktrees\\_c3", ("P:\\worktrees",)),     # inside a production root
        ("P:\\_c3", ("P:\\",)),                          # production root contains the container
        ("P:\\twin", ("P:\\approvals",)),                # not named _c3*
        ("P:\\x\\_c3", ("P:\\approvals",)),              # not top-level
        ("_c3", ("P:\\approvals",)),                     # relative
        ("P:\\_c3", ()),                                  # no production roots named
        ("P:\\_c3:ads", ("P:\\approvals",)),
    ],
)
def test_an_unsafe_container_configuration_is_rejected(container, prods):
    with pytest.raises(ValueError):
        probe.TargetPolicy(container=container, production_roots=prods)


# --- catalogue -----------------------------------------------------------------------------------------------


def test_the_default_catalogue_is_valid_and_never_mutates_production():
    probe.validate_case_catalogue(probe.NEGATIVE_CASES)
    for c in probe.NEGATIVE_CASES:
        if c.production_key is not None:
            assert c.op is probe.Op.OPEN_ACCESS and c.expected == "DENIED"
        else:
            assert not c.target.startswith(("P:", "D:", "C:", "/"))
    assert {c.expected for c in probe.NEGATIVE_CASES} == {"DENIED", "ALLOWED"}
    assert any(c.residual for c in probe.NEGATIVE_CASES)


@pytest.mark.parametrize(
    "case",
    [
        probe.NegativeCase("X1", probe.Op.CREATE_FILE, "", "DENIED", "mutation of production", production_key="approvals", access_mask=2),
        probe.NegativeCase("X2", probe.Op.OPEN_ACCESS, "", "DENIED", "unknown key", production_key="home", access_mask=2),
        probe.NegativeCase("X3", probe.Op.OPEN_ACCESS, "", "ALLOWED", "production allowed?", production_key="approvals", access_mask=2),
        probe.NegativeCase("X4", probe.Op.OPEN_ACCESS, "", "DENIED", "no mask", production_key="approvals"),
        probe.NegativeCase("X5", probe.Op.OPEN_ACCESS, "twin", "DENIED", "no mask on twin"),
        probe.NegativeCase("X6", probe.Op.OPEN_ACCESS, "twin", "MAYBE", "bad expectation", access_mask=2),
    ],
)
def test_bad_catalogue_entries_are_refused(case):
    with pytest.raises(errors.SacrificialTargetRefused):
        probe.validate_case_catalogue([case])


def test_duplicate_case_ids_are_refused():
    c = probe.NEGATIVE_CASES[0]
    with pytest.raises(errors.SacrificialTargetRefused):
        probe.validate_case_catalogue([c, c])


# --- the twin specification, evaluated by the real boundary guard (mocked descriptors) ---------------------------


def twin_guard_backend(mutate=None) -> "base.FakeBackend":
    nodes = probe.twin_security(OWNER, AGENT, OWNER, CONTAINER)
    nodes["P:\\"] = g.NodeSecurity("P:\\", OWNER, base.owner_aces(inherited=False), is_dir=True)
    if mutate:
        mutate(nodes)
    vol = dataclasses.replace(base.GOOD_VOLUME, mount_root="P:\\")
    return base.FakeBackend(nodes=nodes, volume=vol)


POLICY_G = g.BoundaryPolicy(
    trusted_owner_sids=frozenset({OWNER, base.ADMINS}), expected_agent_sid=AGENT,
    trusted_volumes=(g.VolumeBinding(VOL_GUID, label="PetCareAgent", serial=0xABCD1234),),
)


def test_twin_spec_gives_the_agent_exactly_the_production_rights():
    nodes = probe.twin_security(OWNER, AGENT, OWNER, CONTAINER)
    ids = frozenset({AGENT})
    for node in probe.TWIN_NODES:
        path = CONTAINER if not node.rel else CONTAINER + "\\" + node.rel.replace("/", "\\")
        assert g._effective_allow_mask(nodes[path], ids) == probe.twin_expected_agent_mask(node)
    assert probe.AGENT_RX == 0x1200A9 and probe.AGENT_MODIFY == 0x1301BF


@pytest.mark.parametrize("rel,accepted", [("twin\\approvals", True), ("twin\\bin", True), ("twin\\worktrees", False), ("twin\\runtime", False), ("twin\\evidence", False)])
def test_the_boundary_guard_accepts_only_the_protected_twin_directories(rel, accepted):
    guard = g.MockedDescriptorApprovalGuard(POLICY_G, twin_guard_backend())
    path = CONTAINER + "\\" + rel
    if accepted:
        assert guard.verify(None, path).nodes_checked == 4  # dir, twin, _c3, P:\
    else:
        with pytest.raises(errors.ApprovalBoundaryViolation):
            guard.verify(None, path)


def test_an_agent_writable_twin_approvals_would_be_caught_by_the_guard():
    def widen(nodes):
        key = CONTAINER + "\\twin\\approvals"
        nodes[key] = dataclasses.replace(nodes[key], aces=nodes[key].aces + (g.Ace(AGENT, probe.AGENT_MODIFY),))

    guard = g.MockedDescriptorApprovalGuard(POLICY_G, twin_guard_backend(widen))
    with pytest.raises(errors.ApprovalBoundaryViolation):
        guard.verify(None, CONTAINER + "\\twin\\approvals")


def test_canary_files_are_synthetic_and_carry_no_authority():
    assert b"canary" in probe.CANARY_APPROVAL and b"no authority" in probe.CANARY_APPROVAL
    for n in probe.TWIN_NODES:
        assert n.rel == "" or n.rel.startswith("twin")


# --- executing the negative cases -------------------------------------------------------------------------------------


class FakeExecutor:
    def __init__(self, script=None):
        self.calls = []
        self.script = script or {}

    def attempt(self, op, path, aux, access_mask):
        self.calls.append((op, path, aux, access_mask))
        for case in probe.NEGATIVE_CASES:
            if (case.op is op and case.production_key is None and case.access_mask == access_mask
                    and path.lower().endswith("\\" + case.target.replace("/", "\\").lower())):
                return self.script.get(case.case_id, self._default(case))
        for case in probe.NEGATIVE_CASES:
            if case.production_key and path.lower() == PROD[case.production_key].lower() and access_mask == case.access_mask:
                return self.script.get(case.case_id, self._default(case))
        raise AssertionError(f"unmapped attempt {op} {path}")

    @staticmethod
    def _default(case):
        return probe.AttemptResult(True) if case.expected == "ALLOWED" else probe.AttemptResult(False, True, "denied")


def run_cases(executor, approval=None, cases=None):
    return probe.run_negative_cases(
        probe.NEGATIVE_CASES if cases is None else cases, approval=approval or parse(), policy=policy(), executor=executor, now=NOW)


def test_all_cases_pass_when_the_environment_behaves():
    ex = FakeExecutor()
    out = run_cases(ex)
    assert len(out) == len(probe.NEGATIVE_CASES) and all(o.ok for o in out)
    mutating = [c for c in ex.calls if c[0] in probe.MUTATING_OPS]
    assert mutating and all(c[1].lower().startswith("p:\\_c3\\") for c in mutating)
    assert all((c[2] is None) or c[2].lower().startswith("p:\\_c3\\") for c in ex.calls)


def test_unexpected_access_success_stops_immediately():
    ex = FakeExecutor({"N08": probe.AttemptResult(True)})
    with pytest.raises(errors.ProbeAborted) as e:
        run_cases(ex)
    assert "UNEXPECTED_ACCESS_SUCCESS N08" in e.value.detail
    assert len(ex.calls) == 8  # nothing after the first violation is attempted


def test_a_failed_positive_control_stops_the_run():
    ex = FakeExecutor({"N17": probe.AttemptResult(False, True, "denied")})
    with pytest.raises(errors.ProbeAborted) as e:
        run_cases(ex)
    assert "CASE_FAILED N17" in e.value.detail


def test_a_non_access_failure_is_not_counted_as_a_denial():
    ex = FakeExecutor({"N09": probe.AttemptResult(False, False, "FileNotFoundError")})
    with pytest.raises(errors.ProbeAborted) as e:
        run_cases(ex)
    assert "observed OTHER_ERROR" in e.value.detail


@pytest.mark.parametrize("over", [{"phase": "READONLY", "negative_authorized": False}, {"phase": "PLAN", "negative_authorized": False}])
def test_no_operation_is_dispatched_without_negative_authorization(over):
    ex = FakeExecutor()
    with pytest.raises(errors.ApprovalInvalid):
        run_cases(ex, approval=parse(**over))
    assert ex.calls == []


def test_an_expired_approval_dispatches_nothing():
    ex = FakeExecutor()
    with pytest.raises(errors.ApprovalInvalid):
        probe.run_negative_cases(probe.NEGATIVE_CASES, approval=parse(), policy=policy(), executor=ex, now=NOW + timedelta(days=2))
    assert ex.calls == []


@pytest.mark.parametrize(
    "bad_case",
    [
        probe.NegativeCase("B1", probe.Op.CREATE_FILE, "../approvals/x", "DENIED", "escape"),
        probe.NegativeCase("B2", probe.Op.DELETE_FILE, "twin/../../approvals/x", "DENIED", "escape"),
        probe.NegativeCase("B3", probe.Op.CREATE_FILE, "P:\\approvals\\x", "DENIED", "absolute production path"),
        probe.NegativeCase("B4", probe.Op.RENAME, "twin/a", "DENIED", "aux escape", aux="../approvals/stolen"),
        probe.NegativeCase("B5", probe.Op.CREATE_FILE, "", "DENIED", "container itself"),
        probe.NegativeCase("B6", probe.Op.CREATE_FILE, "twin/x:ads", "DENIED", "stream"),
    ],
)
def test_unauthorized_real_directory_mutation_requests_are_refused_before_any_call(bad_case):
    ex = FakeExecutor()
    good_first = list(probe.NEGATIVE_CASES[:3])
    with pytest.raises(errors.SacrificialTargetRefused):
        run_cases(ex, cases=good_first + [bad_case])
    assert ex.calls == []  # even the valid cases before it did not run


def test_a_production_probe_whose_path_is_not_production_is_refused():
    approval = dataclasses.replace(parse(), production_paths=dict(PROD, approvals="C:\\Users\\mattn"))
    ex = FakeExecutor()
    with pytest.raises(errors.SacrificialTargetRefused):
        run_cases(ex, approval=approval)
    assert ex.calls == []


# --- the real OS executor (pytest temp dirs only) --------------------------------------------------------------------------


class TmpPolicy(probe.TargetPolicy):
    """TEST-ONLY: lets a container live inside a pytest temp dir (never top-level)."""

    _top_level_required = False


def native_policy(tmp_path: Path) -> probe.TargetPolicy:
    prod = tmp_path / "prod"
    prod.mkdir(exist_ok=True)
    return TmpPolicy(
        container=str(tmp_path / "_c3"), production_roots=(str(prod),),
        platform="nt" if os.name == "nt" else "posix",
    )


def test_the_os_executor_refuses_mutation_of_production_and_outside_paths(tmp_path):
    pol = native_policy(tmp_path)
    victim = tmp_path / "prod" / "approvals.json"
    victim.write_text("real")
    outside = tmp_path / "elsewhere.txt"
    ex = probe.OsOperationExecutor(pol)
    for op in (probe.Op.CREATE_FILE, probe.Op.DELETE_FILE, probe.Op.OVERWRITE_FILE, probe.Op.CREATE_DIR):
        with pytest.raises(errors.SacrificialTargetRefused):
            ex.attempt(op, str(victim), None, None)
        with pytest.raises(errors.SacrificialTargetRefused):
            ex.attempt(op, str(outside), None, None)
    with pytest.raises(errors.SacrificialTargetRefused):
        ex.attempt(probe.Op.RENAME, str(tmp_path / "_c3" / "a"), str(victim), None)
    assert victim.read_text() == "real" and not outside.exists()


def test_the_os_executor_maps_denials_and_other_errors_and_acts_only_on_disposables(tmp_path, monkeypatch):
    pol = native_policy(tmp_path)
    (tmp_path / "_c3").mkdir()
    ex = probe.OsOperationExecutor(pol)
    target = str(tmp_path / "_c3" / "made.txt")
    assert ex.attempt(probe.Op.CREATE_FILE, target, None, None).success
    assert ex.attempt(probe.Op.CREATE_FILE, target, None, None) == probe.AttemptResult(False, False, "FileExistsError")
    assert ex.attempt(probe.Op.DELETE_FILE, str(tmp_path / "_c3" / "none"), None, None).denied is False

    def boom(*a, **k):
        raise PermissionError("nope")

    monkeypatch.setattr(os, "open", boom)
    res = ex.attempt(probe.Op.CREATE_FILE, str(tmp_path / "_c3" / "d.txt"), None, None)
    assert res.denied and not res.success


def test_open_access_is_read_only_probing_and_needs_an_opener(tmp_path):
    pol = native_policy(tmp_path)
    prod_dir = str(tmp_path / "prod")
    seen = []
    ex = probe.OsOperationExecutor(pol, open_access=lambda p, m: (seen.append((p, m)) or (False, True, "ERR")))
    res = ex.attempt(probe.Op.OPEN_ACCESS, prod_dir, None, 0x2)
    assert res == probe.AttemptResult(False, True, "ERR")
    assert len(seen) == 1 and seen[0][1] == 0x2
    assert probe.OsOperationExecutor(pol).attempt(probe.Op.OPEN_ACCESS, prod_dir, None, 0x2).success is False
    with pytest.raises(errors.SacrificialTargetRefused):
        ex.attempt(probe.Op.OPEN_ACCESS, str(tmp_path / "somewhere-else"), None, 0x2)


# --- cleanup --------------------------------------------------------------------------------------------------------------------


class FakeFs:
    """Dictionary filesystem for nt-style paths: {path: kind}."""

    def __init__(self, entries):
        self.entries = {k.lower(): v for k, v in entries.items()}
        self.removed = []
        self.listed = []
        self.fail = set()

    def lstat_kind(self, path):
        return self.entries.get(path.lower(), "missing")

    def listdir(self, path):
        self.listed.append(path)
        prefix = path.lower().rstrip("\\") + "\\"
        return sorted({k[len(prefix):].split("\\")[0] for k in self.entries if k.startswith(prefix)}) + list(getattr(self, "extra", {}).get(path.lower(), []))

    def _remove(self, path):
        if path.lower() in self.fail:
            raise PermissionError("denied")
        self.entries.pop(path.lower(), None)
        self.removed.append(path)

    remove_file = remove_dir = remove_link = _remove


TREE = {
    "P:\\_c3": "dir", "P:\\_c3\\twin": "dir", "P:\\_c3\\twin\\approvals": "dir",
    "P:\\_c3\\twin\\approvals\\canary-approval.json": "file", "P:\\_c3\\twin\\worktrees": "dir",
    "P:\\_c3\\twin\\worktrees\\junction": "link", "P:\\_c3\\twin\\worktrees\\control.txt": "file",
}


def test_cleanup_removes_children_before_parents_and_never_descends_links():
    fs = FakeFs(TREE)
    fs.entries["p:\\_c3\\twin\\worktrees\\junction\\inside-the-target.txt"] = "file"  # lives behind the link
    rep = probe.cleanup_container(policy(), fs)
    assert rep.clean and not rep.already_clean
    assert "P:\\_c3\\twin\\worktrees\\junction" in fs.removed
    assert all("junction" not in p.lower() for p in fs.listed), "must not list through a link"
    assert fs.removed[-1].lower() == "p:\\_c3"
    order = [p.lower() for p in fs.removed]
    assert order.index("p:\\_c3\\twin\\approvals\\canary-approval.json") < order.index("p:\\_c3\\twin\\approvals") < order.index("p:\\_c3\\twin")


def test_cleanup_is_idempotent():
    fs = FakeFs(TREE)
    probe.cleanup_container(policy(), fs)
    again = probe.cleanup_container(policy(), fs)
    assert again.already_clean and again.removed == 0 and again.clean


@pytest.mark.parametrize("kind", ["link", "file", "other"])
def test_cleanup_refuses_a_container_that_is_not_a_plain_directory(kind):
    fs = FakeFs({"P:\\_c3": kind})
    with pytest.raises(errors.SacrificialTargetRefused):
        probe.cleanup_container(policy(), fs)
    assert fs.removed == []


@pytest.mark.parametrize("requested", ["P:\\approvals", "P:\\", "P:\\_c3\\twin", "P:\\_c3-other", "D:\\PetCareVault", "P:\\_c3\\..\\approvals"])
def test_cleanup_refuses_to_target_anything_but_the_container(requested):
    fs = FakeFs(TREE)
    with pytest.raises(errors.SacrificialTargetRefused):
        probe.cleanup_container(policy(), fs, requested=requested)
    assert fs.removed == []


@pytest.mark.parametrize("name", ["..", ".", "a\\b", "a/b", "C:x", "x:ads", " pad ", ""])
def test_cleanup_refuses_unsafe_directory_entry_names(name):
    fs = FakeFs({"P:\\_c3": "dir"})
    fs.extra = {"p:\\_c3": [name]}
    with pytest.raises(errors.SacrificialTargetRefused):
        probe.cleanup_container(policy(), fs)
    assert fs.removed == []


def test_cleanup_refuses_special_entries_and_enforces_bounds(monkeypatch):
    fs = FakeFs({"P:\\_c3": "dir", "P:\\_c3\\pipe": "other"})
    with pytest.raises(errors.SacrificialTargetRefused):
        probe.cleanup_container(policy(), fs)
    monkeypatch.setattr(probe, "MAX_CLEANUP_ENTRIES", 2)
    big = {"P:\\_c3": "dir", **{f"P:\\_c3\\f{i}": "file" for i in range(5)}}
    with pytest.raises(errors.ProbeAborted):
        probe.cleanup_container(policy(), FakeFs(big))
    monkeypatch.setattr(probe, "MAX_CLEANUP_ENTRIES", 1000)
    monkeypatch.setattr(probe, "MAX_CLEANUP_DEPTH", 1)
    deep = {"P:\\_c3": "dir", "P:\\_c3\\a": "dir", "P:\\_c3\\a\\b": "dir", "P:\\_c3\\a\\b\\c": "dir", "P:\\_c3\\a\\b\\c\\d": "file"}
    with pytest.raises(errors.ProbeAborted):
        probe.cleanup_container(policy(), FakeFs(deep))


def test_cleanup_reports_failures_and_keeps_the_container_when_something_remains():
    fs = FakeFs(TREE)
    fs.fail.add("p:\\_c3\\twin\\worktrees\\control.txt")
    rep = probe.cleanup_container(policy(), fs)
    assert not rep.clean and any("control.txt" in f for f in rep.failures)
    assert "p:\\_c3" in fs.entries  # the container is kept while anything remains


def test_real_cleanup_in_a_temp_dir_removes_a_link_without_touching_its_target(tmp_path):
    pol = native_policy(tmp_path)
    c = tmp_path / "_c3"
    (c / "twin" / "worktrees").mkdir(parents=True)
    (c / "twin" / "worktrees" / "f.txt").write_text("x")
    outside = tmp_path / "prod"
    (outside / "precious.txt").write_text("keep me")
    link = c / "twin" / "worktrees" / "junction"
    try:
        if os.name == "nt":
            import _winapi

            _winapi.CreateJunction(str(outside), str(link))
        else:
            os.symlink(str(outside), str(link))
    except OSError:
        pytest.skip("cannot create a link in this environment")
    rep = probe.cleanup_container(pol, probe.OsFsAdapter())
    assert rep.clean and not c.exists()
    assert (outside / "precious.txt").read_text() == "keep me"
    assert probe.cleanup_container(pol, probe.OsFsAdapter()).already_clean


# --- preflight ----------------------------------------------------------------------------------------------------------------


def test_free_space_checks_fail_closed():
    need = {"P:\\": 5}
    assert probe.check_free_space(need, lambda r: 100, approved_root="P:\\") == ["P:\\"]
    with pytest.raises(errors.ProbeAborted) as e:
        probe.check_free_space(need, lambda r: 1, approved_root="P:\\")
    assert "FREE_SPACE_LOW" in e.value.detail
    for bad in (None, True, "100", 1.5):
        with pytest.raises(errors.ProbeAborted) as e2:
            probe.check_free_space(need, lambda r, b=bad: b, approved_root="P:\\")
        assert "UNVERIFIABLE" in e2.value.detail


# --- G0-R-D: the free-space configuration is untrusted until validated -------------------------------------------------

BAD_FREE_KEYS = [
    {"P:\\": 1, "D:\\": 1},              # extra key (unbound vault volume)
    {"D:\\": 1},                          # substituted drive root
    {"Q:\\": 1},                          # arbitrary drive root
    {"p:\\": 1},                          # case alias
    {"P:/": 1}, {"P:": 1}, {"P:\\\\": 1}, {"P:\\.": 1}, {" P:\\": 1}, {"P:\\ ": 1},   # malformed separators / padding
    {"P:\\x": 1}, {"P:\\approvals": 1},  # not a root
    {"\\\\server\\share\\": 1}, {"\\\\server\\share": 1}, {"//server/share/": 1},   # UNC / network
    {"\\\\?\\P:\\": 1}, {"\\\\.\\P:\\": 1}, {"\\\\?\\Volume{cc594c83-54d8-4340-9d57-05ed19f20112}\\": 1},  # device
    {"..\\": 1}, {".": 1}, {"relative\\dir": 1}, {"": 1},   # relative
    {},                                   # missing the required key
]
BAD_FREE_VALUES = [0, -1, True, False, 1.5, "5", None, [1], probe.MAX_FREE_FLOOR_BYTES + 1]


@pytest.mark.parametrize("free", BAD_FREE_KEYS)
def test_free_space_keys_other_than_the_approved_root_are_refused_at_parse(free):
    with pytest.raises(errors.ApprovalInvalid):
        parse(min_free_bytes=free)


@pytest.mark.parametrize("value", BAD_FREE_VALUES)
def test_invalid_free_space_thresholds_are_refused_at_parse(value):
    with pytest.raises(errors.ApprovalInvalid):
        parse(min_free_bytes={"P:\\": value})


def test_the_largest_allowed_threshold_is_accepted():
    assert parse(min_free_bytes={"P:\\": probe.MAX_FREE_FLOOR_BYTES}).min_free_bytes == {"P:\\": probe.MAX_FREE_FLOOR_BYTES}


@pytest.mark.parametrize("root", ["p:\\", "P:", "P:/", "\\\\?\\P:\\", "\\\\server\\share\\", "PP:\\", "1:\\"])
def test_the_approved_volume_root_must_be_an_exact_drive_root(root):
    with pytest.raises(errors.ApprovalInvalid):
        parse(production_paths=dict(PROD, root=root), min_free_bytes={root: 1})


@pytest.mark.parametrize(
    "over",
    [
        {"production_paths": dict(PROD, approvals="Q:\\approvals")},
        {"production_paths": dict(PROD, bin="Q:\\bin")},
        {"production_paths": dict(PROD, evidence="p:\\evidence")},
        {"container": "Q:\\_c3"},
    ],
)
def test_free_space_root_mappings_inconsistent_with_the_approved_volume_are_refused(over):
    with pytest.raises(errors.ApprovalInvalid):
        parse(**over)


@pytest.mark.parametrize("free", BAD_FREE_KEYS + [{"P:\\": v} for v in BAD_FREE_VALUES] + ["not-a-dict", None, [("P:\\", 1)]])
def test_check_free_space_validates_the_whole_set_before_calling_the_provider(free):
    calls = Counter(lambda r: 10**12)
    with pytest.raises(errors.ProbeAborted):
        probe.check_free_space(free, calls, approved_root="P:\\")
    assert calls.n == 0


@pytest.mark.parametrize("approved_root", ["D:\\", "p:\\", "\\\\server\\share\\", "", None])
def test_check_free_space_refuses_an_unapproved_root_binding(approved_root):
    calls = Counter(lambda r: 10**12)
    with pytest.raises(errors.ProbeAborted):
        probe.check_free_space({"P:\\": 1}, calls, approved_root=approved_root)
    assert calls.n == 0


@pytest.mark.parametrize("free", [{"D:\\": 1}, {"P:\\": 1, "\\\\server\\share\\": 1}, {"P:\\": True}])
def test_a_mocked_run_with_a_tampered_free_space_set_never_reaches_disk_usage(free):
    # The approval object is edited AFTER parsing; execution re-validates before the provider.
    calls = Counter(lambda r: 10**12)
    rep = probe.run_probe(ctx(approval=dataclasses.replace(parse(), min_free_bytes=free), free_space=calls), "READONLY")
    assert rep["verdict"] == "FAIL" and calls.n == 0 and "min_free_bytes" in json.dumps(rep)


# --- running the probe (mocked) ---------------------------------------------------------------------------------------------


class Counter:
    def __init__(self, inner=None):
        self.n = 0
        self.inner = inner

    def __call__(self, *a, **k):
        self.n += 1
        return self.inner(*a, **k) if self.inner else None


def good_identity():
    return base.agent_identity()


def stub_guard(verify):
    """An offline-only guard stand-in that exposes the policy the probe binds to."""

    return type("G", (), {"offline_only": True, "verify": verify, "policy": POLICY_G})()


def ctx(**over) -> probe.ProbeContext:
    be = twin_guard_backend()
    nodes = be.nodes
    for key in ("approvals", "bin", "worktrees", "runtime", "evidence"):
        path = PROD[key]
        mask = probe.AGENT_RX if key in ("approvals", "bin") else probe.AGENT_MODIFY
        nodes[path.lower()] = g.NodeSecurity(path, base.ADMINS, (g.Ace(base.SYSTEM, 0x1F01FF, inherited=True), g.Ace(AGENT, mask)), is_dir=True)
    guard = g.MockedDescriptorApprovalGuard(POLICY_G, be)
    fs = FakeFs(TREE)
    values = dict(
        approval=parse(), guard=guard, identity_provider=good_identity, policy=policy(), free_space=lambda r: 10**12,
        package_manifest=MANIFEST, observed_tree=OBSERVED_TREE, now=NOW, mode="OFFLINE_MOCKED",
        executor=FakeExecutor(), fs=fs,
    )
    values.update(over)
    return probe.ProbeContext(**values)


def test_plan_phase_touches_nothing():
    guard, ident, free, ex, fs = Counter(), Counter(), Counter(), FakeExecutor(), FakeFs(TREE)
    c = ctx(guard=stub_guard(guard), identity_provider=ident, free_space=free, executor=ex, fs=fs)
    rep = probe.run_probe(c, "PLAN")
    assert rep["verdict"] == "PASS_PLAN_ONLY" and guard.n == ident.n == free.n == 0 and ex.calls == [] and fs.removed == []


def test_readonly_mocked_run_passes_but_is_never_reported_as_enforced():
    rep = probe.run_probe(ctx(approval=parse(phase="READONLY", negative_authorized=False)), "READONLY")
    assert rep["verdict"] == "PASS_OFFLINE_MOCKED" and rep["mode"] == "OFFLINE_MOCKED"
    assert [c["id"] for c in rep["checks"]].count("approval") == 1
    assert rep["identity"]["user"].endswith("-1008")


def test_negative_mocked_run_executes_cases_then_cleans_up():
    c = ctx()
    rep = probe.run_probe(c, "NEGATIVE")
    assert rep["verdict"] == "PASS_OFFLINE_MOCKED", rep
    assert len(rep["negative"]) == len(probe.NEGATIVE_CASES) and all(n["ok"] == "True" for n in rep["negative"])
    assert rep["cleanup"]["failures"] == [] and c.fs.removed and c.fs.lstat_kind("P:\\_c3") == "missing"


def test_unexpected_access_success_fails_the_run_and_still_cleans_up():
    c = ctx(executor=FakeExecutor({"N01": probe.AttemptResult(True)}))
    rep = probe.run_probe(c, "NEGATIVE")
    assert rep["verdict"] == "FAIL" and rep["reason_code"] == "PROBE_ABORTED"
    assert rep["cleanup"] is not None and c.fs.lstat_kind("P:\\_c3") == "missing"


def test_a_guard_verdict_that_differs_from_expectation_fails():
    c = ctx()
    c.guard._backend.nodes[PROD["worktrees"].lower()] = g.NodeSecurity(
        PROD["worktrees"], base.ADMINS, (g.Ace(base.SYSTEM, 0x1F01FF, inherited=True), g.Ace(AGENT, probe.AGENT_RX)), is_dir=True)
    rep = probe.run_probe(c, "READONLY")
    assert rep["verdict"] == "FAIL" and "GUARD_VERDICT_MISMATCH" in json.dumps(rep)


def test_wrong_executing_identity_fails_before_anything_else():
    c = ctx(identity_provider=lambda: base.agent_identity(user_sid=OWNER))
    rep = probe.run_probe(c, "READONLY")
    assert rep["verdict"] == "FAIL" and rep["reason_code"] == "APPROVAL_BOUNDARY_VIOLATION"


def test_volume_substitution_is_caught_by_the_guard():
    c = ctx()
    c.guard._backend.volume = dataclasses.replace(base.GOOD_VOLUME, mount_root="P:\\", dos_target="\\??\\C:\\fake")
    rep = probe.run_probe(c, "READONLY")
    assert rep["verdict"] == "FAIL"


def test_dangerous_token_privileges_fail_the_probe():
    bad = base.agent_identity(privileges=base.BENIGN + (g.Privilege("SeRestorePrivilege", False),))
    rep = probe.run_probe(ctx(identity_provider=lambda: bad), "READONLY")
    assert rep["verdict"] == "FAIL"


def test_package_hash_mismatch_fails_before_any_boundary_check():
    guard = Counter()
    c = ctx(guard=stub_guard(guard),
            observed_tree=dict(OBSERVED_TREE, **{"scripts/orchestrator/a.py": ("0" * 64, 1)}))
    rep = probe.run_probe(c, "READONLY")
    assert rep["verdict"] == "FAIL" and rep["reason_code"] == "PACKAGE_INTEGRITY_FAILURE" and guard.n == 0


def test_an_approval_bound_to_another_manifest_fails_immediately():
    ident = Counter(good_identity)
    rep = probe.run_probe(ctx(approval=parse(package_manifest_sha256="1" * 64), identity_provider=ident), "READONLY")
    assert rep["verdict"] == "FAIL" and rep["reason_code"] == "PACKAGE_INTEGRITY_FAILURE" and ident.n == 0


def test_no_external_operation_happens_before_authorization_validates():
    ident, free, ex, fs = Counter(good_identity), Counter(lambda r: 10**12), FakeExecutor(), FakeFs(TREE)
    guard = Counter()
    g_obj = stub_guard(guard)
    for c in (
        ctx(approval=parse(), now=NOW + timedelta(days=3)),                     # expired
        ctx(approval=parse(phase="READONLY", negative_authorized=False)),       # phase too low for NEGATIVE
    ):
        c.identity_provider, c.free_space, c.executor, c.fs, c.guard = ident, free, ex, fs, g_obj
        rep = probe.run_probe(c, "NEGATIVE")
        assert rep["verdict"] == "FAIL"
    assert ident.n == free.n == guard.n == 0 and ex.calls == [] and fs.removed == []


def test_low_or_unverifiable_free_space_fails():
    assert probe.run_probe(ctx(free_space=lambda r: 1), "READONLY")["verdict"] == "FAIL"
    assert probe.run_probe(ctx(free_space=lambda r: None), "READONLY")["verdict"] == "FAIL"


def test_the_negative_phase_needs_the_twin_an_executor_and_a_filesystem():
    assert probe.run_probe(ctx(fs=FakeFs({})), "NEGATIVE")["verdict"] == "FAIL"
    assert probe.run_probe(ctx(executor=None), "NEGATIVE")["verdict"] == "FAIL"


def test_enforced_mode_requires_the_builtin_production_guard():
    rep = probe.run_probe(ctx(mode="ENFORCED"), "READONLY")
    assert rep["verdict"] == "FAIL" and rep["reason_code"] == "APPROVAL_BOUNDARY_VIOLATION"


def test_mocked_mode_requires_an_offline_only_guard():
    class Duck:
        offline_only = False

        def verify(self, *a):
            raise AssertionError("must not run")

    rep = probe.run_probe(ctx(guard=Duck()), "READONLY")
    assert rep["verdict"] == "FAIL"


def test_unknown_mode_and_phase_fail():
    assert probe.run_probe(ctx(mode="LIVE"), "READONLY")["verdict"] == "FAIL"
    assert probe.run_probe(ctx(), "EXECUTE")["verdict"] == "FAIL"


EVIDENCE = rtt.verify()   # genuine evidence for the synthetic interpreter tree INTERP_HASHES
APPROVAL_FILE = "P:\\approvals\\c3-probe.json"
MANIFEST_BYTES = MANIFEST.to_bytes()
ENFORCED_ARGS = dict(
    approval_path=APPROVAL_FILE, expected_agent_sid=AGENT, trusted_owner_sids=(OWNER, base.ADMINS),
    volume_guid=VOL_GUID, volume_label="PetCareAgent", volume_serial=0xABCD1234,
    package_manifest_bytes=MANIFEST_BYTES, provenance=EVIDENCE,
)


class EnforcedHost:
    """Offline stand-in for EVERY host source an ENFORCED run reads: the security
    backend (pinned approval read, token, volume, descriptors), the wall clock, the
    monotonic clock, free space, the live interpreter snapshot and the two tree scans.
    Each is patched at the module boundary it is read from. Records the order of
    observations so tests can prove nothing is observed before trust is established."""

    def __init__(self, monkeypatch, *, doc=None, data=None, env=None, interp=None, app=None, env_error=None,
                 scan_error=None, wall=NOW, mono=None, volume=None, identity=None, pinned_kw=None):
        self.events: list[str] = []
        self.backend_calls = 0
        content = data if data is not None else json.dumps(doc if doc is not None else approval_doc()).encode()
        be = twin_guard_backend()
        for key in ("approvals", "bin", "worktrees", "runtime", "evidence"):
            path = PROD[key]
            mask = probe.AGENT_RX if key in ("approvals", "bin") else probe.AGENT_MODIFY
            be.nodes[path.lower()] = g.NodeSecurity(path, base.ADMINS, (g.Ace(base.SYSTEM, 0x1F01FF, inherited=True), g.Ace(AGENT, mask)), is_dir=True)
        file_node = g.NodeSecurity(APPROVAL_FILE, base.ADMINS, (g.Ace(base.SYSTEM, 0x1F01FF, inherited=True), g.Ace(AGENT, probe.AGENT_RX, inherited=True)))
        be.nodes[APPROVAL_FILE.lower()] = file_node
        self.pinned = hard.FakePinned(content=content, path=APPROVAL_FILE, node=file_node, **(pinned_kw or {}))
        backend = hard.PinBackend(pinned=self.pinned, nodes=be.nodes, volume=volume if volume is not None else be.volume,
                                  identity=identity)
        events = self.events
        real_open = backend.open_pinned

        def open_pinned(path):
            events.append("approval_read")
            return real_open(path)

        backend.open_pinned = open_pinned
        self.backend = backend
        self._env = env if env is not None else rtt.env()
        self._trees = {"P:\\bin\\python": INTERP_SCAN if interp is None else interp,
                       "P:\\bin\\app": OBSERVED_TREE if app is None else app}
        mono_values = iter(mono) if mono is not None else None

        def default_backend():
            self.backend_calls += 1
            return backend

        def capture():
            events.append("env")
            if env_error:
                raise env_error
            return self._env

        def scan(root, **kw):
            events.append("scan:" + root)
            if scan_error:
                raise scan_error
            if root not in self._trees:
                raise errors.PackageIntegrityFailure(f"unexpected live scan root {root}")
            return dict(self._trees[root])

        monkeypatch.setattr(g, "default_backend", default_backend)
        monkeypatch.setattr(rt, "capture_environment", capture)
        monkeypatch.setattr(pkg, "scan_tree", scan)
        monkeypatch.setattr(probe, "_wall_now", lambda: wall)
        monkeypatch.setattr(probe, "_monotonic", (lambda: next(mono_values)) if mono_values else (lambda: 0.0))
        monkeypatch.setattr(probe, "real_free_space", lambda root: 10**12)
        # The NEGATIVE phase's filesystem and executor are replaced too, so an ENFORCED
        # NEGATIVE run can be exercised without ever touching the real P: volume.
        self.fs = FakeFs(TREE)
        self.executor = FakeExecutor()
        monkeypatch.setattr(probe, "OsFsAdapter", lambda: self.fs)
        monkeypatch.setattr(probe, "OsOperationExecutor", lambda pol, open_access=None: self.executor)

    @property
    def observed(self) -> bool:
        return any(e == "env" or e.startswith("scan:") for e in self.events)


def enforced(phase="READONLY", **over):
    kw = dict(ENFORCED_ARGS)
    kw.update(over)
    return probe.run_enforced_probe(phase, **kw)


def reason(rep) -> str:
    return json.dumps(rep)


def ids(rep) -> dict:
    return {c["id"]: c["status"] for c in rep["checks"]}


def test_the_enforced_path_passes_end_to_end_with_trusted_sources_only(monkeypatch):
    host = EnforcedHost(monkeypatch)
    rep = enforced()
    assert rep["mode"] == "ENFORCED" and rep["verdict"] == "PASS", rep
    st = ids(rep)
    for check in ("approval_pinned", "bindings", "runtime", "package", "identity", "free_space",
                  "guard:approvals", "guard:bin", "guard:worktrees", "guard:runtime", "guard:evidence"):
        assert st.get(check) == "PASS", (check, rep)
    # Order: the pinned approval read (with its volume binding) precedes every live observation.
    assert host.events == ["approval_read", "env", "scan:P:\\bin\\python", "scan:P:\\bin\\app"]
    assert host.pinned.closed


# --- 1. trusted clock -----------------------------------------------------------------------------------------


def test_the_enforced_entry_point_accepts_no_time_deadline_or_trust_object_from_the_caller():
    import inspect
    params = set(inspect.signature(probe.run_enforced_probe).parameters)
    assert params == {"phase", "approval_path", "expected_agent_sid", "trusted_owner_sids", "volume_guid",
                      "volume_label", "volume_serial", "package_manifest_bytes", "provenance"}
    for extra in ({"now": NOW}, {"clock": lambda: 0.0}, {"max_seconds": 10**9}, {"approval": parse()},
                  {"approval_snapshot": object()}, {"package_manifest": MANIFEST}, {"runtime_policy": rtt.POLICY},
                  {"runtime_env": rtt.env()}, {"observed_tree": OBSERVED_TREE}, {"guard": object()}, {"policy": policy()}):
        with pytest.raises(TypeError):
            enforced(**extra)


def test_a_caller_built_context_is_never_enforced():
    host_free = Counter()
    rep = probe.run_probe(ctx(mode="ENFORCED", free_space=host_free), "READONLY")
    assert rep["verdict"] == "FAIL" and "only through run_enforced_probe" in reason(rep) and host_free.n == 0
    rep = probe.run_probe(ctx(mode="ENFORCED"), "PLAN")          # PLAN is never labelled ENFORCED evidence
    assert rep["verdict"] == "FAIL"


def test_an_expired_approval_cannot_be_replayed_against_the_trusted_clock(monkeypatch):
    host = EnforcedHost(monkeypatch, wall=NOW + timedelta(days=2))
    rep = enforced()
    assert rep["verdict"] == "FAIL" and rep["reason_code"] == "APPROVAL_INVALID" and "expired" in reason(rep)
    assert not host.observed and host.pinned.closed


def test_a_backdated_trusted_clock_is_refused_by_the_lifetime_bound(monkeypatch):
    host = EnforcedHost(monkeypatch, wall=NOW - timedelta(days=2))
    rep = enforced()
    assert rep["verdict"] == "FAIL" and "lifetime exceeds" in reason(rep) and not host.observed


def test_the_deadline_comes_from_the_approval_and_the_trusted_monotonic_clock(monkeypatch):
    doc = approval_doc(max_run_seconds=10)
    host = EnforcedHost(monkeypatch, doc=doc, mono=[0.0] + [11.0] * 50)
    rep = enforced()
    assert rep["verdict"] == "FAIL" and "DEADLINE_EXCEEDED after 10s" in reason(rep)
    assert not host.observed        # the first tick is before any live observation


@pytest.mark.parametrize("bad", [0, -1, probe.MAX_RUN_SECONDS + 1, True, "60", 1.5, None])
def test_the_owner_bounded_run_limit_is_validated(bad):
    with pytest.raises(errors.ApprovalInvalid):
        parse(max_run_seconds=bad)


# --- 2. the pinned approval snapshot is acquired by the probe itself ------------------------------------------


def test_the_approval_is_read_only_through_the_pinned_production_read(monkeypatch):
    host = EnforcedHost(monkeypatch)
    enforced()
    assert host.backend.opened == [APPROVAL_FILE] and host.pinned.reads >= 1


def test_an_approval_file_that_cannot_be_pinned_is_unverifiable(monkeypatch):
    host = EnforcedHost(monkeypatch)
    host.backend.open_error = g.AclUnreadable("cannot open")
    rep = enforced()
    assert rep["verdict"] == "UNVERIFIED" and rep["reason_code"] == "APPROVAL_BOUNDARY_UNVERIFIABLE" and not host.observed


def test_an_approval_that_changes_while_it_is_read_is_refused(monkeypatch):
    host = EnforcedHost(monkeypatch)

    def swap(p):
        p.identity_now = dataclasses.replace(p.identity, mtime_ns=p.identity.mtime_ns + 1)

    host.pinned.on_read = swap
    rep = enforced()
    assert rep["verdict"] == "FAIL" and "changed while it was being read" in reason(rep) and not host.observed


@pytest.mark.parametrize(
    "kw, expect",
    [
        ({"reparse": True}, "reparse point"),
        ({"nlinks": 2}, "hard links"),
        ({"final_path": "P:\\worktrees\\c3-probe.json"}, "different path"),
    ],
)
def test_a_pinned_file_with_the_wrong_identity_is_refused(monkeypatch, kw, expect):
    host = EnforcedHost(monkeypatch, pinned_kw=kw)
    rep = enforced()
    assert rep["verdict"] == "FAIL" and expect in reason(rep) and not host.observed


@pytest.mark.parametrize("data", [b"not json", b"{}", json.dumps({**approval_doc(), "extra": 1}).encode()])
def test_pinned_bytes_that_do_not_parse_are_refused(monkeypatch, data):
    host = EnforcedHost(monkeypatch, data=data)
    rep = enforced()
    assert rep["verdict"] == "FAIL" and rep["reason_code"] == "APPROVAL_INVALID" and not host.observed


def test_an_approval_outside_the_approved_approvals_directory_is_refused(monkeypatch):
    doc = approval_doc(production_paths=dict(PROD, approvals="P:\\bin"))
    host = EnforcedHost(monkeypatch, doc=doc)
    rep = enforced()
    assert rep["verdict"] == "FAIL" and not host.observed


def test_a_phase_the_approval_does_not_cover_is_refused(monkeypatch):
    host = EnforcedHost(monkeypatch, doc=approval_doc(phase="READONLY", negative_authorized=False))
    rep = enforced("NEGATIVE")
    assert rep["verdict"] == "FAIL" and "does not authorize this phase" in reason(rep) and not host.observed


@pytest.mark.parametrize("phase", ["PLAN", "EXECUTE", None, 3])
def test_enforced_runs_only_readonly_or_negative(monkeypatch, phase):
    host = EnforcedHost(monkeypatch)
    rep = enforced(phase)
    assert rep["verdict"] == "FAIL" and rep["reason_code"] == "APPROVAL_INVALID"
    assert host.backend_calls == 0 and host.events == []


# --- caller callbacks never run before (or after) the trust boundary ------------------------------------------


class Spy:
    calls = 0


class SpyStr(str):
    def __eq__(self, other):
        Spy.calls += 1
        return str.__eq__(self, other)

    __hash__ = str.__hash__

    def lower(self):
        Spy.calls += 1
        return str.lower(self)


class SpyBytes(bytes):
    def __eq__(self, other):
        Spy.calls += 1
        return bytes.__eq__(self, other)

    __hash__ = bytes.__hash__


class SpyTuple(tuple):
    def __iter__(self):
        Spy.calls += 1
        return tuple.__iter__(self)


class SpyInt(int):
    def __eq__(self, other):
        Spy.calls += 1
        return int.__eq__(self, other)

    __hash__ = int.__hash__


@pytest.mark.parametrize(
    "over",
    [
        {"approval_path": SpyStr(APPROVAL_FILE)},
        {"expected_agent_sid": SpyStr(AGENT)},
        {"volume_guid": SpyStr(VOL_GUID)},
        {"volume_label": SpyStr("PetCareAgent")},
        {"trusted_owner_sids": SpyTuple((OWNER, base.ADMINS))},
        {"trusted_owner_sids": (SpyStr(OWNER), base.ADMINS)},
        {"trusted_owner_sids": [OWNER, base.ADMINS]},
        {"volume_serial": SpyInt(0xABCD1234)},
        {"volume_serial": True},
        {"package_manifest_bytes": SpyBytes(MANIFEST_BYTES)},
        {"package_manifest_bytes": MANIFEST},
        {"package_manifest_bytes": bytearray(MANIFEST_BYTES)},
        {"approval_path": ""},
    ],
)
def test_caller_objects_with_overridden_methods_are_refused_before_anything_runs(monkeypatch, over):
    Spy.calls = 0
    host = EnforcedHost(monkeypatch)
    rep = enforced(**over)
    assert rep["verdict"] == "FAIL" and rep["reason_code"] == "APPROVAL_BOUNDARY_VIOLATION", rep
    assert Spy.calls == 0 and host.backend_calls == 0 and host.events == []


@pytest.mark.parametrize("bad", [None, True, "verified", object()])
def test_enforced_mode_needs_genuine_provenance_evidence(monkeypatch, bad):
    host = EnforcedHost(monkeypatch)
    rep = enforced(provenance=bad)
    assert rep["verdict"] == "UNVERIFIED" and rep["reason_code"] == "RUNTIME_UNTRUSTED"
    assert host.backend_calls == 0 and host.events == []


def test_subclassed_or_impure_provenance_evidence_is_refused(monkeypatch):
    host = EnforcedHost(monkeypatch)
    Sub = type("Sub", (rt.ProvenanceEvidence,), {})
    sub = Sub(**{f.name: getattr(EVIDENCE, f.name) for f in dataclasses.fields(rt.ProvenanceEvidence)})
    impure = dataclasses.replace(EVIDENCE, verified_binaries=list(EVIDENCE.verified_binaries))
    for ev in (sub, impure):
        rep = enforced(provenance=ev)
        assert rep["verdict"] == "UNVERIFIED" and rep["reason_code"] == "RUNTIME_UNTRUSTED"
    assert host.backend_calls == 0 and host.events == []


# --- 3. the package manifest is rebuilt from canonical bytes ---------------------------------------------------


def test_manifest_bytes_that_are_not_the_approved_manifest_are_refused(monkeypatch):
    host = EnforcedHost(monkeypatch)
    forged = MANIFEST_BYTES.replace(MANIFEST.files[0].sha256.encode(), b"0" * 64)
    rep = enforced(package_manifest_bytes=forged)
    assert rep["verdict"] == "FAIL" and rep["reason_code"] == "PACKAGE_INTEGRITY_FAILURE"
    assert "not the approved manifest" in reason(rep) and not host.observed


def test_non_canonical_manifest_bytes_are_refused_even_when_their_digest_is_approved(monkeypatch):
    pretty = json.dumps(json.loads(MANIFEST_BYTES), indent=2).encode()
    host = EnforcedHost(monkeypatch, doc=approval_doc(package_manifest_sha256=pkg.sha256_hex(pretty)))
    rep = enforced(package_manifest_bytes=pretty)
    assert rep["verdict"] == "FAIL" and "canonical form" in reason(rep) and not host.observed


def test_malformed_manifest_bytes_with_an_approved_digest_are_refused(monkeypatch):
    junk = b'{"schema":"petcare.c3.package/v1","source_commit":"x","files":[]}'
    host = EnforcedHost(monkeypatch, doc=approval_doc(package_manifest_sha256=pkg.sha256_hex(junk)))
    rep = enforced(package_manifest_bytes=junk)
    assert rep["verdict"] == "FAIL" and rep["reason_code"] == "PACKAGE_INTEGRITY_FAILURE" and not host.observed


def test_the_live_application_tree_not_a_fixture_decides_package_integrity(monkeypatch):
    tampered = dict(OBSERVED_TREE, **{"scripts/orchestrator/a.py": ("0" * 64, 1)})
    EnforcedHost(monkeypatch, app=tampered)
    rep = enforced()
    assert rep["verdict"] == "FAIL" and rep["reason_code"] == "PACKAGE_INTEGRITY_FAILURE"
    assert ids(rep).get("runtime") == "PASS"


# --- 4. fixed runtime security rules ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "flags",
    [dict(rtt.GOOD_FLAGS, isolated=0), dict(rtt.GOOD_FLAGS, ignore_environment=0), dict(rtt.GOOD_FLAGS, dont_write_bytecode=0)],
)
def test_the_live_runtime_is_judged_by_fixed_isolation_rules(monkeypatch, flags):
    EnforcedHost(monkeypatch, env=rtt.env(flags=flags))
    rep = enforced()
    assert rep["verdict"] == "UNVERIFIED" and rep["reason_code"] == "RUNTIME_UNTRUSTED"


def test_extra_import_finders_or_hooks_in_the_live_process_are_refused(monkeypatch):
    EnforcedHost(monkeypatch, env=rtt.env(meta_path=tuple(sorted(rt.DEFAULT_META_PATH)) + ("evil.Finder",)))
    assert enforced()["reason_code"] == "RUNTIME_UNTRUSTED"
    EnforcedHost(monkeypatch, env=rtt.env(path_hooks=("evil.hook",)))
    assert enforced()["reason_code"] == "RUNTIME_UNTRUSTED"


def test_the_live_pytest_process_is_not_a_trusted_runtime(monkeypatch):
    real_capture = rt.capture_environment
    host = EnforcedHost(monkeypatch)
    monkeypatch.setattr(rt, "capture_environment", real_capture)
    rep = enforced()
    assert rep["verdict"] == "UNVERIFIED" and rep["reason_code"] == "RUNTIME_UNTRUSTED"
    assert not any(c["id"].startswith("guard:") for c in rep["checks"])


def test_unobservable_live_state_fails_closed(monkeypatch):
    EnforcedHost(monkeypatch, env_error=OSError("boom"))
    rep = enforced()
    assert rep["verdict"] == "UNVERIFIED" and "could not be observed" in reason(rep)
    EnforcedHost(monkeypatch, env="not-a-snapshot")
    assert "malformed" in reason(enforced())
    EnforcedHost(monkeypatch, scan_error=errors.PackageIntegrityFailure("directory changed during the scan: x"))
    assert enforced()["reason_code"] == "PACKAGE_INTEGRITY_FAILURE"
    EnforcedHost(monkeypatch, interp={})
    assert "empty" in reason(enforced())
    EnforcedHost(monkeypatch, interp={"python.exe": "not-a-tuple"})
    assert enforced()["verdict"] == "UNVERIFIED"


def test_stale_provenance_for_a_different_interpreter_tree_is_refused(monkeypatch):
    EnforcedHost(monkeypatch, interp=dict(INTERP_SCAN, **{"python313._pth": (rtt.sha(b"edited"), 6)}))
    rep = enforced()
    assert rep["verdict"] == "FAIL" and "stale or substituted" in reason(rep)


def test_consistent_evidence_for_a_tree_the_owner_did_not_pin_is_refused(monkeypatch):
    other_hashes = {k: rtt.sha(v) for k, v in dict(rtt.TREE, **{"python313._pth": b"other"}).items()}
    other_ev = rtt.verify(observed_sha256=other_hashes, references=other_hashes,
                          signature_report=json.dumps({"schema": rt.SIGNATURE_SCHEMA, "entries": [
                              {"path": k, "sha256": other_hashes[k], "status": "Valid", "signer": "Python Software Foundation"}
                              for k in sorted(rtt.BINARIES)]}).encode())
    EnforcedHost(monkeypatch, interp={k: (v, 1) for k, v in other_hashes.items()})
    rep = enforced(provenance=other_ev)
    assert rep["verdict"] == "FAIL" and "not the owner-pinned interpreter tree" in reason(rep)


# --- 5. exact volume binding, before any live observation ------------------------------------------------------


def test_a_configured_volume_other_than_the_mounted_one_is_refused_before_observation(monkeypatch):
    host = EnforcedHost(monkeypatch)
    rep = enforced(volume_guid="\\\\?\\Volume{11111111-2222-3333-4444-555555555555}\\")
    assert rep["verdict"] == "FAIL" and not host.observed


def test_an_approval_naming_another_volume_is_refused_before_observation(monkeypatch):
    doc = approval_doc(trusted_volume={"guid": "\\\\?\\Volume{11111111-2222-3333-4444-555555555555}\\",
                                       "label": "PetCareAgent", "serial": 0xABCD1234})
    host = EnforcedHost(monkeypatch, doc=doc)
    rep = enforced()
    assert rep["verdict"] == "FAIL" and "exact enforced binding" in reason(rep) and not host.observed


@pytest.mark.parametrize("over", [{"volume_serial": 0x1}, {"volume_label": "Other"}])
def test_a_conflicting_volume_identity_is_refused(monkeypatch, over):
    host = EnforcedHost(monkeypatch)
    rep = enforced(**over)
    assert rep["verdict"] == "FAIL" and not host.observed


def test_a_drive_letter_substitution_is_refused_before_observation(monkeypatch):
    sub = dataclasses.replace(base.GOOD_VOLUME, mount_root="P:\\", dos_target="\\??\\C:\\fake")
    host = EnforcedHost(monkeypatch, volume=sub)
    rep = enforced()
    assert rep["verdict"] == "FAIL" and not host.observed


@pytest.mark.parametrize("over", [{"expected_agent_sid": OWNER}, {"trusted_owner_sids": (OWNER,)}])
def test_configuration_the_pinned_read_cannot_satisfy_is_refused(monkeypatch, over):
    # Fails closed inside the pinned production read itself (token / owner checks).
    host = EnforcedHost(monkeypatch)
    rep = enforced(**over)
    assert rep["verdict"] in ("FAIL", "UNVERIFIED") and ids(rep).get("approval_pinned") is None and not host.observed


def test_configuration_that_differs_from_the_pinned_approval_is_refused(monkeypatch):
    # The read succeeds (one more trusted owner is configured), but the approval itself
    # names different owners: the configuration must EQUAL the owner-protected approval.
    host = EnforcedHost(monkeypatch)
    rep = enforced(trusted_owner_sids=(OWNER, base.ADMINS, "S-1-5-21-1-2-3-500"))
    assert rep["verdict"] == "FAIL" and "different agent or owners" in reason(rep) and not host.observed


def test_the_mocked_guard_must_bind_exactly_one_volume():
    extra = dataclasses.replace(POLICY_G, trusted_volumes=POLICY_G.trusted_volumes + (
        g.VolumeBinding("\\\\?\\Volume{11111111-2222-3333-4444-555555555555}\\", label="Other", serial=1),))
    c = ctx()
    c.guard = g.MockedDescriptorApprovalGuard(extra, c.guard._backend)
    rep = probe.run_probe(c, "READONLY")
    assert rep["verdict"] == "FAIL" and "exactly the approved volume" in reason(rep)


def test_an_enforced_negative_run_passes_and_cleans_up_with_trusted_sources_only(monkeypatch):
    host = EnforcedHost(monkeypatch)
    rep = enforced("NEGATIVE")
    assert rep["verdict"] == "PASS", rep
    assert len(rep["negative"]) == len(probe.NEGATIVE_CASES) and rep["cleanup"]["failures"] == []
    assert host.fs.lstat_kind("P:\\_c3") == "missing" and host.pinned.closed


def test_an_approval_changed_during_the_cases_is_caught_before_cleanup(monkeypatch):
    # The pinned approval is revalidated again immediately before the removal pass:
    # a change during the cases makes the run FAIL, but cleanup still runs.
    host = EnforcedHost(monkeypatch)
    inner = host.executor.attempt

    def tamper(*a, **k):
        host.pinned.content = b"tampered during the run"
        return inner(*a, **k)

    host.executor.attempt = tamper
    rep = enforced("NEGATIVE")
    assert rep["verdict"] == "FAIL" and "content changed" in reason(rep), rep
    assert rep["cleanup"] is not None and host.fs.lstat_kind("P:\\_c3") == "missing"


def test_the_final_operation_is_bounded_by_the_deadline():
    # Learn how many operations a full run dispatches, then let the clock pass the
    # deadline exactly on the LAST one: only the post-operation tick can catch it.
    probe_ex = FakeExecutor()
    assert probe.run_probe(ctx(executor=probe_ex), "NEGATIVE")["verdict"] == "PASS_OFFLINE_MOCKED"
    total = len(probe_ex.calls)
    state = {"late": False}
    ex = FakeExecutor()
    inner = ex.attempt

    def last_is_late(*a, **k):
        res = inner(*a, **k)
        if len(ex.calls) == total:
            state["late"] = True
        return res

    ex.attempt = last_is_late
    c = ctx(executor=ex, clock=lambda: 10_000.0 if state["late"] else 0.0, max_seconds=300)
    rep = probe.run_probe(c, "NEGATIVE")
    assert len(ex.calls) == total
    assert rep["verdict"] == "FAIL" and "DEADLINE_EXCEEDED" in reason(rep), rep
    assert c.fs.lstat_kind("P:\\_c3") == "missing"


def test_the_wrong_token_stops_an_enforced_run(monkeypatch):
    EnforcedHost(monkeypatch, identity=base.agent_identity(user_sid=OWNER))
    rep = enforced()
    assert rep["verdict"] in ("FAIL", "UNVERIFIED") and ids(rep).get("identity") != "PASS"
    assert not any(k.startswith("guard:") and v == "PASS" for k, v in ids(rep).items())


# --- bindings, deadline, unexpected errors, guard-refusal reasons --------------------------------------------------


def test_the_approval_is_bound_to_the_active_policies():
    other_container = TmpPolicy(container="P:\\_c3x", production_roots=tuple(v for k, v in PROD.items() if k != "root"), platform="nt")
    assert probe.run_probe(ctx(policy=other_container), "READONLY")["reason_code"] == "APPROVAL_INVALID"

    wrong_agent = dataclasses.replace(POLICY_G, expected_agent_sid="S-1-5-21-1-2-3-4242")
    c = ctx()
    c.guard = g.MockedDescriptorApprovalGuard(wrong_agent, c.guard._backend)
    assert probe.run_probe(c, "READONLY")["reason_code"] == "APPROVAL_BOUNDARY_VIOLATION"

    other_vol = dataclasses.replace(POLICY_G, trusted_volumes=(g.VolumeBinding("\\\\?\\Volume{11111111-2222-3333-4444-555555555555}\\", label="PetCareAgent", serial=0xABCD1234),))
    c = ctx()
    c.guard = g.MockedDescriptorApprovalGuard(other_vol, c.guard._backend)
    assert probe.run_probe(c, "READONLY")["reason_code"] == "APPROVAL_BOUNDARY_VIOLATION"

    fewer_owners = dataclasses.replace(POLICY_G, trusted_owner_sids=frozenset({OWNER}))
    c = ctx()
    c.guard = g.MockedDescriptorApprovalGuard(fewer_owners, c.guard._backend)
    assert probe.run_probe(c, "READONLY")["reason_code"] == "APPROVAL_BOUNDARY_VIOLATION"

    c = ctx()
    c.guard = type("G", (), {"offline_only": True, "verify": lambda *a: None})()  # exposes no policy
    assert probe.run_probe(c, "READONLY")["reason_code"] == "APPROVAL_BOUNDARY_UNVERIFIABLE"


def test_approved_production_paths_must_be_production_roots_of_the_policy():
    # G0-R-D refuses these at parse time; the later binding layer must still refuse an edited object.
    for prod in (dict(PROD, approvals="C:\\Users\\mattn\\Documents"), dict(PROD, root="D:\\")):
        with pytest.raises(errors.ApprovalInvalid):
            parse(production_paths=prod)
    hostile = dataclasses.replace(parse(), production_paths=dict(PROD, approvals="C:\\Users\\mattn\\Documents"))
    assert probe.run_probe(ctx(approval=hostile), "READONLY")["reason_code"] == "APPROVAL_INVALID"
    wrong_root = dataclasses.replace(parse(), production_paths=dict(PROD, root="D:\\"))
    assert probe.run_probe(ctx(approval=wrong_root), "READONLY")["reason_code"] == "APPROVAL_INVALID"


@pytest.mark.parametrize(
    "over",
    [{"container": "P:\\_c3\\nested"}, {"container": "C:\\Users\\mattn"}, {"container": "P:\\_c3:ads"}, {"container": 7}, {"container": ""},
     {"production_paths": dict(PROD, vhdx="D:\\x:ads")}],
)
def test_a_hostile_container_or_path_in_the_approval_is_rejected_at_parse_time(over):
    with pytest.raises(errors.ApprovalInvalid):
        parse(**over)


def test_the_run_has_a_real_deadline():
    ticks = iter([0.0] + [10_000.0] * 100)
    rep = probe.run_probe(ctx(clock=lambda: next(ticks), max_seconds=300), "NEGATIVE")
    assert rep["verdict"] == "FAIL" and "DEADLINE_EXCEEDED" in json.dumps(rep)


def test_cleanup_is_not_stopped_by_the_deadline():
    # Deadline trips during the cases; cleanup must still run (it takes no deadline tick).
    calls = {"n": 0}

    def clock():
        calls["n"] += 1
        return 0.0 if calls["n"] <= 12 else 10_000.0

    c = ctx(clock=clock, max_seconds=300)
    rep = probe.run_probe(c, "NEGATIVE")
    assert rep["verdict"] == "FAIL" and c.fs.lstat_kind("P:\\_c3") == "missing"


@pytest.mark.parametrize("which", ["identity_provider", "free_space"])
def test_unexpected_exceptions_become_an_unverified_report_not_a_raise(which):
    def boom(*a, **k):
        raise RuntimeError("provider exploded")

    rep = probe.run_probe(ctx(**{which: boom}), "READONLY")
    assert rep["verdict"] == "UNVERIFIED" and rep["reason_code"] == "UNEXPECTED_RuntimeError"


def test_an_unexpected_executor_exception_still_cleans_up():
    class Exploding:
        def attempt(self, *a, **k):
            raise OSError("disk fell off")

    c = ctx(executor=Exploding())
    rep = probe.run_probe(c, "NEGATIVE")
    assert rep["verdict"] == "UNVERIFIED" and rep["reason_code"] == "UNEXPECTED_OSError"
    assert c.fs.lstat_kind("P:\\_c3") == "missing"


def test_a_refusal_for_the_wrong_reason_is_not_accepted_as_the_expected_denial():
    c = ctx()
    # worktrees is refused here because of its OWNER, not because the agent can write it.
    c.guard._backend.nodes[PROD["worktrees"].lower()] = g.NodeSecurity(
        PROD["worktrees"], "S-1-5-21-9-9-9-5000", (g.Ace(base.SYSTEM, 0x1F01FF, inherited=True), g.Ace(AGENT, probe.AGENT_RX)), is_dir=True)
    rep = probe.run_probe(c, "READONLY")
    assert rep["verdict"] == "FAIL" and "GUARD_REFUSAL_WRONG_REASON" in json.dumps(rep)


def test_the_probes_own_identity_check_covers_system_and_other_ancestor_owners():
    for sid in (g.SID_SYSTEM, g.SID_TRUSTED_INSTALLER):
        bad = base.agent_identity(group_sids=base.agent_identity().group_sids | {sid})
        rep = probe.run_probe(ctx(identity_provider=lambda b=bad: b), "READONLY")
        assert rep["verdict"] == "FAIL" and rep["reason_code"] == "APPROVAL_BOUNDARY_VIOLATION"
        assert not any(c["id"] == "identity" and c["status"] == "PASS" for c in rep["checks"])


def test_an_empty_or_missing_catalogue_proves_nothing():
    with pytest.raises(errors.ProbeAborted) as e:
        run_cases(FakeExecutor(), cases=[])
    assert "NO_CASES" in e.value.detail
    rep = probe.run_probe(ctx(cases=()), "NEGATIVE")
    assert rep["verdict"] == "FAIL" and "NO_CASES" in json.dumps(rep)


def test_cleanup_records_an_unreadable_directory_instead_of_raising():
    class ListFails(FakeFs):
        def listdir(self, path):
            if path.lower().endswith("approvals"):
                raise PermissionError("denied")
            return super().listdir(path)

    fs = ListFails(TREE)
    rep = probe.cleanup_container(policy(), fs)
    assert not rep.clean and any(f.startswith("list:approvals") for f in rep.failures)
    assert "p:\\_c3" in fs.entries  # kept, because something could not be inspected


def test_cleanup_reports_an_entry_that_changed_kind_before_removal():
    class Swaps(FakeFs):
        def lstat_kind(self, path):
            kind = super().lstat_kind(path)
            if path.lower().endswith("twin\\approvals") and getattr(self, "armed", False):
                return "link"
            return kind

        def remove_file(self, path):
            self.armed = True  # after the first file is removed, a directory "becomes" a junction
            super()._remove(path)

    fs = Swaps(TREE)
    rep = probe.cleanup_container(policy(), fs)
    assert any(f.startswith("changed:") for f in rep.failures)
    assert "P:\\_c3\\twin\\approvals" not in fs.removed  # the swapped entry was reported, not removed


def test_the_os_executor_refuses_to_operate_through_a_link_inside_the_container(tmp_path):
    pol = native_policy(tmp_path)
    c = tmp_path / "_c3"
    (c / "twin").mkdir(parents=True)
    outside = tmp_path / "prod"
    link = c / "twin" / "junction"
    try:
        if os.name == "nt":
            import _winapi

            _winapi.CreateJunction(str(outside), str(link))
        else:
            os.symlink(str(outside), str(link))
    except OSError:
        pytest.skip("cannot create a link in this environment")
    with pytest.raises(errors.SacrificialTargetRefused):
        probe.OsOperationExecutor(pol).attempt(probe.Op.CREATE_FILE, str(link / "x.txt"), None, None)
    assert not (outside / "x.txt").exists()


# --- S4U prerequisites -------------------------------------------------------------------------------------------------------------


TRUST = "P:\\bin"
APPROVAL_PATH = "P:\\approvals\\c3-probe.json"


def good_task():
    return {
        "principal_sid": AGENT, "logon_type": "S4U", "run_level": "Limited", "stores_password": False, "triggers": [],
        "actions": [{"execute": "P:\\bin\\python\\python.exe", "working_directory": "P:\\bin\\app",
                     "arguments": probe.build_task_arguments(TRUST, "READONLY", APPROVAL_PATH)}],
        "execution_time_limit_seconds": 300,
    }


def task_findings(task):
    return probe.validate_task_definition(task, expected_agent_sid=AGENT, trusted_root=TRUST, phase="READONLY", approval_path=APPROVAL_PATH)


def test_the_expected_task_definition_validates_cleanly():
    assert task_findings(good_task()) == []
    assert probe.S4U_SPEC["logon_type"] == "S4U" and probe.S4U_SPEC["password_stored"] is False
    assert probe.S4U_SPEC["run_level"] == "Limited" and probe.S4U_SPEC["open_questions_for_G2"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda t: t.update(principal_sid=OWNER),
        lambda t: t.update(logon_type="Password"),
        lambda t: t.update(logon_type="InteractiveToken"),
        lambda t: t.update(run_level="Highest"),
        lambda t: t.update(stores_password=True),
        lambda t: t.pop("stores_password"),
        lambda t: t.update(triggers=[{"type": "Logon"}]),
        lambda t: t.update(actions=[]),
        lambda t: t["actions"].append(dict(t["actions"][0])),
        lambda t: t["actions"][0].update(execute="C:\\Python313\\python.exe"),
        lambda t: t["actions"][0].update(arguments=t["actions"][0]["arguments"] + " --extra"),
        lambda t: t["actions"][0].update(arguments=t["actions"][0]["arguments"].replace("-I -B", "")),
        lambda t: t["actions"][0].update(arguments=t["actions"][0]["arguments"].replace("READONLY", "NEGATIVE")),
        lambda t: t["actions"][0].update(working_directory="P:\\runtime"),
        lambda t: t.update(execution_time_limit_seconds=3600),
        lambda t: t.update(execution_time_limit_seconds=0),
        lambda t: t.pop("execution_time_limit_seconds"),
    ],
)
def test_any_deviation_in_the_registered_task_is_detected(mutate):
    task = good_task()
    mutate(task)
    assert task_findings(task), task


def test_a_task_can_only_run_readonly_or_negative_phases():
    for phase in ("PLAN", "EXECUTE", ""):
        with pytest.raises(ValueError):
            probe.build_task_arguments(TRUST, phase, APPROVAL_PATH)


# --- CLI -----------------------------------------------------------------------------------------------------------------------------


def test_cli_plan_is_pure_and_lists_everything(capsys):
    assert probe.main([]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert "INERT" in doc["g0_status"] and len(doc["negative_cases"]) == len(probe.NEGATIVE_CASES)
    assert doc["s4u_prerequisites"]["logon_type"] == "S4U" and doc["stop_conditions"]
    assert any(c["read_only_production_probe"] for c in doc["negative_cases"])


@pytest.mark.parametrize("phase", ["READONLY", "NEGATIVE"])
def test_cli_refuses_to_run_real_phases_in_g0(phase, capsys):
    assert probe.main(["--phase", phase]) == 2
    assert "not runnable in G0" in capsys.readouterr().err


def test_cli_verify_package_round_trip_and_mismatch(tmp_path, capsys):
    export = tmp_path / "export"
    (export / "scripts" / "orchestrator").mkdir(parents=True)
    (export / "scripts" / "orchestrator" / "a.py").write_bytes(FILES["scripts/orchestrator/a.py"])
    ls = tmp_path / "ls.txt"
    ls.write_text(LISTING, encoding="utf-8", newline="")
    assert probe.main(["--verify-package", str(export), str(ls), "--commit", COMMIT]) == 0
    assert json.loads(capsys.readouterr().out)["manifest_sha256"] == MANIFEST.digest()
    (export / "scripts" / "orchestrator" / "a.py").write_bytes(b"print('a')\r\n")
    assert probe.main(["--verify-package", str(export), str(ls), "--commit", COMMIT]) == 2
    assert "PACKAGE_INTEGRITY_FAILURE" in capsys.readouterr().err
    assert probe.main(["--verify-package", str(export), str(ls)]) == 2


def test_cli_trusted_root_check_fails_closed_for_the_untrusted_test_process(capsys):
    root = "P:\\bin" if os.name == "nt" else "/opt/trusted"
    work = "P:\\runtime" if os.name == "nt" else "/srv/work"
    exe = root + ("\\python\\python.exe" if os.name == "nt" else "/python")
    assert probe.main(["--trusted-root", root]) == 2          # missing writable roots / pinned executable
    assert "needs --agent-writable-root" in capsys.readouterr().err
    assert probe.main(["--trusted-root", root, "--agent-writable-root", work, "--expected-executable", exe]) == 2
    assert "RUNTIME_UNTRUSTED" in capsys.readouterr().err
    # an overlapping writable root is rejected as an unusable policy, not silently accepted
    assert probe.main(["--trusted-root", root, "--agent-writable-root", root, "--expected-executable", exe]) == 2
    assert "policy rejected" in capsys.readouterr().err


def test_the_cli_never_claims_provenance(capsys):
    src = (PKG / "c3_probe.py").read_text(encoding="utf-8")
    assert '"runtime": "trusted"' not in src and "NOT_VERIFIED_BY_THIS_COMMAND" in src


# --- static safety of the new modules --------------------------------------------------------------------------------------------------


PKG = Path(__file__).resolve().parents[2] / "scripts" / "orchestrator"
NEW = [PKG / "c3_package.py", PKG / "c3_runtime.py", PKG / "c3_probe.py"]
ALLOWED = {"__future__", "argparse", "dataclasses", "datetime", "enum", "hashlib", "json", "ntpath", "os", "posixpath", "re",
           "shutil", "stat", "sys", "time", "typing", "unicodedata", "_winapi"}
FORBIDDEN = {"subprocess", "socket", "ssl", "urllib", "http", "requests", "httpx", "ctypes", "tempfile", "asyncio",
             "multiprocessing", "ftplib", "smtplib", "winreg", "zipfile", "tarfile", "importlib", "runpy"}
TOKENS = ["os.system", "Popen", "schtasks", "Register-ScheduledTask", "runas", "net user", "urlopen", "SetNamedSecurityInfo",
          "LogonUser", "AdjustTokenPrivileges", "os.environ[", "os.environ.get", "getenv", "api_key", "Authorization:", "Bearer ",
          "chmod(", "chown("]


def _roots(path):
    out = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.add(node.module.split(".")[0])
    return out


@pytest.mark.parametrize("path", NEW, ids=lambda p: p.name)
def test_new_modules_use_only_the_standard_library_subset_and_no_process_network_or_download_surface(path):
    roots = _roots(path)
    assert not roots & FORBIDDEN, roots & FORBIDDEN
    assert roots <= ALLOWED, roots - ALLOWED
    text = path.read_text(encoding="utf-8")
    for token in TOKENS:
        assert token not in text, f"{path.name} contains {token!r}"


def test_no_production_code_path_weakens_the_container_depth_rule():
    for path in NEW:
        text = path.read_text(encoding="utf-8")
        assert "require_top_level" not in text, path.name          # no constructor switch exists
        assert "_top_level_required = False" not in text, path.name  # and no module overrides the class invariant
    assert probe.TargetPolicy._top_level_required is True
    with pytest.raises(TypeError):
        probe.TargetPolicy(container="P:\\_c3", production_roots=("P:\\approvals",), platform="nt", require_top_level=False)  # type: ignore[call-arg]


def test_the_probe_registers_no_task_and_changes_no_account():
    text = (PKG / "c3_probe.py").read_text(encoding="utf-8")
    for token in ("Register-ScheduledTask", "schtasks", "SeBatchLogonRight", "net localgroup", "icacls", "takeown"):
        assert token not in text
    assert probe.S4U_SPEC["password_stored"] is False


# --- Windows-native (real ctypes; READ-ONLY; pytest temp dir only) -----------------------------------------------------------------


@pytest.mark.skipif(os.name != "nt", reason="Windows-native check")
def test_windows_native_open_access_probe_changes_nothing_and_authz_matches_the_model(tmp_path):
    from scripts.orchestrator.acl_windows import WindowsSecurityBackend

    be = WindowsSecurityBackend()
    d = tmp_path / "d"
    d.mkdir()
    f = d / "f.txt"
    f.write_text("x")
    snapshot = (f.read_text(), sorted(os.listdir(d)), f.stat().st_mtime_ns, d.stat().st_mtime_ns)
    # Our own temp dir: the owner holds full control, so these opens are granted - and they change nothing.
    for mask in (probe.FILE_ADD_FILE, probe.FILE_DELETE_CHILD, probe.WRITE_DAC_RIGHT, probe.DELETE_RIGHT):
        granted, denied, err = be.probe_open_access(str(d), mask)
        assert granted and not denied and err == ""
    assert (f.read_text(), sorted(os.listdir(d)), f.stat().st_mtime_ns, d.stat().st_mtime_ns) == snapshot
    missing = be.probe_open_access(str(tmp_path / "does-not-exist"), probe.FILE_READ_DATA)
    assert missing[0] is False and missing[1] is False and "WinError" in missing[2]
    with pytest.raises(g.AclUnreadable):
        be.probe_open_access(str(d), 0)

    me = be.current_identity()
    stranger = g.Identity("S-1-5-21-1-2-3-9999", frozenset({"S-1-1-0", "S-1-5-32-545", "S-1-5-11"}))
    node = be.read_node(str(d))
    # For a principal that owns nothing here, Windows and the guard model agree exactly.
    authz_s = be.effective_access(str(d), stranger)
    assert authz_s & g.DANGEROUS_TARGET == g._effective_allow_mask(node, stranger.effective_ids) & g.DANGEROUS_TARGET
    assert authz_s & (g.WRITE_DAC | g.DELETE | g.FILE_WRITE_DATA) == 0
    # The owner's rights may arrive through an OWNER RIGHTS (S-1-3-4) ACE, which the model deliberately
    # does not interpret (see the next test for why that is safe). Windows reports the real answer.
    assert be.effective_access(str(d), me) & g.FILE_WRITE_DATA


def test_owner_rights_aces_cannot_hide_an_agent_owned_boundary():
    """The model does not interpret OWNER RIGHTS (S-1-3-4). That is safe because an
    agent-owned node is refused outright, whatever its DACL says."""

    owner_rights = "S-1-3-4"
    nodes = probe.twin_security(OWNER, AGENT, OWNER, CONTAINER)
    nodes["P:\\"] = g.NodeSecurity("P:\\", OWNER, base.owner_aces(inherited=False), is_dir=True)
    key = CONTAINER + "\\twin\\approvals"
    nodes[key] = g.NodeSecurity(key, AGENT, (g.Ace(owner_rights, 0x1F01FF), g.Ace(AGENT, probe.AGENT_RX)), is_dir=True)
    vol = dataclasses.replace(base.GOOD_VOLUME, mount_root="P:\\")
    guard = g.MockedDescriptorApprovalGuard(POLICY_G, base.FakeBackend(nodes=nodes, volume=vol))
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        guard.verify(None, key)
    assert "owned by the agent" in e.value.detail


# --- S4U command-line hardening --------------------------------------------------------------------------------------------------------


def test_the_task_command_line_is_a_module_start_with_isolation_flags():
    args = probe.build_task_arguments(TRUST, "READONLY", APPROVAL_PATH)
    assert args.startswith("-I -B -m scripts.orchestrator.c3_probe ") and "c3_probe.py" not in args
    assert args.endswith(f'--approval "{APPROVAL_PATH}"')


@pytest.mark.parametrize(
    "approval",
    ['P:\\approvals\\x" --phase NEGATIVE', "P:\\approvals\\x' y", "P:\\approvals\\%TEMP%\\x", "P:\\approvals\\..\\runtime\\x",
     "P:\\approvals\\x.json:ads", "\\\\?\\P:\\approvals\\x.json", "relative.json", "P:\\APPROV~1\\x.json"],
)
def test_task_paths_cannot_inject_arguments_or_use_unsafe_forms(approval):
    with pytest.raises(ValueError):
        probe.build_task_arguments(TRUST, "READONLY", approval)


def test_an_unsafe_trusted_root_is_rejected():
    for root in ('P:\\bin" --x', "P:\\bin\\..\\runtime", "P:\\BIN~1"):
        with pytest.raises(ValueError):
            probe.build_task_arguments(root, "READONLY", APPROVAL_PATH)


@pytest.mark.parametrize("execute", ["P:\\BIN~1\\python\\python.exe", "P:\\bin\\python\\python.exe:ads", "P:\\bin\\.\\python\\python.exe",
                                     "\\\\?\\P:\\bin\\python\\python.exe", "python.exe"])
def test_a_task_that_points_at_an_alias_or_unsafe_form_of_the_interpreter_is_rejected(execute):
    task = good_task()
    task["actions"][0]["execute"] = execute
    assert any("pinned interpreter" in f for f in task_findings(task))


def test_path_comparison_in_the_task_readback_is_case_insensitive_only():
    task = good_task()
    task["actions"][0]["execute"] = "p:\\BIN\\Python\\PYTHON.EXE"
    task["actions"][0]["working_directory"] = "P:\\Bin\\App"
    assert task_findings(task) == []


def test_the_spec_records_the_known_limits_and_the_provisioning_checklist():
    assert probe.S4U_SPEC["known_g0_limits"] and probe.S4U_SPEC["g1_provisioning_checklist"]
    text = json.dumps(probe.S4U_SPEC)
    for needle in ("._pth", "reference hash", "System32", "BEFORE the probe's own imports", "handle-relative", "VHDX"):
        assert needle in text, needle


# --- chain identity across the two passes (PR #65 follow-up) -----------------------------------------------------------------------------


def test_a_swapped_ancestor_with_the_same_node_count_is_detected_by_the_chain_digest():
    be = hard.PinBackend()

    def swap_owner(p):
        key = base.AGENT_ROOT.lower()
        be.nodes[key] = dataclasses.replace(be.nodes[key], owner=base.ADMINS)  # still an allowed ancestor owner

    be.pinned.on_read = swap_owner
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        g.read_pinned_approval(be, base.POLICY, base.MAN, base.APPR, enforced=False)
    assert "chain changed" in e.value.detail and be.pinned.closed


def test_the_chain_digest_is_stable_for_an_unchanged_chain():
    be = hard.PinBackend()
    a = g.verify_boundary(be, base.POLICY, base.MAN, base.APPR, enforced=False)
    b = g.verify_boundary(be, base.POLICY, base.MAN, base.APPR, enforced=False)
    assert a.chain_digest and a.chain_digest == b.chain_digest and "chain_digest" not in a.to_dict()


# --- Windows-native: the access probe only accepts query-style rights -------------------------------------------------------------------------


@pytest.mark.skipif(os.name != "nt", reason="Windows-native check")
@pytest.mark.parametrize("mask", [0x40000000, 0x10000000, 0x80000000, 0x02000000, 0x100000, 0x2 | 0x40000000, 0x1000000])
def test_windows_native_open_access_refuses_generic_maximum_and_unknown_rights(tmp_path, mask):
    from scripts.orchestrator.acl_windows import WindowsSecurityBackend

    with pytest.raises(g.AclUnreadable):
        WindowsSecurityBackend().probe_open_access(str(tmp_path), mask)


@pytest.mark.skipif(os.name != "nt", reason="Windows-native check")
def test_windows_native_open_access_and_authz_use_system32_only_and_never_share_delete():
    src = (PKG / "acl_windows.py").read_text(encoding="utf-8")
    assert src.count("winmode=_LOAD_SYSTEM32") == 3 and "_SHARE_READ_WRITE = 0x3" in src
    assert "0x7" not in src.split("_SHARE_READ_WRITE")[1].split("\n")[0]


# --- G0-R-D: free space in ENFORCED runs --------------------------------------------------------------------


class _DiskSpy:
    def __init__(self):
        self.roots = []

    def __call__(self, root):
        self.roots.append(root)
        return 10**12


def test_an_enforced_run_measures_free_space_only_on_the_verified_volume_root(monkeypatch):
    EnforcedHost(monkeypatch)
    spy = _DiskSpy()
    monkeypatch.setattr(probe, "real_free_space", spy)
    rep = enforced()
    assert rep["verdict"] == "PASS", rep
    assert spy.roots == ["P:\\"]


@pytest.mark.parametrize("free", [{"\\\\server\\share\\": 1}, {"P:\\": 1, "D:\\": 1}, {"relative": 1}, {"P:\\": 0}])
def test_an_enforced_approval_with_a_bad_free_space_set_never_reaches_disk_usage(monkeypatch, free):
    host = EnforcedHost(monkeypatch, doc=approval_doc(min_free_bytes=free))
    spy = _DiskSpy()
    monkeypatch.setattr(probe, "real_free_space", spy)
    real_du = []
    monkeypatch.setattr(probe.shutil, "disk_usage", lambda p: real_du.append(p))
    rep = enforced()
    assert rep["verdict"] == "FAIL" and rep["reason_code"] == "APPROVAL_INVALID", rep
    assert spy.roots == [] and real_du == [] and not host.observed


def test_the_real_free_space_provider_is_only_reached_after_validation(monkeypatch):
    # The genuine real_free_space (shutil.disk_usage) is never called for a refused configuration.
    real_du = []
    monkeypatch.setattr(probe.shutil, "disk_usage", lambda p: real_du.append(p))
    with pytest.raises(errors.ProbeAborted):
        probe.check_free_space({"\\\\server\\share\\": 1}, probe.real_free_space, approved_root="P:\\")
    assert real_du == []


# --- G0-R-D: an expected guard denial must be exactly the agent-rights reason --------------------------------


def _worktrees(c, owner, mask, **kw):
    path = PROD["worktrees"]
    c.guard._backend.nodes[path.lower()] = g.NodeSecurity(
        path, owner, (g.Ace(base.SYSTEM, 0x1F01FF, inherited=True), g.Ace(AGENT, mask)), is_dir=True, **kw)


def test_a_mixed_wrong_owner_and_rights_refusal_is_not_the_expected_denial():
    c = ctx()
    _worktrees(c, "S-1-5-21-9-9-9-1001", probe.AGENT_MODIFY)   # untrusted owner AND agent write rights
    rep = probe.run_probe(c, "READONLY")
    assert rep["verdict"] == "FAIL" and "GUARD_REFUSAL_WRONG_REASON guard:worktrees" in json.dumps(rep), rep


def test_a_reparse_refusal_with_rights_is_not_the_expected_denial():
    c = ctx()
    _worktrees(c, base.ADMINS, probe.AGENT_MODIFY, is_reparse=True)
    rep = probe.run_probe(c, "READONLY")
    assert rep["verdict"] == "FAIL" and "GUARD_REFUSAL_WRONG_REASON" in json.dumps(rep)


def test_a_wrong_owner_refusal_alone_is_not_the_expected_denial():
    c = ctx()
    _worktrees(c, "S-1-5-21-9-9-9-1001", probe.AGENT_RX)
    rep = probe.run_probe(c, "READONLY")
    assert rep["verdict"] == "FAIL" and "GUARD_REFUSAL_WRONG_REASON" in json.dumps(rep)


def test_the_plain_rights_denial_is_still_accepted():
    rep = probe.run_probe(ctx(), "READONLY")
    assert rep["verdict"] == "PASS_OFFLINE_MOCKED"
    assert {c["id"]: c["status"] for c in rep["checks"]}["guard:worktrees"] == "PASS"


def _violation(codes, unverified=0):
    exc = errors.ApprovalBoundaryViolation("P:\\worktrees: agent holds DELETE")
    if codes is not None:
        exc.violation_codes = codes
    exc.unverified_count = unverified
    return exc


@pytest.mark.parametrize(
    "exc",
    [
        _violation(None),                                                                 # message only: never evidence
        _violation(()),
        _violation((("AGENT_RIGHTS", "P:\\"),)),                                          # an ancestor, not the target
        _violation((("AGENT_RIGHTS", "P:\\worktrees\\x"),)),
        _violation((("OTHER", "P:\\worktrees"),)),
        _violation((("AGENT_RIGHTS", "P:\\worktrees"), ("OTHER", ""))),                  # combined reasons
        _violation((("AGENT_RIGHTS", "P:\\worktrees"), ("AGENT_RIGHTS", "P:\\"))),
        _violation((("AGENT_RIGHTS", "P:\\worktrees"),), unverified=1),                  # plus something unverifiable
        _violation([("AGENT_RIGHTS", "P:\\worktrees")]),                                 # not a tuple
        _violation((("AGENT_RIGHTS", "P:\\worktrees:ads"),)),
    ],
)
def test_only_an_exact_single_rights_violation_on_the_target_counts(exc):
    assert probe._is_exact_rights_denial(exc, "P:\\worktrees") is False


def test_an_exact_single_rights_violation_on_the_target_counts():
    assert probe._is_exact_rights_denial(_violation((("AGENT_RIGHTS", "P:\\worktrees"),)), "P:\\worktrees") is True
    assert probe._is_exact_rights_denial(_violation((("AGENT_RIGHTS", "p:\\WORKTREES"),)), "P:\\worktrees") is True


def test_the_guard_reports_every_violation_untruncated_with_structured_codes():
    f = g._Findings()
    for i in range(9):
        f.violate(f"v{i}")
    f.violate("P:\\x: agent holds DELETE", code=g.VIOLATION_AGENT_RIGHTS, path="P:\\x")
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        f.raise_if_any()
    assert len(e.value.violation_codes) == 10 and e.value.violation_codes[-1] == ("AGENT_RIGHTS", "P:\\x")
    assert "agent holds" not in e.value.detail          # truncated text: the codes are the evidence
    assert e.value.unverified_count == 0


def test_the_g0_limits_describe_the_free_space_and_guard_reason_rules():
    limits = " ".join(probe.S4U_SPEC["known_g0_limits"])
    assert "free-space floor covers ONLY the approved volume root" in limits and "NO free-space floor" in limits
    assert "structured reasons are exactly one AGENT_RIGHTS" in limits
    assert "scan_tree" in " ".join(probe.S4U_SPEC["blocking_g1"])


@pytest.mark.parametrize("root", ["p:\\", "P:", "PP:\\", "1:\\", "P:/"])
def test_a_consistently_rebased_approval_on_a_non_canonical_root_is_refused(root):
    # Every path uses the same (bad) root form, so only the exact drive-root rule can refuse it.
    rebase = lambda p: root + p[3:] if p.startswith("P:\\") else p  # noqa: E731
    prod = {k: (root if k == "root" else rebase(v)) for k, v in PROD.items()}
    with pytest.raises(errors.ApprovalInvalid):
        parse(production_paths=prod, container=rebase(CONTAINER), min_free_bytes={root: 1})
    calls = Counter(lambda r: 10**12)
    with pytest.raises(errors.ProbeAborted):
        probe.check_free_space({root: 1}, calls, approved_root=root)
    assert calls.n == 0


def test_a_lower_case_approval_path_still_measures_only_the_verified_volume_root(monkeypatch):
    # The approval path is canonicalised (upper-case drive) for the pinned read; the
    # free-space root stays the approved, verified "P:\" and nothing else.
    EnforcedHost(monkeypatch)
    spy = _DiskSpy()
    monkeypatch.setattr(probe, "real_free_space", spy)
    rep = enforced(approval_path="p:\\approvals\\c3-probe.json")
    assert rep["verdict"] == "PASS" and spy.roots == ["P:\\"], rep


def test_an_extra_unverifiable_item_spoils_an_otherwise_exact_rights_denial():
    f = g._Findings()
    f.violate("P:\\worktrees: agent holds DELETE", code=g.VIOLATION_AGENT_RIGHTS, path="P:\\worktrees")
    f.unverified("P:\\: unreadable")
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        f.raise_if_any()
    assert e.value.unverified_count == 1
    assert probe._is_exact_rights_denial(e.value, "P:\\worktrees") is False
