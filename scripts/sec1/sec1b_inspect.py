"""SEC-1B offline, owner-run inspector for three historical Terraform artifacts.

Purpose
-------
Classify which *categories* of sensitive data may be present in three binary
artifacts committed to this repository's history, without revealing any
value. Output is restricted to fixed identifiers, fixed reason codes, counts
and (optionally) sanitized resource addresses / attribute paths.

Hard rules implemented here
---------------------------
* Only three pinned artifacts (commit:path, blob id, size) can be inspected.
* Bytes come from the LOCAL git object store through an allowlisted git argv
  (``protocol.allow=never``, ``GIT_NO_LAZY_FETCH=1``, ``GIT_TRACE*`` removed,
  stderr discarded) and stay in memory. Nothing is extracted or written.
* The raw ZIP structure is audited independently of ``zipfile``: end of
  central directory, every central and local header, raw names, flags,
  methods, sizes, extra fields, comments, prefix/trailing/unreferenced and
  overlapping bytes. Any inconsistency fails closed (UNKNOWN).
* Real decompressed bytes are counted (per entry, total, ratio).
* ``tfstate`` and ``tfstate-prev`` are parsed structurally; nested JSON
  strings, base64 text, provider-private blobs and dict keys are inspected.
* Fail closed: ABSENT is emitted only for a scope whose every byte was
  structurally parsed. Opaque data (``tfplan``, unsupported formats,
  undecodable/opaque values, unexpected entries) makes the scope UNKNOWN.
* Each category declares its BASIS: STRUCTURAL (schema/field facts),
  NAME_HEURISTIC (attribute-name hints) or PATTERN (value-shape matches).
  A PATTERN or NAME_HEURISTIC PRESENT is a *potential* finding only.
* Provenance is never claimed. SOURCE_HINT compares root ``.tf`` file names
  only and always prints ``PROVENANCE=NOT_ESTABLISHED``.
* No value, length, fragment, hash, entry name or exception message is
  printed.

Owner-only execution procedure (after review; Kiro must not run this)
--------------------------------------------------------------------
1. Close all AI agents and editors. Use cmd.exe (not PowerShell).
2. Materialize the exact reviewed bytes (LF, byte-exact)::

       git -C <repo> cat-file blob <REVIEWED_HEAD>:scripts/sec1/sec1b_inspect.py > X:\\sec1b\\sec1b_inspect.py

3. Verify: ``certutil -hashfile X:\\sec1b\\sec1b_inspect.py SHA256`` must equal
   the reviewed SHA-256.
4. Run with a trusted CPython 3.10+::

       python -I -B -S X:\\sec1b\\sec1b_inspect.py --repo <repo> --expected-script-sha256 <sha> [--locations]

   ``-I`` ignores PYTHON* variables, user site and the script directory on
   ``sys.path``; ``-S`` skips ``site`` (.pth injection); ``-B`` writes no
   bytecode. The script refuses to run without all three, if a network
   module is already loaded, if any imported stdlib module resolves outside
   the interpreter's stdlib directories, or if its own bytes differ from the
   expected SHA-256.
5. Copy only the ``SEC1B ...`` lines. Delete the materialized script copy.

Unavoidable residual exposure (owner must accept or mitigate)
-------------------------------------------------------------
* Memory: artifact bytes and decoded strings live in process memory; Python
  cannot reliably zero them.
* Pagefile / hibernation: the OS may page memory to pagefile.sys/hiberfil.sys.
* Crash dumps: a crash may make Windows Error Reporting write a dump with
  process memory (for example under %LOCALAPPDATA%\\CrashDumps).
* Antivirus: scanners may inspect the existing .git objects and, with
  automatic sample submission enabled, upload files. This tool writes none.
* Same Windows identity: any process running as the owner can read this
  process's memory and the repository. Close other agents first.
* Self-check timing: the script hashes its own file after it was loaded; an
  attacker with the owner's identity could race that. Not defended.

Exit codes: 0 every scope classified without UNKNOWN and integrity OK;
1 any UNKNOWN, integrity failure or internal error; 2 usage, runtime or
self-verification refusal.
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
import struct
import subprocess
import sys
import sysconfig
import warnings
import zipfile
import zlib
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Pinned artifacts
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
MAX_NESTED_JSON_BYTES = 4 * 1024 * 1024
READ_CHUNK = 64 * 1024
OPAQUE_B64_MIN_CHARS = 64
DIGEST_MAX_BYTES = 64
ALLOWED_EXTRA_IDS = frozenset({0x0001, 0x000A, 0x5455, 0x7875})

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

BASIS: Dict[str, str] = {cid: "PATTERN" for cid, _ in VALUE_PATTERNS}
BASIS.update({
    "SECRETSMANAGER_SECRET_VALUE": "STRUCTURAL",
    "GOOGLE_USER_TOKENS_SECRET_TOKENS": "STRUCTURAL",
    "TF_SENSITIVE_ATTRIBUTES": "STRUCTURAL",
    "OAUTH_REFRESH_TOKEN_FIELD": "STRUCTURAL",
    "OAUTH_ACCESS_TOKEN_FIELD": "STRUCTURAL",
    "OAUTH_ID_TOKEN_FIELD": "STRUCTURAL",
    "NAMED_SENSITIVE_ATTRIBUTE_NONEMPTY": "NAME_HEURISTIC",
    "LAMBDA_ENV_SECRET_PATTERN": "PATTERN",
})
ALL_CATEGORIES: Tuple[str, ...] = tuple(BASIS.keys())

PRESENT, ABSENT, UNKNOWN = "PRESENT", "ABSENT", "UNKNOWN"
SCOPE_STATE, SCOPE_ARTIFACT = "STATE_SNAPSHOTS", "WHOLE_ARTIFACT"

TFPLAN, TFSTATE, TFSTATE_PREV, TFCONFIG_FILE, TFCONFIG_DIR, LOCKFILE, UNEXPECTED, UNSAFE = (
    "TFPLAN", "TFSTATE", "TFSTATE_PREV", "TFCONFIG_FILE", "TFCONFIG_DIR", "LOCKFILE", "UNEXPECTED", "UNSAFE")
ENTRY_CLASSES = (TFPLAN, TFSTATE, TFSTATE_PREV, TFCONFIG_FILE, TFCONFIG_DIR, LOCKFILE, UNEXPECTED, UNSAFE)

SOURCE_HINTS = ("ROOT_FILENAMES_MATCH_REPO_COMMIT", "ROOT_FILENAMES_PARTIAL_OVERLAP",
                "ROOT_FILENAMES_NO_OVERLAP", "UNDETERMINED")

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass
class CategoryResult:
    hits: int = 0
    locations: List[Tuple[str, str]] = field(default_factory=list)


# Fixed priority so the reported primary reason does not depend on entry order.
REASON_PRIORITY: Tuple[str, ...] = (
    "INTEGRITY_FAILED", "INTERNAL_ERROR", "NOT_ZIP", "TOO_MANY_ENTRIES",
    "EOCD_MISSING", "ZIP64_NOT_AUDITED", "MULTI_DISK_ARCHIVE", "ARCHIVE_PREFIX_DATA", "ARCHIVE_TRAILING_BYTES",
    "ARCHIVE_COMMENT_PRESENT", "CENTRAL_DIRECTORY_MISPLACED", "CENTRAL_DIRECTORY_SIZE_MISMATCH",
    "ENTRY_COUNT_MISMATCH", "CENTRAL_HEADER_INVALID", "LOCAL_HEADER_INVALID", "RAW_NAME_NOT_PRINTABLE_ASCII",
    "RAW_NAME_MISMATCH", "CENTRAL_METADATA_MISMATCH", "LOCAL_CENTRAL_NAME_MISMATCH", "LOCAL_CENTRAL_FLAGS_MISMATCH",
    "LOCAL_CENTRAL_METHOD_MISMATCH", "LOCAL_CENTRAL_SIZE_MISMATCH", "EXTRA_FIELD_UNRECOGNIZED",
    "ENTRY_COMMENT_PRESENT", "ENCRYPTED_ENTRY", "OVERLAPPING_ENTRIES", "UNREFERENCED_ARCHIVE_BYTES",
    "DUPLICATE_ENTRY", "MISSING_REQUIRED_ENTRY", "UNSAFE_OR_UNEXPECTED_ENTRY",
    "ENTRY_TOO_LARGE", "TOTAL_TOO_LARGE", "COMPRESSION_RATIO_EXCEEDED", "ENTRY_SIZE_MISMATCH",
    "ZIP_LIBRARY_WARNING", "ENTRY_READ_ERROR",
    "STATE_NOT_UTF8", "STATE_NOT_JSON", "JSON_DUPLICATE_KEY", "JSON_TOO_DEEP", "STATE_UNSUPPORTED_SHAPE",
    "STATE_RESOURCE_UNPARSED", "STATE_INSTANCE_UNPARSED", "STATE_INSTANCE_UNKNOWN_FIELD",
    "STATE_LEGACY_FLAT_ATTRIBUTES", "STATE_ATTRIBUTES_UNPARSED", "STATE_SENSITIVE_ATTRIBUTES_UNPARSED",
    "LAMBDA_ENV_UNPARSED", "SECRET_VALUE_MISSING", "SECRET_VALUE_UNPARSED", "NESTED_SECRET_UNPARSED",
    "GOOGLE_TOKENS_SECRET_UNPARSED", "GOOGLE_TOKENS_SECRET_UNRECOGNIZED_SHAPE", "STATE_PRIVATE_BLOB_UNPARSED",
    "STATE_PRIVATE_BLOB_UNDECODABLE", "STATE_PRIVATE_BLOB_NOT_JSON", "OPAQUE_ENCODED_VALUE",
    "VALUE_TYPE_UNSUPPORTED", "STATE_PREV_MISSING", "STATE_NOT_FULLY_PARSED",
    "TFPLAN_NOT_STRUCTURALLY_PARSED", "UNEXPECTED_ENTRY_NOT_PARSED", "UNSAFE_ENTRY_NOT_READ",
    "TFCONFIG_PATTERN_SCAN_ONLY", "LOCKFILE_PATTERN_SCAN_ONLY",
)
_RANK = {c: i for i, c in enumerate(REASON_PRIORITY)}


def primary_reason(reasons: Sequence[str]) -> str:
    if not reasons:
        return "INCOMPLETE"
    return sorted(reasons, key=lambda c: (_RANK.get(c, len(_RANK)), c))[0]


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
    source_hint: str = "UNDETERMINED"
    states_parsed: int = 0
    state_scope: Dict[str, CategoryResult] = field(default_factory=dict)
    artifact_scope: Dict[str, CategoryResult] = field(default_factory=dict)
    state_cov: ScopeCoverage = field(default_factory=ScopeCoverage)
    artifact_cov: ScopeCoverage = field(default_factory=ScopeCoverage)
    internal_error: Optional[str] = None

    def __post_init__(self) -> None:
        for c in ALL_CATEGORIES:
            self.state_scope.setdefault(c, CategoryResult())
            self.artifact_scope.setdefault(c, CategoryResult())

    def fail_all(self, reason: str) -> None:
        self.state_cov.fail(reason)
        self.artifact_cov.fail(reason)

    def __repr__(self) -> str:
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
    return {line.rsplit("/", 1)[-1] for line in out.decode("utf-8", "replace").splitlines()
            if line.endswith(".tf")}


# ---------------------------------------------------------------------------
# Sanitizers (optional location output)
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
        if not isinstance(module, str) or not re.match(r"^(module\.%s(\[[0-9]{1,6}\])?\.)+$" % _SEG, module + "."):
            return REDACTED
        if _CREDENTIAL_LIKE.search(module):
            return REDACTED
        parts.append(module)
    prefix = "data." if res.get("mode") == "data" else ""
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
# Raw ZIP audit (independent of zipfile's tolerant parsing)
# ---------------------------------------------------------------------------

_EOCD = b"PK\x05\x06"
_CEN = b"PK\x01\x02"
_LOC = b"PK\x03\x04"
_DESC = b"PK\x07\x08"


def _extras_ok(extra: bytes) -> bool:
    i = 0
    while i < len(extra):
        if i + 4 > len(extra):
            return False
        hid, hlen = struct.unpack("<HH", extra[i:i + 4])
        if i + 4 + hlen > len(extra) or hid not in ALLOWED_EXTRA_IDS:
            return False
        i += 4 + hlen
    return True


def _printable_ascii(raw: bytes) -> bool:
    return len(raw) > 0 and all(0x20 <= b < 0x7F for b in raw)


def raw_zip_audit(data: bytes, infos: Sequence[zipfile.ZipInfo]) -> List[str]:
    """Return fail-closed reason codes for any structural inconsistency."""
    reasons: List[str] = []

    def add(code: str) -> None:
        if code not in reasons:
            reasons.append(code)

    n = len(data)
    pos = data.rfind(_EOCD, max(0, n - (22 + 0xFFFF)))
    if pos < 0 or n - pos < 22:
        return ["EOCD_MISSING"]
    _, disk, cd_disk, ent_disk, ent_total, cd_size, cd_off, clen = struct.unpack("<IHHHHIIH", data[pos:pos + 22])
    if clen:
        add("ARCHIVE_COMMENT_PRESENT")
    if pos + 22 + clen != n:
        add("ARCHIVE_TRAILING_BYTES")
    if disk or cd_disk or ent_disk != ent_total:
        add("MULTI_DISK_ARCHIVE")
    zip64_locator = pos >= 20 and data[pos - 20:pos - 16] == b"PK\x06\x07"
    if 0xFFFF in (ent_total, ent_disk) or 0xFFFFFFFF in (cd_off, cd_size) or zip64_locator:
        add("ZIP64_NOT_AUDITED")
        return reasons
    if cd_off + cd_size != pos:
        add("CENTRAL_DIRECTORY_MISPLACED")
    if ent_total != len(infos):
        add("ENTRY_COUNT_MISMATCH")
    p = cd_off
    regions: List[Tuple[int, int]] = []
    for i in range(ent_total):
        if p + 46 > n or data[p:p + 4] != _CEN:
            add("CENTRAL_HEADER_INVALID")
            return reasons
        (_, _vm, _vn, flags, method, _t, _d, crc, csize, usize, nlen, elen, cmlen, dstart, _ia, _ea,
         loff) = struct.unpack("<IHHHHHHIIIHHHHHII", data[p:p + 46])
        name = data[p + 46:p + 46 + nlen]
        extra = data[p + 46 + nlen:p + 46 + nlen + elen]
        p += 46 + nlen + elen + cmlen
        if cmlen:
            add("ENTRY_COMMENT_PRESENT")
        if dstart:
            add("MULTI_DISK_ARCHIVE")
        if not _printable_ascii(name):
            add("RAW_NAME_NOT_PRINTABLE_ASCII")
        if not _extras_ok(extra):
            add("EXTRA_FIELD_UNRECOGNIZED")
        if flags & 0x1:
            add("ENCRYPTED_ENTRY")
        if i < len(infos):
            info = infos[i]
            try:
                enc = info.orig_filename.encode("utf-8" if info.flag_bits & 0x800 else "cp437")
            except (UnicodeEncodeError, AttributeError):
                enc = None
            if enc != name or info.filename != info.orig_filename:
                add("RAW_NAME_MISMATCH")
            if (info.header_offset, info.compress_size, info.file_size, info.flag_bits, info.compress_type,
                    info.CRC) != (loff, csize, usize, flags, method, crc):
                add("CENTRAL_METADATA_MISMATCH")
        if loff + 30 > n or data[loff:loff + 4] != _LOC:
            add("LOCAL_HEADER_INVALID")
            continue
        (_, _lv, lflags, lmethod, _lt, _ld, lcrc, lcs, lus, lnlen, lelen) = struct.unpack(
            "<IHHHHHIIIHH", data[loff:loff + 30])
        lname = data[loff + 30:loff + 30 + lnlen]
        lextra = data[loff + 30 + lnlen:loff + 30 + lnlen + lelen]
        if lname != name:
            add("LOCAL_CENTRAL_NAME_MISMATCH")
        if lflags != flags:
            add("LOCAL_CENTRAL_FLAGS_MISMATCH")
        if lmethod != method:
            add("LOCAL_CENTRAL_METHOD_MISMATCH")
        if not (flags & 0x8) and (lcrc, lcs, lus) != (crc, csize, usize):
            add("LOCAL_CENTRAL_SIZE_MISMATCH")
        if not _extras_ok(lextra):
            add("EXTRA_FIELD_UNRECOGNIZED")
        end = loff + 30 + lnlen + lelen + csize
        if flags & 0x8:
            end += 16 if data[end:end + 4] == _DESC else 12
        regions.append((loff, end))
    if p != pos:
        add("CENTRAL_DIRECTORY_SIZE_MISMATCH")
    cursor = 0
    for start, end in sorted(regions):
        if start < cursor:
            add("OVERLAPPING_ENTRIES")
        elif start > cursor:
            add("ARCHIVE_PREFIX_DATA" if cursor == 0 else "UNREFERENCED_ARCHIVE_BYTES")
        cursor = max(cursor, end)
    if cursor < cd_off:
        add("ARCHIVE_PREFIX_DATA" if not regions else "UNREFERENCED_ARCHIVE_BYTES")
    elif cursor > cd_off:
        add("OVERLAPPING_ENTRIES")
    return reasons


# ---------------------------------------------------------------------------
# Entry classification and limited reads
# ---------------------------------------------------------------------------

_DRIVE = re.compile(r"^[A-Za-z]:")


def classify_entry(info: zipfile.ZipInfo) -> str:
    name = info.filename
    if getattr(info, "orig_filename", name) != name:
        return UNSAFE  # NUL truncation or separator normalization happened
    if (not name or len(name) > MAX_NAME_LEN or "\x00" in name or "\\" in name or name.startswith("/")
            or _DRIVE.match(name) or any(seg in ("..", ".") for seg in name.split("/"))
            or any(ord(ch) < 32 or ord(ch) > 126 for ch in name)):
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
    buf = io.BytesIO()
    got = 0
    with warnings.catch_warnings():
        # zipfile reports suspicious structure (e.g. overlapped entries) as
        # warnings on stderr; treat them as fail-closed errors instead.
        warnings.simplefilter("error")
        try:
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
        except Warning:
            raise InspectionError("ZIP_LIBRARY_WARNING")
    if got != info.file_size:
        raise InspectionError("ENTRY_SIZE_MISMATCH")
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
    return parse_json_text(text, "STATE_NOT_JSON")


def parse_json_text(text: str, not_json_code: str) -> object:
    try:
        obj = json.loads(text, object_pairs_hook=_no_dup_pairs)
    except InspectionError:
        raise
    except RecursionError:
        raise InspectionError("JSON_TOO_DEEP")
    except ValueError:
        raise InspectionError(not_json_code)
    _check_depth(obj)
    return obj


_VERSION_RE = re.compile(r"^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(?:[-+][0-9A-Za-z.\-]{1,32})?$")
_B64_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")


def _nonempty(v: object) -> bool:
    if v is None or v is False:
        return False
    if isinstance(v, str):
        return v.strip() not in ("", "{}", "[]", "null")
    if isinstance(v, (list, dict)):
        return len(v) > 0
    return True


class _Walker:
    """Value-blind recursive inspection of decoded JSON values."""

    def __init__(self, scope: Dict[str, CategoryResult], cov: ScopeCoverage) -> None:
        self.scope = scope
        self.cov = cov

    def walk(self, obj: object, path: Tuple[object, ...], address: str, in_env: bool = False,
             depth: int = 0) -> None:
        if depth > MAX_JSON_DEPTH:
            self.cov.fail("JSON_TOO_DEEP")
            return
        loc = (address, sanitize_path(path))
        if isinstance(obj, dict):
            for k, v in obj.items():
                sub = path + (k,)
                if isinstance(k, str):
                    self._scan_text(k, (address, sanitize_path(path)), in_env, depth, nested=False)
                    if _NAMED_SENSITIVE.search(k) and _nonempty(v):
                        self._hit("NAMED_SENSITIVE_ATTRIBUTE_NONEMPTY", (address, sanitize_path(sub)))
                    if k.lower() in OAUTH_FIELD_CATEGORIES and _nonempty(v):
                        self._hit(OAUTH_FIELD_CATEGORIES[k.lower()], (address, sanitize_path(sub)))
                env_here = in_env or (k == "variables" and len(path) >= 2 and path[-2] == "environment")
                self.walk(v, sub, address, env_here, depth + 1)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                self.walk(v, path + (i,), address, in_env, depth + 1)
        elif isinstance(obj, str):
            self._scan_text(obj, loc, in_env, depth, nested=True, path=path, address=address)
        elif obj is None or isinstance(obj, (bool, int, float)):
            return
        else:
            self.cov.fail("VALUE_TYPE_UNSUPPORTED")

    def _hit(self, cid: str, loc: Tuple[str, str]) -> None:
        self.scope[cid].hits += 1
        self.scope[cid].locations.append(loc)

    def _scan_text(self, text: str, loc: Tuple[str, str], in_env: bool, depth: int, nested: bool,
                   path: Tuple[object, ...] = (), address: str = "") -> None:
        stripped = text.strip()
        if nested and stripped[:1] in ("{", "[") and len(stripped) <= MAX_NESTED_JSON_BYTES:
            try:
                inner = parse_json_text(stripped, "NESTED_NOT_JSON")
            except InspectionError as exc:
                if exc.code != "NESTED_NOT_JSON":
                    self.cov.fail("NESTED_JSON_" + exc.code)
                inner = None
            if inner is not None:
                self.walk(inner, path, address, in_env, depth + 1)
                return
        found = _scan_str(text, self.scope, loc)
        if in_env and any(c != "EMAIL_ADDRESS" for c in found):
            self._hit("LAMBDA_ENV_SECRET_PATTERN", loc)
        if nested and len(stripped) >= OPAQUE_B64_MIN_CHARS and len(stripped) % 4 == 0 and _B64_RE.match(stripped):
            try:
                raw = base64.b64decode(stripped, validate=True)
            except (binascii.Error, ValueError):
                return
            try:
                decoded = raw.decode("utf-8")
            except UnicodeDecodeError:
                decoded = None
            if decoded is not None and all(ch.isprintable() or ch in "\r\n\t" for ch in decoded):
                self._scan_text(decoded, loc, in_env, depth + 1, nested=True, path=path, address=address)
            elif len(raw) > DIGEST_MAX_BYTES:
                self.cov.fail("OPAQUE_ENCODED_VALUE")
                _scan_bytes(raw, self.scope)


def _inspect_secret_version(attrs: dict, address: str, scope: Dict[str, CategoryResult],
                            cov: ScopeCoverage) -> None:
    secret_id = attrs.get("secret_id")
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
        nested = parse_json_text(stripped, "NESTED_SECRET_UNPARSED")
    except InspectionError as exc:
        cov.fail(exc.code if exc.code == "NESTED_SECRET_UNPARSED" else "NESTED_SECRET_" + exc.code)
        if is_google_tokens:
            cov.fail("GOOGLE_TOKENS_SECRET_UNPARSED")
        return
    probe = {c: CategoryResult() for c in ALL_CATEGORIES}
    _Walker(probe, ScopeCoverage()).walk(nested, ("secret_string",), address)
    token_like = sum(probe[c].hits for c in OAUTH_FIELD_CATEGORIES.values()) + \
        probe["GOOGLE_REFRESH_TOKEN"].hits + probe["GOOGLE_ACCESS_TOKEN"].hits
    if is_google_tokens and token_like:
        scope["GOOGLE_USER_TOKENS_SECRET_TOKENS"].hits += 1
        scope["GOOGLE_USER_TOKENS_SECRET_TOKENS"].locations.append((address, "secret_string"))
    elif is_google_tokens and nested not in ({}, [], None):
        cov.fail("GOOGLE_TOKENS_SECRET_UNRECOGNIZED_SHAPE")


def _inspect_private_blob(pv: object, address: str, scope: Dict[str, CategoryResult],
                          cov: ScopeCoverage) -> None:
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
    probe = {c: CategoryResult() for c in ALL_CATEGORIES}
    _Walker(probe, cov).walk(obj, ("private",), address)
    for c in ("NAMED_SENSITIVE_ATTRIBUTE_NONEMPTY",) + tuple(OAUTH_FIELD_CATEGORIES.values()):
        scope[c].hits += probe[c].hits
        scope[c].locations.extend(probe[c].locations)


_KNOWN_INSTANCE_FIELDS = frozenset({"attributes", "attributes_flat", "sensitive_attributes", "index_key",
                                    "schema_version", "private", "dependencies", "create_before_destroy",
                                    "status", "deposed", "identity", "identity_schema_version"})


def inspect_state(data: bytes, report: ArtifactReport) -> None:
    scope, cov = report.state_scope, report.state_cov
    try:
        obj = parse_json_bytes(data)
    except InspectionError as exc:
        cov.fail(exc.code)
        _scan_bytes(data, scope)
        return
    if not isinstance(obj, dict) or obj.get("version") != 4 or not isinstance(obj.get("resources"), list):
        cov.fail("STATE_UNSUPPORTED_SHAPE")
        _scan_bytes(data, scope)
        return
    report.states_parsed += 1
    tv = obj.get("terraform_version")
    if isinstance(tv, str) and _VERSION_RE.match(tv):
        report.tf_version = tv if report.tf_version in ("UNKNOWN", tv) else "MIXED"
    walker = _Walker(scope, cov)
    for key, val in obj.items():
        if key != "resources":
            walker.walk(val, (key,), "<state>")
    for res in obj["resources"]:
        if not isinstance(res, dict) or not isinstance(res.get("instances"), list):
            cov.fail("STATE_RESOURCE_UNPARSED")
            if isinstance(res, (dict, list, str)):
                walker.walk(res, ("resources",), "<state>")
            continue
        for k, v in res.items():
            if k != "instances":
                walker.walk(v, (k,), "<resource>")
        for inst in res["instances"]:
            if not isinstance(inst, dict):
                cov.fail("STATE_INSTANCE_UNPARSED")
                walker.walk(inst, ("instances",), "<resource>")
                continue
            address = sanitize_address(res, inst)
            for k in inst:
                if k not in _KNOWN_INSTANCE_FIELDS:
                    cov.fail("STATE_INSTANCE_UNKNOWN_FIELD")
            attrs = inst.get("attributes")
            if attrs is None and "attributes_flat" in inst:
                cov.fail("STATE_LEGACY_FLAT_ATTRIBUTES")
                walker.walk(inst.get("attributes_flat"), ("attributes_flat",), address)
            elif not isinstance(attrs, dict):
                cov.fail("STATE_ATTRIBUTES_UNPARSED")
                walker.walk(attrs, ("attributes",), address)
            else:
                walker.walk(attrs, (), address)
                if res.get("type") == "aws_lambda_function":
                    env = attrs.get("environment")
                    if env not in (None, []) and not isinstance(env, list):
                        cov.fail("LAMBDA_ENV_UNPARSED")
                if res.get("type") == "aws_secretsmanager_secret_version":
                    _inspect_secret_version(attrs, address, scope, cov)
            sens = inst.get("sensitive_attributes")
            if isinstance(sens, list) and sens:
                scope["TF_SENSITIVE_ATTRIBUTES"].hits += len(sens)
                scope["TF_SENSITIVE_ATTRIBUTES"].locations.append((address, "sensitive_attributes"))
            elif sens is not None and not isinstance(sens, list):
                cov.fail("STATE_SENSITIVE_ATTRIBUTES_UNPARSED")
            for k, v in inst.items():
                if k not in ("attributes", "attributes_flat", "private"):
                    walker.walk(v, (k,), address)
            if "private" in inst:
                _inspect_private_blob(inst.get("private"), address, scope, cov)


# ---------------------------------------------------------------------------
# Artifact inspection
# ---------------------------------------------------------------------------


def inspect_artifact(spec: ArtifactSpec, run: Runner) -> ArtifactReport:
    report = ArtifactReport(spec.ident)
    try:
        _inspect(spec, run, report)
    except InspectionError as exc:
        report.internal_error = exc.code
        report.fail_all(exc.code)
    except Exception as exc:  # noqa: BLE001 - class name only, never message
        report.internal_error = "INTERNAL_ERROR:%s" % type(exc).__name__
        report.fail_all("INTERNAL_ERROR")
    return report


def _inspect(spec: ArtifactSpec, run: Runner, report: ArtifactReport) -> None:
    data = load_artifact(spec, run, report)
    if data is None:
        report.fail_all("INTEGRITY_FAILED")
        return
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            zf = zipfile.ZipFile(io.BytesIO(data))
            infos = zf.infolist()
    except (zipfile.BadZipFile, zipfile.LargeZipFile, ValueError, EOFError, OSError, struct.error, Warning):
        report.fmt, report.fmt_reason = "NOT_ZIP", "BAD_ZIP"
        report.fail_all("NOT_ZIP")
        _scan_bytes(data, report.artifact_scope)
        return
    if len(infos) > MAX_ENTRIES:
        report.fmt, report.fmt_reason = "UNKNOWN", "TOO_MANY_ENTRIES"
        report.fail_all("TOO_MANY_ENTRIES")
        return
    raw_reasons = raw_zip_audit(data, infos)
    for code in raw_reasons:
        report.fail_all(code)
    seen = set()
    classes: List[Tuple[zipfile.ZipInfo, str]] = []
    for info in infos:
        cls = classify_entry(info)
        key = info.filename.lower()
        if key in seen:
            cls = UNSAFE
            raw_reasons.append("DUPLICATE_ENTRY")
        seen.add(key)
        report.entries[cls] += 1
        classes.append((info, cls))
    if report.entries[TFPLAN] == 1 and report.entries[TFSTATE] == 1 and not raw_reasons:
        report.fmt, report.fmt_reason = "ZIP_SAVED_PLAN", "OK"
    else:
        report.fmt = "ZIP_SAVED_PLAN_UNVERIFIED" if report.entries[TFPLAN] and report.entries[TFSTATE] else "UNKNOWN"
        report.fmt_reason = raw_reasons[0] if raw_reasons else "MISSING_REQUIRED_ENTRY"
        report.fail_all(report.fmt_reason)
    if report.entries[TFSTATE_PREV] != 1:
        report.state_cov.fail("STATE_PREV_MISSING")
    if report.entries[UNSAFE] or report.entries[UNEXPECTED]:
        report.fail_all("UNSAFE_OR_UNEXPECTED_ENTRY")

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
            report.fail_all(exc.code)
            return
        except (zipfile.BadZipFile, zlib.error, EOFError, OSError, ValueError, RuntimeError, NotImplementedError,
                Warning):
            report.fmt_reason = "ENTRY_READ_ERROR"
            report.fail_all("ENTRY_READ_ERROR")
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
            report.artifact_cov.fail("TFCONFIG_PATTERN_SCAN_ONLY")
            _scan_bytes(data_e, report.artifact_scope)
        else:
            report.artifact_cov.fail("UNEXPECTED_ENTRY_NOT_PARSED" if cls == UNEXPECTED else "LOCKFILE_PATTERN_SCAN_ONLY")
            _scan_bytes(data_e, report.artifact_scope)
    expected_states = report.entries[TFSTATE] + report.entries[TFSTATE_PREV]
    if report.states_parsed != expected_states or expected_states == 0:
        report.state_cov.fail("STATE_NOT_FULLY_PARSED")

    repo_names = repo_root_tf_names(spec, run)
    if not tfconfig_root or repo_names is None:
        report.source_hint = "UNDETERMINED"
    elif tfconfig_root == repo_names:
        report.source_hint = "ROOT_FILENAMES_MATCH_REPO_COMMIT"
    elif tfconfig_root & repo_names:
        report.source_hint = "ROOT_FILENAMES_PARTIAL_OVERLAP"
    else:
        report.source_hint = "ROOT_FILENAMES_NO_OVERLAP"


# ---------------------------------------------------------------------------
# Status derivation (the ONLY routes to ABSENT) and rendering
# ---------------------------------------------------------------------------


def status(cid: str, hits: int, cov: ScopeCoverage) -> Tuple[str, str]:
    basis = BASIS[cid]
    if hits > 0:
        return PRESENT, "STRUCTURAL_MATCH" if basis == "STRUCTURAL" else "POTENTIAL_%s_MATCH" % basis
    if cov.complete and not cov.reasons:
        return ABSENT, "FULLY_PARSED_NO_%s_MATCH" % basis
    return UNKNOWN, primary_reason(cov.reasons)


def state_status(r: ArtifactReport, cid: str) -> Tuple[str, str]:
    return status(cid, r.state_scope[cid].hits, r.state_cov)


def artifact_status(r: ArtifactReport, cid: str) -> Tuple[str, str]:
    cov = ScopeCoverage(r.state_cov.complete and r.artifact_cov.complete,
                        r.state_cov.reasons + r.artifact_cov.reasons)
    return status(cid, r.state_scope[cid].hits + r.artifact_scope[cid].hits, cov)


def render(reports: Iterable[ArtifactReport], with_locations: bool = False) -> List[str]:
    lines: List[str] = []
    for r in reports:
        p = "SEC1B ARTIFACT=%s" % r.ident
        lines.append("%s INTEGRITY=%s" % (p, r.integrity))
        lines.append("%s FORMAT=%s REASON=%s" % (p, r.fmt, r.fmt_reason))
        lines.append("%s ENTRIES %s" % (p, " ".join("%s=%d" % (c, r.entries[c]) for c in ENTRY_CLASSES)))
        lines.append("%s TF_VERSION=%s SOURCE_HINT=%s PROVENANCE=NOT_ESTABLISHED" % (p, r.tf_version, r.source_hint))
        a_cov = r.state_cov.complete and r.artifact_cov.complete
        lines.append("%s WHOLE_ARTIFACT_ABSENCE_PROVABLE=%s REASON=%s" % (
            p, "YES" if a_cov else "NO",
            "COMPLETE" if a_cov else primary_reason(r.state_cov.reasons + r.artifact_cov.reasons)))
        if r.internal_error:
            lines.append("%s ERROR=%s" % (p, r.internal_error))
        for cid in ALL_CATEGORIES:
            s, reason = state_status(r, cid)
            lines.append("%s CATEGORY=%s BASIS=%s SCOPE=%s STATUS=%s REASON=%s COUNT=%d" %
                         (p, cid, BASIS[cid], SCOPE_STATE, s, reason, r.state_scope[cid].hits))
            s, reason = artifact_status(r, cid)
            lines.append("%s CATEGORY=%s BASIS=%s SCOPE=%s STATUS=%s REASON=%s COUNT=%d" %
                         (p, cid, BASIS[cid], SCOPE_ARTIFACT, s, reason,
                          r.state_scope[cid].hits + r.artifact_scope[cid].hits))
        if with_locations:
            for cid in ALL_CATEGORIES:
                for addr, path in sorted(set(r.state_scope[cid].locations)):
                    lines.append("%s LOCATION CATEGORY=%s ADDRESS=%s PATH=%s" % (p, cid, addr, path))
    return lines


def any_unknown(reports: Iterable[ArtifactReport]) -> bool:
    for r in reports:
        if r.integrity != "OK" or r.internal_error:
            return True
        for cid in ALL_CATEGORIES:
            if state_status(r, cid)[0] == UNKNOWN or artifact_status(r, cid)[0] == UNKNOWN:
                return True
    return False


# ---------------------------------------------------------------------------
# Execution integrity and CLI
# ---------------------------------------------------------------------------

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_NETWORK_MODULES = ("socket", "ssl", "http.client", "urllib.request", "ftplib", "smtplib", "asyncio")
_CHECKED_MODULES = ("argparse", "base64", "hashlib", "io", "json", "os", "re", "stat", "struct",
                    "subprocess", "sysconfig", "zipfile", "dataclasses", "typing", "json.decoder")


def _stdlib_dirs() -> List[str]:
    paths = sysconfig.get_paths()
    dirs = [paths.get("stdlib"), paths.get("platstdlib"), os.path.join(sys.base_prefix, "DLLs")]
    return [os.path.normcase(os.path.abspath(d)) for d in dirs if d]


def check_runtime(flags=None, version=None, modules=None, stdlib_dirs=None,
                  dont_write_bytecode=None) -> Optional[str]:
    flags = flags if flags is not None else sys.flags
    version = version if version is not None else sys.version_info
    modules = modules if modules is not None else sys.modules
    dirs = stdlib_dirs if stdlib_dirs is not None else _stdlib_dirs()
    dwb = sys.dont_write_bytecode if dont_write_bytecode is None else dont_write_bytecode
    if tuple(version[:2]) < (3, 10):
        return "PYTHON_TOO_OLD"
    if not (getattr(flags, "isolated", 0) and getattr(flags, "no_site", 0) and dwb):
        return "RUN_WITH_python_-I_-B_-S"
    for name in _NETWORK_MODULES:
        if name in modules:
            return "NETWORK_MODULE_LOADED"
    for name in _CHECKED_MODULES:
        mod = modules.get(name)
        if mod is None:
            continue
        origin = getattr(getattr(mod, "__spec__", None), "origin", None)
        if origin in (None, "built-in", "frozen"):
            continue
        norm = os.path.normcase(os.path.abspath(origin))
        if not any(norm.startswith(d + os.sep) or norm == d for d in dirs):
            return "MODULE_ORIGIN_UNTRUSTED"
    return None


def script_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:  # reads THIS script only, never an artifact
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: Optional[Sequence[str]] = None, runner_factory: Callable[[str], Runner] = make_git_runner,
         self_path: Optional[str] = None, out=None, runtime_check: Callable[[], Optional[str]] = check_runtime) -> int:
    out = out or sys.stdout
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--expected-script-sha256", required=True)
    parser.add_argument("--locations", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2
    refusal = runtime_check()
    if refusal:
        out.write("SEC1B REFUSED=%s\n" % refusal)
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
