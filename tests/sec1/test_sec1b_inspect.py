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
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
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

# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def state(resources, version=4, tv="1.8.5", extra=None):
    obj = {"version": version, "terraform_version": tv, "serial": 1, "lineage": "synthetic-lineage",
           "outputs": {}, "resources": resources}
    if extra:
        obj.update(extra)
    return json.dumps(obj).encode("utf-8")


def res(type_, name, attrs, module=None, index_key=None, sensitive=None, private=None, mode="managed"):
    inst = {"schema_version": 0, "attributes": attrs}
    if index_key is not None:
        inst["index_key"] = index_key
    if sensitive is not None:
        inst["sensitive_attributes"] = sensitive
    if private is not None:
        inst["private"] = private
    r = {"mode": mode, "type": type_, "name": name, "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
         "instances": [inst]}
    if module:
        r["module"] = module
    return r


def google_secret(secret_string):
    return res("aws_secretsmanager_secret_version", "google_user_tokens_init",
               {"secret_id": GOOGLE_SECRET_ID, "secret_string": secret_string, "version_id": "v1"},
               module="module.secrets")


def make_zip(entries, compression=zipfile.ZIP_DEFLATED):
    buf = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with zipfile.ZipFile(buf, "w", compression=compression) as zf:
            for e in entries:
                if isinstance(e, zipfile.ZipInfo):
                    zf.writestr(e, b"payload")
                elif len(e) == 3:
                    name, data, info_fn = e
                    zi = zipfile.ZipInfo(name)
                    zi.compress_type = compression
                    info_fn(zi)
                    zf.writestr(zi, data)
                else:
                    name, data = e
                    zf.writestr(name, data)
    return buf.getvalue()


def plan_zip(tfstate=None, tfstate_prev=b"__default__", tfplan=b"\x08\x01synthetic-plan", tfconfig=None,
             lock=b"# synthetic lock\n", extra=()):
    entries = [("tfplan", tfplan)]
    entries.append(("tfstate", tfstate if tfstate is not None else state([])))
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
    return make_zip(entries)


def set_encrypted_flag(data, name):
    """Set the 'encrypted' general-purpose flag for one entry in both headers."""
    b, nb = bytearray(data), name.encode()
    i = 0
    while True:
        i = b.find(b"PK\x03\x04", i)
        if i < 0:
            break
        nlen = int.from_bytes(b[i + 26:i + 28], "little")
        if bytes(b[i + 30:i + 30 + nlen]) == nb:
            b[i + 6] |= 0x1
        i += 4
    i = 0
    while True:
        i = b.find(b"PK\x01\x02", i)
        if i < 0:
            break
        nlen = int.from_bytes(b[i + 28:i + 30], "little")
        if bytes(b[i + 46:i + 46 + nlen]) == nb:
            b[i + 8] |= 0x1
        i += 4
    return bytes(b)


FAKE_BLOB = "ab" * 20
FAKE_COMMIT = "cd" * 20


def spec_for(data, ident="ROLLBACK"):
    return insp.ArtifactSpec(ident, FAKE_COMMIT, "infra/prod/tfplan-synthetic", FAKE_BLOB, len(data))


class FakeGit:
    """Injected runner emulating the four allowed git commands."""

    def __init__(self, data, repo_names=("main.tf", "variables.tf"), rev=None, size=None, blob=None,
                 rc=None, raise_exc=None):
        self.data = data
        self.repo_names = list(repo_names) if repo_names is not None else None
        self.rev = rev
        self.size = size
        self.blob = blob
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
# Base class with leak + fail-closed assertions
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
            if " SCOPE=STATE " in line and "STATUS=ABSENT" in line:
                self.assertTrue(report.state_cov.complete, "STATE ABSENT emitted while incomplete")
            if " SCOPE=ARTIFACT " in line and "STATUS=ABSENT" in line:
                self.assertTrue(report.state_cov.complete and report.artifact_cov.complete,
                                "ARTIFACT ABSENT emitted while incomplete")

    def stat(self, lines, cid, scope):
        tag = " CATEGORY=%s SCOPE=%s " % (cid, scope)
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


