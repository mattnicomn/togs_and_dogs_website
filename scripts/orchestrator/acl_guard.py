"""OS-level approval-boundary enforcement (offline, read-only; G1.6-B + G1.6-C2).

Why this exists
---------------
Owner approval is only meaningful if the identity that RUNS the orchestrator
(the "agent") cannot create, modify, replace, re-own or re-ACL the approval
source. A file-location check alone cannot prove that. This module evaluates a
*snapshot of OS security data* and fails closed unless the boundary is
positively proven. The evaluation is platform-independent and takes data, so it
is fully testable with mocked descriptors on Linux CI.

What it checks (Windows model)
------------------------------
  chain = manifest file -> (dirs up to) approvals dir -> every ancestor -> root

  * PATH FORM (C2): only plain local drive paths are accepted. Alternate data
    streams / any colon beyond the drive, device and extended-length prefixes,
    UNC, relative and drive-relative paths, dot segments, trailing dots/spaces,
    reserved device names, wildcard characters and 8.3 short-name aliases are
    rejected rather than silently normalized.
  * VOLUME BINDING (C2): the approvals path must live directly on a drive-letter
    volume whose identity (volume GUID, plus serial/label/filesystem and the
    file-backed-virtual bus type when configured) matches an owner-configured
    trusted volume, with no ``subst``/redirected mapping, no mount-point hop and
    a fixed drive type. A drive letter or label alone is never trusted.
  * EXECUTING IDENTITY (C2): the process token is the agent. It must equal the
    owner-configured expected agent SID, be distinct from every trusted owner,
    not be administrator/system-capable, run below high integrity, and hold no
    dangerous or unexpected privileges (enabled OR disabled - a disabled
    privilege can be enabled by the process). Privilege state that cannot be
    read is "unverifiable": it is never inferred from group membership.
  * No node is a reparse point; every node has a readable, non-NULL DACL and a
    known owner; unsupported ACE types are "unreadable".
  * TARGET nodes (manifest, approvals dir and anything between): owner is a
    trusted owner and NOT the agent (an owner holds implicit WRITE_DAC); the
    agent's effective ALLOW rights contain none of: add file/subdir, write
    EA/attributes, DELETE_CHILD, DELETE, WRITE_DAC, WRITE_OWNER,
    GENERIC_WRITE, GENERIC_ALL.
  * ANCESTORS: owner trusted or a well-known system principal and not the
    agent; the agent holds no DELETE_CHILD / DELETE / WRITE_DAC / WRITE_OWNER /
    GENERIC_ALL. EXCEPTION (C2, narrow): DELETE on the VOLUME ROOT itself is
    ignored. A volume root has no parent directory and cannot be deleted or
    renamed, so DELETE there grants nothing; DELETE_CHILD, WRITE_DAC,
    WRITE_OWNER and GENERIC_ALL on the root remain fatal, and DELETE on every
    non-root ancestor and on every target remains fatal.

DENY ACEs are ignored (conservative); inherit-only ACEs are skipped.

File identity / TOCTOU (C2)
---------------------------
:func:`read_pinned_approval` opens the approval file ONCE on a stable handle that
denies concurrent writers/deleters (Windows share mode) or on a verified inode
(POSIX), checks identity, hard-link count, reparse state, the OS-reported final
path and the security descriptor *of the open handle*, reads the bytes from that
handle, re-checks identity, and re-runs the chain check. The manifest is then
parsed from those bytes - the path is never re-opened. The runner revalidates the
pinned snapshot before every run.

Nothing here changes any ACL, account or credential; it only reads. The
Windows backend lives in ``acl_windows`` and is imported lazily.
"""

from __future__ import annotations

import hashlib
import ntpath
import os
import posixpath
import re
import stat
from dataclasses import dataclass, replace
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

# --- token privileges --------------------------------------------------------

# Privileges that bypass or subvert DACL checks, or confer SYSTEM-level reach.
DANGEROUS_PRIVILEGES = frozenset({
    "SeBackupPrivilege", "SeRestorePrivilege", "SeTakeOwnershipPrivilege",
    "SeDebugPrivilege", "SeTcbPrivilege", "SeCreateTokenPrivilege",
    "SeLoadDriverPrivilege", "SeManageVolumePrivilege", "SeAssignPrimaryTokenPrivilege",
    "SeImpersonatePrivilege", "SeRelabelPrivilege", "SeSecurityPrivilege",
    "SeSyncAgentPrivilege", "SeEnableDelegationPrivilege", "SeTrustedCredManAccessPrivilege",
    "SeSystemEnvironmentPrivilege", "SeAuditPrivilege", "SeCreatePermanentPrivilege",
})
# The privileges a default standard-user token holds. Anything else is
# "unexpected" and fails closed.
BENIGN_PRIVILEGES = frozenset({
    "SeChangeNotifyPrivilege", "SeShutdownPrivilege", "SeUndockPrivilege",
    "SeIncreaseWorkingSetPrivilege", "SeTimeZonePrivilege",
})
INTEGRITY_HIGH = 0x3000  # S-1-16-12288; the agent must run below this

