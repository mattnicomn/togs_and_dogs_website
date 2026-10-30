"""Pure Moto expression evaluation only. No client, mock table, AWS call or write.

Characterization cases explicitly document limits of snapshot revision checks;
unchanged recreated records and unversioned legacy writes remain activation blockers.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))
import unittest
from copy import deepcopy
from boto3.dynamodb.types import TypeSerializer
from botocore.session import Session
from botocore.validate import validate_parameters
from moto.dynamodb.comparisons import get_filter_expression
from moto.dynamodb.models import Item, DynamoType
from common.assignment_contract import parse_assignment
from common.worker_identity import ContractError, Failure
from test_worker_identity_store import assignment, linkage
from worker_identity_fixtures import fixture


def evaluates(spec, record):
    if record is None:
        item = None
    else:
        serializer = TypeSerializer()
        attrs = {k: serializer.serialize(v) for k, v in record.items()}
        item = Item(DynamoType(attrs["PK"]), DynamoType(attrs["SK"]), attrs)
    expression = get_filter_expression(spec["ConditionExpression"],
                                      spec.get("ExpressionAttributeNames", {}),
                                      spec.get("ExpressionAttributeValues", {}))
    return expression.expr(item)


def conditions(plan, records):
    return [evaluates(next(iter(action.values())), record)
            for action, record in zip(plan.request["TransactItems"], records)]


class FullExpressionBehaviorTests(unittest.TestCase):
    def test_valid_snapshot_satisfies_all_four_conditions(self):
        p, w, l, s, j, parent = fixture()
        self.assertEqual(conditions(assignment(), [w, s, j, parent]), [True]*4)

    def test_parent_membership_is_list_not_string_set_map_null_or_absent(self):
        *_, parent = fixture()
        spec = assignment().request["TransactItems"][3]["Update"]
        for value in ("prefix-job-a-suffix", {"job-a"}, {"job-a": True}, None, [], ["job-b"]):
            with self.subTest(type=type(value).__name__):
                self.assertFalse(evaluates(spec, parent | {"job_ids": value}))
        self.assertFalse(evaluates(spec, {k:v for k,v in parent.items() if k != "job_ids"}))
        self.assertTrue(evaluates(spec, parent))

    def test_malformed_membership_after_successful_parsing_is_rejected(self):
        p, w, l, s, j, parent = fixture()
        plan = assignment(parent=parent)
        self.assertFalse(all(conditions(plan, [w, s, j, parent | {"job_ids": "job-a"}])))

    def test_explicit_null_start_is_rejected_at_adapter(self):
        *_, j, parent = fixture()
        with self.assertRaises(ContractError) as error:
            parse_assignment(j | {"started_at": None}, "tenant_a", "request-a", "job-a")
        self.assertEqual(error.exception.category, Failure.MALFORMED)
        self.assertNotIn("started_at", parse_assignment(j, "tenant_a", "request-a", "job-a"))

    def test_absent_valid_and_malformed_start_forms(self):
        p, w, l, s, j, parent = fixture()
        started = j | {"started_at": "2026-10-29T12:00:00Z", "started_worker_id": w["worker_id"], "started_assignment_revision": 1}
        self.assertEqual(parse_assignment(started, p.tenant, "request-a", "job-a")["started_at"], started["started_at"])
        for value in ("", False, 1, [], {}):
            with self.assertRaises(ContractError):
                parse_assignment(started | {"started_at": value}, p.tenant, "request-a", "job-a")
        spec = assignment().request["TransactItems"][2]["Update"]
        self.assertTrue(evaluates(spec, j))
        self.assertFalse(evaluates(spec, started))
        self.assertFalse(evaluates(spec, j | {"started_at": None}))

    def test_concurrent_sibling_requires_parent_cas_retry(self):
        p, w, l, s, j, parent = fixture()
        sibling = j | {"PK": "JOB#job-b"}
        plan_b = assignment(job_id="job-b", job=sibling)
        self.assertTrue(all(conditions(plan_b, [w, s, sibling, parent])))
        after_a = parent | {"workflow_revision": 2}
        self.assertFalse(all(conditions(plan_b, [w, s, sibling, after_a])))
        refreshed = assignment(job_id="job-b", job=sibling, parent=after_a, expected_parent=2)
        self.assertTrue(all(conditions(refreshed, [w, s, sibling, after_a])))
        # Explicit before/after snapshots, not threads or a database commit.

    def test_conditional_failure_produces_non_executable_design_only(self):
        p, w, l, s, j, parent = fixture()
        records = [w, s, j, parent | {"workflow_revision": 2}]
        before = deepcopy(records)
        plan = assignment()
        self.assertFalse(all(conditions(plan, records)))
        self.assertEqual(records, before)
        self.assertIn("NO_RUNTIME_INTEGRATION", plan.blockers)
        self.assertFalse(hasattr(plan, "execute"))
        # No atomicity claim: the production service is not invoked.

    def test_missing_records_and_advanced_versions_fail_conditions(self):
        p, w, l, s, j, parent = fixture()
        records = [w, s, j, parent]
        for index, version_field in enumerate(("version", "identity_revision", "assignment_revision", "workflow_revision")):
            changed = list(records)
            changed[index] = None
            self.assertFalse(all(conditions(assignment(), changed)))
            changed[index] = records[index] | {version_field: 3}
            self.assertFalse(all(conditions(assignment(), changed)))

    def test_delete_recreate_same_revision_aba_is_explicit_unresolved_blocker(self):
        p, w, l, s, j, parent = fixture()
        plan = assignment()
        recreated = deepcopy([w, s, j, parent])
        self.assertTrue(all(conditions(plan, recreated)))
        self.assertIn("ALL_WRITERS_AND_MIXED_VERSION_COVERAGE_PENDING", plan.blockers)
        self.assertIn("NO_RUNTIME_INTEGRATION", plan.blockers)
        # Identical recreated bytes cannot be distinguished by these revisions.
        # Requires durable non-reuse/incarnation/tombstone design before activation.

    def test_unversioned_legacy_write_preserving_canonical_fields_is_blocked_from_activation(self):
        p, w, l, s, j, parent = fixture()
        plan = assignment()
        stale = j | {"worker_id": "legacy-synthetic@example.invalid"}
        self.assertTrue(all(conditions(plan, [w, s, stale, parent])))
        self.assertIn("ALL_WRITERS_AND_MIXED_VERSION_COVERAGE_PENDING", plan.blockers)
        self.assertIn("NO_RUNTIME_INTEGRATION", plan.blockers)
        # Not a fix for legacy writers. Their real integration is prohibited here.
        self.assertFalse(evaluates(plan.request["TransactItems"][2]["Update"], stale | {"assignment_contract_version": 0}))
        self.assertFalse(evaluates(plan.request["TransactItems"][2]["Update"], stale | {"assignment_revision": 2}))

    def test_linkage_unique_key_conditions_reject_existing_records(self):
        p, w, l, s, j, parent = fixture()
        plan = linkage()
        self.assertFalse(evaluates(plan.request["TransactItems"][0]["Put"], w))
        self.assertFalse(evaluates(plan.request["TransactItems"][1]["Put"], l))
        self.assertTrue(evaluates(plan.request["TransactItems"][0]["Put"], None))
        self.assertTrue(evaluates(plan.request["TransactItems"][1]["Put"], None))
        # Create-key contention shape only; enrollment proof remains pending.

    def test_wrong_child_tenant_worker_revocation_and_execution_revision(self):
        p, w, l, s, j, parent = fixture()
        plan = assignment()
        for index, delta in ((0, {"is_active": False}), (1, {"cognito_sub": "other-subject"}),
                             (2, {"company_id": "tenant_b"}), (2, {"request_id": "request-b"}),
                             (2, {"assigned_worker_id": "wrk_"+"2"*32}), (2, {"execution_revision": 2})):
            records = [w, s, j, parent]
            records[index] = records[index] | delta
            self.assertFalse(all(conditions(plan, records)))

    def test_three_transaction_variants_pass_service_model_without_client(self):
        *_, j, parent = fixture()
        model = Session().get_service_model("dynamodb").operation_model("TransactWriteItems").input_shape
        for plan in (assignment(), linkage(), assignment(job=j | {"assigned_worker_id": None, "status": "JOB_CREATED"})):
            validate_parameters(plan.request, model)
