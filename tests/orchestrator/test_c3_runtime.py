"""G1.6-C3-G0: trusted-runtime and interpreter-provenance verification (offline)."""

from __future__ import annotations

import dataclasses
import hashlib
import json

import pytest

from scripts.orchestrator import c3_runtime as rt
from scripts.orchestrator import errors

ROOT = "P:\\bin"
WRITABLE = ("P:\\worktrees", "P:\\runtime", "P:\\evidence", "C:\\Users\\petcare-agent")
POLICY = rt.RuntimePolicy(platform="nt", trusted_root=ROOT, agent_writable_roots=WRITABLE,
                          expected_executable="P:\\bin\\python\\python.exe")
GOOD_FLAGS = {"isolated": 1, "no_user_site": 1, "ignore_environment": 1, "dont_write_bytecode": 1, "no_site": 1, "safe_path": 1}


def env(**over) -> rt.EnvironmentSnapshot:
    base = dict(
        platform="nt", executable="P:\\bin\\python\\python.exe", prefix="P:\\bin\\python", base_prefix="P:\\bin\\python",
        cwd="P:\\bin\\app", flags=dict(GOOD_FLAGS),
        sys_path=("P:\\bin\\python\\python313.zip", "P:\\bin\\python", "P:\\bin\\app"),
        env_names=("PATH", "SYSTEMROOT", "TEMP"),
        modules=(
            rt.ModuleOrigin("sys", "builtin"), rt.ModuleOrigin("_frozen_importlib", "frozen"),
            rt.ModuleOrigin("ctypes", "file", ("P:\\bin\\python\\python313.zip\\ctypes\\__init__.py",)),
            rt.ModuleOrigin("scripts.orchestrator.acl_guard", "file", ("P:\\bin\\app\\scripts\\orchestrator\\acl_guard.py",)),
            rt.ModuleOrigin("scripts", "namespace", ("P:\\bin\\app\\scripts",)),
        ),
        meta_path=tuple(sorted(rt.DEFAULT_META_PATH)),
    )
    base.update(over)
    return rt.EnvironmentSnapshot(**base)


def findings(**over) -> list[str]:
    return rt.environment_findings(env(**over), POLICY)


def test_the_exact_trusted_runtime_snapshot_is_accepted():
    assert findings() == []
    rt.verify_execution_environment(env(), POLICY)


def test_enforced_operation_requires_provenance_evidence_with_no_override():
    with pytest.raises(errors.RuntimeUntrusted) as e:
        rt.require_trusted_runtime(env(), POLICY, None, observed_interpreter=OBSERVED,
                                   pinned_tree_sha256=rt.interpreter_tree_digest(OBSERVED))
    assert "provenance" in e.value.detail


@pytest.mark.parametrize("flag", rt.DEFAULT_REQUIRED_FLAGS)
def test_every_required_isolation_flag_is_mandatory(flag):
    flags = dict(GOOD_FLAGS, **{flag: 0})
    assert any(flag in f for f in findings(flags=flags))
    flags.pop(flag)
    assert any(flag in f for f in findings(flags=flags))


def test_safe_path_flag_is_checked_when_the_interpreter_supports_it():
    assert any("safe_path" in f for f in findings(flags=dict(GOOD_FLAGS, safe_path=0)))


@pytest.mark.parametrize(
    "exe,needle",
    [
        ("C:\\Users\\mattn\\Desktop\\lambda_package\\python.exe", "outside the trusted root"),
        ("C:\\Python313\\python.exe", "outside the trusted root"),
        ("P:\\runtime\\python.exe", "agent-writable"),
        ("P:\\worktrees\\evil\\python.exe", "agent-writable"),
        ("P:\\bin\\..\\runtime\\python.exe", "dot segment"),
        ("P:\\bin\\python\\python.exe:evil", "colon"),
        ("\\\\?\\P:\\bin\\python\\python.exe", "unsafe path form"),
        ("python.exe", "unsafe path form"),
    ],
)
def test_the_interpreter_must_live_in_the_trusted_root(exe, needle):
    out = findings(executable=exe)
    assert any(needle in f for f in out), out


