"""INACTIVE workflow design. Standard library only; no clients, I/O or handler wiring.

All identities/authorization and complete affected-set discovery are trusted adapter
obligations. These plans are not permission grants or production transactions.
"""
from dataclasses import dataclass, replace
from hashlib import sha256
import json
import re


class WorkflowError(ValueError):
    pass


def require(value, reason):
    if not value:
        raise WorkflowError(reason)


def ident(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value), "IDENTITY")
    return value


def version(value):
    require(type(value) is int and 1 <= value < 2**63, "REVISION")
    return value


def canonical(value):
    # No floats, coercive bool/int revision parsing, sets or mutable record storage.
    def check(v, depth=0):
        require(depth <= 16, "NESTING_BUDGET_REFUSED")
        require(type(v) in (str, int, bool, list, dict, type(None)), "VALUE_TYPE")
        if type(v) is dict:
            require(all(type(k) is str for k in v), "VALUE_TYPE")
            for x in v.values(): check(x, depth+1)
        if type(v) is list:
            for x in v: check(x, depth+1)
    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


MARKERS = ("canonical_worker_id", "identity_revision", "assignment_contract_version",
           "assigned_worker_id", "assignment_revision", "execution_revision",
           "started_worker_id", "started_assignment_revision", "workflow_revision",
           "provisioning_state", "worker_identity", "worker_identity_" + "contract_version")


@dataclass(frozen=True, order=True)
class Key:
    tenant: str
    pk: str
    sk: str

    def validate(self):
        ident(self.tenant)
        require(type(self.pk) is str and type(self.sk) is str, "KEY")
        require(self.pk.startswith(("REQ#", "JOB#", "PET#")), "KEY")
        ident(self.pk.split("#", 1)[1])
        require(self.sk.startswith(("CLIENT#", "REQ#")), "KEY")
        ident(self.sk.split("#", 1)[1])
        return self

    def token(self):
        self.validate()
        return digest([self.tenant, self.pk, self.sk])


@dataclass(frozen=True)
class Record:
    key: Key
    incarnation: str
    revision: int
    body: str

    def data(self):
        self.key.validate(); ident(self.incarnation); version(self.revision)
        require(type(self.body) is str, "SHAPE")
        try:
            value = json.loads(self.body)
        except (ValueError, TypeError):
            raise WorkflowError("SHAPE") from None
        require(type(value) is dict and canonical(value) == self.body, "SHAPE")
        require(value.get("company_id") == self.key.tenant, "TENANT")
        require(not any(m in value for m in MARKERS), "CANONICAL_MARKER")
        require(not any(m in value for m in ("PK", "SK", "record_incarnation", "legacy_write_revision")), "RESERVED_FIELD")
        return value

    def item(self):
        return dict(self.data(), PK=self.key.pk, SK=self.key.sk,
                    record_incarnation=self.incarnation, legacy_write_revision=self.revision)


def record(key, incarnation, revision, **body):
    result = Record(key, incarnation, revision, canonical(body))
    result.data()
    return result


@dataclass(frozen=True)
class Operation:
    tenant: str
    request_id: str
    client_id: str
    operation_id: str
    action: str

    def validate(self):
        for x in (self.tenant, self.request_id, self.client_id, self.operation_id): ident(x)
        require(self.action in {"ASSIGN", "REVIEW", "CANCEL", "CREATE_JOBS", "LINK_PETS", "ROLLBACK_STATUS"}, "ACTION")


