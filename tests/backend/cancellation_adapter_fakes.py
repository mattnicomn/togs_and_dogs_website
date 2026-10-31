"""TEST ONLY synthetic provenance registry and atomic in-memory commit port.

No SDK client, AWS service, network, provider, credential or file persistence.
Parent contract/expressions are composed only in tests, preserving unwired source.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timezone
from boto3.dynamodb.types import TypeDeserializer
from common.cancellation_adapter_foundation import (
    AdapterError,Query,Principal,Observation,ObservationAttestation,OutcomeAttestation,CommitReport,
    freeze,thaw,fingerprint,require,revision,validate_command,raw_digest,
)
from common.cancellation_submission_contract import (
    Submission,BookingAccess,StatusAssumption,parse_snapshot,prepare,transaction,
)
from test_cancellation_submission_contract import updated
from test_worker_identity_expression_behavior import evaluates

STAMP=datetime(2026,10,31,12,tzinfo=timezone.utc)


def query():return Query("tenant_a","client-a","request-a","https://issuer.example.invalid","subject-a","client","operation-a","synthetic reason")


def fixture():
    q=query()
    request={"PK":q.key()[0],"SK":q.key()[1],"company_id":q.tenant,"client_id":q.client_id,"request_id":q.request_id,
             "record_incarnation":"life-a","legacy_write_revision":1,"status":"ASSIGNED","start_date":"2026-11-01",
             "client_email":"opaque-owned-binding","audit_log":[{"action":"old"}],"unknown":{"preserve":[1,2]}}
    lifetime={"PK":"LIFETIME#"+q.token(),"SK":"PERMANENT","incarnation":"life-a","retired":False}
    return q,request,lifetime


class State:
    def __init__(self):
        q,request,lifetime=fixture()
        self.rows={q.key():request,("LIFETIME#"+q.token(),"PERMANENT"):lifetime,
                   ("JOB#other","REQ#other"):{"PK":"JOB#other","SK":"REQ#other","status":"ASSIGNED"},
                   ("PET#other","CLIENT#other"):{"PK":"PET#other","SK":"CLIENT#other"}}
        self.committed={}
        self.attempts={}
        self.effects=[]
        self.security={"principal_epoch":1,"tenant_epoch":1,"revocation_epoch":1,"active":True,"revoked":False,
            "trusted_issuer":"https://issuer.example.invalid","subject":"subject-a","tenant":"tenant_a","role":"client",
            "bindings":{"client_email":"opaque-owned-binding"}}


class FakeAuthority:
    SECURITY_FIELDS={"principal_epoch","tenant_epoch","revocation_epoch","active","revoked","trusted_issuer","subject","tenant","role","bindings"}

    def __init__(self,state):
        self.state=state;self.now=10;self.issued={};self.reports={};self.serial=0

    def __getattr__(self,name):
        if name in self.SECURITY_FIELDS:return self.state.security[name]
        raise AttributeError(name)

    def __setattr__(self,name,value):
        if name in self.SECURITY_FIELDS:self.state.security[name]=value
        else:object.__setattr__(self,name,value)

    def observe(self,q):
        # Single copied snapshot models coherence; no claim of real database isolation.
        rows=deepcopy(self.state.rows);self.serial+=1
        p=Principal(self.trusted_issuer,self.subject,self.tenant,self.role,freeze(self.bindings),self.principal_epoch,
                    self.tenant_epoch,self.revocation_epoch,self.active,self.revoked)
        o=Observation(q.binding(),p,freeze(rows[q.key()]) if q.key() in rows else None,
            freeze(rows[("LIFETIME#"+q.token(),"PERMANENT")]) if ("LIFETIME#"+q.token(),"PERMANENT") in rows else None,
            freeze(rows[("RESERVATION#"+q.token(),"PERMANENT")]) if ("RESERVATION#"+q.token(),"PERMANENT") in rows else None,
            freeze(rows[("CANCEL_SUBMISSION#"+q.tenant+"#"+q.operation,"RECEIPT")]) if ("CANCEL_SUBMISSION#"+q.tenant+"#"+q.operation,"RECEIPT") in rows else None,
            "observation-"+str(self.serial),self.now,self.now+5,"COHERENT_SNAPSHOT")
        self.issued[o.observation_id]=(fingerprint(q),fingerprint(o))
        return o

    def verify_observation(self,q,o,now):
        require(now==self.now,"UNTRUSTED_CLOCK")
        require(self.issued.get(o.observation_id)==(fingerprint(q),fingerprint(o)),"FORGED_OR_MISSING_OBSERVATION")
        p=o.principal
        require((p.issuer,p.subject,p.tenant,p.role,p.identity_bindings)==
                (self.trusted_issuer,self.subject,self.tenant,self.role,freeze(self.bindings)),"STALE_PRINCIPAL_BINDING")
        require((p.principal_epoch,p.tenant_epoch,p.revocation_epoch)==
                (self.principal_epoch,self.tenant_epoch,self.revocation_epoch),"STALE_SECURITY_EPOCH")
        require(self.active is True and self.revoked is False,"CURRENT_AUTHORITY_DENIED")
        if o.receipt is not None:
            require(self.state.committed.get(q.binding())==fingerprint(o.receipt),"UNPROVEN_OPERATION_COMMIT")
        return ObservationAttestation(fingerprint(q),fingerprint(o),o.observation_id,p.principal_epoch,p.tenant_epoch,p.revocation_epoch)

    def issue_report(self,command,state,observation=None,quiescent=False):
        report=CommitReport(command.query.binding(),fingerprint(command),state,observation,state=="REFUSED",quiescent)
        self.reports[fingerprint(report)]=(command.query.binding(),fingerprint(command))
        return report

    def verify_outcome(self,command,report,now):
        require(now==self.now and self.active is True and self.revoked is False,"OUTCOME_AUTHORITY_DENIED")
        q=command.query
        require((q.issuer,q.subject,q.tenant,q.role)==(self.trusted_issuer,self.subject,self.tenant,self.role),"OUTCOME_PRINCIPAL_BINDING")
        require(self.reports.get(fingerprint(report))==(command.query.binding(),fingerprint(command)),"FORGED_OUTCOME")
        return OutcomeAttestation(report.binding,fingerprint(command),fingerprint(report))


class FakeCommitPort:
    def __init__(self,state,authority):self.state=state;self.authority=authority;self.calls=0

    def commit(self,command,mode="normal"):
        # All model checks precede any state publication or attempt bookkeeping.
        validate_command(command,self.authority,self.authority.now)
        q=command.query
        require(self.state.attempts.get(q.binding())!="UNKNOWN","NO_BLIND_RETRY")
        self.calls+=1
        receipt_key=("CANCEL_SUBMISSION#"+q.tenant+"#"+q.operation,"RECEIPT")
        existing=self.state.rows.get(receipt_key)
        if existing is not None:
            stored_binding=existing.get("binding")
            proven=self.state.committed.get(stored_binding)==fingerprint(freeze(existing))
            if proven and stored_binding==q.binding():
                return self.authority.issue_report(command,"COMMITTED",self.authority.observe(q))
            if proven:
                return self.authority.issue_report(command,"REFUSED",quiescent=True)
            self.state.attempts[q.binding()]="UNKNOWN"
            return self.authority.issue_report(command,"UNKNOWN")
        if mode=="timeout_before":
            self.state.attempts[q.binding()]="UNKNOWN"
            return self.authority.issue_report(command,"UNKNOWN")
        request=thaw(command.observation.request)
        p=command.observation.principal
        sub=Submission(q.tenant,q.client_id,q.request_id,q.issuer,q.subject,q.operation,q.reason)
        access=BookingAccess(q.tenant,q.client_id,q.request_id,q.issuer,q.subject,q.role,command.incarnation,
            command.expected_revision,tuple(p.identity_bindings.mapping().items()),True,True,True,True)
        plan=prepare(sub,access,parse_snapshot(request,sub),datetime.fromisoformat(command.submitted_at),
                     StatusAssumption(command.assumed_status,True,"SYNTHETIC_ONLY",command.assumption_reference))
        wire=transaction(plan,"offline-adapter")
        actual_receipt={k:TypeDeserializer().deserialize(v) for k,v in wire["TransactItems"][-1]["Put"]["Item"].items()}
        for k in ("source_revision","committed_revision"):actual_receipt[k]=revision(actual_receipt[k])
        require(freeze(actual_receipt)==command.stored_receipt,"PARENT_RECEIPT_COMPATIBILITY")
        proposed=deepcopy(self.state.rows)
        for entry in wire["TransactItems"]:
            kind,spec=next(iter(entry.items()));raw=spec.get("Key",spec.get("Item"));key=(raw["PK"]["S"],raw["SK"]["S"])
            if mode=="conflict" or not evaluates(spec,self.state.rows.get(key)):
                return self.authority.issue_report(command,"REFUSED",quiescent=True)
            if kind=="Update":proposed[key]=updated(spec,proposed[key])
            elif kind=="Put":proposed[key]={k:TypeDeserializer().deserialize(v) for k,v in spec["Item"].items()}
        expected=deepcopy(self.state.rows[q.key()]);patch=command.patch.mapping()
        expected.update(patch["set"])
        for field,entries in patch["append"].items():expected[field]=expected.get(field,[])+entries
        require(proposed[q.key()]==expected,"PARENT_PATCH_COMPATIBILITY")
        # Single publication point, including proposed durable commit journal.
        self.state.rows=proposed
        receipt_key=("CANCEL_SUBMISSION#"+q.tenant+"#"+q.operation,"RECEIPT")
        normalized=deepcopy(self.state.rows[receipt_key])
        for k in ("source_revision","committed_revision"):normalized[k]=revision(normalized[k])
        self.state.rows[receipt_key]=normalized
        self.state.committed[q.binding()]=fingerprint(freeze(normalized))
        if mode=="timeout_after":
            self.state.attempts[q.binding()]="UNKNOWN"
            return self.authority.issue_report(command,"UNKNOWN")
        self.state.attempts[q.binding()]="COMMITTED"
        return self.authority.issue_report(command,"COMMITTED",self.authority.observe(q))
