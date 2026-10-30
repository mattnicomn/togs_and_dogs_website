"""Synthetic conditions and real in-memory UpdateExpression evaluation; no clients."""
import ast
import json
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import socket
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src/backend"))
from boto3.dynamodb.types import TypeSerializer, TypeDeserializer
from botocore.session import Session
from botocore.validate import validate_parameters
from moto.dynamodb.models import Item, DynamoType
from moto.dynamodb.parsing.expressions import UpdateExpressionParser
from moto.dynamodb.parsing.validators import UpdateExpressionValidator
from moto.dynamodb.parsing.executors import UpdateExpressionExecutor
from test_worker_identity_expression_behavior import evaluates
from common.cancellation_submission_contract import (
    SubmissionError, Submission, BookingAccess, StatusAssumption, Receipt, Plan, MARKERS, STATUSES,
    CurrentBookingEvidence, StoredReceiptEvidence, RefusalEvidence, encoded, digest, revision,
    parse_snapshot, source_status_matrix, prepare, replay, warning, transaction, persistence_outcome, operator_recovery,
)

NOW=datetime(2026,10,30,12,tzinfo=timezone.utc)


def fixture(status="ASSIGNED", role="client"):
    sub=Submission("tenant_a","client-a","request-a","https://issuer.example.invalid","actor-a","operation-a","synthetic reason")
    item={**sub.key(),"company_id":sub.tenant,"client_id":sub.client_id,"request_id":sub.request_id,
          "record_incarnation":"lifetime-a","legacy_write_revision":1,"status":status,"start_date":"2026-10-31",
          "client_email":"opaque-booking-binding","audit_log":[{"action":"EXISTING"}],"unrelated":{"preserve":[1,2]}}
    snap=parse_snapshot(item,sub)
    access=BookingAccess(sub.tenant,sub.client_id,sub.request_id,sub.issuer,sub.actor,role,snap.incarnation,snap.revision,
                         (("client_email","opaque-booking-binding"),),True,True,True,True)
    assumption=StatusAssumption(status,True,"SYNTHETIC_ONLY","synthetic-test-scenario")
    return sub,item,access,snap,assumption


def plan_fixture(**kwargs):
    sub,item,access,snap,assumption=fixture(**kwargs)
    return prepare(sub,access,snap,NOW,assumption),item


def updated(spec, original):
    serializer=TypeSerializer();data={k:serializer.serialize(v) for k,v in original.items()}
    item=Item(DynamoType(data["PK"]),DynamoType(data["SK"]),data)
    schema=SimpleNamespace(table_key_attrs=["PK","SK"],attr=[{"AttributeName":"PK","AttributeType":"S"},{"AttributeName":"SK","AttributeType":"S"}],attribute_keys=["PK","SK"])
    parsed=UpdateExpressionParser.make(spec["UpdateExpression"])
    validated=UpdateExpressionValidator(parsed,spec["ExpressionAttributeNames"],spec["ExpressionAttributeValues"],item,schema).validate()
    UpdateExpressionExecutor(validated,item,spec["ExpressionAttributeNames"]).execute()
    return {k:TypeDeserializer().deserialize(v.to_regular_json()) for k,v in item.attrs.items()}


