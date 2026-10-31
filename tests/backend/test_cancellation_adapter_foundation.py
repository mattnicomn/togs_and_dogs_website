"""Synthetic adapter evidence, classifier and writer compatibility regressions."""
import ast
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import socket
import re
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src/backend"))
from common.cancellation_adapter_foundation import (
    AdapterError,FrozenMap,Observation,ObservationAttestation,CommitReport,OutcomeAttestation,
    freeze,thaw,fingerprint,classify_legacy,validate_observation,prepare_commit,validate_command,
    replay_response,commit_outcome,
)
from common.cancellation_writer_inventory import WRITERS,ROLLOUT_BLOCKERS,assess_writer
from cancellation_adapter_fakes import State,FakeAuthority,FakeCommitPort,fixture,query,STAMP


def setup():
    state=State();authority=FakeAuthority(state);port=FakeCommitPort(state,authority);q=query();o=authority.observe(q)
    return q,state,authority,port,o


def command(q,o,a):return prepare_commit(q,o,a,a.now,STAMP,"ASSIGNED","synthetic-test-only")


class AdapterObservationTests(unittest.TestCase):
    def test_complete_protected_observation_and_non_executable_command(self):
        q,s,a,p,o=setup();row=validate_observation(q,o,a,a.now);cmd=command(q,o,a)
        self.assertEqual(row["status"],"ASSIGNED");self.assertIn("INACTIVE_NO_RUNTIME",cmd.blockers)
        self.assertEqual(cmd.expected_revision,1);self.assertEqual(p.calls,0)
        self.assertEqual(classify_legacy(q,thaw(o.request),thaw(o.lifetime)).disposition,"PROTECTED_PATH_CANDIDATE")

    def test_missing_or_boolean_verifier_cannot_establish_evidence(self):
        q,s,a,p,o=setup()
        class BooleanVerifier:
            def verify_observation(self,*args):return True
        for verifier in (None,{},BooleanVerifier()):
            with self.assertRaises(AdapterError):validate_observation(q,o,verifier,a.now)

    def test_client_json_and_verified_flag_are_not_observations(self):
        q,s,a,p,o=setup()
        for value in ({"verified":True},o.__dict__,True,None):
            with self.assertRaises(AdapterError):validate_observation(q,value,a,a.now)

    def test_forged_snapshot_with_shared_id_and_digest_is_rejected(self):
        q,s,a,p,o=setup();row=thaw(o.request);row["status"]="APPROVED"
        fake=replace(o,request=freeze(row))
        with self.assertRaisesRegex(AdapterError,"FORGED"):validate_observation(q,fake,a,a.now)
        self.assertEqual(fake.observation_id,o.observation_id)

    def test_missing_registry_observation_is_rejected(self):
        q,s,a,p,o=setup();a.issued.clear()
        with self.assertRaises(AdapterError):validate_observation(q,o,a,a.now)

    def test_wrong_principal_issuer_subject_tenant_role_and_query_target(self):
        q,s,a,p,o=setup()
        for delta in ({"issuer":"https://other.example.invalid"},{"subject":"other"},{"tenant":"tenant_b"},
                      {"role":"owner"},{"client_id":"other"},{"request_id":"other"},{"operation":"other"},{"reason":"changed"}):
            with self.assertRaises(AdapterError):validate_observation(replace(q,**delta),o,a,a.now)

    def test_stale_and_untrusted_clock_refuse(self):
        q,s,a,p,o=setup();a.now=16
        with self.assertRaises(AdapterError):validate_observation(q,o,a,a.now)
        a.now=10
        for now in (9,True,11):
            with self.assertRaises(AdapterError):validate_observation(q,o,a,now)

    def test_revocation_tenant_and_principal_epoch_changes_refuse(self):
        for field in ("principal_epoch","tenant_epoch","revocation_epoch"):
            q,s,a,p,o=setup();setattr(a,field,2)
            with self.assertRaises(AdapterError):validate_observation(q,o,a,a.now)
        for field,value in (("active",False),("revoked",True)):
            q,s,a,p,o=setup();setattr(a,field,value)
            with self.assertRaises(AdapterError):validate_observation(q,o,a,a.now)

    def test_incoherent_request_lifetime_receipt_mix_refuses(self):
        q,s,a,p,o=setup();other=replace(o,observation_id="same-read",coherence="UNPROVEN")
        with self.assertRaises(AdapterError):validate_observation(q,other,a,a.now)
        for delta in ({"lifetime":freeze(thaw(o.lifetime)|{"incarnation":"other-life"})},
                      {"receipt":freeze({"commit_state":"COMMITTED"})}):
            with self.assertRaises(AdapterError):validate_observation(q,replace(o,**delta),a,a.now)

    def test_changed_removed_null_and_malformed_identity_fields_refuse(self):
        for value in ("other","",None,False,1,[],{},"MISSING"):
            q,s,a,p,o=setup()
            if value=="MISSING":del s.rows[q.key()]["client_email"]
            else:s.rows[q.key()]["client_email"]=value
            fresh=a.observe(q)
            with self.assertRaises(AdapterError):validate_observation(q,fresh,a,a.now)

    def test_no_expected_identity_binding_is_inferred_from_current_booking(self):
        q,s,a,p,o=setup();s.rows[q.key()]["client_email"]="same-name-but-other-identity"
        with self.assertRaises(AdapterError):command(q,a.observe(q),a)
        self.assertEqual(a.bindings,{"client_email":"opaque-owned-binding"})

    def test_unknown_roles_and_malformed_issuer_fail_closed(self):
        q,s,a,p,o=setup()
        for delta in ({"role":"unknown"},{"role":"platform_admin"},{"issuer":"http://issuer.invalid"},{"issuer":"https://u:p@issuer.invalid"}):
            with self.assertRaises(AdapterError):replace(q,**delta).validate()


