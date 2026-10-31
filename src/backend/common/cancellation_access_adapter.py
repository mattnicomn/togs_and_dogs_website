"""Inactive cancellation-specific access mapping. Standard library; no live I/O.

Injected verifier/reader dependencies are server-owned, never client-selected.
Their attestations are obligations, not token validation supplied by this module.
"""
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
import re
from typing import Protocol
from urllib.parse import urlsplit


class AccessError(ValueError):
    pass


def need(value,reason):
    if not value:raise AccessError(reason)


def ident(value):
    need(type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,128}",value),"IDENTITY")
    return value


def integer(value):
    need(type(value) is int and 1<=value<2**63,"CANONICAL_INTEGER")
    return value


def db_revision(value):
    if type(value) is Decimal:
        need(value.is_finite() and value==value.to_integral_value(),"DB_REVISION")
        value=int(value)
    return integer(value)


def frozen(value,depth=0):
    """Typed immutable evidence, preserving DB Decimal metadata and field presence."""
    need(depth<=16,"DEPTH")
    if type(value) is dict:
        need(all(type(k) is str for k in value),"FIELD_TYPE")
        return ("map",tuple((k,frozen(v,depth+1)) for k,v in sorted(value.items())))
    if type(value) is list:return ("list",tuple(frozen(v,depth+1) for v in value))
    need(type(value) in (str,int,bool,Decimal,type(None)),"FIELD_TYPE")
    if type(value) is Decimal:need(value.is_finite(),"FIELD_TYPE")
    return (type(value).__name__,str(value) if type(value) is Decimal else value)


def thaw(value):
    tag,body=value
    if tag=="map":return {k:thaw(v) for k,v in body}
    if tag=="list":return [thaw(v) for v in body]
    if tag=="Decimal":return Decimal(body)
    return body


def digest(value):
    def encode(v):
        if hasattr(v,"__dataclass_fields__"):
            return (type(v).__name__,tuple((k,encode(getattr(v,k))) for k in v.__dataclass_fields__))
        if type(v) is tuple:return ("tuple",tuple(encode(x) for x in v))
        need(type(v) in (str,int,bool,type(None)),"EVIDENCE_TYPE")
        return (type(v).__name__,v)
    return sha256(json.dumps(encode(value),separators=(",",":"),ensure_ascii=True).encode()).hexdigest()


