"""Gate C3b.3g.2 / PR54 - absent-identity ownership guard.

Offline, synthetic. Evaluates the ACTUAL ConditionExpression that PR51
`transaction()` generates against synthetic stored-item states (not just the
string), proving that an identity field observed ABSENT is fenced with
attribute_not_exists so a concurrent insert cannot slip past the condition even
without a revision bump. No live AWS, SDK, or production data.
"""
import sys
import re
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src/backend"))
from common import cancellation_submission_contract as sc


ISSUER = "https://synthetic-issuer.example.invalid"
NOW = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)


# --- Minimal synthetic DynamoDB ConditionExpression evaluator ----------------
# Supports exactly the closed clause grammar PR51 transaction() emits:
#   attribute_exists(NAME) | attribute_not_exists(NAME_or_#ref)
#   #ref = :val | NAME = :val | attribute_type(#ref, :val)
#   (CLAUSE OR CLAUSE)
# joined by " AND ". NAME may be a literal (PK/SK/company_id/...) or a #ref
# resolved via ExpressionAttributeNames. This is a test oracle, not a DynamoDB
# reimplementation; it mirrors DynamoDB semantics for absent attributes:
#   - "#a = :v" is FALSE when the attribute is absent,
#   - attribute_not_exists is TRUE only when the attribute key is missing.
def _resolve_name(token, names):
    token = token.strip()
    return names.get(token, token)


def _py(av):
    # one-level DynamoDB AttributeValue -> python (enough for test items)
    (t, v), = av.items()
    if t == "S":
        return v
    if t == "N":
        return int(v)
    if t == "BOOL":
        return v
    if t == "NULL":
        return None
    if t == "L":
        return [_py(x) for x in v]
    if t == "M":
        return {k: _py(x) for k, x in v.items()}
    raise AssertionError("unsupported AV type " + t)


def _values(raw_values):
    return {k: _py(v) for k, v in raw_values.items()}


def _type_code(value):
    if isinstance(value, bool):
        return "BOOL"
    if isinstance(value, str):
        return "S"
    if isinstance(value, int):
        return "N"
    if isinstance(value, list):
        return "L"
    if value is None:
        return "NULL"
    return "?"


def _eval_clause(clause, item, names, values):
    clause = clause.strip()
    m = re.fullmatch(r"attribute_exists\((.+)\)", clause)
    if m:
        return _resolve_name(m.group(1), names) in item
    m = re.fullmatch(r"attribute_not_exists\((.+)\)", clause)
    if m:
        return _resolve_name(m.group(1), names) not in item
    m = re.fullmatch(r"attribute_type\((.+),\s*(:\w+)\)", clause)
    if m:
        name = _resolve_name(m.group(1), names)
        want = values[m.group(2)]
        return name in item and _type_code(item[name]) == want
    m = re.fullmatch(r"(\S+)\s*=\s*(:\w+)", clause)
    if m:
        name = _resolve_name(m.group(1), names)
        # equality is false if the attribute is absent (DynamoDB semantics)
        return name in item and item[name] == values[m.group(2)]
    raise AssertionError("unparsed clause: " + repr(clause))


def evaluate(condition, item, names, raw_values):
    """Return True iff the stored `item` satisfies the whole ConditionExpression."""
    values = _values(raw_values)
    # split top-level " AND ", honoring the single parenthesised OR group
    parts = []
    depth = 0
    buf = ""
    tokens = condition.split(" AND ")
    # Re-join tokens that were split inside a parenthesised group.
    for tok in tokens:
        buf = tok if not buf else buf + " AND " + tok
        depth += tok.count("(") - tok.count(")")
        if depth == 0:
            parts.append(buf)
            buf = ""
    assert depth == 0 and not buf, "unbalanced condition"
    for part in parts:
        part = part.strip()
        mm = re.fullmatch(r"\((.+)\)", part)
        if mm and " OR " in mm.group(1):
            if not any(_eval_clause(c, item, names, values) for c in mm.group(1).split(" OR ")):
                return False
        else:
            if not _eval_clause(part, item, names, values):
                return False
    return True


# --- Fixture builders --------------------------------------------------------
def make_submission():
    return sc.Submission("tenant_a", "client-a", "request-a", ISSUER, "subject-a", "operation-a", "a reason")


def stored_request(**overrides):
    """Baseline APPROVED-era request item with ONLY cognito_sub present as the
    fenced identity; client_email and linked_client_profile_id are ABSENT."""
    item = {
        "PK": "REQ#request-a", "SK": "CLIENT#client-a",
        "company_id": "tenant_a", "client_id": "client-a", "request_id": "request-a",
        "record_incarnation": "life-a", "legacy_write_revision": 1,
        "status": "ASSIGNED", "start_date": "2026-11-05",
        "cognito_sub": "subject-a",
    }
    item.update(overrides)
    return item


