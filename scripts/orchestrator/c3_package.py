"""G1.6-C3-G0: offline, deterministic packaging + verification of trusted code.

Pure standard-library tooling. It never downloads anything, never installs or
copies into ``P:\\bin``, and never invokes git or any process. It works on:

  * a directory produced by ``git archive`` (the exact committed bytes), and
  * the text of ``git ls-tree -r <commit>`` for that tree,

and proves, offline, that the export is exactly the pinned commit's content:
every file's git blob id matches, no file is missing or extra, no symlink or
submodule entry exists, no path is unsafe. A worktree checkout is NOT a valid
source: line-ending conversion changes the bytes (and therefore the blob ids),
which this tool detects and refuses.

The resulting manifest is canonical JSON, so its SHA-256 digest is stable and
can be bound into an owner approval.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from typing import Any, Mapping

from . import acl_guard, errors

SCHEMA = "petcare.c3.package/v1"
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_MODES = ("100644", "100755")
MAX_FILES = 20_000
MAX_TOTAL_BYTES = 512 * 1024 * 1024
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def git_blob_id(data: bytes) -> str:
    """The git object id of a blob with this content."""

    return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()  # noqa: S324 - git object id, not security


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_rel_path(rel: Any) -> str:
    """A safe, forward-slash, relative path inside a package, or raise."""

    if not isinstance(rel, str) or not rel or rel != rel.strip():
        raise errors.PackageIntegrityFailure("empty or padded package path")
    if "\\" in rel or rel.startswith("/") or "\x00" in rel:
        raise errors.PackageIntegrityFailure("package paths must be relative and use forward slashes")
    try:
        canon = acl_guard.canonical_windows_path("C:\\" + rel.replace("/", "\\"))
    except acl_guard.PathRejected as exc:
        raise errors.PackageIntegrityFailure(f"unsafe package path: {exc}") from exc
    if canon[3:].replace("\\", "/") != rel:
        raise errors.PackageIntegrityFailure("package path is not in canonical form")
    return rel


def parse_ls_tree(text: str) -> dict[str, tuple[str, str]]:
    """Parse ``git ls-tree -r`` output into ``{path: (mode, blob_sha)}``.

    Symlinks (120000), submodules (160000) and anything else are refused: a
    trusted package must be plain files only.
    """

    entries: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            meta, path = line.split("\t", 1)
            mode, kind, sha = meta.split(" ")
        except ValueError:
            raise errors.PackageIntegrityFailure("malformed ls-tree line") from None
        if kind != "blob" or mode not in _ALLOWED_MODES:
            raise errors.PackageIntegrityFailure(f"non-regular tree entry refused ({mode} {kind})")
        if not _HEX40.match(sha):
            raise errors.PackageIntegrityFailure("malformed blob id in ls-tree")
        validate_rel_path(path)
        if path in entries:
            raise errors.PackageIntegrityFailure("duplicate path in ls-tree")
        entries[path] = (mode, sha)
    if not entries:
        raise errors.PackageIntegrityFailure("empty ls-tree listing")
    return entries


@dataclass(frozen=True)
class FileEntry:
    path: str
    sha256: str
    size: int
    git_blob: str


@dataclass(frozen=True)
class PackageManifest:
    source_commit: str
    files: tuple[FileEntry, ...]
    schema: str = SCHEMA

    def to_bytes(self) -> bytes:
        doc = {
            "schema": self.schema,
            "source_commit": self.source_commit,
            "files": [
                {"path": f.path, "sha256": f.sha256, "size": f.size, "git_blob": f.git_blob}
                for f in sorted(self.files, key=lambda f: f.path)
            ],
        }
        return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")

    def digest(self) -> str:
        return sha256_hex(self.to_bytes())

    @classmethod
    def from_bytes(cls, data: bytes) -> "PackageManifest":
        try:
            doc = json.loads(data.decode("utf-8"))
        except ValueError:
            raise errors.PackageIntegrityFailure("package manifest is not valid JSON") from None
        if not isinstance(doc, dict) or set(doc) != {"schema", "source_commit", "files"} or doc["schema"] != SCHEMA:
            raise errors.PackageIntegrityFailure("package manifest has the wrong shape or schema")
        commit = doc["source_commit"]
        if not isinstance(commit, str) or not _HEX40.match(commit):
            raise errors.PackageIntegrityFailure("package manifest source_commit is invalid")
        files: list[FileEntry] = []
        seen: set[str] = set()
        if not isinstance(doc["files"], list) or not doc["files"]:
            raise errors.PackageIntegrityFailure("package manifest lists no files")
        for item in doc["files"]:
            if not isinstance(item, dict) or set(item) != {"path", "sha256", "size", "git_blob"}:
                raise errors.PackageIntegrityFailure("package manifest entry has the wrong shape")
            path = validate_rel_path(item["path"])
            sha, size, blob = item["sha256"], item["size"], item["git_blob"]
            if not (isinstance(sha, str) and _HEX64.match(sha) and isinstance(blob, str) and _HEX40.match(blob)):
                raise errors.PackageIntegrityFailure("package manifest hash is malformed")
            if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                raise errors.PackageIntegrityFailure("package manifest size is invalid")
            if path.lower() in seen:
                raise errors.PackageIntegrityFailure("package manifest has a (case-insensitive) duplicate path")
            seen.add(path.lower())
            files.append(FileEntry(path, sha, size, blob))
        return cls(source_commit=commit, files=tuple(sorted(files, key=lambda f: f.path)))


def build_manifest(files: Mapping[str, bytes], *, source_commit: str, tree_listing: str) -> PackageManifest:
    """Build the manifest for an export, proving it equals the pinned commit.

    Fails closed on any missing/extra file, blob-id mismatch (including
    line-ending conversion), unsafe or colliding path, or unsupported entry.
    """

    if not isinstance(source_commit, str) or not _HEX40.match(source_commit):
        raise errors.PackageIntegrityFailure("source_commit must be a full 40-hex commit id")
    tree = parse_ls_tree(tree_listing)
    if len(files) > MAX_FILES:
        raise errors.PackageIntegrityFailure("too many files in the export")
    seen: dict[str, str] = {}
    for rel in files:
        validate_rel_path(rel)
        if rel.lower() in seen:
            raise errors.PackageIntegrityFailure("export has case-insensitively colliding paths")
        seen[rel.lower()] = rel
    missing = sorted(set(tree) - set(files))
    extra = sorted(set(files) - set(tree))
    if missing or extra:
        raise errors.PackageIntegrityFailure(f"export differs from the commit tree (missing={missing[:3]}, extra={extra[:3]})")
    entries: list[FileEntry] = []
    for rel in sorted(files):
        data = files[rel]
        blob = git_blob_id(data)
        if blob != tree[rel][1]:
            raise errors.PackageIntegrityFailure(f"content of {rel} does not match its git blob (modified or line-ending converted)")
        entries.append(FileEntry(rel, sha256_hex(data), len(data), blob))
    return PackageManifest(source_commit=source_commit, files=tuple(entries))


def verify_observed_tree(manifest: PackageManifest, observed: Mapping[str, tuple[str, int]]) -> None:
    """``observed`` is ``{relpath: (sha256, size)}`` of an installed tree. It must
    equal the manifest exactly: nothing missing, nothing extra, nothing changed."""

    want = {f.path: (f.sha256, f.size) for f in manifest.files}
    got = dict(observed)
    missing = sorted(set(want) - set(got))
    extra = sorted(set(got) - set(want))
    changed = sorted(p for p in set(want) & set(got) if want[p] != got[p])
    if missing or extra or changed:
        raise errors.PackageIntegrityFailure(
            f"installed tree differs from the manifest (missing={missing[:3]}, extra={extra[:3]}, changed={changed[:3]})"
        )


def _is_reparse(st: os.stat_result) -> bool:
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT)


def scan_tree(root: str, *, keep_bytes: bool = False) -> dict[str, Any]:
    """Read-only walk of a directory. Returns ``{rel: (sha256, size)}`` (or
    ``{rel: bytes}`` with ``keep_bytes``). Refuses symlinks, junctions and special
    files at any depth, and bounds file count and total size."""

    try:
        root_stat = os.lstat(root)
    except OSError as exc:
        raise errors.PackageIntegrityFailure(f"cannot stat the export root: {exc.__class__.__name__}") from exc
    if _is_reparse(root_stat) or not stat.S_ISDIR(root_stat.st_mode):
        raise errors.PackageIntegrityFailure("the export root is a link, reparse point or not a directory")
    out: dict[str, Any] = {}
    total = 0
    stack = [""]
    while stack:
        rel_dir = stack.pop()
        base = os.path.join(root, rel_dir) if rel_dir else root
        try:
            with os.scandir(base) as it:
                children = sorted(it, key=lambda e: e.name)
        except OSError as exc:
            raise errors.PackageIntegrityFailure(f"cannot list {rel_dir or '.'}: {exc.__class__.__name__}") from exc
        for entry in children:
            rel = f"{rel_dir}/{entry.name}" if rel_dir else entry.name
            validate_rel_path(rel)  # directories too: an unsafe empty directory name is also refused
            path = os.path.join(root, rel)
            st = os.lstat(path)  # authoritative: DirEntry.stat() omits inode/device on Windows
            if _is_reparse(st):
                raise errors.PackageIntegrityFailure(f"symlink or reparse point refused: {rel}")
            if stat.S_ISDIR(st.st_mode):
                stack.append(rel)
            elif stat.S_ISREG(st.st_mode):
                if len(out) >= MAX_FILES:
                    raise errors.PackageIntegrityFailure("too many files")
                # Open ONCE (no-follow where the OS has it), prove the handle is the file that
                # was just examined, and read from the handle within the remaining byte budget.
                flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
                try:
                    fd = os.open(path, flags)
                except OSError as exc:
                    raise errors.PackageIntegrityFailure(f"cannot open {rel}: {exc.__class__.__name__}") from exc
                try:
                    fst = os.fstat(fd)
                    if (fst.st_dev, fst.st_ino) != (st.st_dev, st.st_ino) or not stat.S_ISREG(fst.st_mode):
                        raise errors.PackageIntegrityFailure(f"file changed while it was being examined: {rel}")
                    chunks: list[bytes] = []
                    while True:
                        chunk = os.read(fd, 65536)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > MAX_TOTAL_BYTES:
                            raise errors.PackageIntegrityFailure("tree is larger than the allowed maximum")
                        chunks.append(chunk)
                finally:
                    os.close(fd)
                data = b"".join(chunks)
                out[rel] = data if keep_bytes else (sha256_hex(data), len(data))
            else:
                raise errors.PackageIntegrityFailure(f"special file refused: {rel}")
    return out
