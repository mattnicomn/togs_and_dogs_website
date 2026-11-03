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
    """True iff the stored `item` satisfies the whole ConditionExpression.

    Handles flat clauses joined by " AND " plus a single parenthesized OR group
    (the mandatory retirement fence `(attribute_not_exists(#rl) OR #rl = :false)`).
    """
    names, values = spec.names, spec.values
    # Re-join tokens split inside a parenthesized group.
    parts, depth, buf = [], 0, ""
    for tok in spec.condition_expression.split(" AND "):
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
    # Supplies an explicit OBSERVED retirement tag (FALSE) by default so the
    # fixture reflects a caller that actually looked up retired_lifetime. Tests
    # that exercise the evidence gate override retirement_marker explicitly.
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

    def test_reread_observed_absence_is_absent(self):
        # Finding B: an observed absence is an explicit observation - row None AND
        # an explicit tombstone_present=False - not merely a missing re-read row.
        ev = rw.FailureEvidence(kind="reread", observed_row=None, tombstone_present=False,
                                expected=complete_client_expected())
        c = rw.interpret_failure(ev)
        self.assertEqual(c.classification, rw.ABSENT)
        self.assertTrue(c.evidence_backed)

    def test_reread_missing_row_without_observation_is_indeterminate(self):
        # Finding B: observed_row=None with NO explicit tombstone signal is a
        # MISSING re-read, not a proven absence.
        ev = rw.FailureEvidence(kind="reread", observed_row=None, expected=complete_client_expected())
        c = rw.interpret_failure(ev)
        self.assertEqual(c.classification, rw.INDETERMINATE)
        self.assertFalse(c.evidence_backed)

    def test_reread_without_expected_is_indeterminate(self):
        # Finding B: no ExpectedState baseline -> cannot classify.
        ev = rw.FailureEvidence(kind="reread", observed_row=None, tombstone_present=False, expected=None)
        c = rw.interpret_failure(ev)
        self.assertEqual(c.classification, rw.INDETERMINATE)
        self.assertFalse(c.evidence_backed)

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
        # Only standard-library modules are imported (S0b adds hashlib+json for
        # the canonical lifetime token; Correction A adds datetime for ISO-8601
        # UTC validation; still no SDK/network/DB).
        self.assertTrue(imported.issubset({"dataclasses", "re", "hashlib", "json", "datetime"}), imported)

    def test_no_table_or_client_objects(self):
        self.assertFalse(hasattr(rw, "table"))
        self.assertFalse(hasattr(rw, "dynamodb"))
        self.assertFalse(hasattr(rw, "client"))


class FindingA_KeyAndExpectedBindingTests(unittest.TestCase):
    """Finding A: non-REQUEST keys refused; request/client/tenant bound in cond."""
    def test_non_request_key_refused(self):
        for bad in ({"PK": "JOB#x", "SK": "METADATA"},
                    {"PK": "REQ#a", "SK": "METADATA"},
                    {"PK": "COMPANY#a", "SK": "CLIENT#a"}):
            r = rw.build_update(bad, complete_client_expected(), simple_plan(), ELIGIBLE)
            self.assertIsInstance(r, rw.Refusal, bad)
            self.assertEqual(r.reason, "MALFORMED_KEY", bad)

    def test_key_with_extra_attributes_refused(self):
        r = rw.build_update({"PK": "REQ#a", "SK": "CLIENT#a", "x": 1},
                            complete_client_expected(), simple_plan(), ELIGIBLE)
        self.assertEqual(r.reason, "MALFORMED_KEY")

    def test_malformed_identifier_in_key_refused(self):
        r = rw.build_update({"PK": "REQ#bad id!", "SK": "CLIENT#client-a"},
                            complete_client_expected(), simple_plan(), ELIGIBLE)
        self.assertEqual(r.reason, "MALFORMED_KEY")

    def test_mismatched_expected_ids_refused(self):
        r = rw.build_update(KEY, complete_client_expected(request_id="other"), simple_plan(), ELIGIBLE)
        self.assertEqual(r.reason, "KEY_EXPECTED_MISMATCH")
        r = rw.build_update(KEY, complete_client_expected(client_id="other"), simple_plan(), ELIGIBLE)
        self.assertEqual(r.reason, "KEY_EXPECTED_MISMATCH")

    def test_request_client_bound_into_condition(self):
        spec = rw.build_update(KEY, complete_client_expected(), simple_plan(), ELIGIBLE)
        self.assertIsInstance(spec, rw.UpdateSpec)
        self.assertIn("request_id = :reqid", spec.condition_expression)
        self.assertIn("client_id = :cliid", spec.condition_expression)
        self.assertEqual(spec.values[":reqid"], "request-a")
        self.assertEqual(spec.values[":cliid"], "client-a")

    def test_condition_evaluates_request_client_against_item(self):
        spec = rw.build_update(KEY, complete_client_expected(), simple_plan(), ELIGIBLE)
        good = versioned_snapshot(cognito_sub="subject-a")
        self.assertTrue(evaluate(spec, good))
        # An item whose own request_id/client_id disagree with the key fails.
        self.assertFalse(evaluate(spec, versioned_snapshot(cognito_sub="subject-a", request_id="other")))
        self.assertFalse(evaluate(spec, versioned_snapshot(cognito_sub="subject-a", client_id="other")))


class FindingB_FailureEvidenceTests(unittest.TestCase):
    """Finding B: never classify from incomplete/malformed reread evidence."""
    def test_missing_expected_is_indeterminate(self):
        for ev in (rw.FailureEvidence(kind="reread", observed_row=None, tombstone_present=False, expected=None),
                   rw.FailureEvidence(kind="reread", observed_row=versioned_snapshot(), expected=None)):
            c = rw.interpret_failure(ev)
            self.assertEqual(c.classification, rw.INDETERMINATE)
            self.assertFalse(c.evidence_backed)

    def test_missing_reread_vs_observed_absence(self):
        # No observation signal -> MISSING (INDETERMINATE)
        c = rw.interpret_failure(rw.FailureEvidence(kind="reread", observed_row=None,
                                                    expected=complete_client_expected()))
        self.assertEqual(c.classification, rw.INDETERMINATE)
        # Explicit observed absence -> ABSENT
        c = rw.interpret_failure(rw.FailureEvidence(kind="reread", observed_row=None, tombstone_present=False,
                                                    expected=complete_client_expected()))
        self.assertEqual(c.classification, rw.ABSENT)
        self.assertTrue(c.evidence_backed)

    def test_non_bool_tombstone_is_malformed(self):
        for bad in (1, "yes", [1], 0, ""):
            ev = rw.FailureEvidence(kind="reread", observed_row=None, tombstone_present=bad,
                                    expected=complete_client_expected())
            c = rw.interpret_failure(ev)
            self.assertEqual(c.classification, rw.INDETERMINATE, bad)
            self.assertFalse(c.evidence_backed, bad)

    def test_exact_true_tombstone_is_retired(self):
        ev = rw.FailureEvidence(kind="reread", observed_row=None, tombstone_present=True,
                                expected=complete_client_expected())
        c = rw.interpret_failure(ev)
        self.assertEqual(c.classification, rw.RETIRED)
        self.assertTrue(c.evidence_backed)

    def test_transaction_reason_alone_is_indeterminate(self):
        # ConditionalCheckFailed WITHOUT a re-read cannot name the failed clause.
        ev = rw.FailureEvidence(kind="transaction_cancellation",
                                cancellation_reasons=("ConditionalCheckFailed",),
                                observed_row=None, expected=None)
        c = rw.interpret_failure(ev)
        self.assertEqual(c.classification, rw.INDETERMINATE)
        self.assertFalse(c.evidence_backed)

    def test_transaction_reason_with_full_reread_classifies(self):
        ev = rw.FailureEvidence(kind="transaction_cancellation",
                                cancellation_reasons=("ConditionalCheckFailed",),
                                observed_row=versioned_snapshot(company_id="tenant_b"),
                                expected=complete_client_expected())
        c = rw.interpret_failure(ev)
        self.assertEqual(c.classification, rw.TENANT_MISMATCH)
        self.assertTrue(c.evidence_backed)

    def test_malformed_cancellation_reasons_indeterminate(self):
        for bad in (5, "ConditionalCheckFailed"):
            c = rw.interpret_failure(rw.FailureEvidence(kind="transaction_cancellation",
                                                        cancellation_reasons=bad))
            self.assertEqual(c.classification, rw.INDETERMINATE, bad)


class FindingC_AuditConflictTests(unittest.TestCase):
    """Finding C: audit_log may only be touched via append_audit."""
    def test_set_audit_log_plus_append_refused(self):
        r = rw.build_update(KEY, complete_client_expected(),
                            rw.WritePlan(set_fields=(("audit_log", [{"x": 1}]),), append_audit={"y": 2}),
                            ELIGIBLE)
        self.assertEqual(r.reason, "AUDIT_FIELD_CONFLICT")

    def test_remove_audit_log_plus_append_refused(self):
        r = rw.build_update(KEY, complete_client_expected(),
                            rw.WritePlan(remove_fields=("audit_log",), append_audit={"y": 2}),
                            ELIGIBLE)
        self.assertEqual(r.reason, "AUDIT_FIELD_CONFLICT")

    def test_set_audit_log_alone_refused(self):
        r = rw.build_update(KEY, complete_client_expected(),
                            rw.WritePlan(set_fields=(("audit_log", [{"x": 1}]),)), ELIGIBLE)
        self.assertEqual(r.reason, "AUDIT_FIELD_CONFLICT")

    def test_append_audit_alone_still_works(self):
        spec = rw.build_update(KEY, complete_client_expected(),
                               rw.WritePlan(append_audit={"status": "CANCELLATION_REQUESTED"}), ELIGIBLE)
        self.assertIsInstance(spec, rw.UpdateSpec)
        self.assertIn("list_append(if_not_exists(#audit, :emptylist), :auditentry)", spec.update_expression)
        audit_names = [k for k, v in spec.names.items() if v == "audit_log"]
        self.assertEqual(len(audit_names), 1)


