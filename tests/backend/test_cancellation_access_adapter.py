"""Synthetic gateway/access fixtures only. No real credentials, SDK or provider calls."""
import ast
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src/backend"))
from common.cancellation_access_adapter import (
    AccessError,Configuration,Query,GatewayEvidence,GatewayAttestation,LinkProof,Bundle,BundleAttestation,
    CancellationAccessAdapter,event_facts,frozen,thaw,digest,raw_digest,need,
)
from common import cancellation_adapter_foundation as parent


ISSUER="https://synthetic-issuer.example.invalid"
NOW=10


def synthetic_event(http=False):
    claims={"iss":ISSUER,"sub":"subject-a","custom:company_id":"tenant_a","cognito:groups":["client"]}
    return {"requestContext":{"authorizer":{"jwt":{"claims":claims}} if http else {"claims":claims}}}


class SyntheticReader:
    """Complete in-memory fixture lookup; not a database or issuer-qualified identity source."""
    def __init__(self):
        self.query=Query("tenant_a","client-a","request-a","operation-a","synthetic reason")
        q=self.query
        self.request={"PK":q.key()[0],"SK":q.key()[1],"company_id":q.tenant,"client_id":q.client_id,"request_id":q.request_id,
            "record_incarnation":"life-a","legacy_write_revision":1,"status":"ASSIGNED","start_date":"2026-11-01",
            "cognito_sub":"subject-a","linked_client_profile_id":"client-a","client_email":"opaque-binding",
            "audit_log":[{"action":"previous"}],"unknown":{"keep":Decimal("1.25")}}
        self.profiles=[{"PK":"COMPANY#tenant_a","SK":"CLIENT#client-a","client_id":"client-a","company_id":"tenant_a",
                        "cognito_sub":"subject-a","is_active":True}]
        self.tenant={"PK":"TENANT#tenant_a","SK":"METADATA","is_active":True,"subscription_status":"active"}
        self.lifetime={"PK":"LIFETIME#"+q.token(),"SK":"PERMANENT","incarnation":"life-a","retired":False}
        self.reservation=None;self.receipt=None
        self.link=LinkProof(ISSUER,"subject-a",q.tenant,q.client_id,q.request_id,"client-a","life-a",1,
                           (("cognito_sub","subject-a"),("linked_client_profile_id","client-a")),"synthetic-provenance-a")
        self.epochs=(1,1,1);self.revoked=False;self.complete=True;self.coherence="COHERENT_SNAPSHOT"
        self.now=NOW;self.serial=0;self.calls=0;self.registry={};self.fail=False;self.partial=False

    def content(self):
        return (frozen(self.request),tuple(frozen(p) for p in self.profiles),frozen(self.tenant),frozen(self.lifetime),
                frozen(self.reservation) if self.reservation is not None else None,
                frozen(self.receipt) if self.receipt is not None else None,self.link,*self.epochs,
                self.revoked,self.complete,self.coherence)

    def observe(self,q,principal):
        self.calls+=1
        if self.fail:raise OSError("synthetic unavailable")
        if self.partial:return None
        self.serial+=1
        request,profiles,tenant,life,reservation,receipt,link,pe,te,re,revoked,complete,coherence=self.content()
        bundle=Bundle(request,profiles,tenant,life,reservation,receipt,link,pe,te,re,revoked,complete,
                      "synthetic-observation-"+str(self.serial),self.now,self.now+5,coherence)
        self.registry[bundle.observation_id]=(digest(q),digest(principal),digest(bundle),digest(self.content()))
        return bundle


