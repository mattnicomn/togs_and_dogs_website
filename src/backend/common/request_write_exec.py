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
    raw/prepared boundary is by SOURCE/RESULT TYPE, not by inspecting dict keys,
    so a legitimate application map containing a key literally named "S"/"N"/"M"
    stays valid and is never double-serialized.
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

# The 8 AttributeValue type discriminators. Used ONLY to detect an input that is
# ALREADY a prepared AttributeValue (a double-serialization error) - never to
# decide that an arbitrary application map is "pre-serialized". A real
# application map is distinguished because it is passed as a raw value to be
# serialized, whereas a prepared operand only ever appears where the spec puts
# serialized bytes. See _reject_if_already_serialized for the strict rule.
_AV_DISCRIMINATORS = frozenset({"S", "N", "B", "SS", "NS", "BS", "M", "L", "NULL", "BOOL"})


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
    if type(mapping) is not dict:
        raise _SerializationError("SER_NOT_A_MAP")
    _reject_if_already_serialized(mapping)
    out = {}
    for k, v in mapping.items():
        if type(k) is not str or not k:
            raise _SerializationError("SER_ATTR_NAME")
        out[k] = _serialize_value(v)
    return out


def _looks_like_attribute_value(obj):
    """True iff ``obj`` has the exact shape of a bare prepared AttributeValue.

    A bare AV is a single-key dict whose only key is an AV discriminator AND whose
    value matches that discriminator's payload shape (NULL->True, BOOL->bool,
    S/N->str, SS/NS/BS/L->list, M->dict, B->bytes/str). This is a SHAPE check used
    only to catch double-serialization; a legitimate single-key application map
    like {"S": 5} (payload is an int, not a str) does NOT match and stays valid.
    """
    if type(obj) is not dict or len(obj) != 1:
        return False
    (only_key, only_val), = obj.items()
    if only_key not in _AV_DISCRIMINATORS:
        return False
    return (
        (only_key == "NULL" and only_val is True)
        or (only_key == "BOOL" and type(only_val) is bool)
        or (only_key in ("S", "N") and type(only_val) is str)
        or (only_key in ("SS", "NS", "BS", "L") and type(only_val) is list)
        or (only_key == "M" and type(only_val) is dict)
        or (only_key == "B" and isinstance(only_val, (bytes, bytearray, str)))
    )


def _reject_if_already_serialized(mapping):
    """Fail closed if ``mapping`` is ALREADY a prepared AttributeValue map.

    The raw/prepared boundary is enforced by TYPE/position in this module, but as
    defence-in-depth we catch the two double-serialization shapes the live
    manual_external_adapter warned about, applied ONLY to the TOP-LEVEL attribute
    map (whose keys are attribute names):
      1. The map IS itself a bare AttributeValue (e.g. {"S": "x"}).
      2. The map is non-empty and EVERY value is itself a bare AttributeValue
         (e.g. {"PK": {"S": "x"}, "n": {"N": "1"}}) - i.e. a map whose values were
         already serialized, which would be double-wrapped if serialized again.
    A legitimate raw attribute map (values are raw scalars/containers) never
    matches: a raw value like {"S": "hello"} (one attribute among others) only
    trips case 2 if ALL siblings are also bare-AV-shaped, which a real raw map is
    not. Nested values are never passed here, so an attribute literally named
    "S"/"N"/"M" is untouched.
    """
    if _looks_like_attribute_value(mapping):
        raise _SerializationError(
            "SER_ALREADY_SERIALIZED",
            "input is itself a prepared AttributeValue (double-serialization)")
    if mapping and all(_looks_like_attribute_value(v) for v in mapping.values()):
        raise _SerializationError(
            "SER_ALREADY_SERIALIZED",
            "every attribute value is already an AttributeValue (double-serialization)")


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

    # Security-condition presence: the mandatory retirement fence and the
    # revision machinery must be present verbatim. We never rewrite them; we
    # refuse if a required clause/placeholder is absent.
    missing = _missing_update_security(spec)
    if missing is not None:
        return TranslationRefusal("MISSING_SECURITY_CONDITION", missing)

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
        # Create-only security: both key attributes must be fenced absent. Never
        # rewrite - refuse if the create-only condition is not present verbatim.
        if "attribute_not_exists(PK)" not in cond or "attribute_not_exists(SK)" not in cond:
            return TranslationRefusal("MISSING_SECURITY_CONDITION", "create-only attribute_not_exists")
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

    operands = []
    saw_request_retirement_fence = False
    for operand in spec.transact_items:
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
        # No delete may ever appear; the retire shape is Update-only by contract.
        # (The operand-key check above already guarantees this.)
        if "retired_lifetime" in names.values() and "(attribute_not_exists(#rl) OR #rl = :false)" in cond:
            saw_request_retirement_fence = True
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

    # The REQUEST operand must carry the mandatory not-already-retired fence.
    if not saw_request_retirement_fence:
        return TranslationRefusal("MISSING_SECURITY_CONDITION", "retire request retirement fence")

    token = _idempotency_token(table_name, "retire", operands)
    request = {"TransactItems": operands, "ClientRequestToken": token}

    size_refusal = _txn_size_preflight(operands, request)
    if size_refusal is not None:
        return size_refusal

    return PreparedTxn(table_name=table_name, op="retire", request=request, client_request_token=token)


# ---------------------------------------------------------------------------
# Internal security / size helpers
# ---------------------------------------------------------------------------

def _missing_update_security(spec):
    """Return a reason if a required UpdateSpec security clause is missing, else None.

    We NEVER rewrite a condition. We only refuse to translate a spec that lacks a
    mandatory fence, so a weakened/omitted condition can never be serialized into
    a live request through this adapter.
    """
    cond = spec.condition_expression
    names = spec.names
    values = spec.values
    # Mandatory retirement write-fence (PR58): names #rl -> retired_lifetime,
    # values :false == exact bool False, and the OR-group present verbatim.
    if "(attribute_not_exists(#rl) OR #rl = :false)" not in cond:
        return "retirement fence clause"
    if names.get("#rl") != "retired_lifetime":
        return "retired_lifetime name binding"
    if ":false" not in values or values[":false"] is not False:
        return "exact :false boolean"
    # Tenant + REQUEST identity fences.
    if "company_id = :tenant" not in cond:
        return "tenant fence"
    if "request_id = :reqid" not in cond or "client_id = :cliid" not in cond:
        return "request identity fence"
    # Revision pin + advance.
    if "#rev = :rev" not in cond:
        return "revision pin"
    if names.get("#rev") != "legacy_write_revision":
        return "revision name binding"
    if "#rev = :next" not in spec.update_expression:
        return "revision advance"
    if ":rev" not in values or ":next" not in values:
        return "revision values"
    # Incarnation pin (always emitted for an eligible write).
    if "#inc = :inc" not in cond or names.get("#inc") != "record_incarnation":
        return "incarnation fence"
    return None


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