def aggregate(operation, records):
    operation.validate()
    require(type(records) is tuple and bool(records), "COMPLETE_SET_REQUIRED")
    require(all(type(r) is Record for r in records), "SHAPE")
    rows = {r.key: r for r in records}
    require(len(rows) == len(records), "DUPLICATE_ITEM")
    parent_key = Key(operation.tenant, "REQ#"+operation.request_id, "CLIENT#"+operation.client_id)
    require(parent_key in rows, "PARENT")
    parent = rows[parent_key].data()
    require(parent.get("request_id") == operation.request_id and parent.get("client_id") == operation.client_id, "PARENT")
    for field in ("job_ids", "pet_ids"):
        values = parent.get(field)
        require(type(values) is list and all(type(x) is str for x in values), "MEMBERSHIP")
        require(len(values) == len(set(values)), "MEMBERSHIP")
        for value in values: ident(value)
    jobs, pets = set(), set()
    for key, row in rows.items():
        body = row.data()
        require(key.tenant == operation.tenant and body.get("client_id") == operation.client_id, "TENANT_OR_CLIENT")
        if key == parent_key: continue
        if key.pk.startswith("JOB#"):
            jid = key.pk[4:]
            require(key.sk == "REQ#"+operation.request_id and body.get("request_id") == operation.request_id, "CHILD")
            jobs.add(jid)
            refs = body.get("pet_ids")
            require(type(refs) is list and all(type(x) is str and x in parent["pet_ids"] for x in refs), "PET_MEMBERSHIP")
        else:
            require(key.pk.startswith("PET#") and key.sk == "CLIENT#"+operation.client_id, "PET_OWNER")
            require(body.get("pet_id") == key.pk[4:], "PET_OWNER")
            pets.add(key.pk[4:])
    require(jobs == set(parent["job_ids"]) and pets == set(parent["pet_ids"]), "INCOMPLETE_MEMBERSHIP")
    if parent.get("status") == "COMPLETED":
        require(all(r.data().get("status") == "COMPLETED" for k,r in rows.items() if k.pk.startswith("JOB#")), "INCOMPLETE_COMPLETION")
    return rows


@dataclass(frozen=True)
class Effect:
    effect_id: str
    kind: str
    target: Key
    payload: str

    def validate(self, rows):
        ident(self.effect_id)
        require(self.kind in {"CALENDAR", "NOTIFICATION"} and self.target in rows, "EFFECT_TARGET")
        require(type(self.payload) is str, "EFFECT_PAYLOAD")
        try: body = json.loads(self.payload)
        except ValueError: raise WorkflowError("EFFECT_PAYLOAD") from None
        require(type(body) is dict and canonical(body) == self.payload, "EFFECT_PAYLOAD")


@dataclass(frozen=True)
class Plan:
    operation: Operation
    before: tuple
    after: tuple
    effects: tuple
    binding: str
    blockers: tuple = ("INACTIVE_NO_RUNTIME", "TRUSTED_AUTHORIZATION_PENDING", "ALL_WRITERS_PENDING", "API_COMPATIBILITY_PENDING")


def build_plan(operation, before, after, effects=()):
    old, new = aggregate(operation, before), aggregate(operation, after)
    require(set(old) <= set(new), "HARD_DELETE_POLICY_PENDING")
    require(type(effects) is tuple and all(type(e) is Effect for e in effects), "EFFECT_SHAPE")
    require(len({e.effect_id for e in effects}) == len(effects), "DUPLICATE_EFFECT")
    for e in effects: e.validate(new)
    changed = False
    for key, row in new.items():
        if key not in old:
            require(row.revision == 1, "NEW_REVISION")
        elif row != old[key]:
            require(row.incarnation == old[key].incarnation and row.revision == version(old[key].revision)+1, "STALE_OR_INCARNATION")
        changed |= key not in old or row != old[key]
        if operation.action == "ASSIGN" and key.pk.startswith("JOB#"):
            require("started_at" not in row.data() and "started_at" not in old.get(key, row).data(), "REASSIGN_AFTER_START_POLICY_PENDING")
        if operation.action == "CANCEL":
            expected = "COMPLETED" if key in old and old[key].data().get("status") == "COMPLETED" else "CANCELLED"
            if key.pk.startswith(("REQ#", "JOB#")):
                require(row.data().get("status") == expected, "CANCEL_CONSISTENCY")
    require(changed, "NO_MUTATION")
    content = [operation.__dict__, [r.__dict__ | {"key":r.key.__dict__} for r in before],
               [r.__dict__ | {"key":r.key.__dict__} for r in after],
               [e.__dict__ | {"target":e.target.__dict__} for e in effects]]
    return Plan(operation, before, after, effects, digest(content))


