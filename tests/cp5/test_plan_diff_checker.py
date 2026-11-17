"""CP-5J synthetic test suite for the offline Terraform nested plan diff checker.

All fixtures are SYNTHETIC and built in code. No data here comes from any real
Terraform plan, state, tfvars file, AWS account or Stripe account. Credential-
shaped sentinel strings are assembled at runtime from fragments so that they
are obviously fake and are never literal credential-shaped tokens in source.

Run (standard library only, no network, no Terraform):

    python -I -m unittest discover -s tests/cp5 -t tests/cp5 -v
"""

from __future__ import annotations

import ast
import builtins
import contextlib
import copy
import io
import json
import os
import socket
import subprocess
import sys
import unittest
import urllib.request
from pathlib import Path as FsPath
from unittest import mock

_CP5_DIR = FsPath(__file__).resolve().parents[2] / "scripts" / "cp5"
if str(_CP5_DIR) not in sys.path:
    sys.path.insert(0, str(_CP5_DIR))

import nested_diff as nd  # noqa: E402
import plan_diff_checker as pdc  # noqa: E402

# ---------------------------------------------------------------------------
# Synthetic sentinels (never real values)
# ---------------------------------------------------------------------------

_SK = "sk" + "_"
OLD_STRIPE_SENTINEL = _SK + "test" + "_" + "SYNTHETIC-OLD-NOT-A-KEY-0001"
NEW_STRIPE_SENTINEL = _SK + "test" + "_" + "SYNTHETIC-NEW-NOT-A-KEY-0002"
LIVE_STRIPE_SENTINEL = _SK + "live" + "_" + "SYNTHETIC-LIVE-NOT-A-KEY-0003"
WEBHOOK_OLD_SENTINEL = "wh" + "sec_" + "SYNTHETIC-OLD-WEBHOOK-0004"
WEBHOOK_NEW_SENTINEL = "wh" + "sec_" + "SYNTHETIC-NEW-WEBHOOK-0005"
TFVAR_SENTINEL = "SYNTHETIC-TFVAR-VALUE-SENTINEL-0006"
TABLE_OLD_SENTINEL = "SYNTHETIC-TABLE-OLD-SENTINEL-0007"
TABLE_NEW_SENTINEL = "SYNTHETIC-TABLE-NEW-SENTINEL-0008"
OLD_HASH_SENTINEL = "SYNTHETICOLDHASHSENTINEL0000000000000000000="
REPR_SENTINEL = "SYNTHETIC-REPR-SENTINEL-0009"
TOKEN_SENTINEL = "gh" + "p_" + "SYNTHETICTOKEN0010"
JWT_SENTINEL = "ey" + "J" + "SYNTHETICJWT0011"
POLICY_LABEL_SENTINEL = "SYNTHETIC-POLICY-LABEL-0012"

ALL_SENTINELS = (
    OLD_STRIPE_SENTINEL, NEW_STRIPE_SENTINEL, LIVE_STRIPE_SENTINEL,
    WEBHOOK_OLD_SENTINEL, WEBHOOK_NEW_SENTINEL, TFVAR_SENTINEL,
    TABLE_OLD_SENTINEL, TABLE_NEW_SENTINEL, OLD_HASH_SENTINEL, REPR_SENTINEL,
    TOKEN_SENTINEL, JWT_SENTINEL, POLICY_LABEL_SENTINEL,
    "SYNTHETICTOKEN", "SYNTHETICJWT", "SYNTHETIC-POLICY-LABEL",
    # Fragments that must never surface either.
    "SYNTHETIC-OLD-NOT-A-KEY", "SYNTHETIC-NEW-NOT-A-KEY", "SYNTHETIC-LIVE",
    "SYNTHETIC-TABLE", "SYNTHETIC-TFVAR", "SYNTHETICOLDHASH",
)

CANDIDATE = pdc.CP5_CANDIDATE_SOURCE_CODE_HASH
OTHER_HASH = "SYNTHETICOTHERHASH00000000000000000000000A="

ADMIN = "aws_lambda_function.admin"
CANCEL = "aws_lambda_function.cancellation"
REVIEW = "aws_lambda_function.review"


def _lambda_before(name: str) -> dict:
    variables = {
        "TABLE_NAME": TABLE_OLD_SENTINEL,
        "STRIPE_ENV": "sandbox",
        "STRIPE_ENVIRONMENT": "sandbox",
    }
    if name == "admin":
        variables["STRIPE_SECRET_KEY"] = OLD_STRIPE_SENTINEL
    return {
        "function_name": "synthetic-prod-" + name,
        "handler": "handlers.%s_handler.handler" % name,
        "runtime": "python3.11",
        "role": "arn:aws:iam::000000000000:role/synthetic-role",
        "timeout": 30,
        "memory_size": 256,
        "layers": [],
        "tags": {"Project": "synthetic"},
        "tags_all": {"Project": "synthetic"},
        "architectures": ["x86_64"],
        "ephemeral_storage": [{"size": 512}],
        "environment": [{"variables": variables}],
        "logging_config": [{"log_format": "Text", "log_group": "/aws/lambda/synthetic-" + name,
                            "application_log_level": "", "system_log_level": ""}],
        "tracing_config": [{"mode": "PassThrough"}],
        "vpc_config": [],
        "dead_letter_config": [],
        "kms_key_arn": None,
        "source_code_hash": OLD_HASH_SENTINEL,
        "last_modified": "2026-01-01T00:00:00.000+0000",
        "version": "$LATEST",
    }


def _lambda_change(name: str) -> dict:
    """Synthetic code-only update shaped like a real Terraform Lambda update.

    after_unknown deliberately contains the nested (non-true) dict/list
    entries that broke the CP-5 checker.
    """
    before = _lambda_before(name)
    after = copy.deepcopy(before)
    after["source_code_hash"] = CANDIDATE
    del after["last_modified"]
    after_unknown = {
        "last_modified": True,
        "architectures": [False],
        "environment": [{"variables": {}}],
        "ephemeral_storage": [{}],
        "logging_config": [{}],
        "tracing_config": [{}],
        "layers": [],
        "tags": {},
    }
    sensitive = {"environment": [{"variables": {"STRIPE_SECRET_KEY": True}}]} if name == "admin" else {}
    return {
        "address": "aws_lambda_function." + name,
        "mode": "managed",
        "type": "aws_lambda_function",
        "name": name,
        "provider_name": "registry.terraform.io/hashicorp/aws",
        "change": {
            "actions": ["update"],
            "before": before,
            "after": after,
            "after_unknown": after_unknown,
            "before_sensitive": copy.deepcopy(sensitive),
            "after_sensitive": copy.deepcopy(sensitive),
        },
    }


def _generic_change(address: str, rtype: str, actions, mode: str = "managed") -> dict:
    return {
        "address": address,
        "mode": mode,
        "type": rtype,
        "name": address.rsplit(".", 1)[-1],
        "change": {
            "actions": list(actions),
            "before": {"synthetic": "a"} if "create" not in actions else None,
            "after": {"synthetic": "b"} if "delete" not in actions or "create" in actions else None,
            "after_unknown": {},
            "before_sensitive": {},
            "after_sensitive": {},
        },
    }


def make_plan(names=("cancellation", "review", "admin")) -> dict:
    return {
        "format_version": "1.2",
        "terraform_version": "0.0.0-synthetic",
        "variables": {"stripe_secret_key": {"value": TFVAR_SENTINEL}},
        "resource_changes": [_lambda_change(n) for n in names],
        "output_changes": {},
        "errored": False,
        "complete": True,
    }


def rc(plan: dict, address: str) -> dict:
    for entry in plan["resource_changes"]:
        if entry["address"] == address:
            return entry
    raise KeyError(address)


def rotation_policy():
    return pdc.stripe_test_key_rotation_policy(rotation_separately_authorized=True)


def _all_output(result) -> str:
    return "\n".join([
        pdc.render_report(result),
        json.dumps(result.to_dict(), sort_keys=True),
        repr(result),
        str(result),
    ])


