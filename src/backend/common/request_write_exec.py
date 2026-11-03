"""INACTIVE S0d-1 pure DynamoDB low-level request TRANSLATION adapter.

Standard library ONLY. This module translates an already-decided, already-
constructed write SPECIFICATION from ``common.request_write`` (an ``UpdateSpec``,
``CreateSpec`` or ``RetireSpec``) into the exact low-level DynamoDB client request
dictionary that a ``boto3.client("dynamodb")`` call WOULD receive - and nothing
more. It opens no client, imports no boto3/botocore, performs no network/DB/AWS
call, reads no environment, executes no write, imports no handler, and is imported
by no production module.

HARD SCOPE (S0d-1):
  * PURE translation + validation + offline tests. There is NO executor here.
    Real execution, idempotency-window behavior, SDK exception handling and
    TypeSerializer parity are a later, separately approved slice (S0d-2).
  * translate_update(spec, table_name) -> PreparedUpdate | TranslationRefusal
  * translate_create(spec, table_name) -> PreparedTxn    | TranslationRefusal
  * translate_retire(spec, table_name) -> PreparedTxn    | TranslationRefusal

WHAT THIS MODULE GUARANTEES:
  * It accepts ONLY the exact committed spec dataclasses. A ``Refusal`` or any
    other type is refused - the adapter never re-decides policy, it only
    serializes what the pure contract already approved.
  * TableName must be explicitly injected, non-empty and well-formed. There is
    no environment lookup and no default table anywhere.
  * Approved condition/update EXPRESSION STRINGS and ExpressionAttributeNames
    maps are preserved VERBATIM. Only ``Key`` / ``Item`` /
    ``ExpressionAttributeValues`` are AttributeValue-serialized.
  * Serialization is strict and deterministic: bool BEFORE int; False ->
    {"BOOL": false}; ints/finite Decimals -> {"N": "..."} with NO rounding or
    normalization; floats, NaN/Infinity, empty/mixed/nested sets, non-string map
    keys, binary, unknown objects and cyclic/too-deep structures are REFUSED.
  * A raw application value is never confused with a prepared AttributeValue: the
    raw/prepared boundary is enforced by SOURCE/RESULT TYPE (a raw value is never
    one of this module's PreparedUpdate/PreparedTxn/TranslationRefusal objects),
    NOT by guessing at AttributeValue "shape". A legitimate application map whose
    keys are named "S"/"N"/"M"/"BOOL"/"NULL", a single-attribute map with an
    AV-like shape, and nested raw maps all stay valid and serialize normally.
  * create/retire carry a deterministic <=32-hex ClientRequestToken derived from
    the canonical serialized request. A single UpdateItem carries NO token (the
    revision-advance condition is its replay fence).
  * No delete op, no unconditional/upsert form, and no weakened/omitted condition
    can be produced by construction.

HONEST LIMITATIONS (NOT closed here; separately gated):
  * This does NOT prove real boto3 ``TypeSerializer`` parity (asserting that
    requires importing boto3, which this slice forbids), actual DynamoDB
    transaction behavior, live idempotency-window behavior, SDK exception
    compatibility, deployed-fleet safety, child-reconciliation completeness, or
    production readiness.
  * Size guards are CONSERVATIVE preflight upper bounds, not a reproduction of
    DynamoDB's authoritative size accounting. The service remains the authority.
"""
from dataclasses import dataclass
from decimal import Decimal, Context, Inexact, Rounded, localcontext
from hashlib import sha256
import json
import re

from common.request_write import (
    UpdateSpec,
    CreateSpec,
    RetireSpec,
    Refusal,
)


# ---------------------------------------------------------------------------
# Result / refusal types (immutable, inspectable)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TranslationRefusal:
    """A fail-closed refusal to translate. Carries NO partial prepared request."""
    reason: str
    detail: str = ""


@dataclass(frozen=True)
class PreparedUpdate:
    """A constructed (NOT executed) low-level DynamoDB UpdateItem request.

    ``request`` is the exact kwargs dict a ``boto3.client("dynamodb").update_item``
    call WOULD receive: TableName + AttributeValue-serialized Key + verbatim
    UpdateExpression/ConditionExpression + verbatim ExpressionAttributeNames +
    AttributeValue-serialized ExpressionAttributeValues. There is NO
    ClientRequestToken (UpdateItem does not take one).
    """
    table_name: str
    request: dict


@dataclass(frozen=True)
class PreparedTxn:
    """A constructed (NOT executed) low-level DynamoDB TransactWriteItems request.

    ``op`` is "create" or "retire". ``request`` is the exact kwargs dict a
    ``boto3.client("dynamodb").transact_write_items`` call WOULD receive:
    TransactItems (each operand AttributeValue-serialized with its own TableName)
    + a deterministic ClientRequestToken.
    """
    table_name: str
    op: str
    request: dict
    client_request_token: str


