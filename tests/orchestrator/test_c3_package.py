"""G1.6-C3-G0: deterministic, offline packaging + verification of trusted code."""

from __future__ import annotations

import hashlib
import json
import os

import pytest

from scripts.orchestrator import c3_package as pkg
from scripts.orchestrator import errors

COMMIT = "a6b6c66cef916eec4182053a398a9d2106eda5ff"
FILES = {
    "scripts/orchestrator/__init__.py": b"",
    "scripts/orchestrator/a.py": b"print('a')\n",
    "scripts/orchestrator/sub/b.py": b"x = 1\nline2\n",
}


def listing(files=FILES, mode="100644") -> str:
    return "\n".join(f"{mode} blob {pkg.git_blob_id(data)}\t{path}" for path, data in sorted(files.items())) + "\n"


def test_git_blob_id_matches_git():
    assert pkg.git_blob_id(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"
    assert pkg.git_blob_id(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"  # git's well-known empty blob


def test_manifest_is_built_deterministically_and_round_trips():
    a = pkg.build_manifest(FILES, source_commit=COMMIT, tree_listing=listing())
    b = pkg.build_manifest(dict(reversed(list(FILES.items()))), source_commit=COMMIT, tree_listing=listing())
    assert a == b and a.digest() == b.digest() and len(a.digest()) == 64
    again = pkg.PackageManifest.from_bytes(a.to_bytes())
    assert again == a and again.digest() == a.digest()
    assert json.loads(a.to_bytes())["schema"] == pkg.SCHEMA


def test_the_digest_changes_with_any_content_or_commit_change():
    base = pkg.build_manifest(FILES, source_commit=COMMIT, tree_listing=listing()).digest()
    other = dict(FILES, **{"scripts/orchestrator/a.py": b"print('b')\n"})
    assert pkg.build_manifest(other, source_commit=COMMIT, tree_listing=listing(other)).digest() != base
    assert pkg.build_manifest(FILES, source_commit="1" * 40, tree_listing=listing()).digest() != base


def test_line_ending_conversion_is_detected_because_the_blob_id_changes():
    crlf = dict(FILES, **{"scripts/orchestrator/sub/b.py": b"x = 1\r\nline2\r\n"})
    with pytest.raises(errors.PackageIntegrityFailure) as e:
        pkg.build_manifest(crlf, source_commit=COMMIT, tree_listing=listing())
    assert "line-ending" in e.value.detail


def test_missing_extra_and_modified_files_are_refused():
    missing = {k: v for k, v in FILES.items() if k != "scripts/orchestrator/a.py"}
    with pytest.raises(errors.PackageIntegrityFailure):
        pkg.build_manifest(missing, source_commit=COMMIT, tree_listing=listing())
    extra = dict(FILES, **{"scripts/orchestrator/evil.py": b"x"})
    with pytest.raises(errors.PackageIntegrityFailure):
        pkg.build_manifest(extra, source_commit=COMMIT, tree_listing=listing())
    tampered = dict(FILES, **{"scripts/orchestrator/a.py": b"print('EVIL')\n"})
    with pytest.raises(errors.PackageIntegrityFailure):
        pkg.build_manifest(tampered, source_commit=COMMIT, tree_listing=listing())


@pytest.mark.parametrize("commit", ["", "abc", "Z" * 40, "A" * 40, "a" * 39])
def test_the_source_commit_must_be_a_full_lowercase_hex_id(commit):
    with pytest.raises(errors.PackageIntegrityFailure):
        pkg.build_manifest(FILES, source_commit=commit, tree_listing=listing())


@pytest.mark.parametrize("mode,kind", [("120000", "blob"), ("160000", "commit"), ("100664", "blob"), ("040000", "tree")])
def test_symlinks_submodules_and_odd_modes_in_the_tree_are_refused(mode, kind):
    line = f"{mode} {kind} {'a' * 40}\tscripts/orchestrator/a.py\n"
    with pytest.raises(errors.PackageIntegrityFailure):
        pkg.parse_ls_tree(line)


@pytest.mark.parametrize("text", ["", "\n", "garbage", "100644 blob xyz\ta.py", "100644 blob " + "a" * 40 + " a.py"])
def test_malformed_or_empty_listings_are_refused(text):
    with pytest.raises(errors.PackageIntegrityFailure):
        pkg.parse_ls_tree(text)


def test_duplicate_listing_paths_are_refused():
    line = f"100644 blob {'a' * 40}\ta.py\n"
    with pytest.raises(errors.PackageIntegrityFailure):
        pkg.parse_ls_tree(line + line)


@pytest.mark.parametrize(
    "bad",
    ["../x", "/abs/x", "a\\b", "a:b", "a/./b", "a/../b", "C:/x", "a/b.", "a/b ", "CON", "a/nul.txt", "a//b", "", " a", "a/~1", "a/PROGRA~1/x"],
)
def test_unsafe_package_paths_are_refused(bad):
    with pytest.raises(errors.PackageIntegrityFailure):
        pkg.validate_rel_path(bad)


# --- finding #26 (OPEN, documented): Windows path rules on every platform -------------------------

AMBIGUOUS_FORMS = [
    "aux.ts", "nul.json", "src/con", "src/com1.txt", "lpt9.log", "vendor/FOO~1/x.py", "docs/notes.", "docs/notes ",
    "data/file.txt:stream", "data/file.txt::$DATA", '"caf\\303\\251.txt"', "caf\\303\\251.txt", "a/./b", "a/../../etc",
    "./a", "a//b", "//server/share/x", "\\\\?\\C:\\x", "C:x", "a\x00b", " a", "a\t",
    "\u202ex.py", "src/\u200bmain.py", "a\u0085b", "a\x1bb", "\ufeffa.py",
]


@pytest.mark.parametrize("bad", AMBIGUOUS_FORMS)
def test_ambiguous_or_windows_unsafe_paths_fail_closed_everywhere(bad):
    with pytest.raises(errors.PackageIntegrityFailure):
        pkg.validate_rel_path(bad)
    blob = pkg.git_blob_id(b"x")
    with pytest.raises(errors.PackageIntegrityFailure):
        pkg.parse_ls_tree(f"100644 blob {blob}\t{bad}\n")
    with pytest.raises(errors.PackageIntegrityFailure):
        pkg.build_manifest({bad: b"x"}, source_commit=COMMIT, tree_listing=f"100644 blob {blob}\tok.txt\n")


def test_an_innocent_windows_reserved_name_is_refused_too_documented_limitation():
    # Finding #26 is NOT resolved: a legitimate repository file named like a Windows
    # device fails closed with the SAME reason code as tampering. This test pins that
    # behaviour (fail closed) and the fact that it is recorded as a known G0 limit.
    files = {"web/aux.ts": b"export {}\n"}
    with pytest.raises(errors.PackageIntegrityFailure) as e:
        pkg.build_manifest(files, source_commit=COMMIT, tree_listing=listing(files))
    assert e.value.reason_code == "PACKAGE_INTEGRITY_FAILURE"
    from scripts.orchestrator import c3_probe
    limits = " ".join(c3_probe.S4U_SPEC["known_g0_limits"])
    assert "validate_rel_path" in limits and "cannot tell an innocent repository name from a hostile one" in limits


def test_case_insensitive_path_collisions_are_refused():
    files = {"scripts/A.py": b"1", "scripts/a.py": b"2"}
    with pytest.raises(errors.PackageIntegrityFailure) as e:
        pkg.build_manifest(files, source_commit=COMMIT, tree_listing=listing(files))
    assert "collid" in e.value.detail


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(schema="other"),
        lambda d: d.update(extra=1),
        lambda d: d.pop("files"),
        lambda d: d.update(source_commit="xyz"),
        lambda d: d.update(files=[]),
        lambda d: d["files"][0].update(sha256="nope"),
        lambda d: d["files"][0].update(size=-1),
        lambda d: d["files"][0].update(size=True),
        lambda d: d["files"][0].update(path="../x"),
        lambda d: d["files"][0].update(git_blob="1"),
        lambda d: d["files"][0].pop("size"),
        lambda d: d["files"].append(dict(d["files"][0], path=d["files"][0]["path"].upper())),
    ],
)
def test_manifest_parsing_is_strict(mutate):
    doc = json.loads(pkg.build_manifest(FILES, source_commit=COMMIT, tree_listing=listing()).to_bytes())
    mutate(doc)
    with pytest.raises(errors.PackageIntegrityFailure):
        pkg.PackageManifest.from_bytes(json.dumps(doc).encode())