class LegacyClassificationTests(unittest.TestCase):
    def classify(self,change=None,remove=(),life_change=None,no_life=False,reservation=None):
        q,record,life=fixture()
        for k in remove:record.pop(k,None)
        if change:record.update(change)
        if life_change:life.update(life_change)
        before=deepcopy((record,life))
        result=classify_legacy(q,record,None if no_life else life,reservation)
        self.assertEqual((record,life),before)
        return result

    def test_missing_tenant_is_adoption_not_default_tenant(self):
        self.assertEqual(self.classify(remove=("company_id",)).disposition,"STAGED_ADOPTION_REQUIRED")

    def test_missing_incarnation_revision_and_lifetime_require_adoption(self):
        for remove in (("record_incarnation",),("legacy_write_revision",)):
            self.assertEqual(self.classify(remove=remove,no_life=True).disposition,"STAGED_ADOPTION_REQUIRED")
        self.assertEqual(self.classify(no_life=True).disposition,"STAGED_ADOPTION_REQUIRED")

    def test_wrong_explicit_identity_is_protected_refusal(self):
        for change in ({"company_id":"tenant_b"},{"client_id":"other"},{"request_id":"other"},{"PK":"REQ#other"}):
            self.assertEqual(self.classify(change).disposition,"PROTECTED_REFUSAL")

    def test_missing_explicit_ids_need_policy_not_key_guessing(self):
        for key in ("client_id","request_id"):
            self.assertEqual(self.classify(remove=(key,)).disposition,"LEGACY_POLICY_REQUIRED")

    def test_legacy_status_labels_need_policy(self):
        for status in ("BOOKED","SCHEDULED","JOB_CREATED",None):
            self.assertEqual(self.classify({"status":status}).disposition,"LEGACY_POLICY_REQUIRED")
        self.assertEqual(self.classify({"status":"UNKNOWN"}).disposition,"MANUAL_INVESTIGATION_REQUIRED")

    def test_audit_absent_is_supported_null_and_malformed_require_investigation(self):
        self.assertEqual(self.classify(remove=("audit_log",)).disposition,"PROTECTED_PATH_CANDIDATE")
        for value in (None,{},"text",False):
            self.assertEqual(self.classify({"audit_log":value}).disposition,"MANUAL_INVESTIGATION_REQUIRED")

    def test_linked_profile_difference_preserves_provenance_and_needs_policy(self):
        self.assertEqual(self.classify({"linked_client_profile_id":"owner-client-other"}).disposition,"LEGACY_POLICY_REQUIRED")
        for value in (False,{},""):
            self.assertEqual(self.classify({"linked_client_profile_id":value}).disposition,"MANUAL_INVESTIGATION_REQUIRED")

    def test_malformed_revision_never_becomes_default(self):
        for value in (True,0,-1,1.0,"1",Decimal("1.5")):
            self.assertEqual(self.classify({"legacy_write_revision":value}).disposition,"MANUAL_INVESTIGATION_REQUIRED")

    def test_integral_db_decimal_and_unknown_fields_preserve_types(self):
        q,item,life=fixture();item.update(legacy_write_revision=Decimal("1"),unknown=Decimal("1.25"))
        frozen=freeze(item);copy=thaw(frozen)
        self.assertEqual(copy,item);self.assertIs(type(copy["unknown"]),Decimal)
        self.assertEqual(classify_legacy(q,copy,life).disposition,"PROTECTED_PATH_CANDIDATE")

    def test_partial_null_markers_and_reservations_are_protected_refusals(self):
        from common.cancellation_adapter_foundation import MARKERS
        for marker in MARKERS:
            for value in (None,False,{},"unsupported"):
                self.assertEqual(self.classify({marker:value}).disposition,"PROTECTED_REFUSAL")
        self.assertEqual(self.classify(reservation={}).disposition,"PROTECTED_REFUSAL")

    def test_retired_reused_expiring_and_malformed_lifetimes_refuse(self):
        for delta in ({"retired":True},{"retired":0},{"incarnation":"other-life"},{"ttl":None},{"PK":"wrong"}):
            self.assertEqual(self.classify(life_change=delta).disposition,"PROTECTED_REFUSAL")

    def test_missing_record_and_mixed_formats_require_investigation(self):
        q,record,life=fixture()
        for value in (None,[],"legacy"):
            self.assertEqual(classify_legacy(q,value,life).disposition,"MANUAL_INVESTIGATION_REQUIRED")


