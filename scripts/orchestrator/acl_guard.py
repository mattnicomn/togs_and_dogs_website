"""G1.6-B: OS-level approval-boundary enforcement (offline, read-only, pure).

Why this exists
---------------
Owner approval is only meaningful if the identity that RUNS the orchestrator
(the "agent") cannot create, modify, replace, re-own or re-ACL the approval
source. A file-location check alone cannot prove that. This module evaluates a
*snapshot of OS security descriptors* and fails closed unless the boundary is
positively proven.

What it checks (Windows model; the evaluation is platform-independent and takes
data, so it is fully testable with mocked security descriptors on Linux CI):

  chain = manifest file -> (dirs up to) approvals dir -> every ancestor -> root

  * No node is a reparse point (symlink / junction / mount point).
  * Every node has a readable, non-NULL DACL and a known owner; any ACE type
    this guard does not understand is "unreadable" (never guessed).
  * TARGET nodes (manifest, approvals dir and anything between them):
      - owner is a configured trusted owner SID and is NOT the agent (an owner
        holds implicit WRITE_DAC, so an agent-owned node is never protected,
        even when its DACL looks read-only);
      - the agent's effective ALLOW rights contain none of: add file/subdir,
        write EA/attributes, DELETE_CHILD, DELETE, WRITE_DAC, WRITE_OWNER,
        GENERIC_WRITE, GENERIC_ALL. "Agent" means the user SID plus every
        enabled token group (so broad Users / Authenticated Users / Everyone
        grants and inherited ACEs are caught).
  * ANCESTORS: owner is trusted or a well-known system principal and is not the
    agent, and the agent holds no DELETE_CHILD / DELETE / WRITE_DAC /
    WRITE_OWNER / GENERIC_ALL there. (DELETE_CHILD on a parent lets an agent
    rename or replace the whole protected tree.)
  * The agent identity must be distinct from every trusted owner and must not
    be administrator-capable (Administrators present, even deny-only, means the
    process can elevate or take ownership).

DENY ACEs are deliberately ignored (conservative: a deny is never relied on to
cancel a grant) and inherit-only ACEs are skipped (they do not apply to the
object itself).

POSIX has a separate, simpler model (mode bits, uid, sticky bit, symlinks).

Nothing here changes any ACL, account or credential; it only reads descriptors via
a :class:`SecurityBackend`. The Windows backend lives in ``acl_windows`` and is
imported lazily.
"""

from __future__ import annotations

import ntpath
import os
import posixpath
import re
import stat
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from . import errors

# --- access-mask constants (winnt.h) ----------------------------------------

FILE_WRITE_DATA = 0x00000002  # add file (directory) / write data (file)
FILE_APPEND_DATA = 0x00000004  # add subdirectory / append
FILE_WRITE_EA = 0x00000010
FILE_DELETE_CHILD = 0x00000040
FILE_WRITE_ATTRIBUTES = 0x00000100
DELETE = 0x00010000
WRITE_DAC = 0x00040000
WRITE_OWNER = 0x00080000
GENERIC_ALL = 0x10000000
GENERIC_WRITE = 0x40000000

DANGEROUS_TARGET = (
    FILE_WRITE_DATA | FILE_APPEND_DATA | FILE_WRITE_EA | FILE_DELETE_CHILD
    | FILE_WRITE_ATTRIBUTES | DELETE | WRITE_DAC | WRITE_OWNER | GENERIC_WRITE | GENERIC_ALL
)
DANGEROUS_ANCESTOR = FILE_DELETE_CHILD | DELETE | WRITE_DAC | WRITE_OWNER | GENERIC_ALL