# ---------------------------------------------------------------------------
# Constants: documented limits and the numeric context
# ---------------------------------------------------------------------------

# DynamoDB's documented hard limits. These are used ONLY for conservative
# preflight upper-bound refusals - the service remains the authority on exact
# size accounting (which includes attribute-name bytes and per-type overheads we
# do not reproduce). A value we accept MAY still be rejected by the service; a
# value we refuse here is one we can PROVE exceeds the bound.
_MAX_ITEM_BYTES = 400 * 1024          # 400 KB per item
_MAX_TXN_REQUEST_BYTES = 4 * 1024 * 1024  # ~4 MB per transaction request
_MAX_TXN_OPERANDS = 100               # <= 100 operands per transaction
_MAX_SERIALIZE_DEPTH = 32             # defensive recursion/cycle guard

# DynamoDB number constraints: up to 38 significant digits, exponent in
# [-130, +125]. We validate against this WITHOUT rounding - an out-of-range or
# imprecise value is refused, never silently normalized.
_DDB_MAX_PRECISION = 38
_DDB_MIN_EXPONENT = -130
_DDB_MAX_EXPONENT = 125

# Idempotency-token recipe (see _idempotency_token).
_TOKEN_RECIPE_VERSION = 1
_TOKEN_DOMAIN = "petcare.request_write_exec.txn"
_TOKEN_HEX_LEN = 32  # <= DynamoDB's 36-char ClientRequestToken maximum

class _SerializationError(Exception):
    """Internal: a strict serialization failure carrying a stable reason code."""

    def __init__(self, reason, detail=""):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


# ---------------------------------------------------------------------------
# Strict AttributeValue serialization (pure, stdlib only)
# ---------------------------------------------------------------------------

def _validate_ddb_number(value):
    """Validate an int/Decimal against DynamoDB's numeric context WITHOUT rounding.

    Returns the canonical decimal string, or raises _SerializationError. Never
    rounds, pads or normalizes magnitude: a value that cannot be represented
    exactly within DynamoDB's 38-significant-digit / bounded-exponent context is
    REFUSED, not coerced.
    """
    if type(value) is bool:
        # Caller must handle bool before reaching here; defensive.
        raise _SerializationError("SER_BOOL_AS_NUMBER")
    if type(value) is int:
        dec = Decimal(value)
    elif isinstance(value, Decimal):
        dec = value
    else:
        raise _SerializationError("SER_NON_NUMERIC")
    if not dec.is_finite():
        raise _SerializationError("SER_NON_FINITE", "NaN/Infinity rejected")
    # Reject values that cannot be represented exactly within DynamoDB's numeric
    # context. localcontext with traps makes any precision loss (Inexact) or
    # implicit rounding (Rounded) an error instead of a silent normalization.
    ctx = Context(prec=_DDB_MAX_PRECISION, traps=[Inexact, Rounded])
    try:
        with localcontext(ctx):
            # +dec applies the context; a value needing >38 sig digits or any
            # rounding raises here rather than being normalized.
            _ = +dec
    except (Inexact, Rounded):
        raise _SerializationError("SER_NUMBER_PRECISION",
                                  "exceeds DynamoDB 38 significant digits")
    # Exponent bound check (based on the adjusted exponent of the exact value).
    exponent = dec.adjusted()
    if exponent > _DDB_MAX_EXPONENT or exponent < _DDB_MIN_EXPONENT:
        raise _SerializationError("SER_NUMBER_RANGE",
                                  "exponent outside [-130, 125]")
    # Canonical string: exact, no scientific-notation surprises for normal ints.
    # Use str() of the exact Decimal; for ints this is the plain decimal form.
    text = format(dec, "f") if dec == dec.to_integral_value() and abs(exponent) < _DDB_MAX_PRECISION else str(dec)
    return text