class CommitPortTests(unittest.TestCase):
    def test_atomic_commit_and_receipt_parent_contract_compatibility(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);report=p.commit(cmd)
        state,response=commit_outcome(cmd,report,a,a.now)
        self.assertEqual(state,"COMMITTED");self.assertEqual(set(response),{"message","urgent_warning"})
        self.assertEqual(s.rows[q.key()]["status"],"CANCELLATION_REQUESTED")
        self.assertEqual(len(s.rows[q.key()]["audit_log"]),2)

    def test_validation_refusal_publishes_no_rows_or_effects(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);a.revoked=True;before=deepcopy(s.rows)
        with self.assertRaises(AdapterError):p.commit(cmd)
        self.assertEqual(s.rows,before);self.assertEqual(s.effects,[]);self.assertEqual(p.calls,0)

    def test_tampered_command_cannot_modify_arbitrary_fields(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);before=deepcopy(s.rows)
        for delta in ({"patch":freeze({"set":{"payment_status":"changed"}})},{"expected_revision":2},{"incarnation":"other-life"},{"guards":()}):
            with self.assertRaises(AdapterError):p.commit(replace(cmd,**delta))
        self.assertEqual(s.rows,before)

    def test_status_or_revision_writer_race_refuses_atomically(self):
        for field,value in (("status","CANCELLED"),("legacy_write_revision",2),("record_incarnation","other-life")):
            q,s,a,p,o=setup();cmd=command(q,o,a);s.rows[q.key()][field]=value;before=deepcopy(s.rows)
            report=p.commit(cmd);self.assertEqual(commit_outcome(cmd,report,a,a.now),("REFUSED",None))
            self.assertEqual(s.rows,before)

    def test_reservation_and_marker_insertions_after_observation_refuse(self):
        for mode in ("reservation","marker","retire"):
            q,s,a,p,o=setup();cmd=command(q,o,a)
            if mode=="reservation":s.rows[("RESERVATION#"+q.token(),"PERMANENT")]={"PK":"RESERVATION#"+q.token(),"SK":"PERMANENT"}
            elif mode=="marker":s.rows[q.key()]["canonical_worker_id"]=None
            else:s.rows[("LIFETIME#"+q.token(),"PERMANENT")]["retired"]=True
            before=deepcopy(s.rows);report=p.commit(cmd)
            self.assertEqual(commit_outcome(cmd,report,a,a.now),("REFUSED",None));self.assertEqual(s.rows,before)

    def test_concurrent_unknown_fields_and_audit_are_preserved(self):
        q,s,a,p,o=setup();cmd=command(q,o,a)
        s.rows[q.key()]["new_unknown"]={"exact":Decimal("1.25")};s.rows[q.key()]["audit_log"].append({"action":"concurrent"})
        report=p.commit(cmd);commit_outcome(cmd,report,a,a.now)
        self.assertEqual(s.rows[q.key()]["new_unknown"],{"exact":Decimal("1.25")});self.assertEqual(len(s.rows[q.key()]["audit_log"]),3)

    def test_malformed_audit_inserted_after_observation_refuses(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);s.rows[q.key()]["audit_log"]=None;before=deepcopy(s.rows)
        report=p.commit(cmd);self.assertEqual(report.state,"REFUSED");self.assertEqual(s.rows,before)

    def test_timeout_before_commit_stays_unknown_and_blocks_blind_retry(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);before=deepcopy(s.rows);report=p.commit(cmd,"timeout_before")
        self.assertEqual(commit_outcome(cmd,report,a,a.now),("UNKNOWN",None));self.assertEqual(s.rows,before)
        with self.assertRaisesRegex(AdapterError,"NO_BLIND_RETRY"):p.commit(cmd)

    def test_timeout_after_commit_reobserves_receipt_without_second_mutation(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);report=p.commit(cmd,"timeout_after")
        self.assertEqual(commit_outcome(cmd,report,a,a.now),("UNKNOWN",None));before=deepcopy(s.rows)
        response=replay_response(q,a.observe(q),a,a.now)
        self.assertEqual(set(response),{"message","urgent_warning"});self.assertEqual(s.rows,before)
        with self.assertRaisesRegex(AdapterError,"NO_BLIND_RETRY"):p.commit(cmd)

    def test_prepared_receipt_or_independent_revision_does_not_prove_commit(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);s.rows[q.key()]["legacy_write_revision"]=2
        s.rows[("CANCEL_SUBMISSION#"+q.tenant+"#"+q.operation,"RECEIPT")]=cmd.stored_receipt.mapping()
        with self.assertRaisesRegex(AdapterError,"UNPROVEN_OPERATION_COMMIT"):replay_response(q,a.observe(q),a,a.now)

    def test_equal_and_future_source_revision_are_rejected(self):
        for source in (2,102):
            q,s,a,p,o=setup();cmd=command(q,o,a);p.commit(cmd);k=("CANCEL_SUBMISSION#"+q.tenant+"#"+q.operation,"RECEIPT")
            item=s.rows[k];item.update(source_revision=source,committed_revision=source+1)
            # Even compromised synthetic provenance cannot bypass structural revision checks.
            s.committed[q.binding()]=fingerprint(freeze(item))
            with self.assertRaises(AdapterError):replay_response(q,a.observe(q),a,a.now)

    def test_legitimate_historical_replay_and_restart_append_no_audit(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);report=p.commit(cmd);expected=commit_outcome(cmd,report,a,a.now)[1]
        s.rows[q.key()].update(status="CANCELLED",legacy_write_revision=3)
        restarted=FakeAuthority(s);before=deepcopy(s.rows)
        self.assertEqual(replay_response(q,restarted.observe(q),restarted,restarted.now),expected)
        self.assertEqual(s.rows,before)

    def test_changed_current_identity_prevents_replay_after_commit(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);p.commit(cmd);s.rows[q.key()]["client_email"]="other"
        with self.assertRaises(AdapterError):replay_response(q,a.observe(q),a,a.now)

    def test_retirement_blocks_identical_delete_recreate_aba(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);old=deepcopy(s.rows[q.key()]);del s.rows[q.key()]
        s.rows[("LIFETIME#"+q.token(),"PERMANENT")]["retired"]=True;s.rows[q.key()]=old
        report=p.commit(cmd);self.assertEqual(report.state,"REFUSED")

    def test_unfenced_identical_restore_is_characterized_not_claimed_solved(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);old=deepcopy(s.rows[q.key()]);del s.rows[q.key()];s.rows[q.key()]=old
        self.assertEqual(p.commit(cmd).state,"COMMITTED")
        self.assertIn("ALL_WRITERS_PENDING",cmd.blockers)

    def test_forged_commit_and_refusal_reports_are_not_authoritative(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);genuine=p.commit(cmd,"conflict")
        for report in (replace(genuine,state="COMMITTED",observation=o),
                       replace(genuine,attempt_id="unissued-attempt")):
            with self.assertRaisesRegex(AdapterError,"FORGED_OUTCOME"):commit_outcome(cmd,report,a,a.now)

    def test_refusal_requires_verified_non_commit_and_quiescence(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);genuine=p.commit(cmd,"conflict")
        for report in (replace(genuine,non_commit_proven=False),replace(genuine,attempts_quiescent=False)):
            a.reports[fingerprint(report)]=(q.binding(),fingerprint(cmd))
            with self.assertRaisesRegex(AdapterError,"NON_COMMIT_PROOF_REQUIRED"):commit_outcome(cmd,report,a,a.now)

    def test_outcome_binding_and_boolean_attestation_fail_closed(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);report=p.commit(cmd)
        class BooleanVerifier:
            def verify_outcome(self,*args):return True
        with self.assertRaises(AdapterError):commit_outcome(cmd,report,BooleanVerifier(),a.now)
        with self.assertRaises(AdapterError):commit_outcome(cmd,replace(report,binding="wrong"),a,a.now)

    def test_oversize_refusal_precedes_mutation(self):
        q,s,a,p,o=setup();q=replace(q,reason="x"*200000);o=a.observe(q);before=deepcopy(s.rows)
        with self.assertRaisesRegex(AdapterError,"OVERSIZE_REFUSED"):command(q,o,a)
        self.assertEqual(s.rows,before);self.assertEqual(p.calls,0)

    def test_no_implicit_status_policy_or_legacy_enrollment(self):
        q,s,a,p,o=setup();before=deepcopy(s.rows)
        with self.assertRaisesRegex(AdapterError,"POLICY_PENDING"):prepare_commit(q,o,a,a.now,STAMP)
        del s.rows[q.key()]["legacy_write_revision"];before=deepcopy(s.rows)
        with self.assertRaises(AdapterError):command(q,a.observe(q),a)
        self.assertEqual(s.rows,before)


