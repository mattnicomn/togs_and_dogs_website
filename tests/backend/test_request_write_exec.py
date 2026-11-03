"""Offline tests for the INACTIVE S0d-1 pure DynamoDB request-translation adapter.

AWS-free, deterministic, standard library only. These tests build REAL committed
specs via common.request_write (build_update/build_create/build_retire) and then
translate them with common.request_write_exec, asserting:
  * exact result/refusal types and strict TableName validation,
  * verbatim preservation of every approved condition/update expression and the
    required security conditions,
  * strict/deterministic AttributeValue serialization (bool-before-int, Decimal
    precision/exponent boundaries, deterministic set ordering, cycle/depth
    guards, no float/empty-set/mixed-set/non-str-key/binary coercion),
  * that a legitimate application map with an AV-like key name stays valid and is
    never double-serialized,
  * correct 2-operand create (Put) / retire (Update) transactions and NO delete
    or unconditional form,
  * deterministic idempotency token stability/difference, length, and that a
    single UpdateItem carries NO token,
  * conservative size-limit refusals,
  * no SDK/client/environment access and no live-handler import.

HONEST LIMITATION asserted in docstrings below: these do NOT prove boto3
TypeSerializer byte-parity (that needs the SDK, forbidden in this slice) nor any
real DynamoDB/idempotency-window/exception behavior. Those remain separately
gated (S0d-2).
"""
import importlib
import re
import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src/backend"))
from common import request_write as rw
from common import request_write_exec as rx


TABLE = "petcare-hero-main"
KEY = {"PK": "REQ#request-a", "SK": "CLIENT#client-a"}
ELIGIBLE = rw.AdoptionDisposition(rw.ADOPT_ELIGIBLE, ())


def _all_indices(haystack, needle):
    start = 0
    while True:
        i = haystack.find(needle, start)
        if i == -1:
            return
        yield i
        start = i + 1


# --- real-spec fixtures (mirror test_request_write.py fixtures) --------------

def complete_client_expected(**over):
    base = dict(
        tenant="tenant_a", revision=1, incarnation="life-a", source_status="ASSIGNED",
        read_id="read-a",
        present_identity=(("cognito_sub", "subject-a"),),
        absent_identity=("client_email", "linked_client_profile_id"),
        protected_client=True,
        retirement_marker=rw.RETIREMENT_FALSE,
    )
    base.update(over)
    return rw.ExpectedState(**base)


def simple_plan():
    return rw.WritePlan(set_fields=(("cancellation_reason", "r"),),
                        append_audit={"status": "CANCELLATION_REQUESTED"})


def real_update_spec(**over):
    spec = rw.build_update(KEY, complete_client_expected(**over), simple_plan(), ELIGIBLE)
    assert type(spec) is rw.UpdateSpec, ("fixture did not build an UpdateSpec: " + repr(spec))
    return spec


def derived_token():
    return rw._request_lifetime_token("tenant_a", ("REQ#request-a", "CLIENT#client-a"))


def create_intent(**over):
    base = dict(tenant="tenant_a", request_id="request-a", client_id="client-a",
                incarnation="life-a", created_at="2026-11-01T12:00:00+00:00",
                item={"company_id": "tenant_a", "status": "PENDING_REVIEW",
                      "client_email": "owner@example.invalid"})
    base.update(over)
    return rw.CreateIntent(**base)


def absent_lifetime(token):
    return rw.LifetimeEvidence(state=rw.LIFETIME_ABSENT, token=token)


def real_create_spec(**over):
    spec = rw.build_create(KEY, create_intent(**over), absent_lifetime(derived_token()))
    assert type(spec) is rw.CreateSpec, ("fixture did not build a CreateSpec: " + repr(spec))
    return spec


def retire_expected(**over):
    base = dict(tenant="tenant_a", revision=1, incarnation="life-a",
                retired_at="2026-11-01T12:00:00+00:00", source_status=None,
                children=(), child_set_complete=True)
    base.update(over)
    return rw.RetireExpected(**base)


def active_lifetime(token):
    return rw.LifetimeEvidence(state=rw.LIFETIME_ACTIVE, token=token, retired=False,
                               record={"PK": "LIFETIME#" + token, "SK": "PERMANENT",
                                       "retired": False, "incarnation": "life-a"})