class FindingD_InputShapeTests(unittest.TestCase):
    """Finding D: malformed/non-iterable/string collections refused cleanly."""
    def test_non_iterable_set_remove_refused_not_raised(self):
        for plan in (rw.WritePlan(set_fields=5), rw.WritePlan(remove_fields=5),
                     rw.WritePlan(set_fields=None), rw.WritePlan(remove_fields=None)):
            r = rw.build_update(KEY, complete_client_expected(), plan, ELIGIBLE)
            self.assertIsInstance(r, rw.Refusal)
            self.assertEqual(r.reason, "MALFORMED_PLAN_COLLECTION")

    def test_string_as_set_or_remove_collection_refused(self):
        self.assertEqual(rw.build_update(KEY, complete_client_expected(),
                                         rw.WritePlan(set_fields="ab"), ELIGIBLE).reason,
                         "MALFORMED_PLAN_COLLECTION")
        # The previously-silent destructive char-by-char REMOVE is now refused.
        r = rw.build_update(KEY, complete_client_expected(),
                            rw.WritePlan(remove_fields="audit_log"), ELIGIBLE)
        self.assertEqual(r.reason, "MALFORMED_PLAN_COLLECTION")

    def test_protected_identity_non_iterable_refused_not_raised(self):
        r = rw.build_update(KEY, complete_client_expected(present_identity=5, absent_identity=(),
                                                          protected_client=True),
                            simple_plan(), ELIGIBLE)
        self.assertIsInstance(r, rw.Refusal)
        self.assertEqual(r.reason, "OWNERSHIP_EVIDENCE_SHAPE")
        r = rw.build_update(KEY, complete_client_expected(present_identity=(("cognito_sub", "s"),),
                                                          absent_identity=5, protected_client=True),
                            simple_plan(), ELIGIBLE)
        self.assertEqual(r.reason, "OWNERSHIP_EVIDENCE_SHAPE")

    def test_nonprotected_identity_non_iterable_refused_not_raised(self):
        r = rw.build_update(KEY, complete_client_expected(protected_client=False, present_identity=5,
                                                          absent_identity=(), incarnation="life-a",
                                                          revision=1),
                            simple_plan(), ELIGIBLE)
        self.assertIsInstance(r, rw.Refusal)
        self.assertEqual(r.reason, "OWNERSHIP_EVIDENCE_SHAPE")

    def test_string_identity_collections_refused(self):
        r = rw.build_update(KEY, complete_client_expected(protected_client=False,
                                                          present_identity="cognito_sub",
                                                          absent_identity=()),
                            simple_plan(), ELIGIBLE)
        self.assertEqual(r.reason, "OWNERSHIP_EVIDENCE_SHAPE")

    def test_no_typeerror_escapes_for_any_malformed_collection(self):
        # Exhaustive: none of these should raise; all must be clean Refusals.
        bad_plans = [
            rw.WritePlan(set_fields=5), rw.WritePlan(set_fields="xy"),
            rw.WritePlan(remove_fields=5), rw.WritePlan(remove_fields="field"),
            rw.WritePlan(set_fields=(("a", 1, 2),)), rw.WritePlan(set_fields=((5, "v"),)),
        ]
        for plan in bad_plans:
            try:
                r = rw.build_update(KEY, complete_client_expected(), plan, ELIGIBLE)
            except Exception as e:  # noqa: BLE001 - the whole point is no escape
                self.fail(f"raised {type(e).__name__} for {plan}")
            self.assertIsInstance(r, rw.Refusal)


class Correction1_MandatoryIncarnationTests(unittest.TestCase):
    """PR55 hardening C1: an ADOPT_ELIGIBLE write MUST pin a valid incarnation."""
    def test_eligible_missing_incarnation_refused(self):
        r = rw.build_update(KEY, complete_client_expected(incarnation=None), simple_plan(), ELIGIBLE)
        self.assertIsInstance(r, rw.Refusal)
        self.assertEqual(r.reason, "MALFORMED_INCARNATION")

    def test_eligible_malformed_incarnation_refused(self):
        for bad in ("", "bad id!", 5, True, "x" * 129):
            r = rw.build_update(KEY, complete_client_expected(incarnation=bad), simple_plan(), ELIGIBLE)
            self.assertIsInstance(r, rw.Refusal, bad)
            self.assertEqual(r.reason, "MALFORMED_INCARNATION", bad)

    def test_eligible_valid_incarnation_builds_and_pins(self):
        spec = rw.build_update(KEY, complete_client_expected(), simple_plan(), ELIGIBLE)
        self.assertIsInstance(spec, rw.UpdateSpec)
        self.assertIn("#inc = :inc", spec.condition_expression)
        self.assertEqual(spec.names["#inc"], "record_incarnation")
        self.assertEqual(spec.values[":inc"], "life-a")

    def test_lifetime_fence_never_omitted_changed_incarnation_fails(self):
        # The lifetime fence is always present; an item whose incarnation changed
        # must FAIL the actual generated condition.
        spec = rw.build_update(KEY, complete_client_expected(), simple_plan(), ELIGIBLE)
        good = versioned_snapshot(cognito_sub="subject-a")
        self.assertTrue(evaluate(spec, good))
        changed = versioned_snapshot(cognito_sub="subject-a", record_incarnation="DIFFERENT-LIFE")
        self.assertFalse(evaluate(spec, changed))
        removed = versioned_snapshot(cognito_sub="subject-a")
        del removed["record_incarnation"]
        self.assertFalse(evaluate(spec, removed))

    def test_no_seeding_override_still_absent(self):
        # C1 tightens the eligible path; it introduces no bypass.
        self.assertFalse(hasattr(rw, "SEEDING"))
        import inspect
        self.assertEqual(tuple(inspect.signature(rw.build_update).parameters),
                         ("key", "expected", "plan", "disposition"))


class Correction2_RequestIdentityMatchTests(unittest.TestCase):
    """PR55 hardening C2: classify_adoption requires PK/SK ids == persisted ids."""
    def test_request_id_key_mismatch_ineligible(self):
        snap = versioned_snapshot(request_id="other-request")
        d = rw.classify_adoption(snap)
        self.assertEqual(d.disposition, rw.REFUSE_INELIGIBLE)
        self.assertIn("REQUEST_ID_KEY_MISMATCH", d.reasons)

    def test_client_id_key_mismatch_ineligible(self):
        snap = versioned_snapshot(client_id="other-client")
        d = rw.classify_adoption(snap)
        self.assertEqual(d.disposition, rw.REFUSE_INELIGIBLE)
        self.assertIn("CLIENT_ID_KEY_MISMATCH", d.reasons)

    def test_both_identifiers_mismatch_ineligible(self):
        snap = versioned_snapshot(request_id="x", client_id="y")
        d = rw.classify_adoption(snap)
        self.assertEqual(d.disposition, rw.REFUSE_INELIGIBLE)
        self.assertIn("REQUEST_ID_KEY_MISMATCH", d.reasons)
        self.assertIn("CLIENT_ID_KEY_MISMATCH", d.reasons)

    def test_malformed_key_identifier_ineligible(self):
        # PK/SK correctly prefixed but ids are malformed -> ineligible.
        snap = versioned_snapshot(PK="REQ#bad id!", SK="CLIENT#bad id!",
                                  request_id="bad id!", client_id="bad id!")
        d = rw.classify_adoption(snap)
        self.assertEqual(d.disposition, rw.REFUSE_INELIGIBLE)
        self.assertIn("MALFORMED_KEY_IDENTIFIER", d.reasons)

    def test_valid_complete_snapshot_still_eligible(self):
        # A fully consistent row (PK/SK ids == persisted ids, valid rev+inc) is
        # still ADOPT_ELIGIBLE - the tightening does not over-refuse.
        d = rw.classify_adoption(versioned_snapshot())
        self.assertEqual(d.disposition, rw.ADOPT_ELIGIBLE)
        self.assertEqual(d.reasons, ())

    def test_wrong_prefix_still_ineligible(self):
        self.assertEqual(rw.classify_adoption(versioned_snapshot(PK="JOB#x")).disposition,
                         rw.REFUSE_INELIGIBLE)


# ===========================================================================
# S0b - build_create tests
# ===========================================================================

def eval_put_condition(put, item):
    """Evaluate a create-only Put ConditionExpression against a synthetic item.

    The S0b Put grammar is exactly:
      attribute_not_exists(PK) AND attribute_not_exists(SK)
    with literal names (no ExpressionAttributeNames). item is the CURRENT stored
    state at that key (dict) or None if absent.
    """
    cond = put["Put"]["ConditionExpression"]
    cur = item or {}
    ok = True
    for clause in cond.split(" AND "):
        m = re.fullmatch(r"attribute_not_exists\((.+)\)", clause.strip())
        assert m, "unexpected S0b clause: " + clause
        ok = ok and (m.group(1) not in cur)
    return ok


def create_intent(**over):
    base = dict(tenant="tenant_a", request_id="request-a", client_id="client-a",
                incarnation="life-a", created_at="2026-11-01T12:00:00+00:00",
                item={"company_id": "tenant_a", "status": "PENDING_REVIEW",
                      "client_email": "owner@example.invalid"})
    base.update(over)
    return rw.CreateIntent(**base)


def absent_lifetime(token):
    return rw.LifetimeEvidence(state=rw.LIFETIME_ABSENT, token=token)


def derived_token():
    # Recompute via the module helper for binding the evidence token.
    return rw._request_lifetime_token("tenant_a", ("REQ#request-a", "CLIENT#client-a"))