class WriterCompatibilityTests(unittest.TestCase):
    def test_inventory_ids_unique_and_source_paths_functions_exist(self):
        root=Path(__file__).resolve().parents[2]
        self.assertEqual(len({w.name for w in WRITERS}),len(WRITERS))
        for writer in WRITERS:
            path=root/writer.source if writer.source.startswith("scripts/") else root/"src/backend"/writer.source
            source=path.read_text(encoding="utf-8")
            names={n.name for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef)}
            self.assertTrue(set(writer.function.split(" / "))<=names,writer.name)
            lines=source.splitlines()
            for line in writer.lines:self.assertTrue(any(x in lines[line-1] for x in ("put_item","update_item","delete_item","update_status","def ","transact_write_items")),writer.name)

    def test_disjoint_metadata_upserts_still_require_all_atomic_guards(self):
        writer=next(w for w in WRITERS if w.name=="approval_metadata");assessment=assess_writer(writer)
        self.assertIn("no_upsert",assessment.required_guards);self.assertIn("live_lifetime",assessment.required_guards)
        self.assertFalse(assessment.activation_ready)

    def test_delete_replacement_and_identity_writers_are_not_compatible_by_default(self):
        for name in ("admin_purge","generic_db","client_link","zombie_cleanup"):
            writer=next(w for w in WRITERS if w.name==name);assessment=assess_writer(writer)
            self.assertFalse(assessment.activation_ready);self.assertTrue(assessment.required_guards)

    def test_full_synthetic_guard_list_does_not_activate_unrolled_writer(self):
        for writer in WRITERS:
            assessment=assess_writer(writer)
            again=assess_writer(writer,assessment.required_guards)
            self.assertEqual(again.required_guards,());self.assertFalse(again.activation_ready)

    def test_status_audit_identity_and_coupled_paths_are_explicit(self):
        byname={w.name:assess_writer(w) for w in WRITERS}
        self.assertIn("STATUS_CONFLICT",byname["submission"].conflicts)
        self.assertIn("AUDIT_APPEND_PROTOCOL",byname["submission"].conflicts)
        self.assertIn("BOOKING_IDENTITY_INVALIDATION",byname["client_link"].conflicts)
        self.assertIn("complete_affected_set_and_effect_protocol",byname["review"].required_guards)

    def test_older_versions_and_operational_gaps_remain_blockers(self):
        self.assertGreaterEqual(len(ROLLOUT_BLOCKERS),5)
        self.assertTrue(any("PR22" in b for b in ROLLOUT_BLOCKERS));self.assertTrue(any("manual" in b for b in ROLLOUT_BLOCKERS))

    def test_source_modules_are_stdlib_unwired_and_no_network(self):
        root=Path(__file__).resolve().parents[2]
        allowed={"dataclasses","datetime","decimal","hashlib","json","re","typing","urllib"}
        for name in ("cancellation_adapter_foundation","cancellation_writer_inventory"):
            own=root/"src/backend/common"/(name+".py");tree=ast.parse(own.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):self.assertTrue(all(n.name.split(".")[0] in allowed for n in node.names))
                if isinstance(node,ast.ImportFrom):self.assertIn(node.module.split(".")[0],allowed)
            for path in (root/"src/backend").rglob("*.py"):
                if path!=own:self.assertNotIn(name,path.read_text(encoding="utf-8"))
        with patch.object(socket.socket,"connect",side_effect=AssertionError("NETWORK_FORBIDDEN")):
            q,s,a,p,o=setup();cmd=command(q,o,a);report=p.commit(cmd);commit_outcome(cmd,report,a,a.now)
        self.assertEqual(s.effects,[])