def real_retire_spec(**over):
    spec = rw.build_retire(KEY, retire_expected(**over), active_lifetime(derived_token()))
    assert type(spec) is rw.RetireSpec, ("fixture did not build a RetireSpec: " + repr(spec))
    return spec


# ===========================================================================
# A - public translation interface: types, inputs, TableName
# ===========================================================================

class TranslateTypeTests(unittest.TestCase):
    def test_update_returns_prepared_update(self):
        p = rx.translate_update(real_update_spec(), TABLE)
        self.assertIsInstance(p, rx.PreparedUpdate)
        self.assertEqual(p.table_name, TABLE)

    def test_create_returns_prepared_txn(self):
        p = rx.translate_create(real_create_spec(), TABLE)
        self.assertIsInstance(p, rx.PreparedTxn)
        self.assertEqual(p.op, "create")

    def test_retire_returns_prepared_txn(self):
        p = rx.translate_retire(real_retire_spec(), TABLE)
        self.assertIsInstance(p, rx.PreparedTxn)
        self.assertEqual(p.op, "retire")

    def test_refusal_input_is_rejected(self):
        ref = rw.Refusal("SOME_REASON")
        self.assertIsInstance(rx.translate_update(ref, TABLE), rx.TranslationRefusal)
        self.assertIsInstance(rx.translate_create(ref, TABLE), rx.TranslationRefusal)
        self.assertIsInstance(rx.translate_retire(ref, TABLE), rx.TranslationRefusal)
        self.assertEqual(rx.translate_update(ref, TABLE).reason, "REFUSAL_INPUT")

    def test_wrong_spec_type_is_rejected(self):
        # A CreateSpec passed to translate_update, an UpdateSpec to translate_create, etc.
        self.assertEqual(rx.translate_update(real_create_spec(), TABLE).reason, "WRONG_SPEC_TYPE")
        self.assertEqual(rx.translate_create(real_update_spec(), TABLE).reason, "WRONG_SPEC_TYPE")
        self.assertEqual(rx.translate_retire(real_update_spec(), TABLE).reason, "WRONG_SPEC_TYPE")
        self.assertEqual(rx.translate_update(object(), TABLE).reason, "WRONG_SPEC_TYPE")
        self.assertEqual(rx.translate_update(None, TABLE).reason, "WRONG_SPEC_TYPE")

    def test_malformed_table_name_is_rejected(self):
        for bad in (None, "", "  ", "ab", "x" * 256, "bad name!", 5, "has/slash"):
            self.assertEqual(rx.translate_update(real_update_spec(), bad).reason,
                             "MALFORMED_TABLE_NAME", bad)
            self.assertEqual(rx.translate_create(real_create_spec(), bad).reason,
                             "MALFORMED_TABLE_NAME", bad)
            self.assertEqual(rx.translate_retire(real_retire_spec(), bad).reason,
                             "MALFORMED_TABLE_NAME", bad)

    def test_well_formed_table_names_accepted(self):
        for good in ("abc", "petcare.hero_main-1", "A.B_C-9"):
            self.assertIsInstance(rx.translate_update(real_update_spec(), good), rx.PreparedUpdate)


# ===========================================================================
# D - verbatim expression + security-condition preservation
# ===========================================================================

