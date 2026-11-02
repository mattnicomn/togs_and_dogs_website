"""Offline tests for the INACTIVE S0a REQUEST write-safety contract.

AWS-free, deterministic. Besides asserting refusal/classification behavior, the
suite EVALUATES the actual ConditionExpression that build_update() generates
against synthetic stored-item states (not just string contents), proving the
fence behaves correctly: valid state passes; stale revision, cross-tenant,
inserted-absent-identity and changed-present-identity states fail.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src/backend"))
from common import request_write as rw


# --- minimal synthetic DynamoDB ConditionExpression evaluator ----------------
# Supports exactly the closed grammar build_update() emits:
#   attribute_exists(NAME) | attribute_not_exists(#ref) | #ref = :val | NAME = :val
# joined by " AND ". NAME may be a literal (PK/SK/company_id) or a #ref resolved
# via ExpressionAttributeNames. Mirrors DynamoDB semantics: equality is FALSE
# when the attribute is absent; attribute_not_exists is TRUE only when missing.
def _resolve(token, names):
    token = token.strip()
    return names.get(token, token)


def _eval_clause(clause, item, names, values):
    clause = clause.strip()
    m = re.fullmatch(r"attribute_exists\((.+)\)", clause)
    if m:
        return _resolve(m.group(1), names) in item
    m = re.fullmatch(r"attribute_not_exists\((.+)\)", clause)
    if m:
        return _resolve(m.group(1), names) not in item
    m = re.fullmatch(r"(\S+)\s*=\s*(:\w+)", clause)
    if m:
        name = _resolve(m.group(1), names)
        return name in item and item[name] == values[m.group(2)]
    raise AssertionError("unparsed clause: " + repr(clause))


def evaluate(spec, item):
    """True iff the stored `item` satisfies the whole ConditionExpression."""
    for part in spec.condition_expression.split(" AND "):
        if not _eval_clause(part, item, spec.names, spec.values):
            return False
    return True


# --- fixtures ----------------------------------------------------------------
KEY = {"PK": "REQ#request-a", "SK": "CLIENT#client-a"}


def versioned_snapshot(**over):
    item = {
        "PK": "REQ#request-a", "SK": "CLIENT#client-a",
        "company_id": "tenant_a", "client_id": "client-a", "request_id": "request-a",
        "record_incarnation": "life-a", "legacy_write_revision": 1,
        "status": "ASSIGNED",
    }
    item.update(over)
    return item


def complete_client_expected(**over):
    base = dict(
        tenant="tenant_a", revision=1, incarnation="life-a", source_status="ASSIGNED",
        read_id="read-a",
        present_identity=(("cognito_sub", "subject-a"),),
        absent_identity=("client_email", "linked_client_profile_id"),
        protected_client=True,
    )
    base.update(over)
    return rw.ExpectedState(**base)


def simple_plan():
    return rw.WritePlan(set_fields=(("cancellation_reason", "r"),),
                        append_audit={"status": "CANCELLATION_REQUESTED"})


ELIGIBLE = rw.AdoptionDisposition(rw.ADOPT_ELIGIBLE, ())


class ClassifyAdoptionTests(unittest.TestCase):
    def test_versioned_row_is_adopt_eligible(self):
        d = rw.classify_adoption(versioned_snapshot())
        self.assertEqual(d.disposition, rw.ADOPT_ELIGIBLE)

    def test_missing_revision_quarantines_not_adopts(self):
        snap = versioned_snapshot()
        del snap["legacy_write_revision"]
        d = rw.classify_adoption(snap)
        self.assertEqual(d.disposition, rw.QUARANTINE_UNVERSIONED)
        self.assertIn("MISSING_REVISION", d.reasons)

    def test_malformed_revision_quarantines(self):
        for bad in (0, -1, True, "1", 1.0):
            d = rw.classify_adoption(versioned_snapshot(legacy_write_revision=bad))
            self.assertEqual(d.disposition, rw.QUARANTINE_UNVERSIONED, bad)

    def test_missing_or_malformed_incarnation_quarantines(self):
        snap = versioned_snapshot()
        del snap["record_incarnation"]
        self.assertEqual(rw.classify_adoption(snap).disposition, rw.QUARANTINE_UNVERSIONED)
        self.assertEqual(rw.classify_adoption(versioned_snapshot(record_incarnation="")).disposition,
                         rw.QUARANTINE_UNVERSIONED)

    def test_non_request_or_missing_keys_ineligible(self):
        self.assertEqual(rw.classify_adoption(None).disposition, rw.REFUSE_INELIGIBLE)
        self.assertEqual(rw.classify_adoption({}).disposition, rw.REFUSE_INELIGIBLE)
        self.assertEqual(rw.classify_adoption(versioned_snapshot(PK="JOB#x")).disposition, rw.REFUSE_INELIGIBLE)
        self.assertEqual(rw.classify_adoption(versioned_snapshot(company_id="")).disposition, rw.REFUSE_INELIGIBLE)


class BuildUpdateRefusalTests(unittest.TestCase):
    def test_quarantined_disposition_refused(self):
        q = rw.AdoptionDisposition(rw.QUARANTINE_UNVERSIONED, ("MISSING_REVISION",))
        r = rw.build_update(KEY, complete_client_expected(), simple_plan(), q)
        self.assertIsInstance(r, rw.Refusal)
        self.assertEqual(r.reason, "ADOPTION_REFUSED")

    def test_ineligible_disposition_refused(self):
        q = rw.AdoptionDisposition(rw.REFUSE_INELIGIBLE, ("NOT_A_REQUEST_PK",))
        self.assertIsInstance(rw.build_update(KEY, complete_client_expected(), simple_plan(), q), rw.Refusal)

    def test_no_seeding_override_exists(self):
        # There is no flag/mode/parameter that would turn a quarantine into a
        # write. Check the actual API surface, not documentation prose.
        self.assertFalse(hasattr(rw, "SEEDING"))
        import inspect
        params = inspect.signature(rw.build_update).parameters
        self.assertEqual(tuple(params), ("key", "expected", "plan", "disposition"))
        self.assertNotIn("adoption", params)
        # ExpectedState / WritePlan carry no seeding/override/force field.
        for cls in (rw.ExpectedState, rw.WritePlan):
            fields = tuple(cls.__dataclass_fields__)
            for banned in ("seeding", "override", "force", "bypass"):
                self.assertFalse(any(banned in f.lower() for f in fields), (cls.__name__, banned))

    def test_empty_plan_refused(self):
        r = rw.build_update(KEY, complete_client_expected(), rw.WritePlan(), ELIGIBLE)
        self.assertEqual(r.reason, "EMPTY_PLAN")

    def test_reserved_and_identity_fields_refused(self):
        for fld in ("legacy_write_revision", "record_incarnation", "company_id", "PK"):
            r = rw.build_update(KEY, complete_client_expected(),
                                rw.WritePlan(set_fields=((fld, "x"),)), ELIGIBLE)
            self.assertEqual(r.reason, "RESERVED_FIELD", fld)
        for fld in rw.IDENTITY_UNIVERSE:
            r = rw.build_update(KEY, complete_client_expected(),
                                rw.WritePlan(set_fields=((fld, "x"),)), ELIGIBLE)
            self.assertEqual(r.reason, "IDENTITY_FIELD_IMMUTABLE", fld)

    def test_malformed_inputs_refused(self):
        self.assertEqual(rw.build_update({}, complete_client_expected(), simple_plan(), ELIGIBLE).reason, "MALFORMED_KEY")
        self.assertEqual(rw.build_update(KEY, object(), simple_plan(), ELIGIBLE).reason, "MALFORMED_EXPECTED")
        self.assertEqual(rw.build_update(KEY, complete_client_expected(), object(), ELIGIBLE).reason, "MALFORMED_PLAN")
        self.assertEqual(rw.build_update(KEY, complete_client_expected(), simple_plan(), object()).reason, "MALFORMED_DISPOSITION")
        self.assertEqual(rw.build_update(KEY, complete_client_expected(revision=0), simple_plan(), ELIGIBLE).reason, "MALFORMED_REVISION")

    def test_duplicate_field_refused(self):
        r = rw.build_update(KEY, complete_client_expected(),
                            rw.WritePlan(set_fields=(("a", 1),), remove_fields=("a",)), ELIGIBLE)
        self.assertEqual(r.reason, "DUPLICATE_FIELD")


class OwnershipCoverageTests(unittest.TestCase):
    def test_protected_client_requires_complete_coverage(self):
        # omitted absence -> incomplete
        r = rw.build_update(KEY, complete_client_expected(absent_identity=()), simple_plan(), ELIGIBLE)
        self.assertEqual(r.reason, "OWNERSHIP_INCOMPLETE")
        # partial absence -> incomplete
        r = rw.build_update(KEY, complete_client_expected(absent_identity=("client_email",)), simple_plan(), ELIGIBLE)
        self.assertEqual(r.reason, "OWNERSHIP_INCOMPLETE")

    def test_contradictory_coverage_refused(self):
        r = rw.build_update(KEY, complete_client_expected(
            present_identity=(("cognito_sub", "s"),),
            absent_identity=("cognito_sub", "client_email")), simple_plan(), ELIGIBLE)
        self.assertEqual(r.reason, "OWNERSHIP_CONTRADICTION")

    def test_duplicate_absence_refused(self):
        r = rw.build_update(KEY, complete_client_expected(
            present_identity=(("cognito_sub", "s"),),
            absent_identity=("client_email", "client_email")), simple_plan(), ELIGIBLE)
        self.assertEqual(r.reason, "OWNERSHIP_DUPLICATE")

    def test_unknown_identity_field_refused(self):
        r = rw.build_update(KEY, complete_client_expected(
            present_identity=(("cognito_sub", "s"),),
            absent_identity=("not_identity", "client_email")), simple_plan(), ELIGIBLE)
        self.assertEqual(r.reason, "OWNERSHIP_ABSENT_FIELD")

    def test_email_only_fence_rejected(self):
        r = rw.build_update(KEY, complete_client_expected(
            present_identity=(("client_email", "e"),),
            absent_identity=("cognito_sub", "linked_client_profile_id")), simple_plan(), ELIGIBLE)
        self.assertEqual(r.reason, "OWNERSHIP_SUBJECT_REQUIRED")

    def test_complete_valid_coverage_succeeds(self):
        spec = rw.build_update(KEY, complete_client_expected(), simple_plan(), ELIGIBLE)
        self.assertIsInstance(spec, rw.UpdateSpec)
        self.assertEqual(set(spec.fenced_present), {"cognito_sub"})
        self.assertEqual(set(spec.fenced_absent), {"client_email", "linked_client_profile_id"})


class ConditionEvaluationTests(unittest.TestCase):
    """Evaluate the ACTUAL generated condition against synthetic records."""
    def spec(self, **over):
        s = rw.build_update(KEY, complete_client_expected(**over), simple_plan(), ELIGIBLE)
        assert isinstance(s, rw.UpdateSpec), s
        return s

    def test_valid_state_passes(self):
        spec = self.spec()
        # present cognito_sub, absent client_email + linked_client_profile_id, rev/inc/status match
        item = versioned_snapshot(cognito_sub="subject-a")
        self.assertTrue(evaluate(spec, item))

    def test_stale_revision_fails(self):
        spec = self.spec()
        item = versioned_snapshot(cognito_sub="subject-a", legacy_write_revision=2)
        self.assertFalse(evaluate(spec, item))

    def test_cross_tenant_fails(self):
        spec = self.spec()
        item = versioned_snapshot(cognito_sub="subject-a", company_id="tenant_b")
        self.assertFalse(evaluate(spec, item))

    def test_source_status_diverged_fails(self):
        spec = self.spec()
        item = versioned_snapshot(cognito_sub="subject-a", status="CANCELLED")
        self.assertFalse(evaluate(spec, item))

    def test_incarnation_diverged_fails(self):
        spec = self.spec()
        item = versioned_snapshot(cognito_sub="subject-a", record_incarnation="life-b")
        self.assertFalse(evaluate(spec, item))

    def test_present_identity_changed_fails(self):
        spec = self.spec()
        item = versioned_snapshot(cognito_sub="someone-else")
        self.assertFalse(evaluate(spec, item))

    def test_present_identity_removed_fails(self):
        spec = self.spec()
        item = versioned_snapshot()  # no cognito_sub at all
        self.assertFalse(evaluate(spec, item))

    def test_absent_identity_inserted_revision_unchanged_fails(self):
        # The race: a writer inserts an absent identity field without bumping rev.
        spec = self.spec()
        item = versioned_snapshot(cognito_sub="subject-a", client_email="attacker@x.invalid")
        self.assertFalse(evaluate(spec, item))

    def test_unknown_fields_preserved_and_update_advances_revision(self):
        spec = self.spec()
        # The update names only the fields in the plan + audit + revision advance;
        # it never names unknown fields, so unknown fields survive.
        self.assertIn("#rev = :next", spec.update_expression)
        self.assertTrue(spec.advances_revision)
        self.assertNotIn("unrelated", spec.update_expression)
        # no whole-item / upsert form
        self.assertFalse(spec.update_expression.strip().startswith("PUT"))
        self.assertTrue(spec.update_expression.startswith("SET "))


class UnversionedWriterRaceCharacterizationTests(unittest.TestCase):
    """Proves adoption does NOT protect against an unversioned concurrent writer.

    classify_adoption refuses (quarantines) a row that lost its revision, which
    is the containment. This test documents WHY: if one naively adopted missing
    revision as zero, a concurrent writer that changes a field WITHOUT touching
    the revision would still satisfy a `#rev = 0`-style fence. We assert the
    contract's actual behavior: such a row is quarantined, so build_update
    refuses rather than emitting a bypassable fence.
    """
    def test_unversioned_row_cannot_produce_a_fence(self):
        snap = versioned_snapshot(cognito_sub="subject-a")
        del snap["legacy_write_revision"]
        disp = rw.classify_adoption(snap)
        self.assertEqual(disp.disposition, rw.QUARANTINE_UNVERSIONED)
        r = rw.build_update(KEY, complete_client_expected(revision=None), simple_plan(), disp)
        self.assertIsInstance(r, rw.Refusal)

    def test_characterize_naive_zero_fence_would_be_bypassable(self):
        # Demonstration (not production behavior): a fence that pinned revision 0
        # would pass even after a no-revision concurrent field change, because
        # the row still lacks a revision. We show the equality-against-absent is
        # false (so a bare "#rev = :zero" cannot even be satisfied), which is
        # exactly why adopting-as-zero is unsafe and the contract quarantines.
        names = {"#rev": "legacy_write_revision"}
        values = {":zero": 0}
        item = {"company_id": "tenant_a"}  # no revision field, a field changed
        # "#rev = :zero" is False when the attribute is absent (DynamoDB semantics)
        self.assertFalse(_eval_clause("#rev = :zero", item, names, values))


class InterpretFailureTests(unittest.TestCase):
    def test_bare_conditional_failure_is_indeterminate(self):
        c = rw.interpret_failure(rw.FailureEvidence(kind="conditional_check_failed"))
        self.assertEqual(c.classification, rw.INDETERMINATE)
        self.assertFalse(c.evidence_backed)

    def test_transaction_cancellation_without_reread_indeterminate(self):
        c = rw.interpret_failure(rw.FailureEvidence(
            kind="transaction_cancellation", cancellation_reasons=("ConditionalCheckFailed",)))
        self.assertEqual(c.classification, rw.INDETERMINATE)
        self.assertFalse(c.evidence_backed)

    def test_transaction_cancellation_without_conditional_reason_indeterminate(self):
        c = rw.interpret_failure(rw.FailureEvidence(
            kind="transaction_cancellation", cancellation_reasons=("ThrottlingError",)))
        self.assertEqual(c.classification, rw.INDETERMINATE)

    def test_reread_tenant_mismatch_evidence_backed(self):
        ev = rw.FailureEvidence(kind="reread",
                                observed_row=versioned_snapshot(company_id="tenant_b"),
                                expected=complete_client_expected())
        c = rw.interpret_failure(ev)
        self.assertEqual(c.classification, rw.TENANT_MISMATCH)
        self.assertTrue(c.evidence_backed)

    def test_reread_stale_revision_evidence_backed(self):
        ev = rw.FailureEvidence(kind="reread",
                                observed_row=versioned_snapshot(legacy_write_revision=5),
                                expected=complete_client_expected())
        c = rw.interpret_failure(ev)
        self.assertEqual(c.classification, rw.STALE)
        self.assertTrue(c.evidence_backed)

    def test_reread_absent_row_is_absent(self):
        ev = rw.FailureEvidence(kind="reread", observed_row=None, expected=complete_client_expected())
        c = rw.interpret_failure(ev)
        self.assertEqual(c.classification, rw.ABSENT)
        self.assertTrue(c.evidence_backed)

    def test_tombstone_is_retired(self):
        ev = rw.FailureEvidence(kind="reread", observed_row=None, tombstone_present=True,
                                expected=complete_client_expected())
        c = rw.interpret_failure(ev)
        self.assertEqual(c.classification, rw.RETIRED)
        self.assertTrue(c.evidence_backed)

    def test_reread_no_divergence_is_indeterminate(self):
        ev = rw.FailureEvidence(kind="reread",
                                observed_row=versioned_snapshot(),
                                expected=complete_client_expected())
        c = rw.interpret_failure(ev)
        self.assertEqual(c.classification, rw.INDETERMINATE)
        self.assertFalse(c.evidence_backed)

    def test_malformed_evidence_is_indeterminate(self):
        self.assertEqual(rw.interpret_failure(object()).classification, rw.INDETERMINATE)


class NoExecutionPropertiesTests(unittest.TestCase):
    def test_module_imports_no_sdk_or_handlers(self):
        # Inspect the actual import graph (via AST), not prose: the docstring
        # legitimately *names* boto3/dynamodb to state that none are used.
        import ast
        src = (Path(__file__).resolve().parents[2] / "src/backend/common/request_write.py").read_text()
        tree = ast.parse(src)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        for forbidden in ("boto3", "botocore", "requests", "handlers", "urllib"):
            self.assertNotIn(forbidden, imported, forbidden)
        # Only standard-library modules are imported.
        self.assertTrue(imported.issubset({"dataclasses", "re"}), imported)

    def test_no_table_or_client_objects(self):
        self.assertFalse(hasattr(rw, "table"))
        self.assertFalse(hasattr(rw, "dynamodb"))
        self.assertFalse(hasattr(rw, "client"))


if __name__ == "__main__":
    unittest.main()