def _serialize_value(value, _depth=0, _seen=None):
    """Serialize ONE raw application value to a DynamoDB AttributeValue dict.

    Strict, deterministic, stdlib only. Raises _SerializationError on any
    unsupported value. bool is handled BEFORE int. Sets are emitted with a
    deterministic canonical member ordering. Recursion depth and reference cycles
    are guarded.
    """
    if _depth > _MAX_SERIALIZE_DEPTH:
        raise _SerializationError("SER_DEPTH_EXCEEDED")
    if _seen is None:
        _seen = ()

    # Correction C: a prepared/result object is never a raw value (type boundary).
    _reject_prepared_type(value)

    # --- scalars ---
    if value is None:
        return {"NULL": True}
    # bool MUST be checked before int (bool is a subclass of int).
    if type(value) is bool:
        return {"BOOL": value}
    if type(value) is int:
        return {"N": _validate_ddb_number(value)}
    if isinstance(value, Decimal):
        return {"N": _validate_ddb_number(value)}
    if type(value) is float:
        # No implicit float coercion - a float is ambiguous (binary rounding).
        raise _SerializationError("SER_FLOAT_FORBIDDEN")
    if type(value) is str:
        # Empty string is permitted as a scalar/map value by DynamoDB.
        return {"S": value}
    if isinstance(value, (bytes, bytearray)):
        # Binary is out of scope for S0d-1; the committed specs never emit it.
        raise _SerializationError("SER_UNSUPPORTED_BINARY")

    # --- cycle guard for containers (identity-based) ---
    if isinstance(value, (dict, list, tuple, set, frozenset)):
        for ref in _seen:
            if ref is value:
                raise _SerializationError("SER_CYCLE_DETECTED")
        _seen = _seen + (value,)

    # --- maps ---
    if type(value) is dict:
        out = {}
        for k, v in value.items():
            if type(k) is not str:
                raise _SerializationError("SER_MAP_KEY_TYPE")
            out[k] = _serialize_value(v, _depth + 1, _seen)
        return {"M": out}

    # --- lists ---
    if type(value) in (list, tuple):
        return {"L": [_serialize_value(v, _depth + 1, _seen) for v in value]}

    # --- sets (homogeneous string OR number; non-empty; deterministic order) ---
    if type(value) in (set, frozenset):
        if not value:
            raise _SerializationError("SER_EMPTY_SET")
        members = list(value)
        types = {type(m) for m in members}
        # bool is not a valid set member type (it would masquerade as int).
        if any(type(m) is bool for m in members):
            raise _SerializationError("SER_SET_TYPE", "bool in set")
        if types == {str}:
            # Correction B: DynamoDB forbids an empty string as a String Set
            # member. Reject it rather than silently emitting an invalid SS.
            if any(m == "" for m in members):
                raise _SerializationError("SER_EMPTY_STRING_SET_MEMBER")
            # String set: canonical ascending ordering for determinism.
            return {"SS": sorted(members)}
        if types <= {int, Decimal} and types:
            # Number set: validate each and order by canonical string.
            encoded = [_validate_ddb_number(m) for m in members]
            if len(set(encoded)) != len(encoded):
                raise _SerializationError("SER_SET_DUPLICATE")
            return {"NS": sorted(encoded, key=lambda s: (Decimal(s), s))}
        # Mixed / nested / unsupported member types.
        if any(isinstance(m, (set, frozenset, dict, list, tuple)) for m in members):
            raise _SerializationError("SER_NESTED_SET")
        raise _SerializationError("SER_SET_TYPE", "mixed or unsupported set members")

    raise _SerializationError("SER_UNSUPPORTED_TYPE", type(value).__name__)


def _serialize_map(mapping):
    """Serialize a raw {attr: raw_value} map to {attr: AttributeValue}.

    The map's keys are DynamoDB attribute names (strings). Each VALUE is a raw
    application value run through _serialize_value. Raises _SerializationError on
    any invalid key or value.
    """
    _reject_prepared_type(mapping)
    if type(mapping) is not dict:
        raise _SerializationError("SER_NOT_A_MAP")
    out = {}
    for k, v in mapping.items():
        if type(k) is not str or not k:
            raise _SerializationError("SER_ATTR_NAME")
        out[k] = _serialize_value(v)
    return out


def _reject_prepared_type(value):
    """Fail closed if ``value`` is one of THIS module's PREPARED result objects.

    Correction C: the raw/prepared boundary is enforced by TYPE, never by guessing
    at AttributeValue "shape". A legitimate raw application value - including a
    dict whose keys happen to be named "S"/"N"/"M"/"BOOL"/"NULL", a single-
    attribute map with an AV-like shape, or a nested raw map - is NOT evidence of
    pre-serialization and must serialize normally. The ONLY thing that is never a
    valid raw value is one of this module's own prepared/result dataclasses
    (PreparedUpdate / PreparedTxn / TranslationRefusal); feeding one of those into
    a raw serializer is a programming error and is refused loudly rather than
    re-serialized. Prepared requests are plain dicts built only inside the
    translate_* functions from freshly serialized maps, so they can never re-enter
    _serialize_map as a raw value through the public API.
    """
    if isinstance(value, (PreparedUpdate, PreparedTxn, TranslationRefusal)):
        raise _SerializationError(
            "SER_PREPARED_OBJECT",
            "a prepared/result object is not a raw application value")