def test_non_json_manifest_is_refused():
    with pytest.raises(errors.PackageIntegrityFailure):
        pkg.PackageManifest.from_bytes(b"\xff\xfe")


def observed_for(files):
    return {p: (hashlib.sha256(d).hexdigest(), len(d)) for p, d in files.items()}


def test_installed_tree_must_match_the_manifest_exactly():
    m = pkg.build_manifest(FILES, source_commit=COMMIT, tree_listing=listing())
    pkg.verify_observed_tree(m, observed_for(FILES))
    changed = observed_for(dict(FILES, **{"scripts/orchestrator/a.py": b"print('x')\n"}))
    extra = dict(observed_for(FILES), **{"scripts/orchestrator/x.py": ("0" * 64, 1)})
    missing = {k: v for k, v in observed_for(FILES).items() if k != "scripts/orchestrator/a.py"}
    for bad in (changed, extra, missing):
        with pytest.raises(errors.PackageIntegrityFailure):
            pkg.verify_observed_tree(m, bad)


def test_scan_tree_hashes_files_and_round_trips_with_the_manifest(tmp_path):
    for rel, data in FILES.items():
        target = tmp_path.joinpath(*rel.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    m = pkg.build_manifest(pkg.scan_tree(str(tmp_path), keep_bytes=True), source_commit=COMMIT, tree_listing=listing())
    pkg.verify_observed_tree(m, pkg.scan_tree(str(tmp_path)))
    (tmp_path / "scripts" / "orchestrator" / "a.py").write_bytes(b"tampered")
    with pytest.raises(errors.PackageIntegrityFailure):
        pkg.verify_observed_tree(m, pkg.scan_tree(str(tmp_path)))


def test_scan_tree_refuses_links_and_enforces_bounds(tmp_path, monkeypatch):
    (tmp_path / "real").mkdir()
    (tmp_path / "real" / "f.txt").write_text("x")
    link = tmp_path / "link"
    try:
        if os.name == "nt":
            import _winapi

            _winapi.CreateJunction(str(tmp_path / "real"), str(link))
        else:
            os.symlink(str(tmp_path / "real"), str(link))
    except OSError:
        pytest.skip("cannot create a link in this environment")
    with pytest.raises(errors.PackageIntegrityFailure) as e:
        pkg.scan_tree(str(tmp_path))
    assert "symlink or reparse" in e.value.detail
    monkeypatch.setattr(pkg, "MAX_FILES", 0)
    (tmp_path / "link").rmdir() if os.name == "nt" else (tmp_path / "link").unlink()
    with pytest.raises(errors.PackageIntegrityFailure):
        pkg.scan_tree(str(tmp_path))


def test_scan_tree_missing_directory_fails_closed(tmp_path):
    with pytest.raises(errors.PackageIntegrityFailure):
        pkg.scan_tree(str(tmp_path / "does-not-exist"))


def test_scan_tree_refuses_unsafe_empty_directory_names(tmp_path):
    (tmp_path / "a~1").mkdir()  # an 8.3-style alias name, even though it holds no file
    with pytest.raises(errors.PackageIntegrityFailure):
        pkg.scan_tree(str(tmp_path))


def test_scan_tree_refuses_a_link_as_the_export_root(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "f.txt").write_text("x")
    link = tmp_path / "rootlink"
    try:
        if os.name == "nt":
            import _winapi

            _winapi.CreateJunction(str(real), str(link))
        else:
            os.symlink(str(real), str(link))
    except OSError:
        pytest.skip("cannot create a link in this environment")
    with pytest.raises(errors.PackageIntegrityFailure) as e:
        pkg.scan_tree(str(link))
    assert "export root" in e.value.detail


def test_scan_tree_bounds_the_bytes_it_actually_reads(tmp_path, monkeypatch):
    (tmp_path / "big.bin").write_bytes(b"x" * 100)
    monkeypatch.setattr(pkg, "MAX_TOTAL_BYTES", 10)
    with pytest.raises(errors.PackageIntegrityFailure) as e:
        pkg.scan_tree(str(tmp_path))
    assert "larger than the allowed maximum" in e.value.detail