class VerbatimPreservationTests(unittest.TestCase):
    def test_update_expressions_preserved_verbatim(self):
        spec = real_update_spec()
        p = rx.translate_update(spec, TABLE)
        self.assertEqual(p.request["ConditionExpression"], spec.condition_expression)
        self.assertEqual(p.request["UpdateExpression"], spec.update_expression)
        self.assertEqual(p.request["ExpressionAttributeNames"], spec.names)

    def test_update_has_tablename_and_serialized_values(self):
        spec = real_update_spec()
        p = rx.translate_update(spec, TABLE)
        self.assertEqual(p.request["TableName"], TABLE)
        # Key + values are AttributeValue-serialized, not raw.
        self.assertEqual(p.request["Key"]["PK"], {"S": "REQ#request-a"})
        self.assertEqual(p.request["ExpressionAttributeValues"][":false"], {"BOOL": False})
        self.assertEqual(p.request["ExpressionAttributeValues"][":rev"], {"N": "1"})
        self.assertEqual(p.request["ExpressionAttributeValues"][":next"], {"N": "2"})

    def test_update_mandatory_retirement_fence_preserved(self):
        p = rx.translate_update(real_update_spec(), TABLE)
        self.assertIn("(attribute_not_exists(#rl) OR #rl = :false)", p.request["ConditionExpression"])
        self.assertEqual(p.request["ExpressionAttributeNames"]["#rl"], "retired_lifetime")

    def test_update_all_required_security_conditions_present(self):
        p = rx.translate_update(real_update_spec(), TABLE)
        c = p.request["ConditionExpression"]
        for needle in ("company_id = :tenant", "request_id = :reqid", "client_id = :cliid",
                       "#rev = :rev", "#inc = :inc"):
            self.assertIn(needle, c, needle)
        self.assertIn("#rev = :next", p.request["UpdateExpression"])

    def test_create_conditions_preserved_and_tablename_injected(self):
        spec = real_create_spec()
        p = rx.translate_create(spec, TABLE)
        items = p.request["TransactItems"]
        self.assertEqual(len(items), 2)
        for i, operand in enumerate(items):
            self.assertIn("Put", operand)
            self.assertEqual(operand["Put"]["TableName"], TABLE)
            self.assertEqual(operand["Put"]["ConditionExpression"],
                             spec.transact_items[i]["Put"]["ConditionExpression"])
            self.assertIn("attribute_not_exists(PK)", operand["Put"]["ConditionExpression"])
            self.assertIn("attribute_not_exists(SK)", operand["Put"]["ConditionExpression"])

    def test_create_item_serialized(self):
        p = rx.translate_create(real_create_spec(), TABLE)
        req_item = p.request["TransactItems"][0]["Put"]["Item"]
        self.assertEqual(req_item["PK"], {"S": "REQ#request-a"})
        self.assertEqual(req_item["legacy_write_revision"], {"N": "1"})
        # lifetime operand carries retired=False as a BOOL.
        life_item = p.request["TransactItems"][1]["Put"]["Item"]
        self.assertEqual(life_item["retired"], {"BOOL": False})

    def test_retire_two_updates_tablename_and_conditions_verbatim(self):
        spec = real_retire_spec()
        p = rx.translate_retire(spec, TABLE)
        items = p.request["TransactItems"]
        self.assertEqual(len(items), 2)
        for i, operand in enumerate(items):
            self.assertIn("Update", operand)
            self.assertEqual(operand["Update"]["TableName"], TABLE)
            self.assertEqual(operand["Update"]["ConditionExpression"],
                             spec.transact_items[i]["Update"]["ConditionExpression"])
            self.assertEqual(operand["Update"]["UpdateExpression"],
                             spec.transact_items[i]["Update"]["UpdateExpression"])
            self.assertEqual(operand["Update"]["ExpressionAttributeNames"],
                             spec.transact_items[i]["Update"]["ExpressionAttributeNames"])

    def test_retire_request_operand_has_retirement_fence(self):
        p = rx.translate_retire(real_retire_spec(), TABLE)
        request_operand = p.request["TransactItems"][1]["Update"]
        self.assertIn("(attribute_not_exists(#rl) OR #rl = :false)",
                      request_operand["ConditionExpression"])
        self.assertEqual(request_operand["ExpressionAttributeValues"][":true"], {"BOOL": True})


# ===========================================================================
# C - strict AttributeValue serialization
# ===========================================================================

