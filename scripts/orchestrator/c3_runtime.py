"""G1.6-C3-G0: trusted-runtime verification (offline, read-only).

The ACL guard is only as trustworthy as the code that runs it. This module
checks, from a SNAPSHOT of the executing interpreter, that the process is the
owner-approved immutable runtime and not something an agent can steer:

  * interpreter / prefix / working directory are under the trusted root;
  * ``sys.flags`` request isolation (no env, no user site, no bytecode writes);
  * every ``sys.path`` entry and every imported module's origin is under the
    trusted root - never a relative entry, an agent-writable location, or an
    unnamed/unknown origin;
  * no ``PYTHON*`` (or loader-injection) environment variable is present;
  * no ``sitecustomize`` / ``usercustomize`` startup hook and only the
    standard import machinery on ``sys.meta_path``.

It also verifies interpreter *binary provenance* from caller-supplied facts
(hashes, an Authenticode report, owner-recorded reference hashes). Provenance is
never assumed: a missing signature, missing reference, unlisted executable or
hash mismatch fails closed, and two distributions are NEVER presumed to ship
identical binaries.

Everything here is pure and testable with synthetic snapshots; the Windows path
rules are evaluated with ``ntpath`` so Linux CI exercises them too.
"""

from __future__ import annotations

import json
import ntpath
import os
import posixpath
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from . import acl_guard, c3_package, errors

DEFAULT_REQUIRED_FLAGS = ("isolated", "no_user_site", "ignore_environment", "dont_write_bytecode")
DEFAULT_META_PATH = frozenset({
    "_frozen_importlib.BuiltinImporter",
    "_frozen_importlib.FrozenImporter",
    "_frozen_importlib_external.PathFinder",
})
DEFAULT_PATH_HOOKS = frozenset({
    "zipimport.zipimporter",
    "_frozen_importlib_external.FileFinder.path_hook.<locals>.path_hook_for_FileFinder",
})
FORBIDDEN_MODULES = frozenset({"sitecustomize", "usercustomize"})
FORBIDDEN_ENV_EXACT = frozenset({"LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH"})
BINARY_SUFFIXES = (".exe", ".dll", ".pyd")
SIGNATURE_SCHEMA = "petcare.c3.signature-report/v1"
DEFAULT_ALLOWED_SIGNERS = frozenset({"Python Software Foundation"})


def _canon(platform: str, path: Any) -> str:
    try:
        return acl_guard.canonical_windows_path(path) if platform == "nt" else acl_guard.canonical_posix_path(path)
    except acl_guard.PathRejected as exc:
        raise ValueError(f"unsafe path form: {exc}") from exc


def _within(platform: str, child: str, root: str) -> bool:
    pm = ntpath if platform == "nt" else posixpath
    sep = "\\" if platform == "nt" else "/"
    c = pm.normcase(pm.normpath(child))
    r = pm.normcase(pm.normpath(root))
    return c == r or c.startswith(r.rstrip(sep) + sep)


@dataclass(frozen=True)
class RuntimePolicy:
    platform: str
    trusted_root: str
    agent_writable_roots: tuple[str, ...] = ()
    expected_executable: str | None = None
    allowed_meta_path: frozenset[str] = DEFAULT_META_PATH
    allowed_path_hooks: frozenset[str] = DEFAULT_PATH_HOOKS
    required_flags: tuple[str, ...] = DEFAULT_REQUIRED_FLAGS

    def __post_init__(self) -> None:
        if self.platform not in ("nt", "posix"):
            raise ValueError("platform must be 'nt' or 'posix'")
        root = _canon(self.platform, self.trusted_root)
        writable = tuple(_canon(self.platform, p) for p in self.agent_writable_roots)
        for w in writable:
            if _within(self.platform, root, w) or _within(self.platform, w, root):
                raise ValueError("the trusted root overlaps an agent-writable root")
        object.__setattr__(self, "trusted_root", root)
        object.__setattr__(self, "agent_writable_roots", writable)
        if self.expected_executable is not None:
            exe = _canon(self.platform, self.expected_executable)
            if not _within(self.platform, exe, root):
                raise ValueError("the expected executable is outside the trusted root")
            object.__setattr__(self, "expected_executable", exe)