def test_a_different_pinned_executable_is_refused():
    assert any("expected pinned" in f for f in findings(executable="P:\\bin\\python2\\python.exe"))


@pytest.mark.parametrize("entry", ["", ".", "..\\x", "relative\\dir", "C:\\Users\\mattn\\Desktop", "P:\\runtime", "P:\\worktrees\\x",
                                   "P:\\binary", "P:\\bin\\..\\runtime", "P:\\bin\\app:ads", "P:\\PROGRA~1"])
def test_every_sys_path_entry_must_be_absolute_trusted_and_not_agent_writable(entry):
    assert findings(sys_path=("P:\\bin\\python", entry)), entry


def test_the_current_directory_and_cwd_must_be_trusted():
    assert any("working directory" in f for f in findings(cwd="C:\\Users\\mattn"))
    assert any("working directory" in f for f in findings(cwd="P:\\runtime"))
    assert any("working directory" in f for f in findings(cwd="relative"))


@pytest.mark.parametrize("names", [("PYTHONPATH",), ("pythonhome",), ("PYTHONSTARTUP",), ("PYTHONUSERBASE",),
                                   ("PYTHONINSPECT",), ("PYTHONBREAKPOINT",), ("LD_PRELOAD",), ("PATH", "PYTHONWARNINGS")])
def test_python_environment_overrides_are_refused_by_name(names):
    out = findings(env_names=names)
    assert any("environment variable" in f for f in out)


def test_the_environment_summary_never_contains_values():
    summary = rt.environment_summary(env(env_names=("PYTHONPATH", "PATH")))
    assert summary["env_names_python"] == ["PYTHONPATH"]
    assert "value" not in json.dumps(summary).lower()


@pytest.mark.parametrize("name", ["sitecustomize", "usercustomize"])
def test_startup_hook_modules_are_refused(name):
    mods = env().modules + (rt.ModuleOrigin(name, "file", ("P:\\bin\\python\\" + name + ".py",)),)
    assert any("startup hook" in f for f in findings(modules=mods))


@pytest.mark.parametrize(
    "mod,needle",
    [
        (rt.ModuleOrigin("evil", "file", ("P:\\runtime\\evil.py",)), "agent-writable"),
        (rt.ModuleOrigin("evil", "file", ("C:\\Users\\mattn\\site-packages\\evil.py",)), "outside the trusted root"),
        (rt.ModuleOrigin("evil", "file", ("evil.py",)), "unsafe path form"),
        (rt.ModuleOrigin("evil", "namespace", ("P:\\bin\\app", "P:\\worktrees\\pkg")), "agent-writable"),
        (rt.ModuleOrigin("evil", "unknown"), "unknown origin"),
    ],
)
def test_every_loaded_module_must_come_from_the_trusted_root(mod, needle):
    out = findings(modules=env().modules + (mod,))
    assert any(needle in f for f in out), out


def test_non_standard_import_finders_are_refused():
    out = findings(meta_path=tuple(rt.DEFAULT_META_PATH) + ("editable_hook.Finder", "_pytest.assertion.rewrite.AssertionRewritingHook"))
    assert any("meta_path" in f for f in out)


def test_registry_and_custom_path_finders_are_not_on_the_default_allow_list():
    assert "_frozen_importlib_external.WindowsRegistryFinder" not in rt.DEFAULT_META_PATH


def test_platform_mismatch_between_snapshot_and_policy_is_refused():
    assert any("platform" in f for f in findings(platform="posix"))


def test_policy_rejects_overlap_with_agent_writable_roots_and_bad_executables():
    with pytest.raises(ValueError):
        rt.RuntimePolicy("nt", "P:\\runtime\\bin", agent_writable_roots=("P:\\runtime",))
    with pytest.raises(ValueError):
        rt.RuntimePolicy("nt", "P:\\", agent_writable_roots=("P:\\runtime",))
    with pytest.raises(ValueError):
        rt.RuntimePolicy("nt", ROOT, expected_executable="C:\\other\\python.exe")
    with pytest.raises(ValueError):
        rt.RuntimePolicy("nt", "relative\\root")
    with pytest.raises(ValueError):
        rt.RuntimePolicy("mac", ROOT)


