"""OPS-3A.2A — Handler tests for client Accept/Decline wired into admin_handler:

  - POST /client/quotes/{requestId}/accept
  - POST /client/quotes/{requestId}/decline

Exercises HTTP dispatch, client-role gating, server-resolved ownership (never a
caller-supplied client_id), the non-disclosing 404, body validation (integer
expected_revision; decline_reason trim/blank/max-500), the atomic conditional write
guarding BOTH quote_revision and quote_status==SENT, the 409 mapping on
ConditionalCheckFailedException, strict duplicate/competing behavior, and the
read-only booking_ready computation on Accept (never persisting APPROVED).

No AWS/Terraform/network: the DynamoDB table is a local fake and auth helpers are
patched at their source modules. Pure contract math is covered by
tests/backend/test_quote_accept_decline.py.
"""
import sys
import os
import json
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))
os.environ.setdefault('DATA_TABLE_NAME', 'test-table')

import handlers.admin_handler as ah
from handlers.admin_handler import handler as admin_handler


class _ConditionalCheckFailedException(Exception):
    """Stand-in matching botocore's ConditionalCheckFailedException shape."""


class FakeTable:
    def __init__(self, raise_conditional=False):
        self.raise_conditional = raise_conditional
        self.update_calls = []
        exceptions = MagicMock()
        exceptions.ConditionalCheckFailedException = _ConditionalCheckFailedException
        client = MagicMock()
        client.exceptions = exceptions
        self.meta = MagicMock()
        self.meta.client = client

    def update_item(self, **kwargs):
        self.update_calls.append(kwargs)
        if self.raise_conditional:
            raise _ConditionalCheckFailedException("conditional check failed")
        return {}


def make_event(method, path, body=None, path_params=None, role='client',
               email='jane@example.com', company_id='tog_and_dogs'):
    return {
        'httpMethod': method,
        'path': path,
        'pathParameters': path_params or {},
        'queryStringParameters': {},
        'body': json.dumps(body) if body is not None else None,
        'requestContext': {
            'authorizer': {
                'claims': {
                    'sub': 'sub-client-1',
                    'email': email,
                    'email_verified': True,
                    'cognito:groups': [role],
                    'custom:company_id': company_id,
                }
            }
        },
    }


def make_sent_request(**overrides):
    base = {
        'PK': 'REQ#req-001',
        'SK': 'CLIENT#client-001',
        'entity_type': 'REQUEST',
        'company_id': 'tog_and_dogs',
        'request_id': 'req-001',
        'client_id': 'client-001',
        'service_type': '20-Minute Walk',
        'status': 'QUOTE_SENT',
        'quote_status': 'SENT',
        'quote_revision': 1,
        'quote_amount_cents': 5000,
        'currency': 'USD',
        'payment_requirement': 'NONE',
        'payment_status': 'NOT_REQUIRED',
    }
    base.update(overrides)
    return base


@pytest.fixture
def patched_auth(monkeypatch):
    role_mock = MagicMock(return_value='client')
    claims_mock = MagicMock(return_value={'email': 'jane@example.com', 'sub': 'sub-client-1'})
    vto_mock = MagicMock(return_value=None)
    resolve_mock = MagicMock(return_value='client-001')
    company_mock = MagicMock(return_value='tog_and_dogs')
    active_mock = MagicMock(return_value=None)

    monkeypatch.setattr(ah, 'get_effective_role', role_mock)
    monkeypatch.setattr(ah, 'get_claims', claims_mock)

    import common.auth as common_auth
    import common.entitlement as common_entitlement
    monkeypatch.setattr(common_auth, 'validate_tenant_ownership', vto_mock)
    monkeypatch.setattr(common_auth, 'resolve_client_identity', resolve_mock)
    monkeypatch.setattr(common_auth, 'get_current_company_id', company_mock)
    monkeypatch.setattr(common_entitlement, 'require_active_tenant', active_mock)
    return {
        'role': role_mock, 'claims': claims_mock, 'vto': vto_mock,
        'resolve': resolve_mock, 'company': company_mock, 'active': active_mock,
    }


