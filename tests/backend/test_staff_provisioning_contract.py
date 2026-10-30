"""Offline synthetic provisioning acceptance; no live clients or customer records."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))
import ast
import socket
from copy import deepcopy
import unittest
from dataclasses import replace
from unittest.mock import patch
from common.staff_provisioning_contract import (
    Request, Admission, Profile, Proof, State, RecoveryAuthorization, ProvisioningError, validate_request,
    stage, reservation_for, claim_effect, confirm_identity, confirm_group, activate, fail, retry_failed,
    assignment_disposition, owner_execution_eligible,
)
from staff_provisioning_fakes import (
    Store, Identity, Invitations, ISSUER, PersistenceRefused, UnknownOutcome,
    KnownExternalFailure, provision, dispatch_invitation,
)


def request(**changes):
    return replace(Request("tenant_a", "staff-a", "op_"+"1"*32, "a"*64, "inc_"+"1"*32,
                           "handle-a", ("1"*64, "2"*64)), **changes)


def admission(**changes):
    return replace(Admission("tenant_a", "actor-a", "owner", 1, 2, 0,
                             verified=True, current=True, protected_target=False), **changes)


def recovery(store, req, recovery_action, **changes):
    profile = store.data.rows[store.key(req)]
    context = RecoveryAuthorization(req.tenant, req.staff_id, req.operation, req.incarnation,
        profile.version, "actor-a", "owner", recovery_action, verified=True, current=True, protected_target=False)
    return replace(context, **changes)


class ProvisioningContractTests(unittest.TestCase):
    def setUp(self):
        self.store, self.identity, self.invites = Store(), Identity(), Invitations()
        self.req, self.actor = request(), admission()

    def run_flow(self):
        return provision(self.store, self.identity, self.req, self.actor)

    def test_write_first_active_and_outbox_after_confirmed_group(self):
        self.identity.after_create = lambda: self.assertIn("identity-intent", self.store.events)
        active = self.run_flow()
        self.assertEqual(active.state, State.ACTIVE)
        self.assertEqual(self.store.events, ["STAGED", "identity-intent", "identity-confirmed", "group-intent", "group-confirmed", "finalize"])
        self.assertEqual(self.invites.attempts, [])
        self.assertEqual(dispatch_invitation(self.store, self.invites, self.req), "SENT")
        self.assertEqual(len(self.invites.attempts), 1)

    def test_pending_and_failed_never_assignable(self):
        pending = stage(self.req, self.actor)
        for profile in (pending, replace(pending, state=State.IDENTITY), replace(pending, state=State.FAILED)):
            self.assertEqual(assignment_disposition(profile), "DENIED_INCOMPLETE")
            self.assertFalse(owner_execution_eligible(profile))
            self.assertFalse(profile.is_active or profile.is_assignable)
        self.assertFalse(owner_execution_eligible(self.run_flow()))

    def test_duplicate_operation_after_restart_has_no_extra_identity_or_invite(self):
        active = self.run_flow()
        self.store = Store(self.store.data)
        self.assertEqual(self.run_flow(), active)
        self.assertEqual(self.identity.calls, ["CREATE", "GROUP"])
        dispatch_invitation(self.store, self.invites, self.req)
        dispatch_invitation(Store(self.store.data), self.invites, self.req)
        self.assertEqual(len(self.invites.attempts), 1)

    def test_changed_payload_same_operation_conflicts(self):
        self.store.begin(self.req, self.actor)
        with self.assertRaisesRegex(ProvisioningError, "OPERATION_CONFLICT"):
            provision(self.store, self.identity, replace(self.req, payload_hash="b"*64), self.actor)
        self.assertEqual(self.identity.calls, [])

    def test_changed_staff_same_operation_conflicts(self):
        self.store.begin(self.req, self.actor)
        with self.assertRaisesRegex(ProvisioningError, "OPERATION_CONFLICT"):
            self.store.begin(replace(self.req, staff_id="staff-b"), self.actor)

    def test_other_actor_cannot_take_over_receipt(self):
        self.store.begin(self.req, self.actor)
        with self.assertRaisesRegex(ProvisioningError, "ACTOR_MISMATCH"):
            self.store.begin(self.req, replace(self.actor, actor_subject="actor-b"))

    def test_stale_concurrent_quota_request_cannot_overbook(self):
        self.store.begin(self.req, self.actor)
        other = request(staff_id="staff-b", operation="op_"+"2"*32, identity_handle="handle-b", uniqueness_keys=("3"*64,"4"*64))
        with self.assertRaisesRegex(ProvisioningError, "STALE_QUOTA"):
            self.store.begin(other, self.actor)
        self.store.begin(other, replace(self.actor, quota_revision=2))
        third = replace(other, staff_id="staff-c", operation="op_"+"3"*32, identity_handle="handle-c", uniqueness_keys=("5"*64,"6"*64))
        with self.assertRaisesRegex(ProvisioningError, "STAFF_LIMIT"):
            self.store.begin(third, replace(self.actor, quota_revision=3))

    def test_name_email_or_handle_uniqueness_is_not_read_only_precheck(self):
        self.store.begin(self.req, self.actor)
        for unique, handle in ((("1"*64,"3"*64),"handle-b"), (("3"*64,"2"*64),"handle-b"), (("3"*64,"4"*64),"handle-a")):
            other = request(staff_id="staff-b", operation="op_"+"2"*32, uniqueness_keys=unique, identity_handle=handle)
            with self.assertRaisesRegex(ProvisioningError, "DUPLICATE_STAFF"):
                self.store.begin(other, replace(self.actor, quota_revision=2))

    def test_legacy_active_count_consumes_capacity(self):
        self.store = Store(capacity=2, legacy_active=2)
        self.actor = admission(legacy_active_count=2)
        with self.assertRaisesRegex(ProvisioningError, "STAFF_LIMIT"):
            self.run_flow()
        self.assertEqual(self.identity.calls, [])

    def test_tier_downgrade_during_provisioning_blocks_activation(self):
        self.identity.after_create = lambda: setattr(self.store, "capacity", 0)
        with self.assertRaisesRegex(ProvisioningError, "STAFF_LIMIT"):
            self.run_flow()
        self.assertFalse(self.store.data.rows[("tenant_a","staff-a")].is_active)

    def test_persistence_refusal_precedes_any_cognito(self):
        self.store.refuse.add("stage")
        with self.assertRaises(PersistenceRefused):
            self.run_flow()
        self.assertEqual(self.identity.calls, [])
        self.assertEqual(self.store.data.rows, {})

    def test_intent_write_failure_precedes_cognito(self):
        self.store.refuse.add("identity-intent")
        with self.assertRaises(PersistenceRefused):
            self.run_flow()
        self.assertEqual(self.identity.calls, [])

    def test_cognito_success_identity_confirmation_failure_reconciles(self):
        self.store.refuse.add("identity-confirmed")
        with self.assertRaises(PersistenceRefused):
            self.run_flow()
        self.assertEqual(self.identity.calls, ["CREATE"])
        self.store.refuse.clear()
        self.assertEqual(self.run_flow().state, State.ACTIVE)
        self.assertEqual(self.identity.calls.count("CREATE"), 1)
        self.assertIn("RECONCILE_IDENTITY", self.identity.calls)

    def test_cognito_success_finalize_failure_retries_persistence_only(self):
        self.store.refuse.add("finalize")
        with self.assertRaises(PersistenceRefused):
            self.run_flow()
        self.assertEqual(self.store.data.outbox, {})
        self.assertFalse(self.store.data.rows[("tenant_a","staff-a")].is_assignable)
        self.store.refuse.clear()
        self.assertEqual(self.run_flow().state, State.ACTIVE)
        self.assertEqual(self.identity.calls, ["CREATE", "GROUP"])

    def test_group_success_later_write_failure_reconciles_membership(self):
        self.store.refuse.add("group-confirmed")
        with self.assertRaises(PersistenceRefused):
            self.run_flow()
        self.store.refuse.clear()
        self.assertEqual(self.run_flow().state, State.ACTIVE)
        self.assertEqual(self.identity.calls.count("GROUP"), 1)
        self.assertIn("RECONCILE_GROUP", self.identity.calls)

    def test_known_group_failure_is_failed_and_safe_retry(self):
        self.identity.group_failure = True
        with self.assertRaises(KnownExternalFailure):
            self.run_flow()
        self.assertEqual(self.store.data.rows[("tenant_a","staff-a")].state, State.FAILED)
        self.identity.group_failure = False
        self.assertEqual(self.run_flow().state, State.ACTIVE)
        self.assertEqual(self.identity.calls.count("CREATE"), 1)

    def test_unknown_create_timeout_never_blindly_recreates(self):
        self.identity.create_timeout = True
        with self.assertRaises(UnknownOutcome):
            self.run_flow()
        self.assertEqual(self.store.data.rows[("tenant_a","staff-a")].intent, "CREATE")
        self.assertEqual(self.run_flow().state, State.ACTIVE)
        self.assertEqual(self.identity.calls.count("CREATE"), 1)

    def test_unprovable_timeout_remains_incomplete(self):
        self.identity.create_timeout = True
        with self.assertRaises(UnknownOutcome):
            self.run_flow()
        self.identity.unknown_reconciliation = True
        with self.assertRaises(UnknownOutcome):
            self.run_flow()
        self.assertEqual(self.identity.calls.count("CREATE"), 1)
        self.assertFalse(self.store.data.rows[("tenant_a","staff-a")].is_active)
        self.assertEqual(self.store.data.outbox, {})

    def test_unknown_group_timeout_does_not_repeat_group_side_effect(self):
        self.identity.group_timeout = True
        with self.assertRaises(UnknownOutcome):
            self.run_flow()
        self.assertEqual(self.run_flow().state, State.ACTIVE)
        self.assertEqual(self.identity.calls.count("GROUP"), 1)

    def test_existing_identity_without_verified_ownership_never_links(self):
        self.req = request(mode="CREATE_OR_LINK")
        self.identity.identities[(self.req.tenant,self.req.identity_handle)] = self.identity.proof(request(operation="op_"+"2"*32))
        before = dict(self.identity.identities)
        with self.assertRaisesRegex(ProvisioningError, "OWNERSHIP_UNVERIFIED"):
            self.run_flow()
        self.assertEqual(self.identity.identities, before)
        self.assertNotIn("GROUP", self.identity.calls)

    def test_link_existing_requires_proof_not_email_match(self):
        self.req = request(mode="LINK_EXISTING", expected_subject="subject-handle-a")
        with self.assertRaisesRegex(ProvisioningError, "OWNERSHIP_UNVERIFIED"):
            self.run_flow()
        self.assertNotIn("CREATE", self.identity.calls)
        self.assertEqual(self.identity.groups, set())

    def test_verified_existing_link_uses_exact_operation_proof(self):
        self.req = request(mode="LINK_EXISTING", expected_subject="subject-handle-a")
        self.identity.existing_proofs[(self.req.tenant,self.req.identity_handle)] = self.identity.proof(self.req)
        self.assertEqual(self.run_flow().state, State.ACTIVE)
        self.assertEqual(self.identity.calls, ["VERIFY_EXISTING", "GROUP"])

    def test_create_or_link_verified_existing_identity(self):
        self.req = request(mode="CREATE_OR_LINK", expected_subject="subject-handle-a")
        proof = self.identity.proof(self.req)
        self.identity.identities[(self.req.tenant,self.req.identity_handle)] = proof
        self.identity.existing_proofs[(self.req.tenant,self.req.identity_handle)] = proof
        self.assertEqual(self.run_flow().state, State.ACTIVE)
        self.assertEqual(len(self.identity.identities), 1)

    def test_ownership_proof_wrong_tenant_subject_binding_or_issuer_rejected(self):
        self.req = request(mode="LINK_EXISTING", expected_subject="subject-handle-a")
        for field, value in (("tenant","tenant_b"),("operation","op_"+"2"*32),("staff_id","staff-b"),
                             ("issuer","https://other.example.invalid"),("incarnation","inc_"+"2"*32),
                             ("payload_hash","b"*64),("subject","other-subject"),("verified",False)):
            with self.subTest(field=field):
                store, identity = Store(), Identity()
                identity.existing_proofs[(self.req.tenant,self.req.identity_handle)] = replace(identity.proof(self.req), **{field:value})
                with self.assertRaises(ProvisioningError):
                    provision(store,identity,self.req,self.actor)
                self.assertNotIn("GROUP",identity.calls)

    def test_tenant_and_denied_roles_fail_before_external_effect(self):
        for actor in (admission(tenant="tenant_b"), admission(actor_role="staff"), admission(actor_role="client"),
                      admission(actor_role="unknown"), admission(verified=False), admission(current=False)):
            with self.assertRaises(ProvisioningError):
                provision(Store(),self.identity,self.req,actor)
        self.assertEqual(self.identity.calls, [])

    def test_admin_legacy_creation_role_remains_modeled(self):
        self.actor = admission(actor_role="admin")
        self.assertEqual(self.run_flow().state, State.ACTIVE)

    def test_privileged_target_role_stays_policy_pending(self):
        for role in ("owner","admin"):
            with self.assertRaisesRegex(ProvisioningError,"PRIVILEGED_ROLE_POLICY_PENDING"):
                provision(Store(),self.identity,request(target_role=role),self.actor)
        self.assertEqual(self.identity.calls, [])

    def test_protected_target_refused(self):
        with self.assertRaisesRegex(ProvisioningError,"PROTECTED_TARGET"):
            provision(self.store,self.identity,self.req,admission(protected_target=True))
        self.assertEqual(self.identity.calls, [])

    def test_reservation_and_null_marker_conflicts_precede_identity(self):
        key = self.store.key(self.req)
        self.store.data.reservations[key] = replace(reservation_for(self.req),incarnation="inc_"+"2"*32)
        with self.assertRaisesRegex(ProvisioningError,"IDENTITY_REUSE_DENIED"):
            self.run_flow()
        self.store = Store()
        self.store.data.markers.add(key)  # Presence-only marker, including NULL/malformed.
        with self.assertRaisesRegex(ProvisioningError,"CANONICAL_MARKER_CONFLICT"):
            self.run_flow()
        self.assertEqual(self.identity.calls, [])

    def test_marker_inserted_after_stage_prevents_group_and_activation(self):
        self.identity.after_create = lambda: self.store.data.markers.add(self.store.key(self.req))
        with self.assertRaisesRegex(ProvisioningError,"CANONICAL_MARKER_CONFLICT"):
            self.run_flow()
        self.assertEqual(self.identity.calls,["CREATE"])
        self.assertFalse(self.store.data.rows[self.store.key(self.req)].is_active)

    def test_revocation_during_identity_never_activates_or_invites(self):
        self.identity.after_create = lambda: self.store.revoke(self.req, recovery(self.store,self.req,"REVOKE"))
        with self.assertRaises(ProvisioningError):
            self.run_flow()
        self.assertFalse(self.store.data.rows[self.store.key(self.req)].is_active)
        self.assertEqual(self.store.data.outbox,{})

    def test_revocation_after_group_never_finalizes(self):
        self.identity.after_group = lambda: self.store.revoke(self.req, recovery(self.store,self.req,"REVOKE"))
        with self.assertRaises(ProvisioningError):
            self.run_flow()
        self.assertEqual(self.store.data.rows[self.store.key(self.req)].state, State.FAILED)
        self.assertEqual(self.store.data.outbox,{})

    def test_stale_concurrent_profile_transition_rejected(self):
        initial=self.store.begin(self.req,self.actor)
        updated=claim_effect(initial,initial.version,"CREATE")
        self.store.save(initial,updated,"identity-intent")
        with self.assertRaisesRegex(ProvisioningError,"STALE_PROFILE"):
            self.store.save(initial,updated,"identity-intent")

    def test_abandonment_preserves_external_identity_and_permanent_claims(self):
        self.store.refuse.add("finalize")
        with self.assertRaises(PersistenceRefused):
            self.run_flow()
        before=dict(self.identity.identities)
        self.store.abandon(self.req, recovery(self.store,self.req,"ABANDON"))
        self.assertEqual(self.identity.identities,before)
        self.assertIn(self.store.key(self.req),self.store.data.reservations)
        self.assertFalse(self.store.data.rows[self.store.key(self.req)].is_assignable)
        self.store.refuse.clear()
        with self.assertRaisesRegex(ProvisioningError,"MANUAL_RECOVERY_REQUIRED"):
            self.run_flow()

    def test_invitation_not_available_until_atomic_activation(self):
        self.store.begin(self.req,self.actor)
        with self.assertRaises(ProvisioningError):
            dispatch_invitation(self.store,self.invites,self.req)
        self.assertEqual(self.invites.attempts,[])

    def test_ambiguous_invitation_send_never_automatically_retried(self):
        self.run_flow()
        self.invites.timeout=True
        with self.assertRaises(UnknownOutcome):
            dispatch_invitation(self.store,self.invites,self.req)
        self.assertEqual(dispatch_invitation(Store(self.store.data),self.invites,self.req),"UNKNOWN")
        self.assertEqual(len(self.invites.attempts),1)

    def test_claimed_invitation_after_crash_requires_reconciliation(self):
        active=self.run_flow()
        self.store.claim_invitation(self.req,active.version)
        self.assertEqual(dispatch_invitation(self.store,self.invites,self.req),"INFLIGHT")
        self.assertEqual(self.invites.attempts,[])

    def test_concurrent_invitation_claims_and_stale_versions_refused(self):
        active=self.run_flow()
        with self.assertRaisesRegex(ProvisioningError,"STALE_INVITATION_PROFILE"):
            self.store.claim_invitation(self.req,active.version-1)
        self.store.claim_invitation(self.req,active.version)
        with self.assertRaisesRegex(ProvisioningError,"INVITATION_ALREADY_CLAIMED"):
            self.store.claim_invitation(self.req,active.version)

    def test_revocation_before_invitation_claim_refuses(self):
        self.run_flow()
        self.store.revoke(self.req, recovery(self.store,self.req,"REVOKE"))
        with self.assertRaises(ProvisioningError):
            dispatch_invitation(self.store,self.invites,self.req)
        self.assertEqual(self.invites.attempts,[])

    def test_legacy_profiles_are_delegated_unchanged(self):
        legacy={"staff_id":"legacy-staff","is_active":True,"is_assignable":True}
        before=dict(legacy)
        self.assertEqual(assignment_disposition(legacy),"LEGACY_PATH_REQUIRED")
        self.assertEqual(legacy,before)
        self.assertEqual(assignment_disposition(legacy|{"provisioning_state":None}),"PROVISIONING_CONTRACT_REQUIRED")

    def test_pending_profile_cannot_be_finalized_without_proof_and_group(self):
        pending=stage(self.req,self.actor)
        with self.assertRaisesRegex(ProvisioningError,"INCOMPLETE_PROVISIONING"):
            activate(pending,pending.version)

    def test_no_network_and_no_runtime_wiring(self):
        with patch.object(socket.socket,"connect",side_effect=AssertionError("NETWORK_FORBIDDEN")):
            self.assertEqual(self.run_flow().state,State.ACTIVE)
        root=Path(__file__).resolve().parents[2]
        source=root/"src/backend/common/staff_provisioning_contract.py"
        tree=ast.parse(source.read_text(encoding="utf-8"))
        allowed={"dataclasses","enum","re","urllib"}
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):self.assertTrue(all(x.name.split(".")[0] in allowed for x in node.names))
            if isinstance(node,ast.ImportFrom):self.assertIn(node.module.split(".")[0],allowed)
        for file in (root/"src").rglob("*.py"):
            if file!=source:self.assertNotIn("staff_provisioning_contract",file.read_text(encoding="utf-8"))

    def test_existing_link_without_approved_subject_is_not_a_lookup_by_email(self):
        with self.assertRaisesRegex(ProvisioningError,"APPROVED_SUBJECT_REQUIRED"):
            provision(self.store,self.identity,request(mode="LINK_EXISTING"),self.actor)
        self.assertEqual(self.identity.calls,[])

    def test_invitation_sent_but_ack_write_fails_never_duplicates(self):
        self.run_flow()
        self.store.refuse.add("invitation-ack")
        with self.assertRaises(PersistenceRefused):
            dispatch_invitation(self.store,self.invites,self.req)
        self.assertEqual(dispatch_invitation(Store(self.store.data),self.invites,self.req),"INFLIGHT")
        self.assertEqual(len(self.invites.attempts),1)

    def test_unknown_group_reconciliation_requires_manual_resolution(self):
        self.identity.group_timeout=True
        with self.assertRaises(UnknownOutcome):
            self.run_flow()
        self.identity.unknown_reconciliation=True
        with self.assertRaises(UnknownOutcome):
            self.run_flow()
        self.assertEqual(self.identity.calls.count("GROUP"),1)
        self.assertFalse(self.store.data.rows[self.store.key(self.req)].is_active)

    def test_changed_reservation_after_staging_denies_following_effect(self):
        def change():
            key=self.store.key(self.req)
            self.store.data.reservations[key]=replace(self.store.data.reservations[key],retired=True)
        self.identity.after_create=change
        with self.assertRaisesRegex(ProvisioningError,"RESERVATION_CONFLICT"):
            self.run_flow()
        self.assertEqual(self.identity.calls,["CREATE"])
        self.assertEqual(self.store.data.outbox,{})

    def test_strict_request_and_admission_fields(self):
        for bad in (request(mode=[]),request(payload_hash="bad"),request(assignable="true"),request(incarnation="bad")):
            with self.assertRaises(ProvisioningError):
                stage(bad,self.actor)
        for bad in (admission(quota_revision=True),admission(max_staff=True),admission(actor_role=[]),admission(legacy_active_count=-1)):
            with self.assertRaises(ProvisioningError):
                stage(self.req,bad)
        pending=stage(self.req,self.actor)
        with self.assertRaises(ProvisioningError):
            claim_effect(pending,True,"CREATE")


class CorrectiveProofAndRecoveryTests(unittest.TestCase):
    def setup_profile(self, before_group=False):
        store, identity = Store(), Identity()
        req, actor = request(), admission()
        store.refuse.add("group-intent" if before_group else "finalize")
        with self.assertRaises(PersistenceRefused):
            provision(store,identity,req,actor)
        store.refuse.clear()
        identity.calls.clear()
        return store,identity,req,actor,store.data.rows[store.key(req)]

    def bad_proofs(self, proof):
        for field,value in (("verified",False),("verified","true"),("tenant","tenant_b"),
                            ("operation","op_"+"2"*32),("staff_id","staff-b"),
                            ("incarnation","inc_"+"2"*32),("payload_hash","b"*64),
                            ("identity_handle","handle-b"),("subject","other-subject"),
                            ("issuer","https://other.example.invalid"),("evidence_revision",2),
                            ("evidence_revision",True),("evidence_revision",0)):
            yield field,value,replace(proof,**{field:value})

    def test_reloaded_invalid_proof_never_groups_or_activates(self):
        for field,value,_ in self.bad_proofs(Identity().proof(request())):
            with self.subTest(field=field,value=value):
                store,identity,req,actor,profile=self.setup_profile(before_group=True)
                bad=replace(profile,proof=replace(profile.proof,**{field:value}))
                store.data.rows[store.key(req)]=bad
                before=deepcopy(store.data)
                with self.assertRaises(ProvisioningError):
                    provision(store,identity,req,actor)
                self.assertEqual(identity.calls,[])
                self.assertEqual(store.data,before)
                self.assertFalse(store.data.rows[store.key(req)].is_active)
                self.assertEqual(store.data.outbox,{})

    def test_activation_revalidates_every_persisted_binding(self):
        store,identity,req,actor,profile=self.setup_profile()
        for field,value,bad_proof in self.bad_proofs(profile.proof):
            with self.subTest(field=field,value=value), self.assertRaises(ProvisioningError):
                activate(replace(profile,proof=bad_proof),profile.version,ISSUER)
        self.assertEqual(identity.calls,[])
        self.assertEqual(store.data.outbox,{})

    def test_group_claim_and_confirmation_revalidate_proof(self):
        store,identity,req,actor,profile=self.setup_profile(before_group=True)
        bad=replace(profile,proof=replace(profile.proof,verified=False))
        with self.assertRaises(ProvisioningError):
            claim_effect(bad,bad.version,"GROUP",ISSUER)
        intent=claim_effect(profile,profile.version,"GROUP",ISSUER)
        with self.assertRaises(ProvisioningError):
            confirm_group(replace(intent,proof=replace(intent.proof,tenant="tenant_b")),intent.version,intent.proof.subject,"staff",ISSUER)
        self.assertEqual(identity.calls,[])

    def test_no_implicit_trusted_issuer_on_resume_or_activation(self):
        store,identity,req,actor,profile=self.setup_profile()
        for issuer in (None,"http://issuer.example.invalid","https://user:password@issuer.example.invalid", "https://[invalid"):
            with self.assertRaises(ProvisioningError):
                activate(profile,profile.version,issuer)
        self.assertFalse(profile.is_active)

    def test_stale_subject_and_proof_revision_snapshots_refuse(self):
        store,identity,req,actor,profile=self.setup_profile()
        for delta in ({"confirmed_subject":"other-subject"},{"confirmed_subject":None},
                      {"proof_revision":2},{"proof_revision":True},{"proof_revision":0}):
            with self.assertRaises(ProvisioningError):
                activate(replace(profile,**delta),profile.version,ISSUER)

    def test_group_confirmation_is_bound_to_evidence_revision(self):
        store,identity,req,actor,profile=self.setup_profile()
        refreshed=replace(profile,proof=replace(profile.proof,evidence_revision=2),proof_revision=2)
        with self.assertRaisesRegex(ProvisioningError,"STALE_GROUP_PROOF"):
            activate(refreshed,refreshed.version,ISSUER)
        for delta in ({"group_subject":"other-subject"},{"group_role":"owner"},{"group_proof_revision":True}):
            with self.assertRaises(ProvisioningError):
                activate(replace(profile,**delta),profile.version,ISSUER)

    def test_valid_reload_finalizes_without_new_identity_effects(self):
        store,identity,req,actor,profile=self.setup_profile()
        active=provision(Store(store.data),identity,req,actor)
        self.assertEqual(active.state,State.ACTIVE)
        self.assertEqual(identity.calls,[])
        self.assertEqual(assignment_disposition(active,ISSUER),"PROFILE_READY_ONLY")
        self.assertFalse(owner_execution_eligible(active))

    def test_corrupt_active_proof_cannot_resume_or_invite(self):
        store,identity=Store(),Identity()
        req,actor=request(),admission()
        active=provision(store,identity,req,actor)
        store.data.rows[store.key(req)]=replace(active,proof=replace(active.proof,verified=False))
        before=deepcopy(store.data)
        invites=Invitations()
        with self.assertRaises(ProvisioningError):
            dispatch_invitation(store,invites,req)
        with self.assertRaises(ProvisioningError):
            assignment_disposition(store.data.rows[store.key(req)],ISSUER)
        self.assertEqual(invites.attempts,[])
        self.assertEqual(store.data,before)

    def recovery_fixture(self):
        store,identity=Store(),Identity()
        req,actor=request(),admission()
        provision(store,identity,req,actor)
        other=request(tenant="tenant_b",staff_id="staff-b",operation="op_"+"2"*32)
        provision(store,identity,other,admission(tenant="tenant_b"))
        return store,identity,req,actor

    def test_recovery_without_trusted_context_changes_nothing(self):
        for action in ("ABANDON","REVOKE"):
            store,identity,req,actor=self.recovery_fixture()
            before=deepcopy(store.data)
            with self.assertRaisesRegex(ProvisioningError,"TRUSTED_RECOVERY_REQUIRED"):
                getattr(store,action.lower())(req)
            self.assertEqual(store.data,before)

    def test_recovery_context_rejects_every_wrong_binding_without_changes(self):
        for action in ("ABANDON","REVOKE"):
            for field,value in (("tenant","tenant_b"),("staff_id","staff-b"),("operation","op_"+"2"*32),
                                ("incarnation","inc_"+"2"*32),("expected_version",1),("expected_version",True),
                                ("actor_subject","other-actor"),("actor_role","staff"),("actor_role","client"),
                                ("verified",False),("verified","true"),("current",False),("protected_target",True),
                                ("action","REVOKE" if action=="ABANDON" else "ABANDON")):
                with self.subTest(action=action,field=field,value=value):
                    store,identity,req,actor=self.recovery_fixture()
                    context=recovery(store,req,action,**{field:value})
                    before=deepcopy(store.data)
                    with self.assertRaises(ProvisioningError):
                        getattr(store,action.lower())(req,context)
                    self.assertEqual(store.data,before)

    def test_recovery_request_mismatch_cannot_target_same_staff(self):
        for action in ("ABANDON","REVOKE"):
            for delta in ({"operation":"op_"+"2"*32},{"incarnation":"inc_"+"2"*32},
                          {"payload_hash":"b"*64},{"identity_handle":"handle-b"}):
                store,identity,req,actor=self.recovery_fixture()
                before=deepcopy(store.data)
                with self.assertRaises(ProvisioningError):
                    getattr(store,action.lower())(replace(req,**delta),recovery(store,req,action))
                self.assertEqual(store.data,before)

    def test_recovery_wrong_key_or_tenant_leaves_all_profiles_intact(self):
        store,identity,req,actor=self.recovery_fixture()
        before=deepcopy(store.data)
        for target in (replace(req,tenant="tenant_b",staff_id="staff-b"), replace(req,staff_id="missing")):
            with self.assertRaises(ProvisioningError):
                store.abandon(target,recovery(store,req,"ABANDON"))
            self.assertEqual(store.data,before)

    def test_authorized_recovery_keeps_reservations_claims_and_unrelated_outbox(self):
        for action in ("ABANDON","REVOKE"):
            store,identity,req,actor=self.recovery_fixture()
            before=deepcopy(store.data)
            key=store.key(req); other=("tenant_b","staff-b")
            getattr(store,action.lower())(req,recovery(store,req,action))
            self.assertEqual(store.data.rows[key].state,State.FAILED)
            self.assertFalse(store.data.rows[key].is_active or store.data.rows[key].is_assignable)
            self.assertEqual(store.data.rows[other],before.rows[other])
            self.assertEqual(store.data.reservations,before.reservations)
            self.assertEqual(store.data.claims,before.claims)
            self.assertEqual(store.data.receipts,before.receipts)
            self.assertEqual(store.data.outbox[other],before.outbox[other])
            self.assertEqual(store.data.outbox[key]["state"],"CANCELLED")

    def test_stale_recovery_replay_does_not_change_failed_record(self):
        store,identity,req,actor=self.recovery_fixture()
        context=recovery(store,req,"ABANDON")
        store.abandon(req,context)
        before=deepcopy(store.data)
        with self.assertRaisesRegex(ProvisioningError,"STALE_RECOVERY"):
            store.abandon(req,context)
        self.assertEqual(store.data,before)

    def test_recovery_core_cannot_be_called_without_authority(self):
        store,identity,req,actor=self.recovery_fixture()
        profile=store.data.rows[store.key(req)]
        for reason in ("ABANDONED","REVOKED"):
            with self.assertRaisesRegex(ProvisioningError,"TRUSTED_RECOVERY_REQUIRED"):
                fail(profile,profile.version,reason)

    def test_retry_failed_requires_current_initiating_context_and_valid_proof(self):
        store,identity,req,actor,profile=self.setup_profile(before_group=True)
        failed=fail(profile,profile.version,"EXTERNAL_FAILURE")
        for context in (None,replace(actor,current=False),replace(actor,actor_subject="other-actor"),replace(actor,tenant="tenant_b")):
            with self.assertRaises(ProvisioningError):
                retry_failed(failed,failed.version,context,"actor-a",ISSUER)
        with self.assertRaises(ProvisioningError):
            retry_failed(replace(failed,proof=replace(failed.proof,verified=False)),failed.version,actor,"actor-a",ISSUER)

    def test_malformed_reservation_does_not_pass_boolean_equality(self):
        store,identity,req,actor,profile=self.setup_profile()
        key=store.key(req)
        store.data.reservations[key]=replace(store.data.reservations[key],retired=0)
        before=deepcopy(store.data)
        with self.assertRaisesRegex(ProvisioningError,"RESERVATION_CONFLICT"):
            store.revoke(req,recovery(store,req,"REVOKE"))
        self.assertEqual(store.data,before)
        self.assertEqual(identity.calls,[])
