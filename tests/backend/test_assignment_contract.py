import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))
import unittest
from common.worker_identity import ContractError, Failure
from common.assignment_contract import parse_assignment, parse_parent, assert_assignment_snapshot, execution_binding
from worker_identity_fixtures import fixture


class AssignmentContractTests(unittest.TestCase):
    def test_parse_does_not_mutate_or_promote_legacy_email(self):
        _, _, _, _, j, _ = fixture()
        source = j | {"worker_id": "synthetic@example.invalid"}
        self.assertNotIn("worker_id", parse_assignment(source, "tenant_a", "request-a", "job-a"))
        self.assertEqual(source["worker_id"], "synthetic@example.invalid")
        legacy = {k:v for k,v in source.items() if not k.startswith("assignment_")}
        with self.assertRaises(ContractError) as error:
            parse_assignment(legacy, "tenant_a", "request-a", "job-a")
        self.assertEqual(error.exception.category, Failure.LEGACY_ONLY)

    def test_wrong_child_parent_or_tenant(self):
        *_, j, p = fixture()
        for bad in (j | {"PK": "JOB#job-b"}, j | {"SK": "REQ#request-b"}, j | {"request_id": "request-b"}, j | {"company_id": "tenant_b"}):
            with self.assertRaises(ContractError):
                parse_assignment(bad, "tenant_a", "request-a", "job-a")

    def test_started_provenance_requires_strict_revision(self):
        *_, j, p = fixture()
        for value in (True, 1.0, "1", -1, 0):
            with self.assertRaises(ContractError):
                parse_assignment(j | {"started_at": "synthetic-time", "started_worker_id": j["assigned_worker_id"], "started_assignment_revision": value}, "tenant_a", "request-a", "job-a")

    def test_orphaned_started_metadata_fails_closed(self):
        *_, j, p = fixture()
        with self.assertRaises(ContractError):
            parse_assignment(j | {"started_assignment_revision": 1}, "tenant_a", "request-a", "job-a")

    def test_unknown_contract_and_missing_revision(self):
        *_, j, p = fixture()
        for bad in (j | {"assignment_contract_version": 2}, {k:v for k,v in j.items() if k != "execution_revision"}):
            with self.assertRaises(ContractError):
                parse_assignment(bad, "tenant_a", "request-a", "job-a")

    def test_aba_and_execution_and_parent_races(self):
        *_, j, p = fixture()
        for job, parent in ((j | {"assignment_revision": 3}, p), (j | {"execution_revision": 2}, p), (j, p | {"workflow_revision": 2})):
            with self.assertRaises(ContractError) as error:
                assert_assignment_snapshot(job, parent, 1, 1, 1)
            self.assertEqual(error.exception.category, Failure.STALE)

    def test_membership_and_client_mismatch(self):
        *_, j, p = fixture()
        for parent in (p | {"job_ids": ["job-b"]}, p | {"client_id": "client-b"}):
            with self.assertRaises(ContractError) as error:
                assert_assignment_snapshot(j, parent, 1, 1, 1)
            self.assertEqual(error.exception.category, Failure.WRONG_CHILD)

    def test_started_reassignment_is_pending_not_approved(self):
        *_, j, p = fixture()
        with self.assertRaises(ContractError) as error:
            assert_assignment_snapshot(j | {"started_at": "synthetic-time"}, p, 1, 1, 1)
        self.assertEqual(error.exception.category, Failure.POLICY_PENDING)

    def test_terminal_parent_and_child_are_pending_non_grants(self):
        *_, j, p = fixture()
        for job, parent in ((j | {"status": "COMPLETED"}, p), (j, p | {"status": "CANCELLED"})):
            with self.assertRaises(ContractError):
                assert_assignment_snapshot(job, parent, 1, 1, 1)

    def test_parent_shape_rejects_duplicate_or_guessed_children(self):
        *_, j, p = fixture()
        for children in (["job-a", "job-a"], [None], [], "job-a"):
            with self.assertRaises(ContractError):
                parse_parent(p | {"job_ids": children}, "tenant_a", "request-a")

    def test_action_operation_payload_and_both_revisions_are_bound(self):
        args = ("START", "op_" + "1" * 32, "a" * 64, 1, 1)
        original = execution_binding(*args)
        for index, value in enumerate(("COMPLETE", "op_" + "2" * 32, "b" * 64, 2, 2)):
            changed = list(args)
            changed[index] = value
            self.assertNotEqual(execution_binding(*changed), original)