_RIGHT_NAMES = (
    (FILE_WRITE_DATA, "WRITE_DATA/ADD_FILE"),
    (FILE_APPEND_DATA, "APPEND_DATA/ADD_SUBDIR"),
    (FILE_WRITE_EA, "WRITE_EA"),
    (FILE_DELETE_CHILD, "DELETE_CHILD"),
    (FILE_WRITE_ATTRIBUTES, "WRITE_ATTRIBUTES"),
    (DELETE, "DELETE"),
    (WRITE_DAC, "WRITE_DAC"),
    (WRITE_OWNER, "WRITE_OWNER"),
    (GENERIC_WRITE, "GENERIC_WRITE"),
    (GENERIC_ALL, "GENERIC_ALL"),
)

# --- well-known SIDs ---------------------------------------------------------

SID_SYSTEM = "S-1-5-18"
SID_ADMINISTRATORS = "S-1-5-32-544"
SID_TRUSTED_INSTALLER = "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464"
DEFAULT_ANCESTOR_OWNER_SIDS = frozenset({SID_SYSTEM, SID_ADMINISTRATORS, SID_TRUSTED_INSTALLER})

_SID_RE = re.compile(r"^S-1-\d+(-\d+){1,15}$")

MODE_ENFORCED = "ENFORCED"
MODE_OFFLINE_FIXTURE = "OFFLINE_FIXTURE_UNENFORCED"


class AclUnreadable(Exception):
    """A descriptor or identity could not be read or understood. Converted by
    the guard into :class:`errors.ApprovalBoundaryUnverifiable`."""


# --- data model --------------------------------------------------------------


@dataclass(frozen=True)
class Ace:
    sid: str
    mask: int
    allow: bool = True
    inherited: bool = False
    inherit_only: bool = False


@dataclass(frozen=True)
class NodeSecurity:
    path: str
    owner: str | None
    aces: tuple[Ace, ...]
    dacl_present: bool = True
    is_reparse: bool = False
    is_dir: bool = False


@dataclass(frozen=True)
class Identity:
    user_sid: str
    group_sids: frozenset[str] = frozenset()
    deny_only_group_sids: frozenset[str] = frozenset()

    @property
    def effective_ids(self) -> frozenset[str]:
        return frozenset({self.user_sid}) | self.group_sids

    @property
    def all_ids(self) -> frozenset[str]:
        return self.effective_ids | self.deny_only_group_sids


@dataclass(frozen=True)
class PosixNode:
    path: str
    uid: int
    mode: int
    is_symlink: bool = False
    is_dir: bool = False


@runtime_checkable
class SecurityBackend(Protocol):
    platform: str  # "nt" or "posix"

    def current_identity(self) -> Any: ...

    def read_node(self, path: str) -> Any: ...


@dataclass(frozen=True)
class BoundaryPolicy:
    """Owner-supplied trust configuration. Nothing is defaulted permissively:
    the trusted owners must be named explicitly."""

    trusted_owner_sids: frozenset[str] = frozenset()
    trusted_owner_uids: frozenset[int] = frozenset()
    ancestor_owner_sids: frozenset[str] = DEFAULT_ANCESTOR_OWNER_SIDS

    def __post_init__(self) -> None:
        for sid in (*self.trusted_owner_sids, *self.ancestor_owner_sids):
            if not isinstance(sid, str) or not _SID_RE.match(sid):
                raise ValueError("invalid SID in boundary policy")
        for uid in self.trusted_owner_uids:
            if isinstance(uid, bool) or not isinstance(uid, int) or uid < 0:
                raise ValueError("invalid uid in boundary policy")


@dataclass(frozen=True)
class BoundaryReport:
    mode: str
    platform: str
    enforced: bool
    nodes_checked: int = 0
    agent: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "platform": self.platform,
            "enforced": self.enforced,
            "nodes_checked": self.nodes_checked,
            "agent": self.agent,
        }


# --- helpers ------------------------------------------------------------------


def short_sid(sid: str | None) -> str:
    """Shorten long domain/machine SIDs so messages stay compact."""

    if not sid:
        return "<none>"
    parts = sid.split("-")
    if len(parts) >= 6:
        return "-".join(parts[:4]) + "-...-" + parts[-1]
    return sid


