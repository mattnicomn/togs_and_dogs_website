"""G1.6-C3-G0: credential-free probe, sacrificial-test specification, preflight
and cleanup logic. OFFLINE and INERT.

Nothing in this module is run against the real agent in G0. It defines, and
tests with mocks, exactly what a later, separately approved G3 run may do:

  * what the probe checks (identity, privileges, integrity, volume binding, the
    boundary guard's verdict on real and disposable paths, free space);
  * the disposable twin tree under ``<volume>:\\_c3`` and the access outcomes
    expected there;
  * which operations may EVER be attempted, and only against disposable
    objects (everything else is refused before any operation is dispatched);
  * fail-closed stop conditions, bounded execution and idempotent cleanup;
  * the S4U task prerequisites and a read-back validator (no task is registered).

Authority comes only from a strict, owner-controlled approval document. No
operation, filesystem touch or guard call happens before it validates.
"""

from __future__ import annotations

import enum
import json
import ntpath
import os
import posixpath
import shutil
import stat
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Callable, ClassVar, Mapping, Protocol, Sequence

from . import acl_guard, c3_package, c3_runtime, errors

# v2: adds the owner-pinned ``interpreter_tree_sha256`` (G0-R-B, finding #4).
# v3: adds the owner-bounded ``max_run_seconds`` (G0-R-C: the deadline is policy, not caller input).
APPROVAL_SCHEMA = "petcare.c3.probe-approval/v3"
REPORT_SCHEMA = "petcare.c3.probe-report/v1"
PHASES = ("PLAN", "READONLY", "NEGATIVE")
SCOPE_ID = "G1.6-C3"
MAX_RUN_SECONDS = 300
MAX_CLEANUP_ENTRIES = 2000
MAX_CLEANUP_DEPTH = 16
PRODUCTION_KEYS = ("root", "approvals", "bin", "worktrees", "runtime", "evidence", "vault_dir", "vhdx")
AGENT_WRITABLE_PRODUCTION = ("worktrees", "runtime", "evidence")


# --- the owner-controlled approval ------------------------------------------------


@dataclass(frozen=True)
class ProbeApproval:
    scope_id: str
    phase: str
    authorized_by: str
    authorized_at: str
    expires_at: datetime
    expected_agent_sid: str
    trusted_owner_sids: frozenset[str]
    trusted_volume: acl_guard.VolumeBinding
    container: str
    production_paths: Mapping[str, str]
    package_manifest_sha256: str
    min_free_bytes: Mapping[str, int]
    negative_authorized: bool
    max_run_seconds: int          # owner-bounded execution limit (1..MAX_RUN_SECONDS)
    interpreter_tree_sha256: str  # owner-pinned digest of the trusted interpreter tree
    source_sha256: str = ""      # digest of the exact approval bytes that were parsed

    def phase_allows(self, requested: str) -> bool:
        return PHASES.index(requested) <= PHASES.index(self.phase)


_APPROVAL_KEYS = {
    "schema", "scope_id", "phase", "authorized_by", "authorized_at", "expires_at", "expected_agent_sid",
    "trusted_owner_sids", "trusted_volume", "container", "production_paths", "package_manifest_sha256",
    "min_free_bytes", "negative_authorized", "interpreter_tree_sha256", "max_run_seconds",
}


MAX_FREE_FLOOR_BYTES = 2**50  # 1 PiB: anything larger is a malformed threshold
_DRIVE_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _is_drive_root(value: Any) -> bool:
    """Exactly ``X:\\`` with an upper-case letter: no relative, UNC, device,
    ``\\\\?\\`` / ``\\\\.\\``, forward-slash, lower-case or padded form."""

    return type(value) is str and len(value) == 3 and value[0] in _DRIVE_LETTERS and value[1:] == ":\\"


def _validate_free_floor(free: Any, approved_root: str, error: type[errors.OrchestratorStop]) -> None:
    """The free-space configuration is untrusted until this passes: exactly ONE key,
    the approved volume root, mapped to a plain positive integer threshold."""

    if type(free) is not dict:
        raise error("min_free_bytes must be an object")
    if not _is_drive_root(approved_root) or list(free) != [approved_root]:
        raise error(f"min_free_bytes must name exactly the approved volume root {approved_root!r} and nothing else")
    need = free[approved_root]
    if type(need) is not int or not 0 < need <= MAX_FREE_FLOOR_BYTES:
        raise error(f"min_free_bytes threshold must be an integer between 1 and {MAX_FREE_FLOOR_BYTES}")