class AdditionalFoundationTests(unittest.TestCase):
    def test_principal_bindings_change_without_epoch_cannot_reuse_old_observation(self):
        for field,value in (("subject","other"),("role","owner"),("tenant","tenant_b"),("trusted_issuer","https://other.example.invalid")):
            q,s,a,p,o=setup();setattr(a,field,value)
            with self.assertRaises(AdapterError):validate_observation(q,o,a,a.now)
        q,s,a,p,o=setup();a.bindings={"client_email":"other"}
        with self.assertRaises(AdapterError):validate_observation(q,o,a,a.now)

    def test_false_or_numeric_principal_flags_and_versions_refuse(self):
        q,s,a,p,o=setup()
        for delta in ({"tenant_active":1},{"revoked":0},{"principal_epoch":True},{"revocation_epoch":0}):
            with self.assertRaises(AdapterError):validate_observation(q,replace(o,principal=replace(o.principal,**delta)),a,a.now)

    def test_committed_outcome_cannot_disclose_through_changed_principal(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);report=p.commit(cmd);a.subject="other"
        with self.assertRaises(AdapterError):commit_outcome(cmd,report,a,a.now)

    def test_legacy_classifier_never_mutates_request_or_supplies_identity(self):
        q,item,life=fixture();del item["company_id"];del item["record_incarnation"];del item["legacy_write_revision"]
        before=deepcopy(item);result=classify_legacy(q,item,None)
        self.assertEqual(result.disposition,"STAGED_ADOPTION_REQUIRED");self.assertEqual(item,before)
        self.assertNotIn("record_incarnation",item)

    def test_no_production_adapter_can_be_inferred_from_protocol_presence(self):
        q,s,a,p,o=setup();cmd=command(q,o,a)
        self.assertFalse(hasattr(cmd,"execute"));self.assertFalse(hasattr(cmd,"commit"))
        self.assertIn("REAL_ADAPTER_PENDING",cmd.blockers)


class ConcurrentOperationEvidenceTests(unittest.TestCase):
    def test_same_operation_other_coordinator_commit_is_replay_not_refusal(self):
        q,s,a,p,o=setup();first=command(q,o,a);second=command(q,a.observe(q),a)
        p.commit(first);before=deepcopy(s.rows)
        report=FakeCommitPort(s,a).commit(second)
        self.assertEqual(commit_outcome(second,report,a,a.now)[0],"COMMITTED")
        self.assertEqual(s.rows,before);self.assertEqual(len(s.rows[q.key()]["audit_log"]),2)

    def test_unproven_existing_receipt_yields_unknown_not_non_commit_proof(self):
        q,s,a,p,o=setup();cmd=command(q,o,a)
        s.rows[("CANCEL_SUBMISSION#"+q.tenant+"#"+q.operation,"RECEIPT")]=cmd.stored_receipt.mapping()
        before=deepcopy(s.rows);report=p.commit(cmd)
        self.assertEqual(commit_outcome(cmd,report,a,a.now),("UNKNOWN",None));self.assertEqual(s.rows,before)
        with self.assertRaisesRegex(AdapterError,"NO_BLIND_RETRY"):p.commit(cmd)

    def test_changed_payload_operation_key_collision_refuses_without_mutation(self):
        q,s,a,p,o=setup();old=command(q,o,a);changed=replace(q,reason="changed-payload")
        competing=command(changed,a.observe(changed),a);p.commit(old);before=deepcopy(s.rows)
        report=p.commit(competing)
        self.assertEqual(commit_outcome(competing,report,a,a.now),("REFUSED",None));self.assertEqual(s.rows,before)


class InventoryFieldRegressionTests(unittest.TestCase):
    def test_sync_failure_metadata_is_not_mislabeled_as_audit_log(self):
        writer=next(w for w in WRITERS if w.name=="cancel_sync_failure")
        self.assertEqual(writer.writes,("sync_failures",))
        self.assertNotIn("AUDIT_APPEND_PROTOCOL",assess_writer(writer).conflicts)

    def test_quote_and_lifecycle_nonprefix_fields_are_explicit(self):
        quote=next(w for w in WRITERS if w.name=="admin_quote_payment")
        self.assertTrue({"currency","deposit_amount_cents","internal_pricing_notes"}<=set(quote.writes))
        lifecycle=next(w for w in WRITERS if w.name=="admin_lifecycle")
        self.assertTrue({"archived_at","archived_by","deleted_at"}<=set(lifecycle.writes))


class SecurityRestartRegressionTests(unittest.TestCase):
    def test_synthetic_security_state_is_not_reset_by_coordinator_restart(self):
        q,s,a,p,o=setup();a.revoked=True;a.revocation_epoch=2
        restarted=FakeAuthority(s);before=deepcopy(s.rows)
        self.assertTrue(restarted.revoked);self.assertEqual(restarted.revocation_epoch,2)
        with self.assertRaises(AdapterError):validate_observation(q,restarted.observe(q),restarted,restarted.now)
        self.assertEqual(s.rows,before)