def _invoke(event, table, get_item_return):
    orig_table = ah.table
    orig_get = ah.get_item
    try:
        ah.table = table
        ah.get_item = MagicMock(return_value=get_item_return)
        return admin_handler(event, None)
    finally:
        ah.table = orig_table
        ah.get_item = orig_get


# ===========================================================================
# Accept
# ===========================================================================

class TestClientQuoteAccept:

    def test_accept_success_sets_accepted_and_booking_ready(self, patched_auth):
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-001/accept',
                           body={'expected_revision': 1},
                           path_params={'requestId': 'req-001'})
        resp = _invoke(event, table, make_sent_request())
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['quote_status'] == 'ACCEPTED'
        assert body['quote_revision'] == 1
        assert body['quote_accepted_revision'] == 1
        # NONE payment requirement -> booking_ready true (read-only).
        assert body['booking_ready'] is True
        # Exactly one atomic write; condition guards revision + SENT; never APPROVED.
        assert len(table.update_calls) == 1
        call = table.update_calls[0]
        assert call['Key'] == {'PK': 'REQ#req-001', 'SK': 'CLIENT#client-001'}
        vals = call['ExpressionAttributeValues']
        assert vals[':qs'] == 'ACCEPTED'
        assert vals[':exprev'] == 1
        assert vals[':sent'] == 'SENT'
        assert 'APPROVED' not in [str(v) for v in vals.values()]

    def test_accept_booking_ready_false_when_full_payment_unpaid(self, patched_auth):
        table = FakeTable()
        req = make_sent_request(payment_requirement='FULL', payment_status='UNPAID')
        event = make_event('POST', '/client/quotes/req-001/accept',
                           body={'expected_revision': 1},
                           path_params={'requestId': 'req-001'})
        resp = _invoke(event, table, req)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['quote_status'] == 'ACCEPTED'
        assert body['booking_ready'] is False

    def test_accept_non_client_forbidden(self, patched_auth):
        patched_auth['role'].return_value = 'admin'
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-001/accept',
                           body={'expected_revision': 1},
                           path_params={'requestId': 'req-001'}, role='admin')
        resp = _invoke(event, table, make_sent_request())
        # Non-client in the client portal block -> 403 (resolve may also short-circuit)
        assert resp['statusCode'] in (401, 403)

    def test_accept_missing_expected_revision_400(self, patched_auth):
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-001/accept',
                           body={}, path_params={'requestId': 'req-001'})
        resp = _invoke(event, table, make_sent_request())
        assert resp['statusCode'] == 400
        assert len(table.update_calls) == 0

    def test_accept_non_int_expected_revision_400(self, patched_auth):
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-001/accept',
                           body={'expected_revision': '1'},
                           path_params={'requestId': 'req-001'})
        resp = _invoke(event, table, make_sent_request())
        assert resp['statusCode'] == 400

    def test_accept_bool_expected_revision_400(self, patched_auth):
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-001/accept',
                           body={'expected_revision': True},
                           path_params={'requestId': 'req-001'})
        resp = _invoke(event, table, make_sent_request())
        assert resp['statusCode'] == 400

    def test_accept_not_owned_non_disclosing_404(self, patched_auth):
        # get_item returns None (cross-client requestId misses on resolved client_id).
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-999/accept',
                           body={'expected_revision': 1},
                           path_params={'requestId': 'req-999'})
        resp = _invoke(event, table, None)
        assert resp['statusCode'] == 404
        assert len(table.update_calls) == 0

    def test_accept_tenant_mismatch_non_disclosing_404(self, patched_auth):
        patched_auth['vto'].side_effect = PermissionError("cross tenant")
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-001/accept',
                           body={'expected_revision': 1},
                           path_params={'requestId': 'req-001'})
        resp = _invoke(event, table, make_sent_request(company_id='other'))
        assert resp['statusCode'] == 404
        assert len(table.update_calls) == 0

    def test_accept_stale_revision_409(self, patched_auth):
        # Current revision 2, client sends 1 -> pure layer rejects -> 409.
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-001/accept',
                           body={'expected_revision': 1},
                           path_params={'requestId': 'req-001'})
        resp = _invoke(event, table, make_sent_request(quote_revision=2))
        assert resp['statusCode'] == 409
        assert len(table.update_calls) == 0

    def test_accept_not_sent_status_409(self, patched_auth):
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-001/accept',
                           body={'expected_revision': 1},
                           path_params={'requestId': 'req-001'})
        resp = _invoke(event, table, make_sent_request(quote_status='ACCEPTED'))
        assert resp['statusCode'] == 409

    def test_accept_conditional_check_failed_maps_409(self, patched_auth):
        # Pure layer passes, but the atomic write loses the race -> 409.
        table = FakeTable(raise_conditional=True)
        event = make_event('POST', '/client/quotes/req-001/accept',
                           body={'expected_revision': 1},
                           path_params={'requestId': 'req-001'})
        resp = _invoke(event, table, make_sent_request())
        assert resp['statusCode'] == 409
        assert len(table.update_calls) == 1

    def test_accept_does_not_trust_caller_client_id(self, patched_auth):
        # Body carries a foreign client_id; the write key must use the resolved id.
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-001/accept',
                           body={'expected_revision': 1, 'client_id': 'attacker-999'},
                           path_params={'requestId': 'req-001'})
        resp = _invoke(event, table, make_sent_request())
        assert resp['statusCode'] == 200
        assert table.update_calls[0]['Key']['SK'] == 'CLIENT#client-001'