class S0bCanonicalTokenTests(unittest.TestCase):
    """The S0b lifetime token must be byte-identical to the inactive contracts."""
    def test_token_matches_submission_contract(self):
        import importlib
        sc = importlib.import_module("common.cancellation_submission_contract")
        sub = sc.Submission("tenant_a", "client-a", "request-a",
                            "https://issuer.example.invalid", "actor-a", "operation-a", "r")
        self.assertEqual(derived_token(), sub.token())

    def test_token_matches_foundation_and_access(self):
        import importlib
        found = importlib.import_module("common.cancellation_adapter_foundation")
        acc = importlib.import_module("common.cancellation_access_adapter")
        fq = found.Query("tenant_a", "client-a", "request-a",
                         "https://issuer.example.invalid", "subject-a", "client", "operation-a", "r")
        aq = acc.Query("tenant_a", "client-a", "request-a", "operation-a", "r")
        self.assertEqual(derived_token(), fq.token())
        self.assertEqual(derived_token(), aq.token())

    def test_token_is_deterministic(self):
        self.assertEqual(derived_token(), derived_token())


class S0bBuildCreatePositiveTests(unittest.TestCase):
    def test_valid_create_builds_two_create_only_puts(self):
        tok = derived_token()
        spec = rw.build_create(KEY, create_intent(), absent_lifetime(tok))
        self.assertIsInstance(spec, rw.CreateSpec)
        self.assertEqual(len(spec.transact_items), 2)
        req, life = spec.transact_items
        self.assertEqual(req["Put"]["ConditionExpression"],
                         "attribute_not_exists(PK) AND attribute_not_exists(SK)")
        self.assertEqual(life["Put"]["ConditionExpression"],
                         "attribute_not_exists(PK) AND attribute_not_exists(SK)")
        self.assertFalse(spec.advances_revision)
        self.assertEqual(spec.lifetime_token, tok)

    def test_request_item_has_helper_owned_fields(self):
        spec = rw.build_create(KEY, create_intent(), absent_lifetime(derived_token()))
        req_item = spec.transact_items[0]["Put"]["Item"]
        self.assertEqual(req_item["legacy_write_revision"], 1)
        self.assertEqual(req_item["record_incarnation"], "life-a")
        self.assertEqual(req_item["PK"], "REQ#request-a")
        self.assertEqual(req_item["SK"], "CLIENT#client-a")
        self.assertEqual(req_item["company_id"], "tenant_a")
        self.assertEqual(req_item["created_at"], "2026-11-01T12:00:00+00:00")

    def test_lifetime_item_shape(self):
        tok = derived_token()
        spec = rw.build_create(KEY, create_intent(), absent_lifetime(tok))
        life_item = spec.transact_items[1]["Put"]["Item"]
        self.assertEqual(life_item["PK"], "LIFETIME#" + tok)
        self.assertEqual(life_item["SK"], "PERMANENT")
        self.assertEqual(life_item["retired"], False)
        self.assertEqual(life_item["incarnation"], "life-a")

    def test_both_conditions_pass_on_absent_state(self):
        spec = rw.build_create(KEY, create_intent(), absent_lifetime(derived_token()))
        req, life = spec.transact_items
        # No existing REQUEST and no existing lifetime -> both create-only pass.
        self.assertTrue(eval_put_condition(req, None))
        self.assertTrue(eval_put_condition(life, None))


class S0bCollisionAndConcurrencyTests(unittest.TestCase):
    def test_request_collision_fails_condition(self):
        spec = rw.build_create(KEY, create_intent(), absent_lifetime(derived_token()))
        req = spec.transact_items[0]
        existing = {"PK": "REQ#request-a", "SK": "CLIENT#client-a", "company_id": "tenant_a"}
        self.assertFalse(eval_put_condition(req, existing))

    def test_stale_absence_lifetime_now_present_fails_condition(self):
        # Evidence said ABSENT (prior read), but the lifetime now exists: the
        # create-only lifetime Put condition evaluates False -> transaction would
        # cancel. No double-create / no overwrite (atomic self-fencing).
        spec = rw.build_create(KEY, create_intent(), absent_lifetime(derived_token()))
        life = spec.transact_items[1]
        now_present = {"PK": life["Put"]["Item"]["PK"], "SK": "PERMANENT", "retired": False}
        self.assertFalse(eval_put_condition(life, now_present))

    def test_concurrent_request_present_fails_even_if_lifetime_absent(self):
        spec = rw.build_create(KEY, create_intent(), absent_lifetime(derived_token()))
        req = spec.transact_items[0]
        self.assertFalse(eval_put_condition(req, {"PK": "REQ#request-a", "SK": "CLIENT#client-a"}))


class S0bInvalidInputTests(unittest.TestCase):
    def test_malformed_intent_or_evidence(self):
        self.assertEqual(rw.build_create(KEY, object(), absent_lifetime(derived_token())).reason, "MALFORMED_INTENT")
        self.assertEqual(rw.build_create(KEY, create_intent(), object()).reason, "MALFORMED_LIFETIME_EVIDENCE")

    def test_non_request_key_refused(self):
        self.assertEqual(rw.build_create({"PK": "JOB#x", "SK": "METADATA"}, create_intent(),
                                         absent_lifetime(derived_token())).reason, "MALFORMED_KEY")

    def test_intent_key_mismatch_refused(self):
        self.assertEqual(rw.build_create(KEY, create_intent(request_id="other"),
                                         absent_lifetime(derived_token())).reason, "KEY_INTENT_MISMATCH")
        self.assertEqual(rw.build_create(KEY, create_intent(client_id="other"),
                                         absent_lifetime(derived_token())).reason, "KEY_INTENT_MISMATCH")

    def test_tenant_mismatch_refused(self):
        # item.company_id disagrees with intent.tenant
        self.assertEqual(rw.build_create(KEY, create_intent(item={"company_id": "tenant_b"}),
                                         absent_lifetime(derived_token())).reason, "TENANT_MISMATCH")

    def test_malformed_incarnation_or_created_at(self):
        self.assertEqual(rw.build_create(KEY, create_intent(incarnation=None),
                                         absent_lifetime(derived_token())).reason, "MALFORMED_INCARNATION")
        self.assertEqual(rw.build_create(KEY, create_intent(incarnation="bad id!"),
                                         absent_lifetime(derived_token())).reason, "MALFORMED_INCARNATION")
        self.assertEqual(rw.build_create(KEY, create_intent(created_at=""),
                                         absent_lifetime(derived_token())).reason, "MALFORMED_CREATED_AT")
        self.assertEqual(rw.build_create(KEY, create_intent(created_at=5),
                                         absent_lifetime(derived_token())).reason, "MALFORMED_CREATED_AT")

    def test_reserved_item_fields_refused(self):
        for fld in ("legacy_write_revision", "record_incarnation"):
            r = rw.build_create(KEY, create_intent(item={"company_id": "tenant_a", fld: "x"}),
                                absent_lifetime(derived_token()))
            self.assertEqual(r.reason, "RESERVED_FIELD_IN_ITEM", fld)

    def test_item_identifier_conflict_refused(self):
        for fld, bad in (("request_id", "other"), ("client_id", "other"),
                         ("PK", "REQ#other"), ("SK", "CLIENT#other")):
            r = rw.build_create(KEY, create_intent(item={"company_id": "tenant_a", fld: bad}),
                                absent_lifetime(derived_token()))
            self.assertEqual(r.reason, "ITEM_IDENTIFIER_CONFLICT", fld)

    def test_malformed_audit_in_item(self):
        r = rw.build_create(KEY, create_intent(item={"company_id": "tenant_a", "audit_log": "notalist"}),
                            absent_lifetime(derived_token()))
        self.assertEqual(r.reason, "MALFORMED_AUDIT")

    def test_non_dict_item(self):
        self.assertEqual(rw.build_create(KEY, create_intent(item=5),
                                         absent_lifetime(derived_token())).reason, "MALFORMED_ITEM")


class S0bLifetimeEvidenceTests(unittest.TestCase):
    def test_unknown_state_refused(self):
        r = rw.build_create(KEY, create_intent(), rw.LifetimeEvidence(state="WHATEVER", token=derived_token()))
        self.assertEqual(r.reason, "MALFORMED_LIFETIME_EVIDENCE")

    def test_not_observed_refused(self):
        r = rw.build_create(KEY, create_intent(), rw.LifetimeEvidence(state=rw.LIFETIME_NOT_OBSERVED))
        self.assertEqual(r.reason, "LIFETIME_NOT_OBSERVED")

    def test_token_mismatch_refused(self):
        r = rw.build_create(KEY, create_intent(), rw.LifetimeEvidence(state=rw.LIFETIME_ABSENT, token="wrong-token"))
        self.assertEqual(r.reason, "MALFORMED_LIFETIME_EVIDENCE")

    def test_active_lifetime_refused(self):
        tok = derived_token()
        r = rw.build_create(KEY, create_intent(),
                            rw.LifetimeEvidence(state=rw.LIFETIME_ACTIVE, token=tok, retired=False,
                                                record={"PK": "LIFETIME#" + tok, "SK": "PERMANENT", "retired": False}))
        self.assertEqual(r.reason, "LIFETIME_PRESENT")

    def test_retired_lifetime_refused(self):
        tok = derived_token()
        r = rw.build_create(KEY, create_intent(),
                            rw.LifetimeEvidence(state=rw.LIFETIME_RETIRED, token=tok, retired=True,
                                                record={"PK": "LIFETIME#" + tok, "SK": "PERMANENT", "retired": True}))
        self.assertEqual(r.reason, "KEY_RETIRED")

    def test_active_with_inconsistent_retired_refused(self):
        tok = derived_token()
        r = rw.build_create(KEY, create_intent(),
                            rw.LifetimeEvidence(state=rw.LIFETIME_ACTIVE, token=tok, retired=True))
        self.assertEqual(r.reason, "MALFORMED_LIFETIME_EVIDENCE")

    def test_retired_non_bool_refused(self):
        tok = derived_token()
        for bad in (1, "yes", [1]):
            r = rw.build_create(KEY, create_intent(),
                                rw.LifetimeEvidence(state=rw.LIFETIME_RETIRED, token=tok, retired=bad))
            self.assertEqual(r.reason, "MALFORMED_LIFETIME_EVIDENCE", bad)

    def test_absent_with_record_or_retired_refused(self):
        tok = derived_token()
        r = rw.build_create(KEY, create_intent(),
                            rw.LifetimeEvidence(state=rw.LIFETIME_ABSENT, token=tok, retired=False))
        self.assertEqual(r.reason, "MALFORMED_LIFETIME_EVIDENCE")
        r = rw.build_create(KEY, create_intent(),
                            rw.LifetimeEvidence(state=rw.LIFETIME_ABSENT, token=tok, record={"x": 1}))
        self.assertEqual(r.reason, "MALFORMED_LIFETIME_EVIDENCE")