class RefusalJournalCorrectionTests(unittest.TestCase):
    def refusal(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);report=p.commit(cmd,"conflict")
        return q,s,a,p,cmd,report

    def test_current_quiescent_refusal_is_valid_without_row_or_effect_changes(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);before=deepcopy(s.rows)
        report=p.commit(cmd,"conflict")
        self.assertEqual(commit_outcome(cmd,report,a,a.now),("REFUSED",None))
        self.assertEqual(s.rows,before);self.assertEqual(s.effects,[])
        self.assertEqual(report.attempt_id,s.journal[(q.tenant,q.operation)]["attempt_id"])

    def test_refusal_then_success_cannot_report_non_commit(self):
        q,s,a,p,cmd,report=self.refusal();p.commit(cmd);before=deepcopy(s.rows)
        self.assertEqual(commit_outcome(cmd,report,a,a.now),("UNKNOWN",None))
        self.assertEqual(replay_response(q,a.observe(q),a,a.now)["message"],"Cancellation request submitted for review.")
        self.assertEqual(s.rows,before);self.assertEqual(len(s.rows[q.key()]["audit_log"]),2)

    def test_refusal_then_ambiguous_attempts_invalidate_non_commit_and_block_retry(self):
        for mode in ("timeout_before","timeout_after"):
            with self.subTest(mode=mode):
                q,s,a,p,cmd,old=self.refusal();report=p.commit(cmd,mode);before=deepcopy(s.rows)
                self.assertEqual(commit_outcome(cmd,report,a,a.now),("UNKNOWN",None))
                self.assertEqual(commit_outcome(cmd,old,a,a.now),("UNKNOWN",None))
                with self.assertRaisesRegex(AdapterError,"NO_BLIND_RETRY"):p.commit(cmd)
                self.assertEqual(s.rows,before)

    def test_refusal_then_pending_attempt_is_not_quiescent(self):
        q,s,a,p,cmd,old=self.refusal();pending=p.commit(cmd,"pending");before=deepcopy(s.rows)
        self.assertEqual(s.journal[(q.tenant,q.operation)]["state"],"PENDING")
        self.assertEqual(commit_outcome(cmd,pending,a,a.now),("UNKNOWN",None))
        self.assertEqual(commit_outcome(cmd,old,a,a.now),("UNKNOWN",None))
        with self.assertRaisesRegex(AdapterError,"NO_BLIND_RETRY"):p.commit(cmd)
        self.assertEqual(s.rows,before)

    def test_unknown_same_operation_cannot_retry_with_changed_payload_or_coordinator(self):
        for mode in ("pending","timeout_before"):
            q,s,a,p,cmd,old=self.refusal();p.commit(cmd,mode)
            changed=replace(q,reason="changed-payload")
            other=command(changed,a.observe(changed),a);before=deepcopy(s.rows)
            with self.assertRaisesRegex(AdapterError,"NO_BLIND_RETRY"):FakeCommitPort(s,a).commit(other)
            self.assertEqual(s.rows,before)
            self.assertEqual(commit_outcome(cmd,old,a,a.now),("UNKNOWN",None))

    def test_forged_attempt_generation_and_wrong_operation_refuse(self):
        q,s,a,p,cmd,old=self.refusal();before=deepcopy(s.rows)
        for delta in ({"attempt_id":"other-attempt"},{"journal_generation":old.journal_generation+1},
                      {"binding":"other-operation"}):
            with self.assertRaises(AdapterError):commit_outcome(cmd,replace(old,**delta),a,a.now)
        other=replace(cmd,query=replace(q,operation="other-operation"))
        with self.assertRaises(AdapterError):commit_outcome(other,old,a,a.now)
        self.assertEqual(s.rows,before)

    def test_registered_but_stale_generation_does_not_become_authority(self):
        q,s,a,p,cmd,old=self.refusal();forged=replace(old,journal_generation=old.journal_generation+1)
        a.reports[fingerprint(forged)]=(q.binding(),fingerprint(cmd))
        self.assertEqual(commit_outcome(cmd,forged,a,a.now),("UNKNOWN",None))

    def test_refusal_rechecks_receipt_absence_and_commit_journal(self):
        for mode in ("unproven-row","commit-journal"):
            q,s,a,p,cmd,old=self.refusal()
            if mode=="unproven-row":
                s.rows[("CANCEL_SUBMISSION#"+q.tenant+"#"+q.operation,"RECEIPT")]=cmd.stored_receipt.mapping()
            else:s.committed[q.binding()]=fingerprint(cmd.stored_receipt)
            before=deepcopy(s.rows)
            self.assertEqual(commit_outcome(cmd,old,a,a.now),("UNKNOWN",None))
            self.assertEqual(s.rows,before)

    def test_refusal_after_coordinator_restart_is_bound_to_shared_attempt_journal(self):
        q,s,a,p,cmd,old=self.refusal();s.begin_attempt(q)
        self.assertEqual(commit_outcome(cmd,old,a,a.now),("UNKNOWN",None))
        restarted=FakeAuthority(s)
        with self.assertRaises(AdapterError):commit_outcome(cmd,old,restarted,restarted.now)


class ReplayFreshnessCorrectionTests(unittest.TestCase):
    def committed(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);p.commit(cmd)
        return q,s,a,p,a.observe(q)

    def test_retained_replay_refuses_changed_removed_null_and_malformed_identity(self):
        for field in ("client_email","cognito_sub","linked_client_profile_id"):
            for value in ("changed",None,{},[],False,42,"ABSENT"):
                with self.subTest(field=field,value=value):
                    q,s,a,p,o=setup()
                    s.rows[q.key()][field]=q.client_id if field=="linked_client_profile_id" else "opaque-binding"
                    a.bindings={field:s.rows[q.key()][field]};p.commit(command(q,a.observe(q),a));old=a.observe(q)
                    if value=="ABSENT":del s.rows[q.key()][field]
                    else:s.rows[q.key()][field]=value
                    before=deepcopy(s.rows)
                    with self.assertRaisesRegex(AdapterError,"STALE_PERSISTED"):replay_response(q,old,a,a.now)
                    self.assertEqual(s.rows,before);self.assertEqual(s.effects,[])

    def test_retained_replay_refuses_revision_advance_inside_lease(self):
        q,s,a,p,old=self.committed();s.rows[q.key()]["legacy_write_revision"]=3
        self.assertLessEqual(a.now,old.valid_until)
        with self.assertRaisesRegex(AdapterError,"STALE_PERSISTED"):replay_response(q,old,a,a.now)
        before=deepcopy(s.rows);replay_response(q,a.observe(q),a,a.now);self.assertEqual(s.rows,before)

    def test_retained_replay_rechecks_lifetime_presence_retirement_and_contents(self):
        for delta in (None,{"retired":True},{"incarnation":"different"},{"ttl":None}):
            q,s,a,p,old=self.committed();key=("LIFETIME#"+q.token(),"PERMANENT")
            if delta is None:del s.rows[key]
            else:s.rows[key].update(delta)
            before=deepcopy(s.rows)
            with self.assertRaisesRegex(AdapterError,"STALE_PERSISTED"):replay_response(q,old,a,a.now)
            self.assertEqual(s.rows,before)

    def test_retained_replay_rechecks_reservation_and_partial_markers(self):
        for mode in ("reservation","marker"):
            q,s,a,p,old=self.committed()
            if mode=="reservation":s.rows[("RESERVATION#"+q.token(),"PERMANENT")]={"PK":"RESERVATION#"+q.token(),"SK":"PERMANENT"}
            else:s.rows[q.key()]["assigned_worker_id"]=None
            with self.assertRaisesRegex(AdapterError,"STALE_PERSISTED"):replay_response(q,old,a,a.now)
            with self.assertRaises(AdapterError):replay_response(q,a.observe(q),a,a.now)

    def test_fresh_authorized_historical_replay_preserves_rows_and_single_audit(self):
        q,s,a,p,old=self.committed();s.rows[q.key()].update(status="CANCELLED",legacy_write_revision=3)
        with self.assertRaises(AdapterError):replay_response(q,old,a,a.now)
        before=deepcopy(s.rows);fresh=a.observe(q)
        self.assertEqual(replay_response(q,fresh,a,a.now)["urgent_warning"],True)
        self.assertEqual(replay_response(q,fresh,a,a.now)["urgent_warning"],True)
        self.assertEqual(s.rows,before);self.assertEqual(len(s.rows[q.key()]["audit_log"]),2)

    def test_current_observation_validation_refuses_stale_precommit_identity(self):
        q,s,a,p,old=setup();s.rows[q.key()]["client_email"]="changed"
        with self.assertRaisesRegex(AdapterError,"STALE_PERSISTED"):validate_observation(q,old,a,a.now)
        # A previously prepared write is still protected by actual PR51 conditions.
        q,s,a,p,old=setup();cmd=command(q,old,a);s.rows[q.key()]["client_email"]="changed"
        before=deepcopy(s.rows);report=p.commit(cmd)
        self.assertEqual(commit_outcome(cmd,report,a,a.now),("REFUSED",None));self.assertEqual(s.rows,before)

    def test_freshness_does_not_replace_current_revocation_checks(self):
        for field,value in (("revoked",True),("active",False),("principal_epoch",2),("tenant_epoch",2),("revocation_epoch",2)):
            q,s,a,p,old=self.committed();setattr(a,field,value)
            with self.assertRaises(AdapterError):replay_response(q,old,a,a.now)