@dataclass(frozen=True)
class ModuleOrigin:
    name: str
    kind: str                 # builtin | frozen | file | namespace | unknown
    paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class EnvironmentSnapshot:
    platform: str
    executable: str
    prefix: str
    base_prefix: str
    cwd: str
    flags: Mapping[str, int]
    sys_path: tuple[str, ...]
    env_names: tuple[str, ...]
    modules: tuple[ModuleOrigin, ...]
    meta_path: tuple[str, ...]
    path_hooks: tuple[str, ...] = ()


def capture_environment() -> EnvironmentSnapshot:
    """Snapshot the CURRENT interpreter (read-only; reads sys/os only)."""

    flag_names = ("isolated", "no_user_site", "no_site", "ignore_environment", "dont_write_bytecode", "safe_path")
    flags = {n: int(getattr(sys.flags, n)) for n in flag_names if hasattr(sys.flags, n)}
    mods: list[ModuleOrigin] = []
    for name, mod in sorted(list(sys.modules.items())):
        spec = getattr(mod, "__spec__", None)
        origin = getattr(spec, "origin", None) if spec is not None else None
        if origin == "built-in" or (spec is None and name in sys.builtin_module_names):
            mods.append(ModuleOrigin(name, "builtin"))
        elif origin == "frozen":
            mods.append(ModuleOrigin(name, "frozen"))
        elif isinstance(origin, str) and origin not in ("namespace",):
            mods.append(ModuleOrigin(name, "file", (origin,)))
        elif spec is not None and getattr(spec, "submodule_search_locations", None):
            mods.append(ModuleOrigin(name, "namespace", tuple(str(p) for p in spec.submodule_search_locations)))
        elif name == "__main__" and isinstance(getattr(mod, "__file__", None), str):
            mods.append(ModuleOrigin(name, "file", (mod.__file__,)))
        else:
            mods.append(ModuleOrigin(name, "unknown"))
    meta = []
    for finder in sys.meta_path:
        cls = finder if isinstance(finder, type) else type(finder)
        meta.append(f"{cls.__module__}.{cls.__qualname__}")
    hooks = []
    for hook in sys.path_hooks:
        hooks.append(f"{getattr(hook, '__module__', '?')}.{getattr(hook, '__qualname__', type(hook).__qualname__)}")
    return EnvironmentSnapshot(
        platform="nt" if os.name == "nt" else "posix",
        executable=sys.executable,
        prefix=sys.prefix,
        base_prefix=sys.base_prefix,
        cwd=os.getcwd(),
        flags=flags,
        sys_path=tuple(sys.path),
        env_names=tuple(sorted(os.environ)),
        modules=tuple(mods),
        meta_path=tuple(meta),
        path_hooks=tuple(hooks),
    )


def environment_findings(env: EnvironmentSnapshot, policy: RuntimePolicy) -> list[str]:
    """All reasons the snapshot is not the trusted runtime (empty = trusted)."""

    out: list[str] = []
    pf = policy.platform
    if env.platform != pf:
        out.append(f"snapshot platform {env.platform!r} differs from the policy platform {pf!r}")

    for name in policy.required_flags:
        if env.flags.get(name) != 1:
            out.append(f"interpreter flag {name} is not set (isolation required)")
    if "safe_path" in env.flags and env.flags["safe_path"] != 1:
        out.append("interpreter flag safe_path is not set")

    def inside(label: str, path: Any) -> None:
        try:
            canon = _canon(pf, path)
        except ValueError as exc:
            out.append(f"{label}: {exc}")
            return
        for w in policy.agent_writable_roots:
            if _within(pf, canon, w):
                out.append(f"{label} is inside an agent-writable location ({canon})")
                return
        if not _within(pf, canon, policy.trusted_root):
            out.append(f"{label} is outside the trusted root ({canon})")

    inside("interpreter executable", env.executable)
    if policy.expected_executable is not None:
        try:
            if _canon(pf, env.executable) != policy.expected_executable:
                out.append("interpreter executable is not the expected pinned executable")
        except ValueError:
            pass
    inside("sys.prefix", env.prefix)
    inside("sys.base_prefix", env.base_prefix)
    inside("working directory", env.cwd)

    for idx, entry in enumerate(env.sys_path):
        if not isinstance(entry, str) or entry in ("", ".") or entry.startswith(".."):
            out.append(f"sys.path[{idx}] is empty or relative (current-directory import)")
        else:
            inside(f"sys.path[{idx}]", entry)

    bad_env = [n for n in env.env_names if n.upper().startswith("PYTHON") or n in FORBIDDEN_ENV_EXACT]
    if bad_env:
        out.append("unsafe interpreter/loader environment variable(s) present: " + ", ".join(sorted(bad_env)[:6]))

    for mod in env.modules:
        if mod.name in FORBIDDEN_MODULES:
            out.append(f"startup hook module {mod.name} is loaded")
        if mod.kind in ("builtin", "frozen"):
            continue
        if mod.kind == "unknown":
            out.append(f"module {mod.name} has an unknown origin")
            continue
        for p in mod.paths:
            inside(f"module {mod.name}", p)

    extra_finders = sorted(set(env.meta_path) - policy.allowed_meta_path)
    if extra_finders:
        out.append("non-standard import finder(s) on sys.meta_path: " + ", ".join(extra_finders[:4]))
    extra_hooks = sorted(set(env.path_hooks) - policy.allowed_path_hooks)
    if extra_hooks:
        out.append("non-standard import hook(s) on sys.path_hooks: " + ", ".join(extra_hooks[:4]))
    return out