# --- well-known SIDs ---------------------------------------------------------

SID_SYSTEM = "S-1-5-18"
SID_ADMINISTRATORS = "S-1-5-32-544"
SID_TRUSTED_INSTALLER = "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464"
DEFAULT_ANCESTOR_OWNER_SIDS = frozenset({SID_SYSTEM, SID_ADMINISTRATORS, SID_TRUSTED_INSTALLER})

_SID_RE = re.compile(r"^S-1-\d+(-\d+){1,15}$")
_GUID_PATH_RE = re.compile(r"^\\\\\?\\Volume\{[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\}\\$")
_DEVICE_RE = re.compile(r"^\\Device\\HarddiskVolume\d+$")

DRIVE_FIXED = 3
BUS_FILE_BACKED_VIRTUAL = 15  # STORAGE_BUS_TYPE::BusTypeFileBackedVirtual
MAX_APPROVAL_BYTES = 1_048_576

MODE_ENFORCED = "ENFORCED"
MODE_OFFLINE_FIXTURE = "OFFLINE_FIXTURE_UNENFORCED"
MODE_OFFLINE_MOCKED = "OFFLINE_MOCKED_DESCRIPTORS"


class AclUnreadable(Exception):
    """A descriptor, token or volume fact could not be read or understood.
    Converted by the guard into :class:`errors.ApprovalBoundaryUnverifiable`."""


class PathRejected(Exception):
    """A path form is unsafe or ambiguous (converted to a boundary violation)."""


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
class Privilege:
    name: str
    enabled: bool
    enabled_by_default: bool = False
    removed: bool = False


@dataclass(frozen=True)
class Identity:
    user_sid: str
    group_sids: frozenset[str] = frozenset()
    deny_only_group_sids: frozenset[str] = frozenset()
    # None means "could not be read" (unverifiable) - never "assume none".
    privileges: tuple[Privilege, ...] | None = None
    integrity_rid: int | None = None

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


@dataclass(frozen=True)
class VolumeInfo:
    """Facts about the volume behind a drive-letter path (all read-only)."""

    mount_root: str          # GetVolumePathName result, e.g. "P:\\"
    dos_target: str          # QueryDosDevice("P:") first target
    volume_guid: str         # "\\\\?\\Volume{...}\\"
    drive_type: int          # GetDriveType (3 = fixed)
    filesystem: str
    label: str
    serial: int
    bus_type: int | None = None   # STORAGE_BUS_TYPE, None if unreadable
    vendor: str = ""
    product: str = ""


@dataclass(frozen=True)
class VolumeBinding:
    """Owner-configured identity of the one trusted approval volume."""

    volume_guid: str
    filesystem: str = "NTFS"
    label: str | None = None
    serial: int | None = None
    require_file_backed_virtual: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.volume_guid, str) or not _GUID_PATH_RE.match(self.volume_guid):
            raise ValueError("volume_guid must look like \\\\?\\Volume{GUID}\\")
        if self.serial is not None and (isinstance(self.serial, bool) or not isinstance(self.serial, int) or self.serial < 0):
            raise ValueError("serial must be a non-negative integer")


@dataclass(frozen=True)
class FileIdentity:
    volume_serial: int   # st_dev on POSIX
    file_index: int      # st_ino
    size: int
    mtime_ns: int
    nlinks: int


@runtime_checkable
class PinnedFile(Protocol):
    identity: FileIdentity
    final_path: str
    is_reparse: bool

    def node(self) -> Any: ...

    def read_all(self, max_bytes: int) -> bytes: ...

    def current_identity(self) -> FileIdentity: ...

    def path_matches(self) -> bool: ...

    def close(self) -> None: ...


@runtime_checkable
class SecurityBackend(Protocol):
    platform: str  # "nt" or "posix"

    def current_identity(self) -> Any: ...

    def read_node(self, path: str) -> Any: ...


