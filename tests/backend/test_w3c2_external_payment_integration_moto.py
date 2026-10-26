"""
W3-C2 — moto-backed END-TO-END integration tests for the MANUAL_EXTERNAL settlement
adapter (`common.manual_external_adapter.record_external_payment`).

Unlike the mock-only suite (which patches `table.meta.client` with a MagicMock that merely
captures the constructed operands), these tests drive the adapter against a REAL in-memory
DynamoDB backend provided by moto, through the adapter's ACTUAL low-level client
construction path (`_lowlevel_dynamodb_client` -> a genuine bare `boto3.client("dynamodb")`).

This is the regression guard for the serialization-boundary defect: the adapter encodes
operands once with `TypeSerializer`, so it MUST use a bare low-level client. The resource's
attached client (`resource.Table(...).meta.client`) would serialize the already-encoded
operands a second time and raise `TypeError: unhashable type: 'dict'` at the transaction
call. A MagicMock cannot catch that (it never runs boto3's transformer); only a real engine
(moto) exercising the real client seam can.

Strict isolation: synthetic credentials, us-east-1, `mock_aws` only. No real AWS, no network,
no Stripe, no route/UI. Auth/tenant are patched; the DynamoDB layer is the real moto engine.
"""

import os
import sys
import contextlib
from decimal import Decimal
from unittest.mock import patch

import pytest

# Make src/backend importable. This is an import-path change only; it does NOT mutate
# process-wide AWS environment state (that is scoped to the restoring fixture below).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "backend"))

import boto3  # noqa: E402
from moto import mock_aws  # noqa: E402

# Stable references to the SHARED application modules. These are imported ONCE and never
# reloaded; the moto binding is applied via temporary patching (patch.object) that pytest/
# mock restore at context exit, so no sys.modules or module-global state leaks out of a test.
import common.db as _db          # noqa: E402
import common.manual_external_adapter as _mx  # noqa: E402

TABLE_NAME = "w3c2-itest-table"

# Synthetic AWS context applied PER TEST and fully restored afterward (no import-time or
# process-wide mutation that could leak into unrelated tests).
_SYNTHETIC_AWS_ENV = {
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_SESSION_TOKEN": "testing",
    "AWS_SECURITY_TOKEN": "testing",
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_PROFILE": None,          # must be ABSENT (synthetic creds only, never a real profile)
    "DATA_TABLE_NAME": TABLE_NAME,
}


@pytest.fixture(autouse=True)
def _synthetic_aws_env(monkeypatch):
    """Scope synthetic AWS credentials/region/profile/table to each test and restore after.

    monkeypatch records and reverts every change (set or delete) at test teardown, so this
    module cannot leak AWS env state, boto3 default-session config, or DATA_TABLE_NAME into
    unrelated tests. All work remains offline (moto intercepts; synthetic creds only).
    """
    for key, value in _SYNTHETIC_AWS_ENV.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    yield