class MemoryStore:
    def __init__(self,plan,item):
        sub=plan.submission
        self.rows={(item["PK"],item["SK"]):deepcopy(item),
            ("LIFETIME#"+sub.token(),"PERMANENT"):{"PK":"LIFETIME#"+sub.token(),"SK":"PERMANENT","incarnation":plan.snapshot.incarnation,"retired":False},
            ("JOB#unrelated","REQ#unrelated"):{"PK":"JOB#unrelated","SK":"REQ#unrelated","status":"ASSIGNED"},
            ("PET#unrelated","CLIENT#unrelated"):{"PK":"PET#unrelated","SK":"CLIENT#unrelated"}}

    def current(self,sub):return parse_snapshot(self.rows[(sub.key()["PK"],sub.key()["SK"])],sub)

    def current_evidence(self,sub):
        item=self.rows[(sub.key()["PK"],sub.key()["SK"])]
        snapshot=self.current(sub)
        fields=tuple((k,item[k]) for k in ("client_email","linked_client_profile_id","cognito_sub") if k in item)
        read_id="read-"+digest([snapshot.__dict__,fields])[:32]
        return CurrentBookingEvidence(snapshot,fields,read_id,True,True,True)

    def current_access(self,plan):
        evidence=self.current_evidence(plan.submission)
        # This fake refreshes observation identity, NOT the actor's booking binding.
        # Changed persisted identity must therefore be refused by the core guard.
        return replace(plan.access,revision=evidence.snapshot.revision,incarnation=evidence.snapshot.incarnation,read_id=evidence.read_id)

    def receipt(self,sub):
        item=self.rows.get(("CANCEL_SUBMISSION#"+sub.tenant+"#"+sub.operation,"RECEIPT"))
        return None if item is None else Receipt(**{k:item[k] for k in Receipt.__dataclass_fields__})

    def operation_evidence(self,sub):
        item=deepcopy(self.rows.get(("CANCEL_SUBMISSION#"+sub.tenant+"#"+sub.operation,"RECEIPT")))
        if item is None:return None
        # Trusted test adapter observes only published rows, never Plan.receipt.
        # Real DB-boundary normalization must be strict, not bool/float coercion.
        for field in ("source_revision","committed_revision"):
            item[field]=revision(item[field])
        return StoredReceiptEvidence(encoded(item),self.current_evidence(sub).read_id,True,True,True)

    def lifetime(self,sub):return self.rows.get(("LIFETIME#"+sub.token(),"PERMANENT"))

    def submit(self,plan,access=None,conflict=False,timeout=None,receipt_race=False):
        sub=plan.submission
        receipt=self.receipt(sub)
        if receipt is not None:return replay(sub,access or plan.access,self.current_evidence(sub),self.operation_evidence(sub),self.lifetime(sub))
        request=transaction(plan,"offline-submissions")
        if timeout=="before":raise TimeoutError("UNKNOWN")
        if receipt_race:
            spec=request["TransactItems"][-1]["Put"]
            self.rows[(spec["Item"]["PK"]["S"],"RECEIPT")]={k:TypeDeserializer().deserialize(v) for k,v in spec["Item"].items()}
        proposed=deepcopy(self.rows)
        for entry in request["TransactItems"]:
            kind,spec=next(iter(entry.items()));raw=spec.get("Key",spec.get("Item"));key=(raw["PK"]["S"],raw["SK"]["S"])
            if conflict or not evaluates(spec,self.rows.get(key)):raise SubmissionError("CONDITIONAL_REFUSAL")
            if kind=="Update":proposed[key]=updated(spec,proposed[key])
            elif kind=="Put":proposed[key]={k:TypeDeserializer().deserialize(v) for k,v in spec["Item"].items()}
        self.rows=proposed
        if timeout=="after":raise TimeoutError("UNKNOWN")
        return plan.receipt.response()


