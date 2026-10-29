"""Synthetic, stdlib-only tests. Runnable by unittest and existing backend pytest CI."""
import ast
from decimal import Decimal
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import unittest

from worker_identity_contract import (
    Caller, Worker, Link, Visit, Snapshot, Operation, Outcome, ParentModel,
    assess_owner, capture_fence, assess_atomic_fence,
    legacy_assignment_invalidation, completion_rollup_cas, parse_dynamo_revision, MAX_REVISION,
)


def fixture():
    return Snapshot(
        Caller("https://issuer.example.invalid/pool-a", "subject-a", "tenant-a", "owner", trusted_authorizer=True, token_current=True),
        Worker("wrk_11111111111111111111111111111111", "tenant-a", "staff-a", active=True, assignable=True, version=1),
        Link("https://issuer.example.invalid/pool-a", "subject-a", "tenant-a",
             "wrk_11111111111111111111111111111111", "staff-a", active=True, version=1),
        Visit("job-a", "request-a", "tenant-a", "wrk_11111111111111111111111111111111", assignment_revision=1, canonical=True, assignment_contract_version=1, hydrated=True),
    )


def operation(action="START", revision=1):
    return Operation(action, "request-a", "job-a", revision, "op_" + "1" * 32, "a" * 64, 1)


class OwnerIdentityContractTests(unittest.TestCase):
    def assert_denial(self, snapshot, reason, op=None):
        decision = assess_owner(snapshot, op or operation())
        self.assertEqual((decision.outcome, decision.reason), (Outcome.DENIED, reason))

    def test_linked_assigned_owner_is_snapshot_eligible(self):
        self.assertEqual(assess_owner(fixture(), operation()).outcome, Outcome.ELIGIBLE)

    def test_started_assigned_owner_complete_is_snapshot_eligible(self):
        s = fixture()
        s = replace(s, visit=replace(s.visit, started=True, started_assignment_revision=1))
        self.assertEqual(assess_owner(s, operation("COMPLETE")).outcome, Outcome.ELIGIBLE)

    def test_email_disguised_as_canonical_id_is_rejected(self):
        s = fixture()
        email = "synthetic-owner@example.invalid"
        current = replace(s, worker=replace(s.worker, worker_id=email),
                          link=replace(s.link, worker_id=email),
                          visit=replace(s.visit, assigned_worker_id=email))
        self.assert_denial(current, "INVALID_CANONICAL_WORKER_ID")

    def test_missing_trust_and_canonical_flags_fail_closed(self):
        s = fixture()
        self.assert_denial(replace(s, caller=Caller("issuer", "subject", "tenant-a", "owner")), "UNTRUSTED_OR_EXPIRED_CALLER")
        visit = Visit("job-a", "request-a", "tenant-a", s.worker.worker_id)
        self.assert_denial(replace(s, visit=visit), "UNHYDRATED_VISIT")

    def test_truthy_strings_do_not_establish_verification(self):
        s = fixture()
        self.assert_denial(replace(s, caller=replace(s.caller, trusted_authorizer="true")), "UNTRUSTED_OR_EXPIRED_CALLER")
        self.assert_denial(replace(s, worker=replace(s.worker, active="true")), "INACTIVE_OR_UNASSIGNABLE_WORKER")
        self.assert_denial(replace(s, active_link_count=True), "AMBIGUOUS_LINKAGE")

    def test_missing_or_future_assignment_contract_does_not_qualify(self):
        s = fixture()
        for version in (0, 2, True, None):
            with self.subTest(version=version):
                self.assert_denial(replace(s, visit=replace(s.visit, assignment_contract_version=version)), "UNSUPPORTED_ASSIGNMENT_CONTRACT")

    def test_invalid_started_marker_is_not_execution_proof(self):
        s = fixture()
        self.assert_denial(replace(s, visit=replace(s.visit, started="false", started_assignment_revision=1)), "INVALID_EXECUTION_PROVENANCE", operation("COMPLETE"))

    def test_unlinked_owner(self):
        self.assert_denial(replace(fixture(), link=None), "UNLINKED_OWNER")

    def test_missing_worker(self):
        self.assert_denial(replace(fixture(), worker=None), "UNLINKED_OWNER")

    def test_inactive_worker(self):
        s = fixture()
        self.assert_denial(replace(s, worker=replace(s.worker, active=False)), "INACTIVE_OR_UNASSIGNABLE_WORKER")

    def test_unassignable_worker(self):
        s = fixture()
        self.assert_denial(replace(s, worker=replace(s.worker, assignable=False)), "INACTIVE_OR_UNASSIGNABLE_WORKER")

    def test_revoked_link(self):
        s = fixture()
        self.assert_denial(replace(s, link=replace(s.link, active=False)), "REVOKED_LINK")

    def test_wrong_tenant_on_every_trusted_record(self):
        s = fixture()
        for field in ("visit", "link", "worker"):
            with self.subTest(field=field):
                changed = replace(getattr(s, field), tenant="tenant-b")
                self.assert_denial(replace(s, **{field: changed}), "WRONG_TENANT")

    def test_wrong_child(self):
        self.assert_denial(fixture(), "WRONG_CHILD_OR_PARENT", replace(operation(), job_id="job-b"))

    def test_wrong_parent(self):
        self.assert_denial(fixture(), "WRONG_CHILD_OR_PARENT", replace(operation(), request_id="request-b"))

    def test_wrong_issuer_with_same_subject(self):
        s = fixture()
        self.assert_denial(replace(s, link=replace(s.link, issuer="https://issuer.example.invalid/pool-b")), "PRINCIPAL_LINK_MISMATCH")

    def test_wrong_subject(self):
        s = fixture()
        self.assert_denial(replace(s, link=replace(s.link, subject="subject-b")), "PRINCIPAL_LINK_MISMATCH")

    def test_untrusted_client_role_cannot_qualify(self):
        s = fixture()
        self.assert_denial(replace(s, caller=replace(s.caller, trusted_authorizer=False)), "UNTRUSTED_OR_EXPIRED_CALLER")

    def test_expired_token(self):
        s = fixture()
        self.assert_denial(replace(s, caller=replace(s.caller, token_current=False)), "UNTRUSTED_OR_EXPIRED_CALLER")

    def test_missing_principal_and_tenant(self):
        s = fixture()
        for field in ("issuer", "subject", "tenant"):
            with self.subTest(field=field):
                self.assert_denial(replace(s, caller=replace(s.caller, **{field: ""})), "MISSING_PRINCIPAL_OR_TENANT")

    def test_admin_client_unknown_do_not_gain_owner_execution(self):
        s = fixture()
        for role in ("admin", "client", "unknown", "", "owner,staff"):
            with self.subTest(role=role):
                self.assert_denial(replace(s, caller=replace(s.caller, role=role)), "ROLE_NOT_OWNER")

    def test_existing_staff_path_is_delegated_not_reauthorized(self):
        s = fixture()
        decision = assess_owner(replace(s, caller=replace(s.caller, role="staff")), operation())
        self.assertEqual(decision.outcome, Outcome.STAFF_COMPATIBILITY)
        self.assertNotEqual(decision.outcome, Outcome.ELIGIBLE)

    def test_legacy_email_never_qualifies_owner(self):
        s = fixture()
        legacy = replace(s.visit, canonical=False, legacy_worker_reference="synthetic-owner@example.invalid")
        self.assert_denial(replace(s, visit=legacy), "LEGACY_ONLY_ASSIGNMENT")

    def test_no_email_or_display_name_identity_field(self):
        with self.assertRaises(TypeError):
            Caller("issuer", "subject", "tenant", "owner", email="synthetic@example.invalid")
        with self.assertRaises(TypeError):
            Worker("worker", "tenant", "staff", display_name="Synthetic Owner")

    def test_unassigned_visit(self):
        s = fixture()
        self.assert_denial(replace(s, visit=replace(s.visit, assigned_worker_id=None)), "UNASSIGNED_VISIT")

    def test_wrong_worker(self):
        s = fixture()
        self.assert_denial(replace(s, visit=replace(s.visit, assigned_worker_id="worker-b")), "ASSIGNED_WORKER_MISMATCH")

    def test_reciprocal_worker_and_staff_linkage(self):
        s = fixture()
        for field in ("worker_id", "staff_id"):
            with self.subTest(field=field):
                self.assert_denial(replace(s, link=replace(s.link, **{field: "different"})), "RECIPROCAL_LINK_MISMATCH")

    def test_missing_canonical_identity(self):
        s = fixture()
        self.assert_denial(replace(s, worker=replace(s.worker, staff_id="")), "MISSING_CANONICAL_IDENTITY")

    def test_unhydrated_visit(self):
        s = fixture()
        self.assert_denial(replace(s, visit=replace(s.visit, hydrated=False)), "UNHYDRATED_VISIT")

    def test_ambiguous_linkage(self):
        for count in (0, 2):
            with self.subTest(count=count):
                self.assert_denial(replace(fixture(), active_link_count=count), "AMBIGUOUS_LINKAGE")

    def test_stale_assignment_revision(self):
        self.assert_denial(fixture(), "STALE_ASSIGNMENT_REVISION", operation(revision=2))

    def test_invalid_revision_is_not_coerced(self):
        s = fixture()
        for value in (0, -1, True, "1", None):
            with self.subTest(value=value):
                self.assert_denial(replace(s, visit=replace(s.visit, assignment_revision=value)), "INVALID_REVISION")

    def test_terminal_and_unassigned_states(self):
        s = fixture()
        for state in ("CANCELLED", "ARCHIVED", "PENDING", "JOB_CREATED"):
            with self.subTest(state=state):
                self.assert_denial(replace(s, visit=replace(s.visit, status=state)), "INVALID_VISIT_STATE")

    def test_unsupported_action(self):
        self.assert_denial(fixture(), "UNSUPPORTED_ACTION", operation("ASSIGN"))

    def test_records_are_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            fixture().worker.worker_id = "replacement"

    def test_complete_without_start_is_explicitly_pending(self):
        d = assess_owner(fixture(), operation("COMPLETE"))
        self.assertEqual((d.outcome, d.reason), (Outcome.PENDING, "OWNER_COMPLETE_WITHOUT_START_POLICY"))

    def test_replay_is_pending_not_an_implicit_business_decision(self):
        s = fixture()
        cases = [(replace(s.visit, started=True, started_assignment_revision=1), "START"),
                 (replace(s.visit, status="COMPLETED"), "COMPLETE")]
        for visit, action in cases:
            with self.subTest(action=action):
                self.assertEqual(assess_owner(replace(s, visit=visit), operation(action)).reason, "REPLAY_POLICY")

    def test_reassignment_after_start_is_pending(self):
        s = fixture()
        d = assess_owner(replace(s, visit=replace(s.visit, started=True, assignment_revision=2, started_assignment_revision=1)), operation("COMPLETE", revision=2))
        self.assertEqual((d.outcome, d.reason), (Outcome.PENDING, "REASSIGNMENT_AFTER_START_POLICY"))