class S0bHistoricalABATests(unittest.TestCase):
    """missing REQUEST + missing lifetime does NOT prove a never-used key."""
    def test_fresh_and_purged_states_are_observationally_identical(self):
        # Two synthetic histories produce the SAME absent/absent observable state.
        fresh_request_state = None       # never written
        purged_request_state = None      # deleted by an unfenced path
        self.assertEqual(fresh_request_state, purged_request_state)
        # And both would pass a bare create-only REQUEST condition...
        spec = rw.build_create(KEY, create_intent(), absent_lifetime(derived_token()))
        req = spec.transact_items[0]
        self.assertTrue(eval_put_condition(req, fresh_request_state))
        self.assertTrue(eval_put_condition(req, purged_request_state))
        # ...which is EXACTLY why create-only alone cannot prove 'never used'.
        # The builder still required LIFETIME_ABSENT evidence (necessary), but a
        # retired tombstone (S0c) is what would distinguish a purged key.

    def test_retired_tombstone_distinguishes_purged_key(self):
        # If the historical delete had tombstoned (S0c), evidence would be
        # RETIRED and the create is refused - the ABA-safe outcome.
        tok = derived_token()
        r = rw.build_create(KEY, create_intent(),
                            rw.LifetimeEvidence(state=rw.LIFETIME_RETIRED, token=tok, retired=True,
                                                record={"PK": "LIFETIME#" + tok, "SK": "PERMANENT", "retired": True}))
        self.assertEqual(r.reason, "KEY_RETIRED")


class S0bNoExecutionTests(unittest.TestCase):
    def test_build_create_has_no_tablename_or_client(self):
        spec = rw.build_create(KEY, create_intent(), absent_lifetime(derived_token()))
        for entry in spec.transact_items:
            self.assertNotIn("TableName", entry["Put"])
        # The spec is data only; no execution guidance / client handles.
        self.assertFalse(hasattr(rw, "transact_write_items"))


class S0bCorrectionA_CreatedAtValidationTests(unittest.TestCase):
    """Correction A: genuine ISO-8601 UTC validation for created_at."""
    def test_valid_utc_accepted(self):
        for good in ("2026-11-01T12:00:00+00:00", "2026-11-01T12:00:00Z",
                     "2026-11-01T12:00:00.123456+00:00", "2026-11-01 12:00:00+00:00"):
            self.assertTrue(rw._valid_iso_utc(good), good)
            spec = rw.build_create(KEY, create_intent(created_at=good), absent_lifetime(derived_token()))
            self.assertIsInstance(spec, rw.CreateSpec, good)

    def test_invalid_rejected(self):
        for bad in ("not-a-date", "banana", "2026-13-99", "0", "   ", "",
                    "2026-11-01",                      # date-only (incomplete)
                    "2026-11-01T12:00:00",             # naive (no offset)
                    "2026-11-01T12:00:00+02:00",       # non-UTC offset
                    " 2026-11-01T12:00:00+00:00",      # surrounding whitespace
                    "2026-11-01T12:00:00+00:00 "):
            self.assertFalse(rw._valid_iso_utc(bad), bad)
            r = rw.build_create(KEY, create_intent(created_at=bad), absent_lifetime(derived_token()))
            self.assertIsInstance(r, rw.Refusal, bad)
            self.assertEqual(r.reason, "MALFORMED_CREATED_AT", bad)

    def test_non_string_rejected(self):
        for bad in (5, None, 20261101, True, ["2026-11-01T12:00:00Z"]):
            self.assertFalse(rw._valid_iso_utc(bad), bad)

    def test_garbage_no_longer_builds(self):
        # Regression for the review finding: 'banana' used to build a CreateSpec.
        r = rw.build_create(KEY, create_intent(created_at="banana"), absent_lifetime(derived_token()))
        self.assertIsInstance(r, rw.Refusal)
        self.assertEqual(r.reason, "MALFORMED_CREATED_AT")


class S0bCorrectionB_CreatedAtOwnershipTests(unittest.TestCase):
    """Correction B: created_at is builder-owned; item may not supply it."""
    def test_item_created_at_refused_even_if_equal(self):
        same = "2026-11-01T12:00:00+00:00"
        r = rw.build_create(KEY, create_intent(created_at=same,
                                               item={"company_id": "tenant_a", "created_at": same}),
                            absent_lifetime(derived_token()))
        self.assertIsInstance(r, rw.Refusal)
        self.assertEqual(r.reason, "RESERVED_FIELD_IN_ITEM")

    def test_item_created_at_conflict_refused_not_overwritten(self):
        # Regression: a contradictory item.created_at used to be silently overwritten.
        r = rw.build_create(KEY, create_intent(item={"company_id": "tenant_a",
                                                     "created_at": "1999-01-01T00:00:00+00:00"}),
                            absent_lifetime(derived_token()))
        self.assertIsInstance(r, rw.Refusal)
        self.assertEqual(r.reason, "RESERVED_FIELD_IN_ITEM")

    def test_only_intent_created_at_populates_item(self):
        spec = rw.build_create(KEY, create_intent(), absent_lifetime(derived_token()))
        self.assertEqual(spec.transact_items[0]["Put"]["Item"]["created_at"],
                         "2026-11-01T12:00:00+00:00")


class S0bCorrectionC_LifetimeRecordValidationTests(unittest.TestCase):
    """Correction C: ACTIVE/RETIRED require a well-formed consistent record."""
    def tok(self):
        return derived_token()

    def test_active_missing_record_is_malformed(self):
        r = rw.build_create(KEY, create_intent(),
                            rw.LifetimeEvidence(state=rw.LIFETIME_ACTIVE, token=self.tok(), retired=False, record=None))
        self.assertEqual(r.reason, "MALFORMED_LIFETIME_EVIDENCE")

    def test_retired_missing_record_is_malformed(self):
        r = rw.build_create(KEY, create_intent(),
                            rw.LifetimeEvidence(state=rw.LIFETIME_RETIRED, token=self.tok(), retired=True, record=None))
        self.assertEqual(r.reason, "MALFORMED_LIFETIME_EVIDENCE")

    def test_active_wrong_record_key_is_malformed(self):
        t = self.tok()
        r = rw.build_create(KEY, create_intent(),
                            rw.LifetimeEvidence(state=rw.LIFETIME_ACTIVE, token=t, retired=False,
                                                record={"PK": "LIFETIME#WRONG", "SK": "PERMANENT", "retired": False}))
        self.assertEqual(r.reason, "MALFORMED_LIFETIME_EVIDENCE")

    def test_active_wrong_sk_is_malformed(self):
        t = self.tok()
        r = rw.build_create(KEY, create_intent(),
                            rw.LifetimeEvidence(state=rw.LIFETIME_ACTIVE, token=t, retired=False,
                                                record={"PK": "LIFETIME#" + t, "SK": "OTHER", "retired": False}))
        self.assertEqual(r.reason, "MALFORMED_LIFETIME_EVIDENCE")

    def test_record_retired_contradicts_tag_is_malformed(self):
        t = self.tok()
        # RETIRED tag + evidence.retired True, but record.retired False (contradiction).
        r = rw.build_create(KEY, create_intent(),
                            rw.LifetimeEvidence(state=rw.LIFETIME_RETIRED, token=t, retired=True,
                                                record={"PK": "LIFETIME#" + t, "SK": "PERMANENT", "retired": False}))
        self.assertEqual(r.reason, "MALFORMED_LIFETIME_EVIDENCE")

    def test_record_retired_non_bool_is_malformed(self):
        t = self.tok()
        r = rw.build_create(KEY, create_intent(),
                            rw.LifetimeEvidence(state=rw.LIFETIME_ACTIVE, token=t, retired=False,
                                                record={"PK": "LIFETIME#" + t, "SK": "PERMANENT", "retired": 0}))
        self.assertEqual(r.reason, "MALFORMED_LIFETIME_EVIDENCE")

    def test_wellformed_active_and_retired_still_refuse(self):
        t = self.tok()
        active = rw.build_create(KEY, create_intent(),
                                 rw.LifetimeEvidence(state=rw.LIFETIME_ACTIVE, token=t, retired=False,
                                                     record={"PK": "LIFETIME#" + t, "SK": "PERMANENT", "retired": False}))
        self.assertEqual(active.reason, "LIFETIME_PRESENT")
        retired = rw.build_create(KEY, create_intent(),
                                  rw.LifetimeEvidence(state=rw.LIFETIME_RETIRED, token=t, retired=True,
                                                      record={"PK": "LIFETIME#" + t, "SK": "PERMANENT", "retired": True}))
        self.assertEqual(retired.reason, "KEY_RETIRED")

    def test_active_retired_never_produce_createspec(self):
        t = self.tok()
        for st, retv in ((rw.LIFETIME_ACTIVE, False), (rw.LIFETIME_RETIRED, True)):
            for rec_snap in (None, {"PK": "X"}, {"PK": "LIFETIME#" + t, "SK": "PERMANENT", "retired": retv},
                             {"PK": "LIFETIME#" + t, "SK": "PERMANENT", "retired": not retv}):
                r = rw.build_create(KEY, create_intent(),
                                    rw.LifetimeEvidence(state=st, token=t, retired=retv, record=rec_snap))
                self.assertIsInstance(r, rw.Refusal, (st, rec_snap))


