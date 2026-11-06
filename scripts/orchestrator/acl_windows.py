"""Windows security READER for the approval-boundary guard (G1.6-B, G1.6-C2).

Strictly read-only, standard library only (``ctypes``). It can read an object's
owner + DACL (by path or by open handle), the current process token's
user/groups/privileges/integrity level, the facts that identify the volume
behind a drive letter, and it can open ONE file on a pinned, share-restricted
handle for a stable read. It contains no code that sets an ACL/owner, creates
processes, logs on, impersonates, adjusts privileges, or touches the network;
static tests assert that.

ACE parsing is done by hand from the raw ACL bytes (only the standard
ACCESS_ALLOWED / ACCESS_DENIED types are understood). Anything else is raised
as :class:`AclUnreadable` so the guard fails closed rather than guessing.

Every query that can fail raises :class:`AclUnreadable`; the guard converts that
to an "unverifiable" stop.
"""

from __future__ import annotations

import ctypes
import os
import stat
import struct
from ctypes import wintypes

from .acl_guard import (
    Ace, AclUnreadable, FileIdentity, Identity, NodeSecurity, Privilege, VolumeInfo,
)

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
_TOKEN_PRIVILEGES = 3
_TOKEN_INTEGRITY_LEVEL = 25
_SE_GROUP_ENABLED = 0x4
_SE_GROUP_USE_FOR_DENY_ONLY = 0x10
_SE_PRIVILEGE_ENABLED_BY_DEFAULT = 0x1
_SE_PRIVILEGE_ENABLED = 0x2
_SE_PRIVILEGE_REMOVED = 0x4
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_GENERIC_READ = 0x80000000
_FILE_READ_ATTRIBUTES = 0x80
_FILE_SHARE_READ = 0x1
_FILE_SHARE_WRITE = 0x2
_OPEN_EXISTING = 3
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
_INVALID_HANDLES = (None, 0, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF)

