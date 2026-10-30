import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))
import ast
import re
import unittest
from copy import deepcopy
from common.worker_identity import ContractError, Failure
from common.worker_identity_store import build_linkage_request, build_assignment_request, checked_plan
from worker_identity_fixtures import fixture


def assignment(**changes):
    p, w, l, s, j, parent = fixture()
    args = dict(table_name="synthetic-table", tenant=p.tenant, request_id="request-a", job_id="job-a",
                worker=w, staff=s, job=j, parent=parent, expected_assignment=1, expected_execution=1,
                expected_parent=1, operation="op_" + "1" * 32, payload_hash="a" * 64)
    return build_assignment_request(**(args | changes))


def linkage(staff=None, expected=None, **changes):
    p, w, l, s, *_ = fixture()
    s.pop("canonical_worker_id")
    s.pop("identity_revision")
    return build_linkage_request("synthetic-table", p, changes.get("worker", w), changes.get("link", l), staff or s, expected)


class WorkerIdentityStoreTests(unittest.TestCase):
    def test_linkage_is_conditional_create_with_no_overwrite(self):
        plan = linkage()
        actions = plan.request["TransactItems"]
        self.assertEqual(len(actions), 3)
        for action in actions[:2]:
            self.assertEqual(action["Put"]["ConditionExpression"], "attribute_not_exists(PK) AND attribute_not_exists(SK)")
        update = actions[2]["Update"]
        self.assertIn("attribute_not_exists(canonical_worker_id)", update["ConditionExpression"])
        self.assertIn("attribute_not_exists(identity_revision)", update["ConditionExpression"])
        self.assertEqual(update["ExpressionAttributeValues"][":next"], {"N": "1"})
        self.assertIn("ENROLLMENT_PROOF_AND_OPERATOR_PENDING", plan.blockers)
        self.assertFalse(hasattr(plan, "execute"))

    def test_deterministic_link_key_contends_for_same_principal(self):
        p, w, l, s, *_ = fixture()
        other = "wrk_" + "2" * 32
        a = linkage().request["TransactItems"][1]["Put"]
        b = linkage(worker=w | {"worker_id": other, "SK": "WORKER#" + other}, link=l | {"worker_id": other}).request["TransactItems"][1]["Put"]
        self.assertEqual((a["Item"]["PK"], a["Item"]["SK"]), (b["Item"]["PK"], b["Item"]["SK"]))
        self.assertIn("attribute_not_exists", b["ConditionExpression"])
        # Structure proves contention target, not that any database transaction ran.

    def test_existing_staff_revision_is_cas_and_incremented(self):
        p, w, l, s, *_ = fixture()
        s.pop("canonical_worker_id")
        update = linkage(staff=s, expected=1).request["TransactItems"][2]["Update"]
        self.assertIn("identity_revision = :expected", update["ConditionExpression"])
        self.assertEqual(update["ExpressionAttributeValues"][":next"], {"N": "2"})
        with self.assertRaises(ContractError):
            linkage(staff=s, expected=2)

    def test_existing_pointer_is_never_replaced(self):
        p, w, l, s, *_ = fixture()
        with self.assertRaises(ContractError):
            linkage(staff=s, expected=1)

    def test_linkage_rejects_unverified_subject_or_tenant(self):
        p, w, l, s, *_ = fixture()
        s.pop("canonical_worker_id")
        s.pop("identity_revision")
        for bad in (s | {"cognito_sub": "subject-b"}, s | {"company_id": "tenant_b"}, s | {"is_active": False}):
            with self.assertRaises(ContractError):
                linkage(staff=bad)

    def test_relink_and_noninitial_versions_are_not_enrollment(self):
        p, w, l, s, *_ = fixture()
        with self.assertRaises(ContractError):
            linkage(worker=w | {"version": 2})
        with self.assertRaises(ContractError):
            linkage(link=l | {"version": 2})

    def test_exact_child_assignment_has_four_distinct_items(self):
        plan = assignment()
        actions = plan.request["TransactItems"]
        self.assertEqual([next(iter(a)) for a in actions], ["ConditionCheck", "ConditionCheck", "Update", "Update"])
        targets = [(next(iter(a.values()))["Key"]["PK"]["S"], next(iter(a.values()))["Key"]["SK"]["S"]) for a in actions]
        self.assertEqual(len(set(targets)), 4)
        self.assertEqual(targets[2], ("JOB#job-a", "REQ#request-a"))
        self.assertIn("NO_RUNTIME_INTEGRATION", plan.blockers)
        self.assertIn("AUDIT_AND_DURABLE_RECEIPT_PENDING", plan.blockers)

    def test_child_conditions_fence_all_assignment_inputs(self):
        update = assignment().request["TransactItems"][2]["Update"]
        condition = update["ConditionExpression"]
        for text in ("company_id = :tenant", "request_id = :rid", "client_id = :cid",
                     "assignment_revision = :ar", "execution_revision = :er", "assignment_contract_version = :cv",
                     "#status = :oldstatus", "attribute_not_exists(started_at)", "assigned_worker_id = :oldwid"):
            self.assertIn(text, condition)
        self.assertEqual(update["ExpressionAttributeValues"][":next"], {"N": "2"})

    def test_parent_membership_status_and_revision_are_fenced(self):
        update = assignment().request["TransactItems"][3]["Update"]
        for text in ("workflow_revision = :rev", "contains(job_ids, :jid)", "#status = :status", "company_id = :tenant", "client_id = :cid"):
            self.assertIn(text, update["ConditionExpression"])

    def test_worker_and_staff_revocation_inputs_are_fenced(self):
        actions = assignment().request["TransactItems"]
        for action in actions[:2]:
            condition = action["ConditionCheck"]["ConditionExpression"]
            self.assertIn("is_active = :yes", condition)
            self.assertIn("is_assignable = :yes", condition)
        self.assertIn("#v = :version", actions[0]["ConditionCheck"]["ConditionExpression"])
        self.assertIn("identity_revision = :revision", actions[1]["ConditionCheck"]["ConditionExpression"])

    def test_aba_and_parent_and_execution_races_reject_stale_snapshot(self):
        p, w, l, s, j, parent = fixture()
        for change in ({"job": j | {"assignment_revision": 3}}, {"job": j | {"execution_revision": 2}},
                       {"parent": parent | {"workflow_revision": 2}}):
            with self.assertRaises(ContractError) as error:
                assignment(**change)
            self.assertEqual(error.exception.category, Failure.STALE)

    def test_started_job_and_terminal_parent_are_non_grants(self):
        p, w, l, s, j, parent = fixture()
        started = j | {"started_at": "synthetic-time", "started_worker_id": w["worker_id"], "started_assignment_revision": 1}
        for change in ({"job": started}, {"parent": parent | {"status": "CANCELLED"}}):
            with self.assertRaises(ContractError):
                assignment(**change)

    def test_inactive_or_wrong_worker_never_builds_assignment(self):
        p, w, l, s, *_ = fixture()
        for change in ({"worker": w | {"is_active": False}}, {"staff": s | {"is_assignable": False}},
                       {"staff": s | {"canonical_worker_id": "wrk_" + "2" * 32}}):
            with self.assertRaises(ContractError):
                assignment(**change)

    def test_legacy_job_never_promoted_by_builder(self):
        *_, j, parent = fixture()
        j.pop("assignment_contract_version")
        j["worker_id"] = "synthetic@example.invalid"
        with self.assertRaises(ContractError):
            assignment(job=j)

    def test_null_unassigned_slot_has_exact_type_condition(self):
        *_, j, parent = fixture()
        action = assignment(job=j | {"assigned_worker_id": None, "status": "JOB_CREATED"}).request["TransactItems"][2]["Update"]
        self.assertIn("attribute_type(assigned_worker_id, :nulltype)", action["ConditionExpression"])

    def test_builder_does_not_mutate_inputs(self):
        p, w, l, s, j, parent = fixture()
        before = deepcopy((w, s, j, parent))
        assignment(worker=w, staff=s, job=j, parent=parent)
        self.assertEqual((w, s, j, parent), before)

    def test_no_duplicate_item_actions_or_empty_conditions(self):
        plan = assignment()
        actions = plan.request["TransactItems"]
        with self.assertRaises(ContractError):
            checked_plan("synthetic-table", [actions[2], actions[2]], ("NO_RUNTIME_INTEGRATION",))
        bad = deepcopy(actions[2])
        bad["Update"]["ConditionExpression"] = ""
        with self.assertRaises(ContractError):
            checked_plan("synthetic-table", [bad], ("NO_RUNTIME_INTEGRATION",))

    def test_no_plan_can_drop_inactive_blocker(self):
        with self.assertRaises(ContractError):
            checked_plan("synthetic-table", assignment().request["TransactItems"], ())

    def test_expression_aliases_and_values_are_exactly_used(self):
        for plan in (assignment(), linkage()):
            for action in plan.request["TransactItems"]:
                spec = next(iter(action.values()))
                text = spec["ConditionExpression"] + " " + spec.get("UpdateExpression", "")
                self.assertEqual(set(re.findall(r":[A-Za-z][A-Za-z0-9_]*", text)), set(spec.get("ExpressionAttributeValues", {})))
                self.assertEqual(set(re.findall(r"#[A-Za-z][A-Za-z0-9_]*", text)), set(spec.get("ExpressionAttributeNames", {})))

    def test_foundation_is_unwired_and_has_no_sdk_or_io_import(self):
        root = Path(__file__).resolve().parents[2]
        names = {"worker_identity", "worker_identity_store", "assignment_contract"}
        allowed = {"dataclasses", "decimal", "enum", "hashlib", "json", "re", "urllib", "common"}
        for name in names:
            tree = ast.parse((root / "src/backend/common" / (name + ".py")).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue(all(a.name.split(".")[0] in allowed for a in node.names))
                if isinstance(node, ast.ImportFrom):
                    self.assertIn(node.module.split(".")[0], allowed)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"open", "exec", "eval", "__import__"})
        for file in (root / "src").rglob("*.py"):
            if file.stem not in names:
                for name in names:
                    self.assertNotIn("import " + name, file.read_text(encoding="utf-8"))
                    self.assertNotIn("from common." + name, file.read_text(encoding="utf-8"))
