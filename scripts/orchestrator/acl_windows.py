"""Windows security-descriptor READER for the approval-boundary guard (G1.6-B).

Strictly read-only, standard library only (``ctypes``). This module can read an
object's owner + DACL and the current process token's user/groups. It contains
no code that sets an ACL/owner, creates processes, logs on, impersonates,
adjusts privileges, or touches the network; static tests assert that.

ACE parsing is done by hand from the raw ACL bytes (only the standard
ACCESS_ALLOWED / ACCESS_DENIED types are understood). Anything else is raised
as :class:`AclUnreadable` so the guard fails closed rather than guessing.

Residual (documented, not hidden): the descriptor is read by path, so a
time-of-check/time-of-use window exists between this read and later use.
"""

from __future__ import annotations

import ctypes
import os
import stat
import struct
from ctypes import wintypes

from .acl_guard import Ace, AclUnreadable, Identity, NodeSecurity

if os.name != "nt":  # pragma: no cover - the module is only imported on Windows
    raise ImportError("acl_windows is Windows-only")

_SE_FILE_OBJECT = 1
_OWNER_SECURITY_INFORMATION = 0x1
_DACL_SECURITY_INFORMATION = 0x4
_ACE_ACCESS_ALLOWED = 0
_ACE_ACCESS_DENIED = 1
_INHERITED_ACE = 0x10
_INHERIT_ONLY_ACE = 0x08
_TOKEN_QUERY = 0x0008
_TOKEN_USER = 1
_TOKEN_GROUPS = 2
_SE_GROUP_ENABLED = 0x4
_SE_GROUP_USE_FOR_DENY_ONLY = 0x10
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400

_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_advapi32.GetNamedSecurityInfoW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
    ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
    ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
    ctypes.POINTER(ctypes.c_void_p),
]
_advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD
_advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
_advapi32.OpenProcessToken.restype = wintypes.BOOL
_advapi32.GetTokenInformation.argtypes = [
    wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
]
_advapi32.GetTokenInformation.restype = wintypes.BOOL
_kernel32.GetCurrentProcess.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL
_kernel32.LocalFree.argtypes = [ctypes.c_void_p]
_kernel32.LocalFree.restype = ctypes.c_void_p


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class _TokenGroups(ctypes.Structure):
    _fields_ = [("GroupCount", wintypes.DWORD), ("Groups", _SidAndAttributes * 1)]


def _sid_to_string(raw: bytes) -> str:
    if len(raw) < 8:
        raise AclUnreadable("SID too short")
    revision, count = raw[0], raw[1]
    if revision != 1 or count > 15 or len(raw) < 8 + 4 * count:
        raise AclUnreadable("malformed SID")
    authority = int.from_bytes(raw[2:8], "big")
    subs = struct.unpack("<" + "I" * count, raw[8 : 8 + 4 * count])
    auth = str(authority) if authority < 2**32 else f"0x{authority:012X}"
    return "S-1-" + auth + "".join(f"-{s}" for s in subs)


def _sid_from_pointer(ptr: int | None) -> str:
    if not ptr:
        raise AclUnreadable("null SID pointer")
    head = ctypes.string_at(ptr, 2)
    length = 8 + 4 * head[1]
    return _sid_to_string(ctypes.string_at(ptr, length))


def _parse_acl(pacl: int) -> tuple[Ace, ...]:
    header = ctypes.string_at(pacl, 8)
    acl_size = struct.unpack_from("<H", header, 2)[0]
    ace_count = struct.unpack_from("<H", header, 4)[0]
    if acl_size < 8 or acl_size > 65535:
        raise AclUnreadable("invalid ACL size")
    data = ctypes.string_at(pacl, acl_size)
    aces: list[Ace] = []
    offset = 8
    for _ in range(ace_count):
        if offset + 8 > len(data):
            raise AclUnreadable("truncated ACE")
        ace_type, flags, size = struct.unpack_from("<BBH", data, offset)
        if size < 12 or offset + size > len(data):
            raise AclUnreadable("invalid ACE size")
        if ace_type not in (_ACE_ACCESS_ALLOWED, _ACE_ACCESS_DENIED):
            raise AclUnreadable(f"unsupported ACE type {ace_type}")
        mask = struct.unpack_from("<I", data, offset + 4)[0]
        sid = _sid_to_string(data[offset + 8 : offset + size])
        aces.append(
            Ace(
                sid=sid,
                mask=mask,
                allow=ace_type == _ACE_ACCESS_ALLOWED,
                inherited=bool(flags & _INHERITED_ACE),
                inherit_only=bool(flags & _INHERIT_ONLY_ACE),
            )
        )
        offset += size
    return tuple(aces)