class CancellationSubmissionTests(unittest.TestCase):
    def test_authorized_submit_preserves_success_shape(self):
        p,item=plan_fixture();s=MemoryStore(p,item)
        self.assertEqual(s.submit(p),{"message":"Cancellation request submitted for review.","urgent_warning":True})
        current=s.rows[(item["PK"],item["SK"])]
        self.assertEqual(current["status"],"CANCELLATION_REQUESTED")
        self.assertEqual(current["cancellation_requested_by"],"CLIENT#client-a")
        self.assertEqual(current["cancellation_reason"],p.submission.reason)
        self.assertEqual(current["legacy_write_revision"],2)

    def test_false_trust_access_flags_never_prepare(self):
        sub,item,access,snap,policy=fixture()
        for field in ("verified","current","tenant_active","booking_allowed"):
            for value in (False,"true",1,None):
                with self.assertRaises(SubmissionError):prepare(sub,replace(access,**{field:value}),snap,NOW,policy)

    def test_no_access_context_or_client_json_authority(self):
        sub,item,access,snap,policy=fixture()
        for value in (None,access.__dict__,True):
            with self.assertRaises(SubmissionError):prepare(sub,value,snap,NOW,policy)

    def test_exact_actor_issuer_tenant_client_request_binding(self):
        sub,item,access,snap,policy=fixture()
        for field,value in (("actor","actor-b"),("issuer","https://other.example.invalid"),("tenant","tenant_b"),("client_id","client-b"),("request_id","request-b")):
            with self.assertRaises(SubmissionError):prepare(sub,replace(access,**{field:value}),snap,NOW,policy)

    def test_unknown_role_denied_and_existing_privileged_roles_are_modeled_only(self):
        for role in ("client","owner","admin","staff"):
            p,item=plan_fixture(role=role);self.assertIn("INACTIVE_NO_RUNTIME",p.blockers)
        sub,item,access,snap,policy=fixture()
        for role in (None,"unknown","platform_admin",True):
            with self.assertRaises(SubmissionError):prepare(sub,replace(access,role=role),snap,NOW,policy)

    def test_client_requires_concrete_persisted_access_fence(self):
        sub,item,access,snap,policy=fixture()
        for bindings in ((),(("display_name","same-name"),),(("client_email",True),),(("client_email","a"),("client_email","b"))):
            with self.assertRaises(SubmissionError):prepare(sub,replace(access,bindings=bindings),snap,NOW,policy)

    def test_changed_booking_identity_after_access_refuses_commit(self):
        p,item=plan_fixture();s=MemoryStore(p,item);s.rows[(item["PK"],item["SK"])]["client_email"]="different-binding"
        before=deepcopy(s.rows)
        with self.assertRaises(SubmissionError):s.submit(p)
        self.assertEqual(s.rows,before)

    def test_every_status_is_pending_without_explicit_synthetic_assumption(self):
        for status in STATUSES:
            sub,item,access,snap,policy=fixture(status)
            with self.assertRaisesRegex(SubmissionError,"POLICY_PENDING"):prepare(sub,access,snap,NOW)
            self.assertIn("PENDING",source_status_matrix(status))

    def test_allowed_assumption_and_denied_assumption(self):
        sub,item,access,snap,policy=fixture()
        self.assertIn("SOURCE_STATUS_POLICY_PENDING",prepare(sub,access,snap,NOW,policy).blockers)
        for change in ({"permitted":False},{"permitted":"true"},{"mode":"RUNTIME"},{"source_status":"COMPLETED"},{"reference":""}):
            with self.assertRaises(SubmissionError):prepare(sub,access,snap,NOW,replace(policy,**change))

    def test_pending_submission_cannot_be_new_operation_by_default(self):
        for status in ("CANCELLATION_REQUESTED","UNKNOWN_STATUS"):
            sub,item,access,snap,policy=fixture(status)
            with self.assertRaisesRegex(SubmissionError,"POLICY_PENDING"):prepare(sub,access,snap,NOW,policy)

    def test_unsupported_issuer_and_reason_forms_refuse(self):
        sub,item,access,snap,policy=fixture()
        for issuer in ("http://issuer.invalid","https://u:p@issuer.invalid","https://[invalid"):
            with self.assertRaises(SubmissionError):replace(sub,issuer=issuer).validate()
        for reason in (None,1,[],{}):
            with self.assertRaises(SubmissionError):replace(sub,reason=reason).validate()

    def test_identical_replay_returns_original_result_and_one_audit(self):
        p,item=plan_fixture();s=MemoryStore(p,item);first=s.submit(p);before=deepcopy(s.rows)
        self.assertEqual(s.submit(p,access=s.current_access(p)),first)
        self.assertEqual(s.rows,before)
        self.assertEqual(len(s.rows[(item["PK"],item["SK"])]["audit_log"]),2)

    def test_changed_reason_or_actor_under_same_operation_is_conflict(self):
        p,item=plan_fixture();s=MemoryStore(p,item);s.submit(p)
        for delta in ({"reason":"changed"},{"actor":"actor-b"}):
            sub=replace(p.submission,**delta);access=replace(s.current_access(p),actor=sub.actor);before=deepcopy(s.rows)
            with self.assertRaises(SubmissionError):replay(sub,access,s.current_evidence(sub),s.operation_evidence(sub),s.lifetime(sub))
            self.assertEqual(s.rows,before)

    def test_replay_requires_fresh_access_and_same_lifetime(self):
        p,item=plan_fixture();s=MemoryStore(p,item);s.submit(p)
        with self.assertRaises(SubmissionError):s.submit(p)
        with self.assertRaises(SubmissionError):s.submit(p,access=replace(s.current_access(p),current=False))
        snap=replace(s.current(p.submission),incarnation="new-life")
        with self.assertRaises(SubmissionError):replay(p.submission,replace(s.current_access(p),incarnation="new-life"),replace(s.current_evidence(p.submission),snapshot=snap),s.operation_evidence(p.submission),s.lifetime(p.submission))

    def test_replay_after_admin_decision_does_not_reopen_request(self):
        p,item=plan_fixture();s=MemoryStore(p,item);response=s.submit(p)
        s.rows[(item["PK"],item["SK"])].update(status="CANCELLED",legacy_write_revision=3)
        before=deepcopy(s.rows);self.assertEqual(s.submit(p,access=s.current_access(p)),response);self.assertEqual(s.rows,before)

    def test_concurrent_different_operations_only_one_audit(self):
        p,item=plan_fixture();q=replace(p,submission=replace(p.submission,operation="operation-b"))
        q=prepare(q.submission,q.access,q.snapshot,NOW,q.assumption);s=MemoryStore(p,item);s.submit(p);before=deepcopy(s.rows)
        with self.assertRaises(SubmissionError):s.submit(q)
        self.assertEqual(s.rows,before)

    def test_competing_review_and_admin_cancel_refuse_without_partial_receipt(self):
        p,item=plan_fixture()
        for status in ("APPROVED","CANCELLED","COMPLETED","ARCHIVED"):
            s=MemoryStore(p,item);s.rows[(item["PK"],item["SK"])].update(status=status,legacy_write_revision=2)
            before=deepcopy(s.rows)
            with self.assertRaises(SubmissionError):s.submit(p)
            self.assertEqual(s.rows,before)

    def test_status_change_without_revision_is_still_fenced(self):
        p,item=plan_fixture();s=MemoryStore(p,item);s.rows[(item["PK"],item["SK"])]["status"]="CANCELLED"
        with self.assertRaises(SubmissionError):s.submit(p)

    def test_source_date_change_after_warning_refuses(self):
        p,item=plan_fixture();s=MemoryStore(p,item);s.rows[(item["PK"],item["SK"])]["start_date"]="2027-01-01"
        with self.assertRaises(SubmissionError):s.submit(p)

    def test_missing_record_stale_revision_and_incarnation_refuse(self):
        p,item=plan_fixture()
        for mode in ("missing","revision","incarnation","missing-revision"):
            s=MemoryStore(p,item);k=(item["PK"],item["SK"])
            if mode=="missing":del s.rows[k]
            elif mode=="revision":s.rows[k]["legacy_write_revision"]=2
            elif mode=="missing-revision":del s.rows[k]["legacy_write_revision"]
            else:s.rows[k]["record_incarnation"]="new-life"
            before=deepcopy(s.rows)
            with self.assertRaises(SubmissionError):s.submit(p)
            self.assertEqual(s.rows,before)

    def test_strict_db_decimal_revision_parser(self):
        sub,item,*_=fixture()
        self.assertEqual(parse_snapshot(item|{"legacy_write_revision":Decimal("1")},sub).revision,1)
        for bad in (True,False,0,-1,1.0,"1",Decimal("1.2"),Decimal("NaN"),Decimal("Infinity"),2**63):
            with self.assertRaises(SubmissionError):parse_snapshot(item|{"legacy_write_revision":bad},sub)

    def test_initial_and_racing_null_partial_markers_refuse(self):
        p,item=plan_fixture()
        for marker in MARKERS:
            for value in (None,False,{},"unsupported"):
                with self.assertRaises(SubmissionError):parse_snapshot(item|{marker:value},p.submission)
                s=MemoryStore(p,item);s.rows[(item["PK"],item["SK"])][marker]=value;before=deepcopy(s.rows)
                with self.assertRaises(SubmissionError):s.submit(p)
                self.assertEqual(s.rows,before)

    def test_reservation_inserted_after_snapshot_refuses(self):
        p,item=plan_fixture();s=MemoryStore(p,item);s.rows[("RESERVATION#"+p.submission.token(),"PERMANENT")]={"PK":"RESERVATION#"+p.submission.token(),"SK":"PERMANENT"};before=deepcopy(s.rows)
        with self.assertRaises(SubmissionError):s.submit(p)
        self.assertEqual(s.rows,before)

    def test_lifetime_absence_retirement_wrong_incarnation_and_ttl_refuse(self):
        p,item=plan_fixture()
        for mode in ("missing","retired","incarnation","ttl","expires_at"):
            s=MemoryStore(p,item);k=("LIFETIME#"+p.submission.token(),"PERMANENT")
            if mode=="missing":del s.rows[k]
            else:s.rows[k][mode]="wrong" if mode=="incarnation" else True
            before=deepcopy(s.rows)
            with self.assertRaises(SubmissionError):s.submit(p)
            self.assertEqual(s.rows,before)

    def test_retired_lifetime_blocks_identical_record_recreation(self):
        p,item=plan_fixture();s=MemoryStore(p,item);k=(item["PK"],item["SK"]);del s.rows[k]
        s.rows[("LIFETIME#"+p.submission.token(),"PERMANENT")]["retired"]=True;s.rows[k]=deepcopy(item)
        with self.assertRaises(SubmissionError):s.submit(p)

    def test_unversioned_legacy_record_is_unchanged_not_enrolled(self):
        sub,item,*_=fixture();legacy={k:v for k,v in item.items() if k not in {"record_incarnation","legacy_write_revision"}};before=deepcopy(legacy)
        with self.assertRaisesRegex(SubmissionError,"LEGACY_ADAPTER_PENDING"):parse_snapshot(legacy,sub)
        self.assertEqual(legacy,before)

    def test_unknown_fields_added_concurrently_are_preserved_by_real_expression(self):
        p,item=plan_fixture();s=MemoryStore(p,item);k=(item["PK"],item["SK"])
        s.rows[k]["new_unrelated_field"]={"nested":["keep",Decimal("1.5")]}
        s.rows[k]["unrelated"]={"updated":"concurrently"}
        s.submit(p)
        self.assertEqual(s.rows[k]["new_unrelated_field"],{"nested":["keep",Decimal("1.5")]})
        self.assertEqual(s.rows[k]["unrelated"],{"updated":"concurrently"})

    def test_audit_absent_list_and_malformed_forms(self):
        p,item=plan_fixture()
        for existing in ("absent",[],[{"old":"audit"}]):
            data=deepcopy(item)
            if existing=="absent":del data["audit_log"]
            else:data["audit_log"]=existing
            s=MemoryStore(p,data);s.submit(p);self.assertEqual(len(s.rows[(item["PK"],item["SK"])]["audit_log"]),1+(len(existing) if type(existing) is list else 0))
        for invalid in (None,"text",{},False):
            with self.assertRaises(SubmissionError):parse_snapshot(item|{"audit_log":invalid},p.submission)
            s=MemoryStore(p,item);s.rows[(item["PK"],item["SK"])]["audit_log"]=invalid
            with self.assertRaises(SubmissionError):s.submit(p)

    def test_audit_concurrent_append_is_preserved_and_own_entry_once(self):
        p,item=plan_fixture();s=MemoryStore(p,item);k=(item["PK"],item["SK"]);s.rows[k]["audit_log"].append({"action":"OTHER"});s.submit(p);s.submit(p,access=s.current_access(p))
        self.assertEqual(len(s.rows[k]["audit_log"]),3)
        self.assertEqual(sum(x.get("status")=="CANCELLATION_REQUESTED" for x in s.rows[k]["audit_log"]),1)

    def test_confirmed_conflict_changes_nothing(self):
        p,item=plan_fixture();s=MemoryStore(p,item);before=deepcopy(s.rows)
        with self.assertRaises(SubmissionError):s.submit(p,conflict=True)
        self.assertEqual(s.rows,before)
        self.assertEqual(persistence_outcome(p.submission,s.current_access(p),s.current_evidence(p.submission),confirmed_refusal=RefusalEvidence(p.submission.binding(),s.current_evidence(p.submission).read_id,True,True,True,True)),{"state":"REFUSED"})

    def test_timeout_before_commit_is_unknown_not_automatic_retry(self):
        p,item=plan_fixture();s=MemoryStore(p,item);before=deepcopy(s.rows)
        with self.assertRaises(TimeoutError):s.submit(p,timeout="before")
        self.assertEqual(s.rows,before)
        self.assertEqual(persistence_outcome(p.submission,s.current_access(p),s.current_evidence(p.submission)),{"state":"UNKNOWN_NO_BLIND_RETRY"})

    def test_timeout_after_commit_reconciles_receipt_once(self):
        p,item=plan_fixture();s=MemoryStore(p,item)
        with self.assertRaises(TimeoutError):s.submit(p,timeout="after")
        result=persistence_outcome(p.submission,s.current_access(p),s.current_evidence(p.submission),s.operation_evidence(p.submission),lifetime=s.lifetime(p.submission))
        self.assertEqual(result["state"],"REPLAY_CONFIRMED");self.assertEqual(result["response"],p.receipt.response())
        self.assertEqual(len(s.rows[(item["PK"],item["SK"])]["audit_log"]),2)

    def test_receipt_and_refusal_cannot_both_be_claimed(self):
        p,item=plan_fixture();s=MemoryStore(p,item);s.submit(p)
        with self.assertRaises(SubmissionError):persistence_outcome(p.submission,s.current_access(p),s.current_evidence(p.submission),s.operation_evidence(p.submission),True)

    def test_date_only_midnight_utc_and_exact_24_hours(self):
        self.assertTrue(warning("2026-10-31",NOW))
        self.assertFalse(warning("2026-10-31T12:00:00Z",NOW))
        self.assertTrue(warning("2026-10-31T11:59:59Z",NOW))
        self.assertFalse(warning("2026-11-01",NOW))

    def test_offset_and_past_dates_preserve_backend_warning_intent(self):
        self.assertFalse(warning("2026-10-31T14:00:00+02:00",NOW))
        self.assertTrue(warning("2026-10-29",NOW))

    def test_missing_invalid_and_naive_dates_are_explicit(self):
        for value in (None,"","invalid","2026-02-31"):self.assertFalse(warning(value,NOW))
        with self.assertRaisesRegex(SubmissionError,"NAIVE_TIMESTAMP_POLICY_PENDING"):warning("2026-10-31T01:00:00",NOW)
        with self.assertRaises(SubmissionError):warning("2026-10-31",NOW.replace(tzinfo=None))

    def test_receipt_replay_does_not_recompute_warning_or_timestamp(self):
        p,item=plan_fixture();s=MemoryStore(p,item);s.submit(p)
        self.assertEqual(s.receipt(p.submission).submitted_at,p.receipt.submitted_at)
        self.assertEqual(s.submit(p,access=s.current_access(p)),p.receipt.response())

    def test_missing_vs_null_start_date_are_both_fenced(self):
        sub,item,access,_,policy=fixture()
        for mode in ("absent","null"):
            data=deepcopy(item)
            if mode=="absent":del data["start_date"]
            else:data["start_date"]=None
            p=prepare(sub,access,parse_snapshot(data,sub),NOW,policy);s=MemoryStore(p,data)
            s.rows[(item["PK"],item["SK"])]["start_date"]="2026-11-01"
            with self.assertRaises(SubmissionError):s.submit(p)

    def test_empty_reason_and_default_reason_keep_existing_intent(self):
        p,item=plan_fixture()
        for sub in (replace(p.submission,reason=""),Submission("tenant_a","client-a","request-a",p.submission.issuer,"actor-a","operation-a")):
            q=prepare(sub,p.access,p.snapshot,NOW,p.assumption);s=MemoryStore(q,item);s.submit(q)
            self.assertEqual(s.rows[(item["PK"],item["SK"])]["cancellation_reason"],sub.reason)

    def test_wrong_item_keys_or_identity_fields_refuse_parse_and_commit(self):
        p,item=plan_fixture()
        for field,value in (("PK","REQ#other"),("SK","CLIENT#other"),("company_id","tenant_b"),("client_id","other"),("request_id","other")):
            with self.assertRaises(SubmissionError):parse_snapshot(item|{field:value},p.submission)
            if field not in {"PK","SK"}:
                s=MemoryStore(p,item);s.rows[(item["PK"],item["SK"])][field]=value
                with self.assertRaises(SubmissionError):s.submit(p)

    def test_reservation_namespace_matches_pr50(self):
        from common.atomic_workflow_contract import Key
        p,item=plan_fixture();self.assertEqual(p.submission.token(),Key("tenant_a","REQ#request-a","CLIENT#client-a").token())

    def test_offline_shape_has_one_request_update_and_receipt_no_replacement(self):
        p,item=plan_fixture();request=transaction(p,"offline-submissions")
        model=Session().get_service_model("dynamodb").operation_model("TransactWriteItems");validate_parameters(request,model.input_shape)
        self.assertEqual([next(iter(a)) for a in request["TransactItems"]],["Update","ConditionCheck","ConditionCheck","Put"])
        keys=[]
        for a in request["TransactItems"]:
            spec=next(iter(a.values()));k=spec.get("Key",spec.get("Item"));keys.append((k["PK"]["S"],k["SK"]["S"]))
        self.assertEqual(len(keys),len(set(keys)))

    def test_oversize_reason_refuses_before_any_state_change(self):
        p,item=plan_fixture();sub=replace(p.submission,reason="x"*200000);q=prepare(sub,p.access,p.snapshot,NOW,p.assumption);s=MemoryStore(q,item);before=deepcopy(s.rows)
        with self.assertRaisesRegex(SubmissionError,"OVERSIZE_REFUSED"):s.submit(q)
        self.assertEqual(s.rows,before)

    def test_tampered_plan_and_receipt_refuse(self):
        p,item=plan_fixture()
        for delta in ({"binding":"0"*64},{"actor":"other"},{"urgent_warning":"true"},{"submitted_at":"invalid"},{"source_revision":True}):
            bad=replace(p.receipt,**delta)
            with self.assertRaises(SubmissionError):transaction(replace(p,receipt=bad),"offline-submissions")

    def test_no_job_pet_or_external_mutations_and_no_network(self):
        p,item=plan_fixture();s=MemoryStore(p,item);others={k:deepcopy(v) for k,v in s.rows.items() if k[0].startswith(("JOB#","PET#"))}
        with patch.object(socket.socket,"connect",side_effect=AssertionError("NETWORK_FORBIDDEN")):s.submit(p)
        for k,v in others.items():self.assertEqual(s.rows[k],v)
        self.assertEqual(len(s.rows),5)

    def test_module_is_standard_library_and_unwired(self):
        root=Path(__file__).resolve().parents[2];source=root/"src/backend/common/cancellation_submission_contract.py"
        tree=ast.parse(source.read_text(encoding="utf-8"));allowed={"dataclasses","datetime","decimal","hashlib","json","re","urllib"}
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):self.assertTrue(all(v.name.split(".")[0] in allowed for v in n.names))
            if isinstance(n,ast.ImportFrom):self.assertIn(n.module.split(".")[0],allowed)
        for path in (root/"src/backend").rglob("*.py"):
            if path!=source:self.assertNotIn("cancellation_submission_contract",path.read_text(encoding="utf-8"))

    def test_operator_recovery_is_pending_for_every_role(self):
        for role in ("owner","admin","staff","client",None):
            with self.assertRaisesRegex(SubmissionError,"AUTHORIZATION_PENDING"):operator_recovery(role=role)


    def test_replay_rejects_missing_retired_expiring_or_wrong_lifetime(self):
        p,item=plan_fixture();s=MemoryStore(p,item);s.submit(p);context=s.current_access(p);snap=s.current_evidence(p.submission);receipt=s.operation_evidence(p.submission)
        live=s.lifetime(p.submission)
        for value in (None,live|{"retired":True},live|{"retired":0},live|{"ttl":None},live|{"incarnation":"other-life"},live|{"PK":"LIFETIME#wrong"}):
            with self.assertRaises(SubmissionError):replay(p.submission,context,snap,receipt,value)

    def test_commit_lifetime_numeric_false_is_not_boolean_false(self):
        p,item=plan_fixture();s=MemoryStore(p,item);s.lifetime(p.submission)["retired"]=0
        with self.assertRaises(SubmissionError):s.submit(p)

    def test_receipt_conflict_after_request_update_stays_atomic(self):
        p,item=plan_fixture();s=MemoryStore(p,item);key=(item["PK"],item["SK"]);before=deepcopy(s.rows[key])
        # Receipt is inserted by another simulated coordinator after initial lookup.
        # The Update is evaluated on a copy, then the final receipt Put refuses.
        with self.assertRaisesRegex(SubmissionError,"CONDITIONAL_REFUSAL"):
            s.submit(p,receipt_race=True)
        self.assertEqual(s.rows[key],before)
        self.assertEqual(len(s.rows[key]["audit_log"]),1)
        self.assertIsNotNone(s.receipt(p.submission))


