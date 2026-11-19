"""SEC-1B-T synthetic tests for scripts/sec1/sec1b_inspect.py.

Everything here is SYNTHETIC. No real artifact, repository object, credential,
state file or plan is read. Credential-shaped sentinels are assembled from
fragments at runtime. A fake git runner is injected; the real git runner is
only exercised with subprocess patched out.

Run: python -I -B -m unittest discover -s tests/sec1 -t tests/sec1 -v
"""

from __future__ import annotations

import ast
import base64
import builtins
import contextlib
import hashlib
import io
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import types
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest import mock

_SEC1_DIR = Path(__file__).resolve().parents[2] / "scripts" / "sec1"
if str(_SEC1_DIR) not in sys.path:
    sys.path.insert(0, str(_SEC1_DIR))

import sec1b_inspect as insp  # noqa: E402

# ---------------------------------------------------------------------------
# Synthetic sentinels (fragments assembled at runtime)
# ---------------------------------------------------------------------------

REFRESH = "1/" + "/" + "SYNTHREFRESHSENTINEL" + "x" * 10
ACCESS = "ya" + "29." + "SYNTHACCESSSENTINEL" + "y" * 10
AKID = "AK" + "IA" + "SYNTHSENTINEL001"
GCSECRET = "GOCS" + "PX-" + "SYNTHCLIENTSECRET01"
JWT = "ey" + "J" + "SYNTHJWTHEADER00" + "." + "SYNTHJWTPAYLOAD00" + "." + "SYNTHJWTSIG000000"
PEM = "-----BEGIN " + "RSA PRIVATE KEY-----"
EMAIL = "synthetic.sentinel" + "@" + "example.invalid"
STRIPE = "sk_" + "test_" + "SYNTHSTRIPESENT01"
WHSEC = "wh" + "sec_" + "SYNTHWEBHOOKSENT01"
URLCRED = "https://" + "synthuser" + ":" + "synthpass" + "@example.invalid/x"
NAME_SENT = "SYNTHNAMESENT"

FRAGMENTS = (
    "SYNTHREFRESHSENTINEL", "SYNTHACCESSSENTINEL", "SYNTHSENTINEL001", "SYNTHCLIENTSECRET01",
    "SYNTHJWT", "PRIVATE KEY-----", "synthetic.sentinel", "SYNTHSTRIPESENT", "SYNTHWEBHOOKSENT",
    "synthuser", "synthpass", NAME_SENT, "example.invalid", "user-tokens", "main.tf", "tfconfig/",
)

GOOGLE_SECRET_ID = "arn:aws:secretsmanager:us-east-1:000000000000:secret:synth/google/user-tokens-AbCdEf"
S, A = insp.SCOPE_STATE, insp.SCOPE_ARTIFACT

# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def state(resources, version=4, tv="1.8.5", extra=None):
    obj = {"version": version, "terraform_version": tv, "serial": 1, "lineage": "synthetic-lineage",
           "outputs": {}, "resources": resources}
    if extra:
        obj.update(extra)
    return json.dumps(obj).encode("utf-8")


def res(type_, name, attrs, module=None, index_key=None, sensitive=None, private=None, mode="managed",
        inst_extra=None, res_extra=None):
    inst = {"schema_version": 0, "attributes": attrs}
    if index_key is not None:
        inst["index_key"] = index_key
    if sensitive is not None:
        inst["sensitive_attributes"] = sensitive
    if private is not None:
        inst["private"] = private
    if inst_extra:
        inst.update(inst_extra)
    r = {"mode": mode, "type": type_, "name": name, "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
         "instances": [inst]}
    if module:
        r["module"] = module
    if res_extra:
        r.update(res_extra)
    return r


def google_secret(secret_string):
    return res("aws_secretsmanager_secret_version", "google_user_tokens_init",
               {"secret_id": GOOGLE_SECRET_ID, "secret_string": secret_string, "version_id": "v1"},
               module="module.secrets")


def make_zip(entries, compression=zipfile.ZIP_DEFLATED, comment=b""):
    buf = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with zipfile.ZipFile(buf, "w", compression=compression) as zf:
            for e in entries:
                if len(e) == 3:
                    name, data, info_fn = e
                    zi = zipfile.ZipInfo(name)
                    zi.compress_type = compression
                    info_fn(zi)
                    zf.writestr(zi, data)
                else:
                    name, data = e
                    zf.writestr(name, data)
            if comment:
                zf.comment = comment
    return buf.getvalue()


def plan_zip(tfstate=None, tfstate_prev=b"__default__", tfplan=b"\x08\x01synthetic-plan", tfconfig=None,
             lock=b"# synthetic lock\n", extra=(), compression=zipfile.ZIP_DEFLATED, comment=b""):
    entries = [("tfplan", tfplan), ("tfstate", tfstate if tfstate is not None else state([]))]
    if tfstate_prev == b"__default__":
        entries.append(("tfstate-prev", state([])))
    elif tfstate_prev is not None:
        entries.append(("tfstate-prev", tfstate_prev))
    for name, data in (tfconfig if tfconfig is not None else [("tfconfig/main.tf", b"# synthetic\n"),
                                                             ("tfconfig/variables.tf", b"# synthetic\n")]):
        entries.append((name, data))
    if lock is not None:
        entries.append((".terraform.lock.hcl", lock))
    entries.extend(extra)
    return make_zip(entries, compression=compression, comment=comment)


# --- raw header patch helpers ------------------------------------------------


def _iter_headers(b, sig, name_len_off, name_off):
    i = 0
    while True:
        i = b.find(sig, i)
        if i < 0:
            return
        nlen = int.from_bytes(b[i + name_len_off:i + name_len_off + 2], "little")
        yield i, bytes(b[i + name_off:i + name_off + nlen]), i + name_off
        i += 4


def patch_name(data, old, new, local=True, central=True):
    assert len(old) == len(new)
    b = bytearray(data)
    if local:
        for _, nm, at in list(_iter_headers(b, b"PK\x03\x04", 26, 30)):
            if nm == old:
                b[at:at + len(old)] = new
    if central:
        for _, nm, at in list(_iter_headers(b, b"PK\x01\x02", 28, 46)):
            if nm == old:
                b[at:at + len(old)] = new
    return bytes(b)


def patch_local_u16(data, name, field_off, value_or):
    b = bytearray(data)
    for i, nm, _ in list(_iter_headers(b, b"PK\x03\x04", 26, 30)):
        if nm == name:
            cur = int.from_bytes(b[i + field_off:i + field_off + 2], "little")
            b[i + field_off:i + field_off + 2] = (value_or(cur)).to_bytes(2, "little")
    return bytes(b)


def set_encrypted_flag(data, name, local=True, central=True):
    b = bytearray(data)
    if local:
        for i, nm, _ in list(_iter_headers(b, b"PK\x03\x04", 26, 30)):
            if nm == name:
                b[i + 6] |= 0x1
    if central:
        for i, nm, _ in list(_iter_headers(b, b"PK\x01\x02", 28, 46)):
            if nm == name:
                b[i + 8] |= 0x1
    return bytes(b)