class NumericBindingCorrectionTests(unittest.TestCase):
    def test_internal_command_revision_rejects_boolean_float_and_decimal(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);before=deepcopy(s.rows)
        for value in (True,1.0,Decimal("1"),Decimal("1.5"),Decimal("NaN"),Decimal("Infinity"),"1",0,-1):
            with self.assertRaises(AdapterError):validate_command(replace(cmd,expected_revision=value),a,a.now)
        validate_command(cmd,a,a.now);self.assertEqual(s.rows,before)

    def test_observation_attestation_epochs_are_exact_canonical_integers(self):
        q,s,a,p,o=setup()
        class BadVerifier:
            def verify_observation(self,q,o,now):return replace(a.verify_observation(q,o,now),**delta)
        for field in ("principal_epoch","tenant_epoch","revocation_epoch"):
            for value in (True,1.0,Decimal("1"),Decimal("NaN"),"1",0,-1):
                delta={field:value}
                with self.assertRaises(AdapterError):validate_observation(q,o,BadVerifier(),a.now)
        self.assertEqual(validate_observation(q,o,a,a.now)["legacy_write_revision"],1)

    def test_outcome_attestation_and_report_generation_reject_numeric_equivalence(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);report=p.commit(cmd,"conflict")
        class BadVerifier:
            def verify_outcome(self,cmd,report,now):return replace(a.verify_outcome(cmd,report,now),journal_generation=value)
        for value in (True,float(report.journal_generation),Decimal(report.journal_generation),Decimal("NaN"),0,-1):
            with self.assertRaises(AdapterError):commit_outcome(cmd,report,BadVerifier(),a.now)
            with self.assertRaises(AdapterError):commit_outcome(cmd,replace(report,journal_generation=value),a,a.now)
        self.assertEqual(commit_outcome(cmd,report,a,a.now),("REFUSED",None))

    def test_raw_security_epochs_cannot_normalize_through_python_equality(self):
        for field in ("principal_epoch","tenant_epoch","revocation_epoch"):
            for value in (True,1.0,Decimal("1")):
                q,s,a,p,o=setup();setattr(a,field,value)
                with self.assertRaises(AdapterError):validate_observation(q,o,a,a.now)
                with self.assertRaises(AdapterError):validate_observation(q,a.observe(q),a,a.now)

    def test_integral_finite_db_revision_normalizes_before_command_and_receipt(self):
        q,s,a,p,o=setup();s.rows[q.key()]["legacy_write_revision"]=Decimal("1")
        cmd=command(q,a.observe(q),a)
        self.assertIs(type(cmd.expected_revision),int);validate_command(cmd,a,a.now)
        report=p.commit(cmd);self.assertEqual(commit_outcome(cmd,report,a,a.now)[0],"COMMITTED")
        self.assertIs(type(cmd.stored_receipt.mapping()["source_revision"]),int)

    def test_invalid_db_decimals_never_prepare_or_commit(self):
        for value in (Decimal("1.5"),Decimal("NaN"),Decimal("Infinity"),Decimal("-1"),Decimal("0")):
            q,s,a,p,o=setup();s.rows[q.key()]["legacy_write_revision"]=value
            self.assertEqual(classify_legacy(q,s.rows[q.key()],thaw(o.lifetime)).disposition,"MANUAL_INVESTIGATION_REQUIRED")
            with self.assertRaises(AdapterError):command(q,a.observe(q),a)
            self.assertEqual(p.calls,0);self.assertEqual(s.effects,[])

    def test_command_binding_uses_typed_fingerprint_not_dataclass_equality(self):
        q,s,a,p,o=setup();cmd=command(q,o,a);before=deepcopy(s.rows)
        patch=cmd.patch.mapping();patch["set"]["legacy_write_revision"]=Decimal("2")
        receipt=cmd.stored_receipt.mapping();receipt["source_revision"]=True
        for changed in (replace(cmd,patch=freeze(patch)),replace(cmd,stored_receipt=freeze(receipt))):
            self.assertEqual(changed,cmd)  # Python's value equality would accept both.
            with self.assertRaisesRegex(AdapterError,"COMMAND_BINDING"):validate_command(changed,a,a.now)
        self.assertEqual(s.rows,before)