# ===========================================================================
# S0c - build_retire / classify_retire_failure tests
# ===========================================================================

def eval_update_condition(update, item):
    """Evaluate an {"Update": {...}} ConditionExpression against a synthetic item.

    Supports the closed grammar build_retire emits: attribute_exists(NAME),
    attribute_not_exists(#ref), NAME = :val, #ref = :val, and one
    (attribute_not_exists(#ref) OR #ref = :val) group, joined by " AND ".
    item is the CURRENT stored state (dict) or None.
    """
    spec = update["Update"]
    cond = spec["ConditionExpression"]
    names = spec.get("ExpressionAttributeNames", {})
    values = spec.get("ExpressionAttributeValues", {})
    cur = item or {}

    def resolve(tok):
        tok = tok.strip()
        return names.get(tok, tok)

    def clause(c):
        c = c.strip()
        m = re.fullmatch(r"attribute_exists\((.+)\)", c)
        if m:
            return resolve(m.group(1)) in cur
        m = re.fullmatch(r"attribute_not_exists\((.+)\)", c)
        if m:
            return resolve(m.group(1)) not in cur
        m = re.fullmatch(r"(\S+)\s*=\s*(:\w+)", c)
        if m:
            name = resolve(m.group(1))
            return name in cur and cur[name] == values[m.group(2)]
        raise AssertionError("unparsed S0c clause: " + repr(c))

    # Re-join a single parenthesized OR group split by " AND ".
    parts, depth, buf = [], 0, ""
    for tok in cond.split(" AND "):
        buf = tok if not buf else buf + " AND " + tok
        depth += tok.count("(") - tok.count(")")
        if depth == 0:
            parts.append(buf)
            buf = ""
    for part in parts:
        part = part.strip()
        mm = re.fullmatch(r"\((.+)\)", part)
        if mm and " OR " in mm.group(1):
            if not any(clause(c) for c in mm.group(1).split(" OR ")):
                return False
        else:
            if not clause(part):
                return False
    return True


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


def retired_request_row(**over):
    row = {"PK": "REQ#request-a", "SK": "CLIENT#client-a", "company_id": "tenant_a",
           "request_id": "request-a", "client_id": "client-a",
           "legacy_write_revision": 1, "record_incarnation": "life-a"}
    row.update(over)
    return row


class S0cJobStatusParityTests(unittest.TestCase):
    """The mirrored JobStatus value sets must match live common/status.py."""
    def test_mirrored_sets_match_live_enum_and_transitions(self):
        import importlib
        status = importlib.import_module("common.status")
        live_values = {m.value for m in status.JobStatus}
        mirrored = set(rw._KNOWN_JOB_STATES) - {"APPROVED"}  # APPROVED is a documented synonym, not an enum member
        self.assertEqual(mirrored, live_values)
        # Durable = no transition path to an executable (JOB_CREATED/ASSIGNED) state.
        trans = status.JOB_TRANSITIONS
        executable = {"JOB_CREATED", "ASSIGNED", "APPROVED"}
        for st in rw._DURABLY_INACTIVE_JOB_STATES:
            self.assertFalse(set(trans.get(st, [])) & executable, st)
        # Reopenable DOES have a path back to executable.
        for st in rw._REOPENABLE_JOB_STATES:
            self.assertTrue(set(trans.get(st, [])) & executable, st)


class S0cBuildRetirePositiveTests(unittest.TestCase):
    def test_valid_retire_builds_two_updates(self):
        tok = derived_token()
        spec = rw.build_retire(KEY, retire_expected(), active_lifetime(tok))
        self.assertIsInstance(spec, rw.RetireSpec)
        self.assertEqual(len(spec.transact_items), 2)
        life, req = spec.transact_items
        self.assertIn("Update", life)
        self.assertIn("Update", req)
        self.assertTrue(spec.retires_revision)
        self.assertEqual(spec.lifetime_token, tok)
        self.assertNotIn("TableName", life["Update"])
        self.assertNotIn("TableName", req["Update"])

    def test_lifetime_operand_retires_in_place(self):
        tok = derived_token()
        spec = rw.build_retire(KEY, retire_expected(), active_lifetime(tok))
        life = spec.transact_items[0]["Update"]
        self.assertEqual(life["Key"], {"PK": "LIFETIME#" + tok, "SK": "PERMANENT"})
        self.assertIn("#ret = :false", life["ConditionExpression"])
        self.assertIn("#inc = :inc", life["ConditionExpression"])
        self.assertEqual(life["ExpressionAttributeValues"][":true"], True)
        # Never a delete.
        self.assertNotIn("Delete", spec.transact_items[0])

    def test_request_operand_marks_and_advances(self):
        spec = rw.build_retire(KEY, retire_expected(), active_lifetime(derived_token()))
        req = spec.transact_items[1]["Update"]
        self.assertIn("#rl = :true", req["UpdateExpression"])
        self.assertIn("#rev = :next", req["UpdateExpression"])
        self.assertEqual(req["ExpressionAttributeValues"][":next"], 2)
        self.assertIn("(attribute_not_exists(#rl) OR #rl = :false)", req["ConditionExpression"])

    def test_conditions_evaluate_true_on_matching_state(self):
        tok = derived_token()
        spec = rw.build_retire(KEY, retire_expected(), active_lifetime(tok))
        life, req = spec.transact_items
        life_row = {"PK": "LIFETIME#" + tok, "SK": "PERMANENT", "retired": False, "incarnation": "life-a"}
        self.assertTrue(eval_update_condition(life, life_row))
        self.assertTrue(eval_update_condition(req, retired_request_row()))


class S0cBuildRetireFenceTests(unittest.TestCase):
    def test_tenant_identity_revision_incarnation_fences(self):
        spec = rw.build_retire(KEY, retire_expected(), active_lifetime(derived_token()))
        req = spec.transact_items[1]
        self.assertFalse(eval_update_condition(req, retired_request_row(company_id="tenant_b")))
        self.assertFalse(eval_update_condition(req, retired_request_row(request_id="other")))
        self.assertFalse(eval_update_condition(req, retired_request_row(client_id="other")))
        self.assertFalse(eval_update_condition(req, retired_request_row(legacy_write_revision=2)))
        self.assertFalse(eval_update_condition(req, retired_request_row(record_incarnation="life-b")))

    def test_already_retired_marker_blocks(self):
        spec = rw.build_retire(KEY, retire_expected(), active_lifetime(derived_token()))
        req = spec.transact_items[1]
        self.assertFalse(eval_update_condition(req, retired_request_row(retired_lifetime=True)))
        self.assertTrue(eval_update_condition(req, retired_request_row(retired_lifetime=False)))

    def test_lifetime_already_retired_condition_false(self):
        tok = derived_token()
        spec = rw.build_retire(KEY, retire_expected(), active_lifetime(tok))
        life = spec.transact_items[0]
        now_retired = {"PK": "LIFETIME#" + tok, "SK": "PERMANENT", "retired": True, "incarnation": "life-a"}
        self.assertFalse(eval_update_condition(life, now_retired))


class S0cBuildRetireRefusalTests(unittest.TestCase):
    def test_malformed_inputs(self):
        self.assertEqual(rw.build_retire(KEY, object(), active_lifetime(derived_token())).reason, "MALFORMED_EXPECTED")
        self.assertEqual(rw.build_retire(KEY, retire_expected(), object()).reason, "MALFORMED_LIFETIME_EVIDENCE")
        self.assertEqual(rw.build_retire({"PK": "JOB#x", "SK": "Y"}, retire_expected(), active_lifetime(derived_token())).reason, "MALFORMED_KEY")

    def test_key_expected_mismatch(self):
        self.assertEqual(rw.build_retire(KEY, retire_expected(request_id="other"), active_lifetime(derived_token())).reason, "KEY_EXPECTED_MISMATCH")
        self.assertEqual(rw.build_retire(KEY, retire_expected(client_id="other"), active_lifetime(derived_token())).reason, "KEY_EXPECTED_MISMATCH")

    def test_bad_revision_incarnation_retired_at(self):
        self.assertEqual(rw.build_retire(KEY, retire_expected(revision=0), active_lifetime(derived_token())).reason, "MALFORMED_REVISION")
        self.assertEqual(rw.build_retire(KEY, retire_expected(incarnation="bad id!"), active_lifetime(derived_token())).reason, "MALFORMED_INCARNATION")
        for bad in ("", "banana", "2026-11-01", "2026-11-01T12:00:00", "2026-11-01T12:00:00+02:00", 5):
            self.assertEqual(rw.build_retire(KEY, retire_expected(retired_at=bad), active_lifetime(derived_token())).reason, "MALFORMED_RETIRED_AT", bad)

    def test_lifetime_evidence_refusals(self):
        t = derived_token()
        self.assertEqual(rw.build_retire(KEY, retire_expected(), rw.LifetimeEvidence(state=rw.LIFETIME_NOT_OBSERVED)).reason, "LIFETIME_NOT_OBSERVED")
        self.assertEqual(rw.build_retire(KEY, retire_expected(), rw.LifetimeEvidence(state=rw.LIFETIME_ABSENT, token=t)).reason, "LIFETIME_NOT_OBSERVED")
        self.assertEqual(rw.build_retire(KEY, retire_expected(), rw.LifetimeEvidence(state="WHAT", token=t)).reason, "MALFORMED_LIFETIME_EVIDENCE")
        self.assertEqual(rw.build_retire(KEY, retire_expected(), rw.LifetimeEvidence(state=rw.LIFETIME_ACTIVE, token="wrong", retired=False)).reason, "MALFORMED_LIFETIME_EVIDENCE")

    def test_already_retired_evidence(self):
        t = derived_token()
        ev = rw.LifetimeEvidence(state=rw.LIFETIME_RETIRED, token=t, retired=True,
                                 record={"PK": "LIFETIME#" + t, "SK": "PERMANENT", "retired": True, "incarnation": "life-a"})
        self.assertEqual(rw.build_retire(KEY, retire_expected(), ev).reason, "ALREADY_RETIRED")

    def test_lifetime_record_inconsistent(self):
        t = derived_token()
        # wrong key
        ev = rw.LifetimeEvidence(state=rw.LIFETIME_ACTIVE, token=t, retired=False,
                                 record={"PK": "LIFETIME#WRONG", "SK": "PERMANENT", "retired": False, "incarnation": "life-a"})
        self.assertEqual(rw.build_retire(KEY, retire_expected(), ev).reason, "MALFORMED_LIFETIME_EVIDENCE")
        # incarnation mismatch
        ev2 = rw.LifetimeEvidence(state=rw.LIFETIME_ACTIVE, token=t, retired=False,
                                  record={"PK": "LIFETIME#" + t, "SK": "PERMANENT", "retired": False, "incarnation": "other"})
        self.assertEqual(rw.build_retire(KEY, retire_expected(), ev2).reason, "MALFORMED_LIFETIME_EVIDENCE")