# ---------------------------------------------------------------------------
# Happy path and category behavior
# ---------------------------------------------------------------------------


class TestValidPlan(_Base):
    def _full(self):
        st = state([google_secret(json.dumps({"refresh_token": REFRESH, "access_token": ACCESS}))])
        return plan_zip(tfstate=st, tfplan=b"\x0a\x10" + EMAIL.encode() + b"\x12" + AKID.encode())

    def test_valid_plan_categories_and_scopes(self):
        report, lines = self.run_one(self._full())
        self.assertEqual(self.field(lines, "INTEGRITY"), "OK")
        self.assertEqual(self.field(lines, "FORMAT"), "ZIP_SAVED_PLAN")
        self.assertEqual(self.field(lines, "TF_VERSION"), "1.8.5")
        self.assertEqual(self.field(lines, "SOURCE_CONFIG"), "THIS_REPO_MATCH")
        self.assertEqual(self.stat(lines, "GOOGLE_USER_TOKENS_SECRET_TOKENS", "STATE")[0], "PRESENT")
        self.assertEqual(self.stat(lines, "GOOGLE_REFRESH_TOKEN", "STATE")[0], "PRESENT")
        self.assertEqual(self.stat(lines, "GOOGLE_ACCESS_TOKEN", "STATE")[0], "PRESENT")
        self.assertEqual(self.stat(lines, "OAUTH_REFRESH_TOKEN_FIELD", "STATE")[0], "PRESENT")
        self.assertEqual(self.stat(lines, "SECRETSMANAGER_SECRET_VALUE", "STATE")[0], "PRESENT")
        # Only in tfplan bytes: STATE absent (state fully parsed), ARTIFACT present.
        self.assertEqual(self.stat(lines, "AWS_ACCESS_KEY_ID", "STATE"), ("ABSENT", "FULLY_PARSED_NO_MATCH"))
        self.assertEqual(self.stat(lines, "AWS_ACCESS_KEY_ID", "ARTIFACT")[0], "PRESENT")
        self.assertEqual(self.stat(lines, "EMAIL_ADDRESS", "ARTIFACT")[0], "PRESENT")
        # Not found anywhere: ARTIFACT must be UNKNOWN because tfplan is opaque.
        self.assertEqual(self.stat(lines, "PRIVATE_KEY_PEM", "ARTIFACT"),
                         ("UNKNOWN", "TFPLAN_NOT_STRUCTURALLY_PARSED"))
        self.assertEqual(self.stat(lines, "PRIVATE_KEY_PEM", "STATE")[0], "ABSENT")

    def test_locations_are_sanitized(self):
        _, lines = self.run_one(self._full(), locations=True)
        locs = [l for l in lines if " LOCATION " in l]
        self.assertTrue(any("ADDRESS=module.secrets.aws_secretsmanager_secret_version.google_user_tokens_init"
                            in l for l in locs))
        self.assertTrue(any("PATH=secret_string" in l for l in locs))

    def test_no_locations_flag_omits_location_lines(self):
        _, lines = self.run_one(self._full(), locations=False)
        self.assertFalse(any(" LOCATION " in l for l in lines))

    def test_empty_google_secret_is_absent_in_state_unknown_in_artifact(self):
        _, lines = self.run_one(plan_zip(tfstate=state([google_secret("{}")])))
        self.assertEqual(self.stat(lines, "GOOGLE_USER_TOKENS_SECRET_TOKENS", "STATE")[0], "ABSENT")
        self.assertEqual(self.stat(lines, "GOOGLE_USER_TOKENS_SECRET_TOKENS", "ARTIFACT")[0], "UNKNOWN")
        self.assertEqual(self.stat(lines, "SECRETSMANAGER_SECRET_VALUE", "STATE")[0], "ABSENT")

    def test_unparseable_nested_secret_is_unknown(self):
        _, lines = self.run_one(plan_zip(tfstate=state([google_secret("not-json " + NAME_SENT)])))
        self.assertEqual(self.stat(lines, "GOOGLE_USER_TOKENS_SECRET_TOKENS", "STATE"),
                         ("UNKNOWN", "NESTED_SECRET_UNPARSED"))
        self.assertEqual(self.stat(lines, "SECRETSMANAGER_SECRET_VALUE", "STATE")[0], "PRESENT")

    def test_unrecognized_google_secret_shape_is_unknown(self):
        _, lines = self.run_one(plan_zip(tfstate=state([google_secret(json.dumps({"calendar": "x"}))])))
        self.assertEqual(self.stat(lines, "GOOGLE_USER_TOKENS_SECRET_TOKENS", "STATE"),
                         ("UNKNOWN", "GOOGLE_TOKENS_SECRET_UNRECOGNIZED_SHAPE"))

    def test_missing_state_prev_makes_state_unknown(self):
        report, lines = self.run_one(plan_zip(tfstate_prev=None))
        self.assertEqual(self.stat(lines, "PRIVATE_KEY_PEM", "STATE"), ("UNKNOWN", "STATE_PREV_MISSING"))

    def test_previous_state_is_inspected(self):
        prev = state([res("aws_lambda_function", "admin",
                          {"environment": [{"variables": {"API_SECRET": STRIPE}}]})])
        _, lines = self.run_one(plan_zip(tfstate_prev=prev))
        self.assertEqual(self.stat(lines, "STRIPE_KEY", "STATE")[0], "PRESENT")
        self.assertEqual(self.stat(lines, "LAMBDA_ENV_SECRET_PATTERN", "STATE")[0], "PRESENT")
        self.assertEqual(self.stat(lines, "NAMED_SENSITIVE_ATTRIBUTE_NONEMPTY", "STATE")[0], "PRESENT")

    def test_all_value_categories_detected_in_state(self):
        attrs = {"a": REFRESH, "b": ACCESS, "c": JWT, "d": GCSECRET, "e": "123-abc.apps.googleusercontent.com",
                 "f": AKID, "g": PEM, "h": URLCRED, "i": STRIPE, "j": WHSEC, "k": EMAIL}
        _, lines = self.run_one(plan_zip(tfstate=state([res("synthetic_thing", "x", attrs)])))
        for cid, _ in insp.VALUE_PATTERNS:
            self.assertEqual(self.stat(lines, cid, "STATE")[0], "PRESENT", cid)

    def test_sensitive_attributes_counted(self):
        st = state([res("aws_db_instance", "x", {"password": ""}, sensitive=[[{"type": "get_attr", "value": "password"}]])])
        _, lines = self.run_one(plan_zip(tfstate=st))
        self.assertEqual(self.stat(lines, "TF_SENSITIVE_ATTRIBUTES", "STATE")[0], "PRESENT")
        self.assertEqual(self.stat(lines, "NAMED_SENSITIVE_ATTRIBUTE_NONEMPTY", "STATE")[0], "ABSENT")

    def test_outputs_scanned(self):
        st = state([], extra={"outputs": {"o": {"value": AKID, "type": "string"}}})
        _, lines = self.run_one(plan_zip(tfstate=st))
        self.assertEqual(self.stat(lines, "AWS_ACCESS_KEY_ID", "STATE")[0], "PRESENT")