def raw_digest(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()


def row(value):
    need(type(value) is tuple,"ROW_SHAPE")
    try:decoded=thaw(value)
    except (TypeError,ValueError,KeyError):raise AccessError("ROW_SHAPE") from None
    need(type(decoded) is dict and digest(frozen(decoded))==digest(value),"ROW_SHAPE")
    return decoded


IDENTITIES=("client_email","cognito_sub","linked_client_profile_id")
MARKERS=("canonical_worker_id","identity_revision","assignment_contract_version","assigned_worker_id",
         "assignment_revision","execution_revision","started_worker_id","started_assignment_revision",
         "workflow_revision","provisioning_state","worker_identity","worker_identity_"+"contract_version")
BLOCKERS=("INACTIVE_NO_RUNTIME","REAL_GATEWAY_AND_IDENTITY_VERIFIER_PENDING","FRESHNESS_POLICY_PENDING",
          "STORAGE_AND_ALL_WRITERS_PENDING","MIGRATION_RETENTION_API_AND_RELEASE_PENDING")


@dataclass(frozen=True)
class Configuration:
    issuers: tuple

    def validate(self):
        need(type(self.issuers) is tuple and bool(self.issuers) and len(set(self.issuers))==len(self.issuers),"ISSUER_CONFIGURATION")
        for issuer in self.issuers:
            need(type(issuer) is str,"ISSUER_CONFIGURATION")
            try:p=urlsplit(issuer)
            except ValueError:raise AccessError("ISSUER_CONFIGURATION") from None
            need(p.scheme=="https" and bool(p.hostname) and not p.username and not p.password
                 and not p.query and not p.fragment,"ISSUER_CONFIGURATION")


@dataclass(frozen=True)
class Query:
    tenant: str
    client_id: str
    request_id: str
    operation: str
    reason: str

    def validate(self):
        for value in (self.tenant,self.client_id,self.request_id,self.operation):ident(value)
        need(type(self.reason) is str,"REASON")

    def key(self):return ("REQ#"+self.request_id,"CLIENT#"+self.client_id)
    def token(self):return raw_digest([self.tenant,*self.key()])


@dataclass(frozen=True)
class GatewayEvidence:
    issuer: str
    subject: str
    tenant: str
    role: str
    principal_epoch: int
    tenant_epoch: int
    revocation_epoch: int
    observed_at: int
    valid_until: int


@dataclass(frozen=True)
class GatewayAttestation:
    facts_digest: str
    configuration_digest: str
    evidence_digest: str


@dataclass(frozen=True)
class LinkProof:
    issuer: str
    subject: str
    tenant: str
    client_id: str
    request_id: str
    profile_id: str
    incarnation: str
    revision: int
    bindings: tuple
    provenance_id: str


@dataclass(frozen=True)
class Bundle:
    request: tuple
    profiles: tuple
    tenant: tuple
    lifetime: tuple
    reservation: object
    receipt: object
    linkage: LinkProof
    principal_epoch: int
    tenant_epoch: int
    revocation_epoch: int
    revoked: bool
    lookup_complete: bool
    observation_id: str
    observed_at: int
    valid_until: int
    coherence: str


@dataclass(frozen=True)
class BundleAttestation:
    query_digest: str
    gateway_digest: str
    bundle_digest: str


class Reader(Protocol):
    def observe(self,query: Query,principal: GatewayEvidence) -> Bundle: ...


class Verifier(Protocol):
    def authenticate(self,facts: tuple,configuration: Configuration,now: int) -> GatewayEvidence: ...
    def verify_gateway(self,facts: tuple,configuration: Configuration,evidence: GatewayEvidence,now: int) -> GatewayAttestation: ...
    def verify_bundle(self,query: Query,principal: GatewayEvidence,bundle: Bundle,now: int) -> BundleAttestation: ...


@dataclass(frozen=True)
class AccessEvidence:
    query: Query
    facts: tuple
    principal: GatewayEvidence
    bundle: Bundle
    bindings: tuple

    @property
    def activation_ready(self):return False
    @property
    def blockers(self):return BLOCKERS


def event_facts(event):
    need(type(event) is dict,"EVENT")
    context=event.get("requestContext")
    need(type(context) is dict and type(context.get("authorizer")) is dict,"GATEWAY_EVIDENCE_REQUIRED")
    authorizer=context["authorizer"]
    rest=authorizer.get("claims")
    jwt=authorizer.get("jwt")
    need(jwt is None or type(jwt) is dict,"CLAIMS")
    http=jwt.get("claims") if jwt is not None else None
    need(not (rest is not None and http is not None),"AMBIGUOUS_CLAIMS")
    claims=rest if rest is not None else http
    need(type(claims) is dict,"CLAIMS")
    # Deliberately excludes credentials, email, body and client role fields.
    return frozen({k:claims[k] for k in ("iss","sub","custom:company_id","cognito:groups") if k in claims})


def lease(observed,until,now):
    need(type(now) is int and type(observed) is int and type(until) is int and 0<=observed<=now<=until,"STALE_EVIDENCE")


class CancellationAccessAdapter:
    def __init__(self,configuration,reader,verifier):
        need(type(configuration) is Configuration,"ISSUER_CONFIGURATION");configuration.validate()
        need(callable(getattr(reader,"observe",None)) and all(callable(getattr(verifier,m,None)) for m in
             ("authenticate","verify_gateway","verify_bundle")),"TRUSTED_DEPENDENCIES_REQUIRED")
        self.configuration=configuration;self.reader=reader;self.verifier=verifier

    def _principal(self,facts,principal,query,now):
        need(type(principal) is GatewayEvidence,"GATEWAY_PROOF")
        claims=row(facts)
        need(principal.issuer in self.configuration.issuers and claims.get("iss")==principal.issuer,"ISSUER")
        ident(principal.subject);ident(principal.tenant)
        need(claims.get("sub")==principal.subject,"SUBJECT")
        need(claims.get("custom:company_id")==principal.tenant==query.tenant,"TENANT")
        groups=claims.get("cognito:groups")
        if type(groups) is str:groups=[g.strip() for g in groups.split(',')]
        need(type(groups) is list and groups==["client"] and principal.role=="client","CUSTOMER_ROLE_ONLY")
        for value in (principal.principal_epoch,principal.tenant_epoch,principal.revocation_epoch):integer(value)
        lease(principal.observed_at,principal.valid_until,now)
        proof=self.verifier.verify_gateway(facts,self.configuration,principal,now)
        need(type(proof) is GatewayAttestation and digest(proof)==digest(GatewayAttestation(
             digest(facts),digest(self.configuration),digest(principal))),"GATEWAY_ATTESTATION")

    def _bundle(self,query,principal,bundle,now):
        need(type(bundle) is Bundle,"COMPLETE_OBSERVATION_REQUIRED")
        lease(bundle.observed_at,bundle.valid_until,now);ident(bundle.observation_id)
        for value in (bundle.principal_epoch,bundle.tenant_epoch,bundle.revocation_epoch):integer(value)
        need((bundle.principal_epoch,bundle.tenant_epoch,bundle.revocation_epoch)==
             (principal.principal_epoch,principal.tenant_epoch,principal.revocation_epoch),"STALE_SECURITY_EPOCH")
        need(bundle.revoked is False and bundle.lookup_complete is True and bundle.coherence=="COHERENT_SNAPSHOT","INCOMPLETE_OR_REVOKED")
        proof=self.verifier.verify_bundle(query,principal,bundle,now)
        need(type(proof) is BundleAttestation and digest(proof)==digest(BundleAttestation(
             digest(query),digest(principal),digest(bundle))),"BUNDLE_ATTESTATION")
        request=row(bundle.request);tenant=row(bundle.tenant);life=row(bundle.lifetime)
        need((request.get("PK"),request.get("SK"),request.get("company_id"),request.get("client_id"),request.get("request_id"))==
             (*query.key(),query.tenant,query.client_id,query.request_id),"EXACT_BOOKING")
        need(tenant.get("PK")=="TENANT#"+query.tenant and tenant.get("SK")=="METADATA"
             and tenant.get("is_active") is True and tenant.get("subscription_status")=="active","ACTIVE_TENANT_REQUIRED")
        need(request.get("status") in ("APPROVED","ASSIGNED"),"INITIAL_STATUS_ONLY")
        need(not any(k in request for k in MARKERS),"PROTECTED_MARKER")
        incarnation=ident(request.get("record_incarnation"));version=db_revision(request.get("legacy_write_revision"))
        need("audit_log" not in request or type(request["audit_log"]) is list,"AUDIT_SHAPE")
        for field in IDENTITIES:
            if field in request:need(type(request[field]) is str and bool(request[field].strip()),"OWNERSHIP_SHAPE")
        need(bundle.reservation is None,"RESERVATION_PRESENT")
        need(bundle.receipt is None,"REPLAY_ADAPTER_REQUIRED")  # Never promotes prepared/stored metadata to commit authority.
        need((life.get("PK"),life.get("SK"),life.get("incarnation"))==("LIFETIME#"+query.token(),"PERMANENT",incarnation)
             and life.get("retired") is False and "ttl" not in life and "expires_at" not in life,"LIVE_LIFETIME_REQUIRED")
        need(type(bundle.profiles) is tuple and len(bundle.profiles)==1,"UNIQUE_SUBJECT_LINK_REQUIRED")
        profile=row(bundle.profiles[0]);profile_id=ident(profile.get("client_id"))
        need((profile.get("PK"),profile.get("SK"),profile.get("company_id"),profile.get("cognito_sub"))==
             ("COMPANY#"+query.tenant,"CLIENT#"+profile_id,query.tenant,principal.subject)
             and profile.get("is_active") is True,"SUBJECT_PROFILE_LINK")
        link=bundle.linkage;need(type(link) is LinkProof,"OWNERSHIP_PROVENANCE_REQUIRED")
        integer(link.revision);ident(link.provenance_id)
        need((link.issuer,link.subject,link.tenant,link.client_id,link.request_id,link.profile_id,link.incarnation,link.revision)==
             (principal.issuer,principal.subject,query.tenant,query.client_id,query.request_id,profile_id,incarnation,version),"OWNERSHIP_PROVENANCE_BINDING")
        linked=request.get("linked_client_profile_id")
        need((linked is None and profile_id==query.client_id) or linked==profile_id,"LINKED_PROFILE_PROVENANCE")
        if "cognito_sub" in request:need(request["cognito_sub"]==principal.subject,"BOOKING_SUBJECT")
        need(type(link.bindings) is tuple and bool(link.bindings),"PERSISTED_BINDINGS_REQUIRED")
        fields=set()
        for pair in link.bindings:
            need(type(pair) is tuple and len(pair)==2,"PERSISTED_BINDINGS_REQUIRED")
            field,value=pair
            need(field in IDENTITIES and field not in fields and type(value) is str and bool(value.strip())
                 and field in request and request[field]==value,"PERSISTED_IDENTITY_CHANGED")
            fields.add(field)
        # The commit fence must contain a subject/profile identity, never just an email.
        need("cognito_sub" in fields or "linked_client_profile_id" in fields,"IMMUTABLE_OWNERSHIP_FENCE_REQUIRED")
        return link.bindings

    def observe(self,event,query,now):
        need(type(query) is Query,"QUERY");query.validate()
        facts=event_facts(event)
        principal=self.verifier.authenticate(facts,self.configuration,now)
        self._principal(facts,principal,query,now)
        bundle=self.reader.observe(query,principal)
        bindings=self._bundle(query,principal,bundle,now)
        return AccessEvidence(query,facts,principal,bundle,bindings)

    def verify_current(self,evidence,now):
        need(type(evidence) is AccessEvidence,"ACCESS_EVIDENCE")
        evidence.query.validate()
        self._principal(evidence.facts,evidence.principal,evidence.query,now)
        bindings=self._bundle(evidence.query,evidence.principal,evidence.bundle,now)
        need(digest(bindings)==digest(evidence.bindings),"ACCESS_BINDING")
        return evidence  # Verifier must recheck actual current evidence; lease/digest alone is insufficient.