class SerializationTests(unittest.TestCase):
    def test_bool_before_int(self):
        self.assertEqual(rx._serialize_value(False), {"BOOL": False})
        self.assertEqual(rx._serialize_value(True), {"BOOL": True})

    def test_int_is_number_string(self):
        self.assertEqual(rx._serialize_value(0), {"N": "0"})
        self.assertEqual(rx._serialize_value(1), {"N": "1"})
        self.assertEqual(rx._serialize_value(-42), {"N": "-42"})

    def test_finite_decimal_no_rounding(self):
        self.assertEqual(rx._serialize_value(Decimal("1.50")), {"N": "1.50"})
        self.assertEqual(rx._serialize_value(Decimal("0")), {"N": "0"})

    def test_str_including_empty(self):
        self.assertEqual(rx._serialize_value("hi"), {"S": "hi"})
        self.assertEqual(rx._serialize_value(""), {"S": ""})

    def test_none_is_null(self):
        self.assertEqual(rx._serialize_value(None), {"NULL": True})

    def test_nested_map_and_list(self):
        self.assertEqual(
            rx._serialize_value({"a": 1, "b": ["x", True]}),
            {"M": {"a": {"N": "1"}, "b": {"L": [{"S": "x"}, {"BOOL": True}]}}})

    def test_string_set_deterministic_sorted(self):
        self.assertEqual(rx._serialize_value({"b", "a", "c"}), {"SS": ["a", "b", "c"]})

    def test_number_set_deterministic(self):
        out = rx._serialize_value({3, 1, 2})
        self.assertEqual(out, {"NS": ["1", "2", "3"]})

    def test_float_forbidden(self):
        with self.assertRaises(rx._SerializationError) as ctx:
            rx._serialize_value(1.5)
        self.assertEqual(ctx.exception.reason, "SER_FLOAT_FORBIDDEN")

    def test_nan_and_infinity_rejected(self):
        for bad in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
            with self.assertRaises(rx._SerializationError) as ctx:
                rx._serialize_value(bad)
            self.assertEqual(ctx.exception.reason, "SER_NON_FINITE", bad)

    def test_decimal_precision_boundary(self):
        # 38 significant digits is the DynamoDB max; 39 must be refused WITHOUT rounding.
        ok = Decimal("1" * 38)
        self.assertEqual(rx._serialize_value(ok), {"N": "1" * 38})
        with self.assertRaises(rx._SerializationError) as ctx:
            rx._serialize_value(Decimal("1" * 39))
        self.assertEqual(ctx.exception.reason, "SER_NUMBER_PRECISION")

    def test_decimal_exponent_range(self):
        with self.assertRaises(rx._SerializationError) as ctx:
            rx._serialize_value(Decimal("1E+126"))
        self.assertEqual(ctx.exception.reason, "SER_NUMBER_RANGE")

    def test_empty_set_rejected(self):
        with self.assertRaises(rx._SerializationError) as ctx:
            rx._serialize_value(set())
        self.assertEqual(ctx.exception.reason, "SER_EMPTY_SET")

    def test_mixed_set_rejected(self):
        with self.assertRaises(rx._SerializationError) as ctx:
            rx._serialize_value({1, "a"})
        self.assertEqual(ctx.exception.reason, "SER_SET_TYPE")

    def test_nested_set_rejected(self):
        with self.assertRaises(rx._SerializationError) as ctx:
            rx._serialize_value({frozenset({1}), frozenset({2})})
        self.assertEqual(ctx.exception.reason, "SER_NESTED_SET")

    def test_bool_in_set_rejected(self):
        with self.assertRaises(rx._SerializationError) as ctx:
            rx._serialize_value({True, False})
        self.assertEqual(ctx.exception.reason, "SER_SET_TYPE")

    def test_non_string_map_key_rejected(self):
        with self.assertRaises(rx._SerializationError) as ctx:
            rx._serialize_value({1: "x"})
        self.assertEqual(ctx.exception.reason, "SER_MAP_KEY_TYPE")

    def test_binary_rejected(self):
        for bad in (b"x", bytearray(b"y")):
            with self.assertRaises(rx._SerializationError) as ctx:
                rx._serialize_value(bad)
            self.assertEqual(ctx.exception.reason, "SER_UNSUPPORTED_BINARY")

    def test_unsupported_object_rejected(self):
        with self.assertRaises(rx._SerializationError) as ctx:
            rx._serialize_value(object())
        self.assertEqual(ctx.exception.reason, "SER_UNSUPPORTED_TYPE")

    def test_depth_guard(self):
        # Build a structure deeper than the depth guard.
        node = "leaf"
        for _ in range(rx._MAX_SERIALIZE_DEPTH + 2):
            node = {"n": node}
        with self.assertRaises(rx._SerializationError) as ctx:
            rx._serialize_value(node)
        self.assertEqual(ctx.exception.reason, "SER_DEPTH_EXCEEDED")

    def test_cycle_detected(self):
        d = {}
        d["self"] = d
        with self.assertRaises(rx._SerializationError) as ctx:
            rx._serialize_value(d)
        self.assertIn(ctx.exception.reason, ("SER_CYCLE_DETECTED", "SER_DEPTH_EXCEEDED"))