def _create_table(ddb):
    t = ddb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"},
                   {"AttributeName": "SK", "KeyType": "RANGE"}],
        AttributeDefinitions=[{"AttributeName": "PK", "AttributeType": "S"},
                              {"AttributeName": "SK", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    t.wait_until_exists()
    return t


def _event():
    return {"requestContext": {"authorizer": {"claims": {
        "email": "owner@example.com", "cognito:groups": "owner",
        "custom:company_id": "co-1",
    }}}}


def _seed_request(table, **over):
    item = {
        "PK": "REQ#req-1", "SK": "CLIENT#cli-1", "entity_type": "REQUEST",
        "company_id": "co-1", "client_id": "cli-1",
        "payment_requirement": "FULL", "payment_status": "UNPAID",
        "amount_required_cents": 5000, "deposit_amount_cents": 0,
        "amount_paid_cents": 0, "currency": "USD", "quote_status": "ACCEPTED",
    }
    item.update(over)
    table.put_item(Item=item)


@contextlib.contextmanager
def _moto_adapter(seed=True, company="co-1", **seed_over):
    """Stand up a real moto table and TEMPORARILY bind common.db to it — no module reloads.

    Yields (adapter_module, table). The adapter runs its REAL client path:
    _lowlevel_dynamodb_client builds a bare boto3 client, which moto intercepts.

    Isolation contract (why this does not leak):
    - NO ``importlib.reload`` of common.db or common.manual_external_adapter. Reloading
      mutates sys.modules and shared module globals that outlive the ``mock_aws`` context,
      leaving dangling references to an expired moto Table. We import both modules ONCE at
      module load and never replace them.
    - The moto binding is applied with ``patch.object`` on the SHARED ``common.db`` module
      (``table`` and ``TABLE_NAME``). mock restores the exact original attribute objects on
      context exit, so after the test ``common.db.table`` is byte-identical to what it was
      before (no expired-moto-resource reference remains).
    - The adapter reads ``common.db.table`` / ``common.db.get_item`` lazily at call time, so
      patching ``common.db`` is sufficient; the adapter needs no reload.
    - Auth/tenant are patched to a trusted owner; the DynamoDB layer is the real moto engine.
    """
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table(ddb)

        with contextlib.ExitStack() as stack:
            # Temporary, auto-restoring binding of the shared common.db module to moto.
            stack.enter_context(patch.object(_db, "table", table))
            stack.enter_context(patch.object(_db, "TABLE_NAME", TABLE_NAME))
            stack.enter_context(patch("common.auth.require_owner_or_admin", return_value="owner"))
            stack.enter_context(patch("common.auth.get_current_company_id", return_value=company))
            stack.enter_context(patch("common.auth.get_claims", return_value={"email": "owner@example.com"}))
            stack.enter_context(patch("common.auth.DEFAULT_COMPANY_ID", "tog_and_dogs"))

            if seed:
                _seed_request(table, **seed_over)

            yield _mx, table


def _op(**over):
    base = dict(event=_event(), request_id="req-1", client_id="cli-1",
                amount_delta_cents=5000, currency="USD", idempotency_key="idem-1",
                payment_method_category="CASH")
    base.update(over)
    return base


def _summary(table):
    return table.get_item(Key={"PK": "REQ#req-1", "SK": "CLIENT#cli-1"}).get("Item") or {}


def _events(table):
    # Query the REQUEST item collection for PAYEVENT# rows.
    from boto3.dynamodb.conditions import Key
    resp = table.query(KeyConditionExpression=Key("PK").eq("REQ#req-1") & Key("SK").begins_with("PAYEVENT#"))
    return resp.get("Items", [])


# ---------------------------------------------------------------------------
# 1. Successful two-item atomic settlement actually persists (regression guard).
# ---------------------------------------------------------------------------

def test_two_item_transaction_persists_event_and_summary():
    with _moto_adapter() as (mx, table):
        out = mx.record_external_payment(**_op())
        assert out["result"] == mx.RECORD_CREATED
        assert out["resulting_status"] == "PAID"
        # REAL persistence (would have failed with double-serialization TypeError before fix).
        s = _summary(table)
        assert s.get("payment_status") == "PAID"
        assert int(s.get("amount_paid_cents")) == 5000
        assert int(s.get("payment_summary_revision")) == 1
        evs = _events(table)
        assert len(evs) == 1
        assert evs[0]["payment_provider"] == "MANUAL_EXTERNAL"


# ---------------------------------------------------------------------------
# 2. Serialized exactly once: a round-trip read returns native scalars, not nested
#    AttributeValue dicts (double serialization would store {"M": {...}} shapes).
# ---------------------------------------------------------------------------

def test_values_serialized_exactly_once():
    with _moto_adapter() as (mx, table):
        mx.record_external_payment(**_op())
        ev = _events(table)[0]
        # amount_delta_cents must be a plain numeric (Decimal), not a wrapped dict.
        assert not isinstance(ev["amount_delta_cents"], dict)
        assert int(ev["amount_delta_cents"]) == 5000
        # PK/SK are plain strings, not {"S": ...}.
        assert ev["PK"] == "REQ#req-1"
        assert isinstance(ev["SK"], str) and ev["SK"].startswith("PAYEVENT#")
        s = _summary(table)
        assert not isinstance(s["amount_paid_cents"], dict)


# ---------------------------------------------------------------------------
# 3. Idempotent duplicate replay (same key + identical evidence) — no re-apply.
# ---------------------------------------------------------------------------

def test_duplicate_same_event_idempotent_no_reapply():
    with _moto_adapter() as (mx, table):
        first = mx.record_external_payment(**_op())
        assert first["result"] == mx.RECORD_CREATED
        second = mx.record_external_payment(**_op())  # identical op + key
        assert second["result"] == mx.RECORD_DUPLICATE_SAME_EVENT
        s = _summary(table)
        assert int(s["amount_paid_cents"]) == 5000          # not doubled
        assert int(s["payment_summary_revision"]) == 1      # not bumped
        assert len(_events(table)) == 1                      # still one event


# ---------------------------------------------------------------------------
# 4. Conflicting evidence under the same key -> rejected, no second write.
# ---------------------------------------------------------------------------

def test_conflicting_idempotency_key_no_write():
    with _moto_adapter() as (mx, table):
        mx.record_external_payment(**_op(amount_delta_cents=2500))
        with pytest.raises(mx.ManualExternalError) as ei:
            mx.record_external_payment(**_op(amount_delta_cents=4000))  # same key, diff amount
        assert ei.value.code == mx.ERR_IDEMPOTENCY_CONFLICT
        assert len(_events(table)) == 1
        assert int(_summary(table)["amount_paid_cents"]) == 2500


# ---------------------------------------------------------------------------
# 5. Stale revision protection (concurrent out-of-band bump) -> StaleSummaryConflict,
#    atomic: no event written, summary unchanged by the failed attempt.
# ---------------------------------------------------------------------------

def test_stale_revision_conflict_is_atomic():
    # Stale-conflict requires a CONCURRENT writer: the adapter reads the summary at one
    # revision, then another writer advances it before the adapter's conditional write
    # commits. We simulate that by having the adapter LOAD a revision-0 view (via get_item)
    # while the ACTUAL stored summary is already at a higher revision, so the adapter's
    # pinned condition (revision == 0) fails at commit -> StaleSummaryConflict, atomically.
    with _moto_adapter(seed=False) as (mx, table):
        # Actual stored summary is at revision 3 with a different raw status/paid.
        _seed_request(table, payment_summary_revision=3, amount_paid_cents=1500,
                      payment_status="PARTIALLY_PAID")
        # The adapter's load sees a stale revision-0 / UNPAID view (concurrent-writer race).
        stale_view = {
            "PK": "REQ#req-1", "SK": "CLIENT#cli-1", "entity_type": "REQUEST",
            "company_id": "co-1", "client_id": "cli-1",
            "payment_requirement": "FULL", "payment_status": "UNPAID",
            "amount_required_cents": 5000, "deposit_amount_cents": 0,
            "amount_paid_cents": 0, "currency": "USD", "quote_status": "ACCEPTED",
        }

        def _stale_get(pk, sk):
            if isinstance(sk, str) and sk.startswith("CLIENT#"):
                return dict(stale_view)   # adapter loads the stale view
            return None                   # no existing PAYMENT_EVENT

        with patch("common.db.get_item", side_effect=_stale_get):
            with pytest.raises(mx.StaleSummaryConflict):
                mx.record_external_payment(**_op())

        # Atomic: no event persisted; the ACTUAL stored summary is untouched by the attempt.
        assert len(_events(table)) == 0
        s = _summary(table)
        assert int(s["payment_summary_revision"]) == 3
        assert int(s["amount_paid_cents"]) == 1500
        assert s["payment_status"] == "PARTIALLY_PAID"


# ---------------------------------------------------------------------------
# 6. Atomic failure: a settlement rejected at the state guard writes nothing.
# ---------------------------------------------------------------------------

def test_terminal_state_rejection_writes_nothing():
    with _moto_adapter(seed=False) as (mx, table):
        _seed_request(table, payment_status="PAID", amount_paid_cents=5000,
                      payment_summary_revision=1)
        with pytest.raises(mx.ManualExternalError) as ei:
            mx.record_external_payment(**_op())
        assert ei.value.code == mx.ERR_STATE_CONFLICT
        assert len(_events(table)) == 0                      # no new event
        assert int(_summary(table)["amount_paid_cents"]) == 5000


# ---------------------------------------------------------------------------
# 7. Partial -> full settlement across two real transactions.
# ---------------------------------------------------------------------------

def test_partial_then_full_settlement():
    with _moto_adapter() as (mx, table):
        o1 = mx.record_external_payment(**_op(amount_delta_cents=2000, idempotency_key="k1"))
        assert o1["resulting_status"] == "PARTIALLY_PAID"
        assert o1["payment_completed_at"] is None
        s1 = _summary(table)
        assert int(s1["amount_paid_cents"]) == 2000
        assert int(s1["payment_summary_revision"]) == 1

        o2 = mx.record_external_payment(**_op(amount_delta_cents=3000, idempotency_key="k2"))
        assert o2["resulting_status"] == "PAID"
        assert o2["payment_completed_at"] is not None
        s2 = _summary(table)
        assert int(s2["amount_paid_cents"]) == 5000
        assert int(s2["payment_summary_revision"]) == 2
        assert len(_events(table)) == 2


# ---------------------------------------------------------------------------
# 8. The adapter uses a genuine bare low-level client (not the resource client).
# ---------------------------------------------------------------------------

def test_adapter_uses_bare_lowlevel_client_not_resource_client():
    with _moto_adapter() as (mx, table):
        client, name = mx._resolve_table_and_name()
        assert name == TABLE_NAME
        # The resource's attached client carries the dynamodb attribute transformer under
        # the 'before-parameter-build.dynamodb' event; the bare client must NOT be the same
        # object as the resource's attached client.
        assert client is not table.meta.client
        # And it must be a low-level dynamodb client.
        assert client.meta.service_model.service_name == "dynamodb"


# ---------------------------------------------------------------------------
# 9. Low-level client configuration is PRESERVED from the resource (region/endpoint),
#    not silently defaulted.
# ---------------------------------------------------------------------------

def test_lowlevel_client_preserves_region_and_endpoint():
    with _moto_adapter() as (mx, table):
        src_meta = table.meta.client.meta
        bare = mx._lowlevel_dynamodb_client(table)
        # Region and endpoint must match the resource client's resolved configuration.
        assert bare.meta.region_name == src_meta.region_name
        assert bare.meta.endpoint_url == src_meta.endpoint_url
        # botocore Config is carried (not None) so retries/timeouts/signing are preserved.
        assert bare.meta.config is not None


# ---------------------------------------------------------------------------
# 10. Fail-closed: if the resource client config cannot be introspected, the adapter
#     raises ERR_INFRASTRUCTURE rather than silently building a default-endpoint client.
# ---------------------------------------------------------------------------

def test_lowlevel_client_fails_closed_when_config_unavailable():
    with _moto_adapter() as (mx, table):
        class _NoMetaResource:
            # A resource whose .meta.client is missing -> config cannot be resolved.
            class meta:
                client = None
        with pytest.raises(mx.ManualExternalError) as ei:
            mx._lowlevel_dynamodb_client(_NoMetaResource)
        assert ei.value.code == mx.ERR_INFRASTRUCTURE


# ---------------------------------------------------------------------------
# 11. Isolation regression: _moto_adapter must NOT leak shared module state.
#     After the context exits, common.db.table / TABLE_NAME are the exact original
#     objects, and the shared modules in sys.modules are the same objects (no reload),
#     so no dangling reference to the expired moto resource remains.
# ---------------------------------------------------------------------------

def test_moto_adapter_restores_shared_module_state():
    import common.db as db_before
    import common.manual_external_adapter as mx_before

    # Snapshot the pre-context shared state (identity, not just value).
    table_before = db_before.table
    table_name_before = db_before.TABLE_NAME
    db_module_id_before = id(sys.modules["common.db"])
    mx_module_id_before = id(sys.modules["common.manual_external_adapter"])

    with _moto_adapter() as (mx, table):
        # Inside the context, common.db is temporarily bound to the moto table.
        assert db_before.table is table
        assert db_before.TABLE_NAME == TABLE_NAME
        mx.record_external_payment(**_op())  # exercise the real path while bound

    # After exit: every binding is restored to the ORIGINAL object (no moto leak).
    assert db_before.table is table_before
    assert db_before.TABLE_NAME == table_name_before
    # The moto table must NOT remain referenced by the shared module.
    assert db_before.table is not table
    # No module was reloaded/replaced in sys.modules (identity preserved).
    assert id(sys.modules["common.db"]) == db_module_id_before
    assert id(sys.modules["common.manual_external_adapter"]) == mx_module_id_before
    assert sys.modules["common.manual_external_adapter"] is mx_before
    assert sys.modules["common.db"] is db_before