@dataclass(frozen=True)
class BoundaryPolicy:
    """Owner-supplied trust configuration. Nothing is defaulted permissively."""

    trusted_owner_sids: frozenset[str] = frozenset()
    trusted_owner_uids: frozenset[int] = frozenset()
    ancestor_owner_sids: frozenset[str] = DEFAULT_ANCESTOR_OWNER_SIDS
    expected_agent_sid: str | None = None
    expected_agent_uid: int | None = None
    trusted_volumes: tuple[VolumeBinding, ...] = ()
    privilege_allowlist: frozenset[str] = BENIGN_PRIVILEGES

    def __post_init__(self) -> None:
        sids = [*self.trusted_owner_sids, *self.ancestor_owner_sids]
        if self.expected_agent_sid is not None:
            sids.append(self.expected_agent_sid)
        for sid in sids:
            if not isinstance(sid, str) or not _SID_RE.match(sid):
                raise ValueError("invalid SID in boundary policy")
        for uid in (*self.trusted_owner_uids, *([self.expected_agent_uid] if self.expected_agent_uid is not None else [])):
            if isinstance(uid, bool) or not isinstance(uid, int) or uid < 0:
                raise ValueError("invalid uid in boundary policy")
        for vol in self.trusted_volumes:
            if not isinstance(vol, VolumeBinding):
                raise ValueError("trusted_volumes must contain VolumeBinding objects")
        for name in self.privilege_allowlist:
            if name in DANGEROUS_PRIVILEGES:
                raise ValueError("a dangerous privilege can never be allow-listed")


@dataclass(frozen=True)
class BoundaryReport:
    mode: str
    platform: str
    enforced: bool
    nodes_checked: int = 0
    agent: str = ""
    volume: str = ""
    pinned: bool = False
    # Digest of every chain descriptor that was evaluated (owner, DACL, reparse state).
    # Deliberately NOT in to_dict(): it is compared between two passes, not reported.
    chain_digest: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "platform": self.platform,
            "enforced": self.enforced,
            "nodes_checked": self.nodes_checked,
            "agent": self.agent,
            "volume": self.volume,
            "pinned": self.pinned,
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


_WIN_DRIVE_RE = re.compile(r"^([A-Za-z]):\\(.*)$")
_WIN_RESERVED_RE = re.compile(r"^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(\..*)?$", re.IGNORECASE)
_WIN_BAD_CHARS = frozenset('<>"|?*')
_SHORT_NAME_RE = re.compile(r"~\d")


def canonical_windows_path(raw: Any) -> str:
    """Return a safe canonical local drive path or raise :class:`PathRejected`.

    Deliberately strict: anything that Windows would silently reinterpret
    (stream suffixes, trailing dots/spaces, 8.3 aliases, dot segments, device /
    extended-length / UNC prefixes) is rejected instead of normalized.
    """

    if not isinstance(raw, str) or not raw:
        raise PathRejected("empty or non-text path")
    if any(ord(c) < 32 for c in raw):
        raise PathRejected("control character in path")
    p = raw.replace("/", "\\")
    if p.startswith("\\\\"):
        raise PathRejected("UNC, device or extended-length path form")
    m = _WIN_DRIVE_RE.match(p)
    if not m:
        raise PathRejected("not an absolute local drive path (relative or drive-relative form)")
    rest = m.group(2)
    if ":" in rest:
        raise PathRejected("colon after the drive spec (alternate data stream or ambiguous form)")
    parts: list[str] = []
    for comp in rest.split("\\"):
        if comp == "":
            continue  # duplicate separators collapse; the result is re-checked below
        if comp in (".", ".."):
            raise PathRejected("dot segment")
        if comp != comp.rstrip(". "):
            raise PathRejected("trailing dot or space in a path component")
        if any(c in _WIN_BAD_CHARS for c in comp):
            raise PathRejected("wildcard or reserved character in path")
        if _WIN_RESERVED_RE.match(comp):
            raise PathRejected("reserved device name in path")
        if _SHORT_NAME_RE.search(comp):
            raise PathRejected("possible 8.3 short-name alias")
        parts.append(comp)
    return m.group(1).upper() + ":\\" + "\\".join(parts)


def canonical_posix_path(raw: Any) -> str:
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise PathRejected("empty path or NUL byte")
    if not raw.startswith("/"):
        raise PathRejected("not an absolute path")
    if any(seg in (".", "..") for seg in raw.split("/")):
        raise PathRejected("dot segment")
    return posixpath.normpath(raw)