# ===========================================================================
# B - strict raw/prepared boundary; legitimate AV-like app maps
# ===========================================================================

class RawPreparedBoundaryTests(unittest.TestCase):
    def test_legit_app_map_with_av_like_value_key_is_valid(self):
        # A map VALUE that is itself a map containing a key named "S"/"N"/"M" is a
        # legitimate application map and must serialize normally (NOT be mistaken
        # for a prepared AttributeValue). Here "S"/"N" are MULTI-key maps, so even
        # the narrow single-key heuristic leaves them alone.
        out = rx._serialize_value({"S": "hello", "N": "world", "M": "map"})
        self.assertEqual(out, {"M": {"S": {"S": "hello"}, "N": {"S": "world"}, "M": {"S": "map"}}})

    def test_already_serialized_attribute_map_rejected(self):
        # A top-level attribute map whose EVERY value is already an AttributeValue
        # would be double-serialized; it must fail closed.
        already = {"PK": {"S": "REQ#x"}, "rev": {"N": "1"}}
        with self.assertRaises(rx._SerializationError) as ctx:
            rx._serialize_map(already)
        self.assertEqual(ctx.exception.reason, "SER_ALREADY_SERIALIZED")

    def test_bare_attribute_value_as_top_level_map_rejected(self):
        # A map that IS itself a bare AttributeValue (e.g. {"S": "x"}) is a
        # double-serialization error at the top level.
        with self.assertRaises(rx._SerializationError) as ctx:
            rx._serialize_map({"S": "x"})
        self.assertEqual(ctx.exception.reason, "SER_ALREADY_SERIALIZED")

    def test_mixed_raw_and_av_values_not_falsely_rejected(self):
        # A real raw attribute map (raw scalar values) serializes normally even if
        # ONE value happens to be an app map; not all values are AV-shaped.
        out = rx._serialize_map({"PK": "REQ#x", "meta": {"S": "hello"}})
        self.assertEqual(out["PK"], {"S": "REQ#x"})
        # meta is a raw 1-key app map -> serialized (NOT treated as a bare AV).
        self.assertEqual(out["meta"], {"M": {"S": {"S": "hello"}}})

    def test_single_key_app_value_named_S_with_nonstr_payload_is_app_map(self):
        # {"S": 5} is NOT a valid prepared S (payload is int), so it is treated as
        # an application map and serialized (key "S" preserved as attr name).
        self.assertEqual(rx._serialize_value({"S": 5}), {"M": {"S": {"N": "5"}}})


# ===========================================================================
# E - idempotency token
# ===========================================================================

class IdempotencyTokenTests(unittest.TestCase):
    def test_token_present_on_create_and_retire(self):
        self.assertTrue(rx.translate_create(real_create_spec(), TABLE).client_request_token)
        self.assertTrue(rx.translate_retire(real_retire_spec(), TABLE).client_request_token)

    def test_token_length_within_limit(self):
        tok = rx.translate_create(real_create_spec(), TABLE).client_request_token
        self.assertEqual(len(tok), 32)
        self.assertLessEqual(len(tok), 36)
        self.assertTrue(all(c in "0123456789abcdef" for c in tok))

    def test_update_has_no_token(self):
        p = rx.translate_update(real_update_spec(), TABLE)
        self.assertNotIn("ClientRequestToken", p.request)
        self.assertFalse(hasattr(p, "client_request_token"))

    def test_identical_request_identical_token(self):
        t1 = rx.translate_create(real_create_spec(), TABLE).client_request_token
        t2 = rx.translate_create(real_create_spec(), TABLE).client_request_token
        self.assertEqual(t1, t2)

    def test_different_table_changes_token(self):
        t1 = rx.translate_create(real_create_spec(), TABLE).client_request_token
        t2 = rx.translate_create(real_create_spec(), "other-table-xyz").client_request_token
        self.assertNotEqual(t1, t2)

    def test_different_op_changes_token(self):
        # create vs retire over the same key derive different tokens by domain+op.
        tc = rx.translate_create(real_create_spec(), TABLE).client_request_token
        tr = rx.translate_retire(real_retire_spec(), TABLE).client_request_token
        self.assertNotEqual(tc, tr)

    def test_changed_revision_changes_token(self):
        t1 = rx.translate_retire(real_retire_spec(revision=1), TABLE).client_request_token
        t2 = rx.translate_retire(real_retire_spec(revision=2), TABLE).client_request_token
        self.assertNotEqual(t1, t2)