def verify_execution_environment(env: EnvironmentSnapshot, policy: RuntimePolicy) -> None:
    findings = environment_findings(env, policy)
    if findings:
        raise errors.RuntimeUntrusted("; ".join(findings[:8]))


# --- interpreter binary provenance ----------------------------------------------


@dataclass(frozen=True)
class ProvenancePolicy:
    required_binaries: tuple[str, ...]
    allowed_signers: frozenset[str] = DEFAULT_ALLOWED_SIGNERS
    # When non-empty, a binary's certificate thumbprint must be one of these
    # (a display name alone is not an identity). Lower-case hex.
    allowed_thumbprints: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.required_binaries:
            raise ValueError("at least one required binary must be named")
        for rel in self.required_binaries:
            c3_package.validate_rel_path(rel)


def ingest_signature_report(data: bytes, observed_sha256: Mapping[str, str]) -> dict[str, tuple[str, str, str]]:
    """Strictly parse an Authenticode report produced by an owner-approved
    read-only step and BIND each entry to the observed file hash, so a report
    cannot vouch for a file other than the one on disk. The report itself is
    only as trustworthy as the step that produced it: G1 produces it with the
    host's own signature verifier on the exact installed bytes. The probe
    approval does NOT pin the report's digest; it pins the resulting
    interpreter tree digest (``interpreter_tree_sha256``)."""

    try:
        doc = json.loads(data.decode("utf-8"))
    except ValueError:
        raise errors.RuntimeUntrusted("signature report is not valid JSON") from None
    if not isinstance(doc, dict) or set(doc) != {"schema", "entries"} or doc["schema"] != SIGNATURE_SCHEMA:
        raise errors.RuntimeUntrusted("signature report has the wrong shape or schema")
    if not isinstance(doc["entries"], list):
        raise errors.RuntimeUntrusted("signature report entries must be a list")
    out: dict[str, tuple[str, str, str]] = {}
    lowered = {k.lower(): k for k in observed_sha256}
    for item in doc["entries"]:
        required = {"path", "sha256", "status", "signer"}
        if not isinstance(item, dict) or not required <= set(item) or set(item) - required - {"thumbprint"}:
            raise errors.RuntimeUntrusted("signature report entry has the wrong shape")
        if "thumbprint" in item and not isinstance(item["thumbprint"], str):
            raise errors.RuntimeUntrusted("signature report thumbprint must be text")
        path = c3_package.validate_rel_path(item["path"])
        if path.lower() in {k.lower() for k in out}:
            raise errors.RuntimeUntrusted("signature report lists a file twice")
        real = lowered.get(path.lower())
        if real is None:
            raise errors.RuntimeUntrusted("signature report names a file that is not in the tree")
        if item["sha256"] != observed_sha256[real]:
            raise errors.PackageIntegrityFailure(f"signature report hash for {path} does not match the file on disk")
        if not isinstance(item["status"], str) or not isinstance(item["signer"], str):
            raise errors.RuntimeUntrusted("signature report status/signer must be text")
        out[real] = (item["status"], item["signer"], item.get("thumbprint", "").lower())
    return out


_HEX64 = re.compile(r"^[0-9a-f]{64}$")
# Module-private seal: only verify_interpreter_provenance() passes it. This stops
# naive or accidental construction of evidence. It is NOT a security boundary
# against code that runs in this process (that code can read the seal). The
# binding that counts is in require_trusted_runtime: the evidence must equal a
# LIVE re-scan of the interpreter tree AND the owner-pinned tree digest.
_EVIDENCE_SEAL = object()