def test_posix_snapshots_are_evaluated_with_posix_rules():
    pol = rt.RuntimePolicy("posix", "/opt/trusted", agent_writable_roots=("/srv/work",))
    good = rt.EnvironmentSnapshot(
        platform="posix", executable="/opt/trusted/bin/python", prefix="/opt/trusted", base_prefix="/opt/trusted",
        cwd="/opt/trusted/app", flags=dict(GOOD_FLAGS), sys_path=("/opt/trusted/lib", "/opt/trusted/app"),
        env_names=("PATH",), modules=(rt.ModuleOrigin("m", "file", ("/opt/trusted/lib/m.py",)),),
        meta_path=tuple(rt.DEFAULT_META_PATH),
    )
    assert rt.environment_findings(good, pol) == []
    bad = dataclasses.replace(good, sys_path=("/opt/trusted/lib", "/srv/work/x"), env_names=("LD_PRELOAD",))
    out = rt.environment_findings(bad, pol)
    assert any("agent-writable" in f for f in out) and any("environment variable" in f for f in out)


def test_the_live_test_process_is_correctly_NOT_a_trusted_runtime():
    snap = rt.capture_environment()
    assert snap.executable and snap.sys_path and snap.modules and set(snap.flags) >= {"isolated", "no_user_site"}
    pol = rt.RuntimePolicy("nt" if snap.platform == "nt" else "posix", snap.prefix)
    with pytest.raises(errors.RuntimeUntrusted):
        rt.verify_execution_environment(snap, pol)  # pytest is not isolated, so it must fail closed


# --- interpreter binary provenance ------------------------------------------------------------


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


TREE = {"python.exe": b"MZ-python", "python313.dll": b"MZ-dll", "_ctypes.pyd": b"MZ-ctypes", "python313.zip": b"zip", "python313._pth": b"p"}
OBSERVED = {k: sha(v) for k, v in TREE.items()}
BINARIES = {k for k in TREE if k.endswith((".exe", ".dll", ".pyd"))}
# Every file (not only binaries) needs an independent reference hash.
REFS = dict(OBSERVED)
PPOL = rt.ProvenancePolicy(required_binaries=("python.exe", "python313.dll"))


def report(**over) -> bytes:
    entries = [{"path": k, "sha256": OBSERVED[k], "status": "Valid", "signer": "Python Software Foundation"} for k in sorted(BINARIES)]
    doc = {"schema": rt.SIGNATURE_SCHEMA, "entries": entries}
    doc.update(over)
    return json.dumps(doc).encode()


def verify(**over):
    kw = dict(observed_sha256=OBSERVED, signature_report=report(), references=REFS, policy=PPOL)
    kw.update(over)
    return rt.verify_interpreter_provenance(**kw)


def test_fully_attested_interpreter_provenance_is_accepted_and_yields_evidence():
    ev = verify()
    assert isinstance(ev, rt.ProvenanceEvidence)
    assert sorted(ev.verified_binaries) == ["_ctypes.pyd", "python.exe", "python313.dll"]
    assert ev.attested_files == len(OBSERVED) and len(ev.tree_digest) == 64
    # the digest binds the evidence to the exact observed hashes
    changed = dict(OBSERVED, **{"python313._pth": sha(b"different")})
    assert verify(observed_sha256=changed, references=dict(REFS, **{"python313._pth": sha(b"different")})).tree_digest != ev.tree_digest


PINNED = rt.interpreter_tree_digest(OBSERVED)


def gate(ev, *, environment=None, observed=None, pinned=None):
    return rt.require_trusted_runtime(
        environment or env(), POLICY, ev,
        observed_interpreter=OBSERVED if observed is None else observed, pinned_tree_sha256=PINNED if pinned is None else pinned,
    )