class TestPrivateBlob(_Base):
    def _with_private(self, value):
        return plan_zip(tfstate=state([res("aws_s3_bucket", "b", {"bucket": "x"}, private=value)]))

    def test_valid_base64_json_private_keeps_state_complete(self):
        pv = base64.b64encode(json.dumps({"schema_version": "1"}).encode()).decode()
        _, lines = self.run_one(self._with_private(pv))
        self.assertEqual(self.stat(lines, "PRIVATE_KEY_PEM", "STATE")[0], "ABSENT")

    def test_private_with_sentinel_is_present(self):
        pv = base64.b64encode(json.dumps({"token": ACCESS}).encode()).decode()
        _, lines = self.run_one(self._with_private(pv))
        self.assertEqual(self.stat(lines, "GOOGLE_ACCESS_TOKEN", "STATE")[0], "PRESENT")

    def test_invalid_base64_private_is_unknown(self):
        _, lines = self.run_one(self._with_private("!!not base64!!"))
        self.assertEqual(self.stat(lines, "PRIVATE_KEY_PEM", "STATE"), ("UNKNOWN", "STATE_PRIVATE_BLOB_UNDECODABLE"))

    def test_non_json_private_is_unknown(self):
        pv = base64.b64encode(b"\x00\x01binary").decode()
        _, lines = self.run_one(self._with_private(pv))
        self.assertEqual(self.stat(lines, "PRIVATE_KEY_PEM", "STATE"), ("UNKNOWN", "STATE_PRIVATE_BLOB_NOT_JSON"))