class S0cChildEvidenceTests(unittest.TestCase):
    def C(self, job_id, status):
        return rw.ChildJobEvidence(job_id=job_id, status=status)

    def test_active_children_refused(self):
        for st in ("JOB_CREATED", "ASSIGNED", "APPROVED"):
            r = rw.build_retire(KEY, retire_expected(children=(self.C("j1", st),)), active_lifetime(derived_token()))
            self.assertEqual(r.reason, "ACTIVE_CHILDREN_PRESENT", st)

    def test_reopenable_children_refused(self):
        for st in ("CANCELLED", "COMPLETED"):
            r = rw.build_retire(KEY, retire_expected(children=(self.C("j1", st),)), active_lifetime(derived_token()))
            self.assertEqual(r.reason, "REOPENABLE_CHILDREN_PRESENT", st)

    def test_durable_children_pass_gate(self):
        for st in ("ARCHIVED", "DELETED"):
            spec = rw.build_retire(KEY, retire_expected(children=(self.C("j1", st),)), active_lifetime(derived_token()))
            self.assertIsInstance(spec, rw.RetireSpec, st)

    def test_mixed_children_refuse_on_strongest(self):
        r = rw.build_retire(KEY, retire_expected(children=(self.C("j1", "ARCHIVED"), self.C("j2", "ASSIGNED"))),
                            active_lifetime(derived_token()))
        self.assertEqual(r.reason, "ACTIVE_CHILDREN_PRESENT")
        r2 = rw.build_retire(KEY, retire_expected(children=(self.C("j1", "ARCHIVED"), self.C("j2", "CANCELLED"))),
                             active_lifetime(derived_token()))
        self.assertEqual(r2.reason, "REOPENABLE_CHILDREN_PRESENT")

    def test_incomplete_or_malformed_children(self):
        self.assertEqual(rw.build_retire(KEY, retire_expected(child_set_complete=False), active_lifetime(derived_token())).reason, "CHILD_SET_INCOMPLETE")
        self.assertEqual(rw.build_retire(KEY, retire_expected(children=5), active_lifetime(derived_token())).reason, "MALFORMED_CHILD_EVIDENCE")
        self.assertEqual(rw.build_retire(KEY, retire_expected(children=(self.C("j1", "NOPE"),)), active_lifetime(derived_token())).reason, "MALFORMED_CHILD_EVIDENCE")
        self.assertEqual(rw.build_retire(KEY, retire_expected(children=(self.C("bad id!", "ARCHIVED"),)), active_lifetime(derived_token())).reason, "MALFORMED_CHILD_EVIDENCE")

    def test_duplicate_child_ids(self):
        r = rw.build_retire(KEY, retire_expected(children=(self.C("j1", "ARCHIVED"), self.C("j1", "DELETED"))),
                            active_lifetime(derived_token()))
        self.assertEqual(r.reason, "DUPLICATE_CHILD_EVIDENCE")

    def test_stale_child_characterization(self):
        # A DURABLE child passes the gate, but the design does NOT claim this
        # prevents a concurrent reopen/execution - only the future barrier does.
        spec = rw.build_retire(KEY, retire_expected(children=(self.C("j1", "ARCHIVED"),)), active_lifetime(derived_token()))
        self.assertIsInstance(spec, rw.RetireSpec)
        # ARCHIVED has no transition to executable in the live machine, but an
        # unfenced writer could still overwrite it - asserted by parity test only.