class _Base(unittest.TestCase):
    maxDiff = None

    def run_check(self, plan, policy=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = pdc.check_plan(plan, policy)
        self.assertEqual(out.getvalue(), "", "checker must not print")
        self.assertEqual(err.getvalue(), "", "checker must not print")
        self.assert_clean(result)
        return result

    def assert_clean(self, result):
        text = _all_output(result)
        for sentinel in ALL_SENTINELS:
            if sentinel in text:
                self.fail("sanitized output contained a synthetic sentinel")
        # No raw JSON objects/fragments of plan sections.
        # (Fixed reason codes such as ``resource_changes_missing`` are allowed.)
        for marker in ('"before"', '"after"', '"variables":', '"resource_changes"',
                       "python3.11", "synthetic-role", "sandbox"):
            if marker in text:
                self.fail("sanitized output contained raw plan content")

    def assert_class(self, result, expected):
        if result.classification != expected:
            self.fail("classification %s != %s; findings=%s" % (
                result.classification, expected,
                [(f.classification, f.reason, f.address, f.path) for f in result.findings]))

    def paths(self, result, address, kind=None):
        for r in result.resources:
            if r.address == address:
                return [p.path for p in r.paths if kind is None or p.kind == kind]
        return None


# ---------------------------------------------------------------------------
# A, S, AK — exact code-only PASS and unknown handling
# ---------------------------------------------------------------------------


class TestExactPass(_Base):
    def test_A_exact_030_code_only_pass(self):
        result = self.run_check(make_plan())
        self.assert_class(result, pdc.PASS_EXACT_ALLOWED_DIFF)
        self.assertTrue(result.passed)
        counts = dict(result.counts)
        self.assertEqual((counts["add"], counts["change"], counts["destroy"]), (0, 3, 0))
        self.assertEqual(counts["replace"], 0)
        self.assertEqual(counts["read"], 0)
        self.assertEqual(result.findings, ())
        self.assertEqual(result.policy_name, pdc.STRICT_POLICY_NAME)

    def test_S_last_modified_unknown_pass_and_nested_unknown_dicts_not_true(self):
        result = self.run_check(make_plan())
        for address in (ADMIN, CANCEL, REVIEW):
            self.assertEqual(self.paths(result, address, "unknown"), ["last_modified"])
            self.assertEqual(self.paths(result, address, "configured"), ["source_code_hash"])

    def test_AK_unknown_vs_configured_distinction(self):
        result = self.run_check(make_plan())
        admin = [r for r in result.resources if r.address == ADMIN][0]
        kinds = {p.path: (p.kind, p.verdict) for p in admin.paths}
        self.assertEqual(kinds, {
            "source_code_hash": ("configured", "allowed"),
            "last_modified": ("unknown", "allowed"),
        })

    def test_last_modified_known_change_is_not_allowed(self):
        plan = make_plan()
        ch = rc(plan, REVIEW)["change"]
        ch["after"]["last_modified"] = "2026-02-02T00:00:00.000+0000"
        del ch["after_unknown"]["last_modified"]
        result = self.run_check(plan)
        self.assert_class(result, pdc.FAIL_UNEXPECTED_ATTRIBUTE)

    def test_pass_without_last_modified_unknown(self):
        plan = make_plan()
        ch = rc(plan, CANCEL)["change"]
        ch["after"]["last_modified"] = ch["before"]["last_modified"]
        del ch["after_unknown"]["last_modified"]
        self.assert_class(self.run_check(plan), pdc.PASS_EXACT_ALLOWED_DIFF)

    def test_unrelated_noop_entries_allowed(self):
        plan = make_plan()
        noop = _generic_change("aws_s3_bucket.synthetic", "aws_s3_bucket", ["no-op"])
        noop["change"]["after"] = copy.deepcopy(noop["change"]["before"])
        plan["resource_changes"].append(noop)
        self.assert_class(self.run_check(plan), pdc.PASS_EXACT_ALLOWED_DIFF)

    def test_noop_with_diff_is_malformed(self):
        plan = make_plan()
        plan["resource_changes"].append(
            _generic_change("aws_s3_bucket.synthetic", "aws_s3_bucket", ["no-op"]))
        result = self.run_check(plan)
        self.assert_class(result, pdc.FAIL_MALFORMED_PLAN)
        self.assertEqual(result.findings[0].reason, "noop_with_diff")

    def test_input_not_mutated(self):
        plan = make_plan()
        snapshot = copy.deepcopy(plan)
        self.run_check(plan)
        self.run_check(plan, rotation_policy())
        self.assertEqual(plan, snapshot)


# ---------------------------------------------------------------------------
# B — hash
# ---------------------------------------------------------------------------


class TestHash(_Base):
    def test_B_candidate_hash_mismatch_fails(self):
        plan = make_plan()
        rc(plan, ADMIN)["change"]["after"]["source_code_hash"] = OTHER_HASH
        result = self.run_check(plan)
        self.assert_class(result, pdc.FAIL_POLICY_MISMATCH)
        self.assertIn("expected_value_mismatch", [f.reason for f in result.findings])

    def test_hash_unchanged_fails_required_change(self):
        plan = make_plan()
        ch = rc(plan, REVIEW)["change"]
        ch["before"]["source_code_hash"] = CANDIDATE
        result = self.run_check(plan)
        self.assert_class(result, pdc.FAIL_POLICY_MISMATCH)
        self.assertIn("required_change_absent", [f.reason for f in result.findings])

    def test_hash_unknown_fails(self):
        plan = make_plan()
        ch = rc(plan, CANCEL)["change"]
        del ch["after"]["source_code_hash"]
        ch["after_unknown"]["source_code_hash"] = True
        self.assert_class(self.run_check(plan), pdc.FAIL_UNEXPECTED_UNKNOWN)

    def test_hash_non_string_fails(self):
        plan = make_plan()
        rc(plan, CANCEL)["change"]["after"]["source_code_hash"] = 12345
        self.assert_class(self.run_check(plan), pdc.FAIL_POLICY_MISMATCH)

    def test_invalid_policy_hash_rejected(self):
        for bad in ("", "not-base64", CANDIDATE[:-1], None, 5):
            with self.subTest(bad=type(bad).__name__):
                with self.assertRaises(ValueError):
                    pdc.strict_code_only_policy(bad)


# ---------------------------------------------------------------------------
# C–J — resources and actions
# ---------------------------------------------------------------------------


class TestResourcesAndActions(_Base):
    def _extra(self, address, rtype, actions=("update",), mode="managed", policy=None):
        plan = make_plan()
        plan["resource_changes"].append(_generic_change(address, rtype, actions, mode))
        return self.run_check(plan, policy)

    def test_C_additional_lambda_fails(self):
        r = self._extra("aws_lambda_function.pet", "aws_lambda_function")
        self.assert_class(r, pdc.FAIL_UNEXPECTED_RESOURCE)

    def test_D_job_lambda_fails(self):
        plan = make_plan(("cancellation", "review", "admin", "job"))
        self.assert_class(self.run_check(plan), pdc.FAIL_UNEXPECTED_RESOURCE)

    def test_E_intake_lambda_fails(self):
        plan = make_plan(("cancellation", "review", "admin", "intake"))
        self.assert_class(self.run_check(plan), pdc.FAIL_UNEXPECTED_RESOURCE)

    def test_F_iam_update_fails(self):
        r = self._extra("module.iam.aws_iam_policy.dynamodb_access", "aws_iam_policy")
        self.assert_class(r, pdc.FAIL_UNEXPECTED_RESOURCE)

    def test_G_api_gateway_update_fails(self):
        r = self._extra("module.api.aws_api_gateway_deployment.main",
                        "aws_api_gateway_deployment")
        self.assert_class(r, pdc.FAIL_UNEXPECTED_RESOURCE)

    def test_H_create_action_fails(self):
        plan = make_plan()
        ch = rc(plan, ADMIN)["change"]
        ch["actions"] = ["create"]
        self.assert_class(self.run_check(plan), pdc.FAIL_UNEXPECTED_ACTION)
        r = self._extra("aws_sqs_queue.synthetic", "aws_sqs_queue", ("create",))
        self.assert_class(r, pdc.FAIL_UNEXPECTED_RESOURCE)

    def test_I_delete_action_fails(self):
        plan = make_plan()
        rc(plan, REVIEW)["change"]["actions"] = ["delete"]
        self.assert_class(self.run_check(plan), pdc.FAIL_UNEXPECTED_ACTION)
        r = self._extra("aws_sqs_queue.synthetic", "aws_sqs_queue", ("delete",))
        self.assert_class(r, pdc.FAIL_UNEXPECTED_RESOURCE)

    def test_J_replacement_fails(self):
        for actions in (["delete", "create"], ["create", "delete"]):
            with self.subTest(actions=actions):
                plan = make_plan()
                rc(plan, CANCEL)["change"]["actions"] = actions
                result = self.run_check(plan)
                self.assert_class(result, pdc.FAIL_UNEXPECTED_ACTION)
                self.assertIn("replacement", [f.reason for f in result.findings])
                self.assertEqual(dict(result.counts)["replace"], 1)

    def test_replace_paths_fail(self):
        plan = make_plan()
        rc(plan, CANCEL)["change"]["replace_paths"] = [["function_name"]]
        self.assert_class(self.run_check(plan), pdc.FAIL_UNEXPECTED_ACTION)

    def test_moved_or_imported_fail(self):
        for key, value in (("previous_address", "aws_lambda_function.old"),
                           ("importing", {"id": "synthetic"})):
            with self.subTest(key=key):
                plan = make_plan()
                rc(plan, ADMIN)[key] = value
                self.assert_class(self.run_check(plan), pdc.FAIL_UNEXPECTED_ACTION)

    def test_noop_on_expected_resource_fails(self):
        plan = make_plan()
        ch = rc(plan, REVIEW)["change"]
        ch["actions"] = ["no-op"]
        self.assert_class(self.run_check(plan), pdc.FAIL_UNEXPECTED_ACTION)

    def test_missing_expected_resource_fails(self):
        result = self.run_check(make_plan(("cancellation", "review")))
        self.assert_class(result, pdc.FAIL_POLICY_MISMATCH)
        self.assertIn("expected_resource_absent", [f.reason for f in result.findings])

    def test_empty_resource_changes_fails(self):
        plan = make_plan()
        plan["resource_changes"] = []
        self.assert_class(self.run_check(plan), pdc.FAIL_POLICY_MISMATCH)

    def test_wrong_type_on_expected_address_fails(self):
        plan = make_plan()
        rc(plan, ADMIN)["type"] = "aws_lambda_alias"
        self.assert_class(self.run_check(plan), pdc.FAIL_UNEXPECTED_RESOURCE)

    def test_forget_action_fails(self):
        r = self._extra("aws_sqs_queue.synthetic", "aws_sqs_queue", ("forget",))
        self.assert_class(r, pdc.FAIL_UNEXPECTED_RESOURCE)

    def test_AD_pending_data_source_read_fails(self):
        r = self._extra("data.aws_iam_policy_document.synthetic",
                        "aws_iam_policy_document", ("read",), mode="data")
        self.assert_class(r, pdc.FAIL_UNEXPECTED_RESOURCE)
        self.assertIn("pending_data_source_read", [f.reason for f in r.findings])
        self.assertEqual(dict(r.counts)["read"], 1)

    def test_AC_unexpected_output_change_fails(self):
        plan = make_plan()
        plan["output_changes"] = {
            "synthetic_output": {"actions": ["update"], "before": TFVAR_SENTINEL,
                                 "after": TABLE_NEW_SENTINEL, "after_unknown": False,
                                 "before_sensitive": False, "after_sensitive": False},
            "unchanged_output": {"actions": ["no-op"], "before": "x", "after": "x",
                                 "after_unknown": False, "before_sensitive": False,
                                 "after_sensitive": False},
        }
        result = self.run_check(plan)
        self.assert_class(result, pdc.FAIL_POLICY_MISMATCH)
        self.assertEqual([f.address for f in result.findings], ["output.synthetic_output"])

    def test_deferred_changes_fail(self):
        plan = make_plan()
        plan["deferred_changes"] = [{"reason": "synthetic"}]
        self.assert_class(self.run_check(plan), pdc.FAIL_UNEXPECTED_RESOURCE)


# ---------------------------------------------------------------------------
# K–Q — environment and nested configured changes
# ---------------------------------------------------------------------------


class TestEnvironmentAndNested(_Base):
    def _set_var(self, plan, address, key, value):
        rc(plan, address)["change"]["after"]["environment"][0]["variables"][key] = value

    def test_K_admin_stripe_key_change_default_policy_fails(self):
        plan = make_plan()
        self._set_var(plan, ADMIN, "STRIPE_SECRET_KEY", NEW_STRIPE_SENTINEL)
        result = self.run_check(plan)
        self.assert_class(result, pdc.FAIL_UNEXPECTED_ATTRIBUTE)
        f = [f for f in result.findings if f.classification == pdc.FAIL_UNEXPECTED_ATTRIBUTE][0]
        self.assertEqual(f.address, ADMIN)
        self.assertEqual(f.path, "environment[0].variables.STRIPE_SECRET_KEY")
        self.assertTrue(f.sensitive)

    def test_L_admin_stripe_key_change_rotation_policy_passes(self):
        plan = make_plan()
        self._set_var(plan, ADMIN, "STRIPE_SECRET_KEY", NEW_STRIPE_SENTINEL)
        result = self.run_check(plan, rotation_policy())
        self.assert_class(result, pdc.PASS_EXACT_ALLOWED_DIFF)
        self.assertEqual(result.policy_name, pdc.ROTATION_POLICY_NAME)
        admin = [r for r in result.resources if r.address == ADMIN][0]
        stripe = [p for p in admin.paths if p.path.endswith("STRIPE_SECRET_KEY")][0]
        self.assertEqual((stripe.kind, stripe.sensitive, stripe.verdict),
                         ("configured", True, "allowed"))
        self.assertIn("Credential authority and rotation approval are separate controls",
                      pdc.render_report(result))

    def test_M_webhook_secret_difference_fails(self):
        # Admin env carrying a webhook secret change: never allowed.
        plan = make_plan()
        rc(plan, ADMIN)["change"]["before"]["environment"][0]["variables"][
            "STRIPE_WEBHOOK_SECRET"] = WEBHOOK_OLD_SENTINEL
        self._set_var(plan, ADMIN, "STRIPE_WEBHOOK_SECRET", WEBHOOK_NEW_SENTINEL)
        for policy in (None, rotation_policy()):
            with self.subTest(policy=getattr(policy, "name", "default")):
                self.assert_class(self.run_check(plan, policy), pdc.FAIL_UNEXPECTED_ATTRIBUTE)
        # stripe_webhook Lambda update: never in scope.
        plan2 = make_plan(("cancellation", "review", "admin", "stripe_webhook"))
        for policy in (None, rotation_policy()):
            with self.subTest(policy=getattr(policy, "name", "default"), resource=True):
                self.assert_class(self.run_check(plan2, policy), pdc.FAIL_UNEXPECTED_RESOURCE)

    def test_N_other_admin_env_var_fails(self):
        for policy in (None, rotation_policy()):
            with self.subTest(policy=getattr(policy, "name", "default")):
                plan = make_plan()
                self._set_var(plan, ADMIN, "TABLE_NAME", TABLE_NEW_SENTINEL)
                self.assert_class(self.run_check(plan, policy), pdc.FAIL_UNEXPECTED_ATTRIBUTE)

    def test_O_cancellation_env_var_fails(self):
        for policy in (None, rotation_policy()):
            with self.subTest(policy=getattr(policy, "name", "default")):
                plan = make_plan()
                self._set_var(plan, CANCEL, "TABLE_NAME", TABLE_NEW_SENTINEL)
                self.assert_class(self.run_check(plan, policy), pdc.FAIL_UNEXPECTED_ATTRIBUTE)

    def test_P_review_env_var_fails(self):
        for policy in (None, rotation_policy()):
            with self.subTest(policy=getattr(policy, "name", "default")):
                plan = make_plan()
                self._set_var(plan, REVIEW, "NEW_SYNTHETIC_VAR", TABLE_NEW_SENTINEL)
                result = self.run_check(plan, policy)
                self.assert_class(result, pdc.FAIL_UNEXPECTED_ATTRIBUTE)
                self.assertIn("environment[0].variables.NEW_SYNTHETIC_VAR",
                              [f.path for f in result.findings])

    def test_Q_nested_block_changes_fail(self):
        mutations = {
            "logging_config": lambda a: a["logging_config"][0].__setitem__(
                "application_log_level", "DEBUG"),
            "tracing_config": lambda a: a["tracing_config"][0].__setitem__("mode", "Active"),
            "ephemeral_storage": lambda a: a["ephemeral_storage"][0].__setitem__("size", 1024),
            "environment_block_added": lambda a: a["environment"].append({"variables": {}}),
            "role": lambda a: a.__setitem__("role", "arn:aws:iam::000000000000:role/other"),
            "handler": lambda a: a.__setitem__("handler", "other.handler"),
            "function_name": lambda a: a.__setitem__("function_name", "other"),
            "runtime": lambda a: a.__setitem__("runtime", "python3.12"),
            "timeout": lambda a: a.__setitem__("timeout", 31),
            "memory_size": lambda a: a.__setitem__("memory_size", 512),
            "tags": lambda a: a["tags"].__setitem__("Extra", "x"),
            "vpc_config": lambda a: a["vpc_config"].append({"subnet_ids": []}),
            "env_stripe_env_live": lambda a: a["environment"][0]["variables"].__setitem__(
                "STRIPE_ENV", "live"),
        }
        for label, mutate in mutations.items():
            for policy in (None, rotation_policy()):
                with self.subTest(label=label, policy=getattr(policy, "name", "default")):
                    plan = make_plan()
                    mutate(rc(plan, ADMIN)["change"]["after"])
                    self.assert_class(self.run_check(plan, policy),
                                      pdc.FAIL_UNEXPECTED_ATTRIBUTE)

    def test_int_vs_bool_vs_float_not_conflated(self):
        for value in (30.0, True, "30"):
            with self.subTest(value=type(value).__name__):
                plan = make_plan()
                rc(plan, CANCEL)["change"]["after"]["timeout"] = value
                self.assert_class(self.run_check(plan), pdc.FAIL_UNEXPECTED_ATTRIBUTE)


# ---------------------------------------------------------------------------
# R, T — unknowns
# ---------------------------------------------------------------------------


class TestUnknowns(_Base):
    def test_R_nested_unknown_leaf_fails(self):
        plan = make_plan()
        ch = rc(plan, ADMIN)["change"]
        del ch["after"]["environment"][0]["variables"]["TABLE_NAME"]
        ch["after_unknown"]["environment"][0]["variables"]["TABLE_NAME"] = True
        result = self.run_check(plan)
        self.assert_class(result, pdc.FAIL_UNEXPECTED_UNKNOWN)
        self.assertEqual(set(self.paths(result, ADMIN, "unknown")),
                         {"last_modified", "environment[0].variables.TABLE_NAME"})
        self.assertIn("environment[0].variables.TABLE_NAME",
                      [f.path for f in result.findings])

    def test_R_stripe_key_unknown_fails_even_under_rotation(self):
        plan = make_plan()
        ch = rc(plan, ADMIN)["change"]
        del ch["after"]["environment"][0]["variables"]["STRIPE_SECRET_KEY"]
        ch["after_unknown"]["environment"][0]["variables"]["STRIPE_SECRET_KEY"] = True
        for policy in (None, rotation_policy()):
            with self.subTest(policy=getattr(policy, "name", "default")):
                self.assert_class(self.run_check(plan, policy), pdc.FAIL_UNEXPECTED_UNKNOWN)

    def test_T_unexpected_computed_unknown_fails(self):
        for attr in ("version", "qualified_arn", "invoke_arn"):
            with self.subTest(attr=attr):
                plan = make_plan()
                ch = rc(plan, REVIEW)["change"]
                ch["after"].pop(attr, None)
                ch["after_unknown"][attr] = True
                self.assert_class(self.run_check(plan), pdc.FAIL_UNEXPECTED_UNKNOWN)

    def test_whole_environment_unknown_fails(self):
        plan = make_plan()
        ch = rc(plan, ADMIN)["change"]
        del ch["after"]["environment"]
        ch["after_unknown"]["environment"] = True
        result = self.run_check(plan)
        self.assert_class(result, pdc.FAIL_UNEXPECTED_UNKNOWN)
        self.assertIn("environment", self.paths(result, ADMIN, "unknown"))

    def test_unknown_list_element_fails(self):
        plan = make_plan()
        ch = rc(plan, CANCEL)["change"]
        ch["after"]["architectures"] = [None]
        ch["after_unknown"]["architectures"] = [True]
        self.assert_class(self.run_check(plan), pdc.FAIL_UNEXPECTED_UNKNOWN)

    def test_unknown_with_known_value_is_malformed(self):
        plan = make_plan()
        rc(plan, CANCEL)["change"]["after_unknown"]["timeout"] = True
        result = self.run_check(plan)
        self.assert_class(result, pdc.FAIL_MALFORMED_PLAN)
        self.assertEqual(result.findings[0].reason, "unknown_with_known_value")

    def test_unknown_shape_mismatch_is_malformed(self):
        plan = make_plan()
        rc(plan, CANCEL)["change"]["after_unknown"]["timeout"] = {"x": True}
        self.assert_class(self.run_check(plan), pdc.FAIL_MALFORMED_PLAN)

    def test_root_unknown_fails(self):
        plan = make_plan()
        rc(plan, CANCEL)["change"]["after_unknown"] = True
        self.assert_class(self.run_check(plan), pdc.FAIL_MALFORMED_PLAN)


# ---------------------------------------------------------------------------
# U–Y — arrays, missing, null
# ---------------------------------------------------------------------------


class TestArraysAndMissing(_Base):
    def test_U_array_element_addition_fails(self):
        plan = make_plan()
        rc(plan, ADMIN)["change"]["after"]["layers"] = ["arn:synthetic:layer:1"]
        result = self.run_check(plan)
        self.assert_class(result, pdc.FAIL_UNEXPECTED_ATTRIBUTE)
        self.assertIn("layers[0]", [f.path for f in result.findings])

    def test_V_array_element_removal_fails(self):
        plan = make_plan()
        rc(plan, ADMIN)["change"]["after"]["architectures"] = []
        result = self.run_check(plan)
        self.assert_class(result, pdc.FAIL_UNEXPECTED_ATTRIBUTE)
        self.assertIn("architectures[0]", [f.path for f in result.findings])

    def test_W_array_reordering_fails(self):
        plan = make_plan()
        ch = rc(plan, ADMIN)["change"]
        ch["before"]["layers"] = ["arn:synthetic:a", "arn:synthetic:b"]
        ch["after"]["layers"] = ["arn:synthetic:b", "arn:synthetic:a"]
        result = self.run_check(plan)
        self.assert_class(result, pdc.FAIL_UNEXPECTED_ATTRIBUTE)
        self.assertEqual(sorted(f.path for f in result.findings), ["layers[0]", "layers[1]"])

    def test_X_missing_attribute_fails(self):
        plan = make_plan()
        del rc(plan, CANCEL)["change"]["after"]["timeout"]
        result = self.run_check(plan)
        self.assert_class(result, pdc.FAIL_UNEXPECTED_ATTRIBUTE)
        self.assertIn("timeout", [f.path for f in result.findings])

    def test_Y_null_versus_missing_fails(self):
        plan = make_plan()
        del rc(plan, CANCEL)["change"]["after"]["kms_key_arn"]
        self.assert_class(self.run_check(plan), pdc.FAIL_UNEXPECTED_ATTRIBUTE)
        plan = make_plan()
        rc(plan, CANCEL)["change"]["after"]["timeout"] = None
        self.assert_class(self.run_check(plan), pdc.FAIL_UNEXPECTED_ATTRIBUTE)

    def test_empty_to_populated_and_back(self):
        plan = make_plan()
        rc(plan, REVIEW)["change"]["after"]["dead_letter_config"] = [{"target_arn": "x"}]
        self.assert_class(self.run_check(plan), pdc.FAIL_UNEXPECTED_ATTRIBUTE)
        plan = make_plan()
        rc(plan, REVIEW)["change"]["after"]["ephemeral_storage"] = []
        self.assert_class(self.run_check(plan), pdc.FAIL_UNEXPECTED_ATTRIBUTE)


class TestEngine(unittest.TestCase):
    """Direct comparison-engine semantics (AL and array cases)."""

    def d(self, before, after, unk=None):
        return nd.diff_values(before, after, {} if unk is None else unk)

    def test_AL_mixed_nested_dicts_arrays_nulls(self):
        before = {"a": [{"b": None, "c": [1, {"d": "x"}]}], "e": None, "f": {}}
        after = {"a": [{"b": None, "c": [1, {"d": "y"}]}], "e": None, "f": {}}
        r = self.d(before, after)
        self.assertEqual(r.changed, frozenset({("a", 0, "c", 1, "d")}))
        self.assertEqual(r.unknown, frozenset())

    def test_null_vs_empty_containers(self):
        self.assertEqual(self.d({"a": None}, {"a": []}).changed, frozenset({("a",)}))
        self.assertEqual(self.d({"a": {}}, {"a": []}).changed, frozenset({("a",)}))
        self.assertEqual(self.d({"a": None}, {}).changed, frozenset({("a",)}))
        self.assertEqual(self.d({}, {}).changed, frozenset())

    def test_lengths_and_missing_indexes(self):
        r = self.d({"l": [1, 2, 3]}, {"l": [1]})
        self.assertEqual(r.changed, frozenset({("l", 1), ("l", 2)}))
        r = self.d({"l": [1]}, {"l": [1, [5], {"k": 1}]})
        self.assertEqual(r.changed, frozenset({("l", 1), ("l", 2)}))

    def test_nested_unknown_dict_is_not_true(self):
        r = self.d({"a": [{"b": 1}]}, {"a": [{"b": 1}]}, {"a": [{"b": False}], "x": {}})
        self.assertEqual((r.changed, r.unknown), (frozenset(), frozenset()))

    def test_unknown_leaf_under_new_block(self):
        r = self.d({"a": []}, {"a": [{"k": None}]}, {"a": [{"id": True}]})
        self.assertIn(("a", 0, "id"), r.unknown)
        self.assertIn(("a", 0), r.changed)

    def test_unknown_key_absent_from_after(self):
        r = self.d({"t": "x"}, {}, {"t": True})
        self.assertEqual((r.changed, r.unknown), (frozenset(), frozenset({("t",)})))

    def test_depth_limit(self):
        deep = cur = {}
        for _ in range(nd.MAX_DEPTH + 5):
            cur["n"] = {}
            cur = cur["n"]
        with self.assertRaises(nd.MalformedInput):
            nd.diff_values(deep, copy.deepcopy(deep), {})

    def test_marker_covers(self):
        self.assertTrue(nd.marker_covers({"a": True}, ("a", "b", 0)))      # ancestor
        self.assertTrue(nd.marker_covers({"a": {"b": [True]}}, ("a",)))   # descendant
        self.assertTrue(nd.marker_covers({"a": {"b": 1 and True}}, ("a", "b")))
        self.assertFalse(nd.marker_covers({"a": {"b": False}}, ("a", "b")))
        self.assertFalse(nd.marker_covers({}, ("a",)))
        self.assertTrue(nd.marker_covers({"a": {"x": False}}, ("a", 0)))  # shape mismatch

    def test_malformed_exception_carries_no_value(self):
        try:
            nd.diff_values({"a": object()}, {}, {})
        except nd.MalformedInput as exc:
            self.assertEqual(str(exc), "value_type_invalid")
            self.assertEqual(repr(exc), "MalformedInput(value_type_invalid)")
        else:
            self.fail("expected MalformedInput")


# ---------------------------------------------------------------------------
# Z, AA, AB — malformed input
# ---------------------------------------------------------------------------


class _Evil:
    def __repr__(self):
        return REPR_SENTINEL

    __str__ = __repr__

    def __eq__(self, other):
        raise RuntimeError(REPR_SENTINEL)

    __hash__ = object.__hash__


class _EvilStr(str):
    def __repr__(self):
        return REPR_SENTINEL


class TestMalformed(_Base):
    def malformed(self, plan, reason=None):
        result = self.run_check(plan)
        self.assert_class(result, pdc.FAIL_MALFORMED_PLAN)
        self.assertEqual(result.resources, ())
        if reason is not None:
            self.assertEqual(result.findings[0].reason, reason)
        return result

    def test_Z_malformed_plans(self):
        cases = {
            "not_object": ([], "plan_not_object"),
            "string": ("{}", "plan_not_object"),
            "none": (None, "plan_not_object"),
        }
        for label, (plan, reason) in cases.items():
            with self.subTest(label=label):
                self.malformed(plan, reason)

        def mut(fn):
            plan = make_plan()
            fn(plan)
            return plan

        cases = {
            "rc_not_list": (lambda p: p.__setitem__("resource_changes", {}), "resource_changes_not_list"),
            "rc_entry_not_object": (lambda p: p["resource_changes"].append("x"), "resource_change_not_object"),
            "address_missing": (lambda p: p["resource_changes"][0].pop("address"), "address_invalid"),
            "address_bad_chars": (lambda p: p["resource_changes"][0].__setitem__("address", "a b;c"), "address_invalid"),
            "mode_bad": (lambda p: p["resource_changes"][0].__setitem__("mode", "x"), "mode_invalid"),
            "type_bad": (lambda p: p["resource_changes"][0].__setitem__("type", 3), "type_invalid"),
            "change_missing": (lambda p: p["resource_changes"][0].pop("change"), "change_missing"),
            "actions_not_list": (lambda p: p["resource_changes"][0]["change"].__setitem__("actions", "update"), "actions_invalid"),
            "actions_empty": (lambda p: p["resource_changes"][0]["change"].__setitem__("actions", []), "actions_invalid"),
            "actions_unknown": (lambda p: p["resource_changes"][0]["change"].__setitem__("actions", ["upsert"]), "actions_invalid"),
            "after_unknown_missing": (lambda p: p["resource_changes"][0]["change"].pop("after_unknown"), "change_field_missing"),
            "before_sensitive_missing": (lambda p: p["resource_changes"][0]["change"].pop("before_sensitive"), "change_field_missing"),
            "after_unknown_string": (lambda p: p["resource_changes"][0]["change"].__setitem__("after_unknown", "yes"), "marker_type_invalid"),
            "after_unknown_null_leaf": (lambda p: p["resource_changes"][0]["change"]["after_unknown"].__setitem__("x", None), "marker_type_invalid"),
            "sensitive_int": (lambda p: p["resource_changes"][0]["change"].__setitem__("after_sensitive", 1), "marker_type_invalid"),
            "update_before_null": (lambda p: p["resource_changes"][0]["change"].__setitem__("before", None), "update_values_not_objects"),
            "non_string_key": (lambda p: p["resource_changes"][0]["change"]["after"].__setitem__(1, "x"), "object_key_not_string"),
            "tuple_value": (lambda p: p["resource_changes"][0]["change"]["after"].__setitem__("t", (1,)), "value_type_invalid"),
            "errored": (lambda p: p.__setitem__("errored", True), "plan_errored"),
            "incomplete": (lambda p: p.__setitem__("complete", False), "plan_incomplete"),
            "output_changes_list": (lambda p: p.__setitem__("output_changes", []), "output_changes_invalid"),
            "deferred_not_list": (lambda p: p.__setitem__("deferred_changes", {}), "deferred_changes_invalid"),
        }
        for label, (fn, reason) in cases.items():
            with self.subTest(label=label):
                self.malformed(mut(fn), reason)

    def test_AA_missing_resource_changes(self):
        plan = make_plan()
        del plan["resource_changes"]
        self.malformed(plan, "resource_changes_missing")

    def test_AB_duplicate_addresses(self):
        plan = make_plan()
        plan["resource_changes"].append(_lambda_change("admin"))
        self.malformed(plan, "address_duplicate")

    def test_deep_nesting_malformed(self):
        plan = make_plan()
        deep = cur = {}
        for _ in range(500):
            cur["n"] = {}
            cur = cur["n"]
        rc(plan, ADMIN)["change"]["after"]["deep"] = deep
        self.malformed(plan, "depth_exceeded")


# ---------------------------------------------------------------------------
# AE–AI — sensitive data protection
# ---------------------------------------------------------------------------


class TestSensitive(_Base):
    def test_AE_sensitive_marker_propagation_pass(self):
        plan = make_plan()
        for address in (ADMIN, CANCEL, REVIEW):
            ch = rc(plan, address)["change"]
            ch["before_sensitive"] = {"environment": [{"variables": True}]}
            ch["after_sensitive"] = {"environment": [{"variables": True}]}
        self.assert_class(self.run_check(plan), pdc.PASS_EXACT_ALLOWED_DIFF)

        # Ancestor marker propagates to the changed leaf under rotation.
        self._set(plan)
        result = self.run_check(plan, rotation_policy())
        self.assert_class(result, pdc.PASS_EXACT_ALLOWED_DIFF)
        admin = [r for r in result.resources if r.address == ADMIN][0]
        flags = {p.path: p.sensitive for p in admin.paths}
        self.assertTrue(flags["environment[0].variables.STRIPE_SECRET_KEY"])
        self.assertFalse(flags["source_code_hash"])

    def _set(self, plan):
        rc(plan, ADMIN)["change"]["after"]["environment"][0]["variables"][
            "STRIPE_SECRET_KEY"] = NEW_STRIPE_SENTINEL

    def test_sensitive_without_terraform_marker_is_conservative(self):
        plan = make_plan()
        ch = rc(plan, CANCEL)["change"]
        ch["after"]["environment"][0]["variables"]["TABLE_NAME"] = TABLE_NEW_SENTINEL
        ch["after"]["db_password"] = "x"
        ch["before"]["db_password"] = "y"
        result = self.run_check(plan)
        flags = {f.path: f.sensitive for f in result.findings}
        self.assertTrue(flags["environment[0].variables.TABLE_NAME"])
        self.assertTrue(flags["db_password"])

    def test_terraform_marker_alone_marks_sensitive(self):
        # Neither the environment override nor the name heuristic applies to
        # tags.Project; only Terraform's own marker can make it sensitive.
        for side in ("before_sensitive", "after_sensitive"):
            with self.subTest(side=side):
                plan = make_plan()
                ch = rc(plan, CANCEL)["change"]
                ch[side] = {"tags": {"Project": True}}
                ch["after"]["tags"]["Project"] = "changed"
                result = self.run_check(plan)
                flags = {f.path: f.sensitive for f in result.findings}
                self.assertTrue(flags["tags.Project"])
        plan = make_plan()
        rc(plan, CANCEL)["change"]["after"]["tags"]["Project"] = "changed"
        flags = {f.path: f.sensitive for f in self.run_check(plan).findings}
        self.assertFalse(flags["tags.Project"])

    def test_AF_no_secrets_on_failure(self):
        plan = make_plan()
        self._set(plan)
        rc(plan, CANCEL)["change"]["after"]["environment"][0]["variables"][
            "TABLE_NAME"] = TABLE_NEW_SENTINEL
        rc(plan, REVIEW)["change"]["after"]["source_code_hash"] = OTHER_HASH
        for policy in (None, rotation_policy()):
            result = self.run_check(plan, policy)  # run_check asserts cleanliness
            self.assertFalse(result.passed)

    def test_AF_live_key_rejected_without_echo(self):
        plan = make_plan()
        rc(plan, ADMIN)["change"]["after"]["environment"][0]["variables"][
            "STRIPE_SECRET_KEY"] = LIVE_STRIPE_SENTINEL
        result = self.run_check(plan, rotation_policy())
        self.assert_class(result, pdc.FAIL_POLICY_MISMATCH)
        self.assertIn("rotation_not_test_mode", [f.reason for f in result.findings])

    def test_AG_no_secrets_on_success(self):
        plan = make_plan()
        self._set(plan)
        result = self.run_check(plan, rotation_policy())
        self.assertTrue(result.passed)

    def test_AH_no_raw_json_printed(self):
        plan = make_plan()
        self._set(plan)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            result = pdc.check_plan(plan)
            text = pdc.render_report(result)
        self.assertEqual(out.getvalue(), "")
        self.assertNotIn("{", text)
        self.assertNotIn("}", text)

    def test_AI_no_unexpected_exception_repr(self):
        evil_plans = []
        p = make_plan()
        rc(p, ADMIN)["change"]["after"]["evil"] = _Evil()
        evil_plans.append(p)
        p = make_plan()
        rc(p, ADMIN)["change"]["after"]["environment"][0]["variables"]["X"] = _EvilStr("v")
        evil_plans.append(p)
        p = make_plan()
        rc(p, ADMIN)["address"] = _EvilStr(ADMIN)
        evil_plans.append(p)
        for plan in evil_plans:
            result = self.run_check(plan)
            self.assert_class(result, pdc.FAIL_MALFORMED_PLAN)

    def test_AI_internal_error_is_generic(self):
        plan = make_plan()
        with mock.patch.object(nd, "diff_values", side_effect=RuntimeError(REPR_SENTINEL)):
            result = self.run_check(plan)
        self.assert_class(result, pdc.FAIL_MALFORMED_PLAN)
        self.assertEqual(result.findings[0].reason, "internal_error")

    def test_credential_like_keys_redacted(self):
        path = ("environment", 0, "variables", WEBHOOK_NEW_SENTINEL)
        self.assertEqual(pdc.format_path(path), "environment[0].variables.<redacted-key>")
        self.assertEqual(pdc.format_path(("tags", "has space")), "tags.<redacted-key>")
        self.assertEqual(pdc.format_path(()), "<root>")
        plan = make_plan()
        rc(plan, ADMIN)["change"]["after"]["environment"][0]["variables"][
            NEW_STRIPE_SENTINEL] = "v"
        result = self.run_check(plan)
        self.assertIn("environment[0].variables.<redacted-key>",
                      [f.path for f in result.findings])


# ---------------------------------------------------------------------------
# Resource-address and label sanitization (CP-5J security correction)
# ---------------------------------------------------------------------------

UNSAFE_ADDRESSES = {
    # A: synthetic test-key sentinel in a quoted index
    "A_key_quoted_index": 'aws_ssm_parameter.synthetic["%s"]' % OLD_STRIPE_SENTINEL,
    # B: synthetic webhook-secret sentinel
    "B_webhook_quoted_index": 'aws_ssm_parameter.synthetic["%s"]' % WEBHOOK_NEW_SENTINEL,
    "B_webhook_embedded_name": "aws_ssm_parameter.x_%s" % WEBHOOK_OLD_SENTINEL,
    # C: synthetic tokens
    "C_token_name": "aws_s3_object.%s" % TOKEN_SENTINEL,
    "C_jwt_quoted_index": 'aws_s3_object.synthetic["%s"]' % JWT_SENTINEL,
    # D: credential-like text in nested (module) addresses
    "D_module_live_key": "module.%s.aws_lambda_function.synthetic" % LIVE_STRIPE_SENTINEL,
    "D_module_index_key": 'module.m["%s"].aws_lambda_function.synthetic' % NEW_STRIPE_SENTINEL,
    "D_module_embedded": "module.prefix_%s.aws_s3_bucket.b" % WEBHOOK_NEW_SENTINEL,
    # Arbitrary quoted text is never rendered, credential-shaped or not.
    "plain_quoted_index": 'aws_s3_bucket.b["%s"]' % REPR_SENTINEL,
    "canonical_lookalike": 'aws_lambda_function.admin["%s"]' % TOKEN_SENTINEL,
}

SAFE_ADDRESSES = (
    "aws_lambda_function.admin",
    "aws_lambda_function.cancellation",
    "aws_lambda_function.review",
    "aws_lambda_function.job",
    "module.iam.aws_iam_policy.dynamodb_access",
    "module.api.aws_api_gateway_deployment.main",
    "data.aws_iam_policy_document.synthetic",
    "aws_s3_bucket.task_role_logs[0]",
    "module.m[2].aws_s3_bucket.b",
)


class TestAddressSanitization(_Base):
    def _plan_with(self, *addresses, actions=("update",)):
        plan = make_plan()
        for address in addresses:
            entry = _generic_change(address, "aws_s3_bucket", actions)
            plan["resource_changes"].append(entry)
        return plan

    def _assert_no_sentinel_anywhere(self, result):
        objects = [result, *result.resources, *result.findings]
        for r in result.resources:
            objects.extend(r.paths)
        text = "\n".join([_all_output(result)] + [repr(o) for o in objects]
                         + [str(o) for o in objects])
        for sentinel in ALL_SENTINELS:
            if sentinel in text:
                self.fail("sentinel escaped into a public result object")

    def test_ABCD_unsafe_addresses_redacted_and_still_fail(self):
        for label, address in UNSAFE_ADDRESSES.items():
            for policy in (None, rotation_policy()):
                with self.subTest(label=label, policy=getattr(policy, "name", "default")):
                    result = self.run_check(self._plan_with(address), policy)
                    # F / P: still an unexpected resource, never a PASS.
                    self.assert_class(result, pdc.FAIL_UNEXPECTED_RESOURCE)
                    self.assertFalse(result.passed)
                    extra = [f for f in result.findings
                             if f.classification == pdc.FAIL_UNEXPECTED_RESOURCE]
                    self.assertEqual([f.address for f in extra], [pdc.REDACTED_ADDRESS])
                    unexpected = [r for r in result.resources if not r.expected]
                    self.assertEqual([r.address for r in unexpected], [pdc.REDACTED_ADDRESS])
                    self._assert_no_sentinel_anywhere(result)

    def test_E_safe_addresses_remain_readable(self):
        for address in SAFE_ADDRESSES:
            with self.subTest(address=address):
                self.assertEqual(pdc.sanitize_address(address), address)
        result = self.run_check(self._plan_with("module.iam.aws_iam_policy.dynamodb_access"))
        self.assertIn("module.iam.aws_iam_policy.dynamodb_access",
                      [f.address for f in result.findings])
        self.assertEqual(
            [r.address for r in result.resources if r.expected],
            [ADMIN, CANCEL, REVIEW])

    def test_sanitize_address_rejects_non_strings_and_long_values(self):
        long_but_well_formed = "module.m." * 40 + "aws_s3_bucket.b"
        self.assertGreater(len(long_but_well_formed), 256)
        for bad in (None, 5, ["a"], "a" * 300, "aws_s3_bucket.b c", "aws_s3_bucket",
                    long_but_well_formed):
            with self.subTest(bad=type(bad).__name__):
                self.assertEqual(pdc.sanitize_address(bad), pdc.REDACTED_ADDRESS)

    def test_F_unexpected_address_classification_unchanged(self):
        result = self.run_check(self._plan_with(UNSAFE_ADDRESSES["A_key_quoted_index"]))
        self.assertEqual(result.findings[0].reason, "unexpected_resource_change")
        self.assertEqual(dict(result.counts)["change"], 4)

    def test_G_duplicate_detection_uses_original_addresses(self):
        a = UNSAFE_ADDRESSES["A_key_quoted_index"]
        b = UNSAFE_ADDRESSES["B_webhook_quoted_index"]
        # Distinct originals that render identically are NOT duplicates.
        result = self.run_check(self._plan_with(a, b))
        self.assert_class(result, pdc.FAIL_UNEXPECTED_RESOURCE)
        extra = [f for f in result.findings if f.classification == pdc.FAIL_UNEXPECTED_RESOURCE]
        self.assertEqual(len(extra), 2)
        # Identical originals ARE duplicates.
        result = self.run_check(self._plan_with(a, a))
        self.assert_class(result, pdc.FAIL_MALFORMED_PLAN)
        self.assertEqual(result.findings[0].reason, "address_duplicate")
        # Data-source mode with an unsafe address is also redacted.
        plan = make_plan()
        plan["resource_changes"].append(_generic_change(
            'data.aws_ssm_parameter.p["%s"]' % OLD_STRIPE_SENTINEL,
            "aws_ssm_parameter", ["read"], mode="data"))
        result = self.run_check(plan)
        self.assertEqual([f.reason for f in result.findings], ["pending_data_source_read"])
        self.assertEqual(result.findings[0].address, pdc.REDACTED_ADDRESS)

    def test_HIJ_redaction_in_to_dict_render_and_objects(self):
        plan = self._plan_with(*UNSAFE_ADDRESSES.values())
        result = self.run_check(plan)
        d = result.to_dict()
        self.assertTrue(all(r["address"] in (ADMIN, CANCEL, REVIEW, pdc.REDACTED_ADDRESS)
                            for r in d["resources"]))
        self.assertTrue(all(f["address"] in (pdc.REDACTED_ADDRESS,) for f in d["findings"]))
        text = pdc.render_report(result)
        self.assertEqual(text.count(pdc.REDACTED_ADDRESS), 2 * len(UNSAFE_ADDRESSES))
        for obj in [*result.resources, *result.findings]:
            self.assertIn(obj.address, (ADMIN, CANCEL, REVIEW, pdc.REDACTED_ADDRESS))
        self._assert_no_sentinel_anywhere(result)

    def test_K_no_sentinel_in_internal_repr_or_malformed_path(self):
        plan = self._plan_with(*UNSAFE_ADDRESSES.values())
        entries = pdc._parse_entries(plan)
        text = repr(entries) + str(entries)
        for sentinel in ALL_SENTINELS:
            self.assertNotIn(sentinel, text)
        # Address failing structural validation: malformed, nothing echoed.
        bad = make_plan()
        bad["resource_changes"].append(_generic_change(
            "aws_s3_bucket.b %s" % OLD_STRIPE_SENTINEL, "aws_s3_bucket", ["update"]))
        result = self.run_check(bad)
        self.assert_class(result, pdc.FAIL_MALFORMED_PLAN)
        self._assert_no_sentinel_anywhere(result)

    def test_L_redacted_output_deterministic(self):
        addresses = list(UNSAFE_ADDRESSES.values()) + ["aws_sqs_queue.q"]
        plan = self._plan_with(*addresses)
        plan["resource_changes"].append(_generic_change(
            'aws_s3_bucket.c["%s"]' % JWT_SENTINEL, "aws_s3_bucket", ["delete"]))
        baseline = json.dumps(pdc.check_plan(plan).to_dict())
        variant = copy.deepcopy(plan)
        variant["resource_changes"].reverse()
        for _ in range(3):
            self.assertEqual(json.dumps(pdc.check_plan(plan).to_dict()), baseline)
            self.assertEqual(json.dumps(pdc.check_plan(variant).to_dict()), baseline)

    def test_N_strict_policy_unchanged(self):
        policy = pdc.strict_code_only_policy()
        self.assertEqual(policy.name, pdc.STRICT_POLICY_NAME)
        self.assertEqual(tuple(r.address for r in policy.rules), pdc.RELEASE_LAMBDA_ADDRESSES)
        for rule in policy.rules:
            self.assertEqual(rule.required_actions, ("update",))
            self.assertEqual(rule.allowed_changed, frozenset({("source_code_hash",)}))
            self.assertEqual(rule.required_changed, frozenset({("source_code_hash",)}))
            self.assertEqual(rule.allowed_unknown, frozenset({("last_modified",)}))
            self.assertEqual(rule.constraint_for(("source_code_hash",)).expected, CANDIDATE)
        self.assertEqual(pdc.check_plan(make_plan()).policy_name, pdc.STRICT_POLICY_NAME)

    def test_O_rotation_still_explicit_only(self):
        with self.assertRaises(ValueError):
            pdc.stripe_test_key_rotation_policy()
        policy = rotation_policy()
        admin = policy.rule_for(ADMIN)
        self.assertEqual(admin.allowed_changed - {("source_code_hash",)},
                         frozenset({("environment", 0, "variables", "STRIPE_SECRET_KEY")}))
        for address in (CANCEL, REVIEW):
            self.assertEqual(policy.rule_for(address).allowed_changed,
                             frozenset({("source_code_hash",)}))

    def test_P_no_false_pass_with_mixed_safe_and_unsafe(self):
        plan = self._plan_with(UNSAFE_ADDRESSES["canonical_lookalike"])
        rc(plan, ADMIN)["change"]["after"]["environment"][0]["variables"][
            "STRIPE_SECRET_KEY"] = NEW_STRIPE_SENTINEL
        for policy in (None, rotation_policy()):
            with self.subTest(policy=getattr(policy, "name", "default")):
                result = self.run_check(plan, policy)
                self.assertFalse(result.passed)
                self.assert_class(result, pdc.FAIL_UNEXPECTED_RESOURCE)
        # Unsafe-address no-op entries keep their prior semantics (allowed
        # only when identical) and still never produce output.
        plan = make_plan()
        noop = _generic_change(UNSAFE_ADDRESSES["A_key_quoted_index"], "aws_s3_bucket", ["no-op"])
        noop["change"]["after"] = copy.deepcopy(noop["change"]["before"])
        plan["resource_changes"].append(noop)
        result = self.run_check(plan)
        self.assert_class(result, pdc.PASS_EXACT_ALLOWED_DIFF)
        self._assert_no_sentinel_anywhere(result)

    def test_policy_label_sanitized(self):
        base = pdc.strict_code_only_policy()
        for name in (POLICY_LABEL_SENTINEL, NEW_STRIPE_SENTINEL, "ok-name-" + JWT_SENTINEL, ""):
            with self.subTest(name_len=len(name)):
                custom = pdc.Policy(name=name, rules=base.rules)
                result = self.run_check(make_plan(), custom)
                self.assertEqual(result.policy_name, pdc.REDACTED_POLICY_NAME)
                malformed = self.run_check({"resource_changes": "x"}, custom)
                self.assertEqual(malformed.policy_name, pdc.REDACTED_POLICY_NAME)
                self._assert_no_sentinel_anywhere(result)
        self.assertEqual(pdc.sanitize_policy_name(pdc.ROTATION_POLICY_NAME),
                         pdc.ROTATION_POLICY_NAME)

    def test_policy_rule_address_sanitized_when_absent(self):
        base = pdc.strict_code_only_policy()
        extra_rule = pdc.ResourceRule(
            address='aws_lambda_function.x["%s"]' % OLD_STRIPE_SENTINEL,
            resource_type="aws_lambda_function", required_actions=("update",),
            required_changed=frozenset(), allowed_changed=frozenset(),
            allowed_unknown=frozenset())
        custom = pdc.Policy(name="custom-test-policy", rules=base.rules + (extra_rule,))
        result = self.run_check(make_plan(), custom)
        self.assert_class(result, pdc.FAIL_POLICY_MISMATCH)
        self.assertEqual([f.address for f in result.findings], [pdc.REDACTED_ADDRESS])

        # Present and matched by a caller policy: the report still carries
        # only the sanitized rendering of the matched address.
        plan = make_plan()
        entry = _generic_change(extra_rule.address, "aws_lambda_function", ["update"])
        plan["resource_changes"].append(entry)
        result = self.run_check(plan, custom)
        self.assert_class(result, pdc.FAIL_UNEXPECTED_ATTRIBUTE)
        self.assertIn(pdc.REDACTED_ADDRESS, [r.address for r in result.resources if r.expected])
        self.assertEqual({f.address for f in result.findings}, {pdc.REDACTED_ADDRESS})
        self._assert_no_sentinel_anywhere(result)

    def test_key_redaction_matches_embedded_but_not_ordinary_names(self):
        self.assertEqual(pdc.format_path(("task_role",)), "task_role")
        self.assertEqual(pdc.format_path(("laughs_total",)), "laughs_total")
        self.assertEqual(pdc.format_path(("disk_size",)), "disk_size")
        for key in ("x_" + WEBHOOK_NEW_SENTINEL, "pre_" + OLD_STRIPE_SENTINEL,
                    "a_" + TOKEN_SENTINEL, "x_" + JWT_SENTINEL):
            with self.subTest(key_len=len(key)):
                self.assertEqual(pdc.format_path(("tags", key)), "tags." + pdc.REDACTED_KEY)


# ---------------------------------------------------------------------------
# Rotation policy rules
# ---------------------------------------------------------------------------


class TestRotationPolicy(_Base):
    def test_rotation_requires_explicit_true(self):
        for value in (False, None, 1, "true", "True", [True]):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    pdc.stripe_test_key_rotation_policy(rotation_separately_authorized=value)
        with self.assertRaises(ValueError):
            pdc.stripe_test_key_rotation_policy()
        with self.assertRaises(TypeError):
            pdc.stripe_test_key_rotation_policy(True)  # keyword-only

    def test_default_is_strict(self):
        self.assertEqual(pdc.check_plan(make_plan()).policy_name, pdc.STRICT_POLICY_NAME)

    def test_AN_plan_content_cannot_activate_rotation(self):
        plan = make_plan()
        rc(plan, ADMIN)["change"]["after"]["environment"][0]["variables"][
            "STRIPE_SECRET_KEY"] = NEW_STRIPE_SENTINEL
        plan["policy"] = pdc.ROTATION_POLICY_NAME
        plan["cp5j_policy"] = {"name": pdc.ROTATION_POLICY_NAME,
                               "rotation_separately_authorized": True}
        plan["variables"]["rotation_separately_authorized"] = {"value": True}
        rc(plan, ADMIN)["policy"] = pdc.ROTATION_POLICY_NAME
        result = self.run_check(plan)
        self.assertEqual(result.policy_name, pdc.STRICT_POLICY_NAME)
        self.assert_class(result, pdc.FAIL_UNEXPECTED_ATTRIBUTE)

    def test_non_policy_object_rejected(self):
        result = pdc.check_plan(make_plan(), {"name": pdc.ROTATION_POLICY_NAME})
        self.assert_class(result, pdc.FAIL_POLICY_MISMATCH)
        self.assertEqual(result.findings[0].reason, "policy_invalid")

    def test_rotation_rejects_missing_before_or_after(self):
        plan = make_plan()
        ch = rc(plan, ADMIN)["change"]
        del ch["before"]["environment"][0]["variables"]["STRIPE_SECRET_KEY"]
        ch["after"]["environment"][0]["variables"]["STRIPE_SECRET_KEY"] = NEW_STRIPE_SENTINEL
        r = self.run_check(plan, rotation_policy())
        self.assert_class(r, pdc.FAIL_POLICY_MISMATCH)
        self.assertIn("rotation_before_missing_or_invalid", [f.reason for f in r.findings])

        plan = make_plan()
        del rc(plan, ADMIN)["change"]["after"]["environment"][0]["variables"]["STRIPE_SECRET_KEY"]
        r = self.run_check(plan, rotation_policy())
        self.assert_class(r, pdc.FAIL_POLICY_MISMATCH)
        self.assertIn("rotation_after_missing_or_invalid", [f.reason for f in r.findings])

        plan = make_plan()
        rc(plan, ADMIN)["change"]["after"]["environment"][0]["variables"]["STRIPE_SECRET_KEY"] = ""
        r = self.run_check(plan, rotation_policy())
        self.assert_class(r, pdc.FAIL_POLICY_MISMATCH)

    def test_rotation_rejects_non_test_prefix(self):
        plan = make_plan()
        rc(plan, ADMIN)["change"]["after"]["environment"][0]["variables"][
            "STRIPE_SECRET_KEY"] = "SYNTHETIC-NO-PREFIX"
        r = self.run_check(plan, rotation_policy())
        self.assert_class(r, pdc.FAIL_POLICY_MISMATCH)

    def test_rotation_only_on_admin(self):
        plan = make_plan()
        for address in (CANCEL, REVIEW):
            ch = rc(plan, address)["change"]
            ch["before"]["environment"][0]["variables"]["STRIPE_SECRET_KEY"] = OLD_STRIPE_SENTINEL
            ch["after"]["environment"][0]["variables"]["STRIPE_SECRET_KEY"] = NEW_STRIPE_SENTINEL
        self.assert_class(self.run_check(plan, rotation_policy()), pdc.FAIL_UNEXPECTED_ATTRIBUTE)

    def test_rotation_rejects_additional_lambda(self):
        plan = make_plan(("cancellation", "review", "admin", "job"))
        rc(plan, ADMIN)["change"]["after"]["environment"][0]["variables"][
            "STRIPE_SECRET_KEY"] = NEW_STRIPE_SENTINEL
        self.assert_class(self.run_check(plan, rotation_policy()), pdc.FAIL_UNEXPECTED_RESOURCE)

    def test_rotation_policy_still_requires_hash(self):
        plan = make_plan()
        rc(plan, ADMIN)["change"]["after"]["environment"][0]["variables"][
            "STRIPE_SECRET_KEY"] = NEW_STRIPE_SENTINEL
        rc(plan, ADMIN)["change"]["after"]["source_code_hash"] = OTHER_HASH
        self.assert_class(self.run_check(plan, rotation_policy()), pdc.FAIL_POLICY_MISMATCH)

    def test_rotation_policy_passes_without_key_change(self):
        self.assert_class(self.run_check(make_plan(), rotation_policy()),
                          pdc.PASS_EXACT_ALLOWED_DIFF)


# ---------------------------------------------------------------------------
# AJ — determinism
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# First-time Stripe TEST-key configuration policy and targeted-plan exception
# ---------------------------------------------------------------------------

RK_STRIPE_SENTINEL = "rk" + "_" + "test" + "_" + "SYNTHETIC-RK-NOT-A-KEY-0013"
ALL_SENTINELS = ALL_SENTINELS + (RK_STRIPE_SENTINEL, "SYNTHETIC-RK-NOT-A-KEY")
_STRIPE = "environment[0].variables.STRIPE_SECRET_KEY"


def first_time_policy():
    return pdc.stripe_test_key_first_time_configuration_policy(
        first_time_configuration_separately_authorized=True)


def first_time_plan(before="empty", after=RK_STRIPE_SENTINEL):
    """Synthetic first-time configuration: admin key empty/absent -> test key."""
    plan = make_plan()
    ch = rc(plan, ADMIN)["change"]
    bv = ch["before"]["environment"][0]["variables"]
    av = ch["after"]["environment"][0]["variables"]
    if before == "empty":
        bv["STRIPE_SECRET_KEY"] = ""
    elif before == "absent":
        bv.pop("STRIPE_SECRET_KEY", None)
    else:
        bv["STRIPE_SECRET_KEY"] = before
    if after is None:
        av.pop("STRIPE_SECRET_KEY", None)
    else:
        av["STRIPE_SECRET_KEY"] = after
    return plan


def targeted(plan, applyable=True):
    plan["complete"] = False
    plan["applyable"] = applyable
    plan["errored"] = False
    return plan


class TestFirstTimeConfigurationPolicy(_Base):
    def test_requires_explicit_true(self):
        for value in (False, None, 1, "true", "True", [True]):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    pdc.stripe_test_key_first_time_configuration_policy(
                        first_time_configuration_separately_authorized=value)
        with self.assertRaises(ValueError):
            pdc.stripe_test_key_first_time_configuration_policy()
        with self.assertRaises(TypeError):
            pdc.stripe_test_key_first_time_configuration_policy(True)  # keyword-only

    def test_empty_before_and_test_after_passes(self):
        for after in (RK_STRIPE_SENTINEL, NEW_STRIPE_SENTINEL):
            with self.subTest(after_kind=after[:3]):
                result = self.run_check(first_time_plan("empty", after), first_time_policy())
                self.assert_class(result, pdc.PASS_EXACT_ALLOWED_DIFF)
                self.assertEqual(result.policy_name, pdc.FIRST_TIME_POLICY_NAME)
                counts = dict(result.counts)
                self.assertEqual((counts["add"], counts["change"], counts["destroy"]), (0, 3, 0))
                self.assertFalse(result.targeted_plan_exception)
                admin = [r for r in result.resources if r.address == ADMIN][0]
                stripe = [p for p in admin.paths if p.path == _STRIPE][0]
                self.assertEqual((stripe.kind, stripe.sensitive, stripe.verdict),
                                 ("configured", True, "allowed"))

    def test_absent_before_and_test_after_passes(self):
        result = self.run_check(first_time_plan("absent"), first_time_policy())
        self.assert_class(result, pdc.PASS_EXACT_ALLOWED_DIFF)

    def test_nonempty_before_is_rejected(self):
        result = self.run_check(first_time_plan(OLD_STRIPE_SENTINEL), first_time_policy())
        self.assert_class(result, pdc.FAIL_POLICY_MISMATCH)
        self.assertIn("first_time_before_not_empty_or_absent", [f.reason for f in result.findings])

    def test_non_string_before_is_rejected(self):
        for before in (None, 0, 5, True, ["x"], {"k": "v"}):
            with self.subTest(before=repr(before)):
                result = self.run_check(first_time_plan(before), first_time_policy())
                self.assertFalse(result.passed)

    def test_after_must_be_known_nonempty_test_mode(self):
        cases = {
            "live": LIVE_STRIPE_SENTINEL,
            "embedded_live": "rk_test_" + "x_live_y",
            "empty": "",
            "no_prefix": "SYNTHETIC-NO-PREFIX",
            "int": 7,
            "none": None,
            "list": [RK_STRIPE_SENTINEL],
        }
        for label, after in cases.items():
            with self.subTest(case=label):
                plan = first_time_plan("empty")
                av = rc(plan, ADMIN)["change"]["after"]["environment"][0]["variables"]
                av["STRIPE_SECRET_KEY"] = after
                result = self.run_check(plan, first_time_policy())
                self.assertFalse(result.passed)

    def test_key_change_is_required(self):
        for before in ("empty", "absent"):
            with self.subTest(before=before):
                plan = first_time_plan(before, "")
                if before == "absent":
                    rc(plan, ADMIN)["change"]["after"]["environment"][0]["variables"].pop(
                        "STRIPE_SECRET_KEY", None)
                result = self.run_check(plan, first_time_policy())
                self.assert_class(result, pdc.FAIL_POLICY_MISMATCH)
                self.assertIn("required_change_absent", [f.reason for f in result.findings])
        # Plain code-only plan (no key change at all) is also rejected here.
        result = self.run_check(make_plan(), first_time_policy())
        self.assert_class(result, pdc.FAIL_POLICY_MISMATCH)

    def test_after_missing_is_rejected(self):
        result = self.run_check(first_time_plan("empty", None), first_time_policy())
        self.assertFalse(result.passed)

    def test_after_unknown_is_rejected(self):
        plan = first_time_plan("empty", None)
        marker = rc(plan, ADMIN)["change"]["after_unknown"]
        marker["environment"] = [{"variables": {"STRIPE_SECRET_KEY": True}}]
        result = self.run_check(plan, first_time_policy())
        self.assertFalse(result.passed)

    def test_rotation_policy_unchanged_still_rejects_first_time(self):
        plan = first_time_plan("empty")
        result = self.run_check(plan, rotation_policy())
        self.assert_class(result, pdc.FAIL_POLICY_MISMATCH)
        self.assertIn("rotation_before_missing_or_invalid", [f.reason for f in result.findings])
        result = self.run_check(first_time_plan("absent"), rotation_policy())
        self.assert_class(result, pdc.FAIL_POLICY_MISMATCH)

    def test_strict_policy_still_rejects_first_time(self):
        self.assert_class(self.run_check(first_time_plan("empty")), pdc.FAIL_UNEXPECTED_ATTRIBUTE)

    def test_genuine_rotation_still_passes_only_under_rotation_policy(self):
        plan = make_plan()
        rc(plan, ADMIN)["change"]["after"]["environment"][0]["variables"][
            "STRIPE_SECRET_KEY"] = NEW_STRIPE_SENTINEL
        self.assert_class(self.run_check(plan, rotation_policy()), pdc.PASS_EXACT_ALLOWED_DIFF)
        self.assertFalse(self.run_check(plan, first_time_policy()).passed)

    def test_only_admin_may_configure_the_key(self):
        plan = first_time_plan("empty")
        for address in (CANCEL, REVIEW):
            ch = rc(plan, address)["change"]
            ch["before"]["environment"][0]["variables"]["STRIPE_SECRET_KEY"] = ""
            ch["after"]["environment"][0]["variables"]["STRIPE_SECRET_KEY"] = RK_STRIPE_SENTINEL
        self.assert_class(self.run_check(plan, first_time_policy()), pdc.FAIL_UNEXPECTED_ATTRIBUTE)

    def test_hash_still_required(self):
        plan = first_time_plan("empty")
        rc(plan, ADMIN)["change"]["after"]["source_code_hash"] = OTHER_HASH
        self.assert_class(self.run_check(plan, first_time_policy()), pdc.FAIL_POLICY_MISMATCH)

    def test_exactly_three_lambdas_still_required(self):
        plan = first_time_plan("empty")
        plan["resource_changes"].append(_lambda_change("job"))
        self.assert_class(self.run_check(plan, first_time_policy()), pdc.FAIL_UNEXPECTED_RESOURCE)
        plan = first_time_plan("empty")
        plan["resource_changes"] = [e for e in plan["resource_changes"] if e["address"] != REVIEW]
        result = self.run_check(plan, first_time_policy())
        self.assert_class(result, pdc.FAIL_POLICY_MISMATCH)
        self.assertIn("expected_resource_absent", [f.reason for f in result.findings])

    def test_other_environment_drift_still_rejected(self):
        for key, value in (("TABLE_NAME", TABLE_NEW_SENTINEL),
                           ("STRIPE_WEBHOOK_SECRET", WEBHOOK_NEW_SENTINEL),
                           ("STRIPE_ENV", "live")):
            with self.subTest(key=key):
                plan = first_time_plan("empty")
                rc(plan, ADMIN)["change"]["after"]["environment"][0]["variables"][key] = value
                self.assert_class(self.run_check(plan, first_time_policy()),
                                  pdc.FAIL_UNEXPECTED_ATTRIBUTE)

    def test_plan_content_cannot_select_the_policy(self):
        plan = first_time_plan("empty")
        plan["policy"] = pdc.FIRST_TIME_POLICY_NAME
        plan["variables"]["first_time_configuration_separately_authorized"] = {"value": True}
        result = self.run_check(plan)
        self.assertEqual(result.policy_name, pdc.STRICT_POLICY_NAME)
        self.assertFalse(result.passed)

    def test_input_not_mutated(self):
        plan = first_time_plan("empty")
        snapshot = copy.deepcopy(plan)
        pdc.check_plan(plan, first_time_policy())
        self.assertEqual(plan, snapshot)


class TestTargetedPlanException(_Base):
    def run_t(self, plan, policy=None, authorized=True):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = pdc.check_plan(plan, policy, targeted_incomplete_plan_authorized=authorized)
        self.assertEqual((out.getvalue(), err.getvalue()), ("", ""))
        self.assert_clean(result)
        return result

    def reasons(self, result):
        return [f.reason for f in result.findings]

    def test_default_rejects_incomplete_plan(self):
        result = self.run_check(targeted(make_plan()))
        self.assert_class(result, pdc.FAIL_MALFORMED_PLAN)
        self.assertEqual(self.reasons(result), ["plan_incomplete"])
        self.assertFalse(result.targeted_plan_exception)
        result = self.run_t(targeted(make_plan()), authorized=False)
        self.assertEqual(self.reasons(result), ["plan_incomplete"])

    def test_authorization_argument_must_be_literal_bool_keyword_only(self):
        for value in (1, 0, "true", None, [True]):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    pdc.check_plan(make_plan(), None, targeted_incomplete_plan_authorized=value)
        with self.assertRaises(TypeError):
            pdc.check_plan(make_plan(), None, True)  # keyword-only

    def test_authorized_incomplete_plan_passes_with_visible_marker(self):
        result = self.run_t(targeted(make_plan()))
        self.assert_class(result, pdc.PASS_EXACT_ALLOWED_DIFF)
        self.assertTrue(result.targeted_plan_exception)
        text = pdc.render_report(result)
        self.assertIn(pdc.TARGETED_PLAN_EXCEPTION_NOTICE, text)
        self.assertIn("full convergence is NOT claimed", text)
        self.assertTrue(result.to_dict()["targeted_plan_exception"])
        self.assertTrue(json.dumps(result.to_dict()))

    def test_complete_plan_with_authorization_has_no_marker(self):
        result = self.run_t(make_plan())
        self.assert_class(result, pdc.PASS_EXACT_ALLOWED_DIFF)
        self.assertFalse(result.targeted_plan_exception)
        self.assertNotIn("targeted-plan exception", pdc.render_report(result))
        self.assertFalse(result.to_dict()["targeted_plan_exception"])

    def test_requires_applyable_true_errored_false_and_no_deferred(self):
        def malformed(plan, reason):
            result = self.run_t(plan)
            self.assert_class(result, pdc.FAIL_MALFORMED_PLAN)
            self.assertEqual(self.reasons(result), [reason])
            self.assertFalse(result.targeted_plan_exception)

        malformed(targeted(make_plan(), applyable=False), "targeted_plan_not_applyable")
        plan = targeted(make_plan()); del plan["applyable"]
        malformed(plan, "targeted_plan_not_applyable")
        for bad in ("true", 1, None):
            plan = targeted(make_plan()); plan["applyable"] = bad
            malformed(plan, "targeted_plan_not_applyable")
        plan = targeted(make_plan()); plan["errored"] = True
        malformed(plan, "plan_errored")
        plan = targeted(make_plan()); del plan["errored"]
        malformed(plan, "targeted_plan_errored_missing")
        plan = targeted(make_plan()); plan["deferred_changes"] = [{"x": 1}]
        malformed(plan, "targeted_plan_deferred_changes")
        plan = targeted(make_plan()); plan["deferred_changes"] = "none"
        malformed(plan, "targeted_plan_deferred_changes")
        plan = make_plan(); plan["complete"] = "false"
        malformed(plan, "plan_complete_invalid")

    def test_empty_deferred_changes_list_is_allowed(self):
        plan = targeted(make_plan()); plan["deferred_changes"] = []
        self.assert_class(self.run_t(plan), pdc.PASS_EXACT_ALLOWED_DIFF)

    def test_exception_does_not_relax_other_rules(self):
        plan = targeted(make_plan())
        plan["resource_changes"].append(_generic_change("aws_iam_role.synthetic", "aws_iam_role", ["update"]))
        self.assert_class(self.run_t(plan), pdc.FAIL_UNEXPECTED_RESOURCE)

        plan = targeted(make_plan())
        plan["resource_changes"].append(_generic_change("aws_s3_bucket.synthetic", "aws_s3_bucket", ["create"]))
        self.assert_class(self.run_t(plan), pdc.FAIL_UNEXPECTED_RESOURCE)

        plan = targeted(make_plan())
        plan["output_changes"] = {"synthetic_out": {"actions": ["update"]}}
        self.assert_class(self.run_t(plan), pdc.FAIL_POLICY_MISMATCH)

        plan = targeted(make_plan())
        rc(plan, ADMIN)["change"]["after"]["source_code_hash"] = OTHER_HASH
        self.assert_class(self.run_t(plan), pdc.FAIL_POLICY_MISMATCH)

        plan = targeted(make_plan())
        rc(plan, ADMIN)["change"]["after"]["environment"][0]["variables"]["TABLE_NAME"] = TABLE_NEW_SENTINEL
        self.assert_class(self.run_t(plan), pdc.FAIL_UNEXPECTED_ATTRIBUTE)

        plan = targeted(make_plan())
        ch = rc(plan, ADMIN)["change"]
        del ch["after"]["handler"]
        ch["after_unknown"]["handler"] = True
        self.assertFalse(self.run_t(plan).passed)

        plan = targeted(make_plan())
        plan["resource_changes"][0]["change"]["actions"] = ["delete", "create"]
        self.assertFalse(self.run_t(plan).passed)

    def test_failing_report_still_shows_the_marker(self):
        plan = targeted(make_plan())
        rc(plan, ADMIN)["change"]["after"]["source_code_hash"] = OTHER_HASH
        result = self.run_t(plan)
        self.assertTrue(result.targeted_plan_exception)
        self.assertIn(pdc.TARGETED_PLAN_EXCEPTION_NOTICE, pdc.render_report(result))

    def test_noop_with_diff_is_still_malformed(self):
        plan = targeted(make_plan())
        plan["resource_changes"].append(_generic_change("aws_s3_bucket.synthetic", "aws_s3_bucket", ["no-op"]))
        self.assert_class(self.run_t(plan), pdc.FAIL_MALFORMED_PLAN)

    def test_plan_content_cannot_authorize_the_exception(self):
        plan = targeted(make_plan())
        plan["targeted_incomplete_plan_authorized"] = True
        plan["variables"]["targeted_incomplete_plan_authorized"] = {"value": True}
        result = self.run_check(plan)
        self.assert_class(result, pdc.FAIL_MALFORMED_PLAN)
        self.assertEqual(self.reasons(result), ["plan_incomplete"])

    def test_first_time_policy_with_targeted_exception_passes_end_to_end(self):
        plan = targeted(first_time_plan("empty"))
        plan["output_changes"] = {"synthetic_out": {"actions": ["no-op"]}}
        plan["resource_changes"].append(
            {**_generic_change("aws_s3_bucket.synthetic", "aws_s3_bucket", ["no-op"]),
             "change": {"actions": ["no-op"], "before": {"synthetic": "a"}, "after": {"synthetic": "a"},
                        "after_unknown": {}, "before_sensitive": {}, "after_sensitive": {}}})
        result = self.run_t(plan, first_time_policy())
        self.assert_class(result, pdc.PASS_EXACT_ALLOWED_DIFF)
        self.assertEqual(result.policy_name, pdc.FIRST_TIME_POLICY_NAME)
        self.assertTrue(result.targeted_plan_exception)
        text = pdc.render_report(result)
        self.assertIn("policy: " + pdc.FIRST_TIME_POLICY_NAME, text)
        self.assertIn(pdc.TARGETED_PLAN_EXCEPTION_NOTICE, text)
        self.assertEqual(dict(result.counts)["change"], 3)

    def test_rotation_policy_with_targeted_exception_still_needs_nonempty_before(self):
        result = self.run_t(targeted(first_time_plan("empty")), rotation_policy())
        self.assert_class(result, pdc.FAIL_POLICY_MISMATCH)
        self.assertIn("rotation_before_missing_or_invalid", self.reasons(result))

    def test_input_not_mutated(self):
        plan = targeted(first_time_plan("empty"))
        snapshot = copy.deepcopy(plan)
        pdc.check_plan(plan, first_time_policy(), targeted_incomplete_plan_authorized=True)
        self.assertEqual(plan, snapshot)


def _reverse_keys(value):
    if isinstance(value, dict):
        return {k: _reverse_keys(value[k]) for k in reversed(list(value))}
    if isinstance(value, list):
        return [_reverse_keys(v) for v in value]
    return value


class TestDeterminism(_Base):
    def _failing_plan(self):
        plan = make_plan()
        for address in (ADMIN, CANCEL, REVIEW):
            after = rc(plan, address)["change"]["after"]
            after["environment"][0]["variables"]["ZZZ"] = "1"
            after["environment"][0]["variables"]["AAA"] = "2"
            after["layers"] = ["l1", "l2"]
            after["timeout"] = 99
        plan["resource_changes"].append(
            _generic_change("module.iam.aws_iam_policy.x", "aws_iam_policy", ["update"]))
        return plan

    def test_AJ_deterministic_ordering(self):
        plan = self._failing_plan()
        baseline = json.dumps(pdc.check_plan(plan).to_dict(), sort_keys=False)
        variant = _reverse_keys(copy.deepcopy(plan))
        variant["resource_changes"].reverse()
        for _ in range(5):
            self.assertEqual(json.dumps(pdc.check_plan(plan).to_dict(), sort_keys=False), baseline)
            self.assertEqual(json.dumps(pdc.check_plan(variant).to_dict(), sort_keys=False),
                             baseline)
        result = pdc.check_plan(plan)
        admin_paths = [f.path for f in result.findings if f.address == ADMIN]
        self.assertEqual(admin_paths, sorted(admin_paths))
        self.assertEqual(result.classification, pdc.FAIL_UNEXPECTED_RESOURCE)

    def test_render_is_stable(self):
        plan = self._failing_plan()
        texts = {pdc.render_report(pdc.check_plan(plan)) for _ in range(3)}
        self.assertEqual(len(texts), 1)


# ---------------------------------------------------------------------------
# AM, AO — source audit and side-effect guards
# ---------------------------------------------------------------------------

_ALLOWED_IMPORTS = {"__future__", "dataclasses", "typing", "re", "nested_diff"}
_FORBIDDEN_CALLS = {"open", "exec", "eval", "compile", "__import__", "input", "print",
                    "breakpoint", "getattr", "setattr", "globals", "locals", "vars"}
_FORBIDDEN_ATTRS = {"environ", "getenv", "system", "popen", "Popen", "run", "urlopen",
                    "socket", "connect", "read_text", "write_text", "open", "loads", "load",
                    "dumps", "dump"}
_FORBIDDEN_STRINGS = ("api.stripe.com", "http://", "https://", "terraform show",
                      "terraform plan", "cp5.tfplan", "tfvars", "AppData", "release-artifacts")


class TestSourceAudit(unittest.TestCase):
    MODULES = ("nested_diff.py", "plan_diff_checker.py")

    def _tree(self, name):
        source = (_CP5_DIR / name).read_text(encoding="utf-8")
        return source, ast.parse(source)

    def test_AO_imports_are_stdlib_allowlist(self):
        for name in self.MODULES:
            _, tree = self._tree(name)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods = {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom):
                    mods = {(node.module or "").split(".")[0]}
                else:
                    continue
                with self.subTest(module=name, imports=sorted(mods)):
                    self.assertTrue(mods <= _ALLOWED_IMPORTS)

    def test_AO_no_side_effect_calls_or_attributes(self):
        for name in self.MODULES:
            _, tree = self._tree(name)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, _FORBIDDEN_CALLS, name)
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, _FORBIDDEN_ATTRS, name)

    def test_AM_no_stripe_integration_or_paths(self):
        for name in self.MODULES:
            source, tree = self._tree(name)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [a.name for a in node.names] + [getattr(node, "module", "") or ""]
                    self.assertFalse(any("stripe" in n.lower() for n in names), name)
            for needle in _FORBIDDEN_STRINGS:
                self.assertNotIn(needle, source, name)

    def test_no_main_entry_point(self):
        for name in self.MODULES:
            source, _ = self._tree(name)
            self.assertNotIn("__main__", source, name)
            self.assertNotIn("argv", source, name)