def interpreter_tree_digest(observed_sha256: Mapping[str, str]) -> str:
    """Canonical digest of an interpreter tree: ``{relpath: sha256}`` sorted by path.
    The owner pins this value in the probe approval (``interpreter_tree_sha256``)."""

    if not observed_sha256:
        raise errors.RuntimeUntrusted("an empty interpreter tree has no digest")
    lines = []
    for rel in sorted(observed_sha256):
        value = observed_sha256[rel]
        if not isinstance(rel, str) or not isinstance(value, str) or not _HEX64.match(value):
            raise errors.PackageIntegrityFailure("interpreter tree entries must map paths to lowercase sha256 hex")
        lines.append(f"{rel.lower()}={value}")
    return c3_package.sha256_hex("\n".join(lines).encode("utf-8"))


@dataclass(frozen=True)
class ProvenanceEvidence:
    """The result of a successful provenance verification. The runtime gate
    consumes this, not a flag. It carries the exact per-file hashes it attested,
    so the gate can compare them file by file against a live re-scan."""

    verified_binaries: tuple[str, ...]
    attested_files: int
    tree_digest: str
    file_hashes: tuple[tuple[str, str], ...] = ()
    _seal: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._seal is not _EVIDENCE_SEAL:
            raise ValueError("provenance evidence can only be produced by verify_interpreter_provenance")
        if not self.verified_binaries or self.attested_files <= 0 or not isinstance(self.tree_digest, str):
            raise ValueError("provenance evidence must name attested files and a tree digest")
        hashes = dict(self.file_hashes)
        if len(hashes) != len(self.file_hashes) or self.attested_files != len(hashes):
            raise ValueError("provenance evidence file list is inconsistent")
        if interpreter_tree_digest(hashes) != self.tree_digest:
            raise ValueError("provenance evidence digest does not match its own file hashes")
        if not set(self.verified_binaries) <= set(hashes):
            raise ValueError("provenance evidence names a binary it did not attest")


def verify_interpreter_provenance(
    *,
    observed_sha256: Mapping[str, str],
    signature_report: bytes | None,
    references: Mapping[str, str],
    policy: ProvenancePolicy,
) -> ProvenanceEvidence:
    """Fail closed unless EVERY file of the interpreter tree equals an explicitly
    recorded independent reference hash (``python._pth``, the stdlib zip and loose
    ``.py`` files determine what code runs, so they are attested too), and every
    executable binary is additionally validly signed by an allowed signer."""

    if not observed_sha256:
        raise errors.RuntimeUntrusted("no interpreter files were observed")
    if signature_report is None:
        raise errors.RuntimeUntrusted("no signature report was supplied (provenance unverifiable)")
    sigs = ingest_signature_report(signature_report, observed_sha256)
    binaries = sorted(p for p in observed_sha256 if p.lower().endswith(BINARY_SUFFIXES))
    present = {p.lower() for p in binaries}
    for need in policy.required_binaries:
        if need.lower() not in present:
            raise errors.RuntimeUntrusted(f"required interpreter binary is missing: {need}")
    refs = {k.lower(): v for k, v in references.items()}
    unknown_refs = sorted(set(refs) - {p.lower() for p in observed_sha256})
    if unknown_refs:
        raise errors.RuntimeUntrusted("a reference hash names a file that is not in the tree")
    verified: list[str] = []
    for rel in sorted(observed_sha256):
        ref = refs.get(rel.lower())
        if ref is None:
            raise errors.RuntimeUntrusted(f"no independent reference hash is recorded for: {rel}")
        if ref != observed_sha256[rel]:
            raise errors.PackageIntegrityFailure(f"file does not match its recorded reference hash: {rel}")
        if rel in binaries:
            sig = sigs.get(rel)
            if sig is None:
                raise errors.RuntimeUntrusted(f"executable file has no signature entry: {rel}")
            status, signer, thumb = sig
            if status != "Valid":
                raise errors.RuntimeUntrusted(f"executable file is not validly signed: {rel} ({status})")
            if signer not in policy.allowed_signers:
                raise errors.RuntimeUntrusted(f"executable file has an unapproved signer: {rel}")
            if policy.allowed_thumbprints and thumb not in policy.allowed_thumbprints:
                raise errors.RuntimeUntrusted(f"executable file's certificate thumbprint is not approved: {rel}")
            verified.append(rel)
    hashes = tuple(sorted((k, observed_sha256[k]) for k in observed_sha256))
    return ProvenanceEvidence(
        verified_binaries=tuple(verified), attested_files=len(hashes), tree_digest=interpreter_tree_digest(dict(hashes)),
        file_hashes=hashes, _seal=_EVIDENCE_SEAL,
    )