def rights_names(mask: int) -> str:
    return "|".join(name for bit, name in _RIGHT_NAMES if mask & bit) or "none"


def _effective_allow_mask(node: NodeSecurity, ids: frozenset[str]) -> int:
    mask = 0
    for ace in node.aces:
        if ace.allow and not ace.inherit_only and ace.sid in ids:
            mask |= ace.mask
    return mask


_WIN_ABS_RE = re.compile(r"^[A-Za-z]:\\")


def _pathmod(platform: str):
    return ntpath if platform == "nt" else posixpath


def _norm(pm: Any, platform: str, path: str) -> str:
    out = pm.normpath(path)
    return pm.normcase(out) if platform == "nt" else out


def _parents(pm: Any, path: str) -> list[str]:
    chain = [path]
    while True:
        parent = pm.dirname(chain[-1])
        if not parent or parent == chain[-1]:
            return chain
        chain.append(parent)


# --- the evaluation -----------------------------------------------------------


class _Findings:
    def __init__(self) -> None:
        self.violations: list[str] = []
        self.unverifiable: list[str] = []

    def violate(self, msg: str) -> None:
        self.violations.append(msg)

    def unverified(self, msg: str) -> None:
        self.unverifiable.append(msg)

    def raise_if_any(self) -> None:
        if self.violations:
            raise errors.ApprovalBoundaryViolation("; ".join(self.violations[:6]))
        if self.unverifiable:
            raise errors.ApprovalBoundaryUnverifiable("; ".join(self.unverifiable[:6]))


def _verify_windows(
    backend: SecurityBackend,
    policy: BoundaryPolicy,
    manifest_path: str | None,
    approvals_dir: str,
    findings: _Findings,
) -> tuple[int, str]:
    pm = ntpath
    trusted = policy.trusted_owner_sids
    if not trusted:
        raise errors.ApprovalBoundaryUnverifiable("no trusted owner SID is configured")

    try:
        ident = backend.current_identity()
    except AclUnreadable as exc:
        raise errors.ApprovalBoundaryUnverifiable(f"agent identity unreadable: {exc}") from exc
    if not isinstance(ident, Identity):
        raise errors.ApprovalBoundaryUnverifiable("agent identity has an unexpected type")

    agent = short_sid(ident.user_sid)
    agent_ids = ident.effective_ids

    # Identity distinctness.
    if ident.all_ids & trusted:
        findings.violate(
            "agent identity is, or is a member of, a trusted owner principal "
            "(owner and agent are not distinct)"
        )
    if SID_ADMINISTRATORS in ident.all_ids or ident.all_ids & policy.ancestor_owner_sids:
        findings.violate("agent is administrator/system-capable and could take ownership or elevate")

    # Path containment + chain.
    for label, raw in (("approvals dir", approvals_dir), ("manifest", manifest_path)):
        if raw is None:
            continue
        if not _WIN_ABS_RE.match(pm.normpath(raw)) or raw.startswith(("\\\\", "//")):
            findings.violate(f"{label} path is not a local absolute drive path")
    if findings.violations and any("not a local absolute" in v for v in findings.violations):
        return 0, agent

    appr = pm.normpath(approvals_dir)
    chain_targets: list[str] = []
    if manifest_path is not None:
        mp = pm.normpath(manifest_path)
        if _norm(pm, "nt", mp) == _norm(pm, "nt", appr) or not _norm(pm, "nt", mp).startswith(
            _norm(pm, "nt", appr).rstrip("\\") + "\\"
        ):
            findings.violate("manifest is not contained within the approvals dir")
            return 0, agent
        node = mp
        while _norm(pm, "nt", node) != _norm(pm, "nt", appr):
            chain_targets.append(node)
            node = pm.dirname(node)
    chain_targets.append(appr)
    ancestors = _parents(pm, appr)[1:]

    checked = 0
    for path in chain_targets + ancestors:
        is_target = path in chain_targets
        try:
            node = backend.read_node(path)
        except AclUnreadable as exc:
            findings.unverified(f"{path}: unreadable ({exc})")
            continue
        if not isinstance(node, NodeSecurity):
            findings.unverified(f"{path}: unexpected descriptor type")
            continue
        checked += 1
        if node.is_reparse:
            findings.violate(f"{path}: is a reparse point (symlink/junction/mount)")
        if not node.dacl_present:
            findings.unverified(f"{path}: NULL DACL (access is not restricted)")
            continue
        if not node.owner:
            findings.unverified(f"{path}: owner unknown")
            continue
        allowed_owners = trusted if is_target else (trusted | policy.ancestor_owner_sids)
        if node.owner in agent_ids or node.owner == ident.user_sid:
            findings.violate(f"{path}: owned by the agent identity ({short_sid(node.owner)})")
        elif node.owner not in allowed_owners:
            findings.violate(f"{path}: owner {short_sid(node.owner)} is not a trusted owner")
        mask = _effective_allow_mask(node, agent_ids)
        bad = mask & (DANGEROUS_TARGET if is_target else DANGEROUS_ANCESTOR)
        if bad:
            findings.violate(f"{path}: agent holds {rights_names(bad)}")
    return checked, agent