class _Tripwire(Exception):
    pass


def _trip(*_a, **_k):
    raise _Tripwire("side effect attempted")


class _RaisingEnviron(dict):
    def __getitem__(self, key):
        raise _Tripwire("env read")

    def get(self, *a, **k):
        raise _Tripwire("env read")

    def __contains__(self, key):
        raise _Tripwire("env read")


class TestRuntimeSideEffects(unittest.TestCase):
    def test_AO_check_runs_with_io_tripwires(self):
        plan = make_plan()
        plan_rot = make_plan()
        rc(plan_rot, ADMIN)["change"]["after"]["environment"][0]["variables"][
            "STRIPE_SECRET_KEY"] = NEW_STRIPE_SENTINEL
        rot = rotation_policy()
        patches = [
            mock.patch.object(builtins, "open", _trip),
            mock.patch.object(io, "open", _trip),
            mock.patch.object(os, "open", _trip),
            mock.patch.object(os, "system", _trip),
            mock.patch.object(os, "getenv", _trip),
            mock.patch.object(os, "environ", _RaisingEnviron()),
            mock.patch.object(subprocess, "Popen", _trip),
            mock.patch.object(subprocess, "run", _trip),
            mock.patch.object(socket, "socket", _trip),
            mock.patch.object(socket, "create_connection", _trip),
            mock.patch.object(urllib.request, "urlopen", _trip),
        ]
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            r1 = pdc.check_plan(plan)
            r2 = pdc.check_plan(plan_rot, rot)
            r3 = pdc.check_plan(plan_rot)
            text = pdc.render_report(r3)
        self.assertEqual(r1.classification, pdc.PASS_EXACT_ALLOWED_DIFF)
        self.assertEqual(r2.classification, pdc.PASS_EXACT_ALLOWED_DIFF)
        self.assertEqual(r3.classification, pdc.FAIL_UNEXPECTED_ATTRIBUTE)
        self.assertNotIn("internal_error", text)


if __name__ == "__main__":
    unittest.main()