# ===========================================================================
# Decline
# ===========================================================================

class TestClientQuoteDecline:

    def test_decline_success(self, patched_auth):
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-001/decline',
                           body={'expected_revision': 1},
                           path_params={'requestId': 'req-001'})
        resp = _invoke(event, table, make_sent_request())
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['quote_status'] == 'DECLINED'
        assert body['quote_revision'] == 1
        vals = table.update_calls[0]['ExpressionAttributeValues']
        assert vals[':qs'] == 'DECLINED'
        assert vals[':sent'] == 'SENT'

    def test_decline_with_reason_trimmed(self, patched_auth):
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-001/decline',
                           body={'expected_revision': 1, 'decline_reason': '  too costly  '},
                           path_params={'requestId': 'req-001'})
        resp = _invoke(event, table, make_sent_request())
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['quote_declined_reason_client'] == 'too costly'

    def test_decline_blank_reason_absent(self, patched_auth):
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-001/decline',
                           body={'expected_revision': 1, 'decline_reason': '   '},
                           path_params={'requestId': 'req-001'})
        resp = _invoke(event, table, make_sent_request())
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert 'quote_declined_reason_client' not in body

    def test_decline_over_len_reason_400(self, patched_auth):
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-001/decline',
                           body={'expected_revision': 1, 'decline_reason': 'x' * 501},
                           path_params={'requestId': 'req-001'})
        resp = _invoke(event, table, make_sent_request())
        assert resp['statusCode'] == 400
        assert len(table.update_calls) == 0

    def test_decline_missing_expected_revision_400(self, patched_auth):
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-001/decline',
                           body={}, path_params={'requestId': 'req-001'})
        resp = _invoke(event, table, make_sent_request())
        assert resp['statusCode'] == 400

    def test_decline_stale_revision_409(self, patched_auth):
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-001/decline',
                           body={'expected_revision': 1},
                           path_params={'requestId': 'req-001'})
        resp = _invoke(event, table, make_sent_request(quote_revision=3))
        assert resp['statusCode'] == 409

    def test_decline_not_sent_409(self, patched_auth):
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-001/decline',
                           body={'expected_revision': 1},
                           path_params={'requestId': 'req-001'})
        resp = _invoke(event, table, make_sent_request(quote_status='DECLINED'))
        assert resp['statusCode'] == 409

    def test_decline_conditional_check_failed_maps_409(self, patched_auth):
        table = FakeTable(raise_conditional=True)
        event = make_event('POST', '/client/quotes/req-001/decline',
                           body={'expected_revision': 1},
                           path_params={'requestId': 'req-001'})
        resp = _invoke(event, table, make_sent_request())
        assert resp['statusCode'] == 409

    def test_decline_not_owned_404(self, patched_auth):
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-999/decline',
                           body={'expected_revision': 1},
                           path_params={'requestId': 'req-999'})
        resp = _invoke(event, table, None)
        assert resp['statusCode'] == 404


# ===========================================================================
# Concurrency / atomic-condition proof
# ===========================================================================

