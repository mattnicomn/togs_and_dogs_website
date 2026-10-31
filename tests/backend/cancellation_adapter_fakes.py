"""TEST ONLY synthetic provenance registry and atomic in-memory commit port.

No SDK client, AWS service, network, provider, credential or file persistence.
Parent contract/expressions are composed only in tests, preserving unwired source.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timezone
from boto3.dynamodb.types import TypeDeserializer
from common.cancellation_adapter_foundation import (
    AdapterError,RefusalUnresolved,Query,Principal,Observation,ObservationAttestation,OutcomeAttestation,CommitReport,
    freeze,thaw,fingerprint,require,revision,canonical_revision,validate_command,raw_digest,IDENTITY_FIELDS,MARKERS,
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
        self.journal={}
        self.effects=[]
        self.security={"principal_epoch":1,"tenant_epoch":1,"revocation_epoch":1,"active":True,"revoked":False,
            "trusted_issuer":"https://issuer.example.invalid","subject":"subject-a","tenant":"tenant_a","role":"client",
            "bindings":{"client_email":"opaque-owned-binding"}}


    def begin_attempt(self,q):
        key=(q.tenant,q.operation)
        previous=self.journal.get(key,{})
        require(previous.get("state") not in ("PENDING","UNKNOWN"),"NO_BLIND_RETRY")
        generation=previous.get("generation",0)+1
        self.journal[key]={"generation":generation,"attempt_id":"attempt-"+str(generation),
                           "binding":q.binding(),"state":"PENDING"}

    def finish_attempt(self,q,state):
        entry=self.journal[(q.tenant,q.operation)]
        require(entry["binding"]==q.binding() and entry["state"]=="PENDING","ATTEMPT_BINDING")
        entry["generation"]+=1;entry["state"]=state
        self.attempts[q.binding()]=state


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
        return self._verify_observation(q,o,now,True)

    def _verify_observation(self,q,o,now,check_current):
        require(now==self.now,"UNTRUSTED_CLOCK")
        require(self.issued.get(o.observation_id)==(fingerprint(q),fingerprint(o)),"FORGED_OR_MISSING_OBSERVATION")
        p=o.principal
        require((p.issuer,p.subject,p.tenant,p.role,p.identity_bindings)==
                (self.trusted_issuer,self.subject,self.tenant,self.role,freeze(self.bindings)),"STALE_PRINCIPAL_BINDING")
        current_epochs=(self.principal_epoch,self.tenant_epoch,self.revocation_epoch)
        for value in current_epochs:canonical_revision(value)
        require(fingerprint((p.principal_epoch,p.tenant_epoch,p.revocation_epoch))==
                fingerprint(current_epochs),"STALE_SECURITY_EPOCH")
        require(self.active is True and self.revoked is False,"CURRENT_AUTHORITY_DENIED")
        if check_current:
            # Fresh replay authorization checks selected persisted fields, not unrelated metadata.
            rows=deepcopy(self.state.rows)
            fields=("PK","SK","company_id","client_id","request_id","record_incarnation","legacy_write_revision","status","start_date",*IDENTITY_FIELDS,*MARKERS)
            def selected(row):
                return freeze({field:row[field] for field in fields if field in row}) if type(row) is dict else None
            require(fingerprint(selected(thaw(o.request)))==fingerprint(selected(rows.get(q.key()))),"STALE_PERSISTED_OBSERVATION")
            for old,key in ((o.lifetime,("LIFETIME#"+q.token(),"PERMANENT")),
                            (o.reservation,("RESERVATION#"+q.token(),"PERMANENT")),
                            (o.receipt,("CANCEL_SUBMISSION#"+q.tenant+"#"+q.operation,"RECEIPT"))):
                require(fingerprint(old)==fingerprint(freeze(rows[key]) if key in rows else None),"STALE_PERSISTED_OBSERVATION")
        if o.receipt is not None:
            require(self.state.committed.get(q.binding())==fingerprint(o.receipt),"UNPROVEN_OPERATION_COMMIT")
        return ObservationAttestation(fingerprint(q),fingerprint(o),o.observation_id,p.principal_epoch,p.tenant_epoch,p.revocation_epoch)

    def issue_report(self,command,state,observation=None,quiescent=False):
        entry=self.state.journal[(command.query.tenant,command.query.operation)]
        report=CommitReport(command.query.binding(),fingerprint(command),state,observation,state=="REFUSED",quiescent,
                            entry["attempt_id"],entry["generation"])
        self.reports[fingerprint(report)]=(command.query.binding(),fingerprint(command))
        return report

    def verify_outcome(self,command,report,now):
        require(now==self.now and self.active is True and self.revoked is False,"OUTCOME_AUTHORITY_DENIED")
        q=command.query
        require((q.issuer,q.subject,q.tenant,q.role)==(self.trusted_issuer,self.subject,self.tenant,self.role),"OUTCOME_PRINCIPAL_BINDING")
        require(self.reports.get(fingerprint(report))==(command.query.binding(),fingerprint(command)),"FORGED_OUTCOME")
        entry=self.state.journal.get((q.tenant,q.operation))
        current_attempt=(entry is not None and entry["binding"]==q.binding() and entry["attempt_id"]==report.attempt_id
                and type(entry["generation"]) is int and entry["generation"]==report.journal_generation)
        if report.state=="REFUSED" and not current_attempt:raise RefusalUnresolved("STALE_ATTEMPT_EVIDENCE")
        require(current_attempt,"STALE_ATTEMPT_EVIDENCE")
        if report.state=="REFUSED":
            receipt_key=("CANCEL_SUBMISSION#"+q.tenant+"#"+q.operation,"RECEIPT")
            stored=self.state.rows.get(receipt_key)
            # A proven collision belongs to a different binding. Any unproven row is inconclusive.
            receipt_excludes_commit=stored is None or (stored.get("binding")!=q.binding() and
                self.state.committed.get(stored.get("binding"))==fingerprint(freeze(stored)))
            if not (entry["state"]=="REFUSED" and self.state.attempts.get(q.binding())=="REFUSED"
                    and q.binding() not in self.state.committed and receipt_excludes_commit):
                raise RefusalUnresolved("NON_COMMIT_UNRESOLVED")
        return OutcomeAttestation(report.binding,fingerprint(command),fingerprint(report),report.attempt_id,report.journal_generation)


class _CommitVerifier:
    """Test-only issued-snapshot validation; actual current rows are fenced by PR51 conditions.

    Replay never uses this dependency. The port constructs it internally, not from client input.
    """
    def __init__(self,authority):self.authority=authority
    def verify_observation(self,q,o,now):return self.authority._verify_observation(q,o,now,False)


class FakeCommitPort:
    def __init__(self,state,authority):self.state=state;self.authority=authority;self.calls=0

    def _report(self,command,state,observation=None,quiescent=False):
        self.state.finish_attempt(command.query,state)
        return self.authority.issue_report(command,state,observation,quiescent)

    def commit(self,command,mode="normal"):
        # All model checks precede any state publication or attempt bookkeeping.
        validate_command(command,_CommitVerifier(self.authority),self.authority.now)
        q=command.query
        require(self.state.attempts.get(q.binding())!="UNKNOWN","NO_BLIND_RETRY")
        self.state.begin_attempt(q)
        self.calls+=1
        if mode=="pending":
            self.state.attempts[q.binding()]="UNKNOWN"
            return self.authority.issue_report(command,"UNKNOWN")
        receipt_key=("CANCEL_SUBMISSION#"+q.tenant+"#"+q.operation,"RECEIPT")
        existing=self.state.rows.get(receipt_key)
        if existing is not None:
            stored_binding=existing.get("binding")
            proven=self.state.committed.get(stored_binding)==fingerprint(freeze(existing))
            if proven and stored_binding==q.binding():
                return self._report(command,"COMMITTED",self.authority.observe(q))
            if proven:
                return self._report(command,"REFUSED",quiescent=True)
            self.state.attempts[q.binding()]="UNKNOWN"
            return self._report(command,"UNKNOWN")
        if mode=="timeout_before":
            self.state.attempts[q.binding()]="UNKNOWN"
            return self._report(command,"UNKNOWN")
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
                return self._report(command,"REFUSED",quiescent=True)
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
            return self._report(command,"UNKNOWN")
        self.state.attempts[q.binding()]="COMMITTED"
        return self._report(command,"COMMITTED",self.authority.observe(q))