# ===========================================================================
# F - translation refusals (fail closed, no partial result)
# ===========================================================================

class RefusalTests(unittest.TestCase):
    def test_update_missing_security_condition_refused(self):
        # Hand-craft an UpdateSpec lacking the retirement fence; must refuse, not
        # rewrite. (We mutate a copy's condition to simulate a weakened spec.)
        spec = real_update_spec()
        weakened = rw.UpdateSpec(
            key=spec.key,
            condition_expression=spec.condition_expression.replace(
                " AND (attribute_not_exists(#rl) OR #rl = :false)", ""),
            update_expression=spec.update_expression,
            names=spec.names, values=spec.values,
            advances_revision=spec.advances_revision,
            fenced_present=spec.fenced_present, fenced_absent=spec.fenced_absent)
        r = rx.translate_update(weakened, TABLE)
        self.assertIsInstance(r, rx.TranslationRefusal)
        self.assertEqual(r.reason, "MISSING_SECURITY_CONDITION")

    def test_update_malformed_key_refused(self):
        spec = real_update_spec()
        bad = rw.UpdateSpec(
            key={"PK": "REQ#x"},  # missing SK
            condition_expression=spec.condition_expression,
            update_expression=spec.update_expression,
            names=spec.names, values=spec.values,
            advances_revision=True, fenced_present=(), fenced_absent=())
        self.assertEqual(rx.translate_update(bad, TABLE).reason, "MALFORMED_KEY")

    def test_update_unserializable_value_refused_no_partial(self):
        spec = real_update_spec()
        poisoned_values = dict(spec.values)
        poisoned_values[":s0"] = 1.5  # a float - must be refused
        bad = rw.UpdateSpec(
            key=spec.key, condition_expression=spec.condition_expression,
            update_expression=spec.update_expression, names=spec.names,
            values=poisoned_values, advances_revision=True,
            fenced_present=spec.fenced_present, fenced_absent=spec.fenced_absent)
        r = rx.translate_update(bad, TABLE)
        self.assertIsInstance(r, rx.TranslationRefusal)
        self.assertEqual(r.reason, "SER_FLOAT_FORBIDDEN")
        self.assertNotIsInstance(r, rx.PreparedUpdate)

    def test_create_bad_operand_count_refused(self):
        spec = real_create_spec()
        bad = rw.CreateSpec(transact_items=(spec.transact_items[0],),  # only 1
                            lifetime_token=spec.lifetime_token,
                            minted_incarnation=spec.minted_incarnation,
                            advances_revision=False)
        self.assertEqual(rx.translate_create(bad, TABLE).reason, "BAD_OPERAND_COUNT")

    def test_create_missing_condition_refused(self):
        spec = real_create_spec()
        p0 = {"Put": {"Item": spec.transact_items[0]["Put"]["Item"]}}  # no ConditionExpression
        bad = rw.CreateSpec(transact_items=(p0, spec.transact_items[1]),
                            lifetime_token=spec.lifetime_token,
                            minted_incarnation=spec.minted_incarnation,
                            advances_revision=False)
        self.assertEqual(rx.translate_create(bad, TABLE).reason, "MISSING_CONDITION")

    def test_retire_bad_operand_count_refused(self):
        spec = real_retire_spec()
        bad = rw.RetireSpec(transact_items=(spec.transact_items[0],),
                            lifetime_token=spec.lifetime_token,
                            retires_revision=True, retired_at=spec.retired_at)
        self.assertEqual(rx.translate_retire(bad, TABLE).reason, "BAD_OPERAND_COUNT")

    def test_preflight_item_too_large_refused(self):
        # Inflate a create item beyond the conservative item byte bound.
        huge = {"company_id": "tenant_a", "status": "PENDING_REVIEW",
                "blob": "x" * (rx._MAX_ITEM_BYTES + 10)}
        spec = real_create_spec(item=huge)
        r = rx.translate_create(spec, TABLE)
        self.assertIsInstance(r, rx.TranslationRefusal)
        self.assertEqual(r.reason, "PREFLIGHT_ITEM_TOO_LARGE")


