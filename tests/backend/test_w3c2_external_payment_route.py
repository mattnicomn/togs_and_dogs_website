"""
W3-C2 — tests for the MANUAL_EXTERNAL payment API route
(`POST /admin/requests/{requestId}/external-payment`) in `handlers.admin_handler`.

Offline / mock-only. NO live AWS, NO Stripe, NO network. The route is a thin HTTP
adapter over the merged W3-C1 service `common.manual_external_adapter.record_external_payment`;
these tests exercise the route's auth gate, input validation, result->HTTP mapping, and
non-disclosing ownership errors with the adapter mocked. The adapter itself is covered by
`test_w3c1_manual_external_adapter.py`.
"""

import sys
import os
import json
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

os.environ.setdefault('DATA_TABLE_NAME', 'test-table')

from handlers.admin_handler import handler as admin_handler
from common.manual_external_adapter import (
    ManualExternalError,
    StaleSummaryConflict,
    RECORD_CREATED,
    RECORD_DUPLICATE_SAME_EVENT,
    RECORD_CONFLICTING_IDEMPOTENCY_KEY,
    ERR_VALIDATION,
    ERR_NOT_AUTHORIZED,
    ERR_OWNERSHIP,
    ERR_NOT_FOUND,
    ERR_STATE_CONFLICT,
    ERR_IDEMPOTENCY_CONFLICT,
    ERR_STALE_CONFLICT,
    ERR_INFRASTRUCTURE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PATH = '/admin/requests/req-001/external-payment'


def make_event(role='admin', company_id='tog_and_dogs', body=None,
               path_params=None, query_params=None):
    return {
        'httpMethod': 'POST',
        'path': PATH,
        'pathParameters': path_params or {'requestId': 'req-001'},
        'queryStringParameters': query_params or {},
        'body': json.dumps(body) if body is not None else None,
        'requestContext': {
            'authorizer': {
                'claims': {
                    'sub': 'test-sub-123',
                    'email': 'admin@example.com',
                    'cognito:groups': [role],
                    'custom:company_id': company_id,
                }
            }
        },
    }


def _ok_result(result=RECORD_CREATED):
    return {
        'result': result,
        'previous_status': 'UNPAID',
        'resulting_status': 'PAID',
        'amount_paid_cents': 5000,
        'payment_completed_at': '2026-09-24T00:00:00Z',
        'payment_summary_revision': 1,
        'booking_ready': True,
        'booking_ready_reason': 'paid_in_full',
    }


def _valid_body(**over):
    b = {
        'client_id': 'client-001',
        'amount_delta_cents': 5000,
        'currency': 'USD',
        'idempotency_key': 'idem-abc-123',
        'payment_method_category': 'CASH',
    }
    b.update(over)
    return b


ADAPTER = 'common.manual_external_adapter.record_external_payment'


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------

def test_staff_forbidden_no_adapter_call():
    with patch(ADAPTER) as rec:
        resp = admin_handler(make_event(role='staff', body=_valid_body()), None)
    assert resp['statusCode'] == 403
    rec.assert_not_called()


def test_client_forbidden_no_adapter_call():
    with patch(ADAPTER) as rec:
        resp = admin_handler(make_event(role='client', body=_valid_body()), None)
    assert resp['statusCode'] == 403
    rec.assert_not_called()


# ---------------------------------------------------------------------------
# Input validation (before adapter call)
# ---------------------------------------------------------------------------

def test_missing_client_id_bad_request():
    with patch(ADAPTER) as rec:
        body = _valid_body()
        del body['client_id']
        resp = admin_handler(make_event(body=body), None)
    assert resp['statusCode'] == 400
    rec.assert_not_called()


def test_missing_idempotency_key_bad_request():
    with patch(ADAPTER) as rec:
        body = _valid_body()
        del body['idempotency_key']
        resp = admin_handler(make_event(body=body), None)
    assert resp['statusCode'] == 400
    rec.assert_not_called()


def test_blank_idempotency_key_bad_request():
    with patch(ADAPTER) as rec:
        resp = admin_handler(make_event(body=_valid_body(idempotency_key='   ')), None)
    assert resp['statusCode'] == 400
    rec.assert_not_called()


def test_invalid_json_body_bad_request():
    with patch(ADAPTER) as rec:
        event = make_event()
        event['body'] = '{not json'
        resp = admin_handler(event, None)
    assert resp['statusCode'] == 400
    rec.assert_not_called()


def test_client_id_via_query_param_is_accepted():
    with patch(ADAPTER, return_value=_ok_result()) as rec:
        body = _valid_body()
        del body['client_id']
        resp = admin_handler(make_event(body=body, query_params={'clientId': 'client-001'}), None)
    assert resp['statusCode'] == 201
    rec.assert_called_once()


# ---------------------------------------------------------------------------
# Result -> HTTP mapping
# ---------------------------------------------------------------------------

def test_created_returns_201():
    with patch(ADAPTER, return_value=_ok_result(RECORD_CREATED)):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 201
    data = json.loads(resp['body'])
    assert data['result'] == RECORD_CREATED
    assert data['resulting_status'] == 'PAID'
    assert data['amount_paid_cents'] == 5000


def test_duplicate_same_event_returns_200():
    with patch(ADAPTER, return_value=_ok_result(RECORD_DUPLICATE_SAME_EVENT)):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 200
    assert json.loads(resp['body'])['result'] == RECORD_DUPLICATE_SAME_EVENT


def test_conflicting_idempotency_key_returns_409():
    with patch(ADAPTER, return_value=_ok_result(RECORD_CONFLICTING_IDEMPOTENCY_KEY)):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 409


# ---------------------------------------------------------------------------
# Adapter exceptions -> HTTP (non-disclosing)
# ---------------------------------------------------------------------------

# Mapping is on the STABLE `code`, never on message text. Each error here carries a
# sensitive/internal-looking message to prove it is NEVER echoed to the caller.

def _err_body_text(resp):
    return json.loads(resp['body']).get('error', '')


def test_not_authorized_maps_403():
    with patch(ADAPTER, side_effect=ManualExternalError('not authorized to record external payment', code=ERR_NOT_AUTHORIZED)):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 403


def test_request_not_found_maps_404():
    with patch(ADAPTER, side_effect=ManualExternalError('request not found: REQ#req-001/CLIENT#client-001', code=ERR_NOT_FOUND)):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 404
    # Must not echo the adapter message (which contained the REQ#/CLIENT# keys).
    assert 'REQ#' not in _err_body_text(resp)
    assert 'CLIENT#' not in _err_body_text(resp)


def test_ownership_maps_403_non_disclosing():
    # Ownership denial normalizes to the SAME generic 403 as role denial (no enumeration).
    with patch(ADAPTER, side_effect=ManualExternalError('request ownership mismatch', code=ERR_OWNERSHIP)):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 403
    assert _err_body_text(resp) == "Forbidden"
    assert 'tenant' not in _err_body_text(resp).lower()


def test_ownership_and_role_denial_are_indistinguishable():
    # L4: a caller cannot tell "not your tenant" (OWNERSHIP) from "not allowed" (role) or
    # from NOT_AUTHORIZED — all three return the identical generic 403 body.
    staff_resp = admin_handler(make_event(role='staff', body=_valid_body()), None)
    with patch(ADAPTER, side_effect=ManualExternalError('x', code=ERR_OWNERSHIP)):
        own_resp = admin_handler(make_event(body=_valid_body()), None)
    with patch(ADAPTER, side_effect=ManualExternalError('x', code=ERR_NOT_AUTHORIZED)):
        auth_resp = admin_handler(make_event(body=_valid_body()), None)
    assert staff_resp['statusCode'] == own_resp['statusCode'] == auth_resp['statusCode'] == 403
    assert _err_body_text(staff_resp) == _err_body_text(own_resp) == _err_body_text(auth_resp) == "Forbidden"


def test_validation_error_maps_400_no_message_leak():
    with patch(ADAPTER, side_effect=ManualExternalError('amount_delta_cents must be a positive integer of cents', code=ERR_VALIDATION)):
        resp = admin_handler(make_event(body=_valid_body(amount_delta_cents=-1)), None)
    assert resp['statusCode'] == 400
    # Fixed generic 400 message; raw adapter text is not echoed.
    assert 'amount_delta_cents' not in _err_body_text(resp)


def test_state_conflict_maps_409():
    with patch(ADAPTER, side_effect=ManualExternalError('cannot record settlement from status PAID', code=ERR_STATE_CONFLICT)):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 409


def test_idempotency_conflict_exception_maps_409():
    with patch(ADAPTER, side_effect=ManualExternalError('idempotency_key reused with a different payment payload', code=ERR_IDEMPOTENCY_CONFLICT)):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 409


def test_stale_summary_maps_409():
    with patch(ADAPTER, side_effect=StaleSummaryConflict('request payment summary changed concurrently; reload and retry')):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 409


def test_infrastructure_error_maps_500_no_leak():
    # L2: infra/transaction failures surface as a generic 500, never a 4xx, and never leak
    # internal/DynamoDB detail.
    with patch(ADAPTER, side_effect=ManualExternalError('DynamoDB table name is not configured', code=ERR_INFRASTRUCTURE)):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 500
    assert 'DynamoDB' not in _err_body_text(resp)


def test_transaction_failure_maps_500_no_aws_code_leak():
    with patch(ADAPTER, side_effect=ManualExternalError('payment transaction failed', code=ERR_INFRASTRUCTURE)):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 500
    assert 'transaction' not in _err_body_text(resp).lower()


def test_unexpected_error_maps_500_no_leak():
    with patch(ADAPTER, side_effect=RuntimeError('boto internal detail')):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 500
    assert 'boto internal detail' not in _err_body_text(resp)


def test_uncoded_manual_external_error_defaults_to_400():
    # Defense-in-depth: a ManualExternalError raised without an explicit code defaults to
    # ERR_VALIDATION -> generic 400 (never a silent 2xx, never a message leak).
    with patch(ADAPTER, side_effect=ManualExternalError('some new internal message')):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 400
    assert 'some new internal message' not in _err_body_text(resp)


def test_bare_payment_domain_error_maps_400_no_leak():
    # Defense-in-depth: a bare PaymentDomainError (parent, uncoded) from a reused domain
    # helper must map to a generic 400, not a 500, and must not echo its message.
    from common.payment_domain import PaymentDomainError
    with patch(ADAPTER, side_effect=PaymentDomainError('invalid canonical cents value: -100 (amount must not be negative)')):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 400
    assert 'canonical cents' not in _err_body_text(resp)


# ---------------------------------------------------------------------------
# Delegation contract: server-derived fields are never taken from the body
# ---------------------------------------------------------------------------

def test_adapter_called_with_path_request_id_and_no_status_passthrough():
    with patch(ADAPTER, return_value=_ok_result()) as rec:
        # Attempt to inject server-authoritative fields; they must be ignored (the
        # adapter signature has no such parameters, so the route must not forward them).
        body = _valid_body(payment_status='PAID', company_id='attacker', resulting_status='PAID')
        resp = admin_handler(make_event(body=body), None)
    assert resp['statusCode'] == 201
    _args, kwargs = rec.call_args
    assert kwargs['request_id'] == 'req-001'
    assert kwargs['client_id'] == 'client-001'
    assert kwargs['idempotency_key'] == 'idem-abc-123'
    assert kwargs['amount_delta_cents'] == 5000
    # No server-authoritative fields are forwarded as kwargs.
    assert 'payment_status' not in kwargs
    assert 'company_id' not in kwargs
    assert 'resulting_status' not in kwargs


def test_response_projection_has_no_stripe_or_raw_metadata_fields():
    with patch(ADAPTER, return_value=_ok_result()):
        resp = admin_handler(make_event(body=_valid_body(note='paid at front desk')), None)
    data = json.loads(resp['body'])
    for forbidden in ('stripe_payment_url', 'stripe_checkout_session_id', 'note', 'metadata', 'external_reference'):
        assert forbidden not in data


# ---------------------------------------------------------------------------
# L3: Adapter-level stable error-code binding (real adapter, mocked auth/db).
# These lock the adapter's rejection paths to their STABLE codes so a future message
# reword cannot silently change the route's HTTP mapping (the route maps on code only).
# ---------------------------------------------------------------------------

import contextlib
import importlib
from decimal import Decimal
import common.manual_external_adapter as mx
from common.payment_domain import PaymentRequirement, PaymentStatus, QuoteStatus


@pytest.fixture(autouse=True)
def _rebind_live_adapter_classes():
    """Test-isolation guard for the adapter-level tests below.

    `tests/backend/test_w3b_payment_domain.py` calls importlib.reload(common.payment_domain)
    in two coupling tests. A reload installs a BRAND-NEW PaymentDomainError class on the
    live module. The already-imported `common.manual_external_adapter` keeps its import-time
    reference to the OLD class in its `except PaymentDomainError` clauses, while the reloaded
    load_owned_request/canonical_cents raise the NEW class — so under full-suite ordering the
    adapter's translation would miss and an uncoded exception would escape. That is a
    test-ordering artifact of the reload, not a production path (production never reloads).
    We defend against it by reloading the adapter here so it re-binds to the live
    payment_domain classes, and re-resolving the module-global `mx` used by the tests.
    No product code is changed.
    """
    global mx, ManualExternalError, StaleSummaryConflict
    mx = importlib.reload(importlib.import_module("common.manual_external_adapter"))
    # Re-bind the exception classes the route tests raise so they match the adapter's
    # live classes (the ERR_* codes are plain strings and are identity-independent).
    ManualExternalError = mx.ManualExternalError
    StaleSummaryConflict = mx.StaleSummaryConflict
    yield


def _adapter_event():
    return {"requestContext": {"authorizer": {"claims": {
        "email": "owner@example.com", "cognito:groups": "owner",
        "custom:company_id": "co-1",
    }}}}


def _adapter_request(**over):
    base = {
        "PK": "REQ#req-1", "SK": "CLIENT#cli-1", "entity_type": "REQUEST",
        "company_id": "co-1", "client_id": "cli-1",
        "payment_requirement": PaymentRequirement.FULL,
        "payment_status": PaymentStatus.UNPAID,
        "amount_required_cents": 5000, "deposit_amount_cents": 0,
        "amount_paid_cents": 0, "currency": "USD",
        "quote_status": QuoteStatus.ACCEPTED,
    }
    base.update(over)
    return base


@contextlib.contextmanager
def _adapter_patched(request_item, *, role_ok=True, company="co-1", get_item_side=None):
    fake_client = MagicMock()
    fake_table = MagicMock()
    fake_table.name = "test-table"
    fake_table.meta.client = fake_client
    stack = contextlib.ExitStack()
    if role_ok:
        stack.enter_context(patch("common.auth.require_owner_or_admin", return_value="owner"))
    else:
        stack.enter_context(patch("common.auth.require_owner_or_admin", side_effect=PermissionError("denied")))
    stack.enter_context(patch("common.auth.get_current_company_id", return_value=company))
    stack.enter_context(patch("common.auth.get_claims", return_value={"email": "owner@example.com"}))
    if get_item_side is not None:
        stack.enter_context(patch("common.db.get_item", side_effect=get_item_side))
    else:
        def _default_get(pk, sk):
            if isinstance(sk, str) and sk.startswith("CLIENT#"):
                return request_item
            return None
        stack.enter_context(patch("common.db.get_item", side_effect=_default_get))
    stack.enter_context(patch("common.db.table", fake_table))
    stack.enter_context(patch("common.auth.DEFAULT_COMPANY_ID", "tog_and_dogs"))
    try:
        yield
    finally:
        stack.close()


def _call_adapter(**over):
    op = {
        "request_id": "req-1", "client_id": "cli-1", "amount_delta_cents": 5000,
        "currency": "USD", "idempotency_key": "idem-1",
        "payment_method_category": "CASH",
    }
    op.update(over)
    return mx.record_external_payment(_adapter_event(), **op)


def test_adapter_code_not_authorized():
    with _adapter_patched(_adapter_request(), role_ok=False):
        with pytest.raises(mx.ManualExternalError) as ei:
            _call_adapter()
    assert ei.value.code == mx.ERR_NOT_AUTHORIZED


def test_adapter_code_not_found_when_request_absent():
    # load_owned_request raises (no record) AND the existence probe finds nothing -> NOT_FOUND.
    with _adapter_patched(None, get_item_side=lambda pk, sk: None):
        with pytest.raises(mx.ManualExternalError) as ei:
            _call_adapter()
    assert ei.value.code == mx.ERR_NOT_FOUND


def test_adapter_code_ownership_when_cross_tenant():
    # REQUEST exists (probe finds it) but belongs to another tenant -> OWNERSHIP.
    other = _adapter_request(company_id="other-co")
    def _get(pk, sk):
        if isinstance(sk, str) and sk.startswith("CLIENT#"):
            return other
        return None
    with _adapter_patched(other, get_item_side=_get):
        with pytest.raises(mx.ManualExternalError) as ei:
            _call_adapter()
    assert ei.value.code == mx.ERR_OWNERSHIP


def test_adapter_code_validation_negative_amount():
    with _adapter_patched(_adapter_request()):
        with pytest.raises(mx.ManualExternalError) as ei:
            _call_adapter(amount_delta_cents=-100)
    assert ei.value.code == mx.ERR_VALIDATION


def test_adapter_code_validation_currency_mismatch():
    with _adapter_patched(_adapter_request(currency="USD")):
        with pytest.raises(mx.ManualExternalError) as ei:
            _call_adapter(currency="EUR")
    assert ei.value.code == mx.ERR_VALIDATION


def test_adapter_code_state_conflict_terminal_status():
    with _adapter_patched(_adapter_request(payment_status=PaymentStatus.PAID)):
        with pytest.raises(mx.ManualExternalError) as ei:
            _call_adapter()
    assert ei.value.code == mx.ERR_STATE_CONFLICT


def test_adapter_code_state_conflict_overpayment():
    with _adapter_patched(_adapter_request(amount_required_cents=5000, amount_paid_cents=0)):
        with pytest.raises(mx.ManualExternalError) as ei:
            _call_adapter(amount_delta_cents=6000)
    assert ei.value.code == mx.ERR_STATE_CONFLICT


def test_adapter_code_state_conflict_requirement_none():
    with _adapter_patched(_adapter_request(payment_requirement=PaymentRequirement.NONE)):
        with pytest.raises(mx.ManualExternalError) as ei:
            _call_adapter()
    assert ei.value.code == mx.ERR_STATE_CONFLICT


def test_adapter_code_infrastructure_when_table_unconfigured():
    # table resource None -> INFRASTRUCTURE (resolved during the transaction build).
    with _adapter_patched(_adapter_request()):
        with patch("common.db.table", None):
            with pytest.raises(mx.ManualExternalError) as ei:
                _call_adapter()
    assert ei.value.code == mx.ERR_INFRASTRUCTURE
