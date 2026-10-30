"""Offline full-expression evaluation and a simulated all-or-nothing store only."""
import ast
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))
from boto3.dynamodb.types import TypeDeserializer
from botocore.session import Session
from botocore.validate import validate_parameters
from test_worker_identity_expression_behavior import evaluates
from common.atomic_workflow_contract import (
    Key, Record, Operation, Effect, Intent, Evidence, Plan, WorkflowError, MARKERS,
    record, canonical, build_plan, transaction, claim, report, reconcile, effect_update_request,
)


def fixture(children=2, action="ASSIGN", op_id="op-a"):
    op = Operation("tenant_a","request-a","client-a",op_id,action)
    parent = record(Key(op.tenant,"REQ#request-a","CLIENT#client-a"),"life-parent",1,
        company_id=op.tenant,request_id=op.request_id,client_id=op.client_id,status="APPROVED",
        job_ids=["job-"+str(i) for i in range(children)],pet_ids=["pet-a"])
    pet = record(Key(op.tenant,"PET#pet-a","CLIENT#client-a"),"life-pet",1,
        company_id=op.tenant,client_id=op.client_id,pet_id="pet-a")
    jobs = tuple(record(Key(op.tenant,"JOB#job-"+str(i),"REQ#request-a"),"life-job-"+str(i),1,
        company_id=op.tenant,request_id=op.request_id,client_id=op.client_id,status="JOB_CREATED",pet_ids=["pet-a"])
        for i in range(children))
    before = (parent,pet)+jobs
    after = tuple(change(r,status="ASSIGNED",worker_id="legacy-worker") if not r.key.pk.startswith("PET#") else r for r in before)
    if action=="CANCEL": after=tuple(change(r,status="CANCELLED") if not r.key.pk.startswith("PET#") else r for r in before)
    effect = Effect("calendar-a","CALENDAR",jobs[0].key,canonical({"action":action}))
    notify = Effect("notification-a","NOTIFICATION",parent.key,canonical({"action":action}))
    return build_plan(op,before,after,(effect,notify))


def change(row, **delta):
    return record(row.key,row.incarnation,row.revision+1,**(row.data()|delta))


class SimulatedStore:
    """Test interpreter, NOT database or isolation proof. Never invokes a client."""
    def __init__(self, plan):
        self.rows={}
        self.receipts={}
        self.intents={}
        for r in plan.before:
            self.rows[(r.key.pk,r.key.sk)]=r.item()
            self.rows[("LIFETIME#"+r.key.token(),"PERMANENT")]={"PK":"LIFETIME#"+r.key.token(),"SK":"PERMANENT","incarnation":r.incarnation,"retired":False}

    def commit(self, plan, conflict=False):
        # Validate the complete immutable plan before trusting any replay receipt.
        request=transaction(plan,"offline-workflows")
        opkey=(plan.operation.tenant,plan.operation.operation_id)
        if opkey in self.receipts:
            if self.receipts[opkey]!=plan.binding: raise WorkflowError("REPLAY_MISMATCH")
            return "REPLAY_PERSISTED"
        proposed=deepcopy(self.rows)
        decode=TypeDeserializer().deserialize
        for action in request["TransactItems"]:
            kind,spec=next(iter(action.items()))
            raw=spec.get("Key",spec.get("Item"))
            key=(raw["PK"]["S"],raw["SK"]["S"])
            if not evaluates(spec,self.rows.get(key)) or conflict:
                raise WorkflowError("CONDITIONAL_COMMIT_REFUSED")
            if kind=="Put": proposed[key]={k:decode(v) for k,v in spec["Item"].items()}
        # The only publication point. No partial writes or provider effects.
        self.rows=proposed
        self.receipts[opkey]=plan.binding
        for e in plan.effects:
            self.intents[(plan.operation.tenant,plan.operation.operation_id,e.effect_id)]=Intent(plan.operation.tenant,plan.operation.operation_id,e.effect_id,plan.binding)
        return "PERSISTED_EFFECTS_PENDING"

    def update_intent(self, plan, effect, action, context):
        key=(plan.operation.tenant,plan.operation.operation_id,effect)
        old=self.intents[key]
        request=effect_update_request(plan,old,old.revision,"offline-workflows",action,context)
        for entry in request["TransactItems"]:
            spec=next(iter(entry.values()));raw=spec["Key"];target=(raw["PK"]["S"],raw["SK"]["S"])
            if not evaluates(spec,self.rows.get(target)):raise WorkflowError("STALE_AGGREGATE_OR_INTENT")
        if action=="CLAIM":new=claim(old,plan,effect,old.revision,context)
        elif action=="REPORT":new=report(old,plan,effect,old.revision,*context)
        else:new=reconcile(old,plan,effect,old.revision,context)
        target=("OP#"+old.tenant+"#"+old.operation_id,"EFFECT#"+old.effect_id)
        self.rows[target] = self.rows[target] | {"state":new.state,"revision":new.revision,"claim_id":new.claim_id}
        self.intents[key]=new
        return new

    def claim(self, plan, effect, claim_id="attempt-a"):
        return self.update_intent(plan,effect,"CLAIM",claim_id)

    def reconcile(self, plan, effect, evidence):
        return self.update_intent(plan,effect,"RECONCILE",evidence)