# ===========================================================================
# G - zero delete/unconditional, zero SDK/env, zero handler imports
# ===========================================================================

class SafetyPropertyTests(unittest.TestCase):
    def test_no_delete_or_unconditional_op_in_any_output(self):
        up = rx.translate_update(real_update_spec(), TABLE)
        cr = rx.translate_create(real_create_spec(), TABLE)
        rt = rx.translate_retire(real_retire_spec(), TABLE)
        # update: a conditional UpdateItem (ConditionExpression present, no Delete).
        self.assertIn("ConditionExpression", up.request)
        # create: only Put operands; retire: only Update operands; never Delete.
        for operand in cr.request["TransactItems"]:
            self.assertEqual(set(operand), {"Put"})
            self.assertIn("ConditionExpression", operand["Put"])
        for operand in rt.request["TransactItems"]:
            self.assertEqual(set(operand), {"Update"})
            self.assertIn("ConditionExpression", operand["Update"])

    def test_module_source_has_no_sdk_or_env_access(self):
        # Assert there is no ACTUAL import or SDK/env ACCESS. The docstring may
        # mention boto3 in prose, so we check import statements and call sites on
        # non-comment, non-docstring logic by scanning import lines and call
        # patterns rather than bare prose substrings.
        src = Path(rx.__file__).read_text(encoding="utf-8")
        # No import of the SDK or os.environ access anywhere.
        for forbidden in ("import boto3", "from boto3", "import botocore",
                          "from botocore", "import os", "os.environ", "getenv",
                          "transact_write_items(", "update_item(", "put_item(",
                          "delete_item(", "boto3.resource(", "TypeSerializer("):
            self.assertNotIn(forbidden, src, forbidden)
        # The string "boto3.client(" may appear in docstring prose describing the
        # shape the output WOULD feed; if present it must only ever be inside
        # double-backtick documentation quoting, never as an executable call.
        for idx in _all_indices(src, "boto3.client("):
            self.assertEqual(src[idx - 2:idx], "``",
                             "boto3.client( appears outside documentation prose")

    def test_module_imports_only_stdlib_and_contract(self):
        # The only non-stdlib import is common.request_write (the pure contract).
        src = Path(rx.__file__).read_text(encoding="utf-8")
        self.assertIn("from common.request_write import", src)
        self.assertNotIn("handlers", src)

    def test_not_imported_by_any_live_handler(self):
        handlers_dir = Path(rx.__file__).resolve().parents[1] / "handlers"
        offenders = []
        for py in handlers_dir.rglob("*.py"):
            text = py.read_text(encoding="utf-8")
            if "request_write_exec" in text:
                offenders.append(py.name)
        self.assertEqual(offenders, [], "request_write_exec imported by handler(s): " + repr(offenders))

    def test_honest_limitation_no_typeserializer_parity_claim(self):
        # We deliberately do NOT import boto3 to assert TypeSerializer parity.
        # The module may MENTION boto3 in prose (describing what it does not do),
        # but must contain no actual import; byte-parity is asserted only in the
        # future S0d-2 gate where the SDK is permitted.
        src = Path(rx.__file__).read_text(encoding="utf-8")
        # No ACTUAL import of the SDK (prose mentions of boto3/botocore in the
        # module docstring, describing what it does NOT do, are allowed).
        self.assertNotIn("import boto3", src)
        self.assertNotIn("from boto3", src)
        self.assertNotIn("import botocore", src)
        self.assertNotIn("from botocore", src)
        self.assertNotIn("TypeSerializer()", src)


# ===========================================================================
# Inherited-contract sanity: builders still produce the same specs
# ===========================================================================

class InheritedContractUnchangedTests(unittest.TestCase):
    def test_build_update_still_builds(self):
        self.assertIs(type(real_update_spec()), rw.UpdateSpec)

    def test_build_create_still_builds(self):
        self.assertIs(type(real_create_spec()), rw.CreateSpec)

    def test_build_retire_still_builds(self):
        self.assertIs(type(real_retire_spec()), rw.RetireSpec)


if __name__ == "__main__":
    unittest.main()