class TestAtomicConcurrency:

    def test_accept_write_conditions_on_revision_and_sent(self, patched_auth):
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-001/accept',
                           body={'expected_revision': 1},
                           path_params={'requestId': 'req-001'})
        _invoke(event, table, make_sent_request())
        call = table.update_calls[0]
        assert 'ConditionExpression' in call
        vals = call['ExpressionAttributeValues']
        # Both guard operands present: expected revision + SENT.
        assert vals[':exprev'] == 1
        assert vals[':sent'] == 'SENT'

    def test_decline_write_conditions_on_revision_and_sent(self, patched_auth):
        table = FakeTable()
        event = make_event('POST', '/client/quotes/req-001/decline',
                           body={'expected_revision': 1},
                           path_params={'requestId': 'req-001'})
        _invoke(event, table, make_sent_request())
        call = table.update_calls[0]
        assert 'ConditionExpression' in call
        vals = call['ExpressionAttributeValues']
        assert vals[':exprev'] == 1
        assert vals[':sent'] == 'SENT'


# ===========================================================================
# Write-scope invariants (OPS-3A.2A review): the persisted UpdateExpression
# must NOT touch quote_history, the request/booking status, APPROVED, or any
# payment field. Accept/Decline are quote-lifecycle-only writes.
# ===========================================================================

class TestWriteScopeInvariants:

    def _update(self, action, patched_auth, req=None):
        table = FakeTable()
        event = make_event('POST', f'/client/quotes/req-001/{action}',
                           body={'expected_revision': 1},
                           path_params={'requestId': 'req-001'})
        _invoke(event, table, req or make_sent_request())
        assert len(table.update_calls) == 1
        return table.update_calls[0]

    def test_accept_write_does_not_touch_quote_history(self, patched_auth):
        call = self._update('accept', patched_auth)
        assert 'quote_history' not in call['UpdateExpression']
        assert all('quote_history' not in str(v) for v in call['ExpressionAttributeValues'].values())

    def test_decline_write_does_not_touch_quote_history(self, patched_auth):
        call = self._update('decline', patched_auth)
        assert 'quote_history' not in call['UpdateExpression']

    def test_accept_write_does_not_touch_status_or_approved(self, patched_auth):
        call = self._update('accept', patched_auth)
        expr = call['UpdateExpression']
        # quote_status IS written (required); the request/booking `status` mirror is NOT.
        # Strip the quote_* fields, then assert the bare request `status` is absent.
        residual = expr.replace('quote_status', '').replace('quote_accepted_at', '')
        assert ' status ' not in residual and 'status =' not in residual
        # No RequestStatus mirror attribute name/value and no APPROVED anywhere.
        names = call.get('ExpressionAttributeNames', {})
        assert '#reqstatus' not in names
        assert 'status' not in [v for v in names.values()]
        vals = call['ExpressionAttributeValues']
        assert 'APPROVED' not in [str(v) for v in vals.values()]
        assert ':reqstatus' not in vals

    def test_accept_write_has_no_payment_fields(self, patched_auth):
        call = self._update('accept', patched_auth)
        expr = call['UpdateExpression']
        assert 'payment_status' not in expr
        assert 'payment_requirement' not in expr
        assert 'payment_amount_cents' not in expr

    def test_decline_write_has_no_payment_or_status_fields(self, patched_auth):
        call = self._update('decline', patched_auth)
        expr = call['UpdateExpression']
        assert 'payment_status' not in expr
        assert 'payment_requirement' not in expr
        # quote_status IS written; the request/booking `status` mirror is NOT.
        residual = expr.replace('quote_status', '').replace('quote_declined_at', '')
        assert ' status ' not in residual and 'status =' not in residual
        names = call.get('ExpressionAttributeNames', {})
        assert '#reqstatus' not in names
        vals = call['ExpressionAttributeValues']
        assert ':reqstatus' not in vals

    def test_accept_audit_entry_targets_audit_log_not_history(self, patched_auth):
        call = self._update('accept', patched_auth)
        # The append must target audit_log (the lifecycle-event list), never quote_history.
        assert 'audit_log = list_append' in call['UpdateExpression']
        assert 'quote_history' not in call['UpdateExpression']