def insert_gap(data, junk):
    """Insert unreferenced bytes before the 2nd local header and fix offsets."""
    infos = zipfile.ZipFile(io.BytesIO(data)).infolist()
    at = sorted(i.header_offset for i in infos)[1]
    b = bytearray(data[:at] + junk + data[at:])
    for i, _, _ in list(_iter_headers(b, b"PK\x01\x02", 28, 46)):
        loff = struct.unpack("<I", b[i + 42:i + 46])[0]
        if loff >= at:
            b[i + 42:i + 46] = struct.pack("<I", loff + len(junk))
    pos = b.rfind(b"PK\x05\x06")
    cd = struct.unpack("<I", b[pos + 16:pos + 20])[0]
    b[pos + 16:pos + 20] = struct.pack("<I", cd + len(junk))
    return bytes(b)


FAKE_BLOB = "ab" * 20
FAKE_COMMIT = "cd" * 20


def spec_for(data, ident="ROLLBACK"):
    return insp.ArtifactSpec(ident, FAKE_COMMIT, "infra/prod/tfplan-synthetic", FAKE_BLOB, len(data))


class FakeGit:
    def __init__(self, data, repo_names=("main.tf", "variables.tf"), rev=None, size=None, blob=None,
                 rc=None, raise_exc=None):
        self.data, self.rev, self.size, self.blob = data, rev, size, blob
        self.repo_names = list(repo_names) if repo_names is not None else None
        self.rc = rc or {}
        self.raise_exc = raise_exc
        self.calls = []

    def __call__(self, args):
        self.calls.append(tuple(args))
        if self.raise_exc:
            raise self.raise_exc
        cmd = args[0] if args[0] != "cat-file" else "cat-file " + args[1]
        if self.rc.get(cmd):
            return self.rc[cmd], b""
        if args[0] == "rev-parse":
            return 0, ((self.rev or FAKE_BLOB) + "\n").encode()
        if args[:2] == ["cat-file", "-s"]:
            return 0, (str(self.size if self.size is not None else len(self.data)) + "\n").encode()
        if args[:2] == ["cat-file", "blob"]:
            return 0, self.blob if self.blob is not None else self.data
        if args[0] == "ls-tree":
            if self.repo_names is None:
                return 1, b""
            return 0, "\n".join("infra/prod/" + n for n in self.repo_names).encode()
        return 1, b""


# ---------------------------------------------------------------------------
# Base class: leak + fail-closed assertions on EVERY run
# ---------------------------------------------------------------------------


class _Base(unittest.TestCase):
    maxDiff = None

    def run_one(self, data, locations=True, fake=None, ident="ROLLBACK"):
        fake = fake or FakeGit(data)
        spec = spec_for(data, ident)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            report = insp.inspect_artifact(spec, fake)
            lines = insp.render([report], with_locations=locations)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), "")
        text = "\n".join(lines) + repr(report)
        for frag in FRAGMENTS:
            if frag in text:
                self.fail("sanitized output leaked a synthetic fragment")
        for line in lines:
            self.assertTrue(line.startswith("SEC1B ARTIFACT=%s " % ident))
        self.assert_fail_closed(report, lines)
        return report, lines

    def assert_fail_closed(self, report, lines):
        for line in lines:
            if "STATUS=ABSENT" not in line:
                continue
            if " SCOPE=%s " % S in line:
                self.assertTrue(report.state_cov.complete and not report.state_cov.reasons)
            if " SCOPE=%s " % A in line:
                self.assertTrue(report.state_cov.complete and report.artifact_cov.complete)
            self.assertIn("REASON=FULLY_PARSED_NO_", line)
        if report.entries["TFPLAN"]:
            self.assertFalse(any(" SCOPE=%s " % A in l and "STATUS=ABSENT" in l for l in lines),
                             "whole-artifact ABSENT with opaque tfplan")
            self.assertIn("WHOLE_ARTIFACT_ABSENCE_PROVABLE=NO", "\n".join(lines))

    def stat(self, lines, cid, scope):
        tag = " CATEGORY=%s BASIS=%s SCOPE=%s " % (cid, insp.BASIS[cid], scope)
        for line in lines:
            if tag in line:
                return line.split("STATUS=")[1].split()[0], line.split("REASON=")[1].split()[0]
        self.fail("category line missing")

    def field(self, lines, key):
        for line in lines:
            for tok in line.split():
                if tok.startswith(key + "="):
                    return tok.split("=", 1)[1]
        self.fail("field missing")

    def assert_all_unknown(self, lines):
        for line in lines:
            if " CATEGORY=" in line:
                self.assertNotIn("STATUS=ABSENT", line)


# ---------------------------------------------------------------------------
# Happy path, bases, scopes
# ---------------------------------------------------------------------------


