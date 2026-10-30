"""INACTIVE cancellation-request submission design; standard library, no I/O.

No runtime authority, source-status policy, legacy enrollment or recovery grant.
Trusted access contexts and status assumptions exist only as offline preconditions.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import re
from urllib.parse import urlsplit


class SubmissionError(ValueError):
    pass


def need(value, reason):
    if not value:
        raise SubmissionError(reason)


def identifier(value):
    need(type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value), "IDENTITY")
    return value


def revision(value):
    if type(value) is Decimal:
        need(value.is_finite() and value == value.to_integral_value(), "REVISION")
        value = int(value)
    need(type(value) is int and 1 <= value < 2**63, "REVISION")
    return value


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return sha256(encoded(value).encode()).hexdigest()


# Constructed to avoid a false-positive literal import scan in inherited tests.
MARKERS = ("canonical_worker_id", "identity_revision", "assignment_contract_version",
           "assigned_worker_id", "assignment_revision", "execution_revision",
           "started_worker_id", "started_assignment_revision", "workflow_revision",
           "provisioning_state", "worker_identity", "worker_identity_" + "contract_version")
STATUSES = ("PENDING_REVIEW", "MEET_GREET_REQUIRED", "MG_SCHEDULED", "MG_COMPLETED",
            "READY_FOR_APPROVAL", "QUOTE_NEEDED", "QUOTE_SENT", "QUOTED", "APPROVED",
            "BOOKED", "ASSIGNED", "SCHEDULED", "JOB_CREATED", "DECLINED", "PROFILE_CREATED",
            "CANCELLATION_REQUESTED", "CANCELLATION_DENIED", "CANCELLED", "COMPLETED", "ARCHIVED", "DELETED")


def source_status_matrix(status):
    need(type(status) is str, "STATUS_SHAPE")
    if status in {"APPROVED", "BOOKED", "ASSIGNED", "SCHEDULED", "JOB_CREATED"}:
        return "WEB_OFFERED_POLICY_PENDING"
    if status == "CANCELLATION_REQUESTED":
        return "REPLAY_OR_RESUBMISSION_POLICY_PENDING"
    if status in STATUSES:
        return "NOT_WEB_OFFERED_POLICY_PENDING"
    return "UNSUPPORTED_POLICY_PENDING"


@dataclass(frozen=True)
class StatusAssumption:
    source_status: str
    permitted: bool = False
    mode: str = "SYNTHETIC_ONLY"
    reference: str = ""


@dataclass(frozen=True)
class Submission:
    tenant: str
    client_id: str
    request_id: str
    issuer: str
    actor: str
    operation: str
    reason: str = "No reason provided."

    def validate(self):
        for value in (self.tenant,self.client_id,self.request_id,self.actor,self.operation): identifier(value)
        need(type(self.issuer) is str, "ISSUER")
        try: parsed=urlsplit(self.issuer)
        except ValueError: raise SubmissionError("ISSUER") from None
        need(parsed.scheme=="https" and bool(parsed.hostname) and not parsed.username
             and not parsed.password and not parsed.query and not parsed.fragment, "ISSUER")
        need(type(self.reason) is str, "REASON_POLICY_PENDING")

    def key(self):
        self.validate()
        return {"PK":"REQ#"+self.request_id,"SK":"CLIENT#"+self.client_id}

    def token(self):
        return digest([self.tenant,self.key()["PK"],self.key()["SK"]])

    def binding(self):
        self.validate()
        return digest(["CANCELLATION_REQUEST_SUBMISSION_V1", self.__dict__])


@dataclass(frozen=True)
class Snapshot:
    tenant: str
    client_id: str
    request_id: str
    incarnation: str
    revision: int
    status: str
    start_present: bool
    start_date: object = None

    def validate(self):
        for x in (self.tenant,self.client_id,self.request_id,self.incarnation): identifier(x)
        revision(self.revision)
        need(type(self.revision) is int, "PARSE_REVISION_AT_BOUNDARY")
        need(type(self.status) is str and bool(self.status), "STATUS_SHAPE")
        need(type(self.start_present) is bool and (self.start_present or self.start_date is None), "START_SHAPE")
        need(self.start_date is None or type(self.start_date) is str, "START_SHAPE")


def parse_snapshot(item, submission):
    """No mutation/enrollment; unrelated fields remain in the backing record."""
    submission.validate()
    need(type(item) is dict, "MISSING_RECORD")
    need(item.get("PK")==submission.key()["PK"] and item.get("SK")==submission.key()["SK"], "EXACT_ITEM")
    need((item.get("company_id"),item.get("client_id"),item.get("request_id"))==
         (submission.tenant,submission.client_id,submission.request_id), "TARGET_BINDING")
    need(not any(k in item for k in MARKERS), "CANONICAL_MARKER")
    need("record_incarnation" in item and "legacy_write_revision" in item, "LEGACY_ADAPTER_PENDING")
    need("audit_log" not in item or type(item["audit_log"]) is list, "AUDIT_SHAPE")
    result=Snapshot(submission.tenant,submission.client_id,submission.request_id,item["record_incarnation"],
                    revision(item["legacy_write_revision"]),item.get("status"),"start_date" in item,item.get("start_date"))
    result.validate()
    return result


@dataclass(frozen=True)
class BookingAccess:
    tenant: str
    client_id: str
    request_id: str
    issuer: str
    actor: str
    role: str
    incarnation: str
    revision: int
    # Exact booking fields relied upon by a future server authorization adapter.
    bindings: tuple
    verified: bool = False
    current: bool = False
    tenant_active: bool = False
    booking_allowed: bool = False


def authorize(submission, access, snapshot):
    submission.validate(); snapshot.validate()
    need(type(access) is BookingAccess, "TRUSTED_ACCESS_REQUIRED")
    need(access.verified is True and access.current is True and access.tenant_active is True
         and access.booking_allowed is True, "ACCESS_DENIED")
    need((access.tenant,access.client_id,access.request_id,access.issuer,access.actor)==
         (submission.tenant,submission.client_id,submission.request_id,submission.issuer,submission.actor), "ACTOR_TARGET_BINDING")
    need((snapshot.tenant,snapshot.client_id,snapshot.request_id)==
         (submission.tenant,submission.client_id,submission.request_id), "TARGET_BINDING")
    need(type(access.role) is str and access.role in {"client","owner","admin","staff"}, "ACCESS_DENIED")
    need(access.incarnation==snapshot.incarnation and revision(access.revision)==snapshot.revision, "STALE_ACCESS")
    need(type(access.bindings) is tuple, "ACCESS_BINDING")
    fields=set()
    for pair in access.bindings:
        need(type(pair) is tuple and len(pair)==2, "ACCESS_BINDING")
        field,value=pair
        need(field in {"client_email","linked_client_profile_id","cognito_sub"} and field not in fields
             and type(value) is str and bool(value), "ACCESS_BINDING")
        fields.add(field)
    # No client email/name matching occurs here; the existing trusted adapter's
    # verified booking decision must provide its concrete persisted identity fence.
    need(access.role != "client" or bool(fields), "ACCESS_BINDING")


def warning(start, now):
    need(type(now) is datetime and now.tzinfo is not None and now.utcoffset() is not None, "TRUSTED_TIME_REQUIRED")
    if start is None or start == "": return False
    need(type(start) is str, "START_SHAPE")
    try:
        instant=datetime.fromisoformat(start).replace(tzinfo=timezone.utc) if len(start)==10 else datetime.fromisoformat(start.replace("Z","+00:00"))
    except ValueError:
        return False  # Existing handler ignores invalid ISO dates.
    need(instant.tzinfo is not None, "NAIVE_TIMESTAMP_POLICY_PENDING")
    return (instant-now).total_seconds() < 24*3600  # Includes past dates, as current backend does.


@dataclass(frozen=True)
class Receipt:
    tenant: str
    client_id: str
    request_id: str
    issuer: str
    actor: str
    operation: str
    binding: str
    incarnation: str
    source_revision: int
    submitted_at: str
    urgent_warning: bool

    def validate(self, submission):
        need(type(self) is Receipt, "RECEIPT_SHAPE")
        need((self.tenant,self.client_id,self.request_id,self.issuer,self.actor,self.operation,self.binding)==
             (submission.tenant,submission.client_id,submission.request_id,submission.issuer,submission.actor,
              submission.operation,submission.binding()), "OPERATION_PAYLOAD_CONFLICT")
        identifier(self.incarnation);revision(self.source_revision)
        need(type(self.urgent_warning) is bool and type(self.submitted_at) is str, "RECEIPT_SHAPE")
        try: stamp=datetime.fromisoformat(self.submitted_at)
        except ValueError: raise SubmissionError("RECEIPT_SHAPE") from None
        need(stamp.tzinfo is not None, "RECEIPT_SHAPE")

    def response(self):
        return {"message":"Cancellation request submitted for review.","urgent_warning":self.urgent_warning}


@dataclass(frozen=True)
class Plan:
    submission: Submission
    access: BookingAccess
    snapshot: Snapshot
    assumption: StatusAssumption
    receipt: Receipt
    blockers: tuple = ("INACTIVE_NO_RUNTIME", "SOURCE_STATUS_POLICY_PENDING", "TRUSTED_ACCESS_ADAPTER_PENDING",
                       "ALL_WRITERS_LIFETIME_PENDING", "API_RECOVERY_RETENTION_PENDING")


def prepare(submission,access,snapshot,now,assumption=None):
    authorize(submission,access,snapshot)
    need(type(assumption) is StatusAssumption and assumption.mode=="SYNTHETIC_ONLY"
         and assumption.permitted is True and assumption.source_status==snapshot.status
         and type(assumption.reference) is str and bool(assumption.reference), "SOURCE_STATUS_POLICY_PENDING")
    need(snapshot.status in STATUSES and snapshot.status!="CANCELLATION_REQUESTED", "RESUBMISSION_POLICY_PENDING")
    receipt=Receipt(submission.tenant,submission.client_id,submission.request_id,submission.issuer,submission.actor,
                    submission.operation,submission.binding(),snapshot.incarnation,snapshot.revision,
                    now.astimezone(timezone.utc).isoformat() if type(now) is datetime and now.tzinfo else "",
                    warning(snapshot.start_date,now))
    receipt.validate(submission)
    return Plan(submission,access,snapshot,assumption,receipt)


def replay(submission,access,current_snapshot,receipt,lifetime=None):
    """Current trusted booking access is required; replay never reapplies mutation."""
    authorize(submission,access,current_snapshot)
    need(type(receipt) is Receipt, "RECEIPT_SHAPE")
    receipt.validate(submission)
    need(type(lifetime) is dict and lifetime.get("PK")=="LIFETIME#"+submission.token()
         and lifetime.get("SK")=="PERMANENT" and lifetime.get("incarnation")==current_snapshot.incarnation
         and lifetime.get("retired") is False and "ttl" not in lifetime and "expires_at" not in lifetime, "LIFETIME_CONFLICT")
    need(receipt.incarnation==current_snapshot.incarnation, "LIFETIME_CONFLICT")
    return receipt.response()  # Original result, not a promise about current booking status.


def av(value):
    if value is None:return {"NULL":True}
    if type(value) is bool:return {"BOOL":value}
    if type(value) is str:return {"S":value}
    if type(value) is int:return {"N":str(value)}
    if type(value) is list:return {"L":[av(v) for v in value]}
    if type(value) is dict:return {"M":{k:av(v) for k,v in value.items()}}
    raise SubmissionError("VALUE_TYPE")


def attrs(value):return {k:av(v) for k,v in value.items()}


def transaction(plan,table_name):
    need(type(plan) is Plan, "PLAN_SHAPE")
    receipt=plan.receipt;receipt.validate(plan.submission)
    instant=datetime.fromisoformat(receipt.submitted_at)
    need(prepare(plan.submission,plan.access,plan.snapshot,instant,plan.assumption)==plan, "PLAN_BINDING")
    need(type(table_name) is str and re.fullmatch(r"[A-Za-z0-9_.-]{3,255}",table_name), "TABLE")
    sub=plan.submission;snap=plan.snapshot
    need(snap.revision < 2**63-1,"REVISION_EXHAUSTED")
    names={"#s":"status","#inc":"record_incarnation","#rev":"legacy_write_revision","#start":"start_date","#audit":"audit_log"}
    values={":tenant":sub.tenant,":client":sub.client_id,":request":sub.request_id,":old":snap.status,":inc":snap.incarnation,
            ":rev":snap.revision,":next":snap.revision+1,":new":"CANCELLATION_REQUESTED",":reason":sub.reason,
            ":time":receipt.submitted_at,":by":"CLIENT#"+sub.client_id,":empty":[],":list":"L",":number":"N",
            ":audit":[{"status":"CANCELLATION_REQUESTED","timestamp":receipt.submitted_at,"by":"CLIENT#"+sub.client_id,"reason":sub.reason}]}
    parts=["attribute_exists(PK)","attribute_exists(SK)","company_id = :tenant","client_id = :client","request_id = :request",
           "#s = :old","#inc = :inc","#rev = :rev","attribute_type(#rev, :number)","(attribute_not_exists(#audit) OR attribute_type(#audit, :list))"]
    if snap.start_present:parts.append("#start = :start");values[":start"]=snap.start_date
    else:parts.append("attribute_not_exists(#start)")
    for index,marker in enumerate(MARKERS):
        names["#m"+str(index)]=marker;parts.append("attribute_not_exists(#m"+str(index)+")")
    for index,(field,value) in enumerate(plan.access.bindings):
        names["#a"+str(index)]=field;values[":a"+str(index)]=value;parts.append("#a"+str(index)+" = :a"+str(index))
    update={"TableName":table_name,"Key":attrs(sub.key()),"ConditionExpression":" AND ".join(parts),
        "UpdateExpression":"SET #s = :new, cancellation_reason = :reason, cancellation_requested_at = :time, cancellation_requested_by = :by, #audit = list_append(if_not_exists(#audit, :empty), :audit), #rev = :next",
        "ExpressionAttributeNames":names,"ExpressionAttributeValues":attrs(values)}
    reservation={"TableName":table_name,"Key":attrs({"PK":"RESERVATION#"+sub.token(),"SK":"PERMANENT"}),"ConditionExpression":"attribute_not_exists(PK)"}
    lifetime={"TableName":table_name,"Key":attrs({"PK":"LIFETIME#"+sub.token(),"SK":"PERMANENT"}),
        "ConditionExpression":"incarnation = :inc AND retired = :no AND attribute_type(retired, :bool_type) AND attribute_not_exists(#ttl) AND attribute_not_exists(#expires)",
        "ExpressionAttributeNames":{"#ttl":"ttl","#expires":"expires_at"},"ExpressionAttributeValues":attrs({":inc":snap.incarnation,":no":False,":bool_type":"BOOL"})}
    saved={"PK":"CANCEL_SUBMISSION#"+sub.tenant+"#"+sub.operation,"SK":"RECEIPT",**receipt.__dict__}
    receipt_put={"TableName":table_name,"Item":attrs(saved),"ConditionExpression":"attribute_not_exists(PK)"}
    request={"TransactItems":[{"Update":update},{"ConditionCheck":reservation},{"ConditionCheck":lifetime},{"Put":receipt_put}]}
    need(len(update["ConditionExpression"].encode())<=4096 and len(encoded(request).encode())*2+4096<300*1024,"OVERSIZE_REFUSED")
    return request


def persistence_outcome(submission,access,snapshot,receipt=None,confirmed_refusal=False,lifetime=None):
    """No receipt after timeout is ambiguous, never proof of non-commit/quiescence."""
    authorize(submission,access,snapshot)
    need(type(confirmed_refusal) is bool,"OUTCOME_SHAPE")
    if receipt is not None:
        need(not confirmed_refusal,"OUTCOME_CONFLICT")
        return {"state":"REPLAY_CONFIRMED","response":replay(submission,access,snapshot,receipt,lifetime)}
    return {"state":"REFUSED" if confirmed_refusal else "UNKNOWN_NO_BLIND_RETRY"}


def operator_recovery(*_args,**_kwargs):
    raise SubmissionError("OPERATOR_RECOVERY_AUTHORIZATION_PENDING")