class CorrectiveReplayEvidenceTests(unittest.TestCase):
    def committed(self):
        plan,item=plan_fixture();store=MemoryStore(plan,item);store.submit(plan)
        return plan,store

    def assert_refused(self,plan,store,booking=None,operation=None,access=None):
        before=deepcopy(store.rows)
        with self.assertRaises(SubmissionError):
            replay(plan.submission,access or store.current_access(plan),
                   booking if booking is not None else store.current_evidence(plan.submission),
                   operation if operation is not None else store.operation_evidence(plan.submission),
                   store.lifetime(plan.submission))
        self.assertEqual(store.rows,before)

    def tampered_operation(self,store,sub,**delta):
        evidence=store.operation_evidence(sub);item=json.loads(evidence.item_json);item.update(delta)
        if any(k in Receipt.__dataclass_fields__ for k in delta):
            item["receipt_digest"]=digest({k:item[k] for k in Receipt.__dataclass_fields__})
        return replace(evidence,item_json=encoded(item))

    def test_prepared_uncommitted_receipt_never_confirms(self):
        p,item=plan_fixture();s=MemoryStore(p,item);before=deepcopy(s.rows)
        with self.assertRaisesRegex(SubmissionError,"STORED_OPERATION_EVIDENCE_REQUIRED"):
            persistence_outcome(p.submission,s.current_access(p),s.current_evidence(p.submission),p.receipt,lifetime=s.lifetime(p.submission))
        self.assertIsNone(s.operation_evidence(p.submission));self.assertEqual(s.rows,before)
        self.assertEqual(s.rows[(item["PK"],item["SK"])]["status"],"ASSIGNED")

    def test_wrapping_prepared_metadata_is_not_stored_evidence(self):
        p,item=plan_fixture();s=MemoryStore(p,item);b=s.current_evidence(p.submission)
        wrapped=StoredReceiptEvidence(encoded(p.receipt.__dict__),b.read_id,True,True,True)
        self.assert_refused(p,s,operation=wrapped)

    def test_independent_revision_advance_without_receipt_stays_unknown(self):
        p,item=plan_fixture();s=MemoryStore(p,item);s.rows[(item["PK"],item["SK"])]["legacy_write_revision"]=2
        result=persistence_outcome(p.submission,s.current_access(p),s.current_evidence(p.submission),s.operation_evidence(p.submission))
        self.assertEqual(result,{"state":"UNKNOWN_NO_BLIND_RETRY"})
        self.assert_refused(p,s,operation=p.receipt)
        # Even a complete planned Put plus revision progression has no provenance.
        spec=transaction(p,"offline-submissions")["TransactItems"][-1]["Put"]
        planned={k:TypeDeserializer().deserialize(v) for k,v in spec["Item"].items()}
        for field in ("source_revision","committed_revision"):planned[field]=revision(planned[field])
        unverified=StoredReceiptEvidence(encoded(planned),s.current_evidence(p.submission).read_id)
        self.assert_refused(p,s,operation=unverified)

    def test_equal_and_future_source_revision_refuse_even_with_matching_digest(self):
        p,s=self.committed();current=s.current(p.submission).revision
        for source in (current,current+100):
            evidence=self.tampered_operation(s,p.submission,source_revision=source,committed_revision=source+1)
            self.assert_refused(p,s,operation=evidence)

    def test_committed_revision_must_be_exact_source_plus_one(self):
        p,s=self.committed()
        for value in (1,3,True,2.0,"2",None):
            self.assert_refused(p,s,operation=self.tampered_operation(s,p.submission,committed_revision=value))

    def test_wrong_stored_operation_target_actor_issuer_payload_and_incarnation_refuse(self):
        p,s=self.committed()
        for delta in ({"operation":"other-op"},{"tenant":"tenant_b"},{"client_id":"client-b"},
                      {"request_id":"request-b"},{"actor":"actor-b"},{"issuer":"https://other.example.invalid"},
                      {"binding":"0"*64},{"incarnation":"other-life"}):
            self.assert_refused(p,s,operation=self.tampered_operation(s,p.submission,**delta))

    def test_wrong_storage_location_state_or_receipt_digest_refuse(self):
        p,s=self.committed()
        for delta in ({"PK":"CANCEL_SUBMISSION#tenant_a#other-op"},{"SK":"PREPARED"},
                      {"commit_state":"PREPARED"},{"receipt_digest":"0"*64}):
            self.assert_refused(p,s,operation=self.tampered_operation(s,p.submission,**delta))

    def test_stored_evidence_flags_and_coherent_read_are_required(self):
        p,s=self.committed();e=s.operation_evidence(p.submission)
        for field in ("verified","authoritative","current"):
            for value in (False,1,"true",None):self.assert_refused(p,s,operation=replace(e,**{field:value}))
        self.assert_refused(p,s,operation=replace(e,read_id="other-read"))
        self.assert_refused(p,s,operation=json.loads(e.item_json))

    def test_incomplete_extra_and_noncanonical_stored_items_refuse(self):
        p,s=self.committed();e=s.operation_evidence(p.submission);item=json.loads(e.item_json)
        for value in (encoded({k:v for k,v in item.items() if k!="committed_revision"}),
                      encoded(item|{"ttl":None}),json.dumps(item,indent=2),"not-json"):
            self.assert_refused(p,s,operation=replace(e,item_json=value))

    def test_timeout_before_commit_remains_unknown_with_no_receipt_evidence(self):
        p,item=plan_fixture();s=MemoryStore(p,item)
        with self.assertRaises(TimeoutError):s.submit(p,timeout="before")
        self.assertEqual(persistence_outcome(p.submission,s.current_access(p),s.current_evidence(p.submission)),{"state":"UNKNOWN_NO_BLIND_RETRY"})

    def test_timeout_after_commit_requires_stored_observation_not_prepared_receipt(self):
        p,item=plan_fixture();s=MemoryStore(p,item)
        with self.assertRaises(TimeoutError):s.submit(p,timeout="after")
        self.assert_refused(p,s,operation=p.receipt)
        result=persistence_outcome(p.submission,s.current_access(p),s.current_evidence(p.submission),s.operation_evidence(p.submission),lifetime=s.lifetime(p.submission))
        self.assertEqual(result,{"state":"REPLAY_CONFIRMED","response":p.receipt.response()})

    def test_changed_removed_null_and_malformed_current_identity_refuse(self):
        for value in ("changed","",None,False,1,[],{},"REMOVED"):
            p,s=self.committed();key=(p.submission.key()["PK"],p.submission.key()["SK"])
            if value=="REMOVED":del s.rows[key]["client_email"]
            else:s.rows[key]["client_email"]=value
            self.assert_refused(p,s)

    def test_every_relied_identity_field_is_compared_to_persisted_value(self):
        for field in ("client_email","linked_client_profile_id","cognito_sub"):
            sub,item,access,snapshot,policy=fixture();item[field]="actor-binding"
            access=replace(access,bindings=((field,"actor-binding"),))
            p=prepare(sub,access,parse_snapshot(item,sub),NOW,policy);s=MemoryStore(p,item);s.submit(p)
            s.rows[(item["PK"],item["SK"])][field]="someone-else"
            self.assert_refused(p,s)

    def test_stale_read_or_revision_context_after_identity_change_refuses(self):
        p,s=self.committed();access=s.current_access(p);key=(p.submission.key()["PK"],p.submission.key()["SK"])
        s.rows[key]["client_email"]="changed"
        self.assert_refused(p,s,access=access)
        p,s=self.committed();access=s.current_access(p);s.rows[key]["legacy_write_revision"]=3
        self.assert_refused(p,s,access=access)

    def test_booking_evidence_flags_shape_and_binding_fields_fail_closed(self):
        p,s=self.committed();e=s.current_evidence(p.submission)
        for field in ("verified","authoritative","current"):
            for value in (False,1,"true",None):self.assert_refused(p,s,booking=replace(e,**{field:value}))
        for fields in ((),(("client_email",None),),(("display_name","opaque-booking-binding"),),
                       (("client_email","opaque-booking-binding"),("client_email","opaque-booking-binding"))):
            self.assert_refused(p,s,booking=replace(e,identity_fields=fields))
        self.assert_refused(p,s,booking=e.snapshot)

    def test_wrong_current_role_actor_issuer_target_and_tenant_refuse(self):
        p,s=self.committed();access=s.current_access(p)
        for delta in ({"role":"unknown"},{"actor":"actor-b"},{"issuer":"https://other.example.invalid"},
                      {"tenant":"tenant_b"},{"client_id":"client-b"},{"request_id":"request-b"},
                      {"verified":False},{"current":False},{"tenant_active":False},{"booking_allowed":False}):
            self.assert_refused(p,s,access=replace(access,**delta))

    def test_valid_replay_preserves_original_result_audit_and_unrelated_fields(self):
        p,s=self.committed();key=(p.submission.key()["PK"],p.submission.key()["SK"])
        s.rows[key]["unknown_after_commit"]={"preserve":[1,2]};before=deepcopy(s.rows)
        for _ in range(3):self.assertEqual(s.submit(p,access=s.current_access(p)),p.receipt.response())
        self.assertEqual(s.rows,before);self.assertEqual(len(s.rows[key]["audit_log"]),2)

    def test_boolean_or_unverified_refusal_is_not_authoritative_outcome(self):
        p,item=plan_fixture();s=MemoryStore(p,item);access=s.current_access(p);booking=s.current_evidence(p.submission)
        proof=RefusalEvidence(p.submission.binding(),booking.read_id,True,True,True,True)
        for value in (True,None,{},replace(proof,verified=False),replace(proof,authoritative=False),
                      replace(proof,operation_not_committed=False),replace(proof,attempts_quiescent=False),
                      replace(proof,binding="0"*64),replace(proof,read_id="other-read")):
            before=deepcopy(s.rows)
            with self.assertRaises(SubmissionError):persistence_outcome(p.submission,access,booking,confirmed_refusal=value)
            self.assertEqual(s.rows,before)

    def test_corrected_reconciliation_uses_no_network_or_mutation(self):
        p,s=self.committed();before=deepcopy(s.rows)
        with patch.object(socket.socket,"connect",side_effect=AssertionError("NETWORK_FORBIDDEN")):
            result=persistence_outcome(p.submission,s.current_access(p),s.current_evidence(p.submission),s.operation_evidence(p.submission),lifetime=s.lifetime(p.submission))
        self.assertEqual(result["state"],"REPLAY_CONFIRMED");self.assertEqual(s.rows,before)