class TestValidPlan(_Base):
    def _full(self):
        st = state([google_secret(json.dumps({"refresh_token": REFRESH, "access_token": ACCESS}))])
        return plan_zip(tfstate=st, tfplan=b"\x0a\x10" + EMAIL.encode() + b"\x12" + AKID.encode())

    def test_valid_plan_categories_and_scopes(self):
        _, lines = self.run_one(self._full())
        self.assertEqual(self.field(lines, "INTEGRITY"), "OK")
        self.assertEqual(self.field(lines, "FORMAT"), "ZIP_SAVED_PLAN")
        self.assertEqual(self.field(lines, "TF_VERSION"), "1.8.5")
        self.assertEqual(self.stat(lines, "GOOGLE_USER_TOKENS_SECRET_TOKENS", S), ("PRESENT", "STRUCTURAL_MATCH"))
        self.assertEqual(self.stat(lines, "GOOGLE_REFRESH_TOKEN", S), ("PRESENT", "POTENTIAL_PATTERN_MATCH"))
        self.assertEqual(self.stat(lines, "OAUTH_REFRESH_TOKEN_FIELD", S), ("PRESENT", "STRUCTURAL_MATCH"))
        self.assertEqual(self.stat(lines, "NAMED_SENSITIVE_ATTRIBUTE_NONEMPTY", S),
                         ("PRESENT", "POTENTIAL_NAME_HEURISTIC_MATCH"))
        self.assertEqual(self.stat(lines, "AWS_ACCESS_KEY_ID", S), ("ABSENT", "FULLY_PARSED_NO_PATTERN_MATCH"))
        self.assertEqual(self.stat(lines, "AWS_ACCESS_KEY_ID", A)[0], "PRESENT")
        self.assertEqual(self.stat(lines, "EMAIL_ADDRESS", A)[0], "PRESENT")
        self.assertEqual(self.stat(lines, "PRIVATE_KEY_PEM", A), ("UNKNOWN", "TFPLAN_NOT_STRUCTURALLY_PARSED"))
        self.assertEqual(self.stat(lines, "TF_SENSITIVE_ATTRIBUTES", S),
                         ("ABSENT", "FULLY_PARSED_NO_STRUCTURAL_MATCH"))

    def test_locations_are_sanitized(self):
        _, lines = self.run_one(self._full(), locations=True)
        locs = [l for l in lines if " LOCATION " in l]
        self.assertTrue(any("ADDRESS=module.secrets.aws_secretsmanager_secret_version.google_user_tokens_init"
                            in l for l in locs))

    def test_no_locations_flag_omits_location_lines(self):
        _, lines = self.run_one(self._full(), locations=False)
        self.assertFalse(any(" LOCATION " in l for l in lines))

    def test_empty_google_secret(self):
        _, lines = self.run_one(plan_zip(tfstate=state([google_secret("{}")])))
        self.assertEqual(self.stat(lines, "GOOGLE_USER_TOKENS_SECRET_TOKENS", S)[0], "ABSENT")
        self.assertEqual(self.stat(lines, "GOOGLE_USER_TOKENS_SECRET_TOKENS", A)[0], "UNKNOWN")
        self.assertEqual(self.stat(lines, "SECRETSMANAGER_SECRET_VALUE", S)[0], "ABSENT")

    def test_unparseable_nested_secret(self):
        _, lines = self.run_one(plan_zip(tfstate=state([google_secret("not-json " + NAME_SENT)])))
        self.assertEqual(self.stat(lines, "GOOGLE_USER_TOKENS_SECRET_TOKENS", S), ("UNKNOWN", "NESTED_SECRET_UNPARSED"))
        self.assertEqual(self.stat(lines, "SECRETSMANAGER_SECRET_VALUE", S)[0], "PRESENT")

    def test_unrecognized_google_secret_shape(self):
        _, lines = self.run_one(plan_zip(tfstate=state([google_secret(json.dumps({"calendar": "x"}))])))
        self.assertEqual(self.stat(lines, "GOOGLE_USER_TOKENS_SECRET_TOKENS", S),
                         ("UNKNOWN", "GOOGLE_TOKENS_SECRET_UNRECOGNIZED_SHAPE"))

    def test_missing_state_prev(self):
        _, lines = self.run_one(plan_zip(tfstate_prev=None))
        self.assertEqual(self.stat(lines, "PRIVATE_KEY_PEM", S), ("UNKNOWN", "STATE_PREV_MISSING"))

    def test_previous_state_is_inspected(self):
        prev = state([res("aws_lambda_function", "admin", {"environment": [{"variables": {"API_SECRET": STRIPE}}]})])
        _, lines = self.run_one(plan_zip(tfstate_prev=prev))
        self.assertEqual(self.stat(lines, "STRIPE_KEY", S)[0], "PRESENT")
        self.assertEqual(self.stat(lines, "LAMBDA_ENV_SECRET_PATTERN", S)[0], "PRESENT")

    def test_all_value_categories_detected(self):
        attrs = {"a": REFRESH, "b": ACCESS, "c": JWT, "d": GCSECRET, "e": "123-abc.apps.googleusercontent.com",
                 "f": AKID, "g": PEM, "h": URLCRED, "i": STRIPE, "j": WHSEC, "k": EMAIL}
        _, lines = self.run_one(plan_zip(tfstate=state([res("synthetic_thing", "x", attrs)])))
        for cid, _ in insp.VALUE_PATTERNS:
            self.assertEqual(self.stat(lines, cid, S)[0], "PRESENT", cid)

    def test_sensitive_attributes_counted(self):
        st = state([res("aws_db_instance", "x", {"password": ""}, sensitive=[[{"type": "get_attr", "value": "password"}]])])
        _, lines = self.run_one(plan_zip(tfstate=st))
        self.assertEqual(self.stat(lines, "TF_SENSITIVE_ATTRIBUTES", S)[0], "PRESENT")

    def test_outputs_scanned(self):
        _, lines = self.run_one(plan_zip(tfstate=state([], extra={"outputs": {"o": {"value": AKID}}})))
        self.assertEqual(self.stat(lines, "AWS_ACCESS_KEY_ID", S)[0], "PRESENT")


class TestSourceAttribution(_Base):
    def test_matching_filenames_never_claim_provenance(self):
        unrelated = [("tfconfig/main.tf", b'resource "other_vendor_thing" "x" {}\n'),
                     ("tfconfig/variables.tf", b'variable "unrelated" {}\n')]
        _, lines = self.run_one(plan_zip(tfconfig=unrelated))
        self.assertEqual(self.field(lines, "SOURCE_HINT"), "ROOT_FILENAMES_MATCH_REPO_COMMIT")
        self.assertEqual(self.field(lines, "PROVENANCE"), "NOT_ESTABLISHED")
        text = "\n".join(lines)
        for word in ("THIS_REPO", "SOURCE_CONFIG=", "PROVENANCE=ESTABLISHED"):
            self.assertNotIn(word, text)

    def test_hint_variants(self):
        data = plan_zip()
        for names, expected in ((("main.tf", "variables.tf"), "ROOT_FILENAMES_MATCH_REPO_COMMIT"),
                                (("main.tf", "budgets.tf"), "ROOT_FILENAMES_PARTIAL_OVERLAP"),
                                (("main.tf", "variables.tf", "extra.tf"), "ROOT_FILENAMES_PARTIAL_OVERLAP"),
                                (("other.tf",), "ROOT_FILENAMES_NO_OVERLAP"),
                                (None, "UNDETERMINED")):
            with self.subTest(expected=expected):
                _, lines = self.run_one(data, fake=FakeGit(data, repo_names=names))
                self.assertEqual(self.field(lines, "SOURCE_HINT"), expected)
                self.assertEqual(self.field(lines, "PROVENANCE"), "NOT_ESTABLISHED")

    def test_no_tfconfig_is_undetermined(self):
        _, lines = self.run_one(plan_zip(tfconfig=[]))
        self.assertEqual(self.field(lines, "SOURCE_HINT"), "UNDETERMINED")


class TestPrivateBlob(_Base):
    def _with_private(self, value):
        return plan_zip(tfstate=state([res("aws_s3_bucket", "b", {"bucket": "x"}, private=value)]))

    def test_valid_private_keeps_state_complete(self):
        pv = base64.b64encode(json.dumps({"schema_version": "1"}).encode()).decode()
        _, lines = self.run_one(self._with_private(pv))
        self.assertEqual(self.stat(lines, "PRIVATE_KEY_PEM", S)[0], "ABSENT")

    def test_private_with_sentinel(self):
        pv = base64.b64encode(json.dumps({"token": ACCESS}).encode()).decode()
        _, lines = self.run_one(self._with_private(pv))
        self.assertEqual(self.stat(lines, "GOOGLE_ACCESS_TOKEN", S)[0], "PRESENT")

    def test_invalid_base64_private(self):
        _, lines = self.run_one(self._with_private("!!not base64!!"))
        self.assertEqual(self.stat(lines, "PRIVATE_KEY_PEM", S), ("UNKNOWN", "STATE_PRIVATE_BLOB_UNDECODABLE"))

    def test_non_json_private(self):
        _, lines = self.run_one(self._with_private(base64.b64encode(b"\x00\x01binary").decode()))
        self.assertEqual(self.stat(lines, "PRIVATE_KEY_PEM", S), ("UNKNOWN", "STATE_PRIVATE_BLOB_NOT_JSON"))