class OwnershipClassificationCorrectionTests(unittest.TestCase):
    def test_absent_optional_ownership_fields_are_not_invented(self):
        q,row,life=fixture()
        for field in ("client_email","cognito_sub","linked_client_profile_id"):row.pop(field,None)
        before=deepcopy(row);result=classify_legacy(q,row,life)
        self.assertEqual(result.disposition,"PROTECTED_PATH_CANDIDATE");self.assertEqual(row,before)
        # Classification is not booking authorization; a client still needs concrete verified bindings.
        q,s,a,p,o=setup();a.bindings={}
        with self.assertRaises(AdapterError):command(q,a.observe(q),a)

    def test_explicit_null_and_invalid_optional_ownership_values_are_not_candidates(self):
        for field in ("client_email","cognito_sub","linked_client_profile_id"):
            for value in (None,"","   ",{},[],False,True,1,1.0,Decimal("1")):
                q,row,life=fixture();row[field]=value;before=deepcopy(row)
                result=classify_legacy(q,row,life)
                self.assertEqual(result.disposition,"MANUAL_INVESTIGATION_REQUIRED")
                self.assertIn(("NULL_" if value is None else "MALFORMED_")+field,result.reasons)
                self.assertEqual(row,before)

    def test_nonempty_opaque_ownership_fields_are_structural_not_email_identity_proof(self):
        q,row,life=fixture();row.update(client_email="opaque-owned-binding",cognito_sub="opaque-subject",linked_client_profile_id=q.client_id)
        self.assertEqual(classify_legacy(q,row,life).disposition,"PROTECTED_PATH_CANDIDATE")
        row["linked_client_profile_id"]="other-client"
        self.assertEqual(classify_legacy(q,row,life).disposition,"LEGACY_POLICY_REQUIRED")

    def test_mixed_ownership_and_legacy_defects_keep_most_restrictive_disposition(self):
        q,row,life=fixture();del row["company_id"];row.update(client_email=None,cognito_sub={},linked_client_profile_id="other")
        result=classify_legacy(q,row,None)
        self.assertEqual(result.disposition,"MANUAL_INVESTIGATION_REQUIRED")
        self.assertTrue({"NULL_client_email","MALFORMED_cognito_sub","LINKED_OWNER_DIFFERS","MISSING_company_id","MISSING_LIFETIME"}<=set(result.reasons))
        row["assigned_worker_id"]=None
        self.assertEqual(classify_legacy(q,row,None).disposition,"PROTECTED_REFUSAL")


class ReviewInventoryCorrectionTests(unittest.TestCase):
    def test_review_request_fields_match_all_literal_and_constructed_write_branches(self):
        root=Path(__file__).resolve().parents[2];tree=ast.parse((root/"src/backend/handlers/review_handler.py").read_text(encoding="utf-8"))
        expressions=[];calls=[]
        for node in ast.walk(tree):
            if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Attribute) or node.func.attr!="update_item":continue
            kw={x.arg:x.value for x in node.keywords}
            key=kw.get("Key")
            if not isinstance(key,ast.Dict):continue
            pk=next((v for k,v in zip(key.keys,key.values) if isinstance(k,ast.Constant) and k.value=="PK"),None)
            if not isinstance(pk,ast.JoinedStr) or not any(isinstance(v,ast.Constant) and v.value=="REQ#" for v in pk.values):continue
            calls.append(node.lineno);expr=kw["UpdateExpression"]
            if isinstance(expr,ast.Constant):expressions.append(expr.value)
            elif isinstance(expr,ast.Name):
                for assignment in ast.walk(tree):
                    if isinstance(assignment,ast.Assign):targets=assignment.targets
                    elif isinstance(assignment,ast.AugAssign):targets=[assignment.target]
                    else:continue
                    if assignment.lineno<node.lineno and any(isinstance(t,ast.Name) and t.id==expr.id for t in targets):
                        self.assertIsInstance(assignment.value,ast.Constant)
                        expressions.append(assignment.value.value)
            else:self.fail("Uncharacterized REQUEST expression construction")
        fields=set()
        for expression in expressions:
            fields.update(re.findall(r"(?:\bSET\s+|,\s*)([#A-Za-z_]\w*)\s*=",expression))
            removed=expression.split(" REMOVE ",1)
            if len(removed)==2:fields.update(x.strip() for x in removed[1].split(','))
            elif expression.startswith("REMOVE "):fields.update(x.strip() for x in expression[7:].split(','))
        fields={"status" if field=="#stat" else field for field in fields}
        writer=next(w for w in WRITERS if w.name=="review")
        self.assertEqual(set(calls),set(writer.lines))
        self.assertEqual(fields,set(writer.writes))
        self.assertTrue({"updated_at","updated_by","visit_notes","client_profile_link_status"}<=fields)

    def test_review_coupling_and_all_inventory_activation_blocks_are_preserved(self):
        writer=next(w for w in WRITERS if w.name=="review")
        self.assertEqual(writer.category,"COORDINATED_MULTI_RECORD_PROTOCOL")
        self.assertTrue({"CLIENT/PET M&G","JOB","Calendar","notifications","async creation"}<=set(writer.coupled))
        self.assertEqual(len(WRITERS),26)
        for writer in WRITERS:
            result=assess_writer(writer)
            self.assertFalse(assess_writer(writer,result.required_guards).activation_ready)