def _is_hex64(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise errors.ApprovalInvalid("timestamp must be text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise errors.ApprovalInvalid("timestamp is not ISO-8601") from None
    if parsed.tzinfo is None:
        raise errors.ApprovalInvalid("timestamp must carry a timezone")
    return parsed


def parse_probe_approval(data: bytes | None, *, now: datetime) -> ProbeApproval:
    """Strictly parse and validate the probe approval. Missing, malformed,
    unknown-keyed, expired or internally inconsistent documents are refused."""

    if data is None:
        raise errors.ApprovalMissing("no probe approval was supplied")
    try:
        doc = json.loads(data.decode("utf-8"))
    except ValueError:
        raise errors.ApprovalInvalid("probe approval is not valid JSON") from None
    if not isinstance(doc, dict) or set(doc) != _APPROVAL_KEYS or doc["schema"] != APPROVAL_SCHEMA:
        raise errors.ApprovalInvalid("probe approval has the wrong shape, schema or unknown keys")
    if doc["scope_id"] != SCOPE_ID:
        raise errors.ScopeMismatch("probe approval is for a different scope")
    if doc["phase"] not in PHASES:
        raise errors.ApprovalInvalid("probe approval phase is not recognized")
    for key in ("authorized_by", "authorized_at"):
        if not isinstance(doc[key], str) or not doc[key].strip():
            raise errors.ApprovalInvalid(f"{key} must be non-empty text")
    expires = _parse_time(doc["expires_at"])
    if expires <= now:
        raise errors.ApprovalInvalid("probe approval has expired")
    if (expires - now).total_seconds() > 24 * 3600:
        raise errors.ApprovalInvalid("probe approval lifetime exceeds 24 hours")
    neg = doc["negative_authorized"]
    if not isinstance(neg, bool):
        raise errors.ApprovalInvalid("negative_authorized must be a boolean")
    if neg and doc["phase"] != "NEGATIVE":
        raise errors.ApprovalInvalid("negative_authorized requires phase NEGATIVE")
    if doc["phase"] == "NEGATIVE" and not neg:
        raise errors.ApprovalInvalid("phase NEGATIVE requires negative_authorized=true")
    owners = doc["trusted_owner_sids"]
    if not isinstance(owners, list) or not owners or not all(isinstance(s, str) for s in owners):
        raise errors.ApprovalInvalid("trusted_owner_sids must be a non-empty list of SIDs")
    vol = doc["trusted_volume"]
    if not isinstance(vol, dict) or set(vol) != {"guid", "label", "serial"}:
        raise errors.ApprovalInvalid("trusted_volume must have guid, label and serial")
    prod = doc["production_paths"]
    if not isinstance(prod, dict) or set(prod) != set(PRODUCTION_KEYS) or not all(isinstance(v, str) for v in prod.values()):
        raise errors.ApprovalInvalid("production_paths must name exactly the protected production locations")
    digest = doc["package_manifest_sha256"]
    if not _is_hex64(digest):
        raise errors.ApprovalInvalid("package_manifest_sha256 must be 64 lowercase hex characters")
    interp_digest = doc["interpreter_tree_sha256"]
    if not _is_hex64(interp_digest):
        raise errors.ApprovalInvalid("interpreter_tree_sha256 must be 64 lowercase hex characters")
    max_run = doc["max_run_seconds"]
    if isinstance(max_run, bool) or not isinstance(max_run, int) or not 0 < max_run <= MAX_RUN_SECONDS:
        raise errors.ApprovalInvalid(f"max_run_seconds must be an integer between 1 and {MAX_RUN_SECONDS}")
    # G0-R-D: the free-space floor may only name the drive root of the ONE approved,
    # verified volume (the volume the pinned approval read binds). No other key form is
    # accepted and nothing is normalised: the root must already be exactly "X:\".
    # The exact "X:\" shape of the root is enforced by _validate_free_floor below.
    root = prod["root"]
    for key in ("approvals", "bin", "worktrees", "runtime", "evidence"):
        if prod[key][:3] != root:
            raise errors.ApprovalInvalid(f"production_paths.{key} must be on the approved volume root {root}")
    if not isinstance(doc["container"], str) or doc["container"][:3] != root:
        raise errors.ApprovalInvalid("the container must be on the approved volume root")
    _validate_free_floor(doc["min_free_bytes"], root, errors.ApprovalInvalid)
    free = doc["min_free_bytes"]
    try:
        binding = acl_guard.VolumeBinding(vol["guid"], label=vol["label"], serial=vol["serial"])
        acl_guard.BoundaryPolicy(trusted_owner_sids=frozenset(owners), expected_agent_sid=doc["expected_agent_sid"])
        container = acl_guard.canonical_windows_path(doc["container"])
        for value in prod.values():
            acl_guard.canonical_windows_path(value)
        if not ntpath.basename(container).startswith("_c3"):
            raise ValueError("container must be named '_c3*'")
        if ntpath.dirname(ntpath.dirname(container)) != ntpath.dirname(container):
            raise ValueError("container must be a top-level directory of a volume")
    except (ValueError, TypeError, acl_guard.PathRejected) as exc:
        raise errors.ApprovalInvalid(f"probe approval value rejected: {exc}") from None
    return ProbeApproval(
        scope_id=doc["scope_id"], phase=doc["phase"], authorized_by=doc["authorized_by"],
        authorized_at=doc["authorized_at"], expires_at=expires, expected_agent_sid=doc["expected_agent_sid"],
        trusted_owner_sids=frozenset(owners), trusted_volume=binding, container=container,
        production_paths=dict(prod), package_manifest_sha256=digest, min_free_bytes=dict(free),
        negative_authorized=neg, max_run_seconds=max_run, interpreter_tree_sha256=interp_digest,
        source_sha256=c3_package.sha256_hex(data),
    )


# --- target policy: production is untouchable, only the twin is disposable ---------


class TargetClass(str, enum.Enum):
    PRODUCTION = "PRODUCTION"
    CONTAINER = "CONTAINER"
    DISPOSABLE = "DISPOSABLE"
    OUTSIDE = "OUTSIDE"


@dataclass(frozen=True)
class TargetPolicy:
    container: str                       # e.g. P:\_c3 (owner-created disposable container)
    production_roots: tuple[str, ...]
    platform: str = "nt"
    # Class-level invariant (not a constructor argument): the container must be a
    # top-level directory of a volume. Only a test subclass overrides it.
    _top_level_required: ClassVar[bool] = True

    def __post_init__(self) -> None:
        pf = self.platform
        try:
            container = c3_runtime._canon(pf, self.container)
            prods = tuple(c3_runtime._canon(pf, p) for p in self.production_roots)
        except ValueError as exc:
            raise ValueError(f"unsafe target path: {exc}") from None
        if not prods:
            raise ValueError("production roots must be named")
        pm = ntpath if pf == "nt" else posixpath
        name = pm.basename(container)
        if not name.startswith("_c3"):
            raise ValueError("the disposable container must be named '_c3*'")
        if self._top_level_required and pm.dirname(pm.dirname(container)) != pm.dirname(container):
            raise ValueError("the disposable container must be a top-level directory of a volume")
        for p in prods:
            if c3_runtime._within(pf, container, p) or c3_runtime._within(pf, p, container):
                raise ValueError("the disposable container overlaps a production root")
        object.__setattr__(self, "container", container)
        object.__setattr__(self, "production_roots", prods)

    def _canon(self, path: Any) -> str:
        try:
            return c3_runtime._canon(self.platform, path)
        except ValueError as exc:
            raise errors.SacrificialTargetRefused(f"unsafe target path form: {exc}") from None

    def classify(self, path: Any) -> TargetClass:
        canon = self._canon(path)
        for p in self.production_roots:
            if c3_runtime._within(self.platform, canon, p):
                return TargetClass.PRODUCTION
        pm = ntpath if self.platform == "nt" else posixpath
        if pm.normcase(canon) == pm.normcase(self.container):
            return TargetClass.CONTAINER
        if c3_runtime._within(self.platform, canon, self.container):
            return TargetClass.DISPOSABLE
        return TargetClass.OUTSIDE

    def volume_root(self) -> str:
        """The drive root of the container's volume (``P:\\``); the only
        non-production location a read-only access probe may name."""

        pm = ntpath if self.platform == "nt" else posixpath
        return pm.dirname(self.container)

    def is_probe_readable(self, path: Any) -> bool:
        """True for production locations and the bare volume root: the only
        places a READ-ONLY access probe may target."""

        pm = ntpath if self.platform == "nt" else posixpath
        canon = self._canon(path)
        if pm.normcase(canon) == pm.normcase(self.volume_root()):
            return True
        return self.classify(canon) is TargetClass.PRODUCTION

    def resolve_disposable(self, rel: str) -> str:
        """Join a container-relative path and require it to be strictly inside."""

        if not isinstance(rel, str) or not rel or rel.startswith(("/", "\\")) or "\\" in rel:
            raise errors.SacrificialTargetRefused("disposable targets must be container-relative with forward slashes")
        sep = "\\" if self.platform == "nt" else "/"
        full = self.container.rstrip(sep) + sep + rel.replace("/", sep)
        if self.classify(full) is not TargetClass.DISPOSABLE:
            raise errors.SacrificialTargetRefused("target is not strictly inside the disposable container")
        return self._canon(full)


# --- operations, outcomes and the negative-case catalogue ----------------------------


class Op(str, enum.Enum):
    OPEN_ACCESS = "OPEN_ACCESS"          # open an EXISTING object requesting rights; never creates or changes anything
    CREATE_FILE = "CREATE_FILE"
    CREATE_DIR = "CREATE_DIR"
    OVERWRITE_FILE = "OVERWRITE_FILE"    # open an existing file for write; writes nothing
    DELETE_FILE = "DELETE_FILE"
    RENAME = "RENAME"
    CREATE_JUNCTION = "CREATE_JUNCTION"
    CREATE_HARDLINK = "CREATE_HARDLINK"


MUTATING_OPS = frozenset(Op) - {Op.OPEN_ACCESS}

FILE_ADD_FILE = 0x2
FILE_ADD_SUBDIRECTORY = 0x4
FILE_DELETE_CHILD = 0x40
FILE_READ_DATA = 0x1
DELETE_RIGHT = 0x10000
WRITE_DAC_RIGHT = 0x40000
WRITE_OWNER_RIGHT = 0x80000


@dataclass(frozen=True)
class AttemptResult:
    success: bool
    denied: bool = False
    error: str = ""


class OperationExecutor(Protocol):
    def attempt(self, op: Op, path: str, aux: str | None, access_mask: int | None) -> AttemptResult: ...


@dataclass(frozen=True)
class NegativeCase:
    case_id: str
    op: Op
    target: str                  # container-relative (disposable) or a PRODUCTION key for read-only access probes
    expected: str                # "DENIED" or "ALLOWED"
    purpose: str
    aux: str | None = None       # container-relative second path (rename destination / link source / junction target)
    access_mask: int | None = None
    production_key: str | None = None   # set ONLY for read-only OPEN_ACCESS probes of a real location
    residual: bool = False       # an expected-ALLOWED result that documents a known, accepted residual


NEGATIVE_CASES: tuple[NegativeCase, ...] = (
    NegativeCase("N01", Op.OPEN_ACCESS, "twin/approvals", "DENIED", "no add-file right on approvals", access_mask=FILE_ADD_FILE),
    NegativeCase("N02", Op.OPEN_ACCESS, "twin/approvals", "DENIED", "no add-subdirectory right", access_mask=FILE_ADD_SUBDIRECTORY),
    NegativeCase("N03", Op.OPEN_ACCESS, "twin/approvals", "DENIED", "no delete-child right", access_mask=FILE_DELETE_CHILD),
    NegativeCase("N04", Op.OPEN_ACCESS, "twin/approvals", "DENIED", "no WRITE_DAC", access_mask=WRITE_DAC_RIGHT),
    NegativeCase("N05", Op.OPEN_ACCESS, "twin/approvals", "DENIED", "no WRITE_OWNER", access_mask=WRITE_OWNER_RIGHT),
    NegativeCase("N06", Op.OPEN_ACCESS, "twin/approvals/canary-approval.json", "DENIED", "no write-data right on the approval file", access_mask=FILE_ADD_FILE),
    NegativeCase("N07", Op.OPEN_ACCESS, "twin/approvals/canary-approval.json", "DENIED", "no DELETE right on the approval file", access_mask=DELETE_RIGHT),
    NegativeCase("N08", Op.CREATE_FILE, "twin/approvals/new.txt", "DENIED", "cannot create inside approvals"),
    NegativeCase("N09", Op.DELETE_FILE, "twin/approvals/canary-approval.json", "DENIED", "cannot delete the approval file"),
    NegativeCase("N10", Op.RENAME, "twin/approvals/canary-approval.json", "DENIED", "cannot move the approval file", aux="twin/worktrees/stolen.json"),
    NegativeCase("N11", Op.OVERWRITE_FILE, "twin/approvals/canary-approval.json", "DENIED", "cannot open the approval file for write"),
    NegativeCase("N12", Op.CREATE_FILE, "twin/new-at-twin-root.txt", "DENIED", "cannot create at the twin root"),
    NegativeCase("N13", Op.CREATE_DIR, "escape", "DENIED", "cannot create beside the twin in the container"),
    NegativeCase("N14", Op.RENAME, "twin/approvals", "DENIED", "cannot rename the approvals directory", aux="twin/approvals-moved"),
    NegativeCase("N15", Op.CREATE_FILE, "twin/bin/new.exe", "DENIED", "cannot add code to bin"),
    NegativeCase("N16", Op.CREATE_HARDLINK, "twin/worktrees/link.json", "DENIED", "cannot hard-link the approval file", aux="twin/approvals/canary-approval.json"),
    NegativeCase("N17", Op.CREATE_FILE, "twin/worktrees/control.txt", "ALLOWED", "positive control: worktrees is writable"),
    NegativeCase("N18", Op.CREATE_JUNCTION, "twin/worktrees/junction", "ALLOWED", "agent can create a junction; the guard must then refuse any path through it", aux="twin/approvals"),
    NegativeCase("N19", Op.OPEN_ACCESS, "twin/worktrees", "ALLOWED", "documented residual: Modify includes DELETE on the directory itself", access_mask=DELETE_RIGHT, residual=True),
    NegativeCase("P01", Op.OPEN_ACCESS, "", "DENIED", "REAL approvals: no add-file right", access_mask=FILE_ADD_FILE, production_key="approvals"),
    NegativeCase("P02", Op.OPEN_ACCESS, "", "DENIED", "REAL approvals: no WRITE_DAC", access_mask=WRITE_DAC_RIGHT, production_key="approvals"),
    NegativeCase("P03", Op.OPEN_ACCESS, "", "DENIED", "REAL bin: no add-file right", access_mask=FILE_ADD_FILE, production_key="bin"),
    NegativeCase("P04", Op.OPEN_ACCESS, "", "DENIED", "REAL volume root: no add-subdirectory right", access_mask=FILE_ADD_SUBDIRECTORY, production_key="root"),
    NegativeCase("P05", Op.OPEN_ACCESS, "", "DENIED", "REAL VHDX folder: no read access", access_mask=FILE_READ_DATA, production_key="vault_dir"),
    NegativeCase("P06", Op.OPEN_ACCESS, "", "DENIED", "REAL VHDX file: no read access", access_mask=FILE_READ_DATA, production_key="vhdx"),
)


def validate_case_catalogue(cases: Sequence[NegativeCase]) -> None:
    """Static sanity: unique ids; mutating ops never name production; production
    probes are read-only OPEN_ACCESS on a known production key only."""

    seen: set[str] = set()
    for c in cases:
        if c.case_id in seen:
            raise errors.SacrificialTargetRefused(f"duplicate case id {c.case_id}")
        seen.add(c.case_id)
        if c.expected not in ("DENIED", "ALLOWED"):
            raise errors.SacrificialTargetRefused(f"{c.case_id}: invalid expectation")
        if c.production_key is not None:
            if c.op is not Op.OPEN_ACCESS or c.production_key not in PRODUCTION_KEYS or c.expected != "DENIED":
                raise errors.SacrificialTargetRefused(f"{c.case_id}: a production probe must be a read-only DENIED OPEN_ACCESS")
            if c.access_mask is None or c.aux is not None:
                raise errors.SacrificialTargetRefused(f"{c.case_id}: malformed production probe")
        elif c.op is Op.OPEN_ACCESS and c.access_mask is None:
            raise errors.SacrificialTargetRefused(f"{c.case_id}: OPEN_ACCESS needs an access mask")


# --- the disposable twin tree specification (nothing is created in G0) ----------------


AGENT_RX = 0x1200A9
AGENT_MODIFY = 0x1301BF
CANARY_APPROVAL = b'{"canary": true, "note": "synthetic disposable file; carries no authority"}\n'
CANARY_TEXT = b"canary\n"


@dataclass(frozen=True)
class TwinNode:
    rel: str                 # container-relative; "" is the container itself
    kind: str                # "dir" | "file"
    agent_rights: str        # RX_THIS_FOLDER | RX_INHERIT | MODIFY_INHERIT | INHERITED
    content: bytes | None = None


TWIN_NODES: tuple[TwinNode, ...] = (
    TwinNode("", "dir", "RX_THIS_FOLDER"),
    TwinNode("twin", "dir", "RX_THIS_FOLDER"),
    TwinNode("twin/approvals", "dir", "RX_INHERIT"),
    TwinNode("twin/approvals/canary-approval.json", "file", "INHERITED", CANARY_APPROVAL),
    TwinNode("twin/bin", "dir", "RX_INHERIT"),
    TwinNode("twin/bin/canary.txt", "file", "INHERITED", CANARY_TEXT),
    TwinNode("twin/worktrees", "dir", "MODIFY_INHERIT"),
    TwinNode("twin/runtime", "dir", "MODIFY_INHERIT"),
    TwinNode("twin/evidence", "dir", "MODIFY_INHERIT"),
)


def twin_expected_agent_mask(node: TwinNode) -> int:
    return AGENT_MODIFY if node.agent_rights == "MODIFY_INHERIT" else AGENT_RX


def twin_security(owner_sid: str, agent_sid: str, owner_user_sid: str, container_path: str) -> dict[str, acl_guard.NodeSecurity]:
    """The intended descriptors of the twin (for G1 provisioning and for tests):
    protected container/twin roots, SYSTEM/Administrators/owner Full, the agent
    limited exactly as production. Returns ``{abs_path: NodeSecurity}``."""

    full = 0x1F01FF
    principals = (acl_guard.SID_SYSTEM, acl_guard.SID_ADMINISTRATORS, owner_user_sid)
    out: dict[str, acl_guard.NodeSecurity] = {}
    for node in TWIN_NODES:
        path = container_path if not node.rel else container_path.rstrip("\\") + "\\" + node.rel.replace("/", "\\")
        agent_mask = twin_expected_agent_mask(node)
        if node.rel in ("", "twin"):
            # Protected roots: explicit full-control ACEs; the agent only reads this folder.
            aces = tuple(acl_guard.Ace(sid, full) for sid in principals) + (acl_guard.Ace(agent_sid, agent_mask),)
        else:
            # Everything below inherits the principals; the agent ACE is explicit on
            # directories and inherited on the canary files.
            inherited = tuple(acl_guard.Ace(sid, full, inherited=True) for sid in principals)
            aces = (acl_guard.Ace(agent_sid, agent_mask, inherited=(node.kind == "file")),) + inherited
        out[path] = acl_guard.NodeSecurity(path, owner_sid, aces, is_dir=(node.kind == "dir"))
    return out


# --- filesystem adapter + idempotent, bounded cleanup ----------------------------------


class FsAdapter(Protocol):
    def lstat_kind(self, path: str) -> str: ...      # missing | file | dir | link | other
    def listdir(self, path: str) -> list[str]: ...
    def remove_file(self, path: str) -> None: ...
    def remove_dir(self, path: str) -> None: ...
    def remove_link(self, path: str) -> None: ...


class OsFsAdapter:
    """Real filesystem adapter (used by tests on pytest temp dirs)."""

    def lstat_kind(self, path: str) -> str:
        try:
            st = os.lstat(path)
        except FileNotFoundError:
            return "missing"
        if stat.S_ISLNK(st.st_mode) or (getattr(st, "st_file_attributes", 0) & 0x400):
            return "link"
        if stat.S_ISDIR(st.st_mode):
            return "dir"
        return "file" if stat.S_ISREG(st.st_mode) else "other"

    def listdir(self, path: str) -> list[str]:
        return sorted(os.listdir(path))

    def remove_file(self, path: str) -> None:
        os.remove(path)

    def remove_dir(self, path: str) -> None:
        os.rmdir(path)

    def remove_link(self, path: str) -> None:
        # Never follows: a junction/directory link is removed with rmdir, a file link with unlink.
        try:
            os.rmdir(path)
        except OSError:
            os.remove(path)


@dataclass(frozen=True)
class CleanupReport:
    already_clean: bool
    removed: int
    failures: tuple[str, ...] = ()

    @property
    def clean(self) -> bool:
        return not self.failures


def cleanup_container(
    policy: TargetPolicy, fs: FsAdapter, *, requested: str | None = None, tick: Callable[[], None] | None = None,
) -> CleanupReport:
    """Remove the disposable container and everything in it.

    Idempotent (a missing container is success); never leaves the container
    (every child is re-checked); never descends into a link/junction; bounded in
    depth and entry count; refuses a container that is itself a link.
    """

    pf = policy.platform
    pm = ntpath if pf == "nt" else posixpath
    if requested is not None and policy._canon(requested) != policy.container:
        raise errors.SacrificialTargetRefused("cleanup was requested for something other than the disposable container")
    kind = fs.lstat_kind(policy.container)
    if kind == "missing":
        return CleanupReport(already_clean=True, removed=0)
    if kind != "dir":
        raise errors.SacrificialTargetRefused(f"the container is a {kind}, not a plain directory; refusing to touch it")
    plan: list[tuple[str, str]] = []
    failures: list[str] = []
    stack = [(policy.container, 0)]
    while stack:
        path, depth = stack.pop()
        if depth > MAX_CLEANUP_DEPTH:
            raise errors.ProbeAborted("cleanup depth bound exceeded")
        if tick is not None:
            tick()
        try:
            names = fs.listdir(path)
        except OSError as exc:
            # An unreadable directory is recorded, not fatal to the report; the
            # container is then kept (something remains).
            failures.append(f"list:{pm.basename(path)}:{exc.__class__.__name__}")
            continue
        for name in names:
            if not name or name in (".", "..") or any(ch in name for ch in "\\/:") or name != name.strip():
                raise errors.SacrificialTargetRefused("unsafe directory entry name")
            child = pm.join(path, name)
            if not c3_runtime._within(pf, child, policy.container) or pm.normcase(child) == pm.normcase(policy.container):
                raise errors.SacrificialTargetRefused("an entry escapes the disposable container")
            if len(plan) >= MAX_CLEANUP_ENTRIES:
                raise errors.ProbeAborted("cleanup entry bound exceeded")
            k = fs.lstat_kind(child)
            if k == "dir":
                plan.append(("dir", child))
                stack.append((child, depth + 1))
            elif k == "file":
                plan.append(("file", child))
            elif k == "link":
                plan.append(("link", child))      # removed itself, never traversed
            else:
                raise errors.SacrificialTargetRefused(f"special or vanished entry refused: {name}")
    removed = 0
    for k, child in reversed(plan):
        if tick is not None:
            tick()
        # Re-prove the planned kind immediately before removing it: an entry that was
        # swapped (e.g. a directory replaced by a junction) is reported, not followed.
        if fs.lstat_kind(child) != k:
            failures.append(f"changed:{pm.basename(child)}")
            continue
        try:
            {"file": fs.remove_file, "dir": fs.remove_dir, "link": fs.remove_link}[k](child)
            removed += 1
        except OSError as exc:
            failures.append(f"{k}:{pm.basename(child)}:{exc.__class__.__name__}")
    if not failures:
        try:
            fs.remove_dir(policy.container)
            removed += 1
        except OSError as exc:
            failures.append(f"container:{exc.__class__.__name__}")
    return CleanupReport(already_clean=False, removed=removed, failures=tuple(failures))


# --- executing the negative cases (only after authorization) -----------------------------


@dataclass(frozen=True)
class CaseOutcome:
    case_id: str
    expected: str
    observed: str            # DENIED | ALLOWED | OTHER_ERROR
    ok: bool
    note: str = ""


def require_negative_authorization(approval: ProbeApproval, now: datetime) -> None:
    if approval.phase != "NEGATIVE" or not approval.negative_authorized:
        raise errors.ApprovalInvalid("negative tests are not authorized by this approval")
    if approval.expires_at <= now:
        raise errors.ApprovalInvalid("probe approval has expired")


def run_negative_cases(
    cases: Sequence[NegativeCase], *, approval: ProbeApproval, policy: TargetPolicy,
    executor: OperationExecutor, now: datetime, tick: Callable[[], None] | None = None,
) -> list[CaseOutcome]:
    """Dispatch the catalogue. EVERY target is validated BEFORE the first
    operation runs, so a bad catalogue cannot half-execute. Stops immediately on
    an unexpected access success or on a failure that is not an access denial."""

    require_negative_authorization(approval, now)
    if not cases:
        raise errors.ProbeAborted("NO_CASES: an empty catalogue proves nothing")
    validate_case_catalogue(cases)
    plan: list[tuple[NegativeCase, str, str | None]] = []
    for c in cases:
        if c.production_key is not None:
            path = approval.production_paths[c.production_key]
            if not policy.is_probe_readable(path):
                raise errors.SacrificialTargetRefused(f"{c.case_id}: the production path is not a protected location")
            if c.production_key == "root" and policy._canon(path) != policy.volume_root():
                raise errors.SacrificialTargetRefused(f"{c.case_id}: 'root' must be the container's volume root")
            plan.append((c, policy._canon(path), None))
            continue
        target = policy.resolve_disposable(c.target)
        aux = policy.resolve_disposable(c.aux) if c.aux else None
        plan.append((c, target, aux))
    outcomes: list[CaseOutcome] = []
    for c, target, aux in plan:
        if tick is not None:
            tick()
        res = executor.attempt(c.op, target, aux, c.access_mask)
        observed = "ALLOWED" if res.success else ("DENIED" if res.denied else "OTHER_ERROR")
        ok = observed == c.expected
        outcomes.append(CaseOutcome(c.case_id, c.expected, observed, ok, res.error[:80]))
        if not ok:
            if observed == "ALLOWED" and c.expected == "DENIED":
                raise errors.ProbeAborted(f"UNEXPECTED_ACCESS_SUCCESS {c.case_id}: {c.purpose}")
            raise errors.ProbeAborted(f"CASE_FAILED {c.case_id}: expected {c.expected}, observed {observed}")
    return outcomes


class OsOperationExecutor:
    """Real executor for tests on pytest temp dirs / for the future G3 run.

    It cannot be constructed without an explicit ``TargetPolicy`` and it
    re-checks every path itself (defence in depth) before touching it: mutating
    operations require DISPOSABLE targets; production targets are accepted only
    for the read-only OPEN_ACCESS probe.
    """

    def __init__(self, policy: TargetPolicy, open_access: Callable[[str, int], tuple[bool, bool, str]] | None = None) -> None:
        self._policy = policy
        self._open_access = open_access

    def _refuse_if_an_ancestor_is_a_link(self, path: str) -> None:
        """Defence in depth (check-then-use; the residual race is a documented G3
        prerequisite: handle-relative operations): refuse when any EXISTING
        directory between the container and the target is a link/junction."""

        pm = ntpath if self._policy.platform == "nt" else posixpath
        current = self._policy.container
        remainder = path[len(current):].strip("\\/")
        parts = [p for p in remainder.replace("\\", "/").split("/") if p][:-1]
        for part in [""] + parts:
            probe_path = pm.join(current, part) if part else current
            if part:
                current = probe_path
            try:
                st = os.lstat(probe_path)
            except FileNotFoundError:
                return
            if stat.S_ISLNK(st.st_mode) or (getattr(st, "st_file_attributes", 0) & 0x400):
                raise errors.SacrificialTargetRefused("a link or junction lies inside the disposable path")

    def attempt(self, op: Op, path: str, aux: str | None, access_mask: int | None) -> AttemptResult:
        cls = self._policy.classify(path)
        if op in MUTATING_OPS:
            if cls is not TargetClass.DISPOSABLE:
                raise errors.SacrificialTargetRefused(f"{op.value} refused on a {cls.value} target")
            if aux is not None and self._policy.classify(aux) is not TargetClass.DISPOSABLE:
                raise errors.SacrificialTargetRefused("auxiliary path is not disposable")
        elif cls is not TargetClass.DISPOSABLE and not self._policy.is_probe_readable(path):
            raise errors.SacrificialTargetRefused(f"OPEN_ACCESS refused on a {cls.value} target")
        if op in MUTATING_OPS:
            self._refuse_if_an_ancestor_is_a_link(path)
            if aux is not None and op is Op.RENAME:
                self._refuse_if_an_ancestor_is_a_link(aux)
        try:
            if op is Op.OPEN_ACCESS:
                if self._open_access is None or access_mask is None:
                    return AttemptResult(False, False, "no access opener")
                granted, denied, err = self._open_access(path, access_mask)
                return AttemptResult(granted, denied, err)
            if op is Op.CREATE_FILE:
                os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            elif op is Op.CREATE_DIR:
                os.mkdir(path)
            elif op is Op.OVERWRITE_FILE:
                with open(path, "r+b"):
                    pass
            elif op is Op.DELETE_FILE:
                os.remove(path)
            elif op is Op.RENAME:
                os.rename(path, aux or "")
            elif op is Op.CREATE_HARDLINK:
                os.link(aux or "", path)
            elif op is Op.CREATE_JUNCTION:
                if os.name == "nt":
                    import _winapi

                    _winapi.CreateJunction(aux or "", path)
                else:
                    os.symlink(aux or "", path)
            return AttemptResult(True)
        except PermissionError as exc:
            return AttemptResult(False, True, exc.__class__.__name__)
        except OSError as exc:
            return AttemptResult(False, False, exc.__class__.__name__)


# --- preflight helpers ----------------------------------------------------------------------


def check_free_space(minimums: Mapping[str, int], provider: Callable[[str], int | None], *, approved_root: str) -> list[str]:
    """Return the verified roots; unreadable or low space aborts (fail closed).

    The WHOLE configuration is re-validated against the approved volume root before
    the provider (``shutil.disk_usage`` in ENFORCED runs) is called even once."""

    _validate_free_floor(minimums, approved_root, errors.ProbeAborted)
    ok: list[str] = []
    for root, need in minimums.items():
        free = provider(root)
        if free is None or isinstance(free, bool) or not isinstance(free, int):
            raise errors.ProbeAborted(f"FREE_SPACE_UNVERIFIABLE {root}")
        if free < need:
            raise errors.ProbeAborted(f"FREE_SPACE_LOW {root}")
        ok.append(root)
    return ok


# --- S4U prerequisites + read-back validation (no task is ever registered here) -------------


S4U_SPEC: Mapping[str, Any] = {
    "principal": "the approved agent account (by SID), NOT the owner, NOT an administrator",
    "logon_type": "S4U",
    "run_level": "Limited",
    "password_stored": False,
    "triggers": "none (on-demand start only)",
    "actions": 1,
    "interpreter": "<trusted_root>\\python\\python.exe",
    "interpreter_flags": ["-I", "-B"],
    "working_directory": "<trusted_root>\\app (agent read-only)",
    "execution_time_limit_seconds": MAX_RUN_SECONDS,
    "entry_point": "python.exe -I -B -m scripts.orchestrator.c3_probe (package on the interpreter's ._pth)",
    "g1_provisioning_checklist": [
        "interpreter ._pth lists only the interpreter directory/zip and <trusted_root>\\app (no current dir, no site-packages unless attested)",
        "every interpreter file (not only .exe/.dll/.pyd) has an owner-recorded reference hash",
        "system DLLs are loaded from System32 only (the Windows backend uses LOAD_LIBRARY_SEARCH_SYSTEM32)",
        "trust is established by an owner-controlled launcher BEFORE the probe's own imports run",
        "the launcher calls run_enforced_probe with configuration and canonical manifest bytes it obtained itself",
        "the tree listing for the pinned commit comes from the owner's trusted object database (blob ids are SHA-1)",
    ],
    "known_g0_limits": [
        "sacrificial operations are path-based; handle-relative no-follow operations are a G3 prerequisite",
        "cleanup re-checks each entry immediately before removal but is not handle-relative",
        "no guard expectation exists for D:\\PetCareVault / the VHDX (needs a second volume binding); P05/P06 open probes cover it",
        "launcher-before-import trust and signature-report production are specified, not implemented",
        # Finding #26 (OPEN - documented, not resolved).
        "package paths are validated with WINDOWS rules on every platform (c3_package.validate_rel_path): reserved "
        "device names (con, aux, nul, com1 ...), 8.3-style '~N' components, trailing dots/spaces, alternate streams "
        "and git core.quotePath-escaped names are all refused with the same PACKAGE_INTEGRITY_FAILURE reason as "
        "tampering. This fails closed but cannot tell an innocent repository name from a hostile one, and a repository "
        "containing such a name cannot be packaged. Only line-oriented, tab-separated 'git ls-tree -r' output "
        "produced with core.quotePath=false is supported; NUL-delimited '-z' output is NOT parsed and fails closed. "
        "Unicode control/format characters (e.g. U+202E) are also refused (G0-R-B); confusable or homoglyph names are "
        "NOT detected",
        "the ProvenanceEvidence seal and the ENFORCED time sources (_wall_now/_monotonic) are module objects: they "
        "block caller input and naive construction, but code already running in the probe process can replace them, "
        "so the binding that counts is the live interpreter re-scan against the owner-pinned interpreter_tree_sha256 "
        "and, ultimately, launcher-before-import trust (G1)",
        "ENFORCED rebuilds the package manifest from canonical bytes whose sha256 equals the approved "
        "package_manifest_sha256 (no caller manifest object is used); the installed application tree is re-scanned "
        "live. The manifest's source_commit/listing relationship is still not bound to a trusted object database (G1)",
        # G0-R-D: free space and guard-refusal reasons.
        "the free-space floor covers ONLY the approved volume root (production_paths.root, exactly 'X:\\', the volume "
        "the pinned approval read verifies); min_free_bytes must name exactly that key with a 1..2**50 integer and is "
        "re-validated before any disk_usage call. The D:\\ vault / VHDX host volume has NO free-space floor until a "
        "second volume binding exists (G3 prerequisite, together with the VHDX growth risk)",
        "an expected guard denial is accepted only when the guard's structured reasons are exactly one AGENT_RIGHTS "
        "violation on the queried path and nothing unverifiable; the human detail text is no longer matched. The "
        "reason codes distinguish only AGENT_RIGHTS from OTHER (finer owner/volume/identity codes are not modelled)",
        "the trusted owner SIDs, agent SID and volume binding passed to run_enforced_probe are deployment "
        "configuration: they must equal the values in the owner-protected approval, but their own provenance is the "
        "G1 launcher's responsibility",
    ],
    # Limits that MUST be resolved before G1 is authorized (not accepted, not fixed).
    "blocking_g1": [
        "scan_tree (c3_package) enumerates directories by PATH, not through pinned no-follow directory handles: the "
        "Python standard library offers no handle-relative directory enumeration on Windows (no dir_fd / fd-scandir) "
        "and this module may not use ctypes. G0-R-C adds detection only (each directory's identity and reparse state "
        "is re-checked before enumeration, after enumeration and after the whole walk, and every file handle must "
        "match its lstat identity); a directory swapped and restored inside those windows is NOT detected. Because "
        "this walk produces the ENFORCED interpreter and application attestation, G1 must provide a handle-relative "
        "walk (e.g. NtCreateFile relative to a pinned directory handle in the Windows backend) or an equivalent "
        "owner-controlled guarantee that <bin> cannot change during the run",
    ],
    "open_questions_for_G2": [
        "Does the agent account hold the 'Log on as a batch job' right? (unreadable without elevation)",
        "Does the S4U token carry the expected groups, only standard-user privileges and Medium integrity?",
        "Is the task's own security descriptor limited to the owner for start/read?",
    ],
}


def _task_path(value: str) -> str:
    """A canonical local drive path with no quote, so it cannot break out of the
    quoted command line it is placed in."""

    if not isinstance(value, str) or '"' in value or "'" in value or "%" in value:
        raise ValueError("task paths may not contain quotes or environment expansion")
    try:
        return acl_guard.canonical_windows_path(value)
    except acl_guard.PathRejected as exc:
        raise ValueError(f"unsafe task path: {exc}") from None


def build_task_arguments(trusted_root: str, phase: str, approval_path: str) -> str:
    """The fixed command line of the (future) task. It starts the probe as a
    MODULE of the immutable package (``-m``): the ``._pth`` file of the pinned
    interpreter must list ``<trusted_root>\\app`` so the package is importable
    while ``-I`` keeps the current directory and the environment out of it."""

    if phase not in PHASES[1:]:
        raise ValueError("a task may only run the READONLY or NEGATIVE phase")
    _task_path(trusted_root)
    approval = _task_path(approval_path)
    return f'-I -B -m scripts.orchestrator.c3_probe --phase {phase} --approval "{approval}"'


def validate_task_definition(task: Mapping[str, Any], *, expected_agent_sid: str, trusted_root: str, phase: str, approval_path: str) -> list[str]:
    """Findings for a read-back of a (future) registered task; empty = matches."""

    out: list[str] = []
    if task.get("principal_sid") != expected_agent_sid:
        out.append("task principal is not the approved agent SID")
    if task.get("logon_type") != "S4U":
        out.append("task logon type is not S4U")
    if task.get("run_level") != "Limited":
        out.append("task must run with limited (non-elevated) rights")
    if task.get("stores_password") is not False:
        out.append("task stores credentials or its credential state is unknown")
    if task.get("triggers") != []:
        out.append("task must have no triggers (on-demand only)")
    actions = task.get("actions")
    if not isinstance(actions, list) or len(actions) != 1:
        out.append("task must have exactly one action")
    else:
        act = actions[0]
        root = _task_path(trusted_root)
        expected_exe = ntpath.normcase(root.rstrip("\\") + "\\python\\python.exe")
        expected_wd = ntpath.normcase(root.rstrip("\\") + "\\app")

        def same(value: Any, expected: str) -> bool:
            try:
                return ntpath.normcase(acl_guard.canonical_windows_path(value)) == expected
            except acl_guard.PathRejected:
                return False  # 8.3 aliases, streams, dot segments, UNC ... are never "the same path"

        if not isinstance(act, dict) or not same(act.get("execute", ""), expected_exe):
            out.append("task action does not run the pinned interpreter (or uses an alias/unsafe form)")
        if not isinstance(act, dict) or act.get("arguments") != build_task_arguments(trusted_root, phase, approval_path):
            out.append("task arguments differ from the approved fixed command line")
        if not isinstance(act, dict) or not same(act.get("working_directory", ""), expected_wd):
            out.append("task working directory is not the trusted application directory")
    limit = task.get("execution_time_limit_seconds")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 0 < limit <= MAX_RUN_SECONDS:
        out.append("task execution time limit is missing or too long")
    return out


# --- the probe run ------------------------------------------------------------------------------


@dataclass
class ProbeContext:
    """OFFLINE_MOCKED runs only.

    ENFORCED runs never take a caller-built context: they go through
    :func:`run_enforced_probe`, which accepts plain configuration values and
    builds every trust input itself (G0-R-C). A context with ``mode`` left at
    ``"ENFORCED"`` is refused before anything in it is used.
    """

    approval: ProbeApproval
    guard: Any
    policy: TargetPolicy
    package_manifest: c3_package.PackageManifest
    observed_tree: Mapping[str, tuple[str, int]] | None
    now: datetime
    mode: str = "ENFORCED"                      # must be set to OFFLINE_MOCKED explicitly
    identity_provider: Callable[[], acl_guard.Identity] | None = None
    free_space: Callable[[str], int | None] | None = None
    executor: OperationExecutor | None = None
    fs: FsAdapter | None = None
    cases: Sequence[NegativeCase] | None = None
    max_seconds: float = MAX_RUN_SECONDS
    clock: Callable[[], float] = time.monotonic


def real_free_space(root: str) -> int | None:
    try:
        return int(shutil.disk_usage(root).free)
    except OSError:
        return None


# Trusted time sources for ENFORCED runs. They are module functions (not caller
# input). Code running inside the probe process could still replace them; that is
# the same in-process residual recorded for the provenance seal.
def _wall_now() -> datetime:
    return datetime.now(timezone.utc)


_monotonic = time.monotonic


@dataclass
class _Report:
    mode: str
    phase: str
    checks: list[dict[str, str]] = field(default_factory=list)
    identity: dict[str, Any] = field(default_factory=dict)
    negative: list[dict[str, str]] = field(default_factory=list)
    cleanup: dict[str, Any] | None = None
    verdict: str = "UNVERIFIED"
    reason_code: str | None = None

    def check(self, check_id: str, status: str, detail: str = "") -> None:
        self.checks.append({"id": check_id, "status": status, "detail": detail[:300]})

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": REPORT_SCHEMA, "mode": self.mode, "phase": self.phase, "verdict": self.verdict,
            "reason_code": self.reason_code, "checks": self.checks, "identity": self.identity,
            "negative": self.negative, "cleanup": self.cleanup,
        }


@dataclass
class _Deps:
    identity: Callable[[], acl_guard.Identity]
    free_space: Callable[[str], int | None]
    fs: FsAdapter | None
    executor: OperationExecutor | None
    cases: Sequence[NegativeCase]


@dataclass
class _Trusted:
    """Everything the shared execution steps need, produced by ONE authorization
    function: :func:`_authorize_enforced` (built internally) or
    :func:`_authorize_mocked` (offline fixtures)."""

    enforced: bool
    approval: ProbeApproval
    policy: TargetPolicy
    guard: Any
    manifest: c3_package.PackageManifest
    observed_tree: Mapping[str, tuple[str, int]]
    deps: _Deps
    wall_now: Callable[[], datetime]
    tick: Callable[[], None]
    snapshot: acl_guard.ApprovedFileSnapshot | None = None
    ran_negative: bool = False


def run_probe(ctx: ProbeContext, phase: str) -> dict[str, Any]:
    """OFFLINE_MOCKED run. Returns a report; any typed stop ends the run with a
    FAIL/UNVERIFIED verdict (never an exception to the caller)."""

    rep = _Report(mode=ctx.mode if isinstance(ctx.mode, str) else "?", phase=phase if isinstance(phase, str) else "?")
    _drive(rep, phase, lambda: _authorize_mocked(ctx, phase, rep))
    return rep.to_dict()


_ENFORCED_PHASES = ("READONLY", "NEGATIVE")


def run_enforced_probe(
    phase: str,
    *,
    approval_path: str,
    expected_agent_sid: str,
    trusted_owner_sids: tuple[str, ...],
    volume_guid: str,
    volume_label: str,
    volume_serial: int,
    package_manifest_bytes: bytes,
    provenance: c3_runtime.ProvenanceEvidence,
) -> dict[str, Any]:
    """ENFORCED run (G0-R-C). Only plain configuration values are accepted:
    exact ``str`` / ``int`` / ``bytes`` / ``tuple`` of ``str``, plus genuine sealed
    provenance evidence. There is no clock, deadline, approval object, snapshot,
    manifest object, target policy, guard, runtime policy, provider or observation
    parameter: the probe derives all of them itself, and no caller-defined method
    is ever invoked. Returns a report; never raises to the caller."""

    rep = _Report(mode="ENFORCED", phase=phase if type(phase) is str else "?")
    cfg = dict(approval_path=approval_path, expected_agent_sid=expected_agent_sid, trusted_owner_sids=trusted_owner_sids,
               volume_guid=volume_guid, volume_label=volume_label, volume_serial=volume_serial,
               package_manifest_bytes=package_manifest_bytes, provenance=provenance)
    _drive(rep, phase, lambda: _authorize_enforced(phase, cfg, rep))
    return rep.to_dict()


def _plain_text(name: str, value: Any) -> str:
    if type(value) is not str or not value:
        raise errors.ApprovalBoundaryViolation(f"{name} must be plain, non-empty text")
    return value


def _authorize_enforced(phase: Any, cfg: Mapping[str, Any], rep: _Report) -> _Trusted:
    start = _monotonic()
    if type(phase) is not str or phase not in _ENFORCED_PHASES:
        raise errors.ApprovalInvalid("ENFORCED runs only the READONLY or NEGATIVE phase (PLAN is offline)")

    # 1. Plain inputs only: exact builtin types, so no caller-defined method can run.
    approval_path = _plain_text("approval_path", cfg["approval_path"])
    agent_sid = _plain_text("expected_agent_sid", cfg["expected_agent_sid"])
    vol_guid = _plain_text("volume_guid", cfg["volume_guid"])
    vol_label = _plain_text("volume_label", cfg["volume_label"])
    owners = cfg["trusted_owner_sids"]
    if type(owners) is not tuple or not owners or any(type(s) is not str for s in owners):
        raise errors.ApprovalBoundaryViolation("trusted_owner_sids must be a non-empty tuple of plain text SIDs")
    if type(cfg["volume_serial"]) is not int:
        raise errors.ApprovalBoundaryViolation("volume_serial must be a plain integer")
    manifest_bytes = cfg["package_manifest_bytes"]
    if type(manifest_bytes) is not bytes:
        raise errors.ApprovalBoundaryViolation("the package manifest must be supplied as canonical bytes")
    provenance = cfg["provenance"]
    if not c3_runtime.is_genuine_evidence(provenance):
        raise errors.RuntimeUntrusted("interpreter provenance evidence is missing or not genuine")

    # 2. The exact volume binding and the boundary policy, built here (one volume only).
    try:
        binding = acl_guard.VolumeBinding(vol_guid, label=vol_label, serial=cfg["volume_serial"])
        boundary = acl_guard.BoundaryPolicy(
            trusted_owner_sids=frozenset(owners), expected_agent_sid=agent_sid, trusted_volumes=(binding,))
        approval_file = acl_guard.canonical_windows_path(approval_path)
    except (ValueError, TypeError, acl_guard.PathRejected) as exc:
        raise errors.ApprovalInvalid(f"enforced configuration rejected: {exc}") from None
    approvals_dir = ntpath.dirname(approval_file)
    backend = acl_guard.default_backend()
    if getattr(backend, "platform", None) != "nt":
        raise errors.ApprovalBoundaryUnverifiable("ENFORCED runs require the Windows security backend")

    # 3. The approval is read ONCE through the production pinned read (boundary chain,
    #    exact volume binding, pinned handle identity) and parsed from those bytes with
    #    the trusted wall clock. Nothing caller-supplied describes the approval.
    snap = acl_guard.read_pinned_approval(backend, boundary, approval_file, approvals_dir, enforced=True)
    try:
        content = snap.content
        if type(content) is not bytes or c3_package.sha256_hex(content) != snap.sha256:
            raise errors.ApprovalBoundaryViolation("the pinned approval bytes are inconsistent")
        approval = parse_probe_approval(content, now=_wall_now())
        if approval.expected_agent_sid != agent_sid or approval.trusted_owner_sids != frozenset(owners):
            raise errors.ApprovalBoundaryViolation("the approval names a different agent or owners than the enforced boundary")
        if approval.trusted_volume != binding:
            raise errors.ApprovalBoundaryViolation("the approval's trusted volume differs from the exact enforced binding")
        appr_dir = acl_guard.canonical_windows_path(approval.production_paths["approvals"])
        if ntpath.normcase(appr_dir) != ntpath.normcase(approvals_dir):
            raise errors.ApprovalBoundaryViolation("the approval file is not in the approved approvals directory")
        # The free-space root is bound to the volume the pinned read just verified: parsing
        # requires approvals[:3] == root exactly, and the check above makes approvals_dir
        # (canonical, upper-case drive) the same directory, so root IS the verified volume.
        if not approval.phase_allows(phase):
            raise errors.ApprovalInvalid("the approval does not authorize this phase")
        deadline = start + approval.max_run_seconds

        def tick() -> None:
            if _monotonic() > deadline:
                raise errors.ProbeAborted(f"DEADLINE_EXCEEDED after {approval.max_run_seconds}s")

        rep.check("approval_pinned", "PASS", f"read through the pinned production guard; phase {approval.phase}")

        # 4. The package manifest is rebuilt from canonical bytes whose digest is approved.
        if c3_package.sha256_hex(manifest_bytes) != approval.package_manifest_sha256:
            raise errors.PackageIntegrityFailure("the package manifest bytes are not the approved manifest")
        manifest = c3_package.PackageManifest.from_bytes(manifest_bytes)
        if manifest.to_bytes() != manifest_bytes:
            raise errors.PackageIntegrityFailure("the package manifest bytes are not in canonical form")

        # 5. Target policy, guard and runtime rules are derived from the approval.
        policy = TargetPolicy(
            container=approval.container,
            production_roots=tuple(approval.production_paths[k] for k in PRODUCTION_KEYS if k != "root"), platform="nt")
        guard = acl_guard.ProductionApprovalGuard(boundary)
        _check_bindings(approval, policy, guard)
        runtime_policy, interp_root, app_root = _enforced_runtime_policy(approval)
        rep.check("bindings", "PASS", "approval, exact volume binding, target policy and guard agree")
        tick()

        # 6. Only now: live observations (environment, interpreter tree, application tree).
        live_env, live_interp, observed_tree = _observe_live(interp_root, app_root)
        c3_runtime.require_trusted_runtime(
            live_env, runtime_policy, provenance,
            observed_interpreter=live_interp, pinned_tree_sha256=approval.interpreter_tree_sha256,
        )
        rep.check("runtime", "PASS", "live isolated runtime; provenance equals the live, owner-pinned interpreter tree")
        tick()
        deps = _Deps(
            identity=backend.current_identity, free_space=real_free_space, fs=OsFsAdapter(),
            executor=OsOperationExecutor(policy, open_access=getattr(backend, "probe_open_access", None)),
            cases=NEGATIVE_CASES,
        )
        return _Trusted(enforced=True, approval=approval, policy=policy, guard=guard, manifest=manifest,
                        observed_tree=observed_tree, deps=deps, wall_now=_wall_now, tick=tick, snapshot=snap)
    except BaseException:
        snap.close()
        raise


def _enforced_runtime_policy(approval: ProbeApproval) -> tuple[c3_runtime.RuntimePolicy, str, str]:
    """The runtime security rules are FIXED (the module defaults: required isolation
    flags, standard finders and path hooks). Only the locations come from the
    approval: trusted root = approved ``bin``; interpreter = ``<bin>\\python\\python.exe``;
    every approved agent-writable location is declared agent-writable."""

    prod = approval.production_paths
    try:
        bin_root = acl_guard.canonical_windows_path(prod["bin"])
        writable = tuple(acl_guard.canonical_windows_path(prod[k]) for k in AGENT_WRITABLE_PRODUCTION)
        interp_root = bin_root.rstrip("\\") + "\\python"
        app_root = bin_root.rstrip("\\") + "\\app"
        policy = c3_runtime.RuntimePolicy(platform="nt", trusted_root=bin_root, agent_writable_roots=writable,
                                          expected_executable=interp_root + "\\python.exe")
    except (ValueError, acl_guard.PathRejected) as exc:
        raise errors.RuntimeUntrusted(f"approved runtime location is unsafe: {exc}") from None
    return policy, interp_root, app_root


def _observe_live(interp_root: str, app_root: str) -> tuple[c3_runtime.EnvironmentSnapshot, dict[str, str], dict[str, tuple[str, int]]]:
    """Trusted LIVE inspection only: the current interpreter's own state and
    read-only re-scans of the interpreter and application trees. Anything that
    cannot be established fails closed."""

    try:
        env = c3_runtime.capture_environment()
    except Exception as exc:  # noqa: BLE001 - an unobservable runtime is untrusted, whatever the cause
        raise errors.RuntimeUntrusted(f"the live runtime could not be observed ({type(exc).__name__})") from None
    if type(env) is not c3_runtime.EnvironmentSnapshot:
        raise errors.RuntimeUntrusted("the live runtime observation is malformed")
    interp_scan = c3_package.scan_tree(interp_root)   # PackageIntegrityFailure if unreadable/linked/odd/changed
    app_scan = c3_package.scan_tree(app_root)
    interp: dict[str, str] = {}
    for rel, value in interp_scan.items():
        if not (type(value) is tuple and len(value) == 2 and type(value[0]) is str):
            raise errors.RuntimeUntrusted("the live interpreter tree observation is malformed")
        interp[rel] = value[0]
    if not interp or not app_scan:
        raise errors.RuntimeUntrusted("the live interpreter or application tree is empty")
    return env, interp, dict(app_scan)


def _check_bindings(approval: ProbeApproval, policy: TargetPolicy, guard: Any) -> None:
    """The approval is the single source of truth: the active target policy and the
    boundary guard's policy must be exactly what the owner approved, with EXACTLY
    the approved volume binding (no additional trusted volume)."""

    if policy.container != approval.container:
        raise errors.ApprovalInvalid("the approved container differs from the active target policy")
    for key, value in approval.production_paths.items():
        canon = policy._canon(value)
        if key == "root":
            if canon != policy.volume_root():
                raise errors.ApprovalInvalid("the approved volume root differs from the container's volume")
        elif policy.classify(canon) is not TargetClass.PRODUCTION:
            raise errors.ApprovalInvalid(f"approved production path '{key}' is not a production root of the active policy")
    guard_policy = getattr(guard, "policy", None)
    if type(guard_policy) is not acl_guard.BoundaryPolicy:
        raise errors.ApprovalBoundaryUnverifiable("the guard does not expose its policy for binding")
    if guard_policy.expected_agent_sid != approval.expected_agent_sid:
        raise errors.ApprovalBoundaryViolation("the guard's expected agent differs from the approved agent")
    if guard_policy.trusted_owner_sids != approval.trusted_owner_sids:
        raise errors.ApprovalBoundaryViolation("the guard's trusted owners differ from the approved owners")
    if guard_policy.trusted_volumes != (approval.trusted_volume,):
        raise errors.ApprovalBoundaryViolation("the guard must bind exactly the approved volume and no other")


def _authorize_mocked(ctx: ProbeContext, phase: str, rep: _Report) -> _Trusted | None:
    if ctx.mode == "ENFORCED":
        raise errors.ApprovalBoundaryViolation(
            "ENFORCED runs only through run_enforced_probe; a caller-built context is never trusted")
    if ctx.mode != "OFFLINE_MOCKED":
        raise errors.ApprovalInvalid("unknown probe mode")
    deadline = ctx.clock() + ctx.max_seconds

    def tick() -> None:
        if ctx.clock() > deadline:
            raise errors.ProbeAborted(f"DEADLINE_EXCEEDED after {ctx.max_seconds:.0f}s")

    if phase not in PHASES:
        raise errors.ApprovalInvalid("unknown probe phase")
    if not ctx.approval.phase_allows(phase):
        raise errors.ApprovalInvalid("the approval does not authorize this phase")
    if ctx.approval.expires_at <= ctx.now:
        raise errors.ApprovalInvalid("probe approval has expired")
    if ctx.approval.package_manifest_sha256 != ctx.package_manifest.digest():
        raise errors.PackageIntegrityFailure("the approval is bound to a different package manifest")
    rep.check("approval", "PASS", f"phase {ctx.approval.phase}, expires {ctx.approval.expires_at.isoformat()}")
    if phase == "PLAN":
        rep.verdict = "PASS_PLAN_ONLY"
        return None
    if not getattr(ctx.guard, "offline_only", False):
        raise errors.ApprovalBoundaryViolation("mocked mode requires an offline-only guard")
    if ctx.observed_tree is None:
        raise errors.ProbeAborted("mocked mode requires an observed-tree fixture")
    if ctx.identity_provider is None or ctx.free_space is None:
        raise errors.ProbeAborted("mocked mode requires an identity provider and a free-space provider")
    deps = _Deps(ctx.identity_provider, ctx.free_space, ctx.fs, ctx.executor,
                 ctx.cases if ctx.cases is not None else NEGATIVE_CASES)
    rep.check("runtime", "SKIPPED", "mocked mode: runtime trust is not asserted")
    _check_bindings(ctx.approval, ctx.policy, ctx.guard)
    rep.check("bindings", "PASS", "approval, target policy and guard policy agree")
    tick()
    return _Trusted(enforced=False, approval=ctx.approval, policy=ctx.policy, guard=ctx.guard, manifest=ctx.package_manifest,
                    observed_tree=ctx.observed_tree, deps=deps, wall_now=lambda: ctx.now, tick=tick)


def _execute(run: _Trusted, phase: str, rep: _Report) -> None:
    deps = run.deps
    # 2. Package integrity (ENFORCED: against the live re-scan of the installed app tree).
    c3_package.verify_observed_tree(run.manifest, run.observed_tree)
    rep.check("package", "PASS", f"{len(run.manifest.files)} files match manifest")

    # 3. Executing identity facts (token read; no logon).
    ident = deps.identity()
    if ident.user_sid != run.approval.expected_agent_sid:
        raise errors.ApprovalBoundaryViolation("the executing token is not the approved agent identity")
    _assert_identity_safe(ident, run.approval)
    rep.identity = {
        "user": acl_guard.short_sid(ident.user_sid),
        "groups": len(ident.group_sids),
        "deny_only_groups": len(ident.deny_only_group_sids),
        "integrity_rid": ident.integrity_rid,
        "privileges": None if ident.privileges is None else [(p.name, p.enabled) for p in ident.privileges],
    }
    rep.check("identity", "PASS", "token user equals the approved agent")

    # 4. Free space.
    check_free_space(run.approval.min_free_bytes, deps.free_space, approved_root=run.approval.production_paths["root"])
    rep.check("free_space", "PASS", ",".join(sorted(run.approval.min_free_bytes)))
    run.tick()

    # 5. Boundary verdicts on REAL locations (the guard also binds the volume identity).
    prod = run.approval.production_paths
    for key, expect_ok in (("approvals", True), ("bin", True)) + tuple((k, False) for k in AGENT_WRITABLE_PRODUCTION):
        _guard_expectation(run.guard, rep, f"guard:{key}", prod[key], expect_ok)
        run.tick()
    if phase == "READONLY":
        rep.verdict = "PASS" if run.enforced else "PASS_OFFLINE_MOCKED"
        return

    # 6. NEGATIVE phase: authorization (fresh clock), pinned snapshot, executor, twin, then the cases.
    require_negative_authorization(run.approval, run.wall_now())
    if run.snapshot is not None:
        run.snapshot.revalidate()
    if deps.executor is None or deps.fs is None:
        raise errors.ProbeAborted("negative phase requires an executor and a filesystem adapter")
    if deps.fs.lstat_kind(run.policy.container) != "dir":
        raise errors.ProbeAborted("the disposable twin tree is missing")
    container = run.policy.container
    sep = "\\" if run.policy.platform == "nt" else "/"
    for rel, expect_ok in (("twin/approvals", True), ("twin/bin", True), ("twin/worktrees", False)):
        _guard_expectation(run.guard, rep, f"guard:{rel}", container + sep + rel.replace("/", sep), expect_ok)
    run.ran_negative = True
    for out in run_negative_cases(deps.cases, approval=run.approval, policy=run.policy, executor=deps.executor,
                                  now=run.wall_now(), tick=run.tick):
        rep.negative.append({"id": out.case_id, "expected": out.expected, "observed": out.observed, "ok": str(out.ok)})
    run.tick()  # the final operation is bounded too (finding #17)
    rep.verdict = "PASS" if run.enforced else "PASS_OFFLINE_MOCKED"


def _drive(rep: _Report, phase: str, authorize: Callable[[], "_Trusted | None"]) -> None:
    run: _Trusted | None = None
    try:
        run = authorize()
        if run is None:
            return
        _execute(run, phase, rep)
    except errors.OrchestratorStop as stop:
        rep.reason_code = stop.reason_code
        rep.check("stop", "FAIL", stop.detail)
        unverifiable = isinstance(stop, (errors.ApprovalBoundaryUnverifiable, errors.RuntimeUntrusted, errors.ApprovalMissing))
        rep.verdict = "UNVERIFIED" if unverifiable else "FAIL"
    except Exception as exc:  # noqa: BLE001 - the contract is "always a report"
        rep.reason_code = f"UNEXPECTED_{type(exc).__name__}"
        rep.check("stop", "FAIL", f"unexpected {type(exc).__name__}")
        rep.verdict = "UNVERIFIED"
    finally:
        try:
            if run is not None and run.ran_negative and run.deps.fs is not None:
                _cleanup(run, rep)
        finally:
            if run is not None and run.snapshot is not None:
                run.snapshot.close()


def _cleanup(run: _Trusted, rep: _Report) -> None:
    def fail(code: str) -> None:
        if rep.verdict.startswith("PASS"):
            rep.verdict = "FAIL"
            rep.reason_code = code

    if run.snapshot is not None:
        # Re-confirm the authorization before the removal pass; cleanup still runs
        # (it only ever touches the approved container), but the run cannot PASS.
        try:
            run.snapshot.revalidate()
        except errors.OrchestratorStop as stop:
            rep.check("approval_before_cleanup", "FAIL", stop.detail)
            fail(stop.reason_code)
    try:
        r = cleanup_container(run.policy, run.deps.fs)  # type: ignore[arg-type]  # presence checked by the caller
        rep.cleanup = {"already_clean": r.already_clean, "removed": r.removed, "failures": list(r.failures)}
        if not r.clean:
            fail("CLEANUP_INCOMPLETE")
    except errors.OrchestratorStop as stop:
        rep.cleanup = {"error": stop.reason_code}
        fail(stop.reason_code)
    except Exception as exc:  # noqa: BLE001 - cleanup problems must be reported, never raised
        rep.cleanup = {"error": f"UNEXPECTED_{type(exc).__name__}"}
        fail("CLEANUP_INCOMPLETE")


def _assert_identity_safe(ident: acl_guard.Identity, approval: ProbeApproval) -> None:
    """The probe's own, independent check of the token facts it reports. Group
    membership alone is never enough: privileges and integrity must be known."""

    if (ident.all_ids & approval.trusted_owner_sids or acl_guard.SID_ADMINISTRATORS in ident.all_ids
            or ident.all_ids & acl_guard.DEFAULT_ANCESTOR_OWNER_SIDS):
        raise errors.ApprovalBoundaryViolation("the executing token is owner-, administrator- or system-capable")
    if ident.privileges is None or ident.integrity_rid is None:
        raise errors.ApprovalBoundaryUnverifiable("token privileges or integrity could not be read")
    for p in ident.privileges:
        if p.removed:
            continue
        if p.name in acl_guard.DANGEROUS_PRIVILEGES or p.name not in acl_guard.BENIGN_PRIVILEGES:
            raise errors.ApprovalBoundaryViolation(f"the executing token holds {p.name or 'an unnamed privilege'}")
    if ident.integrity_rid >= acl_guard.INTEGRITY_HIGH:
        raise errors.ApprovalBoundaryViolation("the executing token runs at high integrity")


def _is_exact_rights_denial(stop: errors.ApprovalBoundaryViolation, path: str) -> bool:
    """G0-R-D: an expected denial is accepted ONLY when the guard's structured
    reasons are exactly one agent-rights violation on the queried path itself and
    nothing else (no owner, volume, identity, reparse or ancestor violation and no
    unverifiable item). A message substring is never evidence."""

    codes = getattr(stop, "violation_codes", None)
    if type(codes) is not tuple or len(codes) != 1 or getattr(stop, "unverified_count", None) != 0:
        return False
    code, where = codes[0]
    try:
        same = ntpath.normcase(acl_guard.canonical_windows_path(where)) == ntpath.normcase(acl_guard.canonical_windows_path(path))
    except acl_guard.PathRejected:
        return False
    return code == acl_guard.VIOLATION_AGENT_RIGHTS and same


def _guard_expectation(guard: Any, rep: _Report, check_id: str, path: str, expect_ok: bool) -> None:
    try:
        guard.verify(None, path)
        accepted = True
    except errors.ApprovalBoundaryUnverifiable:
        raise
    except errors.ApprovalBoundaryViolation as stop:
        accepted = False
        if not expect_ok and not _is_exact_rights_denial(stop, path):
            # A refusal for the WRONG reason (volume, identity, reparse, owner ...) is not
            # evidence that the agent lacks write rights here; it is a stop.
            rep.check(check_id, "FAIL", "refused, but not because the agent lacks write rights")
            raise errors.ProbeAborted(f"GUARD_REFUSAL_WRONG_REASON {check_id}") from None
    if accepted != expect_ok:
        rep.check(check_id, "FAIL", f"guard {'accepted' if accepted else 'refused'}, expected {'accept' if expect_ok else 'refuse'}")
        raise errors.ProbeAborted(f"GUARD_VERDICT_MISMATCH {check_id}")
    rep.check(check_id, "PASS", "accepted" if accepted else "refused as expected")


# --- CLI (G0: plan / package / runtime verification only; phases are not runnable) -------------


def _plan_document() -> dict[str, Any]:
    return {
        "schema": REPORT_SCHEMA, "g0_status": "INERT - nothing here is executed against the agent in G0",
        "phases": list(PHASES), "negative_cases": [
            {"id": c.case_id, "op": c.op.value, "target": c.production_key or c.target, "expected": c.expected,
             "read_only_production_probe": c.production_key is not None, "residual": c.residual, "purpose": c.purpose}
            for c in NEGATIVE_CASES],
        "twin": [{"path": n.rel or ".", "kind": n.kind, "agent_rights": n.agent_rights} for n in TWIN_NODES],
        "s4u_prerequisites": S4U_SPEC,
        "stop_conditions": [
            "any denied operation that succeeds", "guard verdict differs from expectation", "token privilege or integrity unexpected",
            "package or provenance hash mismatch", "volume identity mismatch", "free space below minimum",
            "any path that is not strictly inside the disposable container for a mutating operation", f"run longer than {MAX_RUN_SECONDS}s",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="c3_probe")
    parser.add_argument("--phase", choices=PHASES, default="PLAN")
    parser.add_argument("--approval", default=None)
    parser.add_argument("--verify-package", nargs=2, metavar=("EXPORT_DIR", "LS_TREE_FILE"),
                        help="verify an exported directory against a git ls-tree listing and print the manifest digest")
    parser.add_argument("--commit", default=None, help="40-hex commit id for --verify-package")
    parser.add_argument("--trusted-root", default=None, help="check the CURRENT interpreter's ENVIRONMENT against this trusted root")
    parser.add_argument("--agent-writable-root", action="append", default=[],
                        help="an agent-writable location nothing may load from (repeatable; required with --trusted-root)")
    parser.add_argument("--expected-executable", default=None, help="exact pinned interpreter path (required with --trusted-root)")
    args = parser.parse_args(argv)
    try:
        if args.verify_package:
            if not args.commit:
                raise errors.PackageIntegrityFailure("--commit is required with --verify-package")
            files = c3_package.scan_tree(args.verify_package[0], keep_bytes=True)
            with open(args.verify_package[1], "r", encoding="utf-8", newline="") as fh:
                listing = fh.read()
            manifest = c3_package.build_manifest(files, source_commit=args.commit, tree_listing=listing)
            print(json.dumps({"manifest_sha256": manifest.digest(), "files": len(manifest.files)}, sort_keys=True))
            return 0
        if args.trusted_root:
            if not args.agent_writable_root or not args.expected_executable:
                raise errors.RuntimeUntrusted("--trusted-root needs --agent-writable-root and --expected-executable")
            try:
                policy = c3_runtime.RuntimePolicy(
                    platform="nt" if os.name == "nt" else "posix", trusted_root=args.trusted_root,
                    agent_writable_roots=tuple(args.agent_writable_root), expected_executable=args.expected_executable,
                )
            except ValueError as exc:
                raise errors.RuntimeUntrusted(f"runtime policy rejected: {exc}") from None
            c3_runtime.verify_execution_environment(c3_runtime.capture_environment(), policy)
            # Environment checks only: binary provenance is NOT established here.
            print(json.dumps({"runtime_environment": "consistent", "binary_provenance": "NOT_VERIFIED_BY_THIS_COMMAND"}))
            return 0
        if args.phase == "PLAN":
            print(json.dumps(_plan_document(), indent=2, sort_keys=True))
            return 0
        raise errors.ApprovalInvalid("phases READONLY and NEGATIVE are not runnable in G0 (separate approval required)")
    except errors.OrchestratorStop as stop:
        print(f"STOP: {stop.reason_code}: {stop.detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