def _pathmod(platform: str):
    return ntpath if platform == "nt" else posixpath


def _norm(platform: str, path: str) -> str:
    return ntpath.normcase(path) if platform == "nt" else path


def _parents(pm: Any, path: str) -> list[str]:
    chain = [path]
    while True:
        parent = pm.dirname(chain[-1])
        if not parent or parent == chain[-1]:
            return chain
        chain.append(parent)


# --- the evaluation -----------------------------------------------------------


VIOLATION_AGENT_RIGHTS = "AGENT_RIGHTS"
VIOLATION_OTHER = "OTHER"


class _Findings:
    def __init__(self) -> None:
        self.violations: list[str] = []
        self.unverifiable: list[str] = []
        # Structured (code, path) for EVERY violation, never truncated. Only the
        # agent-rights denial has its own code; everything else is OTHER.
        self.codes: list[tuple[str, str]] = []

    def violate(self, msg: str, *, code: str = VIOLATION_OTHER, path: str = "") -> None:
        self.violations.append(msg)
        self.codes.append((code, path))

    def unverified(self, msg: str) -> None:
        self.unverifiable.append(msg)

    def raise_if_any(self) -> None:
        if self.violations:
            exc = errors.ApprovalBoundaryViolation("; ".join(self.violations[:6]))
            exc.violation_codes = tuple(self.codes)  # type: ignore[attr-defined]
            exc.unverified_count = len(self.unverifiable)  # type: ignore[attr-defined]
            raise exc
        if self.unverifiable:
            raise errors.ApprovalBoundaryUnverifiable("; ".join(self.unverifiable[:6]))


def _check_identity_windows(ident: Identity, policy: BoundaryPolicy, findings: _Findings) -> None:
    trusted = policy.trusted_owner_sids
    if ident.user_sid != policy.expected_agent_sid:
        findings.violate("executing token is not the expected agent identity")
    if ident.all_ids & trusted:
        findings.violate(
            "agent identity is, or is a member of, a trusted owner principal "
            "(owner and agent are not distinct)"
        )
    if SID_ADMINISTRATORS in ident.all_ids or ident.all_ids & policy.ancestor_owner_sids:
        findings.violate("agent is administrator/system-capable and could take ownership or elevate")
    if ident.privileges is None:
        findings.unverified("token privileges could not be read (never inferred from group membership)")
    else:
        for priv in ident.privileges:
            if priv.removed:
                continue
            state = "enabled" if priv.enabled else "disabled but can be enabled by the process"
            if priv.name.startswith("LUID:") or not priv.name:
                findings.unverified("a token privilege could not be named")
            elif priv.name in DANGEROUS_PRIVILEGES:
                findings.violate(f"token holds {priv.name} ({state})")
            elif priv.name not in policy.privilege_allowlist:
                findings.violate(f"token holds unexpected privilege {priv.name} ({state})")
    if ident.integrity_rid is None:
        findings.unverified("token integrity level could not be read")
    elif ident.integrity_rid >= INTEGRITY_HIGH:
        findings.violate("agent runs at high/system integrity")


def _check_volume(backend: Any, policy: BoundaryPolicy, appr: str, findings: _Findings) -> str:
    """Bind the approvals path to the owner-configured trusted volume."""

    fn = getattr(backend, "volume_info", None)
    if fn is None:
        findings.unverified("volume identity cannot be read by this backend")
        return ""
    try:
        info = fn(appr)
    except AclUnreadable as exc:
        findings.unverified(f"volume identity unreadable ({exc})")
        return ""
    if not isinstance(info, VolumeInfo):
        findings.unverified("volume identity has an unexpected type")
        return ""
    short = (info.volume_guid or "")[11:19] if info.volume_guid else ""
    if ntpath.normcase(info.mount_root) != ntpath.normcase(appr[:3]):
        findings.violate("approvals path is not on the drive-letter volume itself (mount-point or redirected path)")
    if not _DEVICE_RE.match(info.dos_target or ""):
        findings.violate("drive letter is substituted, redirected or not a local volume device")
    if info.drive_type != DRIVE_FIXED:
        findings.violate("drive is not a fixed local volume")
    binding = next(
        (b for b in policy.trusted_volumes if b.volume_guid.lower() == (info.volume_guid or "").lower()),
        None,
    )
    if binding is None:
        findings.violate("volume identity is not a trusted volume")
        return short
    if info.filesystem.upper() != binding.filesystem.upper():
        findings.violate("trusted volume has an unexpected filesystem")
    if binding.label is not None and info.label != binding.label:
        findings.violate("trusted volume label does not match")
    if binding.serial is not None and info.serial != binding.serial:
        findings.violate("trusted volume serial number does not match")
    if binding.require_file_backed_virtual:
        if info.bus_type is None:
            findings.unverified("volume bus type could not be read")
        elif info.bus_type != BUS_FILE_BACKED_VIRTUAL:
            findings.violate("trusted volume is not a file-backed virtual disk")
    return short


