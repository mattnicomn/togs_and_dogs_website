"""SEC-1B offline, owner-run inspector for three historical Terraform artifacts.

Purpose
-------
Classify which *categories* of sensitive data may be present in three binary
artifacts that were committed to this repository's history, without ever
revealing a value. Output is restricted to fixed identifiers, fixed reason
codes, counts and (optionally) sanitized resource addresses / attribute paths.

Hard rules implemented here
---------------------------
* Only three pinned artifacts can be inspected (commit:path, blob id, size).
  No other path, file or URL is accepted.
* Artifact bytes are obtained from the LOCAL git object store with fixed
  ``git cat-file`` arguments and kept in memory. Nothing is extracted or
  written to disk. Git is invoked with ``protocol.allow=never`` and
  ``GIT_NO_LAZY_FETCH=1`` so it cannot reach the network, and ``GIT_TRACE*``
  variables are removed from its environment.
* ZIP entries are validated one by one; real decompressed bytes are counted
  while reading (header sizes are not trusted).
* Both ``tfstate`` and ``tfstate-prev`` are parsed when present.
* Fail closed: a category is ABSENT only when every byte that could hold it
  was structurally parsed. Anything incomplete is UNKNOWN. A pattern match is
  reported as PRESENT (a *potential* finding for the owner to judge).
* Values, value lengths, fragments, hashes, entry names and exception
  messages are never printed.

Unavoidable residual exposure (owner must accept or mitigate)
-------------------------------------------------------------
* Memory: artifact bytes, decompressed entries and decoded strings live in
  this process's memory. Python cannot reliably zero them.
* Pagefile / hibernation: the OS may page that memory to disk (pagefile.sys,
  hiberfil.sys).
* Crash dumps: if Python crashes, Windows Error Reporting may write a dump
  containing process memory under %LOCALAPPDATA%\\CrashDumps or similar.
* Antivirus: real-time scanners may inspect the git object store and, with
  automatic sample submission enabled, may upload files they consider
  suspicious. This tool writes no new files, but the objects already exist in
  the repository's .git directory.
* The git object store itself already holds these blobs; this tool does not
  change that.
* Same Windows identity: other processes running as the owner (including AI
  agents) could read this process's memory or the repository. Close them.

Usage (owner only, after review)::

    python -I -B scripts\\sec1\\sec1b_inspect.py --repo <repo> \\
        --expected-script-sha256 <reviewed sha256 of this file> [--locations]

Exit codes: 0 every artifact fully classified with no UNKNOWN; 1 any UNKNOWN,
integrity failure or internal error; 2 usage / self-verification failure.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import io
import json
import os
import re
import stat as _stat
import subprocess
import sys
import zipfile
import zlib
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Pinned artifacts (metadata recorded in SEC-1A / SEC-1B-T preflight)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArtifactSpec:
    ident: str
    commit: str
    path: str
    blob: str
    size: int


ARTIFACTS: Tuple[ArtifactSpec, ...] = (
    ArtifactSpec("ROLLBACK", "b4d422e13cd71ea76f1f071c987c9b22f8a7d7c7",
                 "infra/prod/tfplan-rollback", "3504b25e1e4ef509f75df7c0e9dbae60874d3c5d", 92835),
    ArtifactSpec("FRONTEND", "87163672e6699036a9ca2fc3b78f345b5a5bd198",
                 "infra/prod/tfplan-frontend", "08c5792efea051de34d5d0c0666d118bb34de5af", 66684),
    ArtifactSpec("USMH", "87163672e6699036a9ca2fc3b78f345b5a5bd198",
                 "infra/prod/tfplan-usmh", "7b5fa7a56a05ffdc690753d741794faffe9089a5", 73385),
)

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

MAX_ENTRIES = 2000
MAX_ENTRY_BYTES = 50 * 1024 * 1024
MAX_TOTAL_BYTES = 200 * 1024 * 1024
MAX_RATIO = 100
MAX_NAME_LEN = 255
MAX_JSON_DEPTH = 128
READ_CHUNK = 64 * 1024

# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

VALUE_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("GOOGLE_REFRESH_TOKEN", r"(?<![A-Za-z0-9])1//[0-9A-Za-z_\-]{20,}"),
    ("GOOGLE_ACCESS_TOKEN", r"ya29\.[0-9A-Za-z_\-]{20,}"),
    ("JWT_TOKEN", r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    ("GOOGLE_CLIENT_SECRET", r"GOCSPX-[0-9A-Za-z_\-]{10,}"),
    ("GOOGLE_CLIENT_ID", r"[0-9]+-[0-9a-z]+\.apps\.googleusercontent\.com"),
    ("AWS_ACCESS_KEY_ID", r"(?<![A-Z0-9])(?:AKIA|ASIA)[0-9A-Z]{16}(?![A-Z0-9])"),
    ("PRIVATE_KEY_PEM", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("URL_EMBEDDED_CREDENTIAL", r"[A-Za-z][A-Za-z0-9+.\-]*://[^/\s:@\"']+:[^/\s@\"']+@"),
    ("STRIPE_KEY", r"(?:sk|rk)_(?:test|live)_[0-9A-Za-z]{10,}"),
    ("STRIPE_WEBHOOK_SECRET", r"whsec_[0-9A-Za-z]{10,}"),
    ("EMAIL_ADDRESS", r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}"),
)
_STR_PATTERNS = tuple((cid, re.compile(p)) for cid, p in VALUE_PATTERNS)
_BYTE_PATTERNS = tuple((cid, re.compile(p.encode("ascii"))) for cid, p in VALUE_PATTERNS)

OAUTH_FIELD_CATEGORIES = {
    "refresh_token": "OAUTH_REFRESH_TOKEN_FIELD",
    "access_token": "OAUTH_ACCESS_TOKEN_FIELD",
    "id_token": "OAUTH_ID_TOKEN_FIELD",
}
_NAMED_SENSITIVE = re.compile(
    r"(secret|password|passwd|token|private_key|client_secret|api_key|apikey|access_key|credential)",
    re.IGNORECASE)

STRUCTURAL_CATEGORIES = (
    "SECRETSMANAGER_SECRET_VALUE",
    "GOOGLE_USER_TOKENS_SECRET_TOKENS",
    "NAMED_SENSITIVE_ATTRIBUTE_NONEMPTY",
    "TF_SENSITIVE_ATTRIBUTES",
    "LAMBDA_ENV_SECRET_PATTERN",
) + tuple(OAUTH_FIELD_CATEGORIES.values())

ALL_CATEGORIES: Tuple[str, ...] = tuple(c for c, _ in VALUE_PATTERNS) + STRUCTURAL_CATEGORIES

PRESENT, ABSENT, UNKNOWN = "PRESENT", "ABSENT", "UNKNOWN"

# Entry classes
TFPLAN, TFSTATE, TFSTATE_PREV, TFCONFIG_FILE, TFCONFIG_DIR, LOCKFILE, UNEXPECTED, UNSAFE = (
    "TFPLAN", "TFSTATE", "TFSTATE_PREV", "TFCONFIG_FILE", "TFCONFIG_DIR", "LOCKFILE", "UNEXPECTED", "UNSAFE")
ENTRY_CLASSES = (TFPLAN, TFSTATE, TFSTATE_PREV, TFCONFIG_FILE, TFCONFIG_DIR, LOCKFILE, UNEXPECTED, UNSAFE)

# ---------------------------------------------------------------------------
# Results (sanitized by construction: fixed codes, counts, sanitized strings)
# ---------------------------------------------------------------------------


@dataclass
class CategoryResult:
    hits: int = 0
    locations: List[Tuple[str, str]] = field(default_factory=list)


@dataclass
class ScopeCoverage:
    complete: bool = True
    reasons: List[str] = field(default_factory=list)

    def fail(self, reason: str) -> None:
        self.complete = False
        if reason not in self.reasons:
            self.reasons.append(reason)


@dataclass
class ArtifactReport:
    ident: str
    integrity: str = "NOT_CHECKED"
    fmt: str = "UNKNOWN"
    fmt_reason: str = "NOT_PARSED"
    entries: Dict[str, int] = field(default_factory=lambda: {c: 0 for c in ENTRY_CLASSES})
    tf_version: str = "UNKNOWN"
    source_config: str = "UNKNOWN"
    state_scope: Dict[str, CategoryResult] = field(default_factory=dict)
    artifact_scope: Dict[str, CategoryResult] = field(default_factory=dict)
    state_cov: ScopeCoverage = field(default_factory=ScopeCoverage)
    artifact_cov: ScopeCoverage = field(default_factory=ScopeCoverage)
    internal_error: Optional[str] = None

    def __post_init__(self) -> None:
        for c in ALL_CATEGORIES:
            self.state_scope.setdefault(c, CategoryResult())
            self.artifact_scope.setdefault(c, CategoryResult())

    def __repr__(self) -> str:  # never expose internals
        return "ArtifactReport(%s)" % self.ident


class InspectionError(Exception):
    """Fixed-code error. Never carries data."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code

    def __repr__(self) -> str:
        return "InspectionError(%s)" % self.code