class SyntheticVerifier:
    """Private issued-fact registry is test provenance, NEVER real gateway authentication."""
    def __init__(self,event,reader):
        self.facts=event_facts(event);self.reader=reader;self.now=NOW;self.calls=0
        self.principal=GatewayEvidence(ISSUER,"subject-a","tenant_a","client",1,1,1,NOW,NOW+5)
        self.gateway_boolean=False;self.bundle_boolean=False
        self.trusted_links={digest(reader.link)}

    def authenticate(self,facts,configuration,now):
        self.calls+=1
        need(digest(facts)==digest(self.facts),"UNISSUED_GATEWAY_FACTS")
        return self.principal

    def verify_gateway(self,facts,configuration,evidence,now):
        need(now==self.now and digest(facts)==digest(self.facts) and digest(evidence)==digest(self.principal),"STALE_OR_FORGED_GATEWAY")
        if self.gateway_boolean:return True
        return GatewayAttestation(digest(facts),digest(configuration),digest(evidence))

    def verify_bundle(self,q,principal,bundle,now):
        need(now==self.now and self.reader.registry.get(bundle.observation_id)==
            (digest(q),digest(principal),digest(bundle),digest(self.reader.content())),"STALE_OR_FORGED_BUNDLE")
        need(type(bundle.linkage) is LinkProof,"OWNERSHIP_PROVENANCE_REQUIRED")
        need(digest(bundle.linkage) in self.trusted_links,"UNISSUED_LINK_PROVENANCE")
        if self.bundle_boolean:return True
        return BundleAttestation(digest(q),digest(principal),digest(bundle))


def setup(http=False):
    event=synthetic_event(http);reader=SyntheticReader();verifier=SyntheticVerifier(event,reader)
    adapter=CancellationAccessAdapter(Configuration((ISSUER,)),reader,verifier)
    return event,reader,verifier,adapter,reader.query


def rows(reader):return deepcopy((reader.request,reader.profiles,reader.tenant,reader.lifetime,reader.reservation,reader.receipt,reader.link))


