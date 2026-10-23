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

def test_not_authorized_maps_403():
    with patch(ADAPTER, side_effect=ManualExternalError('not authorized to record external payment')):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 403


def test_request_not_found_maps_404():
    with patch(ADAPTER, side_effect=ManualExternalError('request not found: REQ#req-001/CLIENT#client-001')):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 404


def test_cross_tenant_maps_403_non_disclosing():
    with patch(ADAPTER, side_effect=ManualExternalError('cross-tenant request ownership mismatch')):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 403
    # Must not disclose the owning tenant or internal detail.
    assert 'tenant' not in json.loads(resp['body'])['error'].lower()


def test_client_ownership_mismatch_maps_403():
    with patch(ADAPTER, side_effect=ManualExternalError('client ownership mismatch for request')):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 403


def test_validation_error_maps_400():
    with patch(ADAPTER, side_effect=ManualExternalError('amount_delta_cents must be a positive integer of cents')):
        resp = admin_handler(make_event(body=_valid_body(amount_delta_cents=-1)), None)
    assert resp['statusCode'] == 400


def test_stale_summary_maps_409():
    with patch(ADAPTER, side_effect=StaleSummaryConflict('stale revision')):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 409


def test_unexpected_error_maps_500_no_leak():
    with patch(ADAPTER, side_effect=RuntimeError('boto internal detail')):
        resp = admin_handler(make_event(body=_valid_body()), None)
    assert resp['statusCode'] == 500
    assert 'boto internal detail' not in json.loads(resp['body'])['error']


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