def test_the_runtime_gate_takes_evidence_not_a_boolean():
    ev = verify()
    gate(ev)
    for bad in (None, True, False, "verified", 1, {"verified_binaries": ["python.exe"]}):
        with pytest.raises(errors.RuntimeUntrusted):
            gate(bad)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        rt.ProvenanceEvidence(verified_binaries=(), attested_files=0, tree_digest="0" * 64)
    # evidence does not excuse an untrusted environment
    with pytest.raises(errors.RuntimeUntrusted):
        gate(ev, environment=env(cwd="C:\\Users\\mattn"))


def test_evidence_records_every_attested_file_hash():
    ev = verify()
    assert dict(ev.file_hashes) == OBSERVED and ev.attested_files == len(OBSERVED) and ev.tree_digest == PINNED


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(verified_binaries=("python.exe",), attested_files=1, tree_digest="0" * 64),
        dict(verified_binaries=("python.exe",), attested_files=len(OBSERVED), tree_digest=PINNED,
             file_hashes=tuple(sorted(OBSERVED.items()))),                     # internally consistent, but unsealed
        dict(verified_binaries=("python.exe",), attested_files=1, tree_digest=PINNED, _seal=object()),
    ],
)
def test_caller_constructed_provenance_evidence_is_refused(kwargs):
    with pytest.raises(ValueError):
        rt.ProvenanceEvidence(**kwargs)


def test_patched_evidence_must_stay_internally_consistent():
    ev = verify()
    with pytest.raises(ValueError):
        dataclasses.replace(ev, tree_digest="0" * 64)
    with pytest.raises(ValueError):
        dataclasses.replace(ev, attested_files=ev.attested_files + 1)
    with pytest.raises(ValueError):
        dataclasses.replace(ev, verified_binaries=ev.verified_binaries + ("ghost.dll",))


def test_the_gate_binds_evidence_to_the_live_tree_and_the_pinned_digest():
    ev = verify()
    edited = dict(OBSERVED, **{"python313._pth": sha(b"edited")})
    with pytest.raises(errors.PackageIntegrityFailure, match="stale or substituted"):
        gate(ev, observed=edited, pinned=rt.interpreter_tree_digest(edited))
    with pytest.raises(errors.PackageIntegrityFailure):
        gate(ev, observed=dict(OBSERVED, **{"evil.pth": sha(b"x")}))
    with pytest.raises(errors.PackageIntegrityFailure):
        gate(ev, observed={k: v for k, v in OBSERVED.items() if k != "python313.zip"})
    with pytest.raises(errors.PackageIntegrityFailure, match="owner-pinned"):
        gate(ev, pinned="1" * 64)
    # a self-consistent rewrite of the evidence for another tree still fails against the live tree
    forged = dataclasses.replace(ev, file_hashes=tuple(sorted(edited.items())), tree_digest=rt.interpreter_tree_digest(edited))
    with pytest.raises(errors.PackageIntegrityFailure):
        gate(forged)


def test_the_gate_requires_every_live_binary_to_be_attested():
    ev = verify()
    partial = dataclasses.replace(ev, verified_binaries=ev.verified_binaries[:1])
    with pytest.raises(errors.RuntimeUntrusted, match="every executable binary"):
        gate(partial)


@pytest.mark.parametrize("pinned", ["", "0" * 63, "G" * 64, "A" * 64, None])
def test_the_gate_requires_a_wellformed_pinned_digest(pinned):
    with pytest.raises(errors.RuntimeUntrusted):
        rt.require_trusted_runtime(env(), POLICY, verify(), observed_interpreter=OBSERVED, pinned_tree_sha256=pinned)  # type: ignore[arg-type]


def test_the_gate_requires_a_live_observation():
    for observed in ({}, None, [("python.exe", OBSERVED["python.exe"])]):
        with pytest.raises(errors.RuntimeUntrusted):
            rt.require_trusted_runtime(env(), POLICY, verify(), observed_interpreter=observed, pinned_tree_sha256=PINNED)  # type: ignore[arg-type]