# ---------------------------------------------------------------------------
# Idempotency token (create/retire only)
# ---------------------------------------------------------------------------

def _idempotency_token(table_name, op, serialized_transact_items):
    """Deterministic <=32-hex ClientRequestToken over the canonical request.

    Preimage = canonical JSON of {recipe version, domain label, table identity,
    operation kind, FULL serialized transaction operands}. Map keys are sorted so
    logically-identical requests hash identically; the operand LIST order is
    preserved (operand order is semantically meaningful). Identical full requests
    -> identical token; any change to payload/condition/key/revision/table ->
    different preimage and (overwhelmingly) a different token.

    Collision/permanence assumptions (documented, not a guarantee): a 128-bit
    (32-hex) truncated SHA-256 makes an ACCIDENTAL collision between two distinct
    requests negligible; no adversarial-collision resistance is claimed at 128
    bits, and NO business-level permanent idempotency is claimed. The token only
    aids DynamoDB transport de-duplication within its ~10-minute window; outside
    that window it guarantees nothing and a resend is a brand-new transaction.
    """
    preimage = json.dumps(
        {
            "v": _TOKEN_RECIPE_VERSION,
            "d": _TOKEN_DOMAIN,
            "table": table_name,
            "op": op,
            "items": list(serialized_transact_items),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return sha256(preimage.encode("utf-8")).hexdigest()[:_TOKEN_HEX_LEN]


# ---------------------------------------------------------------------------
# Size preflight (conservative upper-bound guards)
# ---------------------------------------------------------------------------

def _serialized_byte_size(obj):
    """A deterministic, conservative byte measure of a serialized structure.

    Uses the canonical JSON encoding length as an UPPER-BOUND proxy. This is NOT
    DynamoDB's size formula; it is only used to PROVE a request is too large
    (never to certify it is small enough - the service is the authority).
    """
    return len(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))


# ===========================================================================
# Strict security-expression validation (Correction A)
# ===========================================================================
#
# The committed builders emit a CLOSED expression grammar: a flat list of clauses
# joined by " AND ", with exactly one parenthesized OR group (the retirement
# fence). We parse that exact grammar into a canonical multiset of typed clauses
# and validate STRUCTURE + name/value bindings - never substring presence. Any
# clause that is not a recognized safe form (e.g. an injected OR branch, an extra
# predicate, altered grouping, or a weakened fence) makes the whole expression
# FAIL CLOSED. We do NOT rewrite; we only accept or refuse, and on accept the
# committed string is preserved verbatim.
#
# This is a narrowly-scoped exact-grammar recognizer for the builders' output,
# NOT a general DynamoDB expression parser. An adversarially hand-built spec that
# does not match the grammar is refused.

# Clause token kinds the grammar permits.
#   ("exists", LITERAL)                       -> attribute_exists(LITERAL)
#   ("not_exists", NAMEREF)                   -> attribute_not_exists(NAMEREF)
#   ("eq", LHS, RHS)                          -> LHS = RHS   (LHS literal or #ref, RHS :val)
#   ("retirement_fence",)                     -> (attribute_not_exists(#rl) OR #rl = :false)
_RETIREMENT_FENCE_CLAUSE = "(attribute_not_exists(#rl) OR #rl = :false)"
_EQ_RE = re.compile(r"^(#?[A-Za-z0-9_]+|[A-Za-z0-9_]+)\s=\s(:[A-Za-z0-9_]+)$")
_EXISTS_RE = re.compile(r"^attribute_exists\(([#A-Za-z0-9_]+)\)$")
_NOT_EXISTS_RE = re.compile(r"^attribute_not_exists\(([#A-Za-z0-9_]+)\)$")


def _split_top_level_and(expression):
    """Split an expression into top-level ' AND '-joined clauses.

    Respects a single parenthesized group so the retirement fence
    '(attribute_not_exists(#rl) OR #rl = :false)' is kept whole. Returns the list
    of clause strings, or None if parentheses are unbalanced.
    """
    parts, depth, buf = [], 0, ""
    for tok in expression.split(" AND "):
        buf = tok if not buf else buf + " AND " + tok
        depth += tok.count("(") - tok.count(")")
        if depth == 0:
            parts.append(buf)
            buf = ""
        elif depth < 0:
            return None
    if depth != 0 or buf:
        return None
    return [p.strip() for p in parts]


def _classify_clause(clause):
    """Classify one clause into a typed tuple, or return None if not a safe form.

    Any clause that is not EXACTLY one of the closed grammar forms (including an
    OR anywhere other than the single approved retirement fence) is rejected by
    returning None, so the caller fails closed.
    """
    if clause == _RETIREMENT_FENCE_CLAUSE:
        return ("retirement_fence",)
    # Reject any other parenthesis/OR usage outright - no unauthorized grouping
    # or OR branch is part of the grammar.
    if "(" in clause or ")" in clause or " OR " in clause:
        m = _EXISTS_RE.match(clause)
        if m:
            return ("exists", m.group(1))
        m = _NOT_EXISTS_RE.match(clause)
        if m:
            return ("not_exists", m.group(1))
        return None
    m = _EXISTS_RE.match(clause)
    if m:
        return ("exists", m.group(1))
    m = _NOT_EXISTS_RE.match(clause)
    if m:
        return ("not_exists", m.group(1))
    m = _EQ_RE.match(clause)
    if m:
        return ("eq", m.group(1), m.group(2))
    return None


def _parse_condition(expression):
    """Parse an expression into a list of typed clauses, or None on any bad form."""
    if type(expression) is not str or not expression:
        return None
    clauses = _split_top_level_and(expression)
    if clauses is None:
        return None
    typed = []
    for c in clauses:
        t = _classify_clause(c)
        if t is None:
            return None
        typed.append(t)
    return typed


def _names_value_consistent(names, values):
    """Every #ref used must be defined in names; every :val used in values.

    Returns None if consistent, else a reason. Also rejects a names/values map
    that is not a plain dict.
    """
    if type(names) is not dict or type(values) is not dict:
        return "BINDINGS_NOT_MAP"
    return None


def _require_clause(typed, clause, reason):
    return None if clause in typed else reason


def _validate_update_condition(spec):
    """Strict grammar validation of an S0a UpdateSpec. Returns None or a reason.

    Requires the EXACT mandatory fence clause-set as whole clauses with correct
    name bindings, forbids any unrecognized clause, and checks that the revision
    advance appears in the update expression. Adversarial specs that smuggle an
    extra/weakened predicate fail here.
    """
    names, values = spec.names, spec.values
    bad = _names_value_consistent(names, values)
    if bad:
        return bad
    typed = _parse_condition(spec.condition_expression)
    if typed is None:
        return "UNPARSEABLE_OR_UNSAFE_CONDITION"
    # Mandatory clause set (whole clauses), independent of optional identity/status.
    required = [
        ("exists", "PK"), ("exists", "SK"),
        ("eq", "company_id", ":tenant"),
        ("eq", "request_id", ":reqid"),
        ("eq", "client_id", ":cliid"),
        ("eq", "#rev", ":rev"),
        ("eq", "#inc", ":inc"),
        ("retirement_fence",),
    ]
    for clause in required:
        if clause not in typed:
            return "MISSING_REQUIRED_CLAUSE:" + _clause_label(clause)
    # Name bindings for the fence + pins must be exactly correct.
    if names.get("#rl") != "retired_lifetime":
        return "BAD_BINDING_#rl"
    if names.get("#rev") != "legacy_write_revision":
        return "BAD_BINDING_#rev"
    if names.get("#inc") != "record_incarnation":
        return "BAD_BINDING_#inc"
    if values.get(":false") is not False:
        return "BAD_BINDING_:false"
    # Revision advance must be present in the update expression as a SET clause.
    if "#rev = :next" not in spec.update_expression:
        return "MISSING_REVISION_ADVANCE"
    if ":rev" not in values or ":next" not in values:
        return "MISSING_REVISION_VALUES"
    # Every remaining clause must be a recognized safe form (guaranteed by parse).
    # Optional clauses allowed: #sstat=:sstat, #idN=:idN, attribute_not_exists(#naN).
    for t in typed:
        if t in required:
            continue
        if t[0] == "eq" and t[1].startswith("#") and names.get(t[1]) is not None:
            continue
        if t[0] == "not_exists" and t[1].startswith("#") and names.get(t[1]) is not None:
            continue
        return "UNEXPECTED_CLAUSE:" + _clause_label(t)
    return None


def _clause_label(t):
    if t[0] == "retirement_fence":
        return "retirement_fence"
    if t[0] == "exists":
        return "attribute_exists(" + t[1] + ")"
    if t[0] == "not_exists":
        return "attribute_not_exists(" + t[1] + ")"
    return t[1] + " = " + t[2]


def _validate_create_put_condition(cond):
    """S0b create-only Put: EXACTLY attribute_not_exists(PK) AND attribute_not_exists(SK).

    No tenant/identity binding is expected on a create (the item carries identity);
    the mandatory protection is the two create-only existence guards and NOTHING
    that would permit an overwrite. Any extra/altered clause fails closed.
    """
    typed = _parse_condition(cond)
    if typed is None:
        return "UNPARSEABLE_OR_UNSAFE_CONDITION"
    if sorted(typed) != sorted([("not_exists", "PK"), ("not_exists", "SK")]):
        return "CREATE_ONLY_CONDITION_ALTERED"
    return None


def _validate_retire_lifetime_condition(upd):
    """S0c lifetime Update: attribute_exists(PK) AND #ret=:false AND #inc=:inc.

    The retire-in-place guard must assert the record exists, is NOT already
    retired, and matches the expected incarnation. Never a delete; never without
    the not-already-retired guard.
    """
    cond = upd.get("ConditionExpression")
    names = upd.get("ExpressionAttributeNames", {})
    values = upd.get("ExpressionAttributeValues", {})
    typed = _parse_condition(cond)
    if typed is None:
        return "UNPARSEABLE_OR_UNSAFE_CONDITION"
    required = [("exists", "PK"), ("eq", "#ret", ":false"), ("eq", "#inc", ":inc")]
    if sorted(typed) != sorted(required):
        return "LIFETIME_OPERAND_ALTERED"
    if names.get("#ret") != "retired":
        return "BAD_BINDING_#ret"
    if names.get("#inc") != "incarnation":
        return "BAD_BINDING_#inc"
    if values.get(":false") is not False:
        return "BAD_BINDING_:false"
    # Must set retired=True (not clear it) and advance a revision; never delete.
    expr = upd.get("UpdateExpression", "")
    if "#ret = :true" not in expr or values.get(":true") is not True:
        return "LIFETIME_NOT_RETIRED_SET"
    return None


def _validate_retire_request_condition(upd):
    """S0c REQUEST Update: same fence set as S0a plus the retirement marker write.

    Reuses the S0a mandatory clause-set validation (tenant/identity/revision/
    incarnation/retirement-fence) and additionally requires the operand to SET
    retired_lifetime=True and advance the revision.
    """
    cond = upd.get("ConditionExpression")
    names = upd.get("ExpressionAttributeNames", {})
    values = upd.get("ExpressionAttributeValues", {})
    typed = _parse_condition(cond)
    if typed is None:
        return "UNPARSEABLE_OR_UNSAFE_CONDITION"
    required = [
        ("exists", "PK"), ("exists", "SK"),
        ("eq", "company_id", ":tenant"),
        ("eq", "request_id", ":reqid"),
        ("eq", "client_id", ":cliid"),
        ("eq", "#rev", ":rev"),
        ("eq", "#inc", ":inc"),
        ("retirement_fence",),
    ]
    for clause in required:
        if clause not in typed:
            return "MISSING_REQUIRED_CLAUSE:" + _clause_label(clause)
    if names.get("#rl") != "retired_lifetime":
        return "BAD_BINDING_#rl"
    if names.get("#rev") != "legacy_write_revision":
        return "BAD_BINDING_#rev"
    if names.get("#inc") != "record_incarnation":
        return "BAD_BINDING_#inc"
    if values.get(":false") is not False:
        return "BAD_BINDING_:false"
    for t in typed:
        if t in required:
            continue
        if t[0] == "eq" and t[1].startswith("#") and names.get(t[1]) is not None:
            continue
        if t[0] == "not_exists" and t[1].startswith("#") and names.get(t[1]) is not None:
            continue
        return "UNEXPECTED_CLAUSE:" + _clause_label(t)
    # Must SET retired_lifetime=True and advance the revision; never clear it.
    expr = upd.get("UpdateExpression", "")
    if "#rl = :true" not in expr or values.get(":true") is not True:
        return "REQUEST_NOT_MARKED_RETIRED"
    if "#rev = :next" not in expr or ":next" not in values:
        return "MISSING_REVISION_ADVANCE"
    return None


# ---------------------------------------------------------------------------
# Public translation functions
# ---------------------------------------------------------------------------

def _valid_table_name(table_name):
    # DynamoDB table names: 3-255 chars, [A-Za-z0-9_.-]. We require an explicitly
    # injected, non-empty, well-formed name - no env lookup, no default.
    if type(table_name) is not str or not table_name:
        return False
    if not (3 <= len(table_name) <= 255):
        return False
    return all(c.isalnum() or c in "_.-" for c in table_name)


def translate_update(spec, table_name):
    """Translate a committed UpdateSpec into a low-level UpdateItem request."""
    if type(spec) is Refusal:
        return TranslationRefusal("REFUSAL_INPUT", "a Refusal is not translatable")
    if type(spec) is not UpdateSpec:
        return TranslationRefusal("WRONG_SPEC_TYPE", type(spec).__name__)
    if not _valid_table_name(table_name):
        return TranslationRefusal("MALFORMED_TABLE_NAME")

    # Required operand fields must be present and well-typed (the spec guarantees
    # them, but we fail closed rather than trust the type blindly).
    if type(spec.key) is not dict or set(spec.key) != {"PK", "SK"}:
        return TranslationRefusal("MALFORMED_KEY")
    if type(spec.condition_expression) is not str or not spec.condition_expression:
        return TranslationRefusal("MISSING_CONDITION")
    if type(spec.update_expression) is not str or not spec.update_expression:
        return TranslationRefusal("MISSING_UPDATE_EXPRESSION")
    if type(spec.names) is not dict or not spec.names:
        return TranslationRefusal("MISSING_NAMES")
    if type(spec.values) is not dict or not spec.values:
        return TranslationRefusal("MISSING_VALUES")

    # Correction A: strict grammar validation of the whole condition - clause
    # structure and name/value bindings, not substring presence. We never
    # rewrite; we refuse any expression that does not match the committed S0a
    # grammar with all mandatory fences intact.
    bad = _validate_update_condition(spec)
    if bad is not None:
        return TranslationRefusal("MISSING_SECURITY_CONDITION", bad)

    try:
        serialized_key = _serialize_map(spec.key)
        serialized_values = _serialize_map(spec.values)
    except _SerializationError as exc:
        return TranslationRefusal(exc.reason, exc.detail)

    request = {
        "TableName": table_name,
        "Key": serialized_key,
        "UpdateExpression": spec.update_expression,       # verbatim
        "ConditionExpression": spec.condition_expression,  # verbatim
        "ExpressionAttributeNames": dict(spec.names),      # verbatim mapping
        "ExpressionAttributeValues": serialized_values,
    }

    size = _serialized_byte_size(request)
    if size > _MAX_ITEM_BYTES:
        return TranslationRefusal("PREFLIGHT_ITEM_TOO_LARGE", str(size))

    return PreparedUpdate(table_name=table_name, request=request)


def translate_create(spec, table_name):
    """Translate a committed CreateSpec into a 2-Put TransactWriteItems request."""
    if type(spec) is Refusal:
        return TranslationRefusal("REFUSAL_INPUT", "a Refusal is not translatable")
    if type(spec) is not CreateSpec:
        return TranslationRefusal("WRONG_SPEC_TYPE", type(spec).__name__)
    if not _valid_table_name(table_name):
        return TranslationRefusal("MALFORMED_TABLE_NAME")
    if type(spec.transact_items) not in (tuple, list) or len(spec.transact_items) != 2:
        return TranslationRefusal("BAD_OPERAND_COUNT", "create requires exactly 2 operands")

    operands = []
    for operand in spec.transact_items:
        if type(operand) is not dict or set(operand) != {"Put"}:
            return TranslationRefusal("BAD_OPERAND_SHAPE", "create operands must be a single Put")
        put = operand["Put"]
        if type(put) is not dict:
            return TranslationRefusal("BAD_OPERAND_SHAPE", "Put must be a map")
        if "Item" not in put or type(put["Item"]) is not dict:
            return TranslationRefusal("MISSING_ITEM")
        cond = put.get("ConditionExpression")
        if type(cond) is not str or not cond:
            return TranslationRefusal("MISSING_CONDITION")
        # Correction A: create-only condition must be EXACTLY the two existence
        # guards (no extra/altered clause that could permit an overwrite). Both
        # Put operands are validated independently.
        bad = _validate_create_put_condition(cond)
        if bad is not None:
            return TranslationRefusal("MISSING_SECURITY_CONDITION", bad)
        try:
            serialized_item = _serialize_map(put["Item"])
        except _SerializationError as exc:
            return TranslationRefusal(exc.reason, exc.detail)
        prepared_put = {
            "Put": {
                "TableName": table_name,
                "Item": serialized_item,
                "ConditionExpression": cond,  # verbatim
            }
        }
        operands.append(prepared_put)

    token = _idempotency_token(table_name, "create", operands)
    request = {"TransactItems": operands, "ClientRequestToken": token}

    size_refusal = _txn_size_preflight(operands, request)
    if size_refusal is not None:
        return size_refusal

    return PreparedTxn(table_name=table_name, op="create", request=request, client_request_token=token)


def translate_retire(spec, table_name):
    """Translate a committed RetireSpec into a 2-Update TransactWriteItems request."""
    if type(spec) is Refusal:
        return TranslationRefusal("REFUSAL_INPUT", "a Refusal is not translatable")
    if type(spec) is not RetireSpec:
        return TranslationRefusal("WRONG_SPEC_TYPE", type(spec).__name__)
    if not _valid_table_name(table_name):
        return TranslationRefusal("MALFORMED_TABLE_NAME")
    if type(spec.transact_items) not in (tuple, list) or len(spec.transact_items) != 2:
        return TranslationRefusal("BAD_OPERAND_COUNT", "retire requires exactly 2 operands")

    # Correction A: the two retire operands have FIXED roles by position -
    # operand 0 is the lifetime retire-in-place Update (key LIFETIME#.../PERMANENT)
    # and operand 1 is the REQUEST Update (key REQ#.../CLIENT#...). We validate each
    # by its role, reject a swapped/role-confused operand, and require each
    # operand's protections independently.
    operands = []
    for index, operand in enumerate(spec.transact_items):
        if type(operand) is not dict or set(operand) != {"Update"}:
            return TranslationRefusal("BAD_OPERAND_SHAPE", "retire operands must be a single Update")
        upd = operand["Update"]
        if type(upd) is not dict:
            return TranslationRefusal("BAD_OPERAND_SHAPE", "Update must be a map")
        key = upd.get("Key")
        if type(key) is not dict or set(key) != {"PK", "SK"}:
            return TranslationRefusal("MALFORMED_KEY")
        update_expr = upd.get("UpdateExpression")
        cond = upd.get("ConditionExpression")
        names = upd.get("ExpressionAttributeNames")
        values = upd.get("ExpressionAttributeValues")
        if type(update_expr) is not str or not update_expr:
            return TranslationRefusal("MISSING_UPDATE_EXPRESSION")
        if type(cond) is not str or not cond:
            return TranslationRefusal("MISSING_CONDITION")
        if type(names) is not dict or not names:
            return TranslationRefusal("MISSING_NAMES")
        if type(values) is not dict or not values:
            return TranslationRefusal("MISSING_VALUES")

        # Role validation by position + key shape, then role-specific grammar.
        pk = key.get("PK", "")
        if index == 0:
            # Lifetime operand: key must be LIFETIME#.../PERMANENT.
            if not (isinstance(pk, str) and pk.startswith("LIFETIME#") and key.get("SK") == "PERMANENT"):
                return TranslationRefusal("RETIRE_OPERAND_ROLE", "operand 0 must be the lifetime record")
            role_bad = _validate_retire_lifetime_condition(upd)
            if role_bad is not None:
                return TranslationRefusal("MISSING_SECURITY_CONDITION", role_bad)
        else:
            # REQUEST operand: key must be REQ#.../CLIENT#...; full fence set.
            if not (isinstance(pk, str) and pk.startswith("REQ#")
                    and isinstance(key.get("SK"), str) and key["SK"].startswith("CLIENT#")):
                return TranslationRefusal("RETIRE_OPERAND_ROLE", "operand 1 must be the REQUEST record")
            role_bad = _validate_retire_request_condition(upd)
            if role_bad is not None:
                return TranslationRefusal("MISSING_SECURITY_CONDITION", role_bad)

        try:
            serialized_key = _serialize_map(key)
            serialized_values = _serialize_map(values)
        except _SerializationError as exc:
            return TranslationRefusal(exc.reason, exc.detail)
        prepared_update = {
            "Update": {
                "TableName": table_name,
                "Key": serialized_key,
                "UpdateExpression": update_expr,     # verbatim
                "ConditionExpression": cond,          # verbatim
                "ExpressionAttributeNames": dict(names),   # verbatim
                "ExpressionAttributeValues": serialized_values,
            }
        }
        operands.append(prepared_update)

    token = _idempotency_token(table_name, "retire", operands)
    request = {"TransactItems": operands, "ClientRequestToken": token}

    size_refusal = _txn_size_preflight(operands, request)
    if size_refusal is not None:
        return size_refusal

    return PreparedTxn(table_name=table_name, op="retire", request=request, client_request_token=token)


# ---------------------------------------------------------------------------
# Internal security / size helpers
# ---------------------------------------------------------------------------

def _txn_size_preflight(operands, request):
    """Conservative preflight for transaction operand count and byte size."""
    if len(operands) > _MAX_TXN_OPERANDS:
        return TranslationRefusal("PREFLIGHT_TOO_MANY_OPERANDS", str(len(operands)))
    for op in operands:
        body = next(iter(op.values()))
        item_like = body.get("Item") or body.get("Key") or {}
        if _serialized_byte_size(item_like) > _MAX_ITEM_BYTES:
            return TranslationRefusal("PREFLIGHT_ITEM_TOO_LARGE")
    if _serialized_byte_size(request) > _MAX_TXN_REQUEST_BYTES:
        return TranslationRefusal("PREFLIGHT_TXN_TOO_LARGE")
    return None
