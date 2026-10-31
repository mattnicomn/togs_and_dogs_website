"""INACTIVE adapter ports/classification. No SDK, I/O, handler imports or execution.

A verifier is a trusted server-owned dependency, never chosen by a caller. The
interfaces do not authenticate credentials or establish real storage isolation.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import re
from typing import Protocol
from urllib.parse import urlsplit


class AdapterError(ValueError):
    pass


class RefusalUnresolved(AdapterError):
    """Trusted verifier cannot currently prove non-commit AND quiescence."""


def require(value, reason):
    if not value: raise AdapterError(reason)


def identifier(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,128}",value),"IDENTITY")
    return value


def revision(value):
    if type(value) is Decimal:
        require(value.is_finite() and value==value.to_integral_value(),"REVISION")
        value=int(value)
    require(type(value) is int and 1<=value<2**63,"REVISION")
    return value


def canonical_revision(value):
    """Internal evidence uses exact integers; DB Decimal parsing belongs in revision."""
    require(type(value) is int,"CANONICAL_REVISION")
    return revision(value)


@dataclass(frozen=True)
class FrozenMap:
    entries: tuple

    def mapping(self): return {k:thaw(v) for k,v in self.entries}


@dataclass(frozen=True)
class FrozenList:
    entries: tuple


def freeze(value, depth=0):
    require(depth<=16,"NESTING_BUDGET")
    if type(value) is dict:
        require(all(type(k) is str for k in value),"FIELD_TYPE")
        return FrozenMap(tuple((k,freeze(v,depth+1)) for k,v in sorted(value.items())))
    if type(value) is list:return FrozenList(tuple(freeze(v,depth+1) for v in value))
    require(type(value) in (str,int,bool,Decimal,type(None)),"FIELD_TYPE")
    if type(value) is Decimal:require(value.is_finite(),"FIELD_TYPE")
    return value


def thaw(value):
    if type(value) is FrozenMap:return value.mapping()
    if type(value) is FrozenList:return [thaw(v) for v in value.entries]
    return value


def fingerprint(value):
    def tagged(v):
        if type(v) is FrozenMap:return ["map",[[k,tagged(x)] for k,x in v.entries]]
        if type(v) is FrozenList:return ["list",[tagged(x) for x in v.entries]]
        if type(v) is tuple:return ["tuple",[tagged(x) for x in v]]
        if hasattr(v,"__dataclass_fields__"):
            return [type(v).__name__,[[k,tagged(getattr(v,k))] for k in v.__dataclass_fields__]]
        if type(v) is Decimal:return ["decimal",str(v)]
        require(type(v) in (str,int,bool,type(None)),"FINGERPRINT_TYPE")
        return [type(v).__name__,v]
    return sha256(json.dumps(tagged(value),separators=(",",":"),ensure_ascii=True).encode()).hexdigest()


def raw_digest(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()


MARKERS=("canonical_worker_id","identity_revision","assignment_contract_version","assigned_worker_id",
         "assignment_revision","execution_revision","started_worker_id","started_assignment_revision",
         "workflow_revision","provisioning_state","worker_identity","worker_identity_"+"contract_version")
STATUSES=("PENDING_REVIEW","MEET_GREET_REQUIRED","MG_SCHEDULED","MG_COMPLETED","READY_FOR_APPROVAL",
          "QUOTE_NEEDED","QUOTE_SENT","QUOTED","APPROVED","ASSIGNED","DECLINED","PROFILE_CREATED",
          "CANCELLATION_REQUESTED","CANCELLATION_DENIED","CANCELLED","COMPLETED","ARCHIVED","DELETED")
IDENTITY_FIELDS=("client_email","linked_client_profile_id","cognito_sub")


@dataclass(frozen=True)
class Query:
    tenant: str
    client_id: str
    request_id: str
    issuer: str
    subject: str
    role: str
    operation: str
    reason: str

    def validate(self):
        for x in (self.tenant,self.client_id,self.request_id,self.subject,self.operation):identifier(x)
        require(type(self.issuer) is str,"ISSUER")
        try:p=urlsplit(self.issuer)
        except ValueError:raise AdapterError("ISSUER") from None
        require(p.scheme=="https" and bool(p.hostname) and not p.username and not p.password
                and not p.query and not p.fragment,"ISSUER")
        require(type(self.role) is str and self.role in ("client","owner","admin","staff"),"ROLE_PENDING_OR_DENIED")
        require(type(self.reason) is str,"REASON_POLICY_PENDING")

    def key(self):return ("REQ#"+self.request_id,"CLIENT#"+self.client_id)

    def token(self):return raw_digest([self.tenant,*self.key()])

    def binding(self):
        self.validate()
        body=dict(tenant=self.tenant,client_id=self.client_id,request_id=self.request_id,issuer=self.issuer,
                  actor=self.subject,operation=self.operation,reason=self.reason)
        return raw_digest(["CANCELLATION_REQUEST_SUBMISSION_V1",body])


@dataclass(frozen=True)
class Principal:
    issuer: str
    subject: str
    tenant: str
    role: str
    identity_bindings: FrozenMap
    principal_epoch: int
    tenant_epoch: int
    revocation_epoch: int
    tenant_active: bool
    revoked: bool


@dataclass(frozen=True)
class Observation:
    binding: str
    principal: Principal
    request: object
    lifetime: object
    reservation: object
    receipt: object
    observation_id: str
    observed_at: int
    valid_until: int
    coherence: str


@dataclass(frozen=True)
class ObservationAttestation:
    query_fingerprint: str
    observation_fingerprint: str
    observation_id: str
    principal_epoch: int
    tenant_epoch: int
    revocation_epoch: int


@dataclass(frozen=True)
class Compatibility:
    disposition: str
    reasons: tuple


def classify_legacy(query, request, lifetime, reservation=None):
    """Pure schema classification, NOT eligibility or migration authority."""
    query.validate()
    if type(request) is not dict:return Compatibility("MANUAL_INVESTIGATION_REQUIRED",("MISSING_OR_MALFORMED_REQUEST",))
    reasons=[];classes=[]
    def note(category,reason):classes.append(category);reasons.append(reason)
    if reservation is not None:note("PROTECTED_REFUSAL","RESERVATION_PRESENT")
    if any(m in request for m in MARKERS):note("PROTECTED_REFUSAL","CANONICAL_OR_PARTIAL_MARKER")
    for field,expected in (("PK",query.key()[0]),("SK",query.key()[1]),("company_id",query.tenant),
                           ("client_id",query.client_id),("request_id",query.request_id)):
        if field not in request or request[field] is None:
            note("STAGED_ADOPTION_REQUIRED" if field=="company_id" else "LEGACY_POLICY_REQUIRED","MISSING_"+field)
        elif request[field]!=expected:note("PROTECTED_REFUSAL","TARGET_MISMATCH_"+field)
    incarnation=request.get("record_incarnation")
    if incarnation is None:note("STAGED_ADOPTION_REQUIRED","MISSING_INCARNATION")
    else:
        try:identifier(incarnation)
        except AdapterError:note("MANUAL_INVESTIGATION_REQUIRED","MALFORMED_INCARNATION")
    if "legacy_write_revision" not in request:note("STAGED_ADOPTION_REQUIRED","MISSING_REVISION")
    else:
        try:revision(request["legacy_write_revision"])
        except AdapterError:note("MANUAL_INVESTIGATION_REQUIRED","MALFORMED_REVISION")
    status=request.get("status")
    if type(status) is not str or status not in STATUSES:
        note("LEGACY_POLICY_REQUIRED" if status in (None,"BOOKED","SCHEDULED","JOB_CREATED") else "MANUAL_INVESTIGATION_REQUIRED","STATUS_VARIANT")
    if "audit_log" in request and type(request["audit_log"]) is not list:note("MANUAL_INVESTIGATION_REQUIRED","AUDIT_SHAPE")
    for field in IDENTITY_FIELDS:
        if field in request:
            value=request[field]
            if value is None:note("MANUAL_INVESTIGATION_REQUIRED","NULL_"+field)
            elif type(value) is not str or not value.strip():
                note("MANUAL_INVESTIGATION_REQUIRED","MALFORMED_"+field)
            elif field=="linked_client_profile_id" and value!=query.client_id:
                note("LEGACY_POLICY_REQUIRED","LINKED_OWNER_DIFFERS")
    if lifetime is None:note("STAGED_ADOPTION_REQUIRED","MISSING_LIFETIME")
    elif type(lifetime) is not dict:note("PROTECTED_REFUSAL","LIFETIME_SHAPE")
    elif (lifetime.get("PK"),lifetime.get("SK"),lifetime.get("incarnation"),lifetime.get("retired"))!=("LIFETIME#"+query.token(),"PERMANENT",incarnation,False) or lifetime.get("retired") is not False or "ttl" in lifetime or "expires_at" in lifetime:
        note("PROTECTED_REFUSAL","LIFETIME_CONFLICT")
    order=("PROTECTED_REFUSAL","MANUAL_INVESTIGATION_REQUIRED","STAGED_ADOPTION_REQUIRED","LEGACY_POLICY_REQUIRED")
    disposition=next((x for x in order if x in classes),"PROTECTED_PATH_CANDIDATE")
    return Compatibility(disposition,tuple(sorted(set(reasons))))


class ObservationPort(Protocol):
    def observe(self, query: Query) -> Observation: ...


class VerificationPort(Protocol):
    def verify_observation(self, query: Query, observation: Observation, now: int) -> ObservationAttestation: ...
    def verify_outcome(self, command: "CommitCommand", report: "CommitReport", now: int) -> "OutcomeAttestation": ...


def validate_observation(query, observation, verifier, now):
    query.validate()
    require(type(observation) is Observation and type(observation.principal) is Principal,"OBSERVATION_SHAPE")
    require(type(now) is int and type(observation.observed_at) is int and type(observation.valid_until) is int
            and 0<=observation.observed_at<=now<=observation.valid_until,"STALE_OBSERVATION")
    identifier(observation.observation_id)
    require(observation.coherence=="COHERENT_SNAPSHOT" and observation.binding==query.binding(),"INCOHERENT_OBSERVATION")
    p=observation.principal
    require((p.issuer,p.subject,p.tenant,p.role)==(query.issuer,query.subject,query.tenant,query.role),"PRINCIPAL_BINDING")
    for epoch in (p.principal_epoch,p.tenant_epoch,p.revocation_epoch):canonical_revision(epoch)
    require(p.tenant_active is True and p.revoked is False,"INACTIVE_OR_REVOKED")
    require(type(p.identity_bindings) is FrozenMap,"IDENTITY_BINDING_SHAPE")
    require(all(value is None or type(value) is FrozenMap for value in
                (observation.request,observation.lifetime,observation.reservation,observation.receipt)),"OBSERVATION_SHAPE")
    require(verifier is not None and callable(getattr(verifier,"verify_observation",None)),"VERIFIER_REQUIRED")
    proof=verifier.verify_observation(query,observation,now)
    require(type(proof) is ObservationAttestation,"ATTESTATION_REQUIRED")
    for epoch in (proof.principal_epoch,proof.tenant_epoch,proof.revocation_epoch):canonical_revision(epoch)
    require(fingerprint(proof)==fingerprint(ObservationAttestation(fingerprint(query),fingerprint(observation),observation.observation_id,
                p.principal_epoch,p.tenant_epoch,p.revocation_epoch)),"ATTESTATION_BINDING")
    request=thaw(observation.request)
    require(type(request) is dict,"MISSING_REQUEST")
    for field,expected in (("PK",query.key()[0]),("SK",query.key()[1]),("company_id",query.tenant),
                           ("client_id",query.client_id),("request_id",query.request_id)):
        require(request.get(field)==expected,"TARGET_BINDING")
    bindings=p.identity_bindings.mapping()
    require(query.role!="client" or bool(bindings),"BOOKING_OWNERSHIP_REQUIRED")
    for field,expected in bindings.items():
        require(field in IDENTITY_FIELDS and type(expected) is str and bool(expected),"BOOKING_OWNERSHIP_REQUIRED")
        require(field in request and type(request[field]) is str and request[field]==expected,"BOOKING_IDENTITY_CHANGED")
    return request


def urgent_warning(start, instant):
    require(type(instant) is datetime and instant.tzinfo is not None and instant.utcoffset() is not None,"TRUSTED_TIME_REQUIRED")
    if start is None or start=="":return False
    require(type(start) is str,"START_SHAPE")
    try:date=datetime.fromisoformat(start).replace(tzinfo=timezone.utc) if len(start)==10 else datetime.fromisoformat(start.replace("Z","+00:00"))
    except ValueError:return False
    require(date.tzinfo is not None,"NAIVE_TIME_POLICY_PENDING")
    return (date-instant).total_seconds()<86400


@dataclass(frozen=True)
class CommitCommand:
    query: Query
    observation: Observation
    submitted_at: str
    assumed_status: str
    assumption_reference: str
    expected_revision: int
    incarnation: str
    patch: FrozenMap
    stored_receipt: FrozenMap
    guards: tuple
    blockers: tuple=("INACTIVE_NO_RUNTIME","SOURCE_STATUS_POLICY_PENDING","REAL_ADAPTER_PENDING","ALL_WRITERS_PENDING","RETENTION_ROLLOUT_PENDING")


def prepare_commit(query, observation, verifier, now, submitted_at, assumed_status=None, assumption_reference=""):
    request=validate_observation(query,observation,verifier,now)
    classification=classify_legacy(query,request,thaw(observation.lifetime),thaw(observation.reservation))
    require(classification.disposition=="PROTECTED_PATH_CANDIDATE",classification.disposition)
    require(observation.receipt is None,"REPLAY_REQUIRED")
    require(assumed_status==request["status"] and type(assumption_reference) is str and bool(assumption_reference)
            and assumed_status!="CANCELLATION_REQUESTED","SOURCE_STATUS_POLICY_PENDING")
    old=revision(request["legacy_write_revision"]);require(old<2**63-1,"REVISION_EXHAUSTED")
    stamp=submitted_at.astimezone(timezone.utc).isoformat() if type(submitted_at) is datetime and submitted_at.tzinfo else ""
    urgent=urgent_warning(request.get("start_date"),submitted_at)
    receipt=dict(tenant=query.tenant,client_id=query.client_id,request_id=query.request_id,issuer=query.issuer,
        actor=query.subject,operation=query.operation,binding=query.binding(),incarnation=request["record_incarnation"],
        source_revision=old,submitted_at=stamp,urgent_warning=urgent)
    stored=dict(receipt,PK="CANCEL_SUBMISSION#"+query.tenant+"#"+query.operation,SK="RECEIPT",
                commit_state="COMMITTED",committed_revision=old+1,receipt_digest=raw_digest(receipt))
    audit=dict(status="CANCELLATION_REQUESTED",timestamp=stamp,by="CLIENT#"+query.client_id,reason=query.reason)
    patch=freeze({"set":{"status":"CANCELLATION_REQUESTED","cancellation_reason":query.reason,
        "cancellation_requested_at":stamp,"cancellation_requested_by":"CLIENT#"+query.client_id,"legacy_write_revision":old+1},
        "append":{"audit_log":[audit]}})
    guards=("EXACT_EXISTING_REQUEST","EXPECTED_REVISION_AND_INCARNATION","SOURCE_STATUS_AND_START",
            "ACTUAL_BOOKING_IDENTITY","AUDIT_LIST_OR_ABSENT","NO_CANONICAL_MARKERS","RESERVATION_ABSENT",
            "LIVE_PERMANENT_LIFETIME","CREATE_ONLY_RECEIPT","ATOMIC_REQUEST_AND_RECEIPT","FIELD_PRESERVING_UPDATE")
    command=CommitCommand(query,observation,stamp,assumed_status,assumption_reference,old,request["record_incarnation"],patch,freeze(stored),guards)
    require(len(fingerprint(command))==64 and len(json.dumps(patch.mapping()))*2+4096<300*1024,"OVERSIZE_REFUSED")
    return command


def validate_command(command, verifier, now):
    require(type(command) is CommitCommand,"COMMAND_REQUIRED")
    canonical_revision(command.expected_revision)
    expected=prepare_commit(command.query,command.observation,verifier,now,datetime.fromisoformat(command.submitted_at),
                            command.assumed_status,command.assumption_reference)
    require(fingerprint(command)==fingerprint(expected),"COMMAND_BINDING")


def replay_response(query, observation, verifier, now):
    request=validate_observation(query,observation,verifier,now)
    require(classify_legacy(query,request,thaw(observation.lifetime),thaw(observation.reservation)).disposition=="PROTECTED_PATH_CANDIDATE","PROTECTED_REFUSAL")
    require(type(observation.receipt) is FrozenMap,"COMMITTED_RECEIPT_REQUIRED")
    item=observation.receipt.mapping()
    fields=("tenant","client_id","request_id","issuer","actor","operation","binding","incarnation","source_revision","submitted_at","urgent_warning")
    require(set(item)==set(fields)|{"PK","SK","commit_state","committed_revision","receipt_digest"},"RECEIPT_SHAPE")
    require((item["tenant"],item["client_id"],item["request_id"],item["issuer"],item["actor"],item["operation"],item["binding"],item["incarnation"])
            ==(query.tenant,query.client_id,query.request_id,query.issuer,query.subject,query.operation,query.binding(),request["record_incarnation"]),"RECEIPT_BINDING")
    require(item["PK"]=="CANCEL_SUBMISSION#"+query.tenant+"#"+query.operation and item["SK"]=="RECEIPT"
            and item["commit_state"]=="COMMITTED","RECEIPT_LOCATION")
    source=revision(item["source_revision"]);committed=revision(item["committed_revision"])
    require(committed==source+1 and revision(request["legacy_write_revision"])>=committed,"COMMIT_REVISION")
    require(item["receipt_digest"]==raw_digest({k:(revision(item[k]) if k=="source_revision" else item[k]) for k in fields}),"RECEIPT_DIGEST")
    require(type(item["urgent_warning"]) is bool and type(item["submitted_at"]) is str,"RECEIPT_SHAPE")
    try:stamp=datetime.fromisoformat(item["submitted_at"])
    except ValueError:raise AdapterError("RECEIPT_SHAPE") from None
    require(stamp.tzinfo is not None,"RECEIPT_SHAPE")
    return {"message":"Cancellation request submitted for review.","urgent_warning":item["urgent_warning"]}


@dataclass(frozen=True)
class CommitReport:
    binding: str
    command_fingerprint: str
    state: str
    observation: object=None
    non_commit_proven: bool=False
    attempts_quiescent: bool=False
    attempt_id: str=""
    journal_generation: int=0


@dataclass(frozen=True)
class OutcomeAttestation:
    binding: str
    command_fingerprint: str
    report_fingerprint: str
    attempt_id: str=""
    journal_generation: int=0


class ConditionalCommitPort(Protocol):
    def commit(self, command: CommitCommand) -> CommitReport: ...


def commit_outcome(command, report, verifier, now):
    require(type(command) is CommitCommand and type(report) is CommitReport,"OUTCOME_SHAPE")
    canonical_revision(command.expected_revision)
    identifier(report.attempt_id);canonical_revision(report.journal_generation)
    require(report.binding==command.query.binding() and report.command_fingerprint==fingerprint(command),"OUTCOME_BINDING")
    require(verifier is not None and callable(getattr(verifier,"verify_outcome",None)),"VERIFIER_REQUIRED")
    try:proof=verifier.verify_outcome(command,report,now)
    except RefusalUnresolved:
        require(report.state=="REFUSED","OUTCOME_ATTESTATION")
        return ("UNKNOWN",None)  # Lost non-commit/quiescence proof is never a retry grant.
    require(type(proof) is OutcomeAttestation,"OUTCOME_ATTESTATION")
    identifier(proof.attempt_id);canonical_revision(proof.journal_generation)
    require(fingerprint(proof)==fingerprint(OutcomeAttestation(report.binding,fingerprint(command),fingerprint(report),
            report.attempt_id,report.journal_generation)),"OUTCOME_ATTESTATION")
    require(report.state in ("COMMITTED","REFUSED","UNKNOWN"),"OUTCOME_SHAPE")
    if report.state=="COMMITTED":
        return ("COMMITTED",replay_response(command.query,report.observation,verifier,now))
    if report.state=="REFUSED":
        require(report.non_commit_proven is True and report.attempts_quiescent is True,"NON_COMMIT_PROOF_REQUIRED")
    return (report.state,None)  # UNKNOWN never permits a blind retry or new key.