def av(value):
    if value is None: return {"NULL": True}
    if type(value) is bool: return {"BOOL": value}
    if type(value) is int: return {"N": str(value)}
    if type(value) is str: return {"S": value}
    if type(value) is list: return {"L": [av(v) for v in value]}
    if type(value) is dict: return {"M": {k:av(v) for k,v in value.items()}}
    raise WorkflowError("VALUE_TYPE")


def attrs(value): return {k:av(v) for k,v in value.items()}


def snapshot_condition(row):
    names = {"#inc":"record_incarnation", "#rev":"legacy_write_revision"}
    values = {":inc":row.incarnation, ":rev":row.revision}
    parts = ["#inc = :inc", "#rev = :rev"]
    for i,(field,value) in enumerate(row.data().items()):
        names["#f"+str(i)] = field; values[":f"+str(i)] = value
        parts.append("#f"+str(i)+" = :f"+str(i))
    for i,marker in enumerate(MARKERS):
        names["#m"+str(i)] = marker; parts.append("attribute_not_exists(#m"+str(i)+")")
    condition = " AND ".join(parts)
    require(len(condition.encode()) <= 4096, "EXPRESSION_BUDGET_REFUSED")
    return condition, values, names


def transaction(plan, table_name):
    """Offline low-level request SHAPE ONLY. No execute method or SDK import.

    Permanent lifetime witnesses are proposed adapter storage, not live records.
    Retirement/non-reuse must survive deletion, rollback and mixed-version writers.
    """
    require(type(plan) is Plan and build_plan(plan.operation, plan.before, plan.after, plan.effects) == plan, "PLAN_BINDING")
    require(type(table_name) is str and re.fullmatch(r"[A-Za-z0-9_.-]{3,255}", table_name), "TABLE")
    old = {r.key:r for r in plan.before}
    actions = []
    def action(kind, item=None, key=None, condition="attribute_not_exists(PK)", values=None, names=None):
        spec = {"TableName":table_name, "ConditionExpression":condition}
        if item is not None: spec["Item"] = attrs(item)
        else: spec["Key"] = attrs(key)
        if values: spec["ExpressionAttributeValues"] = attrs(values)
        if names: spec["ExpressionAttributeNames"] = names
        require(len(condition.encode()) <= 4096, "EXPRESSION_BUDGET_REFUSED")
        actions.append({kind:spec})
    for row in plan.after:
        key = row.key
        action("ConditionCheck", key={"PK":"RESERVATION#"+key.token(),"SK":"PERMANENT"})
        lifetime = {"PK":"LIFETIME#"+key.token(),"SK":"PERMANENT"}
        if key not in old:
            action("Put", item=lifetime | {"incarnation":row.incarnation,"retired":False})
            condition, values, names = "attribute_not_exists(PK)", None, None
        else:
            prior = old[key]
            action("ConditionCheck", key=lifetime, condition="incarnation = :inc AND retired = :no AND attribute_not_exists(#ttl) AND attribute_not_exists(#expires)", values={":inc":prior.incarnation,":no":False}, names={"#ttl":"ttl","#expires":"expires_at"})
            condition, values, names = snapshot_condition(prior)
        if row == old.get(key):
            action("ConditionCheck", key={"PK":key.pk,"SK":key.sk}, condition=condition, values=values, names=names)
        else:
            action("Put", item=row.item(), condition=condition, values=values, names=names)
    namespace = "OP#"+plan.operation.tenant+"#"+plan.operation.operation_id
    action("Put", item={"PK":namespace,"SK":"RECEIPT","binding":plan.binding,"result":"PERSISTED_EFFECTS_PENDING",
                         "plan_json":canonical({"operation":plan.operation.__dict__,
                            "before":[r.item() for r in plan.before],"after":[r.item() for r in plan.after],
                            "effects":[{"id":e.effect_id,"kind":e.kind,"target":[e.target.tenant,e.target.pk,e.target.sk],"payload":e.payload} for e in plan.effects]})})
    for effect in plan.effects:
        action("Put", item={"PK":namespace,"SK":"EFFECT#"+effect.effect_id,"binding":plan.binding,
                            "kind":effect.kind,"payload":effect.payload,"target_pk":effect.target.pk,"target_sk":effect.target.sk,
                            "tenant":effect.target.tenant,"state":"PENDING","revision":1,"claim_id":""})
    targets=[]
    for entry in actions:
        spec=next(iter(entry.values())); item=spec.get("Key",spec.get("Item"))
        targets.append((item["PK"]["S"],item["SK"]["S"]))
        require(len(canonical(spec).encode())*2+1024 < 350*1024, "ITEM_BUDGET_REFUSED")
    require(len(targets)==len(set(targets)), "DUPLICATE_ITEM")
    require(len(actions)<=100 and sum(len(canonical(a).encode())*2+1024 for a in actions)<3*1024*1024, "OVERSIZED_REFUSED")
    return {"TransactItems":actions}