def build_transaction(absent_fields, present_bindings=(("cognito_sub", "subject-a"),), snap_status="ASSIGNED"):
    sub = make_submission()
    snap = sc.Snapshot("tenant_a", "client-a", "request-a", "life-a", 1, snap_status, True, "2026-11-05")
    access = sc.BookingAccess(
        "tenant_a", "client-a", "request-a", ISSUER, "subject-a", "client",
        "life-a", 1, present_bindings, True, True, True, True, "read-a",
        absent_fields=absent_fields,
    )
    assumption = sc.StatusAssumption(snap_status, True, "SYNTHETIC_ONLY", "DESIGN_ONLY_TEST")
    plan = sc.prepare(sub, access, snap, NOW, assumption)
    return sc.transaction(plan, "petcare-hero-table")


def request_update(txn):
    update = txn["TransactItems"][0]["Update"]
    return update["ConditionExpression"], update["ExpressionAttributeNames"], update["ExpressionAttributeValues"]


class AbsentIdentityGuardTests(unittest.TestCase):

    def test_absent_field_fenced_with_attribute_not_exists(self):
        _, names, _ = request_update(build_transaction(("client_email", "linked_client_profile_id")))
        cond, _, _ = request_update(build_transaction(("client_email", "linked_client_profile_id")))
        # The two absent fields must each appear under attribute_not_exists.
        fenced = {names[n] for n in names if ("attribute_not_exists(" + n + ")") in cond}
        self.assertIn("client_email", fenced)
        self.assertIn("linked_client_profile_id", fenced)
        # Present field still fenced by equality, not attribute_not_exists.
        self.assertIn("#a0 = :a0", cond)

    def test_absent_field_remains_absent_condition_passes(self):
        cond, names, values = request_update(build_transaction(("client_email", "linked_client_profile_id")))
        item = stored_request()  # no client_email, no linked_client_profile_id
        self.assertTrue(evaluate(cond, item, names, values))

    def test_absent_field_inserted_revision_unchanged_denies(self):
        cond, names, values = request_update(build_transaction(("client_email", "linked_client_profile_id")))
        # Concurrent writer inserts an identity field WITHOUT bumping revision.
        item = stored_request(client_email="attacker@example.invalid")
        self.assertFalse(evaluate(cond, item, names, values))

    def test_absent_field_inserted_revision_changed_denies(self):
        cond, names, values = request_update(build_transaction(("client_email", "linked_client_profile_id")))
        item = stored_request(linked_client_profile_id="other-client", legacy_write_revision=2)
        # Revision pin (#rev = :rev) AND attribute_not_exists both fail.
        self.assertFalse(evaluate(cond, item, names, values))

    def test_present_field_changed_removed_or_null_denies(self):
        cond, names, values = request_update(build_transaction(("client_email", "linked_client_profile_id")))
        # changed
        self.assertFalse(evaluate(cond, stored_request(cognito_sub="other"), names, values))
        # removed
        removed = stored_request()
        del removed["cognito_sub"]
        self.assertFalse(evaluate(cond, removed, names, values))
        # NULL
        self.assertFalse(evaluate(cond, stored_request(cognito_sub=None), names, values))

    def test_existing_successful_transaction_remains_valid(self):
        cond, names, values = request_update(build_transaction(("client_email", "linked_client_profile_id")))
        # The clean snapshot (correct revision/incarnation/status, present field
        # intact, absent fields still absent) must satisfy the condition.
        self.assertTrue(evaluate(cond, stored_request(), names, values))
        # And with NO absent fields supplied (legacy path), the condition still
        # validates a clean present-only fence.
        cond2, names2, values2 = request_update(
            build_transaction((), present_bindings=(("cognito_sub", "subject-a"),))
        )
        self.assertTrue(evaluate(cond2, stored_request(), names2, values2))

    def test_conflicting_absence_evidence_is_rejected(self):
        # A field claimed BOTH present (binding) and absent must be refused by
        # authorize() before any transaction is built.
        with self.assertRaisesRegex(sc.SubmissionError, "ACCESS_ABSENCE_BINDING"):
            build_transaction(("cognito_sub",), present_bindings=(("cognito_sub", "subject-a"),))

    def test_forged_absence_evidence_unknown_field_rejected(self):
        with self.assertRaisesRegex(sc.SubmissionError, "ACCESS_ABSENCE_BINDING"):
            build_transaction(("not_an_identity_field",))
        with self.assertRaisesRegex(sc.SubmissionError, "ACCESS_ABSENCE_BINDING"):
            build_transaction(("client_email", "client_email"))  # duplicate

    def test_condition_and_transaction_size_within_limits(self):
        txn = build_transaction(("client_email", "linked_client_profile_id"))
        cond, _, _ = request_update(txn)
        self.assertLessEqual(len(cond.encode()), 4096)
        # transaction() already asserts the 300KB TransactWriteItems envelope;
        # reaching here means it passed.
        self.assertEqual(len(txn["TransactItems"]), 4)


if __name__ == "__main__":
    unittest.main()