# ---------------------------------------------------------------------------
# Malformed archives and entries
# ---------------------------------------------------------------------------


class TestArchiveSafety(_Base):
    def assert_all_unknown(self, lines):
        for line in lines:
            if " CATEGORY=" in line:
                self.assertNotIn("STATUS=ABSENT", line)

    def test_not_a_zip(self):
        data = b"not a zip " + AKID.encode()
        _, lines = self.run_one(data)
        self.assertEqual(self.field(lines, "FORMAT"), "NOT_ZIP")
        self.assert_all_unknown(lines)
        self.assertEqual(self.stat(lines, "AWS_ACCESS_KEY_ID", "ARTIFACT")[0], "PRESENT")

    def test_truncated_zip(self):
        data = plan_zip()
        _, lines = self.run_one(data[: len(data) // 2])
        self.assert_all_unknown(lines)

    def test_crc_corruption(self):
        payload = b"A" * 200
        data = bytearray(make_zip([("tfplan", payload), ("tfstate", state([]))], compression=zipfile.ZIP_STORED))
        idx = data.find(payload)
        data[idx + 10] ^= 0xFF
        _, lines = self.run_one(bytes(data))
        self.assert_all_unknown(lines)
        self.assertEqual(self.field(lines, "REASON"), "ENTRY_READ_ERROR")

    def test_encrypted_flag_entry_is_unsafe(self):
        data = set_encrypted_flag(plan_zip(extra=[("tfconfig/secret.tf", b"x")]), "tfconfig/secret.tf")
        report, lines = self.run_one(data)
        self.assertEqual(report.entries["UNSAFE"], 1)
        self.assert_all_unknown(lines)

    def test_unsupported_compression_is_unsafe(self):
        def bz(zi):
            zi.compress_type = zipfile.ZIP_BZIP2
        data = plan_zip(extra=[("tfconfig/x.tf", b"x", bz)])
        report, lines = self.run_one(data)
        self.assertEqual(report.entries["UNSAFE"], 1)
        self.assert_all_unknown(lines)

    def test_unsafe_names(self):
        for name in ("../" + NAME_SENT, "/" + NAME_SENT, "C:/" + NAME_SENT, "tfconfig/../../" + NAME_SENT,
                     NAME_SENT + "a" * 300):
            with self.subTest(kind=name[:3]):
                report, lines = self.run_one(plan_zip(extra=[(name, b"x")]))
                self.assertEqual(report.entries["UNSAFE"], 1)
                self.assert_all_unknown(lines)

    def test_symlink_entry_is_unsafe(self):
        def link(zi):
            zi.create_system = 3
            zi.external_attr = (0o120777 << 16)
        report, lines = self.run_one(plan_zip(extra=[("tfconfig/link.tf", b"../../etc", link)]))
        self.assertEqual(report.entries["UNSAFE"], 1)
        self.assert_all_unknown(lines)

    def test_duplicate_entry_names(self):
        report, lines = self.run_one(plan_zip(extra=[("tfstate", state([]))]))
        self.assertGreaterEqual(report.entries["UNSAFE"], 1)
        self.assertEqual(self.field(lines, "REASON"), "DUPLICATE_ENTRY")
        self.assert_all_unknown(lines)

    def test_case_insensitive_duplicate(self):
        report, _ = self.run_one(plan_zip(extra=[("TFSTATE", state([]))]))
        self.assertGreaterEqual(report.entries["UNSAFE"], 1)

    def test_unexpected_entry_forces_unknown_but_is_scanned(self):
        report, lines = self.run_one(plan_zip(extra=[("notes.txt", AKID.encode())]))
        self.assertEqual(report.entries["UNEXPECTED"], 1)
        self.assertEqual(self.stat(lines, "AWS_ACCESS_KEY_ID", "ARTIFACT")[0], "PRESENT")
        self.assert_all_unknown(lines)

    def test_missing_tfstate(self):
        data = make_zip([("tfplan", b"x")])
        _, lines = self.run_one(data)
        self.assertEqual(self.field(lines, "FORMAT"), "UNKNOWN")
        self.assert_all_unknown(lines)

    def test_compression_ratio_bomb(self):
        data = plan_zip(extra=[("tfconfig/bomb.tf", b"\x00" * (5 * 1024 * 1024))])
        _, lines = self.run_one(data)
        self.assertEqual(self.field(lines, "REASON"), "COMPRESSION_RATIO_EXCEEDED")
        self.assert_all_unknown(lines)

    def test_entry_size_limit_counts_real_bytes(self):
        with mock.patch.object(insp, "MAX_ENTRY_BYTES", 1000):
            _, lines = self.run_one(plan_zip(extra=[("tfconfig/big.tf", os.urandom(4000))]))
        self.assertEqual(self.field(lines, "REASON"), "ENTRY_TOO_LARGE")
        self.assert_all_unknown(lines)

    def test_total_size_limit(self):
        with mock.patch.object(insp, "MAX_TOTAL_BYTES", 2000):
            _, lines = self.run_one(plan_zip(extra=[("tfconfig/a.tf", os.urandom(1500)),
                                                    ("tfconfig/b.tf", os.urandom(1500))]))
        self.assertEqual(self.field(lines, "REASON"), "TOTAL_TOO_LARGE")
        self.assert_all_unknown(lines)

    def test_too_many_entries(self):
        with mock.patch.object(insp, "MAX_ENTRIES", 5):
            _, lines = self.run_one(plan_zip(extra=[("tfconfig/%d.tf" % i, b"x") for i in range(5)]))
        self.assertEqual(self.field(lines, "REASON"), "TOO_MANY_ENTRIES")
        self.assert_all_unknown(lines)


class TestStateMalformed(_Base):
    def assert_state_unknown(self, lines, reason=None):
        s, r = self.stat(lines, "PRIVATE_KEY_PEM", "STATE")
        self.assertEqual(s, "UNKNOWN")
        if reason:
            self.assertEqual(r, reason)

    def test_invalid_utf8(self):
        _, lines = self.run_one(plan_zip(tfstate=b"\xff\xfe" + AKID.encode()))
        self.assert_state_unknown(lines, "STATE_NOT_UTF8")
        self.assertEqual(self.stat(lines, "AWS_ACCESS_KEY_ID", "STATE")[0], "PRESENT")

    def test_not_json(self):
        _, lines = self.run_one(plan_zip(tfstate=b"{not json " + EMAIL.encode()))
        self.assert_state_unknown(lines, "STATE_NOT_JSON")
        self.assertEqual(self.stat(lines, "EMAIL_ADDRESS", "STATE")[0], "PRESENT")

    def test_duplicate_json_keys(self):
        _, lines = self.run_one(plan_zip(tfstate=b'{"version": 4, "version": 4, "resources": []}'))
        self.assert_state_unknown(lines, "JSON_DUPLICATE_KEY")

    def test_too_deep(self):
        deep = {"version": 4, "resources": []}
        cur = deep
        for _ in range(40):
            cur["n"] = {}
            cur = cur["n"]
        with mock.patch.object(insp, "MAX_JSON_DEPTH", 10):
            _, lines = self.run_one(plan_zip(tfstate=json.dumps(deep).encode()))
        self.assert_state_unknown(lines, "JSON_TOO_DEEP")

    def test_unsupported_version_and_shapes(self):
        for blob, reason in ((state([], version=3), "STATE_UNSUPPORTED_SHAPE"),
                             (json.dumps({"version": 4, "resources": {}}).encode(), "STATE_UNSUPPORTED_SHAPE"),
                             (json.dumps([1, 2]).encode(), "STATE_UNSUPPORTED_SHAPE")):
            with self.subTest(reason=reason):
                _, lines = self.run_one(plan_zip(tfstate=blob))
                self.assert_state_unknown(lines, reason)

    def test_bad_resource_instance_attributes(self):
        bad = [{"mode": "managed", "type": "t", "name": "n", "instances": [{"attributes": "x"}]}]
        _, lines = self.run_one(plan_zip(tfstate=json.dumps({"version": 4, "resources": bad}).encode()))
        self.assert_state_unknown(lines, "STATE_ATTRIBUTES_UNPARSED")

    def test_legacy_flat_attributes(self):
        bad = [{"mode": "managed", "type": "t", "name": "n", "instances": [{"attributes_flat": {"k": AKID}}]}]
        _, lines = self.run_one(plan_zip(tfstate=json.dumps({"version": 4, "resources": bad}).encode()))
        self.assert_state_unknown(lines, "STATE_LEGACY_FLAT_ATTRIBUTES")
        self.assertEqual(self.stat(lines, "AWS_ACCESS_KEY_ID", "STATE")[0], "PRESENT")

    def test_unknown_instance_field(self):
        bad = [{"mode": "managed", "type": "t", "name": "n", "instances": [{"attributes": {}, "mystery": 1}]}]
        _, lines = self.run_one(plan_zip(tfstate=json.dumps({"version": 4, "resources": bad}).encode()))
        self.assert_state_unknown(lines, "STATE_INSTANCE_UNKNOWN_FIELD")


class TestSanitization(_Base):
    def test_quoted_index_key_redacted(self):
        st = state([res("aws_s3_bucket", "b", {"bucket": AKID}, index_key=NAME_SENT)])
        _, lines = self.run_one(plan_zip(tfstate=st))
        self.assertTrue(any("ADDRESS=<redacted>" in l for l in lines if " LOCATION " in l))

    def test_credential_like_env_name_redacted(self):
        st = state([res("aws_lambda_function", "admin",
                        {"environment": [{"variables": {"x_" + WHSEC: STRIPE}}]})])
        _, lines = self.run_one(plan_zip(tfstate=st))
        self.assertTrue(any("PATH=environment[0].variables.<redacted>" in l for l in lines))

    def test_integer_index_kept_and_module(self):
        st = state([res("aws_s3_bucket", "b", {"bucket": AKID}, module="module.m[2]", index_key=3)])
        _, lines = self.run_one(plan_zip(tfstate=st))
        self.assertTrue(any("ADDRESS=module.m[2].aws_s3_bucket.b[3]" in l for l in lines))

    def test_entry_names_never_printed(self):
        _, lines = self.run_one(plan_zip(tfconfig=[("tfconfig/" + NAME_SENT + ".tf", b"x")]))
        self.assertFalse(any(NAME_SENT in l for l in lines))


class TestIntegrityAndSource(_Base):
    def test_object_mismatch(self):
        data = plan_zip()
        fake = FakeGit(data, rev="ef" * 20)
        report, lines = self.run_one(data, fake=fake)
        self.assertEqual(report.integrity, "OBJECT_MISMATCH")
        self.assertNotIn(("cat-file", "blob", FAKE_BLOB), fake.calls)
        self.assertFalse(any("STATUS=ABSENT" in l for l in lines))

    def test_size_mismatch_header(self):
        data = plan_zip()
        report, _ = self.run_one(data, fake=FakeGit(data, size=len(data) + 1))
        self.assertEqual(report.integrity, "SIZE_MISMATCH")

    def test_size_mismatch_payload(self):
        data = plan_zip()
        report, _ = self.run_one(data, fake=FakeGit(data, blob=data[:-1]))
        self.assertEqual(report.integrity, "SIZE_MISMATCH")

    def test_git_error(self):
        data = plan_zip()
        report, _ = self.run_one(data, fake=FakeGit(data, rc={"rev-parse": 128}))
        self.assertEqual(report.integrity, "GIT_ERROR")

    def test_source_config_variants(self):
        data = plan_zip()
        for names, expected in ((("main.tf", "variables.tf"), "THIS_REPO_MATCH"),
                                (("main.tf", "budgets.tf"), "PARTIAL"),
                                (("other.tf",), "OTHER"),
                                (None, "UNKNOWN")):
            with self.subTest(expected=expected):
                _, lines = self.run_one(data, fake=FakeGit(data, repo_names=names))
                self.assertEqual(self.field(lines, "SOURCE_CONFIG"), expected)

    def test_internal_error_reports_class_only(self):
        data = plan_zip()
        report, lines = self.run_one(data, fake=FakeGit(data, raise_exc=RuntimeError(AKID + NAME_SENT)))
        self.assertEqual(report.internal_error, "INTERNAL_ERROR:RuntimeError")
        self.assertTrue(any("ERROR=INTERNAL_ERROR:RuntimeError" in l for l in lines))


class TestDeterminism(_Base):
    def test_entry_order_does_not_change_output(self):
        st = state([google_secret(json.dumps({"refresh_token": REFRESH}))])
        a = make_zip([("tfplan", b"x"), ("tfstate", st), ("tfstate-prev", state([])),
                      ("tfconfig/main.tf", b"x"), ("tfconfig/variables.tf", b"x")])
        b = make_zip([("tfconfig/variables.tf", b"x"), ("tfstate-prev", state([])), ("tfconfig/main.tf", b"x"),
                      ("tfstate", st), ("tfplan", b"x")])
        _, la = self.run_one(a)
        _, lb = self.run_one(b)
        self.assertEqual(la, lb)


# ---------------------------------------------------------------------------
# Real git runner (subprocess patched) and CLI
# ---------------------------------------------------------------------------


class TestGitRunner(unittest.TestCase):
    def test_allowlist_rejects_everything_else(self):
        bad = [["cat-file", "blob", "HEAD"], ["show", "x"], ["rev-parse", "HEAD"], ["cat-file", "-p", "ab" * 20],
               ["ls-tree", "--name-only", "HEAD", "--", "infra/prod/"], ["fetch"], ["cat-file", "blob", "ab" * 20, "x"]]
        for args in bad:
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
                run = insp.make_git_runner("C:/synthetic/repo")
                spec = insp.ARTIFACTS[0]
                rc, out = run(["rev-parse", "%s:%s" % (spec.commit, spec.path)])
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
            self.assertGreater(a.size, 0)


class TestCli(unittest.TestCase):
    def _main(self, args, data=None):
        data = data or plan_zip()
        spec = spec_for(data)
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "copy.py"
            script.write_bytes(b"synthetic script bytes")
            import hashlib
            good = hashlib.sha256(b"synthetic script bytes").hexdigest()
            argv = [a.replace("<GOOD>", good) for a in args]
            with mock.patch.object(insp, "ARTIFACTS", (spec,)):
                rc = insp.main(argv, runner_factory=lambda repo: FakeGit(data), self_path=str(script), out=out)
        return rc, out.getvalue()

    def test_good_hash_runs_and_reports_incomplete(self):
        rc, text = self._main(["--repo", "x", "--expected-script-sha256", "<GOOD>"])
        self.assertEqual(rc, 1)
        self.assertIn("SEC1B SELF_CHECK=OK", text)
        self.assertIn("SEC1B RESULT=INCOMPLETE_OR_UNKNOWN", text)
        for line in text.splitlines():
            self.assertTrue(line.startswith("SEC1B "))

    def test_hash_mismatch_refuses(self):
        rc, text = self._main(["--repo", "x", "--expected-script-sha256", "0" * 64])
        self.assertEqual(rc, 2)
        self.assertIn("SELF_CHECK=MISMATCH", text)
        self.assertNotIn("ARTIFACT=", text)

    def test_bad_hash_format_and_missing_args(self):
        self.assertEqual(self._main(["--repo", "x", "--expected-script-sha256", "zz"])[0], 2)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self._main(["--repo", "x"])[0], 2)

    def test_requires_isolated_flags_when_not_injected(self):
        out = io.StringIO()
        with mock.patch.object(insp.sys, "flags", mock.Mock(isolated=0)):
            rc = insp.main(["--repo", "x", "--expected-script-sha256", "0" * 64], out=out)
        self.assertEqual(rc, 2)
        self.assertIn("RUN_WITH_python_-I_-B", out.getvalue())


# ---------------------------------------------------------------------------
# No side effects and source audit
# ---------------------------------------------------------------------------


class _Trip(Exception):
    pass


def _trip(*a, **k):
    raise _Trip("side effect")


class TestNoSideEffects(unittest.TestCase):
    def test_inspection_has_no_io_network_or_subprocess(self):
        st = state([google_secret(json.dumps({"refresh_token": REFRESH}))])
        data = plan_zip(tfstate=st)
        patches = [
            mock.patch.object(builtins, "open", _trip),
            mock.patch.object(io, "open", _trip),
            mock.patch.object(os, "open", _trip),
            mock.patch.object(os, "remove", _trip),
            mock.patch.object(os, "rename", _trip),
            mock.patch.object(os, "mkdir", _trip),
            mock.patch.object(os, "makedirs", _trip),
            mock.patch.object(tempfile, "mkstemp", _trip),
            mock.patch.object(tempfile, "NamedTemporaryFile", _trip),
            mock.patch.object(socket, "socket", _trip),
            mock.patch.object(socket, "create_connection", _trip),
            mock.patch.object(subprocess, "run", _trip),
            mock.patch.object(subprocess, "Popen", _trip),
        ]
        before = sorted(os.listdir(tempfile.gettempdir()))
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            report = insp.inspect_artifact(spec_for(data), FakeGit(data))
            lines = insp.render([report], with_locations=True)
        self.assertIsNone(report.internal_error)
        self.assertTrue(lines)
        after = sorted(os.listdir(tempfile.gettempdir()))
        self.assertEqual(set(after) - set(before), set())


_ALLOWED_IMPORTS = {"__future__", "argparse", "base64", "binascii", "hashlib", "io", "json", "os", "re",
                    "stat", "subprocess", "sys", "zipfile", "zlib", "dataclasses", "typing"}


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

    def test_subprocess_only_in_git_runner_and_no_shell_true(self):
        for fn in [n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef)]:
            for node in ast.walk(fn):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                        and node.value.id == "subprocess" and node.attr in ("run", "Popen", "call", "check_output"):
                    self.assertIn(fn.name, ("runner", "make_git_runner"))
        self.assertNotIn("shell=True", self.src)

    def test_no_extraction_or_write_apis(self):
        for needle in (".extract(", ".extractall(", "write_bytes", "write_text", "urlopen", "socket"):
            self.assertNotIn(needle, self.src)

    def test_residual_risks_documented(self):
        for needle in ("Pagefile", "Crash dumps", "Antivirus", "Memory"):
            self.assertIn(needle, self.src)


if __name__ == "__main__":
    unittest.main()