def _eval_windows_node(
    findings: _Findings, path: str, node: Any, *, is_target: bool, is_root: bool,
    policy: BoundaryPolicy, ident: Identity,
) -> None:
    if not isinstance(node, NodeSecurity):
        findings.unverified(f"{path}: unexpected descriptor type")
        return
    agent_ids = ident.effective_ids
    if node.is_reparse:
        findings.violate(f"{path}: is a reparse point (symlink/junction/mount)")
    if not node.dacl_present:
        findings.unverified(f"{path}: NULL DACL (access is not restricted)")
        return
    if not node.owner:
        findings.unverified(f"{path}: owner unknown")
        return
    trusted = policy.trusted_owner_sids
    allowed_owners = trusted if is_target else (trusted | policy.ancestor_owner_sids)
    if node.owner in agent_ids or node.owner == ident.user_sid:
        findings.violate(f"{path}: owned by the agent identity ({short_sid(node.owner)})")
    elif node.owner not in allowed_owners:
        findings.violate(f"{path}: owner {short_sid(node.owner)} is not a trusted owner")
    mask = _effective_allow_mask(node, agent_ids)
    dangerous = DANGEROUS_TARGET if is_target else DANGEROUS_ANCESTOR
    if is_root and not is_target:
        # Narrow C2 exception: a volume root cannot be deleted or renamed, so
        # DELETE on it is inert. Everything else stays fatal.
        dangerous &= ~DELETE
    bad = mask & dangerous
    if bad:
        findings.violate(f"{path}: agent holds {rights_names(bad)}", code=VIOLATION_AGENT_RIGHTS, path=path)


def _split_chain(pm: Any, platform: str, mp: str | None, appr: str, findings: _Findings) -> list[str] | None:
    targets: list[str] = []
    if mp is not None:
        nm, na = _norm(platform, mp), _norm(platform, appr)
        sep = "\\" if platform == "nt" else "/"
        if nm == na or not nm.startswith(na.rstrip(sep) + sep):
            findings.violate("manifest is not contained within the approvals dir")
            return None
        node = mp
        while _norm(platform, node) != na:
            targets.append(node)
            node = pm.dirname(node)
    targets.append(appr)
    return targets


def _verify_windows(
    backend: Any, policy: BoundaryPolicy, manifest_path: str | None, approvals_dir: str, findings: _Findings,
) -> tuple[int, str, str]:
    pm = ntpath
    if not policy.trusted_owner_sids:
        raise errors.ApprovalBoundaryUnverifiable("no trusted owner SID is configured")
    if not policy.expected_agent_sid:
        raise errors.ApprovalBoundaryUnverifiable("no expected agent SID is configured")
    if not policy.trusted_volumes:
        raise errors.ApprovalBoundaryUnverifiable("no trusted approval volume is configured")

    try:
        ident = backend.current_identity()
    except AclUnreadable as exc:
        raise errors.ApprovalBoundaryUnverifiable(f"agent identity unreadable: {exc}") from exc
    if not isinstance(ident, Identity):
        raise errors.ApprovalBoundaryUnverifiable("agent identity has an unexpected type")

    agent = short_sid(ident.user_sid)
    _check_identity_windows(ident, policy, findings)

    try:
        appr = canonical_windows_path(approvals_dir)
        mp = canonical_windows_path(manifest_path) if manifest_path is not None else None
    except PathRejected as exc:
        findings.violate(f"path rejected: {exc}")
        return 0, agent, "", ""

    targets = _split_chain(pm, "nt", mp, appr, findings)
    if targets is None:
        return 0, agent, "", ""
    volume = _check_volume(backend, policy, appr, findings)
    ancestors = _parents(pm, appr)[1:]

    checked = 0
    seen: list[str] = []
    for path in targets + ancestors:
        is_target = path in targets
        try:
            node = backend.read_node(path)
        except AclUnreadable as exc:
            findings.unverified(f"{path}: unreadable ({exc})")
            continue
        checked += 1
        seen.append(repr(node))
        _eval_windows_node(
            findings, path, node, is_target=is_target,
            is_root=(pm.dirname(path) == path), policy=policy, ident=ident,
        )
    return checked, agent, volume, hashlib.sha256("\n".join(seen).encode("utf-8")).hexdigest()