class WindowsSecurityBackend:
    platform = "nt"

    def read_node(self, path: str) -> NodeSecurity:
        try:
            st = os.lstat(path)
        except OSError as exc:
            raise AclUnreadable(f"stat failed: {exc.__class__.__name__}") from exc
        attrs = getattr(st, "st_file_attributes", 0)
        is_reparse = bool(attrs & _FILE_ATTRIBUTE_REPARSE_POINT) or stat.S_ISLNK(st.st_mode)

        owner = ctypes.c_void_p()
        dacl = ctypes.c_void_p()
        sd = ctypes.c_void_p()
        rc = _advapi32.GetNamedSecurityInfoW(
            path, _SE_FILE_OBJECT, _OWNER_SECURITY_INFORMATION | _DACL_SECURITY_INFORMATION,
            ctypes.byref(owner), None, ctypes.byref(dacl), None, ctypes.byref(sd),
        )
        if rc != 0:
            raise AclUnreadable(f"GetNamedSecurityInfo error {rc}")
        try:
            owner_sid = _sid_from_pointer(owner.value)
            if not dacl.value:
                return NodeSecurity(path, owner_sid, (), dacl_present=False,
                                    is_reparse=is_reparse, is_dir=stat.S_ISDIR(st.st_mode))
            aces = _parse_acl(dacl.value)
            return NodeSecurity(path, owner_sid, aces, dacl_present=True,
                                is_reparse=is_reparse, is_dir=stat.S_ISDIR(st.st_mode))
        finally:
            if sd.value:
                _kernel32.LocalFree(sd)

    def current_identity(self) -> Identity:
        token = wintypes.HANDLE()
        if not _advapi32.OpenProcessToken(_kernel32.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(token)):
            raise AclUnreadable("OpenProcessToken failed")
        try:
            user = self._token_buffer(token, _TOKEN_USER)
            user_ptr = _SidAndAttributes.from_buffer(user).Sid
            user_sid = _sid_from_pointer(user_ptr)

            buf = self._token_buffer(token, _TOKEN_GROUPS)
            count = _TokenGroups.from_buffer(buf).GroupCount
            if count > 1024:
                raise AclUnreadable("implausible group count")
            base = ctypes.addressof(buf) + _TokenGroups.Groups.offset
            enabled: set[str] = set()
            deny_only: set[str] = set()
            for i in range(count):
                entry = _SidAndAttributes.from_address(base + i * ctypes.sizeof(_SidAndAttributes))
                sid = _sid_from_pointer(entry.Sid)
                attrs = entry.Attributes
                if attrs & _SE_GROUP_USE_FOR_DENY_ONLY:
                    deny_only.add(sid)
                elif attrs & _SE_GROUP_ENABLED:
                    enabled.add(sid)
            return Identity(user_sid, frozenset(enabled), frozenset(deny_only))
        finally:
            _kernel32.CloseHandle(token)

    @staticmethod
    def _token_buffer(token: wintypes.HANDLE, info_class: int):
        needed = wintypes.DWORD(0)
        _advapi32.GetTokenInformation(token, info_class, None, 0, ctypes.byref(needed))
        if needed.value == 0 or needed.value > 1_000_000:
            raise AclUnreadable("token information size invalid")
        buf = ctypes.create_string_buffer(needed.value)
        if not _advapi32.GetTokenInformation(token, info_class, buf, needed.value, ctypes.byref(needed)):
            raise AclUnreadable("GetTokenInformation failed")
        return buf