class TestCompleteness(_Base):
    def test_secret_in_dict_key_detected(self):
        st = state([res("synthetic_thing", "x", {"tags": {AKID: "v"}})])
        _, lines = self.run_one(plan_zip(tfstate=st))
        self.assertEqual(self.stat(lines, "AWS_ACCESS_KEY_ID", S)[0], "PRESENT")

    def test_nested_json_string_with_escapes_detected(self):
        escaped = REFRESH.replace("/", "\\/")
        inner = '{"t": "%s"}' % escaped
        st = state([res("aws_iam_policy", "p", {"policy": inner})])
        _, lines = self.run_one(plan_zip(tfstate=st))
        self.assertEqual(self.stat(lines, "GOOGLE_REFRESH_TOKEN", S)[0], "PRESENT")

    def test_base64_text_value_detected(self):
        payload = base64.b64encode(("config " + AKID + " " * 40).encode()).decode()
        st = state([res("synthetic_thing", "x", {"user_data_base64": payload})])
        _, lines = self.run_one(plan_zip(tfstate=st))
        self.assertEqual(self.stat(lines, "AWS_ACCESS_KEY_ID", S)[0], "PRESENT")

    def test_opaque_binary_base64_makes_state_unknown(self):
        payload = base64.b64encode(os.urandom(96)).decode()
        st = state([res("synthetic_thing", "x", {"blob": payload})])
        _, lines = self.run_one(plan_zip(tfstate=st))
        self.assertEqual(self.stat(lines, "PRIVATE_KEY_PEM", S), ("UNKNOWN", "OPAQUE_ENCODED_VALUE"))

    def test_digest_sized_base64_keeps_state_complete(self):
        st = state([res("aws_lambda_function", "f", {"source_code_hash": base64.b64encode(os.urandom(32)).decode()})])
        _, lines = self.run_one(plan_zip(tfstate=st))
        self.assertEqual(self.stat(lines, "PRIVATE_KEY_PEM", S)[0], "ABSENT")

    def test_resource_and_instance_fields_scanned(self):
        st = state([res("synthetic_thing", "x", {}, inst_extra={"dependencies": [AKID]},
                        res_extra={"each": EMAIL})])
        _, lines = self.run_one(plan_zip(tfstate=st))
        self.assertEqual(self.stat(lines, "AWS_ACCESS_KEY_ID", S)[0], "PRESENT")
        self.assertEqual(self.stat(lines, "EMAIL_ADDRESS", S)[0], "PRESENT")

    def test_failed_state_parse_counts_as_not_fully_parsed(self):
        _, lines = self.run_one(plan_zip(tfstate_prev=b"{broken"))
        self.assertEqual(self.stat(lines, "PRIVATE_KEY_PEM", S)[0], "UNKNOWN")

    def test_only_status_function_returns_absent(self):
        tree = ast.parse((_SEC1_DIR / "sec1b_inspect.py").read_text(encoding="utf-8"))
        owners = []
        for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            for node in ast.walk(fn):
                if isinstance(node, ast.Name) and node.id == "ABSENT":
                    owners.append(fn.name)
        self.assertEqual(set(owners), {"status"})

    def test_tfplan_present_never_whole_artifact_absent(self):
        for data in (plan_zip(), plan_zip(tfstate=state([google_secret("{}")])), plan_zip(lock=None)):
            report, lines = self.run_one(data)
            self.assertTrue(report.entries["TFPLAN"])


# ---------------------------------------------------------------------------
# ZIP structure: zipfile-visible and raw-header cases
# ---------------------------------------------------------------------------