@dataclass(frozen=True)
class Intent:
    tenant: str
    operation_id: str
    effect_id: str
    binding: str
    state: str = "PENDING"
    revision: int = 1
    claim_id: str = ""


def check_intent(intent, plan, effect_id, expected):
    require(type(intent) is Intent and type(plan) is Plan, "INTENT_SHAPE")
    require(build_plan(plan.operation,plan.before,plan.after,plan.effects)==plan, "PLAN_BINDING")
    require((intent.tenant,intent.operation_id,intent.effect_id,intent.binding)==
            (plan.operation.tenant,plan.operation.operation_id,effect_id,plan.binding), "INTENT_BINDING")
    require(effect_id in {e.effect_id for e in plan.effects}, "INTENT_BINDING")
    require(version(intent.revision)==version(expected), "STALE_INTENT")
    require(type(intent.state) is str and intent.state in {"PENDING","CLAIMED","HOLD","DONE"}, "INTENT_STATE")
    if intent.state == "PENDING":
        require(type(intent.claim_id) is str and intent.claim_id == "", "CLAIM_MISMATCH")
    else:
        ident(intent.claim_id)


def claim(intent, plan, effect_id, expected, claim_id):
    check_intent(intent,plan,effect_id,expected); ident(claim_id)
    require(intent.state=="PENDING" and intent.claim_id=="", "RECONCILIATION_REQUIRED")
    return replace(intent,state="CLAIMED",revision=version(intent.revision+1),claim_id=claim_id)


def report(intent, plan, effect_id, expected, claim_id, outcome):
    check_intent(intent,plan,effect_id,expected)
    require(intent.state=="CLAIMED" and intent.claim_id==claim_id and bool(claim_id), "CLAIM_MISMATCH")
    require(outcome in {"APPLIED","UNKNOWN","NOT_APPLIED"}, "OUTCOME")
    # NOT_APPLIED also needs authoritative evidence before another irreversible attempt.
    return replace(intent,state="DONE" if outcome=="APPLIED" else "HOLD",revision=version(intent.revision+1))


@dataclass(frozen=True)
class Evidence:
    tenant: str
    operation_id: str
    effect_id: str
    binding: str
    claim_id: str
    outcome: str
    verified: bool = False
    current: bool = False