def is_genuine_evidence(evidence: Any) -> bool:
    """True only for evidence produced by :func:`verify_interpreter_provenance`:
    the exact class, the module seal, and plain builtin field values (so no
    caller-defined ``__eq__``/``__iter__``/``__hash__`` can run when it is compared)."""

    if type(evidence) is not ProvenanceEvidence or evidence._seal is not _EVIDENCE_SEAL:
        return False
    fh, vb = evidence.file_hashes, evidence.verified_binaries
    if type(fh) is not tuple or type(vb) is not tuple or type(evidence.tree_digest) is not str or type(evidence.attested_files) is not int:
        return False
    if not all(type(p) is tuple and len(p) == 2 and type(p[0]) is str and type(p[1]) is str for p in fh):
        return False
    return all(type(b) is str for b in vb)


def require_trusted_runtime(
    env: EnvironmentSnapshot,
    policy: RuntimePolicy,
    evidence: "ProvenanceEvidence | None",
    *,
    observed_interpreter: Mapping[str, str],
    pinned_tree_sha256: str,
) -> None:
    """The gate for ENFORCED operations. All of these must hold:

    * ``evidence`` is genuine :class:`ProvenanceEvidence` (never a flag);
    * its per-file hashes equal ``observed_interpreter`` - a LIVE re-scan of the
      interpreter tree taken by the caller of this gate - file for file, with
      nothing missing or extra (stale or substituted evidence fails);
    * its digest equals the live digest AND the owner-pinned ``pinned_tree_sha256``;
    * every executable binary in the live tree was attested as validly signed;
    * the live environment snapshot is the isolated trusted runtime.
    """

    if not is_genuine_evidence(evidence):
        raise errors.RuntimeUntrusted("interpreter provenance evidence is missing")
    if type(env) is not EnvironmentSnapshot or type(policy) is not RuntimePolicy:
        raise errors.RuntimeUntrusted("the runtime snapshot or policy is not a genuine object")
    # The security RULES are fixed: a policy may only be at least as strict as the defaults.
    if (not set(DEFAULT_REQUIRED_FLAGS) <= set(policy.required_flags)
            or not set(policy.allowed_meta_path) <= DEFAULT_META_PATH
            or not set(policy.allowed_path_hooks) <= DEFAULT_PATH_HOOKS
            or policy.expected_executable is None or not policy.agent_writable_roots):
        raise errors.RuntimeUntrusted("the runtime policy weakens the fixed runtime security rules")
    if not isinstance(pinned_tree_sha256, str) or not _HEX64.match(pinned_tree_sha256):
        raise errors.RuntimeUntrusted("no owner-pinned interpreter tree digest is available")
    if not isinstance(observed_interpreter, Mapping) or not observed_interpreter:
        raise errors.RuntimeUntrusted("the live interpreter tree could not be observed")
    live_digest = interpreter_tree_digest(observed_interpreter)
    if dict(evidence.file_hashes) != dict(observed_interpreter):
        raise errors.PackageIntegrityFailure("provenance evidence does not match the live interpreter tree (stale or substituted)")
    if evidence.tree_digest != live_digest:
        raise errors.PackageIntegrityFailure("provenance evidence digest differs from the live interpreter tree digest")
    if live_digest != pinned_tree_sha256:
        raise errors.PackageIntegrityFailure("the live interpreter tree is not the owner-pinned interpreter tree")
    live_binaries = {p for p in observed_interpreter if p.lower().endswith(BINARY_SUFFIXES)}
    if set(evidence.verified_binaries) != live_binaries:
        raise errors.RuntimeUntrusted("provenance evidence does not attest every executable binary in the live tree")
    verify_execution_environment(env, policy)


def environment_summary(env: EnvironmentSnapshot) -> dict[str, Any]:
    """A redaction-safe summary (env NAMES only, never values)."""

    return {
        "platform": env.platform,
        "flags": dict(env.flags),
        "sys_path_entries": len(env.sys_path),
        "modules": len(env.modules),
        "env_names_python": sorted(n for n in env.env_names if n.upper().startswith("PYTHON")),
        "meta_path": list(env.meta_path),
    }