def _eval_posix_node(
    findings: _Findings, path: str, node: Any, *, is_target: bool, euid: int, policy: BoundaryPolicy,
) -> None:
    if not isinstance(node, PosixNode):
        findings.unverified(f"{path}: unexpected descriptor type")
        return
    allowed_ancestor_uids = set(policy.trusted_owner_uids) | {0}
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


def _verify_posix(
    backend: Any, policy: BoundaryPolicy, manifest_path: str | None, approvals_dir: str, findings: _Findings,
) -> tuple[int, str, str]:
    pm = posixpath
    ident = backend.current_identity()
    euid = ident if isinstance(ident, int) and not isinstance(ident, bool) else None
    if euid is None:
        raise errors.ApprovalBoundaryUnverifiable("agent uid unreadable")
    agent = f"uid:{euid}"
    if not policy.trusted_owner_uids:
        raise errors.ApprovalBoundaryUnverifiable("no trusted owner uid is configured")
    if policy.expected_agent_uid is None:
        raise errors.ApprovalBoundaryUnverifiable("no expected agent uid is configured")
    if euid != policy.expected_agent_uid:
        findings.violate("executing uid is not the expected agent identity")
    if euid == 0:
        findings.violate("agent runs as root and bypasses file permissions")
    if euid in policy.trusted_owner_uids:
        findings.violate("agent identity is a trusted owner (owner and agent are not distinct)")

    try:
        appr = canonical_posix_path(approvals_dir)
        mp = canonical_posix_path(manifest_path) if manifest_path is not None else None
    except PathRejected as exc:
        findings.violate(f"path rejected: {exc}")
        return 0, agent, "", ""
    targets = _split_chain(pm, "posix", mp, appr, findings)
    if targets is None:
        return 0, agent, "", ""
    ancestors = _parents(pm, appr)[1:]

    checked = 0
    seen: list[str] = []
    for path in targets + ancestors:
        try:
            node = backend.read_node(path)
        except AclUnreadable as exc:
            findings.unverified(f"{path}: unreadable ({exc})")
            continue
        checked += 1
        seen.append(repr(node))
        _eval_posix_node(findings, path, node, is_target=path in targets, euid=euid, policy=policy)
    return checked, agent, "", hashlib.sha256("\n".join(seen).encode("utf-8")).hexdigest()


def verify_boundary(
    backend: Any,
    policy: BoundaryPolicy,
    manifest_path: "str | os.PathLike[str] | None",
    approvals_dir: "str | os.PathLike[str]",
    *,
    enforced: bool = True,
) -> BoundaryReport:
    """Evaluate the approval boundary. Raises a typed stop unless PROVEN.

    ``enforced`` only labels the report; it never relaxes any check. Callers
    that pass ``enforced=False`` (mocked descriptors) get an unenforced report.
    """

    mp = os.fspath(manifest_path) if manifest_path is not None else None
    ad = os.fspath(approvals_dir)
    findings = _Findings()
    platform = getattr(backend, "platform", None)
    try:
        if platform == "nt":
            checked, agent, volume, digest = _verify_windows(backend, policy, mp, ad, findings)
        elif platform == "posix":
            checked, agent, volume, digest = _verify_posix(backend, policy, mp, ad, findings)
        else:
            raise errors.ApprovalBoundaryUnverifiable("unsupported platform for boundary verification")
    except AclUnreadable as exc:
        raise errors.ApprovalBoundaryUnverifiable(f"security descriptor unreadable: {exc}") from exc
    findings.raise_if_any()
    return BoundaryReport(
        MODE_ENFORCED if enforced else MODE_OFFLINE_MOCKED, platform, enforced, checked, agent, volume,
        chain_digest=digest,
    )


# --- pinned approval read (file identity / TOCTOU) -----------------------------