class TestArchiveSafety(_Base):
    def test_not_a_zip(self):
        _, lines = self.run_one(b"not a zip " + AKID.encode())
        self.assertEqual(self.field(lines, "FORMAT"), "NOT_ZIP")
        self.assert_all_unknown(lines)
        self.assertEqual(self.stat(lines, "AWS_ACCESS_KEY_ID", A)[0], "PRESENT")

    def test_truncated_zip(self):
        data = plan_zip()
        _, lines = self.run_one(data[: len(data) // 2])
        self.assert_all_unknown(lines)

    def test_crc_corruption(self):
        payload = b"A" * 200
        data = bytearray(make_zip([("tfplan", payload), ("tfstate", state([]))], compression=zipfile.ZIP_STORED))
        data[data.find(payload) + 10] ^= 0xFF
        _, lines = self.run_one(bytes(data))
        self.assert_all_unknown(lines)
        self.assertEqual(self.field(lines, "REASON"), "ENTRY_READ_ERROR")

    def test_encrypted_flag(self):
        data = set_encrypted_flag(plan_zip(extra=[("tfconfig/secret.tf", b"x")]), b"tfconfig/secret.tf")
        report, lines = self.run_one(data)
        self.assertEqual(report.entries["UNSAFE"], 1)
        self.assert_all_unknown(lines)

    def test_unsupported_compression(self):
        def bz(zi):
            zi.compress_type = zipfile.ZIP_BZIP2
        report, lines = self.run_one(plan_zip(extra=[("tfconfig/x.tf", b"x", bz)]))
        self.assertEqual(report.entries["UNSAFE"], 1)
        self.assert_all_unknown(lines)

    def test_unsafe_names(self):
        for name in ("../" + NAME_SENT, "/" + NAME_SENT, "C:/" + NAME_SENT, "tfconfig/../../" + NAME_SENT,
                     "tfconfig/./" + NAME_SENT, NAME_SENT + "a" * 300):
            with self.subTest(kind=name[:4]):
                report, lines = self.run_one(plan_zip(extra=[(name, b"x")]))
                self.assertEqual(report.entries["UNSAFE"], 1)
                self.assert_all_unknown(lines)

    def test_symlink_entry(self):
        def link(zi):
            zi.create_system = 3
            zi.external_attr = (0o120777 << 16)
        report, lines = self.run_one(plan_zip(extra=[("tfconfig/link.tf", b"../../etc", link)]))
        self.assertEqual(report.entries["UNSAFE"], 1)
        self.assert_all_unknown(lines)

    def test_duplicate_and_case_insensitive_duplicate(self):
        for dup in ("tfstate", "TFSTATE"):
            with self.subTest(dup=dup):
                report, lines = self.run_one(plan_zip(extra=[(dup, state([]))]))
                self.assertGreaterEqual(report.entries["UNSAFE"], 1)
                self.assert_all_unknown(lines)

    def test_unexpected_entry_is_scanned_but_unknown(self):
        report, lines = self.run_one(plan_zip(extra=[("notes.txt", AKID.encode())]))
        self.assertEqual(report.entries["UNEXPECTED"], 1)
        self.assertEqual(self.stat(lines, "AWS_ACCESS_KEY_ID", A)[0], "PRESENT")
        self.assert_all_unknown(lines)

    def test_missing_tfstate(self):
        _, lines = self.run_one(make_zip([("tfplan", b"x")]))
        self.assertEqual(self.field(lines, "FORMAT"), "UNKNOWN")
        self.assert_all_unknown(lines)

    def test_compression_ratio_bomb(self):
        _, lines = self.run_one(plan_zip(extra=[("tfconfig/bomb.tf", b"\x00" * (5 * 1024 * 1024))]))
        self.assertEqual(self.field(lines, "REASON"), "COMPRESSION_RATIO_EXCEEDED")
        self.assert_all_unknown(lines)

    def test_entry_and_total_and_count_limits(self):
        with mock.patch.object(insp, "MAX_ENTRY_BYTES", 1000):
            _, lines = self.run_one(plan_zip(extra=[("tfconfig/big.tf", os.urandom(4000))]))
            self.assertEqual(self.field(lines, "REASON"), "ENTRY_TOO_LARGE")
        with mock.patch.object(insp, "MAX_TOTAL_BYTES", 2000):
            _, lines = self.run_one(plan_zip(extra=[("tfconfig/a.tf", os.urandom(1500)),
                                                    ("tfconfig/b.tf", os.urandom(1500))]))
            self.assertEqual(self.field(lines, "REASON"), "TOTAL_TOO_LARGE")
        with mock.patch.object(insp, "MAX_ENTRIES", 5):
            _, lines = self.run_one(plan_zip(extra=[("tfconfig/%d.tf" % i, b"x") for i in range(5)]))
            self.assertEqual(self.field(lines, "REASON"), "TOO_MANY_ENTRIES")


class TestRawZipHeaders(_Base):
    BASE_NAME = b"tfconfig/aXb.tf"

    def _base(self, **kw):
        return plan_zip(extra=[(self.BASE_NAME.decode(), b"# x\n")], **kw)

    def _assert_raw_failure(self, data, expected_code=None):
        report, lines = self.run_one(data)
        self.assert_all_unknown(lines)
        self.assertNotEqual(self.field(lines, "FORMAT"), "ZIP_SAVED_PLAN")
        if expected_code:
            reasons = report.state_cov.reasons + report.artifact_cov.reasons + [report.fmt_reason]
            self.assertIn(expected_code, reasons)
        return report, lines

    def test_embedded_nul_in_raw_name(self):
        data = patch_name(self._base(), self.BASE_NAME, b"tfconfig/a\x00b.tf")
        report, _ = self._assert_raw_failure(data, "RAW_NAME_NOT_PRINTABLE_ASCII")
        self.assertGreaterEqual(report.entries["UNSAFE"], 1)

    def test_backslash_in_raw_name(self):
        data = patch_name(self._base(), self.BASE_NAME, b"tfconfig/a\\b.tf")
        report, _ = self._assert_raw_failure(data)
        self.assertGreaterEqual(report.entries["UNSAFE"], 1)

    def test_non_ascii_name(self):
        report, _ = self._assert_raw_failure(plan_zip(extra=[("tfconfig/\u00e9.tf", b"x")]),
                                             "RAW_NAME_NOT_PRINTABLE_ASCII")
        self.assertGreaterEqual(report.entries["UNSAFE"], 1)

    def test_local_central_name_mismatch(self):
        data = patch_name(self._base(), self.BASE_NAME, b"tfconfig/aYb.tf", central=False)
        self._assert_raw_failure(data, "LOCAL_CENTRAL_NAME_MISMATCH")

    def test_local_central_flags_mismatch(self):
        data = set_encrypted_flag(self._base(), self.BASE_NAME, central=False)
        self._assert_raw_failure(data, "LOCAL_CENTRAL_FLAGS_MISMATCH")

    def test_local_central_method_mismatch(self):
        data = patch_local_u16(self._base(), self.BASE_NAME, 8, lambda cur: 0 if cur else 8)
        self._assert_raw_failure(data, "LOCAL_CENTRAL_METHOD_MISMATCH")

    def test_prefix_data(self):
        self._assert_raw_failure(b"JUNKJUNK" + self._base())

    def test_trailing_bytes(self):
        self._assert_raw_failure(self._base() + b"TRAILINGJUNK")

    def test_archive_comment(self):
        self._assert_raw_failure(self._base(comment=b"synthetic comment"), "ARCHIVE_COMMENT_PRESENT")

    def test_unrecognized_extra_field(self):
        def ex(zi):
            zi.extra = struct.pack("<HH", 0x9999, 2) + b"ab"
        self._assert_raw_failure(plan_zip(extra=[("tfconfig/e.tf", b"x", ex)]), "EXTRA_FIELD_UNRECOGNIZED")

    def test_unicode_path_extra_field(self):
        def ex(zi):
            uname = b"tfconfig/other.tf"
            body = b"\x01" + struct.pack("<I", 0) + uname
            zi.extra = struct.pack("<HH", 0x7075, len(body)) + body
        self._assert_raw_failure(plan_zip(extra=[("tfconfig/e.tf", b"x", ex)]))

    def test_unreferenced_gap_between_entries(self):
        data = insert_gap(make_zip([("tfplan", b"x"), ("tfstate", state([])), ("tfstate-prev", state([]))],
                                   compression=zipfile.ZIP_STORED), b"HIDDEN" + AKID.encode())
        self._assert_raw_failure(data, "UNREFERENCED_ARCHIVE_BYTES")

    def test_overlapping_entries(self):
        data = bytearray(make_zip([("tfplan", b"x"), ("tfstate", state([])), ("tfstate-prev", state([]))],
                                  compression=zipfile.ZIP_STORED))
        heads = list(_iter_headers(data, b"PK\x01\x02", 28, 46))
        first_loff = data[heads[0][0] + 42:heads[0][0] + 46]
        data[heads[1][0] + 42:heads[1][0] + 46] = first_loff
        report, _ = self._assert_raw_failure(bytes(data))
        reasons = report.state_cov.reasons + report.artifact_cov.reasons
        self.assertTrue(set(reasons) & {"OVERLAPPING_ENTRIES", "LOCAL_CENTRAL_NAME_MISMATCH"})

    def test_library_warning_is_fail_closed_not_printed(self):
        def warn_open(*a, **k):
            import warnings as _w
            _w.warn("synthetic zipfile warning", UserWarning)
            raise AssertionError("unreachable")
        data = plan_zip()
        with mock.patch.object(zipfile.ZipFile, "open", warn_open):
            report, lines = self.run_one(data)
        self.assertIn("ZIP_LIBRARY_WARNING", report.state_cov.reasons)
        self.assert_all_unknown(lines)

    def test_entry_count_mismatch_direct(self):
        data = bytearray(self._base())
        pos = data.rfind(b"PK\x05\x06")
        cnt = struct.unpack("<H", data[pos + 10:pos + 12])[0]
        data[pos + 8:pos + 12] = struct.pack("<HH", cnt + 1, cnt + 1)
        infos = zipfile.ZipFile(io.BytesIO(self._base())).infolist()
        self.assertTrue(set(insp.raw_zip_audit(bytes(data), infos)) & {"ENTRY_COUNT_MISMATCH", "CENTRAL_HEADER_INVALID"})

    def test_zip64_markers_direct(self):
        data = bytearray(self._base())
        pos = data.rfind(b"PK\x05\x06")
        data[pos + 10:pos + 12] = struct.pack("<H", 0xFFFF)
        self.assertIn("ZIP64_NOT_AUDITED", insp.raw_zip_audit(bytes(data), []))

    def _eocd(self, data):
        return data.rfind(b"PK\x05\x06")

    def test_every_raw_reason_reaches_both_scopes(self):
        data = b"JUNKJUNK" + self._base(comment=b"c")
        infos = zipfile.ZipFile(io.BytesIO(data)).infolist()
        expected = insp.raw_zip_audit(data, infos)
        self.assertGreaterEqual(len(expected), 2)
        report, _ = self._assert_raw_failure(data)
        for code in expected:
            self.assertIn(code, report.state_cov.reasons)
            self.assertIn(code, report.artifact_cov.reasons)

    def test_central_metadata_mismatch_direct(self):
        data = self._base()
        infos = zipfile.ZipFile(io.BytesIO(data)).infolist()
        infos[0].file_size += 1
        self.assertIn("CENTRAL_METADATA_MISMATCH", insp.raw_zip_audit(data, infos))

    def test_local_central_crc_mismatch(self):
        data = patch_local_u16(self._base(), self.BASE_NAME, 14, lambda cur: cur ^ 0xFFFF)
        self._assert_raw_failure(data, "LOCAL_CENTRAL_SIZE_MISMATCH")

    def test_multi_disk_direct(self):
        clean = self._base()
        data = bytearray(clean)
        pos = self._eocd(data)
        data[pos + 4:pos + 6] = struct.pack("<H", 1)
        infos = zipfile.ZipFile(io.BytesIO(clean)).infolist()
        self.assertIn("MULTI_DISK_ARCHIVE", insp.raw_zip_audit(bytes(data), infos))

    def test_central_directory_misplaced_direct(self):
        clean = self._base()
        data = bytearray(clean)
        pos = self._eocd(data)
        size = struct.unpack("<I", data[pos + 12:pos + 16])[0]
        data[pos + 12:pos + 16] = struct.pack("<I", size + 1)
        infos = zipfile.ZipFile(io.BytesIO(clean)).infolist()
        self.assertIn("CENTRAL_DIRECTORY_MISPLACED", insp.raw_zip_audit(bytes(data), infos))

    def test_entry_count_mismatch_vs_library_view(self):
        data = self._base()
        infos = zipfile.ZipFile(io.BytesIO(data)).infolist()
        self.assertIn("ENTRY_COUNT_MISMATCH", insp.raw_zip_audit(data, infos[:-1]))

    def test_two_central_entries_sharing_one_local_header(self):
        data = bytearray(make_zip([("dup", b"same"), ("dup", b"same")], compression=zipfile.ZIP_STORED))
        heads = list(_iter_headers(data, b"PK\x01\x02", 28, 46))
        data[heads[1][0] + 42:heads[1][0] + 46] = data[heads[0][0] + 42:heads[0][0] + 46]
        data = bytes(data)
        infos = zipfile.ZipFile(io.BytesIO(data)).infolist()
        self.assertIn("OVERLAPPING_ENTRIES", insp.raw_zip_audit(data, infos))

    def test_entry_comment(self):
        def cm(zi):
            zi.comment = b"synthetic"
        self._assert_raw_failure(plan_zip(extra=[("tfconfig/c.tf", b"x", cm)]), "ENTRY_COMMENT_PRESENT")

    def test_entry_size_mismatch_direct(self):
        info = types.SimpleNamespace(file_size=10, compress_size=10)
        zf = types.SimpleNamespace(open=lambda i, m: io.BytesIO(b"x" * 5))
        with self.assertRaises(insp.InspectionError) as ctx:
            insp.read_entry_limited(zf, info, [0])
        self.assertEqual(ctx.exception.code, "ENTRY_SIZE_MISMATCH")

    def test_zipfile_open_warning_is_fail_closed(self):
        data = plan_zip()
        real = zipfile.ZipFile

        def warn_ctor(*a, **k):
            warnings.warn("synthetic zipfile warning", UserWarning)
            return real(*a, **k)

        with mock.patch.object(insp.zipfile, "ZipFile", warn_ctor):
            _, lines = self.run_one(data)
        self.assertEqual(self.field(lines, "FORMAT"), "NOT_ZIP")
        self.assert_all_unknown(lines)

    def test_clean_archive_has_no_raw_reasons(self):
        data = self._base()
        self.assertEqual(insp.raw_zip_audit(data, zipfile.ZipFile(io.BytesIO(data)).infolist()), [])


class TestFailClosedGuards(_Base):
    """Guards that are otherwise masked by the always-opaque tfplan entry."""

    def test_silently_skipped_state_is_not_fully_parsed(self):
        with mock.patch.object(insp, "inspect_state", lambda data, report: None):
            _, lines = self.run_one(plan_zip())
        self.assertEqual(self.stat(lines, "PRIVATE_KEY_PEM", S), ("UNKNOWN", "STATE_NOT_FULLY_PARSED"))

    def test_scan_only_entries_record_their_reason(self):
        report, _ = self.run_one(plan_zip(extra=[("notes.txt", b"x")]))
        for code in ("TFCONFIG_PATTERN_SCAN_ONLY", "LOCKFILE_PATTERN_SCAN_ONLY", "UNEXPECTED_ENTRY_NOT_PARSED",
                     "TFPLAN_NOT_STRUCTURALLY_PARSED"):
            self.assertIn(code, report.artifact_cov.reasons)

    def test_artifact_scope_requires_state_coverage(self):
        r = insp.ArtifactReport("ROLLBACK")
        r.state_cov.fail("STATE_PREV_MISSING")
        self.assertEqual(insp.artifact_status(r, "PRIVATE_KEY_PEM"), ("UNKNOWN", "STATE_PREV_MISSING"))
        self.assertEqual(insp.artifact_status(insp.ArtifactReport("ROLLBACK"), "PRIVATE_KEY_PEM")[0], "ABSENT")

    def test_integrity_or_internal_error_is_unknown_even_if_covered(self):
        for attr, val in (("integrity", "SIZE_MISMATCH"), ("internal_error", "X")):
            with self.subTest(attr=attr):
                r = insp.ArtifactReport("ROLLBACK")
                r.integrity = "OK"
                setattr(r, attr, val)
                self.assertTrue(insp.any_unknown([r]))
        ok = insp.ArtifactReport("ROLLBACK")
        ok.integrity = "OK"
        self.assertFalse(insp.any_unknown([ok]))


class TestStateMalformed(_Base):
    def _unknown(self, lines, reason=None):
        s, r = self.stat(lines, "PRIVATE_KEY_PEM", S)
        self.assertEqual(s, "UNKNOWN")
        if reason:
            self.assertEqual(r, reason)

    def test_invalid_utf8(self):
        _, lines = self.run_one(plan_zip(tfstate=b"\xff\xfe" + AKID.encode()))
        self._unknown(lines, "STATE_NOT_UTF8")
        self.assertEqual(self.stat(lines, "AWS_ACCESS_KEY_ID", S)[0], "PRESENT")

    def test_not_json(self):
        _, lines = self.run_one(plan_zip(tfstate=b"{not json " + EMAIL.encode()))
        self._unknown(lines, "STATE_NOT_JSON")

    def test_duplicate_json_keys(self):
        _, lines = self.run_one(plan_zip(tfstate=b'{"version": 4, "version": 4, "resources": []}'))
        self._unknown(lines, "JSON_DUPLICATE_KEY")

    def test_too_deep(self):
        deep = {"version": 4, "resources": []}
        cur = deep
        for _ in range(40):
            cur["n"] = {}
            cur = cur["n"]
        with mock.patch.object(insp, "MAX_JSON_DEPTH", 10):
            _, lines = self.run_one(plan_zip(tfstate=json.dumps(deep).encode()))
        self._unknown(lines, "JSON_TOO_DEEP")

    def test_unsupported_shapes(self):
        for blob in (state([], version=3), json.dumps({"version": 4, "resources": {}}).encode(), b"[1, 2]"):
            with self.subTest(n=len(blob)):
                _, lines = self.run_one(plan_zip(tfstate=blob))
                self._unknown(lines, "STATE_UNSUPPORTED_SHAPE")

    def test_bad_attributes_flat_and_unknown_field(self):
        cases = (([{"mode": "managed", "type": "t", "name": "n", "instances": [{"attributes": "x"}]}],
                  "STATE_ATTRIBUTES_UNPARSED"),
                 ([{"mode": "managed", "type": "t", "name": "n", "instances": [{"attributes_flat": {"k": AKID}}]}],
                  "STATE_LEGACY_FLAT_ATTRIBUTES"),
                 ([{"mode": "managed", "type": "t", "name": "n", "instances": [{"attributes": {}, "mystery": 1}]}],
                  "STATE_INSTANCE_UNKNOWN_FIELD"))
        for resources, reason in cases:
            with self.subTest(reason=reason):
                _, lines = self.run_one(plan_zip(tfstate=json.dumps({"version": 4, "resources": resources}).encode()))
                self._unknown(lines, reason)


class TestSanitization(_Base):
    def test_quoted_index_key_redacted(self):
        _, lines = self.run_one(plan_zip(tfstate=state([res("aws_s3_bucket", "b", {"bucket": AKID}, index_key=NAME_SENT)])))
        self.assertTrue(any("ADDRESS=<redacted>" in l for l in lines if " LOCATION " in l))

    def test_credential_like_env_name_redacted(self):
        st = state([res("aws_lambda_function", "admin", {"environment": [{"variables": {"x_" + WHSEC: STRIPE}}]})])
        _, lines = self.run_one(plan_zip(tfstate=st))
        self.assertTrue(any("PATH=environment[0].variables.<redacted>" in l for l in lines))

    def test_integer_index_and_module(self):
        st = state([res("aws_s3_bucket", "b", {"bucket": AKID}, module="module.m[2]", index_key=3)])
        _, lines = self.run_one(plan_zip(tfstate=st))
        self.assertTrue(any("ADDRESS=module.m[2].aws_s3_bucket.b[3]" in l for l in lines))

    def test_entry_names_never_printed(self):
        _, lines = self.run_one(plan_zip(tfconfig=[("tfconfig/" + NAME_SENT + ".tf", b"x")]))
        self.assertFalse(any(NAME_SENT in l for l in lines))


class TestIntegrity(_Base):
    def test_object_mismatch(self):
        data = plan_zip()
        fake = FakeGit(data, rev="ef" * 20)
        report, lines = self.run_one(data, fake=fake)
        self.assertEqual(report.integrity, "OBJECT_MISMATCH")
        self.assertNotIn(("cat-file", "blob", FAKE_BLOB), fake.calls)
        self.assert_all_unknown(lines)

    def test_size_and_git_errors(self):
        data = plan_zip()
        for fake, expected in ((FakeGit(data, size=len(data) + 1), "SIZE_MISMATCH"),
                               (FakeGit(data, blob=data[:-1]), "SIZE_MISMATCH"),
                               (FakeGit(data, rc={"rev-parse": 128}), "GIT_ERROR")):
            with self.subTest(expected=expected):
                report, lines = self.run_one(data, fake=fake)
                self.assertEqual(report.integrity, expected)
                self.assert_all_unknown(lines)

    def test_internal_error_class_only(self):
        data = plan_zip()
        report, lines = self.run_one(data, fake=FakeGit(data, raise_exc=RuntimeError(AKID + NAME_SENT)))
        self.assertEqual(report.internal_error, "INTERNAL_ERROR:RuntimeError")
        self.assert_all_unknown(lines)


class TestDeterminism(_Base):
    def test_entry_order_does_not_change_output(self):
        st = state([google_secret(json.dumps({"refresh_token": REFRESH}))])
        a = make_zip([("tfplan", b"x"), ("tfstate", st), ("tfstate-prev", state([])),
                      ("tfconfig/main.tf", b"x"), ("tfconfig/variables.tf", b"x")])
        b = make_zip([("tfconfig/variables.tf", b"x"), ("tfstate-prev", state([])), ("tfconfig/main.tf", b"x"),
                      ("tfstate", st), ("tfplan", b"x")])
        self.assertEqual(self.run_one(a)[1], self.run_one(b)[1])


# ---------------------------------------------------------------------------
# Git runner, execution integrity, CLI
# ---------------------------------------------------------------------------


class TestGitRunner(unittest.TestCase):
    def test_allowlist_rejects_everything_else(self):
        for args in (["cat-file", "blob", "HEAD"], ["show", "x"], ["rev-parse", "HEAD"], ["cat-file", "-p", "ab" * 20],
                     ["ls-tree", "--name-only", "HEAD", "--", "infra/prod/"], ["fetch"],
                     ["cat-file", "blob", "ab" * 20, "x"]):
            with self.subTest(args=args[0]):
                with self.assertRaises(insp.InspectionError):
                    insp._assert_allowed_git_args(args)

    def test_runner_invocation_is_offline_and_quiet(self):
        captured = {}

        def fake_run(argv, **kw):
            captured["argv"], captured["kw"] = argv, kw
            return subprocess.CompletedProcess(argv, 0, stdout=b"ok")

        with mock.patch.dict(os.environ, {"GIT_TRACE": "1", "GIT_TRACE_PACKET": "1"}):
            with mock.patch.object(insp.subprocess, "run", fake_run):
                spec = insp.ARTIFACTS[0]
                rc, out = insp.make_git_runner("C:/synthetic/repo")(["rev-parse", "%s:%s" % (spec.commit, spec.path)])
        argv, kw = captured["argv"], captured["kw"]
        self.assertEqual((rc, out), (0, b"ok"))
        self.assertIn("protocol.allow=never", argv)
        self.assertIs(kw["shell"], False)
        self.assertEqual(kw["stderr"], subprocess.DEVNULL)
        self.assertEqual(kw["stdin"], subprocess.DEVNULL)
        self.assertEqual(kw["env"]["GIT_NO_LAZY_FETCH"], "1")
        self.assertFalse(any(k.upper().startswith("GIT_TRACE") for k in kw["env"]))

    def test_pinned_specs_are_exact(self):
        self.assertEqual([a.ident for a in insp.ARTIFACTS], ["ROLLBACK", "FRONTEND", "USMH"])
        for a in insp.ARTIFACTS:
            self.assertRegex(a.commit, r"^[0-9a-f]{40}$")
            self.assertRegex(a.blob, r"^[0-9a-f]{40}$")


class _Flags:
    def __init__(self, isolated=1, no_site=1):
        self.isolated, self.no_site = isolated, no_site


class TestRuntimeCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.lib = os.path.join(self.tmp, "Lib")
        os.makedirs(self.lib)

    def _mod(self, origin):
        return types.SimpleNamespace(__spec__=types.SimpleNamespace(origin=origin))

    def _check(self, **kw):
        args = dict(flags=_Flags(), version=(3, 13), modules={"json": self._mod(os.path.join(self.lib, "json.py"))},
                    stdlib_dirs=[os.path.normcase(os.path.abspath(self.lib))], dont_write_bytecode=True)
        args.update(kw)
        return insp.check_runtime(**args)

    def test_good_runtime(self):
        self.assertIsNone(self._check())

    def test_requires_isolated_no_site_and_no_bytecode(self):
        self.assertEqual(self._check(flags=_Flags(isolated=0)), "RUN_WITH_python_-I_-B_-S")
        self.assertEqual(self._check(flags=_Flags(no_site=0)), "RUN_WITH_python_-I_-B_-S")
        self.assertEqual(self._check(dont_write_bytecode=False), "RUN_WITH_python_-I_-B_-S")

    def test_old_python(self):
        self.assertEqual(self._check(version=(3, 9)), "PYTHON_TOO_OLD")

    def test_network_module_loaded(self):
        mods = {"socket": self._mod(os.path.join(self.lib, "socket.py"))}
        self.assertEqual(self._check(modules=mods), "NETWORK_MODULE_LOADED")

    def test_shadowed_module_origin(self):
        mods = {"json": self._mod(os.path.join(self.tmp, "evil", "json.py"))}
        self.assertEqual(self._check(modules=mods), "MODULE_ORIGIN_UNTRUSTED")

    def test_builtin_and_frozen_origins_ok(self):
        mods = {"json": self._mod("built-in"), "os": self._mod("frozen")}
        self.assertIsNone(self._check(modules=mods))


class TestCli(unittest.TestCase):
    def _main(self, args, data=None, runtime=lambda: None):
        data = data or plan_zip()
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "copy.py"
            script.write_bytes(b"synthetic script bytes")
            good = hashlib.sha256(b"synthetic script bytes").hexdigest()
            argv = [a.replace("<GOOD>", good) for a in args]
            with mock.patch.object(insp, "ARTIFACTS", (spec_for(data),)):
                rc = insp.main(argv, runner_factory=lambda repo: FakeGit(data), self_path=str(script), out=out,
                               runtime_check=runtime)
        return rc, out.getvalue()

    def test_good_hash_runs(self):
        rc, text = self._main(["--repo", "x", "--expected-script-sha256", "<GOOD>"])
        self.assertEqual(rc, 1)
        self.assertIn("SEC1B SELF_CHECK=OK", text)
        self.assertIn("SEC1B RESULT=INCOMPLETE_OR_UNKNOWN", text)
        self.assertTrue(all(l.startswith("SEC1B ") for l in text.splitlines()))

    def test_hash_mismatch_refuses(self):
        rc, text = self._main(["--repo", "x", "--expected-script-sha256", "0" * 64])
        self.assertEqual(rc, 2)
        self.assertIn("SELF_CHECK=MISMATCH", text)
        self.assertNotIn("ARTIFACT=", text)

    def test_runtime_refusal_happens_before_hash_or_git(self):
        with mock.patch.object(insp, "script_sha256", side_effect=AssertionError("must not hash")):
            rc, text = self._main(["--repo", "x", "--expected-script-sha256", "<GOOD>"],
                                  runtime=lambda: "RUN_WITH_python_-I_-B_-S")
        self.assertEqual(rc, 2)
        self.assertIn("SEC1B REFUSED=RUN_WITH_python_-I_-B_-S", text)
        self.assertNotIn("ARTIFACT=", text)

    def test_bad_args(self):
        self.assertEqual(self._main(["--repo", "x", "--expected-script-sha256", "zz"])[0], 2)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self._main(["--repo", "x"])[0], 2)


# ---------------------------------------------------------------------------
# No side effects and source audit
# ---------------------------------------------------------------------------


class _Trip(Exception):
    pass


def _trip(*a, **k):
    raise _Trip("side effect")


class TestNoSideEffects(unittest.TestCase):
    def test_inspection_has_no_io_network_or_subprocess(self):
        data = plan_zip(tfstate=state([google_secret(json.dumps({"refresh_token": REFRESH}))]))
        patches = [mock.patch.object(builtins, "open", _trip), mock.patch.object(io, "open", _trip),
                   mock.patch.object(os, "open", _trip), mock.patch.object(os, "remove", _trip),
                   mock.patch.object(os, "rename", _trip), mock.patch.object(os, "mkdir", _trip),
                   mock.patch.object(os, "makedirs", _trip), mock.patch.object(tempfile, "mkstemp", _trip),
                   mock.patch.object(tempfile, "NamedTemporaryFile", _trip),
                   mock.patch.object(socket, "socket", _trip), mock.patch.object(socket, "create_connection", _trip),
                   mock.patch.object(subprocess, "run", _trip), mock.patch.object(subprocess, "Popen", _trip)]
        before = sorted(os.listdir(tempfile.gettempdir()))
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            report = insp.inspect_artifact(spec_for(data), FakeGit(data))
            lines = insp.render([report], with_locations=True)
        self.assertIsNone(report.internal_error)
        self.assertTrue(lines)
        self.assertEqual(set(os.listdir(tempfile.gettempdir())) - set(before), set())


_ALLOWED_IMPORTS = {"__future__", "argparse", "base64", "binascii", "hashlib", "io", "json", "os", "re",
                    "stat", "struct", "subprocess", "sys", "sysconfig", "warnings", "zipfile", "zlib",
                    "dataclasses", "typing"}


class TestSourceAudit(unittest.TestCase):
    def setUp(self):
        self.src = (_SEC1_DIR / "sec1b_inspect.py").read_text(encoding="utf-8")
        self.tree = ast.parse(self.src)

    def test_imports_stdlib_allowlist(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                mods = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                mods = {(node.module or "").split(".")[0]}
            else:
                continue
            self.assertTrue(mods <= _ALLOWED_IMPORTS, mods)

    def test_open_only_in_script_sha256_and_no_print(self):
        for fn in [n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef)]:
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id == "open":
                        self.assertEqual(fn.name, "script_sha256")
                    self.assertNotEqual(node.func.id, "print")

    def test_subprocess_only_in_git_runner(self):
        for fn in [n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef)]:
            for node in ast.walk(fn):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                        and node.value.id == "subprocess" and node.attr in ("run", "Popen", "call", "check_output"):
                    self.assertIn(fn.name, ("runner", "make_git_runner"))
        self.assertNotIn("shell=True", self.src)

    def test_no_extraction_or_write_apis(self):
        for needle in (".extract(", ".extractall(", "write_bytes", "write_text", "urlopen", "import socket"):
            self.assertNotIn(needle, self.src)

    def test_procedure_and_residual_risks_documented(self):
        for needle in ("Pagefile", "Crash dumps", "Antivirus", "Memory", "certutil -hashfile", "-I -B -S",
                       "cat-file blob <REVIEWED_HEAD>"):
            self.assertIn(needle, self.src)


if __name__ == "__main__":
    unittest.main()