class MockProvider:
    def __init__(self): self.calls=[]
    def apply(self, intent, ambiguous=False):
        self.calls.append((intent.operation_id,intent.effect_id,intent.claim_id))
        return "UNKNOWN" if ambiguous else "APPLIED"


def deliver(store, provider, plan, effect, interrupt=False, ambiguous=False):
    intent=store.claim(plan,effect)
    if interrupt: return  # Unknown whether the provider was invoked; durable claim remains.
    result=provider.apply(intent,ambiguous)
    store.update_intent(plan,effect,"REPORT",(intent.claim_id,result))


def evidence(intent, **delta):
    return replace(Evidence(intent.tenant,intent.operation_id,intent.effect_id,intent.binding,intent.claim_id,"APPLIED",True,True),**delta)


class AtomicWorkflowTests(unittest.TestCase):
    def test_all_conditions_pass_and_success_is_persistence_only(self):
        p=fixture();s=SimulatedStore(p)
        self.assertEqual(s.commit(p),"PERSISTED_EFFECTS_PENDING")
        self.assertEqual(len(s.intents),2)
        self.assertTrue(all(i.state=="PENDING" for i in s.intents.values()))
        for r in p.after:self.assertEqual(s.rows[(r.key.pk,r.key.sk)],r.item())

    def test_failed_condition_has_zero_changes_or_prior_effects(self):
        p=fixture();s=SimulatedStore(p);provider=MockProvider()
        s.rows[(p.before[-1].key.pk,p.before[-1].key.sk)]["legacy_write_revision"]=2
        before=deepcopy(s.__dict__)
        with self.assertRaises(WorkflowError):s.commit(p)
        self.assertEqual(s.__dict__,before);self.assertEqual(provider.calls,[])

    def test_conflict_has_no_partial_batch_or_outbox(self):
        p=fixture(5);s=SimulatedStore(p);before=deepcopy(s.__dict__)
        with self.assertRaises(WorkflowError):s.commit(p,conflict=True)
        self.assertEqual(s.__dict__,before)

    def test_each_reservation_inserted_after_snapshot_refuses_atomically(self):
        p=fixture()
        for row in p.after:
            s=SimulatedStore(p);token=row.key.token()
            s.rows[("RESERVATION#"+token,"PERMANENT")]={"PK":"RESERVATION#"+token,"SK":"PERMANENT","incarnation":"canonical-life"}
            before=deepcopy(s.__dict__)
            with self.assertRaises(WorkflowError):s.commit(p)
            self.assertEqual(s.__dict__,before)

    def test_every_marker_including_null_refuses_after_snapshot(self):
        p=fixture()
        for marker in MARKERS:
            for value in (None,False,{},"unsupported",2):
                with self.subTest(marker=marker,value=value):
                    s=SimulatedStore(p);key=p.before[-1].key
                    s.rows[(key.pk,key.sk)][marker]=value
                    before=deepcopy(s.__dict__)
                    with self.assertRaises(WorkflowError):s.commit(p)
                    self.assertEqual(s.__dict__,before)

    def test_marked_initial_snapshot_never_builds(self):
        p=fixture()
        for marker in MARKERS:
            r=p.before[-1]
            with self.assertRaises(WorkflowError):
                record(r.key,r.incarnation,r.revision,**(r.data()|{marker:None}))

    def test_wrong_tenant_client_request_and_child(self):
        p=fixture()
        variants=[replace(p.operation,tenant="tenant_b"),replace(p.operation,client_id="client-b"),replace(p.operation,request_id="request-b")]
        for op in variants:
            with self.assertRaises(WorkflowError):build_plan(op,p.before,p.after,p.effects)
        row=p.after[-1]
        for delta in ({"request_id":"request-b"},{"client_id":"client-b"},{"company_id":"tenant_b"}):
            with self.assertRaises(WorkflowError):
                build_plan(p.operation,p.before,p.after[:-1]+(change(row,**delta),),p.effects)

    def test_parent_membership_rejects_wrong_type_duplicates_and_wrong_child(self):
        p=fixture()
        for value in (None,"job-0",{},["job-0","job-0"],["job-missing"],[True]):
            row=replace(p.after[0],body=canonical(p.after[0].data()|{"job_ids":value}))
            with self.assertRaises(WorkflowError):build_plan(p.operation,p.before,(row,)+p.after[1:],p.effects)

    def test_missing_parent_child_or_pet_is_not_complete_set(self):
        p=fixture()
        for index in range(len(p.after)):
            with self.assertRaises(WorkflowError):build_plan(p.operation,p.before,p.after[:index]+p.after[index+1:],p.effects)

    def test_parent_cas_serializes_sibling_updates(self):
        p=fixture();s=SimulatedStore(p);q=fixture(op_id="op-b")
        s.commit(p);before=deepcopy(s.__dict__)
        with self.assertRaises(WorkflowError):s.commit(q)
        self.assertEqual(s.__dict__,before)

    def test_assignment_then_cancellation_stale_snapshot_refuses(self):
        p=fixture();q=fixture(action="CANCEL",op_id="cancel-a");s=SimulatedStore(p)
        s.commit(p);before=deepcopy(s.__dict__)
        with self.assertRaises(WorkflowError):s.commit(q)
        self.assertEqual(s.__dict__,before)

    def test_cancel_then_assignment_stale_snapshot_refuses(self):
        p=fixture();q=fixture(action="CANCEL",op_id="cancel-a");s=SimulatedStore(p)
        s.commit(q)
        with self.assertRaises(WorkflowError):s.commit(p)
        self.assertEqual(s.receipts,{(q.operation.tenant,q.operation.operation_id):q.binding})

    def test_review_then_assignment_race_refuses(self):
        p=fixture();review=build_plan(replace(p.operation,operation_id="review-a",action="REVIEW"),p.before,p.after,p.effects)
        s=SimulatedStore(p);s.commit(review)
        with self.assertRaises(WorkflowError):s.commit(p)

    def test_fresh_cancellation_preserves_completed_child(self):
        p=fixture();before=p.before[:-1]+(replace(p.before[-1],body=canonical(p.before[-1].data()|{"status":"COMPLETED"})),)
        after=tuple(change(r,status="CANCELLED") if r.key.pk.startswith(("REQ#","JOB#")) and r.data().get("status")!="COMPLETED" else r for r in before)
        q=build_plan(replace(p.operation,action="CANCEL"),before,after,())
        s=SimulatedStore(q);s.commit(q)
        self.assertEqual(s.rows[(before[-1].key.pk,before[-1].key.sk)]["status"],"COMPLETED")

    def test_cancel_partial_children_is_refused(self):
        p=fixture(action="CANCEL")
        with self.assertRaises(WorkflowError):build_plan(p.operation,p.before,p.after[:-1]+(p.before[-1],),())

    def test_parent_completion_requires_all_children_complete(self):
        p=fixture();parent=change(p.before[0],status="COMPLETED")
        with self.assertRaises(WorkflowError):build_plan(replace(p.operation,action="REVIEW"),p.before,(parent,)+p.before[1:],())

    def test_pet_and_child_creation_commit_with_parent_references(self):
        p=fixture(1);parent=change(p.before[0],job_ids=["job-0","job-new"],pet_ids=["pet-a","pet-new"])
        pet=record(Key("tenant_a","PET#pet-new","CLIENT#client-a"),"life-pet-new",1,company_id="tenant_a",client_id="client-a",pet_id="pet-new")
        job=record(Key("tenant_a","JOB#job-new","REQ#request-a"),"life-job-new",1,company_id="tenant_a",client_id="client-a",request_id="request-a",status="JOB_CREATED",pet_ids=["pet-new"])
        q=build_plan(replace(p.operation,action="CREATE_JOBS"),p.before,(parent,)+p.before[1:]+(pet,job),())
        s=SimulatedStore(q);s.commit(q)
        self.assertIn((job.key.pk,job.key.sk),s.rows)
        self.assertEqual(s.rows[(parent.key.pk,parent.key.sk)]["pet_ids"],["pet-a","pet-new"])

    def test_failed_new_pet_commit_leaves_no_new_pet_or_reference(self):
        p=fixture(1);pet=record(Key("tenant_a","PET#pet-new","CLIENT#client-a"),"life-new",1,company_id="tenant_a",client_id="client-a",pet_id="pet-new")
        parent=change(p.before[0],pet_ids=["pet-a","pet-new"])
        q=build_plan(replace(p.operation,action="LINK_PETS"),p.before,(parent,)+p.before[1:]+(pet,),())
        s=SimulatedStore(q);before=deepcopy(s.__dict__)
        with self.assertRaises(WorkflowError):s.commit(q,conflict=True)
        self.assertEqual(s.__dict__,before)

    def test_pet_client_or_membership_mismatch_refuses(self):
        p=fixture();pet=p.after[1]
        for delta in ({"client_id":"client-b"},{"pet_id":"pet-b"}):
            with self.assertRaises(WorkflowError):build_plan(p.operation,p.before,(p.after[0],change(pet,**delta))+p.after[2:],())
        job=p.after[-1]
        with self.assertRaises(WorkflowError):build_plan(p.operation,p.before,p.after[:-1]+(change(job,pet_ids=["pet-missing"]),),())

    def test_lifetime_retirement_blocks_identical_delete_recreate_aba(self):
        p=fixture();s=SimulatedStore(p);r=p.before[-1];key=(r.key.pk,r.key.sk)
        del s.rows[key]
        s.rows[("LIFETIME#"+r.key.token(),"PERMANENT")]["retired"]=True
        s.rows[key]=r.item()  # Even byte-identical recreation cannot revive lifetime.
        with self.assertRaises(WorkflowError):s.commit(p)

    def test_missing_lifetime_or_new_incarnation_refuses(self):
        p=fixture()
        for mode in ("missing","changed","ttl","expires_at"):
            s=SimulatedStore(p);r=p.before[-1];k=("LIFETIME#"+r.key.token(),"PERMANENT")
            if mode=="missing":del s.rows[k]
            elif mode=="changed":s.rows[k]["incarnation"]="life-other"
            else:s.rows[k][mode]=123
            with self.assertRaises(WorkflowError):s.commit(p)

    def test_old_revision_and_boolean_revision_refuse(self):
        p=fixture();r=p.after[-1]
        for rev in (True,1,0,-1,1.0,2**63):
            with self.assertRaises(WorkflowError):build_plan(p.operation,p.before,p.after[:-1]+(replace(r,revision=rev),),())

    def test_incarnation_change_cannot_be_ordinary_update(self):
        p=fixture()
        with self.assertRaises(WorkflowError):build_plan(p.operation,p.before,p.after[:-1]+(replace(p.after[-1],incarnation="replacement"),),())

    def test_hard_delete_requires_separate_policy(self):
        p=fixture();parent=change(p.before[0],job_ids=["job-0"])
        with self.assertRaisesRegex(WorkflowError,"HARD_DELETE_POLICY_PENDING"):
            build_plan(p.operation,p.before,(parent,)+p.before[1:-1],())

    def test_replay_uses_durable_binding_not_provider_token_window(self):
        p=fixture();s=SimulatedStore(p);s.commit(p);before=deepcopy(s.__dict__)
        self.assertEqual(s.commit(p),"REPLAY_PERSISTED");self.assertEqual(s.__dict__,before)

    def test_same_operation_changed_payload_refuses(self):
        p=fixture();s=SimulatedStore(p);s.commit(p)
        q=build_plan(p.operation,p.before,p.after,(replace(p.effects[0],payload=canonical({"different":True})),))
        with self.assertRaisesRegex(WorkflowError,"REPLAY_MISMATCH"):s.commit(q)

    def test_forged_plan_digest_cannot_replay(self):
        p=fixture();s=SimulatedStore(p);s.commit(p)
        with self.assertRaisesRegex(WorkflowError,"PLAN_BINDING"):s.commit(replace(p,binding="0"*64))

    def test_interruption_before_dispatch_leaves_pending(self):
        p=fixture();s=SimulatedStore(p);s.commit(p);provider=MockProvider()
        self.assertEqual(provider.calls,[]);deliver(s,provider,p,"calendar-a")
        self.assertEqual(len(provider.calls),1)

    def test_interruption_after_claim_requires_reconciliation(self):
        p=fixture();s=SimulatedStore(p);s.commit(p);provider=MockProvider()
        deliver(s,provider,p,"calendar-a",interrupt=True)
        with self.assertRaises(WorkflowError):deliver(s,provider,p,"calendar-a")
        self.assertEqual(provider.calls,[])

    def test_ambiguous_calendar_and_notification_never_blindly_retry(self):
        for effect in ("calendar-a","notification-a"):
            p=fixture();s=SimulatedStore(p);s.commit(p);provider=MockProvider()
            deliver(s,provider,p,effect,ambiguous=True)
            with self.assertRaises(WorkflowError):deliver(s,provider,p,effect)
            self.assertEqual(len(provider.calls),1)
            intent=s.intents[(p.operation.tenant,p.operation.operation_id,effect)]
            done=s.reconcile(p,effect,evidence(intent))
            self.assertEqual(done.state,"DONE")
            with self.assertRaises(WorkflowError):deliver(s,provider,p,effect)
            self.assertEqual(len(provider.calls),1)

    def test_authoritative_absence_allows_new_claim_without_duplicate_effect(self):
        p=fixture();s=SimulatedStore(p);s.commit(p);provider=MockProvider()
        deliver(s,provider,p,"calendar-a",interrupt=True)
        key=(p.operation.tenant,p.operation.operation_id,"calendar-a");i=s.intents[key]
        s.reconcile(p,"calendar-a",evidence(i,outcome="NOT_APPLIED"))
        deliver(s,provider,p,"calendar-a")
        self.assertEqual(len(provider.calls),1)

    def test_unverified_wrong_or_stale_evidence_changes_nothing(self):
        p=fixture();s=SimulatedStore(p);s.commit(p);i=s.claim(p,"calendar-a")
        for delta in ({"verified":False},{"verified":"true"},{"current":False},{"tenant":"tenant_b"},
                      {"operation_id":"op-other"},{"effect_id":"notification-a"},{"binding":"0"*64},
                      {"claim_id":"old-attempt"},{"outcome":"UNKNOWN"}):
            before=deepcopy(s.__dict__)
            with self.assertRaises(WorkflowError):s.reconcile(p,"calendar-a",evidence(i,**delta))
            self.assertEqual(s.__dict__,before)
        with self.assertRaises(WorkflowError):reconcile(i,p,"calendar-a",i.revision-1,evidence(i))

    def test_stale_claim_ack_and_wrong_effect_cannot_complete(self):
        p=fixture();i=Intent(p.operation.tenant,p.operation.operation_id,"calendar-a",p.binding)
        i=claim(i,p,"calendar-a",1,"attempt-a")
        for effect,rev,attempt in (("notification-a",2,"attempt-a"),("calendar-a",1,"attempt-a"),("calendar-a",2,"attempt-b")):
            with self.assertRaises(WorkflowError):report(i,p,effect,rev,attempt,"APPLIED")

    def test_superseding_cancel_prevents_old_effect_claim(self):
        p=fixture();s=SimulatedStore(p);s.commit(p)
        after=tuple(change(r,status="CANCELLED") if r.key.pk.startswith(("JOB#","REQ#")) else r for r in p.after)
        q=build_plan(replace(p.operation,operation_id="cancel-new",action="CANCEL"),p.after,after,())
        s.commit(q)
        with self.assertRaisesRegex(WorkflowError,"STALE_AGGREGATE"):s.claim(p,"calendar-a")

    def test_effect_failure_never_rolls_back_committed_records(self):
        p=fixture();s=SimulatedStore(p);s.commit(p);rows=deepcopy(s.rows);provider=MockProvider()
        deliver(s,provider,p,"calendar-a",ambiguous=True)
        for r in p.after:self.assertEqual(s.rows[(r.key.pk,r.key.sk)],rows[(r.key.pk,r.key.sk)])
        self.assertEqual(s.receipts[(p.operation.tenant,p.operation.operation_id)],p.binding)

    def test_oversized_booking_refused_without_chunking(self):
        p=fixture(33)
        with self.assertRaisesRegex(WorkflowError,"OVERSIZED_REFUSED"):transaction(p,"offline-workflows")

    def test_oversized_record_and_receipt_refused(self):
        p=fixture();r=change(p.before[-1],notes="x"*200000)
        q=build_plan(p.operation,p.before,p.after[:-1]+(r,),())
        with self.assertRaises(WorkflowError):transaction(q,"offline-workflows")

    def test_offline_botocore_shape_and_distinct_targets(self):
        p=fixture();request=transaction(p,"offline-workflows")
        model=Session().get_service_model("dynamodb").operation_model("TransactWriteItems")
        validate_parameters(request,model.input_shape)
        keys=[]
        for action in request["TransactItems"]:
            spec=next(iter(action.values()));k=spec.get("Key",spec.get("Item"))
            keys.append((k["PK"]["S"],k["SK"]["S"]))
        self.assertEqual(len(keys),len(set(keys)))

    def test_effect_target_and_duplicate_ids_are_bound(self):
        p=fixture()
        for effects in ((p.effects[0],p.effects[0]),(replace(p.effects[0],target=Key("tenant_b","JOB#job-0","REQ#request-a")),)):
            with self.assertRaises(WorkflowError):build_plan(p.operation,p.before,p.after,effects)

    def test_reassignment_after_start_is_pending_not_permission(self):
        p=fixture();old=replace(p.before[-1],body=canonical(p.before[-1].data()|{"started_at":"synthetic-start"}))
        new=change(old,status="ASSIGNED",worker_id="different-worker")
        with self.assertRaisesRegex(WorkflowError,"POLICY_PENDING"):build_plan(p.operation,p.before[:-1]+(old,),p.after[:-1]+(new,),())

    def test_legacy_unversioned_records_need_adapter_and_no_runtime_change(self):
        p=fixture();legacy=p.before[0].data();copy=deepcopy(legacy)
        with self.assertRaises(WorkflowError):Record(p.before[0].key,"",0,canonical(legacy)).data()
        self.assertEqual(legacy,copy)
        self.assertIn("API_COMPATIBILITY_PENDING",p.blockers)

    def test_legacy_partial_success_is_not_mislabeled_atomic_success(self):
        # Historical missing-child success needs an explicit future API decision.
        p=fixture();partial=p.after[:-1]
        with self.assertRaisesRegex(WorkflowError,"INCOMPLETE_MEMBERSHIP"):
            build_plan(p.operation,p.before,partial,p.effects)

    def test_no_sdk_or_runtime_import_and_no_network(self):
        root=Path(__file__).resolve().parents[2]
        path=root/"src/backend/common/atomic_workflow_contract.py"
        tree=ast.parse(path.read_text(encoding="utf-8"))
        allowed={"dataclasses","hashlib","json","re"}
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):self.assertTrue(all(n.name in allowed for n in node.names))
            if isinstance(node,ast.ImportFrom):self.assertIn(node.module,allowed)
        for source in (root/"src/backend").rglob("*.py"):
            if source!=path:self.assertNotIn("atomic_workflow_contract",source.read_text(encoding="utf-8"))
        with patch.object(socket.socket,"connect",side_effect=AssertionError("NETWORK_FORBIDDEN")):
            p=fixture();s=SimulatedStore(p);s.commit(p);deliver(s,MockProvider(),p,"calendar-a")


    def test_claim_expression_rechecks_lifetime_and_outbox_cas(self):
        p=fixture()
        for mode in ("lifetime","outbox","marker","reservation"):
            s=SimulatedStore(p);s.commit(p);r=p.after[-1]
            if mode=="lifetime":s.rows[("LIFETIME#"+r.key.token(),"PERMANENT")]["retired"]=True
            elif mode=="outbox":s.rows[("OP#tenant_a#op-a","EFFECT#calendar-a")]["revision"]=2
            elif mode=="marker":s.rows[(r.key.pk,r.key.sk)]["assigned_worker_id"]=None
            else:s.rows[("RESERVATION#"+r.key.token(),"PERMANENT")]={"PK":"RESERVATION#"+r.key.token(),"SK":"PERMANENT"}
            before=deepcopy(s.__dict__)
            with self.assertRaises(WorkflowError):s.claim(p,"calendar-a")
            self.assertEqual(s.__dict__,before)

    def test_claim_report_reconcile_request_shapes_and_evidence_guards(self):
        p=fixture();i=Intent("tenant_a","op-a","calendar-a",p.binding)
        model=Session().get_service_model("dynamodb").operation_model("TransactWriteItems")
        validate_parameters(effect_update_request(p,i,1,"offline-workflows","CLAIM","attempt-a"),model.input_shape)
        i=claim(i,p,"calendar-a",1,"attempt-a")
        validate_parameters(effect_update_request(p,i,2,"offline-workflows","REPORT",("attempt-a","UNKNOWN")),model.input_shape)
        validate_parameters(effect_update_request(p,i,2,"offline-workflows","RECONCILE",evidence(i)),model.input_shape)
        with self.assertRaises(WorkflowError):effect_update_request(p,i,2,"offline-workflows","RECONCILE",evidence(i,verified=False))


    def test_unfenced_identical_restore_is_explicit_rollout_blocker(self):
        # No condition can distinguish byte-identical storage rollback when an old
        # writer bypasses permanent lifetime retirement. This is NOT ABA closure.
        p=fixture();s=SimulatedStore(p);r=p.before[-1];k=(r.key.pk,r.key.sk)
        del s.rows[k];s.rows[k]=r.item()
        self.assertEqual(s.commit(p),"PERSISTED_EFFECTS_PENDING")
        self.assertIn("ALL_WRITERS_PENDING",p.blockers)

    def test_unversioned_new_unknown_field_is_explicit_adapter_blocker(self):
        # Full-field equality catches changed observed fields, not arbitrary new
        # attributes from writers that ignore the future revision protocol.
        p=fixture();s=SimulatedStore(p);r=p.before[-1];k=(r.key.pk,r.key.sk)
        s.rows[k]["unversioned_addition"]="synthetic"
        s.commit(p)
        self.assertNotIn("unversioned_addition",s.rows[k])
        self.assertIn("ALL_WRITERS_PENDING",p.blockers)


    def test_expression_and_nesting_budgets_fail_closed(self):
        p=fixture();r=p.before[-1]
        big=record(r.key,r.incarnation,1,**(r.data()|{"field"+str(i):i for i in range(300)}))
        before=p.before[:-1]+(big,);after=p.after[:-1]+(change(big,status="ASSIGNED"),)
        q=build_plan(p.operation,before,after,())
        with self.assertRaisesRegex(WorkflowError,"EXPRESSION_BUDGET_REFUSED"):transaction(q,"offline-workflows")
        nested={}
        for _ in range(18):nested={"next":nested}
        with self.assertRaisesRegex(WorkflowError,"NESTING_BUDGET_REFUSED"):canonical(nested)

    def test_rollback_is_new_conditional_operation_not_effect_compensation(self):
        p=fixture();s=SimulatedStore(p);s.commit(p);provider=MockProvider();deliver(s,provider,p,"notification-a")
        rollback=tuple(record(old.key,old.incarnation,current.revision+1,**old.data()) if old!=current else current
                       for old,current in zip(p.before,p.after))
        q=build_plan(replace(p.operation,operation_id="rollback-a",action="ROLLBACK_STATUS"),p.after,rollback,())
        s.commit(q)
        self.assertEqual(len(provider.calls),1)
        self.assertEqual(s.intents[("tenant_a","op-a","notification-a")].state,"DONE")
        self.assertEqual(len(s.receipts),2)


    def test_malformed_persisted_intent_cannot_reconcile_or_claim(self):
        p=fixture();i=claim(Intent("tenant_a","op-a","calendar-a",p.binding),p,"calendar-a",1,"attempt-a")
        for field,value in (("claim_id",True),("claim_id",0),("claim_id",""),("state","UNSUPPORTED"),("revision",True)):
            bad=replace(i,**{field:value})
            with self.assertRaises(WorkflowError):reconcile(bad,p,"calendar-a",bad.revision,evidence(bad))