class S0cClassifyRetireFailureTests(unittest.TestCase):
    """Corrections A + B: classification binds to the AUTHORITATIVE target key
    (evidence.target_request_key + derived lifetime token), strictly validates
    observations, and defaults to INDETERMINATE on any wrong-target/malformed/
    contradictory evidence."""
    def obs(self, state, pk=None, sk=None, snapshot=None):
        key = {"PK": pk, "SK": sk} if pk is not None else None
        return rw.RecordObservation(state=state, key=key, snapshot=snapshot)

    def life_key(self):
        return {"PK": "LIFETIME#" + derived_token(), "SK": "PERMANENT"}

    def ev(self, **over):
        base = dict(kind="reread", target_request_key={"PK": "REQ#request-a", "SK": "CLIENT#client-a"},
                    expected=retire_expected())
        base.update(over)
        return rw.RetireFailureEvidence(**base)

    # --- basic guards -------------------------------------------------------
    def test_non_evidence_or_expected_indeterminate(self):
        self.assertEqual(rw.classify_retire_failure(object()).classification, rw.INDETERMINATE)
        self.assertEqual(rw.classify_retire_failure(self.ev(expected=None)).classification, rw.INDETERMINATE)

    def test_missing_or_malformed_target_key_indeterminate(self):
        self.assertEqual(rw.classify_retire_failure(self.ev(target_request_key=None)).classification, rw.INDETERMINATE)
        self.assertEqual(rw.classify_retire_failure(self.ev(target_request_key={"PK": "JOB#x", "SK": "Y"})).classification, rw.INDETERMINATE)
        self.assertEqual(rw.classify_retire_failure(self.ev(target_request_key={"PK": "REQ#bad id!", "SK": "CLIENT#c"})).classification, rw.INDETERMINATE)

    def test_not_observed_is_indeterminate(self):
        self.assertEqual(rw.classify_retire_failure(self.ev(kind="transaction_cancellation")).classification, rw.INDETERMINATE)

    def test_bare_cancellation_indeterminate(self):
        self.assertEqual(rw.classify_retire_failure(
            self.ev(kind="transaction_cancellation", cancellation_reasons=("ConditionalCheckFailed", "ConditionalCheckFailed"))
        ).classification, rw.INDETERMINATE)

    # --- Correction A: evidence.kind validation -----------------------------
    def test_unknown_or_bad_kind_never_classifies(self):
        # Even with a fully valid, key-bound retired-lifetime observation that
        # WOULD otherwise be ALREADY_RETIRED, an invalid kind -> INDETERMINATE.
        life = self.obs(rw.OBSERVED_PRESENT, "LIFETIME#" + derived_token(), "PERMANENT",
                        {"PK": "LIFETIME#" + derived_token(), "SK": "PERMANENT", "retired": True, "incarnation": "life-a"})
        for bad_kind in ("garbage", "", "REREAD", "Reread", None, 123, ("reread",)):
            c = rw.classify_retire_failure(self.ev(kind=bad_kind, lifetime_obs=life))
            self.assertEqual(c.classification, rw.INDETERMINATE, bad_kind)
            self.assertFalse(c.evidence_backed, bad_kind)

    def test_valid_kinds_still_classify(self):
        life = self.obs(rw.OBSERVED_PRESENT, "LIFETIME#" + derived_token(), "PERMANENT",
                        {"PK": "LIFETIME#" + derived_token(), "SK": "PERMANENT", "retired": True, "incarnation": "life-a"})
        # reread (no reasons) -> classifies
        self.assertEqual(rw.classify_retire_failure(self.ev(kind="reread", lifetime_obs=life)).classification, rw.ALREADY_RETIRED)
        # transaction_cancellation with a well-formed 2-entry envelope -> classifies
        self.assertEqual(rw.classify_retire_failure(
            self.ev(kind="transaction_cancellation", cancellation_reasons=("None", "ConditionalCheckFailed"), lifetime_obs=life)
        ).classification, rw.ALREADY_RETIRED)

    # --- Correction B: cancellation metadata validation ---------------------
    def test_malformed_cancellation_container_never_classifies(self):
        life = self.obs(rw.OBSERVED_PRESENT, "LIFETIME#" + derived_token(), "PERMANENT",
                        {"PK": "LIFETIME#" + derived_token(), "SK": "PERMANENT", "retired": True, "incarnation": "life-a"})
        for bad in ("string", 5, None, {"a": 1}):
            c = rw.classify_retire_failure(
                self.ev(kind="transaction_cancellation", cancellation_reasons=bad, lifetime_obs=life))
            self.assertEqual(c.classification, rw.INDETERMINATE, bad)

    def test_malformed_cancellation_entry_never_classifies(self):
        life = self.obs(rw.OBSERVED_PRESENT, "LIFETIME#" + derived_token(), "PERMANENT",
                        {"PK": "LIFETIME#" + derived_token(), "SK": "PERMANENT", "retired": True, "incarnation": "life-a"})
        for bad_entry in ((None,), (5,), ({},), ("ok", 7)):
            c = rw.classify_retire_failure(
                self.ev(kind="transaction_cancellation", cancellation_reasons=bad_entry, lifetime_obs=life))
            self.assertEqual(c.classification, rw.INDETERMINATE, bad_entry)

    def test_unsupported_cancellation_count(self):
        life = self.obs(rw.OBSERVED_PRESENT, "LIFETIME#" + derived_token(), "PERMANENT",
                        {"PK": "LIFETIME#" + derived_token(), "SK": "PERMANENT", "retired": True, "incarnation": "life-a"})
        # More than two positional operands is unsupported.
        c = rw.classify_retire_failure(
            self.ev(kind="transaction_cancellation", cancellation_reasons=("a", "b", "c"), lifetime_obs=life))
        self.assertEqual(c.classification, rw.INDETERMINATE)

    def test_reread_with_cancellation_reasons_is_contradictory(self):
        life = self.obs(rw.OBSERVED_PRESENT, "LIFETIME#" + derived_token(), "PERMANENT",
                        {"PK": "LIFETIME#" + derived_token(), "SK": "PERMANENT", "retired": True, "incarnation": "life-a"})
        c = rw.classify_retire_failure(
            self.ev(kind="reread", cancellation_reasons=("ConditionalCheckFailed",), lifetime_obs=life))
        self.assertEqual(c.classification, rw.INDETERMINATE)

    def test_valid_transaction_envelope_zero_reasons_insufficient_without_obs(self):
        # A valid transaction_cancellation envelope with no reasons and no useful
        # observation is INSUFFICIENT, not a specific failure.
        c = rw.classify_retire_failure(self.ev(kind="transaction_cancellation", cancellation_reasons=()))
        self.assertEqual(c.classification, rw.INDETERMINATE)

    # --- correct, key-bound positive classifications ------------------------
    def test_already_retired_evidence_backed(self):
        t = derived_token()
        life = self.obs(rw.OBSERVED_PRESENT, "LIFETIME#" + t, "PERMANENT",
                        {"PK": "LIFETIME#" + t, "SK": "PERMANENT", "retired": True, "incarnation": "life-a"})
        c = rw.classify_retire_failure(self.ev(lifetime_obs=life))
        self.assertEqual(c.classification, rw.ALREADY_RETIRED)
        self.assertTrue(c.evidence_backed)

    def test_lifetime_missing_evidence_backed(self):
        t = derived_token()
        life = self.obs(rw.OBSERVED_ABSENT, "LIFETIME#" + t, "PERMANENT")
        self.assertEqual(rw.classify_retire_failure(self.ev(lifetime_obs=life)).classification, rw.LIFETIME_MISSING)

    def test_request_absent_evidence_backed(self):
        req = self.obs(rw.OBSERVED_ABSENT, "REQ#request-a", "CLIENT#client-a")
        self.assertEqual(rw.classify_retire_failure(self.ev(request_obs=req)).classification, rw.REQUEST_ABSENT)

    def test_tenant_stale_incarnation(self):
        def rq(**o):
            return self.obs(rw.OBSERVED_PRESENT, "REQ#request-a", "CLIENT#client-a", retired_request_row(**o))
        self.assertEqual(rw.classify_retire_failure(self.ev(request_obs=rq(company_id="tenant_b"))).classification, rw.TENANT_MISMATCH)
        self.assertEqual(rw.classify_retire_failure(self.ev(request_obs=rq(legacy_write_revision=5))).classification, rw.STALE)
        self.assertEqual(rw.classify_retire_failure(self.ev(request_obs=rq(record_incarnation="life-b"))).classification, rw.INCARNATION_DIVERGED)

    # --- Correction A: wrong-target rejection -------------------------------
    def test_wrong_target_request_key_self_consistent_indeterminate(self):
        # A perfectly self-consistent REQUEST row for a DIFFERENT key must NOT
        # classify against our target.
        other = self.obs(rw.OBSERVED_PRESENT, "REQ#other", "CLIENT#other",
                         {"PK": "REQ#other", "SK": "CLIENT#other", "company_id": "tenant_a",
                          "legacy_write_revision": 1, "record_incarnation": "life-a"})
        self.assertEqual(rw.classify_retire_failure(self.ev(request_obs=other)).classification, rw.INDETERMINATE)

    def test_wrong_lifetime_token_self_consistent_indeterminate(self):
        # A self-consistent lifetime record under a DIFFERENT token must not bind.
        life = self.obs(rw.OBSERVED_PRESENT, "LIFETIME#deadbeef", "PERMANENT",
                        {"PK": "LIFETIME#deadbeef", "SK": "PERMANENT", "retired": True, "incarnation": "life-a"})
        self.assertEqual(rw.classify_retire_failure(self.ev(lifetime_obs=life)).classification, rw.INDETERMINATE)

    def test_unrelated_retired_lifetime_same_incarnation_never_already_retired(self):
        # The exact attack Correction A closes: an unrelated retired lifetime
        # with the same incarnation must NOT produce ALREADY_RETIRED.
        life = self.obs(rw.OBSERVED_PRESENT, "LIFETIME#deadbeef", "PERMANENT",
                        {"PK": "LIFETIME#deadbeef", "SK": "PERMANENT", "retired": True, "incarnation": "life-a"})
        c = rw.classify_retire_failure(self.ev(lifetime_obs=life))
        self.assertNotEqual(c.classification, rw.ALREADY_RETIRED)
        self.assertEqual(c.classification, rw.INDETERMINATE)

    # --- Correction B: observation shape / consistency ----------------------
    def test_observed_absent_carrying_snapshot_indeterminate(self):
        bad = rw.RecordObservation(state=rw.OBSERVED_ABSENT, key=self.life_key(),
                                   snapshot={"PK": self.life_key()["PK"], "SK": "PERMANENT"})
        self.assertEqual(rw.classify_retire_failure(self.ev(lifetime_obs=bad)).classification, rw.INDETERMINATE)

    def test_not_observed_with_snapshot_indeterminate(self):
        bad = rw.RecordObservation(state=rw.NOT_OBSERVED, snapshot={"x": 1})
        self.assertEqual(rw.classify_retire_failure(self.ev(request_obs=bad)).classification, rw.INDETERMINATE)

    def test_present_snapshot_pk_sk_mismatch_indeterminate(self):
        t = derived_token()
        bad = self.obs(rw.OBSERVED_PRESENT, "LIFETIME#" + t, "PERMANENT",
                       {"PK": "LIFETIME#OTHER", "SK": "PERMANENT", "retired": True, "incarnation": "life-a"})
        self.assertEqual(rw.classify_retire_failure(self.ev(lifetime_obs=bad)).classification, rw.INDETERMINATE)

    def test_missing_or_wrong_type_required_fields_indeterminate(self):
        t = derived_token()
        # retired non-bool
        life1 = self.obs(rw.OBSERVED_PRESENT, "LIFETIME#" + t, "PERMANENT",
                         {"PK": "LIFETIME#" + t, "SK": "PERMANENT", "retired": 1, "incarnation": "life-a"})
        self.assertEqual(rw.classify_retire_failure(self.ev(lifetime_obs=life1)).classification, rw.INDETERMINATE)
        # incarnation missing
        life2 = self.obs(rw.OBSERVED_PRESENT, "LIFETIME#" + t, "PERMANENT",
                         {"PK": "LIFETIME#" + t, "SK": "PERMANENT", "retired": True})
        self.assertEqual(rw.classify_retire_failure(self.ev(lifetime_obs=life2)).classification, rw.INDETERMINATE)
        # request revision wrong type
        req = self.obs(rw.OBSERVED_PRESENT, "REQ#request-a", "CLIENT#client-a",
                       {"PK": "REQ#request-a", "SK": "CLIENT#client-a", "company_id": "tenant_a",
                        "legacy_write_revision": "1", "record_incarnation": "life-a"})
        self.assertEqual(rw.classify_retire_failure(self.ev(request_obs=req)).classification, rw.INDETERMINATE)

    def test_malformed_with_valid_looking_fields_indeterminate(self):
        # Right shape/fields but WRONG target key -> MALFORMED -> INDETERMINATE.
        req = self.obs(rw.OBSERVED_PRESENT, "REQ#wrong", "CLIENT#wrong",
                       {"PK": "REQ#wrong", "SK": "CLIENT#wrong", "company_id": "tenant_a",
                        "legacy_write_revision": 1, "record_incarnation": "life-a"})
        self.assertEqual(rw.classify_retire_failure(self.ev(request_obs=req)).classification, rw.INDETERMINATE)

    def test_contradictory_observations_indeterminate(self):
        # REQUEST present and UNCHANGED (matches expected) while lifetime claims
        # retired -> contradiction -> INDETERMINATE (neither ALREADY_RETIRED nor
        # a clean request classification).
        t = derived_token()
        life = self.obs(rw.OBSERVED_PRESENT, "LIFETIME#" + t, "PERMANENT",
                        {"PK": "LIFETIME#" + t, "SK": "PERMANENT", "retired": True, "incarnation": "life-a"})
        req = self.obs(rw.OBSERVED_PRESENT, "REQ#request-a", "CLIENT#client-a", retired_request_row())
        c = rw.classify_retire_failure(self.ev(lifetime_obs=life, request_obs=req))
        self.assertEqual(c.classification, rw.INDETERMINATE)


class S0cNoExecutionTests(unittest.TestCase):
    def test_retire_spec_is_data_only(self):
        spec = rw.build_retire(KEY, retire_expected(), active_lifetime(derived_token()))
        self.assertEqual(len(spec.transact_items), 2)
        for entry in spec.transact_items:
            self.assertIn("Update", entry)
            self.assertNotIn("TableName", entry["Update"])
            self.assertNotIn("Delete", entry)
        self.assertFalse(hasattr(rw, "transact_write_items"))