def test_the_tree_digest_is_canonical_and_strict():
    assert rt.interpreter_tree_digest(OBSERVED) == rt.interpreter_tree_digest(dict(reversed(list(OBSERVED.items()))))
    with pytest.raises(errors.RuntimeUntrusted):
        rt.interpreter_tree_digest({})
    for bad in ({"python.exe": "ABC"}, {"python.exe": "0" * 64 + "0"}, {"python.exe": 5}):
        with pytest.raises(errors.PackageIntegrityFailure):
            rt.interpreter_tree_digest(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("name", ["python313._pth", "python313.zip"])
def test_non_binary_files_that_determine_the_import_path_need_a_reference_too(name):
    refs = dict(REFS)
    refs.pop(name)
    with pytest.raises(errors.RuntimeUntrusted) as e:
        verify(references=refs)
    assert name in e.value.detail and "independent reference" in e.value.detail


@pytest.mark.parametrize("name", ["python313._pth", "python313.zip"])
def test_a_tampered_import_path_file_is_an_integrity_failure(name):
    observed = dict(OBSERVED, **{name: sha(b"tampered")})
    entries = [{"path": k, "sha256": observed[k], "status": "Valid", "signer": "Python Software Foundation"} for k in sorted(BINARIES)]
    with pytest.raises(errors.PackageIntegrityFailure):
        verify(observed_sha256=observed, signature_report=json.dumps({"schema": rt.SIGNATURE_SCHEMA, "entries": entries}).encode())


def test_certificate_thumbprints_can_be_pinned():
    pol = rt.ProvenancePolicy(required_binaries=("python.exe", "python313.dll"), allowed_thumbprints=frozenset({"ab" * 20}))
    entries = [{"path": k, "sha256": OBSERVED[k], "status": "Valid", "signer": "Python Software Foundation", "thumbprint": "AB" * 20}
               for k in sorted(BINARIES)]
    good = json.dumps({"schema": rt.SIGNATURE_SCHEMA, "entries": entries}).encode()
    assert verify(policy=pol, signature_report=good).verified_binaries
    entries[0]["thumbprint"] = "cd" * 20
    with pytest.raises(errors.RuntimeUntrusted) as e:
        verify(policy=pol, signature_report=json.dumps({"schema": rt.SIGNATURE_SCHEMA, "entries": entries}).encode())
    assert "thumbprint" in e.value.detail
    with pytest.raises(errors.RuntimeUntrusted):  # a pinned policy cannot be satisfied by a report without thumbprints
        verify(policy=pol)
    bad_type = [{"path": "python.exe", "sha256": OBSERVED["python.exe"], "status": "Valid", "signer": "x", "thumbprint": 5}]
    with pytest.raises(errors.RuntimeUntrusted):
        verify(signature_report=json.dumps({"schema": rt.SIGNATURE_SCHEMA, "entries": bad_type}).encode())


def test_import_hooks_on_sys_path_hooks_are_checked():
    assert any("path_hooks" in f for f in findings(path_hooks=("editable_hook.path_hook",)))
    assert findings(path_hooks=tuple(rt.DEFAULT_PATH_HOOKS)) == []


def test_missing_signature_report_or_empty_tree_fails_closed():
    with pytest.raises(errors.RuntimeUntrusted):
        verify(signature_report=None)
    with pytest.raises(errors.RuntimeUntrusted):
        verify(observed_sha256={})


def test_a_signed_binary_without_an_independent_reference_is_not_trusted():
    # Valid Authenticode alone is not provenance: we never assume another
    # distribution's identical-looking binary is the same file.
    refs = dict(REFS)
    refs.pop("python313.dll")
    with pytest.raises(errors.RuntimeUntrusted) as e:
        verify(references=refs)
    assert "independent reference" in e.value.detail
    with pytest.raises(errors.RuntimeUntrusted):
        verify(references={})


def test_a_reference_that_differs_from_the_file_is_an_integrity_failure():
    with pytest.raises(errors.PackageIntegrityFailure):
        verify(references=dict(REFS, **{"python.exe": sha(b"another-distribution-python")}))


@pytest.mark.parametrize("status", ["NotSigned", "HashMismatch", "UnknownError", "valid", ""])
def test_only_a_valid_signature_is_accepted(status):
    entries = [{"path": k, "sha256": OBSERVED[k], "status": "Valid", "signer": "Python Software Foundation"} for k in REFS]
    entries[0]["status"] = status
    with pytest.raises(errors.RuntimeUntrusted):
        verify(signature_report=json.dumps({"schema": rt.SIGNATURE_SCHEMA, "entries": entries}).encode())


def test_an_unapproved_signer_is_refused():
    entries = [{"path": k, "sha256": OBSERVED[k], "status": "Valid", "signer": "Python Software Foundation"} for k in REFS]
    entries[1]["signer"] = "Evil Corp"
    with pytest.raises(errors.RuntimeUntrusted):
        verify(signature_report=json.dumps({"schema": rt.SIGNATURE_SCHEMA, "entries": entries}).encode())


def test_a_report_hash_that_does_not_match_the_file_on_disk_is_refused():
    entries = [{"path": k, "sha256": OBSERVED[k], "status": "Valid", "signer": "Python Software Foundation"} for k in REFS]
    entries[0]["sha256"] = "0" * 64
    with pytest.raises(errors.PackageIntegrityFailure):
        verify(signature_report=json.dumps({"schema": rt.SIGNATURE_SCHEMA, "entries": entries}).encode())


def test_an_unlisted_executable_in_the_tree_is_refused():
    observed = dict(OBSERVED, **{"extra.dll": sha(b"x")})
    with pytest.raises(errors.RuntimeUntrusted) as e:
        verify(observed_sha256=observed)
    assert "extra.dll" in e.value.detail


def test_a_missing_required_binary_is_refused():
    observed = {k: v for k, v in OBSERVED.items() if k != "python313.dll"}
    refs = {k: v for k, v in REFS.items() if k != "python313.dll"}
    entries = [{"path": k, "sha256": observed[k], "status": "Valid", "signer": "Python Software Foundation"}
               for k in refs if k in BINARIES]
    with pytest.raises(errors.RuntimeUntrusted) as e:
        verify(observed_sha256=observed, references=refs, signature_report=json.dumps({"schema": rt.SIGNATURE_SCHEMA, "entries": entries}).encode())
    assert "missing" in e.value.detail


@pytest.mark.parametrize(
    "bad",
    [b"\xff", b"not json", b"[]", json.dumps({"schema": "x", "entries": []}).encode(),
     json.dumps({"schema": rt.SIGNATURE_SCHEMA, "entries": "x"}).encode(),
     json.dumps({"schema": rt.SIGNATURE_SCHEMA, "entries": [{"path": "python.exe"}]}).encode(),
     json.dumps({"schema": rt.SIGNATURE_SCHEMA, "entries": [], "extra": 1}).encode()],
)
def test_malformed_signature_reports_are_refused(bad):
    with pytest.raises(errors.RuntimeUntrusted):
        verify(signature_report=bad)


def test_duplicate_and_unknown_report_entries_and_unknown_references_are_refused():
    entry = {"path": "python.exe", "sha256": OBSERVED["python.exe"], "status": "Valid", "signer": "Python Software Foundation"}
    with pytest.raises(errors.RuntimeUntrusted):
        verify(signature_report=json.dumps({"schema": rt.SIGNATURE_SCHEMA, "entries": [entry, dict(entry, path="PYTHON.EXE")]}).encode())
    with pytest.raises(errors.RuntimeUntrusted):
        verify(signature_report=json.dumps({"schema": rt.SIGNATURE_SCHEMA, "entries": [dict(entry, path="ghost.dll")]}).encode())
    with pytest.raises(errors.RuntimeUntrusted):
        verify(references=dict(REFS, **{"ghost.dll": "0" * 64}))


def test_provenance_policy_requires_named_valid_binaries():
    with pytest.raises(ValueError):
        rt.ProvenancePolicy(required_binaries=())
    with pytest.raises(errors.PackageIntegrityFailure):
        rt.ProvenancePolicy(required_binaries=("../python.exe",))