class ApprovedFileSnapshot:
    """Bytes read from a pinned approval file, plus the open handle that pins it."""

    def __init__(
        self, *, path: str, content: bytes, sha256: str, identity: FileIdentity, pinned: PinnedFile,
        report: BoundaryReport,
    ) -> None:
        self.path = path
        self.content = content
        self.sha256 = sha256
        self.identity = identity
        self.report = report
        self._pinned = pinned
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def revalidate(self) -> None:
        """Fail closed unless the pinned file is byte-for-byte what was read and
        the path still names it."""

        if self._closed:
            raise errors.ApprovalBoundaryUnverifiable("the approval snapshot is closed")
        try:
            cur = self._pinned.current_identity()
            data = self._pinned.read_all(MAX_APPROVAL_BYTES)
            same_path = self._pinned.path_matches()
        except AclUnreadable as exc:
            raise errors.ApprovalBoundaryUnverifiable(f"pinned approval file unreadable: {exc}") from exc
        if cur != self.identity:
            raise errors.ApprovalBoundaryViolation("approval file identity, size or timestamp changed since it was read")
        if hashlib.sha256(data).hexdigest() != self.sha256:
            raise errors.ApprovalBoundaryViolation("approval file content changed since it was read")
        if not same_path:
            raise errors.ApprovalBoundaryViolation("the approval path no longer names the pinned file")

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._pinned.close()

    def __enter__(self) -> "ApprovedFileSnapshot":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def read_pinned_approval(
    backend: Any,
    policy: BoundaryPolicy,
    manifest_path: "str | os.PathLike[str]",
    approvals_dir: "str | os.PathLike[str]",
    *,
    enforced: bool = True,
) -> ApprovedFileSnapshot:
    """Check the chain, open the approval file once on a pinned handle, verify
    its identity and descriptor, read it, re-verify, and return the snapshot.

    The caller MUST parse the returned bytes (never re-open the path).
    """

    if manifest_path is None:
        raise errors.ApprovalBoundaryUnverifiable("no approval file was given")
    mp_raw, ad_raw = os.fspath(manifest_path), os.fspath(approvals_dir)
    first = verify_boundary(backend, policy, mp_raw, ad_raw, enforced=enforced)
    platform = backend.platform
    pm = _pathmod(platform)
    try:
        canon = canonical_windows_path(mp_raw) if platform == "nt" else canonical_posix_path(mp_raw)
    except PathRejected as exc:
        raise errors.ApprovalBoundaryViolation(f"path rejected: {exc}") from exc
    opener = getattr(backend, "open_pinned", None)
    if opener is None:
        raise errors.ApprovalBoundaryUnverifiable("this backend cannot pin the approval file")
    try:
        pinned = opener(canon)
    except AclUnreadable as exc:
        raise errors.ApprovalBoundaryUnverifiable(f"approval file could not be pinned: {exc}") from exc

    try:
        findings = _Findings()
        ident0 = pinned.identity
        if pinned.is_reparse:
            findings.violate("the opened approval file is a reparse point or symlink")
        if ident0.nlinks != 1:
            findings.violate("the approval file has additional hard links")
        if _norm(platform, pinned.final_path) != _norm(platform, canon):
            findings.violate("the opened approval file resolves to a different path than requested")
        who = backend.current_identity()
        if platform == "nt":
            _eval_windows_node(findings, canon, pinned.node(), is_target=True, is_root=False, policy=policy, ident=who)
        else:
            _eval_posix_node(findings, canon, pinned.node(), is_target=True, euid=who, policy=policy)
        findings.raise_if_any()

        content = pinned.read_all(MAX_APPROVAL_BYTES)
        if pinned.current_identity() != ident0:
            raise errors.ApprovalBoundaryViolation("the approval file changed while it was being read")
        if not pinned.path_matches():
            raise errors.ApprovalBoundaryViolation("the approval path no longer names the opened file")
        second = verify_boundary(backend, policy, mp_raw, ad_raw, enforced=enforced)
        if second.nodes_checked != first.nodes_checked or second.chain_digest != first.chain_digest:
            raise errors.ApprovalBoundaryViolation("the approval chain changed while it was being read")
    except AclUnreadable as exc:
        pinned.close()
        raise errors.ApprovalBoundaryUnverifiable(f"approval file unreadable: {exc}") from exc
    except BaseException:
        pinned.close()
        raise
    return ApprovedFileSnapshot(
        path=canon, content=content, sha256=hashlib.sha256(content).hexdigest(), identity=ident0,
        pinned=pinned, report=replace(second, pinned=True),
    )


# --- POSIX backend (real) -------------------------------------------------------