# ---------------------------------------------------------------------------
# Git access (fixed argv only, no network)
# ---------------------------------------------------------------------------

Runner = Callable[[Sequence[str]], Tuple[int, bytes]]


def _git_env() -> Dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_TRACE")}
    env["GIT_NO_LAZY_FETCH"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def make_git_runner(repo: str) -> Runner:
    """Return a runner restricted to the exact git argv this tool needs."""
    base = ["git", "-C", repo, "-c", "protocol.allow=never", "-c", "core.fsmonitor=false"]

    def runner(args: Sequence[str]) -> Tuple[int, bytes]:
        _assert_allowed_git_args(args)
        proc = subprocess.run(base + list(args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, env=_git_env(), shell=False, timeout=120)
        return proc.returncode, proc.stdout

    return runner


_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_ALLOWED_SPECS = {"%s:%s" % (a.commit, a.path) for a in ARTIFACTS}
_ALLOWED_COMMITS = {a.commit for a in ARTIFACTS}


def _assert_allowed_git_args(args: Sequence[str]) -> None:
    a = list(args)
    ok = (
        (len(a) == 2 and a[0] == "rev-parse" and a[1] in _ALLOWED_SPECS)
        or (len(a) == 3 and a[:2] == ["cat-file", "-s"] and bool(_HEX40.match(a[2])))
        or (len(a) == 3 and a[:2] == ["cat-file", "blob"] and bool(_HEX40.match(a[2])))
        or (len(a) == 5 and a[:2] == ["ls-tree", "--name-only"] and a[2] in _ALLOWED_COMMITS
            and a[3:] == ["--", "infra/prod/"])
    )
    if not ok:
        raise InspectionError("GIT_ARGS_NOT_ALLOWED")


def load_artifact(spec: ArtifactSpec, run: Runner, report: ArtifactReport) -> Optional[bytes]:
    rc, out = run(["rev-parse", "%s:%s" % (spec.commit, spec.path)])
    if rc != 0:
        report.integrity = "GIT_ERROR"
        return None
    if out.decode("ascii", "replace").strip() != spec.blob:
        report.integrity = "OBJECT_MISMATCH"
        return None
    rc, out = run(["cat-file", "-s", spec.blob])
    if rc != 0 or out.decode("ascii", "replace").strip() != str(spec.size):
        report.integrity = "SIZE_MISMATCH" if rc == 0 else "GIT_ERROR"
        return None
    rc, data = run(["cat-file", "blob", spec.blob])
    if rc != 0:
        report.integrity = "GIT_ERROR"
        return None
    if len(data) != spec.size:
        report.integrity = "SIZE_MISMATCH"
        return None
    report.integrity = "OK"
    return data


def repo_root_tf_names(spec: ArtifactSpec, run: Runner) -> Optional[set]:
    rc, out = run(["ls-tree", "--name-only", spec.commit, "--", "infra/prod/"])
    if rc != 0:
        return None
    names = set()
    for line in out.decode("utf-8", "replace").splitlines():
        base = line.rsplit("/", 1)[-1]
        if base.endswith(".tf"):
            names.add(base)
    return names


# ---------------------------------------------------------------------------
# Sanitizers for optional location output
# ---------------------------------------------------------------------------

REDACTED = "<redacted>"
_SEG = r"[A-Za-z_][A-Za-z0-9_\-]{0,63}"
_SEG_RE = re.compile("^%s$" % _SEG)
_CREDENTIAL_LIKE = re.compile(
    r"([spr]k_(test|live)_|whsec_|AKIA|ASIA|GOCSPX-|ya29\.|1//|github_pat_|xox[abpr]-"
    r"|(^|[^A-Za-z0-9])([spr]k_|gh[pousr]_|eyJ))")


def _safe_seg(s: object) -> str:
    if isinstance(s, str) and _SEG_RE.match(s) and not _CREDENTIAL_LIKE.search(s):
        return s
    return REDACTED


def sanitize_address(res: dict, inst: dict) -> str:
    parts = []
    module = res.get("module")
    if module is not None:
        if not isinstance(module, str) or not re.match(r"^(module\.%s(\[[0-9]{1,6}\])?\.?)+$" % _SEG, module + "."):
            return REDACTED
        if _CREDENTIAL_LIKE.search(module):
            return REDACTED
        parts.append(module)
    mode = res.get("mode")
    prefix = "data." if mode == "data" else ""
    t, n = _safe_seg(res.get("type")), _safe_seg(res.get("name"))
    if REDACTED in (t, n):
        return REDACTED
    addr = "%s%s.%s" % (prefix, t, n)
    idx = inst.get("index_key") if isinstance(inst, dict) else None
    if isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx < 10 ** 6:
        addr += "[%d]" % idx
    elif idx is not None:
        return REDACTED
    return ".".join(parts + [addr]) if parts else addr


def sanitize_path(path: Tuple[object, ...]) -> str:
    out = ""
    for seg in path:
        if isinstance(seg, int) and not isinstance(seg, bool):
            out += "[%d]" % seg
        else:
            s = _safe_seg(seg)
            out += s if not out else "." + s
    return out or "<root>"


# ---------------------------------------------------------------------------
# ZIP handling
# ---------------------------------------------------------------------------

_DRIVE = re.compile(r"^[A-Za-z]:")


def classify_entry(info: zipfile.ZipInfo) -> str:
    name = info.filename
    if (not name or len(name) > MAX_NAME_LEN or "\x00" in name or "\\" in name or name.startswith("/")
            or _DRIVE.match(name) or any(seg == ".." for seg in name.split("/"))
            or any(ord(ch) < 32 for ch in name)):
        return UNSAFE
    mode = (info.external_attr >> 16) & 0xFFFF
    if mode and _stat.S_ISLNK(mode):
        return UNSAFE
    if info.flag_bits & 0x1:
        return UNSAFE
    if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
        return UNSAFE
    if name == "tfplan":
        return TFPLAN
    if name == "tfstate":
        return TFSTATE
    if name == "tfstate-prev":
        return TFSTATE_PREV
    if name == ".terraform.lock.hcl":
        return LOCKFILE
    if name.startswith("tfconfig/"):
        return TFCONFIG_DIR if name.endswith("/") else TFCONFIG_FILE
    return UNEXPECTED


def read_entry_limited(zf: zipfile.ZipFile, info: zipfile.ZipInfo, budget: List[int]) -> bytes:
    """Read with real decompressed-byte accounting. Raises InspectionError."""
    buf = io.BytesIO()
    got = 0
    with zf.open(info, "r") as fh:
        while True:
            chunk = fh.read(READ_CHUNK)
            if not chunk:
                break
            got += len(chunk)
            budget[0] += len(chunk)
            if got > MAX_ENTRY_BYTES:
                raise InspectionError("ENTRY_TOO_LARGE")
            if budget[0] > MAX_TOTAL_BYTES:
                raise InspectionError("TOTAL_TOO_LARGE")
            if info.compress_size > 0 and got > MAX_RATIO * info.compress_size + READ_CHUNK:
                raise InspectionError("COMPRESSION_RATIO_EXCEEDED")
            if info.compress_size == 0 and got > READ_CHUNK:
                raise InspectionError("COMPRESSION_RATIO_EXCEEDED")
            buf.write(chunk)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def _scan_bytes(data: bytes, scope: Dict[str, CategoryResult]) -> None:
    for cid, rx in _BYTE_PATTERNS:
        n = sum(1 for _ in rx.finditer(data))
        if n:
            scope[cid].hits += n


def _scan_str(value: str, scope: Dict[str, CategoryResult], loc: Optional[Tuple[str, str]]) -> List[str]:
    found = []
    for cid, rx in _STR_PATTERNS:
        n = sum(1 for _ in rx.finditer(value))
        if n:
            scope[cid].hits += n
            if loc is not None:
                scope[cid].locations.append(loc)
            found.append(cid)
    return found


def _no_dup_pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise InspectionError("JSON_DUPLICATE_KEY")
        out[k] = v
    return out


def _check_depth(obj: object, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise InspectionError("JSON_TOO_DEEP")
    if isinstance(obj, dict):
        for v in obj.values():
            _check_depth(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _check_depth(v, depth + 1)


def parse_json_bytes(data: bytes) -> object:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise InspectionError("STATE_NOT_UTF8")
    try:
        obj = json.loads(text, object_pairs_hook=_no_dup_pairs)
    except InspectionError:
        raise
    except RecursionError:
        raise InspectionError("JSON_TOO_DEEP")
    except ValueError:
        raise InspectionError("STATE_NOT_JSON")
    _check_depth(obj)
    return obj


_VERSION_RE = re.compile(r"^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(?:[-+][0-9A-Za-z.\-]{1,32})?$")


def _walk_attributes(obj: object, path: Tuple[object, ...], address: str, scope: Dict[str, CategoryResult],
                     in_lambda_env: bool, cov: ScopeCoverage, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        cov.fail("JSON_TOO_DEEP")
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            sub = path + (k,)
            # aws_lambda_function: environment[<i>].variables.<NAME>
            env_here = in_lambda_env or (k == "variables" and len(path) >= 2 and path[-2] == "environment")
            if isinstance(k, str) and _NAMED_SENSITIVE.search(k) and _nonempty(v):
                scope["NAMED_SENSITIVE_ATTRIBUTE_NONEMPTY"].hits += 1
                scope["NAMED_SENSITIVE_ATTRIBUTE_NONEMPTY"].locations.append((address, sanitize_path(sub)))
            if isinstance(k, str) and k.lower() in OAUTH_FIELD_CATEGORIES and _nonempty(v):
                cid = OAUTH_FIELD_CATEGORIES[k.lower()]
                scope[cid].hits += 1
                scope[cid].locations.append((address, sanitize_path(sub)))
            _walk_attributes(v, sub, address, scope, env_here, cov, depth + 1)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _walk_attributes(v, path + (i,), address, scope, in_lambda_env, cov, depth + 1)
    elif isinstance(obj, str):
        found = _scan_str(obj, scope, (address, sanitize_path(path)))
        if in_lambda_env and any(c != "EMAIL_ADDRESS" for c in found):
            scope["LAMBDA_ENV_SECRET_PATTERN"].hits += 1
            scope["LAMBDA_ENV_SECRET_PATTERN"].locations.append((address, sanitize_path(path)))


def _nonempty(v: object) -> bool:
    if v is None or v is False:
        return False
    if isinstance(v, str):
        return v.strip() not in ("", "{}", "[]", "null")
    if isinstance(v, (list, dict)):
        return len(v) > 0
    return True


def _inspect_secret_version(attrs: dict, address: str, scope: Dict[str, CategoryResult],
                            cov: ScopeCoverage) -> None:
    secret_id = attrs.get("secret_id") if isinstance(attrs, dict) else None
    is_google_tokens = isinstance(secret_id, str) and "/google/user-tokens" in secret_id
    ss = attrs.get("secret_string")
    sb = attrs.get("secret_binary")
    if isinstance(sb, str) and sb:
        scope["SECRETSMANAGER_SECRET_VALUE"].hits += 1
        scope["SECRETSMANAGER_SECRET_VALUE"].locations.append((address, "secret_binary"))
    if ss is None:
        if "secret_string" not in attrs and not sb:
            cov.fail("SECRET_VALUE_MISSING")
        return
    if not isinstance(ss, str):
        cov.fail("SECRET_VALUE_UNPARSED")
        return
    stripped = ss.strip()
    if stripped in ("", "{}"):
        return
    scope["SECRETSMANAGER_SECRET_VALUE"].hits += 1
    scope["SECRETSMANAGER_SECRET_VALUE"].locations.append((address, "secret_string"))
    try:
        nested = json.loads(stripped, object_pairs_hook=_no_dup_pairs)
        _check_depth(nested)
    except (InspectionError, ValueError, RecursionError):
        cov.fail("NESTED_SECRET_UNPARSED")
        if is_google_tokens:
            cov.fail("GOOGLE_TOKENS_SECRET_UNPARSED")
        return
    nested_scope = {c: CategoryResult() for c in ALL_CATEGORIES}
    _walk_attributes(nested, ("secret_string",), address, nested_scope, False, cov)
    token_like = sum(nested_scope[c].hits for c in OAUTH_FIELD_CATEGORIES.values()) + \
        nested_scope["GOOGLE_REFRESH_TOKEN"].hits + nested_scope["GOOGLE_ACCESS_TOKEN"].hits
    # The outer walk already pattern-scanned the raw secret_string text; only
    # the structural OAuth field categories are added from the nested parse.
    for c in OAUTH_FIELD_CATEGORIES.values():
        scope[c].hits += nested_scope[c].hits
        scope[c].locations.extend(nested_scope[c].locations)
    if is_google_tokens and token_like:
        scope["GOOGLE_USER_TOKENS_SECRET_TOKENS"].hits += 1
        scope["GOOGLE_USER_TOKENS_SECRET_TOKENS"].locations.append((address, "secret_string"))
    elif is_google_tokens and isinstance(nested, dict) and nested:
        # Populated but no recognizable token keys: cannot prove absence.
        cov.fail("GOOGLE_TOKENS_SECRET_UNRECOGNIZED_SHAPE")


def _inspect_private_blob(pv: object, address: str, scope: Dict[str, CategoryResult],
                          cov: ScopeCoverage) -> None:
    """Provider-private metadata: base64 of (usually) JSON. Fail closed otherwise."""
    if pv is None:
        return
    if not isinstance(pv, str):
        cov.fail("STATE_PRIVATE_BLOB_UNPARSED")
        return
    try:
        raw = base64.b64decode(pv, validate=True)
    except (binascii.Error, ValueError):
        cov.fail("STATE_PRIVATE_BLOB_UNDECODABLE")
        _scan_str(pv, scope, None)
        return
    _scan_bytes(raw, scope)
    try:
        obj = parse_json_bytes(raw)
    except InspectionError:
        cov.fail("STATE_PRIVATE_BLOB_NOT_JSON")
        return
    nested = {c: CategoryResult() for c in ALL_CATEGORIES}
    _walk_attributes(obj, ("private",), address, nested, False, cov)
    # Pattern hits already counted by the byte scan; add structural field hits only.
    for c in ("NAMED_SENSITIVE_ATTRIBUTE_NONEMPTY",) + tuple(OAUTH_FIELD_CATEGORIES.values()):
        scope[c].hits += nested[c].hits
        scope[c].locations.extend(nested[c].locations)


def inspect_state(data: bytes, report: ArtifactReport) -> None:
    scope, cov = report.state_scope, report.state_cov
    try:
        obj = parse_json_bytes(data)
    except InspectionError as exc:
        cov.fail(exc.code)
        _scan_bytes(data, scope)  # presence only
        return
    if not isinstance(obj, dict) or obj.get("version") != 4 or not isinstance(obj.get("resources"), list):
        cov.fail("STATE_UNSUPPORTED_SHAPE")
        _scan_bytes(data, scope)
        return
    tv = obj.get("terraform_version")
    if isinstance(tv, str) and _VERSION_RE.match(tv) and report.tf_version in ("UNKNOWN", tv):
        report.tf_version = tv
    elif isinstance(tv, str) and _VERSION_RE.match(tv):
        report.tf_version = "MIXED"
    # Non-resource top-level content (outputs, etc.) is scanned structurally too.
    for key, val in obj.items():
        if key != "resources":
            _walk_attributes(val, (key,), "<state>", scope, False, cov)
    for res in obj["resources"]:
        if not isinstance(res, dict) or not isinstance(res.get("instances"), list):
            cov.fail("STATE_RESOURCE_UNPARSED")
            continue
        for inst in res["instances"]:
            if not isinstance(inst, dict):
                cov.fail("STATE_INSTANCE_UNPARSED")
                continue
            address = sanitize_address(res, inst)
            attrs = inst.get("attributes")
            if "attributes_flat" in inst and attrs is None:
                cov.fail("STATE_LEGACY_FLAT_ATTRIBUTES")
                _walk_attributes(inst.get("attributes_flat"), ("attributes_flat",), address, scope, False, cov)
                continue
            if not isinstance(attrs, dict):
                cov.fail("STATE_ATTRIBUTES_UNPARSED")
                continue
            sens = inst.get("sensitive_attributes")
            if isinstance(sens, list) and sens:
                scope["TF_SENSITIVE_ATTRIBUTES"].hits += len(sens)
                scope["TF_SENSITIVE_ATTRIBUTES"].locations.append((address, "sensitive_attributes"))
            elif sens is not None and not isinstance(sens, list):
                cov.fail("STATE_SENSITIVE_ATTRIBUTES_UNPARSED")
            in_env = False
            _walk_attributes(attrs, (), address, scope, in_env, cov)
            if res.get("type") == "aws_lambda_function":
                env = attrs.get("environment")
                if env not in (None, []) and not isinstance(env, list):
                    cov.fail("LAMBDA_ENV_UNPARSED")
            if res.get("type") == "aws_secretsmanager_secret_version":
                _inspect_secret_version(attrs, address, scope, cov)
            for k in inst:
                if k not in ("attributes", "attributes_flat", "sensitive_attributes", "index_key",
                             "schema_version", "private", "dependencies", "create_before_destroy",
                             "status", "deposed", "identity", "identity_schema_version"):
                    cov.fail("STATE_INSTANCE_UNKNOWN_FIELD")
            if "private" in inst:
                _inspect_private_blob(inst.get("private"), address, scope, cov)


def inspect_artifact(spec: ArtifactSpec, run: Runner) -> ArtifactReport:
    report = ArtifactReport(spec.ident)
    try:
        _inspect(spec, run, report)
    except InspectionError as exc:
        report.internal_error = exc.code
        report.state_cov.fail(exc.code)
        report.artifact_cov.fail(exc.code)
    except Exception as exc:  # noqa: BLE001 - class name only, never message
        report.internal_error = "INTERNAL_ERROR:%s" % type(exc).__name__
        report.state_cov.fail("INTERNAL_ERROR")
        report.artifact_cov.fail("INTERNAL_ERROR")
    return report


def _inspect(spec: ArtifactSpec, run: Runner, report: ArtifactReport) -> None:
    data = load_artifact(spec, run, report)
    if data is None:
        report.state_cov.fail("INTEGRITY_FAILED")
        report.artifact_cov.fail("INTEGRITY_FAILED")
        return
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        infos = zf.infolist()
    except (zipfile.BadZipFile, zipfile.LargeZipFile, ValueError, EOFError, OSError):
        report.fmt, report.fmt_reason = "NOT_ZIP", "BAD_ZIP"
        report.state_cov.fail("NOT_ZIP")
        report.artifact_cov.fail("NOT_ZIP")
        _scan_bytes(data, report.artifact_scope)
        return
    if len(infos) > MAX_ENTRIES:
        report.fmt, report.fmt_reason = "UNKNOWN", "TOO_MANY_ENTRIES"
        report.state_cov.fail("TOO_MANY_ENTRIES")
        report.artifact_cov.fail("TOO_MANY_ENTRIES")
        return
    seen = set()
    classes: List[Tuple[zipfile.ZipInfo, str]] = []
    for info in infos:
        cls = classify_entry(info)
        key = info.filename.lower()
        if key in seen:
            cls = UNSAFE
            report.fmt_reason = "DUPLICATE_ENTRY"
        seen.add(key)
        report.entries[cls] += 1
        classes.append((info, cls))
    has_plan = report.entries[TFPLAN] == 1
    has_state = report.entries[TFSTATE] == 1
    if has_plan and has_state:
        report.fmt = "ZIP_SAVED_PLAN"
        if report.fmt_reason == "NOT_PARSED":
            report.fmt_reason = "OK"
    else:
        report.fmt = "UNKNOWN"
        report.fmt_reason = "MISSING_REQUIRED_ENTRY" if report.fmt_reason == "NOT_PARSED" else report.fmt_reason
        report.state_cov.fail("MISSING_REQUIRED_ENTRY")
        report.artifact_cov.fail("MISSING_REQUIRED_ENTRY")
    if report.entries[TFSTATE_PREV] != 1:
        report.state_cov.fail("STATE_PREV_MISSING")
    if report.entries[UNSAFE] or report.entries[UNEXPECTED]:
        report.state_cov.fail("UNSAFE_OR_UNEXPECTED_ENTRY")
        report.artifact_cov.fail("UNSAFE_OR_UNEXPECTED_ENTRY")

    budget = [0]
    tfconfig_root: set = set()
    for info, cls in classes:
        if cls == TFCONFIG_DIR:
            continue
        if cls == UNSAFE:
            report.artifact_cov.fail("UNSAFE_ENTRY_NOT_READ")
            continue
        try:
            data_e = read_entry_limited(zf, info, budget)
        except InspectionError as exc:
            report.fmt_reason = exc.code
            report.state_cov.fail(exc.code)
            report.artifact_cov.fail(exc.code)
            return
        except (zipfile.BadZipFile, zlib.error, EOFError, OSError, ValueError, RuntimeError, NotImplementedError):
            report.fmt_reason = "ENTRY_READ_ERROR"
            report.state_cov.fail("ENTRY_READ_ERROR")
            report.artifact_cov.fail("ENTRY_READ_ERROR")
            return
        if cls in (TFSTATE, TFSTATE_PREV):
            inspect_state(data_e, report)
        elif cls == TFPLAN:
            report.artifact_cov.fail("TFPLAN_NOT_STRUCTURALLY_PARSED")
            _scan_bytes(data_e, report.artifact_scope)
        elif cls == TFCONFIG_FILE:
            rel = info.filename[len("tfconfig/"):]
            if "/" not in rel and rel.endswith(".tf"):
                tfconfig_root.add(rel)
            try:
                data_e.decode("utf-8")
            except UnicodeDecodeError:
                report.artifact_cov.fail("TFCONFIG_NOT_UTF8")
            _scan_bytes(data_e, report.artifact_scope)
        else:  # LOCKFILE, UNEXPECTED
            if cls == UNEXPECTED:
                report.artifact_cov.fail("UNEXPECTED_ENTRY_NOT_PARSED")
            _scan_bytes(data_e, report.artifact_scope)

    repo_names = repo_root_tf_names(spec, run)
    if not tfconfig_root or repo_names is None:
        report.source_config = "UNKNOWN"
    elif tfconfig_root == repo_names:
        report.source_config = "THIS_REPO_MATCH"
    elif tfconfig_root & repo_names:
        report.source_config = "PARTIAL"
    else:
        report.source_config = "OTHER"


# ---------------------------------------------------------------------------
# Status derivation and rendering
# ---------------------------------------------------------------------------


def status(result: CategoryResult, cov: ScopeCoverage) -> Tuple[str, str]:
    if result.hits > 0:
        return PRESENT, "POTENTIAL_MATCH"
    if cov.complete:
        return ABSENT, "FULLY_PARSED_NO_MATCH"
    return UNKNOWN, cov.reasons[0] if cov.reasons else "INCOMPLETE"


def artifact_status(report: ArtifactReport, cid: str) -> Tuple[str, str]:
    combined = CategoryResult(report.state_scope[cid].hits + report.artifact_scope[cid].hits)
    cov = ScopeCoverage(report.state_cov.complete and report.artifact_cov.complete,
                        report.state_cov.reasons + report.artifact_cov.reasons)
    return status(combined, cov)


def render(reports: Iterable[ArtifactReport], with_locations: bool = False) -> List[str]:
    lines: List[str] = []
    for r in reports:
        p = "SEC1B ARTIFACT=%s" % r.ident
        lines.append("%s INTEGRITY=%s" % (p, r.integrity))
        lines.append("%s FORMAT=%s REASON=%s" % (p, r.fmt, r.fmt_reason))
        lines.append("%s ENTRIES %s" % (p, " ".join("%s=%d" % (c, r.entries[c]) for c in ENTRY_CLASSES)))
        lines.append("%s TF_VERSION=%s SOURCE_CONFIG=%s" % (p, r.tf_version, r.source_config))
        if r.internal_error:
            lines.append("%s ERROR=%s" % (p, r.internal_error))
        for cid in ALL_CATEGORIES:
            s, reason = status(r.state_scope[cid], r.state_cov)
            lines.append("%s CATEGORY=%s SCOPE=STATE STATUS=%s REASON=%s COUNT=%d" %
                         (p, cid, s, reason, r.state_scope[cid].hits))
            s, reason = artifact_status(r, cid)
            lines.append("%s CATEGORY=%s SCOPE=ARTIFACT STATUS=%s REASON=%s COUNT=%d" %
                         (p, cid, s, reason, r.state_scope[cid].hits + r.artifact_scope[cid].hits))
        if with_locations:
            seen = set()
            for cid in ALL_CATEGORIES:
                for addr, path in r.state_scope[cid].locations:
                    key = (cid, addr, path)
                    if key in seen:
                        continue
                    seen.add(key)
                    lines.append("%s LOCATION CATEGORY=%s ADDRESS=%s PATH=%s" % (p, cid, addr, path))
    return lines


def any_unknown(reports: Iterable[ArtifactReport]) -> bool:
    for r in reports:
        if r.integrity != "OK" or r.internal_error:
            return True
        for cid in ALL_CATEGORIES:
            if status(r.state_scope[cid], r.state_cov)[0] == UNKNOWN or artifact_status(r, cid)[0] == UNKNOWN:
                return True
    return False


# ---------------------------------------------------------------------------
# Self-verification and CLI
# ---------------------------------------------------------------------------

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def script_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:  # reads THIS script only, never an artifact
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: Optional[Sequence[str]] = None, runner_factory: Callable[[str], Runner] = make_git_runner,
         self_path: Optional[str] = None, out=None) -> int:
    out = out or sys.stdout
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--expected-script-sha256", required=True)
    parser.add_argument("--locations", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2
    if not (sys.flags.isolated and sys.dont_write_bytecode) and self_path is None:
        out.write("SEC1B USAGE=RUN_WITH_python_-I_-B\n")
        return 2
    expected = args.expected_script_sha256.strip().lower()
    if not _SHA256_HEX.match(expected):
        out.write("SEC1B USAGE=BAD_EXPECTED_SHA256\n")
        return 2
    try:
        actual = script_sha256(self_path or os.path.abspath(__file__))
    except OSError:
        out.write("SEC1B SELF_CHECK=READ_ERROR\n")
        return 2
    if actual != expected:
        out.write("SEC1B SELF_CHECK=MISMATCH\n")
        return 2
    out.write("SEC1B SELF_CHECK=OK\n")
    run = runner_factory(args.repo)
    reports = [inspect_artifact(spec, run) for spec in ARTIFACTS]
    for line in render(reports, args.locations):
        out.write(line + "\n")
    rc = 1 if any_unknown(reports) else 0
    out.write("SEC1B RESULT=%s\n" % ("INCOMPLETE_OR_UNKNOWN" if rc else "COMPLETE"))
    return rc


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stdout.write("SEC1B ERROR=INTERNAL_ERROR:%s\n" % type(exc).__name__)
        sys.exit(1)