_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_advapi32.GetNamedSecurityInfoW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
    ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
    ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
    ctypes.POINTER(ctypes.c_void_p),
]
_advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD
_advapi32.GetSecurityInfo.argtypes = [
    ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
    ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
    ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
    ctypes.POINTER(ctypes.c_void_p),
]
_advapi32.GetSecurityInfo.restype = wintypes.DWORD
_advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
_advapi32.OpenProcessToken.restype = wintypes.BOOL
_advapi32.GetTokenInformation.argtypes = [
    wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
]
_advapi32.GetTokenInformation.restype = wintypes.BOOL
_advapi32.LookupPrivilegeNameW.argtypes = [
    wintypes.LPCWSTR, ctypes.c_void_p, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
]
_advapi32.LookupPrivilegeNameW.restype = wintypes.BOOL
_kernel32.GetCurrentProcess.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
_kernel32.CloseHandle.restype = wintypes.BOOL
_kernel32.LocalFree.argtypes = [ctypes.c_void_p]
_kernel32.LocalFree.restype = ctypes.c_void_p
_kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
]
_kernel32.CreateFileW.restype = ctypes.c_void_p
_kernel32.ReadFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
_kernel32.ReadFile.restype = wintypes.BOOL
_kernel32.SetFilePointerEx.argtypes = [ctypes.c_void_p, ctypes.c_longlong, ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD]
_kernel32.SetFilePointerEx.restype = wintypes.BOOL
_kernel32.GetFinalPathNameByHandleW.argtypes = [ctypes.c_void_p, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
_kernel32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
_kernel32.QueryDosDeviceW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
_kernel32.QueryDosDeviceW.restype = wintypes.DWORD
_kernel32.GetVolumePathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
_kernel32.GetVolumePathNameW.restype = wintypes.BOOL
_kernel32.GetVolumeNameForVolumeMountPointW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
_kernel32.GetVolumeNameForVolumeMountPointW.restype = wintypes.BOOL
_kernel32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
_kernel32.GetDriveTypeW.restype = wintypes.UINT
_kernel32.GetVolumeInformationW.argtypes = [
    wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR, wintypes.DWORD,
]
_kernel32.GetVolumeInformationW.restype = wintypes.BOOL
_kernel32.DeviceIoControl.argtypes = [
    ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
]
_kernel32.DeviceIoControl.restype = wintypes.BOOL


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class _TokenGroups(ctypes.Structure):
    _fields_ = [("GroupCount", wintypes.DWORD), ("Groups", _SidAndAttributes * 1)]


class _Luid(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _LuidAndAttributes(ctypes.Structure):
    _fields_ = [("Luid", _Luid), ("Attributes", wintypes.DWORD)]


class _TokenPrivileges(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", _LuidAndAttributes * 1)]


class _ByHandleFileInformation(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]


_kernel32.GetFileInformationByHandle.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ByHandleFileInformation)]
_kernel32.GetFileInformationByHandle.restype = wintypes.BOOL


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


def _node_from_pointers(path: str, owner: ctypes.c_void_p, dacl: ctypes.c_void_p, *, is_reparse: bool, is_dir: bool) -> NodeSecurity:
    owner_sid = _sid_from_pointer(owner.value)
    if not dacl.value:
        return NodeSecurity(path, owner_sid, (), dacl_present=False, is_reparse=is_reparse, is_dir=is_dir)
    return NodeSecurity(path, owner_sid, _parse_acl(dacl.value), dacl_present=True, is_reparse=is_reparse, is_dir=is_dir)


def _is_bad_handle(h: int | None) -> bool:
    return h in _INVALID_HANDLES


def _filetime_ns(ft: wintypes.FILETIME) -> int:
    return ((ft.dwHighDateTime << 32) | ft.dwLowDateTime) * 100


def _identity_from_info(info: _ByHandleFileInformation) -> FileIdentity:
    return FileIdentity(
        volume_serial=int(info.dwVolumeSerialNumber),
        file_index=(int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow),
        size=(int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow),
        mtime_ns=_filetime_ns(info.ftLastWriteTime),
        nlinks=int(info.nNumberOfLinks),
    )


class _WinPinned:
    """One approval file held open on a handle that denies writers and deleters."""

    def __init__(self, handle: int, path: str) -> None:
        self._h = handle
        self._path = path
        self._closed = False
        info = self._info()
        self.identity = _identity_from_info(info)
        self.is_reparse = bool(info.dwFileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT)
        self.final_path = self._final_path()

    def _info(self) -> _ByHandleFileInformation:
        info = _ByHandleFileInformation()
        if not _kernel32.GetFileInformationByHandle(self._h, ctypes.byref(info)):
            raise AclUnreadable("GetFileInformationByHandle failed")
        return info

    def _final_path(self) -> str:
        buf = ctypes.create_unicode_buffer(1024)
        n = _kernel32.GetFinalPathNameByHandleW(self._h, buf, 1024, 0)
        if n == 0 or n >= 1024:
            raise AclUnreadable("GetFinalPathNameByHandle failed")
        value = buf.value
        if value.startswith("\\\\?\\UNC\\"):
            return "\\\\" + value[8:]
        if value.startswith("\\\\?\\"):
            return value[4:]
        return value

    def node(self) -> NodeSecurity:
        owner, dacl, sd = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
        rc = _advapi32.GetSecurityInfo(
            self._h, _SE_FILE_OBJECT, _OWNER_SECURITY_INFORMATION | _DACL_SECURITY_INFORMATION,
            ctypes.byref(owner), None, ctypes.byref(dacl), None, ctypes.byref(sd),
        )
        if rc != 0:
            raise AclUnreadable(f"GetSecurityInfo error {rc}")
        try:
            return _node_from_pointers(self._path, owner, dacl, is_reparse=self.is_reparse, is_dir=False)
        finally:
            if sd.value:
                _kernel32.LocalFree(sd)

    def read_all(self, max_bytes: int) -> bytes:
        if not _kernel32.SetFilePointerEx(self._h, 0, None, 0):
            raise AclUnreadable("SetFilePointerEx failed")
        chunks: list[bytes] = []
        total = 0
        buf = ctypes.create_string_buffer(65536)
        while True:
            got = wintypes.DWORD(0)
            if not _kernel32.ReadFile(self._h, buf, 65536, ctypes.byref(got), None):
                raise AclUnreadable("ReadFile failed")
            if got.value == 0:
                return b"".join(chunks)
            total += got.value
            if total > max_bytes:
                raise AclUnreadable("approval file is larger than the allowed maximum")
            chunks.append(buf.raw[: got.value])

    def current_identity(self) -> FileIdentity:
        return _identity_from_info(self._info())

    def path_matches(self) -> bool:
        # Attribute-only second open of the PATH (no data access, so it does not
        # conflict with our share mode): does the path still name this exact file?
        h = _kernel32.CreateFileW(
            self._path, _FILE_READ_ATTRIBUTES, _FILE_SHARE_READ | _FILE_SHARE_WRITE, None, _OPEN_EXISTING,
            _FILE_FLAG_OPEN_REPARSE_POINT, None,
        )
        if _is_bad_handle(h):
            return False
        try:
            info = _ByHandleFileInformation()
            if not _kernel32.GetFileInformationByHandle(h, ctypes.byref(info)):
                return False
            if info.dwFileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT:
                return False
            now = _identity_from_info(info)
            return (now.volume_serial, now.file_index) == (self.identity.volume_serial, self.identity.file_index)
        finally:
            _kernel32.CloseHandle(h)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            _kernel32.CloseHandle(self._h)


class WindowsSecurityBackend:
    platform = "nt"

    # --- descriptors -------------------------------------------------------

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
            return _node_from_pointers(path, owner, dacl, is_reparse=is_reparse, is_dir=stat.S_ISDIR(st.st_mode))
        finally:
            if sd.value:
                _kernel32.LocalFree(sd)

    # --- the executing token -------------------------------------------------

    def current_identity(self) -> Identity:
        token = wintypes.HANDLE()
        if not _advapi32.OpenProcessToken(_kernel32.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(token)):
            raise AclUnreadable("OpenProcessToken failed")
        try:
            user = self._token_buffer(token, _TOKEN_USER)
            user_sid = _sid_from_pointer(_SidAndAttributes.from_buffer(user).Sid)

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
            return Identity(
                user_sid, frozenset(enabled), frozenset(deny_only),
                privileges=self._privileges(token), integrity_rid=self._integrity(token),
            )
        finally:
            _kernel32.CloseHandle(token)

    def _privileges(self, token: wintypes.HANDLE) -> tuple[Privilege, ...]:
        buf = self._token_buffer(token, _TOKEN_PRIVILEGES)
        count = _TokenPrivileges.from_buffer(buf).PrivilegeCount
        if count > 512:
            raise AclUnreadable("implausible privilege count")
        base = ctypes.addressof(buf) + _TokenPrivileges.Privileges.offset
        out: list[Privilege] = []
        for i in range(count):
            entry = _LuidAndAttributes.from_address(base + i * ctypes.sizeof(_LuidAndAttributes))
            name_buf = ctypes.create_unicode_buffer(128)
            size = wintypes.DWORD(128)
            if _advapi32.LookupPrivilegeNameW(None, ctypes.byref(entry.Luid), name_buf, ctypes.byref(size)):
                name = name_buf.value
            else:
                name = f"LUID:{entry.Luid.HighPart:x}:{entry.Luid.LowPart:x}"
            attrs = entry.Attributes
            out.append(Privilege(
                name=name,
                enabled=bool(attrs & _SE_PRIVILEGE_ENABLED),
                enabled_by_default=bool(attrs & _SE_PRIVILEGE_ENABLED_BY_DEFAULT),
                removed=bool(attrs & _SE_PRIVILEGE_REMOVED),
            ))
        return tuple(out)

    def _integrity(self, token: wintypes.HANDLE) -> int:
        buf = self._token_buffer(token, _TOKEN_INTEGRITY_LEVEL)
        sid = _sid_from_pointer(_SidAndAttributes.from_buffer(buf).Sid)
        if not sid.startswith("S-1-16-"):
            raise AclUnreadable("unexpected integrity label")
        return int(sid.rsplit("-", 1)[1])

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

    # --- volume identity -----------------------------------------------------

    def volume_info(self, path: str) -> VolumeInfo:
        if len(path) < 3 or path[1] != ":" or path[2] != "\\":
            raise AclUnreadable("not a drive-letter path")
        drive = path[:2]
        dev = ctypes.create_unicode_buffer(1024)
        if _kernel32.QueryDosDeviceW(drive, dev, 1024) == 0:
            raise AclUnreadable("QueryDosDevice failed")
        dos_target = dev.value  # first target in the multi-string

        root = ctypes.create_unicode_buffer(1024)
        if not _kernel32.GetVolumePathNameW(path, root, 1024):
            raise AclUnreadable("GetVolumePathName failed")
        mount_root = root.value

        guid = ctypes.create_unicode_buffer(100)
        if not _kernel32.GetVolumeNameForVolumeMountPointW(mount_root, guid, 100):
            raise AclUnreadable("GetVolumeNameForVolumeMountPoint failed")

        drive_type = int(_kernel32.GetDriveTypeW(mount_root))
        label = ctypes.create_unicode_buffer(261)
        fsname = ctypes.create_unicode_buffer(261)
        serial, maxcomp, flags = wintypes.DWORD(0), wintypes.DWORD(0), wintypes.DWORD(0)
        if not _kernel32.GetVolumeInformationW(
            mount_root, label, 261, ctypes.byref(serial), ctypes.byref(maxcomp), ctypes.byref(flags), fsname, 261,
        ):
            raise AclUnreadable("GetVolumeInformation failed")

        bus_type, vendor, product = self._bus_info(drive)
        return VolumeInfo(
            mount_root=mount_root, dos_target=dos_target, volume_guid=guid.value, drive_type=drive_type,
            filesystem=fsname.value, label=label.value, serial=int(serial.value),
            bus_type=bus_type, vendor=vendor, product=product,
        )

    @staticmethod
    def _bus_info(drive: str) -> tuple[int | None, str, str]:
        """STORAGE_DEVICE_DESCRIPTOR via a zero-access volume handle (query only).
        Returns (None, '', '') when the platform refuses; the guard then treats a
        required bus-type binding as unverifiable."""

        h = _kernel32.CreateFileW("\\\\.\\" + drive, 0, _FILE_SHARE_READ | _FILE_SHARE_WRITE, None, _OPEN_EXISTING, 0, None)
        if _is_bad_handle(h):
            return None, "", ""
        try:
            query = struct.pack("<II4s", 0, 0, b"\x00" * 4)  # StorageDeviceProperty, PropertyStandardQuery
            out = ctypes.create_string_buffer(1024)
            ret = wintypes.DWORD(0)
            if not _kernel32.DeviceIoControl(h, _IOCTL_STORAGE_QUERY_PROPERTY, query, len(query), out, 1024, ctypes.byref(ret), None):
                return None, "", ""
            raw = out.raw[: ret.value]
            if len(raw) < 36:
                return None, "", ""
            vendor_off, product_off = struct.unpack_from("<II", raw, 12)
            bus = struct.unpack_from("<I", raw, 28)[0]

            def text(off: int) -> str:
                if off <= 0 or off >= len(raw):
                    return ""
                end = raw.find(b"\x00", off)
                return raw[off : end if end != -1 else len(raw)].decode("ascii", "replace").strip()

            return int(bus), text(vendor_off), text(product_off)
        finally:
            _kernel32.CloseHandle(h)

    # --- pinned read -----------------------------------------------------------

    def open_pinned(self, path: str) -> _WinPinned:
        # Read-only; sharing ONLY for readers, so a writer or a deleter/renamer
        # cannot touch the file while it is held. The final component is not
        # followed if it is a reparse point.
        h = _kernel32.CreateFileW(
            path, _GENERIC_READ, _FILE_SHARE_READ, None, _OPEN_EXISTING, _FILE_FLAG_OPEN_REPARSE_POINT, None,
        )
        if _is_bad_handle(h):
            raise AclUnreadable(f"CreateFile failed (error {ctypes.get_last_error()})")
        try:
            return _WinPinned(h, path)
        except BaseException:
            _kernel32.CloseHandle(h)
            raise