class _PosixPinned:
    def __init__(self, fd: int, path: str) -> None:
        self._fd = fd
        self._path = path
        st = os.fstat(fd)
        self.identity = self._ident(st)
        self.is_reparse = False
        try:
            self.final_path = os.readlink(f"/proc/self/fd/{fd}")
        except OSError:
            self.final_path = os.path.realpath(path)
        if self.final_path.endswith(" (deleted)"):
            self.final_path = "<deleted>"

    @staticmethod
    def _ident(st: os.stat_result) -> FileIdentity:
        return FileIdentity(st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_nlink)

    def node(self) -> PosixNode:
        st = os.fstat(self._fd)
        return PosixNode(self._path, st.st_uid, st.st_mode, is_symlink=False, is_dir=False)

    def read_all(self, max_bytes: int) -> bytes:
        os.lseek(self._fd, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(self._fd, 65536)
            if not chunk:
                return b"".join(chunks)
            total += len(chunk)
            if total > max_bytes:
                raise AclUnreadable("approval file is larger than the allowed maximum")
            chunks.append(chunk)

    def current_identity(self) -> FileIdentity:
        return self._ident(os.fstat(self._fd))

    def path_matches(self) -> bool:
        try:
            st = os.lstat(self._path)
        except OSError:
            return False
        return (st.st_dev, st.st_ino) == (self.identity.volume_serial, self.identity.file_index) and not stat.S_ISLNK(st.st_mode)

    def close(self) -> None:
        try:
            os.close(self._fd)
        except OSError:
            pass


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

    def open_pinned(self, path: str) -> _PosixPinned:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        try:
            fd = os.open(path, flags)
        except OSError as exc:
            raise AclUnreadable(f"open failed ({exc.__class__.__name__})") from exc
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise AclUnreadable("not a regular file")
            return _PosixPinned(fd, path)
        except BaseException:
            os.close(fd)
            raise


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

    def read_approved(self, manifest_path: Any, approvals_dir: Any) -> "ApprovedFileSnapshot | None": ...


class ProductionApprovalGuard:
    """ENFORCED: proves the OS approval boundary or raises a typed stop.

    It always uses the genuine backend for the CURRENT process token. No backend
    can be injected, so a mocked identity or descriptor can never produce an
    ENFORCED report - mocks are confined to :class:`MockedDescriptorApprovalGuard`.
    """

    mode = MODE_ENFORCED
    offline_only = False

    def __init__(self, policy: BoundaryPolicy) -> None:
        if not isinstance(policy, BoundaryPolicy):
            raise TypeError("policy must be a BoundaryPolicy")
        self._policy = policy

    @property
    def policy(self) -> BoundaryPolicy:
        return self._policy

    def verify(self, manifest_path: Any, approvals_dir: Any) -> BoundaryReport:
        return verify_boundary(default_backend(), self._policy, manifest_path, approvals_dir, enforced=True)

    def read_approved(self, manifest_path: Any, approvals_dir: Any) -> ApprovedFileSnapshot:
        return read_pinned_approval(default_backend(), self._policy, manifest_path, approvals_dir, enforced=True)


class MockedDescriptorApprovalGuard:
    """OFFLINE ONLY: runs the full evaluation against MOCKED descriptors/identity.

    The report is always unenforced and the runner refuses it unless every
    adapter is an offline fixture/mock, so it can never authorize production.
    """

    mode = MODE_OFFLINE_MOCKED
    offline_only = True

    def __init__(self, policy: BoundaryPolicy, backend: Any) -> None:
        if not isinstance(policy, BoundaryPolicy):
            raise TypeError("policy must be a BoundaryPolicy")
        self._policy = policy
        self._backend = backend

    @property
    def policy(self) -> BoundaryPolicy:
        return self._policy

    def verify(self, manifest_path: Any, approvals_dir: Any) -> BoundaryReport:
        return verify_boundary(self._backend, self._policy, manifest_path, approvals_dir, enforced=False)

    def read_approved(self, manifest_path: Any, approvals_dir: Any) -> "ApprovedFileSnapshot | None":
        if not hasattr(self._backend, "open_pinned"):
            return None
        return read_pinned_approval(self._backend, self._policy, manifest_path, approvals_dir, enforced=False)


class OfflineFixtureApprovalGuard:
    """Offline fixtures ONLY. Performs NO OS check and is therefore refused by
    the runner unless every adapter is an offline fixture/mock. It can never be
    used for production authorization."""

    mode = MODE_OFFLINE_FIXTURE
    offline_only = True

    def verify(self, manifest_path: Any, approvals_dir: Any) -> BoundaryReport:
        return BoundaryReport(MODE_OFFLINE_FIXTURE, "n/a", False, 0, "n/a")

    def read_approved(self, manifest_path: Any, approvals_dir: Any) -> None:
        return None