def _verify_posix(
    backend: SecurityBackend,
    policy: BoundaryPolicy,
    manifest_path: str | None,
    approvals_dir: str,
    findings: _Findings,
) -> tuple[int, str]:
    pm = posixpath
    ident = backend.current_identity()
    euid = ident if isinstance(ident, int) and not isinstance(ident, bool) else None
    if euid is None:
        raise errors.ApprovalBoundaryUnverifiable("agent uid unreadable")
    agent = f"uid:{euid}"
    if euid == 0:
        findings.violate("agent runs as root and bypasses file permissions")
    if not policy.trusted_owner_uids:
        raise errors.ApprovalBoundaryUnverifiable("no trusted owner uid is configured")
    if euid in policy.trusted_owner_uids:
        findings.violate("agent identity is a trusted owner (owner and agent are not distinct)")

    for label, raw in (("approvals dir", approvals_dir), ("manifest", manifest_path)):
        if raw is not None and not pm.isabs(raw):
            findings.violate(f"{label} path is not absolute")
    if findings.violations and any("not absolute" in v for v in findings.violations):
        return 0, agent

    appr = pm.normpath(approvals_dir)
    targets: list[str] = []
    if manifest_path is not None:
        mp = pm.normpath(manifest_path)
        if mp == appr or not mp.startswith(appr.rstrip("/") + "/"):
            findings.violate("manifest is not contained within the approvals dir")
            return 0, agent
        node = mp
        while node != appr:
            targets.append(node)
            node = pm.dirname(node)
    targets.append(appr)
    ancestors = _parents(pm, appr)[1:]
    allowed_ancestor_uids = set(policy.trusted_owner_uids) | {0}

    checked = 0
    for path in targets + ancestors:
        is_target = path in targets
        try:
            node = backend.read_node(path)
        except AclUnreadable as exc:
            findings.unverified(f"{path}: unreadable ({exc})")
            continue
        if not isinstance(node, PosixNode):
            findings.unverified(f"{path}: unexpected descriptor type")
            continue
        checked += 1
        if node.is_symlink:
            findings.violate(f"{path}: is a symlink")
        if node.uid == euid:
            findings.violate(f"{path}: owned by the agent uid")
        elif is_target and node.uid not in policy.trusted_owner_uids:
            findings.violate(f"{path}: owner uid {node.uid} is not a trusted owner")
        elif not is_target and node.uid not in allowed_ancestor_uids:
            findings.violate(f"{path}: owner uid {node.uid} is not trusted")
        writable_others = node.mode & 0o022
        if is_target and writable_others:
            findings.violate(f"{path}: group/other-writable (mode {oct(node.mode & 0o7777)})")
        elif not is_target and writable_others and not (node.mode & stat.S_ISVTX):
            findings.violate(
                f"{path}: group/other-writable ancestor without sticky bit (mode {oct(node.mode & 0o7777)})"
            )
    return checked, agent