def reconcile(intent, plan, effect_id, expected, evidence):
    check_intent(intent,plan,effect_id,expected)
    require(type(evidence) is Evidence and evidence.verified is True and evidence.current is True, "TRUSTED_EVIDENCE_REQUIRED")
    require((evidence.tenant,evidence.operation_id,evidence.effect_id,evidence.binding,evidence.claim_id)==
            (intent.tenant,intent.operation_id,intent.effect_id,intent.binding,intent.claim_id), "EVIDENCE_BINDING")
    require(intent.state in {"CLAIMED","HOLD"} and bool(intent.claim_id), "RECONCILIATION_REQUIRED")
    require(evidence.outcome in {"APPLIED","NOT_APPLIED"}, "AUTHORITATIVE_OUTCOME_REQUIRED")
    return replace(intent,state="DONE" if evidence.outcome=="APPLIED" else "PENDING",
                   revision=version(intent.revision+1),claim_id="" if evidence.outcome=="NOT_APPLIED" else intent.claim_id)


def effect_update_request(plan, old, expected, table_name, action, context):
    """Inactive conditional claim/ack/reconciliation request shape.

    Derives new only through claim/report/reconcile guards. No public API, signer or
    provider authority exists here. Every original aggregate/lifetime remains fenced.
    """
    check_intent(old, plan, old.effect_id, expected)
    if action == "CLAIM":
        new = claim(old,plan,old.effect_id,expected,context)
    elif action == "REPORT":
        require(type(context) is tuple and len(context)==2, "REPORT_CONTEXT")
        new = report(old,plan,old.effect_id,expected,*context)
    elif action == "RECONCILE":
        new = reconcile(old,plan,old.effect_id,expected,context)
    else:
        raise WorkflowError("INTENT_TRANSITION")
    require(new.revision == old.revision+1, "STALE_INTENT")
    require((old.state,new.state) in {("PENDING","CLAIMED"),("CLAIMED","DONE"),
            ("CLAIMED","HOLD"),("CLAIMED","PENDING"),("HOLD","DONE"),("HOLD","PENDING")}, "INTENT_TRANSITION")
    # Reuse the validated transaction's reservation/lifetime specifications, then
    # replace create-time lifetime puts with current-incarnation condition checks.
    original = transaction(plan, table_name)["TransactItems"]
    actions = []
    for index,row in enumerate(plan.after):
        actions.append(original[index*3])
        lifetime = {"PK":"LIFETIME#"+row.key.token(),"SK":"PERMANENT"}
        actions.append({"ConditionCheck":{"TableName":table_name,"Key":attrs(lifetime),
            "ConditionExpression":"incarnation = :inc AND retired = :no AND attribute_not_exists(#ttl) AND attribute_not_exists(#exp)",
            "ExpressionAttributeNames":{"#ttl":"ttl","#exp":"expires_at"},
            "ExpressionAttributeValues":attrs({":inc":row.incarnation,":no":False})}})
        condition,values,names = snapshot_condition(row)
        actions.append({"ConditionCheck":{"TableName":table_name,"Key":attrs({"PK":row.key.pk,"SK":row.key.sk}),
            "ConditionExpression":condition,"ExpressionAttributeNames":names,"ExpressionAttributeValues":attrs(values)}})
    pk = "OP#"+old.tenant+"#"+old.operation_id
    actions.append({"ConditionCheck":{"TableName":table_name,"Key":attrs({"PK":pk,"SK":"RECEIPT"}),
        "ConditionExpression":"binding = :binding","ExpressionAttributeValues":attrs({":binding":old.binding})}})
    actions.append({"Update":{"TableName":table_name,"Key":attrs({"PK":pk,"SK":"EFFECT#"+old.effect_id}),
        "ConditionExpression":"binding = :binding AND tenant = :tenant AND #state = :old AND revision = :rev AND claim_id = :claim",
        "UpdateExpression":"SET #state = :new, revision = :next, claim_id = :next_claim",
        "ExpressionAttributeNames":{"#state":"state"},
        "ExpressionAttributeValues":attrs({":binding":old.binding,":tenant":old.tenant,":old":old.state,":rev":old.revision,
            ":claim":old.claim_id,":new":new.state,":next":new.revision,":next_claim":new.claim_id})}})
    require(len(actions)<=100 and sum(len(canonical(a).encode())*2+1024 for a in actions)<3*1024*1024, "OVERSIZED_REFUSED")
    return {"TransactItems":actions}