class CancellationAccessTests(unittest.TestCase):
    def test_valid_rest_gateway_customer_linkage_is_inactive_and_non_mutating(self):
        event,r,v,a,q=setup();before=rows(r);result=a.observe(event,q,NOW)
        self.assertEqual(result.bindings,r.link.bindings);self.assertFalse(result.activation_ready)
        self.assertIn("REAL_GATEWAY_AND_IDENTITY_VERIFIER_PENDING",result.blockers)
        self.assertEqual(a.verify_current(result,NOW),result);self.assertEqual(rows(r),before)
        self.assertIs(type(thaw(result.bundle.request)["unknown"]["keep"]),Decimal)

    def test_http_jwt_claims_shape_is_supported_but_not_self_authenticating(self):
        event,r,v,a,q=setup(True);self.assertEqual(a.observe(event,q,NOW).principal.subject,"subject-a")
        event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]="unissued"
        with self.assertRaises(AccessError):a.observe(event,q,NOW)

    def test_missing_wrong_issuer_and_unconfigured_issuer_deny(self):
        for issuer in (None,"","https://other.example.invalid","http://issuer.invalid"):
            event,r,v,a,q=setup();claims=event["requestContext"]["authorizer"]["claims"]
            if issuer is None:del claims["iss"]
            else:claims["iss"]=issuer
            with self.assertRaises(AccessError):a.observe(event,q,NOW)
            self.assertEqual(r.calls,0)
        event,r,v,a,q=setup();a.configuration=Configuration(("https://other.example.invalid",))
        with self.assertRaisesRegex(AccessError,"ISSUER"):a.observe(event,q,NOW)

    def test_missing_invalid_or_wrong_subject_denies_before_reads(self):
        for subject in (None,"",{},False,"wrong-subject"):
            event,r,v,a,q=setup();claims=event["requestContext"]["authorizer"]["claims"]
            claims["sub"]=subject
            with self.assertRaises(AccessError):a.observe(event,q,NOW)
            self.assertEqual(r.calls,0)

    def test_forged_event_flags_and_top_level_claims_are_not_gateway_proof(self):
        event,r,v,a,q=setup()
        forged={"verified":True,"role":"client","claims":deepcopy(event["requestContext"]["authorizer"]["claims"])}
        with self.assertRaises(AccessError):a.observe(forged,q,NOW)
        self.assertEqual(r.calls,0)

    def test_attested_gateway_principal_must_still_match_subject_tenant_and_customer_role(self):
        for delta in ({"subject":"other"},{"tenant":"tenant_b"},{"role":"owner"},{"role":"staff"},{"role":"admin"}):
            event,r,v,a,q=setup();v.principal=replace(v.principal,**delta)
            with self.assertRaises(AccessError):a.observe(event,q,NOW)
            self.assertEqual(r.calls,0)
        event,r,v,a,q=setup();v.principal=True
        with self.assertRaisesRegex(AccessError,"GATEWAY_PROOF"):a.observe(event,q,NOW)

    def test_client_body_role_and_credentials_are_not_retained_or_authoritative(self):
        event,r,v,a,q=setup();expected=event_facts(event)
        event["body"]={"role":"owner","subject":"other","verified":True};event["role"]="admin"
        event["headers"]={"Authorization":"SYNTHETIC-NOT-A-CREDENTIAL"}
        self.assertEqual(event_facts(event),expected)
        result=a.observe(event,q,NOW);self.assertEqual(result.principal.role,"client")
        self.assertNotIn("Authorization",repr(result));self.assertNotIn("SYNTHETIC-NOT-A-CREDENTIAL",repr(result))

    def test_dual_role_admin_staff_owner_unknown_and_duplicate_groups_deny(self):
        for groups in (["owner"],["admin"],["staff"],["unknown"],["client","owner"],["client","client"],[],None,True):
            event,r,v,a,q=setup();event["requestContext"]["authorizer"]["claims"]["cognito:groups"]=groups
            v.facts=event_facts(event)
            with self.assertRaisesRegex(AccessError,"CUSTOMER_ROLE"):a.observe(event,q,NOW)
            self.assertEqual(r.calls,0)

    def test_existing_comma_string_customer_group_maps_explicitly(self):
        event,r,v,a,q=setup();event["requestContext"]["authorizer"]["claims"]["cognito:groups"]="client"
        v.facts=event_facts(event);self.assertEqual(a.observe(event,q,NOW).principal.role,"client")

    def test_rest_and_jwt_ambiguity_or_malformed_authorizer_denies(self):
        event,r,v,a,q=setup();claims=event["requestContext"]["authorizer"]["claims"]
        event["requestContext"]["authorizer"]["jwt"]={"claims":claims}
        with self.assertRaisesRegex(AccessError,"AMBIGUOUS"):a.observe(event,q,NOW)
        for authorizer in (None,True,[],{"claims":True},{"jwt":"bad"}):
            with self.assertRaises(AccessError):a.observe({"requestContext":{"authorizer":authorizer}},q,NOW)

    def test_email_only_or_unverified_email_match_never_links_subject(self):
        event,r,v,a,q=setup();claims=event["requestContext"]["authorizer"]["claims"]
        del claims["sub"];claims.update(email="synthetic@example.invalid",email_verified=True)
        v.facts=event_facts(event);v.principal=replace(v.principal,subject="")
        with self.assertRaises(AccessError):a.observe(event,q,NOW)
        event,r,v,a,q=setup();r.profiles[0].pop("cognito_sub");r.profiles[0]["email"]="opaque-binding"
        with self.assertRaisesRegex(AccessError,"SUBJECT_PROFILE"):a.observe(event,q,NOW)

    def test_duplicate_zero_and_ambiguous_subject_profile_results_deny(self):
        for profiles in ([],["duplicate"],["other-subject"]):
            event,r,v,a,q=setup()
            if profiles==[]:r.profiles=[]
            elif profiles==["duplicate"]:r.profiles.append(deepcopy(r.profiles[0]))
            else:r.profiles[0]["cognito_sub"]="other"
            with self.assertRaises(AccessError):a.observe(event,q,NOW)

    def test_incomplete_profile_lookup_or_unverified_provenance_denies(self):
        event,r,v,a,q=setup();r.complete=False
        with self.assertRaisesRegex(AccessError,"INCOMPLETE"):a.observe(event,q,NOW)
        event,r,v,a,q=setup();r.link=None
        with self.assertRaisesRegex(AccessError,"PROVENANCE_REQUIRED"):a.observe(event,q,NOW)

    def test_wrong_tenant_client_request_and_stable_operation_query_binding(self):
        for field,value in (("tenant","tenant_b"),("client_id","other-client"),("request_id","other-request")):
            event,r,v,a,q=setup()
            with self.assertRaises(AccessError):a.observe(event,replace(q,**{field:value}),NOW)
        event,r,v,a,q=setup();result=a.observe(event,q,NOW)
        for field in ("operation","reason"):
            with self.assertRaises(AccessError):a.verify_current(replace(result,query=replace(q,**{field:"changed"})),NOW)

    def test_absent_null_wrong_company_never_uses_tenant_fallback(self):
        for value in (None,"tenant_b","ABSENT"):
            event,r,v,a,q=setup()
            if value=="ABSENT":del r.request["company_id"]
            else:r.request["company_id"]=value
            with self.assertRaisesRegex(AccessError,"EXACT_BOOKING"):a.observe(event,q,NOW)

    def test_tenant_inactive_unknown_null_or_bypass_values_are_denied(self):
        for delta in ({"is_active":False},{"is_active":None},{"is_active":1},{"subscription_status":"suspended"},{"subscription_status":None}):
            event,r,v,a,q=setup();r.tenant.update(delta);r.tenant["protected_admin_bypass"]=True
            with self.assertRaisesRegex(AccessError,"ACTIVE_TENANT"):a.observe(event,q,NOW)
        event,r,v,a,q=setup();r.tenant={}
        with self.assertRaises(AccessError):a.observe(event,q,NOW)

    def test_profile_wrong_tenant_key_inactive_and_subject_denies(self):
        for delta in ({"company_id":"tenant_b"},{"PK":"COMPANY#tenant_b"},{"SK":"CLIENT#other"},{"is_active":False},{"is_active":1},{"cognito_sub":None}):
            event,r,v,a,q=setup();r.profiles[0].update(delta)
            with self.assertRaises(AccessError):a.observe(event,q,NOW)

    def test_revocation_and_stale_or_malformed_epochs_deny(self):
        event,r,v,a,q=setup();r.revoked=True
        with self.assertRaisesRegex(AccessError,"REVOKED"):a.observe(event,q,NOW)
        for epochs in ((2,1,1),(1,2,1),(1,1,2),(True,1,1),(1,1.0,1),(1,1,Decimal("1"))):
            event,r,v,a,q=setup();r.epochs=epochs
            with self.assertRaises(AccessError):a.observe(event,q,NOW)

    def test_principal_epoch_types_and_lease_are_strict(self):
        for delta in ({"principal_epoch":True},{"tenant_epoch":1.0},{"revocation_epoch":Decimal("1")},{"observed_at":True},{"valid_until":9}):
            event,r,v,a,q=setup();v.principal=replace(v.principal,**delta)
            with self.assertRaises(AccessError):a.observe(event,q,NOW)
        event,r,v,a,q=setup()
        with self.assertRaises(AccessError):a.observe(event,q,True)

    def test_lease_expiry_and_current_security_change_invalidate_retained_evidence(self):
        event,r,v,a,q=setup();result=a.observe(event,q,NOW)
        with self.assertRaises(AccessError):a.verify_current(result,NOW+6)
        for mutation in ("epoch","revoked","tenant"):
            event,r,v,a,q=setup();result=a.observe(event,q,NOW)
            if mutation=="epoch":v.principal=replace(v.principal,principal_epoch=2)
            elif mutation=="revoked":r.revoked=True
            else:r.tenant["is_active"]=False
            with self.assertRaises(AccessError):a.verify_current(result,NOW)

    def test_missing_null_malformed_ownership_fields_deny_without_mutation(self):
        for field in ("client_email","cognito_sub","linked_client_profile_id"):
            for value in (None,"",{},[],True,42):
                event,r,v,a,q=setup();r.request[field]=value;before=rows(r)
                with self.assertRaises(AccessError):a.observe(event,q,NOW)
                self.assertEqual(rows(r),before)
        event,r,v,a,q=setup();del r.request["cognito_sub"]
        with self.assertRaises(AccessError):a.observe(event,q,NOW)

    def test_changed_removed_or_null_identity_after_observation_refuses(self):
        for field in ("cognito_sub","linked_client_profile_id","client_email"):
            for value in (None,{},"other","ABSENT"):
                event,r,v,a,q=setup();result=a.observe(event,q,NOW)
                if value=="ABSENT":del r.request[field]
                else:r.request[field]=value
                before=rows(r)
                with self.assertRaisesRegex(AccessError,"STALE_OR_FORGED"):a.verify_current(result,NOW)
                self.assertEqual(rows(r),before)

    def test_revision_lifetime_reservation_receipt_and_linkage_changes_invalidate_snapshot(self):
        for change in ("revision","life","reservation","receipt","profile","link"):
            event,r,v,a,q=setup();result=a.observe(event,q,NOW)
            if change=="revision":r.request["legacy_write_revision"]=2
            elif change=="life":r.lifetime["retired"]=True
            elif change=="reservation":r.reservation={"PK":"protected"}
            elif change=="receipt":r.receipt={"commit_state":"COMMITTED"}
            elif change=="profile":r.profiles=[]
            else:r.link=replace(r.link,provenance_id="other")
            with self.assertRaises(AccessError):a.verify_current(result,NOW)

    def test_linked_profile_mismatch_requires_exact_verified_provenance(self):
        event,r,v,a,q=setup();r.request["linked_client_profile_id"]="other"
        with self.assertRaises(AccessError):a.observe(event,q,NOW)
        event,r,v,a,q=setup();r.profiles[0].update(client_id="profile-b",SK="CLIENT#profile-b")
        r.request["linked_client_profile_id"]="profile-b"
        with self.assertRaisesRegex(AccessError,"PROVENANCE_BINDING"):a.observe(event,q,NOW)
        r.link=replace(r.link,profile_id="profile-b",bindings=(("cognito_sub","subject-a"),("linked_client_profile_id","profile-b")))
        with self.assertRaisesRegex(AccessError,"UNISSUED_LINK_PROVENANCE"):a.observe(event,q,NOW)
        v.trusted_links.add(digest(r.link))  # Explicit independent synthetic authority, not a reader flag.
        result=a.observe(event,q,NOW);self.assertEqual(result.bundle.linkage.profile_id,"profile-b")
        self.assertEqual(r.request["client_id"],"client-a")

    def test_verified_subject_profile_link_can_fence_booking_without_booking_subject_field(self):
        event,r,v,a,q=setup();del r.request["cognito_sub"]
        r.link=replace(r.link,bindings=(("linked_client_profile_id","client-a"),))
        v.trusted_links.add(digest(r.link));before=rows(r)
        result=a.observe(event,q,NOW)
        self.assertEqual(result.bindings,(("linked_client_profile_id","client-a"),));self.assertEqual(rows(r),before)

    def test_wrong_linkage_actor_issuer_operation_target_or_revision_denies(self):
        for delta in ({"issuer":"https://other.invalid"},{"subject":"other"},{"tenant":"tenant_b"},{"client_id":"other"},
                      {"request_id":"other"},{"incarnation":"other"},{"revision":2},{"revision":True},{"revision":1.0},{"provenance_id":""}):
            event,r,v,a,q=setup();r.link=replace(r.link,**delta)
            with self.assertRaises(AccessError):a.observe(event,q,NOW)

    def test_linkage_numeric_equivalence_is_rejected_at_typed_evidence_boundary(self):
        event,r,v,a,q=setup();r.link=replace(r.link,revision=True);v.trusted_links.add(digest(r.link))
        with self.assertRaisesRegex(AccessError,"CANONICAL_INTEGER"):a.observe(event,q,NOW)
        for revision in (1.0,Decimal("1")):
            event,r,v,a,q=setup();r.link=replace(r.link,revision=revision)
            with self.assertRaisesRegex(AccessError,"EVIDENCE_TYPE"):a.observe(event,q,NOW)

    def test_provenance_revocation_invalidates_retained_access_without_data_mutation(self):
        event,r,v,a,q=setup();result=a.observe(event,q,NOW);before=rows(r);v.trusted_links.clear()
        with self.assertRaisesRegex(AccessError,"UNISSUED_LINK_PROVENANCE"):a.verify_current(result,NOW)
        self.assertEqual(rows(r),before)

    def test_email_only_empty_duplicate_and_mismatched_binding_fences_deny(self):
        for bindings in ((),(("client_email","opaque-binding"),),(("cognito_sub","other"),),
                         (("cognito_sub","subject-a"),("cognito_sub","subject-a")),(("unsupported","subject-a"),)):
            event,r,v,a,q=setup();r.link=replace(r.link,bindings=bindings)
            with self.assertRaises(AccessError):a.observe(event,q,NOW)

    def test_unversioned_missing_incarnation_and_invalid_numeric_records_deny(self):
        for field in ("record_incarnation","legacy_write_revision"):
            event,r,v,a,q=setup();del r.request[field]
            with self.assertRaises(AccessError):a.observe(event,q,NOW)
        for value in (True,1.0,"1",0,-1,Decimal("1.5"),Decimal("NaN"),Decimal("Infinity")):
            event,r,v,a,q=setup();r.request["legacy_write_revision"]=value
            with self.assertRaises(AccessError):a.observe(event,q,NOW)

    def test_integral_db_decimal_revision_is_explicitly_normalized(self):
        event,r,v,a,q=setup();r.request["legacy_write_revision"]=Decimal("1")
        result=a.observe(event,q,NOW);self.assertIs(type(result.bundle.linkage.revision),int)
        self.assertIs(type(thaw(result.bundle.request)["legacy_write_revision"]),Decimal)

    def test_only_initial_canonical_source_statuses_are_candidates(self):
        for status in ("APPROVED","ASSIGNED"):
            event,r,v,a,q=setup();r.request["status"]=status;self.assertFalse(a.observe(event,q,NOW).activation_ready)
        for status in ("BOOKED","SCHEDULED","JOB_CREATED","CANCELLATION_DENIED","CANCELLED","COMPLETED","CANCELLATION_REQUESTED",None,"unknown"):
            event,r,v,a,q=setup();r.request["status"]=status
            with self.assertRaisesRegex(AccessError,"INITIAL_STATUS"):a.observe(event,q,NOW)

    def test_partial_canonical_marker_lifetime_and_reservation_conflicts_deny(self):
        for change in ("marker","missing-life","retired","wrong-life","expiring","reservation"):
            event,r,v,a,q=setup()
            if change=="marker":r.request["assigned_worker_id"]=None
            elif change=="missing-life":r.lifetime={}
            elif change=="retired":r.lifetime["retired"]=True
            elif change=="wrong-life":r.lifetime["incarnation"]="different"
            elif change=="expiring":r.lifetime["ttl"]=None
            else:r.reservation={}
            with self.assertRaises(AccessError):a.observe(event,q,NOW)

    def test_prepared_or_stored_receipt_is_never_accepted_as_commit_evidence(self):
        for receipt in ({},{"commit_state":"COMMITTED"},{"binding":"prepared-only","source_revision":1}):
            event,r,v,a,q=setup();r.receipt=receipt;before=rows(r)
            with self.assertRaisesRegex(AccessError,"REPLAY_ADAPTER_REQUIRED"):a.observe(event,q,NOW)
            self.assertEqual(rows(r),before)

    def test_reader_failure_partial_and_incoherent_observations_fail_closed(self):
        event,r,v,a,q=setup();r.fail=True
        with self.assertRaises(OSError):a.observe(event,q,NOW)
        event,r,v,a,q=setup();r.partial=True
        with self.assertRaisesRegex(AccessError,"COMPLETE_OBSERVATION"):a.observe(event,q,NOW)
        event,r,v,a,q=setup();r.coherence="SAME_ID_ONLY"
        with self.assertRaisesRegex(AccessError,"INCOMPLETE"):a.observe(event,q,NOW)

    def test_boolean_and_fabricated_verifier_results_are_not_attestations(self):
        for stage in ("gateway","bundle"):
            event,r,v,a,q=setup();setattr(v,stage+"_boolean",True)
            with self.assertRaisesRegex(AccessError,"ATTESTATION"):a.observe(event,q,NOW)
        event,r,v,a,q=setup();result=a.observe(event,q,NOW)
        forged=replace(result,bundle=replace(result.bundle,request=frozen(thaw(result.bundle.request)|{"status":"APPROVED"})))
        with self.assertRaises(AccessError):a.verify_current(forged,NOW)

    def test_verifier_dependencies_cannot_be_omitted_or_replaced_with_flags(self):
        event,r,v,a,q=setup()
        for verifier in (None,True,{"verified":True}):
            with self.assertRaisesRegex(AccessError,"DEPENDENCIES"):CancellationAccessAdapter(Configuration((ISSUER,)),r,verifier)

    def test_source_is_unwired_stdlib_without_sdk_or_network_execution(self):
        root=Path(__file__).resolve().parents[2];own=root/"src/backend/common/cancellation_access_adapter.py"
        source=own.read_text(encoding="utf-8");tree=ast.parse(source)
        allowed={"dataclasses","decimal","hashlib","json","re","typing","urllib"}
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):self.assertTrue(all(n.name.split('.')[0] in allowed for n in node.names))
            elif isinstance(node,ast.ImportFrom):self.assertIn(node.module.split('.')[0],allowed)
        for path in (root/"src/backend").rglob('*.py'):
            if path!=own:self.assertNotIn("cancellation_access_adapter",path.read_text(encoding="utf-8"))
        with patch.object(socket.socket,"connect",side_effect=AssertionError("NETWORK_FORBIDDEN")):
            event,r,v,a,q=setup();before=rows(r);result=a.observe(event,q,NOW);a.verify_current(result,NOW)
            self.assertEqual(rows(r),before)

    def test_actual_legacy_auth_and_db_characterization_is_not_trusted_adapter_authority(self):
        root=Path(__file__).resolve().parents[2]/"src/backend"
        auth=(root/"common/auth.py").read_text(encoding="utf-8")
        tree=ast.parse(auth);functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        access=ast.get_source_segment(auth,functions["require_client_booking_access"])
        self.assertIn("booking_email == user_email",access)
        resolver=ast.get_source_segment(auth,functions["resolve_client_identity"])
        self.assertIn("client.get('cognito_sub') == cognito_sub",resolver)
        self.assertIn("email_verified",resolver)
        entitlement=(root/"common/entitlement.py").read_text(encoding="utf-8")
        self.assertIn("_is_bypass_active(event)",entitlement);self.assertIn("_get_entitlement_safely(company_id)",entitlement)
        db=(root/"common/db.py").read_text(encoding="utf-8")
        self.assertIn("table.get_item(Key=",db);self.assertNotIn("ConsistentRead",db)

    def test_structural_parent_observation_and_preparation_without_commit_or_enrollment(self):
        from datetime import datetime,timezone
        event,r,v,a,q=setup();evidence=a.observe(event,q,NOW);before=rows(r)
        pq=parent.Query(q.tenant,q.client_id,q.request_id,evidence.principal.issuer,evidence.principal.subject,"client",q.operation,q.reason)
        pg=evidence.principal
        principal=parent.Principal(pg.issuer,pg.subject,pg.tenant,pg.role,parent.freeze(dict(evidence.bindings)),
                                   pg.principal_epoch,pg.tenant_epoch,pg.revocation_epoch,True,False)
        b=evidence.bundle
        observation=parent.Observation(pq.binding(),principal,parent.freeze(thaw(b.request)),parent.freeze(thaw(b.lifetime)),None,None,
                                       b.observation_id,b.observed_at,b.valid_until,b.coherence)
        class TestOnlyBridge:
            def verify_observation(self,query,obs,now):
                a.verify_current(evidence,now)
                need(parent.fingerprint(query)==parent.fingerprint(pq) and parent.fingerprint(obs)==parent.fingerprint(observation),"BRIDGE_BINDING")
                return parent.ObservationAttestation(parent.fingerprint(query),parent.fingerprint(obs),obs.observation_id,
                                                     pg.principal_epoch,pg.tenant_epoch,pg.revocation_epoch)
        bridge=TestOnlyBridge()
        self.assertEqual(parent.validate_observation(pq,observation,bridge,NOW)["client_id"],q.client_id)
        cmd=parent.prepare_commit(pq,observation,bridge,NOW,datetime(2026,10,31,12,tzinfo=timezone.utc),"ASSIGNED","DESIGN_ONLY_TEST")
        self.assertIn("INACTIVE_NO_RUNTIME",cmd.blockers);self.assertEqual(rows(r),before)
        r.request["legacy_write_revision"]=2
        with self.assertRaises(AccessError):parent.validate_observation(pq,observation,bridge,NOW)