def verify_boundary(
    backend: SecurityBackend,
    policy: BoundaryPolicy,
    manifest_path: "str | os.PathLike[str] | None",
    approvals_dir: "str | os.PathLike[str]",
) -> BoundaryReport:
    """Evaluate the approval boundary. Raises a typed stop unless PROVEN."""

    mp = os.fspath(manifest_path) if manifest_path is not None else None
    ad = os.fspath(approvals_dir)
    findings = _Findings()
    platform = getattr(backend, "platform", None)
    try:
        if platform == "nt":
            checked, agent = _verify_windows(backend, policy, mp, ad, findings)
        elif platform == "posix":
            checked, agent = _verify_posix(backend, policy, mp, ad, findings)
        else:
            raise errors.ApprovalBoundaryUnverifiable("unsupported platform for boundary verification")
    except AclUnreadable as exc:
        raise errors.ApprovalBoundaryUnverifiable(f"security descriptor unreadable: {exc}") from exc
    findings.raise_if_any()
    return BoundaryReport(MODE_ENFORCED, platform, True, checked, agent)


# --- POSIX backend (real) -------------------------------------------------------


class PosixSecurityBackend:
    platform = "posix"

    def current_identity(self) -> int:
        try:
            return os.geteuid()  # type: ignore[attr-defined]
        except AttributeError as exc:  # pragma: no cover - not POSIX
            raise AclUnreadable("geteuid unavailable") from exc

    def read_node(self, path: str) -> PosixNode:
        try:
            st = os.lstat(path)
        except OSError as exc:
            raise AclUnreadable(exc.__class__.__name__) from exc
        return PosixNode(
            path=path,
            uid=st.st_uid,
            mode=st.st_mode,
            is_symlink=stat.S_ISLNK(st.st_mode),
            is_dir=stat.S_ISDIR(st.st_mode),
        )


def default_backend() -> SecurityBackend:
    if os.name == "nt":
        from .acl_windows import WindowsSecurityBackend  # lazy: ctypes, Windows only

        return WindowsSecurityBackend()
    return PosixSecurityBackend()


# --- guards ----------------------------------------------------------------------


@runtime_checkable
class ApprovalGuard(Protocol):
    mode: str
    offline_only: bool

    def verify(self, manifest_path: Any, approvals_dir: Any) -> BoundaryReport: ...


class ProductionApprovalGuard:
    """ENFORCED: proves the OS approval boundary or raises a typed stop."""

    mode = MODE_ENFORCED
    offline_only = False

    def __init__(self, policy: BoundaryPolicy, backend: SecurityBackend | None = None) -> None:
        if not isinstance(policy, BoundaryPolicy):
            raise TypeError("policy must be a BoundaryPolicy")
        self._policy = policy
        self._backend = backend

    def verify(self, manifest_path: Any, approvals_dir: Any) -> BoundaryReport:
        backend = self._backend if self._backend is not None else default_backend()
        return verify_boundary(backend, self._policy, manifest_path, approvals_dir)


class OfflineFixtureApprovalGuard:
    """Offline fixtures ONLY. Performs NO OS check and is therefore refused by
    the runner unless every adapter is an offline fixture/mock. It can never be
    used for production authorization."""

    mode = MODE_OFFLINE_FIXTURE
    offline_only = True

    def verify(self, manifest_path: Any, approvals_dir: Any) -> BoundaryReport:
        return BoundaryReport(MODE_OFFLINE_FIXTURE, "n/a", False, 0, "n/a")