class AtomicBoundaryModelTests(unittest.TestCase):
    def test_unchanged_commit_fence(self):
        s = fixture()
        self.assertEqual(assess_atomic_fence(s, operation(), capture_fence(s, operation(), 1), 1).outcome, Outcome.ELIGIBLE)

    def test_reassignment_between_read_and_commit(self):
        s = fixture()
        current = replace(s, visit=replace(s.visit, assigned_worker_id="worker-b", assignment_revision=2))
        self.assertEqual(assess_atomic_fence(current, operation(), capture_fence(s, operation(), 1), 1).reason, "ASSIGNED_WORKER_MISMATCH")

    def test_assignment_aba_does_not_restore_old_permission(self):
        s = fixture()
        current = replace(s, visit=replace(s.visit, assignment_revision=3))
        self.assertEqual(assess_atomic_fence(current, operation(), capture_fence(s, operation(), 1), 1).reason, "STALE_ASSIGNMENT_REVISION")

    def test_link_revocation_between_read_and_commit(self):
        s = fixture()
        current = replace(s, link=replace(s.link, active=False, version=2))
        self.assertEqual(assess_atomic_fence(current, operation(), capture_fence(s, operation(), 1), 1).reason, "REVOKED_LINK")

    def test_worker_disable_between_read_and_commit(self):
        s = fixture()
        current = replace(s, worker=replace(s.worker, active=False, version=2))
        self.assertEqual(assess_atomic_fence(current, operation(), capture_fence(s, operation(), 1), 1).reason, "INACTIVE_OR_UNASSIGNABLE_WORKER")

    def test_link_or_worker_version_change_requires_new_fence(self):
        s = fixture()
        for field in ("worker", "link"):
            with self.subTest(field=field):
                current = replace(s, **{field: replace(getattr(s, field), version=2)})
                self.assertEqual(assess_atomic_fence(current, operation(), capture_fence(s, operation(), 1), 1).reason, "COMMIT_FENCE_CHANGED")

    def test_identity_change_cannot_reuse_a_fence(self):
        s = fixture()
        current = replace(s, caller=replace(s.caller, subject="subject-b"), link=replace(s.link, subject="subject-b"))
        self.assertEqual(assess_atomic_fence(current, operation(), capture_fence(s, operation(), 1), 1).reason, "COMMIT_FENCE_CHANGED")

    def test_relinked_worker_cannot_reuse_an_old_fence(self):
        s = fixture()
        other = "wrk_22222222222222222222222222222222"
        current = replace(s, worker=replace(s.worker, worker_id=other),
                          link=replace(s.link, worker_id=other),
                          visit=replace(s.visit, assigned_worker_id=other))
        self.assertEqual(assess_atomic_fence(current, operation(), capture_fence(s, operation(), 1), 1).reason, "COMMIT_FENCE_CHANGED")

    def test_parent_change_rejects_stale_commit(self):
        s = fixture()
        self.assertEqual(assess_atomic_fence(s, operation(), capture_fence(s, operation(), 1), 2).reason, "COMMIT_FENCE_CHANGED")

    def test_duplicate_start_does_not_become_a_second_eligible_mutation(self):
        s = fixture()
        current = replace(s, visit=replace(s.visit, started=True, started_assignment_revision=1))
        self.assertEqual(assess_atomic_fence(current, operation(), capture_fence(s, operation(), 1), 1).outcome, Outcome.PENDING)

    def test_revoked_caller_never_gains_new_execution_via_replay(self):
        s = fixture()
        current = replace(s, link=replace(s.link, active=False), visit=replace(s.visit, status="COMPLETED"))
        self.assertEqual(assess_owner(current, operation("COMPLETE")).outcome, Outcome.DENIED)
        # Whether an old receipt may be disclosed is a separate pending policy.

    def test_legacy_writer_invalidates_canonical_owner_eligibility(self):
        s = fixture()
        changed = legacy_assignment_invalidation(s.visit, 1)
        self.assertEqual(changed.assignment_revision, 2)
        self.assertIsNone(changed.assigned_worker_id)
        self.assertFalse(changed.canonical)
        self.assertEqual(assess_owner(replace(s, visit=changed), operation(revision=2)).reason, "LEGACY_ONLY_ASSIGNMENT")
        self.assertTrue(s.visit.canonical)  # no mutation of input

    def test_stale_legacy_writer_cannot_invalidate_a_newer_assignment(self):
        with self.assertRaisesRegex(ValueError, "STALE_ASSIGNMENT_REVISION"):
            legacy_assignment_invalidation(fixture().visit, 2)

    def test_legacy_expected_revision_does_not_coerce_boolean(self):
        with self.assertRaisesRegex(ValueError, "STALE_ASSIGNMENT_REVISION"):
            legacy_assignment_invalidation(fixture().visit, True)

    def test_parent_expected_revision_does_not_coerce_boolean(self):
        with self.assertRaisesRegex(ValueError, "STALE_PARENT_REVISION"):
            completion_rollup_cas(ParentModel("request-a", "tenant-a", frozenset({"job-a"})), "job-a", True)

    def test_concurrent_sibling_completion_has_no_lost_update(self):
        parent = ParentModel("request-a", "tenant-a", frozenset({"job-a", "job-b"}))
        a = completion_rollup_cas(parent, "job-a", 1)
        with self.assertRaisesRegex(ValueError, "STALE_PARENT_REVISION"):
            completion_rollup_cas(a, "job-b", 1)
        b = completion_rollup_cas(a, "job-b", a.revision)
        self.assertEqual(b.completed, parent.children)
        self.assertEqual(len(b.completed), 2)
        self.assertEqual(parent.completed, frozenset())

    def test_duplicate_rollup_does_not_double_count(self):
        p = ParentModel("request-a", "tenant-a", frozenset({"job-a"}))
        once = completion_rollup_cas(p, "job-a", 1)
        self.assertEqual(completion_rollup_cas(once, "job-a", once.revision), once)

    def test_unknown_sibling_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "WRONG_CHILD"):
            completion_rollup_cas(ParentModel("request-a", "tenant-a", frozenset({"job-a"})), "job-b", 1)

    def test_models_have_no_external_dependency_or_live_import(self):
        root = Path(__file__).resolve().parents[2]
        model = Path(__file__).with_name("worker_identity_contract.py")
        tree = ast.parse(model.read_text(encoding="utf-8"))
        imports = {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertLessEqual(imports, {"dataclasses", "enum", "typing", "decimal"})
        plain_imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        self.assertEqual(plain_imports, {"re"})
        for file in (root / "src").rglob("*.py"):
            self.assertNotIn("worker_identity_contract", file.read_text(encoding="utf-8"))



class CorrectedExecutionFenceTests(unittest.TestCase):
    def test_started_revision_rejects_coercive_values(self):
        s = fixture()
        for value in (True, False, 1.0, 1.5, Decimal("1"), -1, 0, "1", None, MAX_REVISION + 1):
            with self.subTest(value=value):
                current = replace(s, visit=replace(s.visit, started=True, started_assignment_revision=value))
                self.assertEqual(assess_owner(current, operation("COMPLETE")).reason, "INVALID_EXECUTION_PROVENANCE")

    def test_explicit_dynamodb_integral_conversion(self):
        for value in (1, MAX_REVISION, Decimal("1"), Decimal("1.000"), Decimal(MAX_REVISION)):
            with self.subTest(value=value):
                self.assertIs(type(parse_dynamo_revision(value)), int)
                self.assertEqual(parse_dynamo_revision(value), int(value))

    def test_db_parser_rejects_invalid_values(self):
        for value in (True, False, 1.0, 1.5, "1", None, -1, 0, MAX_REVISION + 1,
                      Decimal("1.5"), Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity"),
                      Decimal("-1"), Decimal("0"), Decimal(MAX_REVISION + 1)):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_dynamo_revision(value)

    def test_start_fence_cannot_be_reused_for_complete(self):
        s = fixture()
        current = replace(s, visit=replace(s.visit, started=True, started_assignment_revision=1))
        self.assertEqual(assess_atomic_fence(current, operation("COMPLETE"), capture_fence(s, operation(), 1), 1).reason, "COMMIT_FENCE_CHANGED")

    def test_complete_fence_cannot_be_reused_for_start(self):
        s = fixture()
        started = replace(s, visit=replace(s.visit, started=True, started_assignment_revision=1))
        fence = capture_fence(started, operation("COMPLETE"), 1)
        self.assertEqual(assess_atomic_fence(s, operation(), fence, 1).reason, "COMMIT_FENCE_CHANGED")

    def test_operation_identity_and_payload_are_bound(self):
        s = fixture()
        for op in (replace(operation(), operation_id="op_" + "2" * 32),
                   replace(operation(), payload_digest="b" * 64)):
            self.assertEqual(assess_atomic_fence(s, op, capture_fence(s, operation(), 1), 1).reason, "COMMIT_FENCE_CHANGED")

    def test_execution_revision_is_fenced(self):
        s = fixture()
        current = replace(s, visit=replace(s.visit, execution_revision=2))
        self.assertEqual(assess_owner(current, operation()).reason, "STALE_EXECUTION_REVISION")
        self.assertEqual(assess_atomic_fence(current, replace(operation(), expected_execution_revision=2), capture_fence(s, operation(), 1), 1).reason, "COMMIT_FENCE_CHANGED")

    def test_all_domain_revisions_reject_non_integer_values(self):
        s = fixture()
        for value in (True, 1.0, Decimal("1"), "1", -1, 0, MAX_REVISION + 1):
            for field in ("worker", "link"):
                current = replace(s, **{field: replace(getattr(s, field), version=value)})
                self.assertEqual(assess_owner(current, operation()).reason, "INVALID_REVISION")
            current = replace(s, visit=replace(s.visit, execution_revision=value))
            self.assertEqual(assess_owner(current, operation()).reason, "INVALID_REVISION")

    def test_malformed_operation_binding_never_qualifies(self):
        for field, value in (("operation_id", ""), ("payload_digest", "bad"),
                             ("expected_execution_revision", True), ("expected_assignment_revision", 1.0)):
            self.assertEqual(assess_owner(fixture(), replace(operation(), **{field: value})).reason, "INVALID_OPERATION_BINDING")

    def test_forged_boolean_fence_revision_does_not_equal_integer(self):
        s = fixture()
        fence = capture_fence(s, operation(), 1)
        for field in ("parent_revision", "link_version", "worker_version", "assignment_revision", "execution_revision"):
            self.assertEqual(assess_atomic_fence(s, operation(), replace(fence, **{field: True}), 1).reason, "INVALID_FENCE")


if __name__ == "__main__":
    unittest.main()