# ===========================================================================
# S0a retirement write-fence (A / B / C) tests
# ===========================================================================

def retire_fence_expected(**over):
    # A complete-coverage protected-client ExpectedState (so build_update reaches
    # condition construction) with an explicit OBSERVED retirement tag by default
    # (FALSE); evidence-gate tests override retirement_marker explicitly.
    base = dict(tenant="tenant_a", revision=1, incarnation="life-a", source_status=None,
                present_identity=(("cognito_sub", "subject-a"),),
                absent_identity=("client_email", "linked_client_profile_id"),
                protected_client=True,
                retirement_marker=rw.RETIREMENT_FALSE)
    base.update(over)
    return rw.ExpectedState(**base)


def rf_plan():
    return rw.WritePlan(set_fields=(("cancellation_reason", "r"),), append_audit={"status": "X"})


ELIG = rw.AdoptionDisposition(rw.ADOPT_ELIGIBLE, ())
RF_KEY = {"PK": "REQ#request-a", "SK": "CLIENT#client-a"}


class S0aRetirementEvidenceTests(unittest.TestCase):
    """Part A: tagged retirement-marker evidence handling."""
    def test_true_marker_refused(self):
        r = rw.build_update(RF_KEY, retire_fence_expected(retirement_marker=rw.RETIREMENT_TRUE), rf_plan(), ELIG)
        self.assertIsInstance(r, rw.Refusal)
        self.assertEqual(r.reason, "RETIRED_REQUEST")

    def test_malformed_or_unknown_marker_fail_closed(self):
        for bad in ("garbage", "", None, True, 1, ("x",)):
            r = rw.build_update(RF_KEY, retire_fence_expected(retirement_marker=bad), rf_plan(), ELIG)
            self.assertIsInstance(r, rw.Refusal, bad)
            self.assertEqual(r.reason, "MALFORMED_RETIREMENT_EVIDENCE", bad)

    def test_false_marker_eligible(self):
        spec = rw.build_update(RF_KEY, retire_fence_expected(retirement_marker=rw.RETIREMENT_FALSE), rf_plan(), ELIG)
        self.assertIsInstance(spec, rw.UpdateSpec)

    def test_observed_absent_marker_eligible(self):
        spec = rw.build_update(RF_KEY, retire_fence_expected(retirement_marker=rw.RETIREMENT_ABSENT), rf_plan(), ELIG)
        self.assertIsInstance(spec, rw.UpdateSpec)

    def test_explicit_not_observed_refused(self):
        # PR58 correction: an unperformed lookup (NOT_OBSERVED) fails closed,
        # even with otherwise-valid complete coverage.
        r = rw.build_update(RF_KEY, retire_fence_expected(retirement_marker=rw.RETIREMENT_NOT_OBSERVED),
                            rf_plan(), ELIG)
        self.assertIsInstance(r, rw.Refusal)
        self.assertEqual(r.reason, "RETIREMENT_EVIDENCE_NOT_OBSERVED")

    def test_omitted_evidence_defaults_to_not_observed_and_refuses(self):
        # The ExpectedState default is NOT_OBSERVED; a caller that omits the tag
        # entirely is refused - omitted evidence never authorizes an update.
        omitted = rw.ExpectedState(tenant="tenant_a", revision=1, incarnation="life-a",
                                   present_identity=(("cognito_sub", "subject-a"),),
                                   absent_identity=("client_email", "linked_client_profile_id"),
                                   protected_client=True)
        self.assertEqual(omitted.retirement_marker, rw.RETIREMENT_NOT_OBSERVED)
        r = rw.build_update(RF_KEY, omitted, rf_plan(), ELIG)
        self.assertIsInstance(r, rw.Refusal)
        self.assertEqual(r.reason, "RETIREMENT_EVIDENCE_NOT_OBSERVED")

    def test_missing_vs_observed_absence_distinct(self):
        # NOT_OBSERVED (unperformed lookup -> refuse) and OBSERVED_ABSENT
        # (actually-observed missing attribute -> eligible) are distinct tags with
        # distinct outcomes; observed absence is never inferred from a missing lookup.
        self.assertNotEqual(rw.RETIREMENT_NOT_OBSERVED, rw.RETIREMENT_ABSENT)
        self.assertEqual(rw.build_update(RF_KEY, retire_fence_expected(retirement_marker=rw.RETIREMENT_NOT_OBSERVED),
                                         rf_plan(), ELIG).reason, "RETIREMENT_EVIDENCE_NOT_OBSERVED")
        self.assertIsInstance(rw.build_update(RF_KEY, retire_fence_expected(retirement_marker=rw.RETIREMENT_ABSENT),
                                              rf_plan(), ELIG), rw.UpdateSpec)


class S0aRetirementFenceConditionTests(unittest.TestCase):
    """Part B: mandatory (attribute_not_exists(#rl) OR #rl = :false) on EVERY update."""
    def spec(self, **over):
        s = rw.build_update(RF_KEY, retire_fence_expected(**over), rf_plan(), ELIG)
        assert isinstance(s, rw.UpdateSpec), s
        return s

    def test_condition_present_on_every_update(self):
        # With and without a declared status transition, the fence is present.
        for over in ({}, {"source_status": "ASSIGNED"}):
            spec = self.spec(**over)
            self.assertIn("(attribute_not_exists(#rl) OR #rl = :false)", spec.condition_expression)
            self.assertEqual(spec.names["#rl"], "retired_lifetime")
            self.assertEqual(spec.values[":false"], False)

    def test_absent_marker_passes(self):
        spec = self.spec()
        item = versioned_snapshot(cognito_sub="subject-a")  # no retired_lifetime attribute
        self.assertTrue(evaluate(spec, item))

    def test_exact_false_passes(self):
        spec = self.spec()
        item = versioned_snapshot(cognito_sub="subject-a", retired_lifetime=False)
        self.assertTrue(evaluate(spec, item))

    def test_exact_true_fails(self):
        spec = self.spec()
        item = versioned_snapshot(cognito_sub="subject-a", retired_lifetime=True)
        self.assertFalse(evaluate(spec, item))

    def test_non_bool_marker_fails(self):
        # A non-bool value is neither absent nor == False -> condition false.
        for bad in (1, "true", "True"):
            spec = self.spec()
            item = versioned_snapshot(cognito_sub="subject-a", retired_lifetime=bad)
            self.assertFalse(evaluate(spec, item), bad)

    def test_concurrent_retirement_after_read_fails(self):
        # Caller read FALSE/absent; a concurrent S0c retire set it True before
        # this update commits -> the fence makes the update fail closed.
        spec = self.spec(retirement_marker=rw.RETIREMENT_FALSE)
        now_retired = versioned_snapshot(cognito_sub="subject-a", retired_lifetime=True)
        self.assertFalse(evaluate(spec, now_retired))


class S0aReservedRetirementMetadataTests(unittest.TestCase):
    """Part C: retired_lifetime / retired_at are reserved from plans."""
    def test_set_retirement_fields_refused(self):
        for fld in ("retired_lifetime", "retired_at"):
            r = rw.build_update(RF_KEY, retire_fence_expected(),
                                rw.WritePlan(set_fields=((fld, "x"),)), ELIG)
            self.assertIsInstance(r, rw.Refusal, fld)
            self.assertEqual(r.reason, "RESERVED_FIELD", fld)

    def test_remove_retirement_fields_refused(self):
        # In particular, a plan may not CLEAR the permanent marker via REMOVE.
        for fld in ("retired_lifetime", "retired_at"):
            r = rw.build_update(RF_KEY, retire_fence_expected(),
                                rw.WritePlan(remove_fields=(fld,)), ELIG)
            self.assertIsInstance(r, rw.Refusal, fld)
            self.assertEqual(r.reason, "RESERVED_FIELD", fld)

    def test_fields_present_in_reserved_set(self):
        self.assertIn("retired_lifetime", rw.RESERVED_FIELDS)
        self.assertIn("retired_at", rw.RESERVED_FIELDS)
        # Existing reserved protections preserved.
        for prior in ("legacy_write_revision", "record_incarnation", "PK", "SK", "company_id"):
            self.assertIn(prior, rw.RESERVED_FIELDS)


class S0aRetirementCompatibilityTests(unittest.TestCase):
    """Part D: S0b/S0c and existing S0a protections unchanged alongside the fence."""
    def test_protected_client_identity_still_enforced(self):
        # Incomplete ownership coverage still refused even with a FALSE marker.
        r = rw.build_update(RF_KEY, retire_fence_expected(retirement_marker=rw.RETIREMENT_FALSE,
                                                          absent_identity=("client_email",)),
                            rf_plan(), ELIG)
        self.assertEqual(r.reason, "OWNERSHIP_INCOMPLETE")

    def test_revision_and_audit_behavior_preserved(self):
        spec = rw.build_update(RF_KEY, retire_fence_expected(retirement_marker=rw.RETIREMENT_FALSE), rf_plan(), ELIG)
        self.assertIn("#rev = :next", spec.update_expression)
        self.assertTrue(spec.advances_revision)
        self.assertIn("list_append(if_not_exists(#audit, :emptylist), :auditentry)", spec.update_expression)

    def test_s0b_build_create_still_works(self):
        spec = rw.build_create(KEY, create_intent(), absent_lifetime(derived_token()))
        self.assertIsInstance(spec, rw.CreateSpec)

    def test_s0c_build_retire_still_works(self):
        spec = rw.build_retire(KEY, retire_expected(), active_lifetime(derived_token()))
        self.assertIsInstance(spec, rw.RetireSpec)


if __name__ == "__main__":
    unittest.main()
