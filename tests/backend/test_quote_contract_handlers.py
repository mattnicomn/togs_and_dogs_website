"""
OPS-3A.1B — Handler integration tests for the quote endpoints wired into
admin_handler:

  - PATCH /admin/requests/{requestId}/quote   (owner/admin draft/update)
  - POST  /admin/requests/{requestId}/quote/send (owner/admin DRAFT->SENT)
  - GET   /client/quotes/{requestId}          (client-safe read projection)

These tests exercise the HTTP dispatch, authorization, the requestId-only lookup,
the derived RequestStatus mirror (DRAFT->QUOTE_NEEDED, SENT->QUOTE_SENT, never
APPROVED), the atomic send guard (409 on ConditionalCheckFailedException), and the
client-safe projection allowlist. The pure quote-contract math is covered separately
by tests/backend/test_quote_contract.py; here we assert the wiring and side effects.

No AWS, Terraform, deploy, or network dependency — the DynamoDB table is a local
fake and auth helpers are patched at their source module.
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


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _ConditionalCheckFailedException(Exception):
    """Stand-in matching botocore's ConditionalCheckFailedException shape."""


class FakeTable:
    """Minimal DynamoDB table double.

    - update_item records calls and may raise ConditionalCheckFailedException
      (controlled by ``raise_conditional``).
    - query returns ``query_items`` for the requestId-only fallback lookup.
    - exposes ``meta.client.exceptions.ConditionalCheckFailedException`` so the
      handler's except clause resolves to our exception type.
    """

    def __init__(self, query_items=None, raise_conditional=False):
        self.query_items = query_items if query_items is not None else []
        self.raise_conditional = raise_conditional
        self.update_calls = []
        self.query_calls = []

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

    def query(self, **kwargs):
        self.query_calls.append(kwargs)
        return {'Items': list(self.query_items)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_event(method, path, body=None, path_params=None, query_params=None,
               role='admin', email='admin@example.com', company_id='tog_and_dogs'):
    return {
        'httpMethod': method,
        'path': path,
        'pathParameters': path_params or {},
        'queryStringParameters': query_params or {},
        'body': json.dumps(body) if body is not None else None,
        'requestContext': {
            'authorizer': {
                'claims': {
                    'sub': 'sub-123',
                    'email': email,
                    'cognito:groups': [role],
                    'custom:company_id': company_id,
                }
            }
        },
    }


def make_request_record(**overrides):
    base = {
        'PK': 'REQ#req-001',
        'SK': 'CLIENT#client-001',
        'entity_type': 'REQUEST',
        'company_id': 'tog_and_dogs',
        'request_id': 'req-001',
        'client_id': 'client-001',
        'client_name': 'Jane Doe',
        'client_email': 'jane@example.com',
        'service_type': '20-Minute Walk',
        'pet_names': ['Rex'],
        'start_date': '2026-10-10',
        'end_date': '2026-10-10',
        'status': 'PENDING_REVIEW',
    }
    base.update(overrides)
    return base


@pytest.fixture
def patched_auth(monkeypatch):
    """Patch the auth/entitlement helpers so handler logic is deterministic.

    Returns a dict of the mocks so individual tests can tweak behavior (e.g.
    make role a non-admin, or make tenant ownership raise).
    """
    role_mock = MagicMock(return_value='admin')
    claims_mock = MagicMock(return_value={'email': 'admin@example.com', 'username': 'admin'})
    vto_mock = MagicMock(return_value=None)  # no PermissionError by default
    resolve_mock = MagicMock(return_value='client-001')
    company_mock = MagicMock(return_value='tog_and_dogs')
    active_mock = MagicMock(return_value=None)  # active tenant -> no block response

    # Module-global names in admin_handler (imported at top of module).
    monkeypatch.setattr(ah, 'get_effective_role', role_mock)
    monkeypatch.setattr(ah, 'get_claims', claims_mock)

    # Locally-imported names resolve at call time from their source modules.
    import common.auth as common_auth
    import common.entitlement as common_entitlement
    monkeypatch.setattr(common_auth, 'validate_tenant_ownership', vto_mock)
    monkeypatch.setattr(common_auth, 'resolve_client_identity', resolve_mock)
    monkeypatch.setattr(common_auth, 'get_current_company_id', company_mock)
    monkeypatch.setattr(common_entitlement, 'require_active_tenant', active_mock)

    return {
        'role': role_mock,
        'claims': claims_mock,
        'vto': vto_mock,
        'resolve': resolve_mock,
        'company': company_mock,
        'active': active_mock,
    }


# ===========================================================================
# PATCH /admin/requests/{requestId}/quote  (draft / update)
# ===========================================================================

class TestAdminQuoteUpdate:

    def _invoke(self, event, table):
        orig = ah.table
        try:
            ah.table = table
            return admin_handler(event, None)
        finally:
            ah.table = orig

    def test_first_draft_sets_draft_and_derives_quote_needed(self, patched_auth, monkeypatch):
        """A first draft sets quote_status=DRAFT and mirrors status=QUOTE_NEEDED."""
        req = make_request_record()  # no quote_status yet
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=req))

        event = make_event(
            'PATCH', '/admin/requests/req-001/quote',
            body={'quote_amount_cents': 5000, 'quote_notes_client': 'Standard walk'},
            path_params={'requestId': 'req-001'},
            query_params={'clientId': 'client-001'},
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['quote_status'] == 'DRAFT'
        assert body['quote_amount_cents'] == 5000
        assert body['status'] == 'QUOTE_NEEDED'

        # Persisted update mirrored status and NEVER wrote APPROVED.
        assert len(table.update_calls) == 1
        call = table.update_calls[0]
        assert call['Key'] == {'PK': 'REQ#req-001', 'SK': 'CLIENT#client-001'}
        names = call.get('ExpressionAttributeNames', {})
        values = call.get('ExpressionAttributeValues', {})
        assert 'status' in names.values()
        assert values.get(':reqstatus') == 'QUOTE_NEEDED'
        assert 'APPROVED' not in values.values()
        assert 'BOOKING_CONFIRMED' not in values.values()

    def test_requestid_only_lookup_resolves_client(self, patched_auth, monkeypatch):
        """No client_id in body: handler resolves it via the query fallback."""
        req = make_request_record()
        table = FakeTable(query_items=[req])
        # get_item returns None so the query fallback is exercised.
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=None))

        event = make_event(
            'PATCH', '/admin/requests/req-001/quote',
            body={'quote_amount_cents': 7500},
            path_params={'requestId': 'req-001'},
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 200
        assert len(table.query_calls) == 1
        # client_id resolved from the queried record for the write key.
        assert table.update_calls[0]['Key']['SK'] == 'CLIENT#client-001'

    def test_non_admin_forbidden(self, patched_auth, monkeypatch):
        patched_auth['role'].return_value = 'staff'
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=make_request_record()))
        event = make_event(
            'PATCH', '/admin/requests/req-001/quote',
            body={'quote_amount_cents': 5000}, path_params={'requestId': 'req-001'},
            query_params={'clientId': 'client-001'}, role='staff',
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 403

    def test_client_role_forbidden(self, patched_auth, monkeypatch):
        patched_auth['role'].return_value = 'client'
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=make_request_record()))
        event = make_event(
            'PATCH', '/admin/requests/req-001/quote',
            body={'quote_amount_cents': 5000}, path_params={'requestId': 'req-001'},
            query_params={'clientId': 'client-001'}, role='client',
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 403

    def test_tenant_mismatch_forbidden(self, patched_auth, monkeypatch):
        patched_auth['vto'].side_effect = PermissionError("cross tenant")
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=make_request_record(company_id='other')))
        event = make_event(
            'PATCH', '/admin/requests/req-001/quote',
            body={'quote_amount_cents': 5000}, path_params={'requestId': 'req-001'},
            query_params={'clientId': 'client-001'},
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 403
        assert len(table.update_calls) == 0

    def test_not_found(self, patched_auth, monkeypatch):
        table = FakeTable(query_items=[])
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=None))
        event = make_event(
            'PATCH', '/admin/requests/missing/quote',
            body={'quote_amount_cents': 5000}, path_params={'requestId': 'missing'},
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 404

    def test_empty_update_rejected(self, patched_auth, monkeypatch):
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=make_request_record()))
        event = make_event(
            'PATCH', '/admin/requests/req-001/quote',
            body={}, path_params={'requestId': 'req-001'},
            query_params={'clientId': 'client-001'},
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 400

    def test_invalid_payment_requirement_rejected(self, patched_auth, monkeypatch):
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=make_request_record()))
        event = make_event(
            'PATCH', '/admin/requests/req-001/quote',
            body={'quote_amount_cents': 5000, 'payment_requirement': 'BOGUS'},
            path_params={'requestId': 'req-001'},
            query_params={'clientId': 'client-001'},
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 400
        assert len(table.update_calls) == 0

    def test_commercial_change_on_sent_bumps_revision_and_returns_draft(self, patched_auth, monkeypatch):
        """Editing the amount of a SENT quote creates a new DRAFT revision (re-send)."""
        req = make_request_record(
            quote_status='SENT', quote_amount_cents=5000, quote_revision=1,
            currency='USD', status='QUOTE_SENT', quote_sent_at='2026-10-05T00:00:00Z',
        )
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=req))
        event = make_event(
            'PATCH', '/admin/requests/req-001/quote',
            body={'quote_amount_cents': 9000}, path_params={'requestId': 'req-001'},
            query_params={'clientId': 'client-001'},
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['quote_status'] == 'DRAFT'
        assert body['quote_revision'] == 2
        assert body['status'] == 'QUOTE_NEEDED'
        values = table.update_calls[0]['ExpressionAttributeValues']
        assert 'APPROVED' not in values.values()

    def test_internal_note_only_does_not_revise_or_mirror(self, patched_auth, monkeypatch):
        """Internal-only note on a SENT quote neither bumps revision nor flips status."""
        req = make_request_record(
            quote_status='SENT', quote_amount_cents=5000, quote_revision=1, status='QUOTE_SENT',
        )
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=req))
        event = make_event(
            'PATCH', '/admin/requests/req-001/quote',
            body={'quote_notes_internal': 'call client first'},
            path_params={'requestId': 'req-001'},
            query_params={'clientId': 'client-001'},
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        # quote_status stays SENT; no derived status mirror written.
        assert body['quote_status'] == 'SENT'
        values = table.update_calls[0]['ExpressionAttributeValues']
        assert ':reqstatus' not in values  # no derived status write for internal-only
        assert 'APPROVED' not in values.values()


# ===========================================================================
# POST /admin/requests/{requestId}/quote/send
# ===========================================================================

class TestAdminQuoteSend:

    def _invoke(self, event, table):
        orig = ah.table
        try:
            ah.table = table
            return admin_handler(event, None)
        finally:
            ah.table = orig

    def test_draft_to_sent_mirrors_quote_sent(self, patched_auth, monkeypatch):
        req = make_request_record(
            quote_status='DRAFT', quote_amount_cents=5000, quote_revision=1, status='QUOTE_NEEDED',
        )
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=req))
        event = make_event(
            'POST', '/admin/requests/req-001/quote/send',
            body={}, path_params={'requestId': 'req-001'},
            query_params={'clientId': 'client-001'},
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['quote_status'] == 'SENT'
        assert body['status'] == 'QUOTE_SENT'
        call = table.update_calls[0]
        values = call['ExpressionAttributeValues']
        assert values[':qs'] == 'SENT'
        assert values[':reqstatus'] == 'QUOTE_SENT'
        assert 'APPROVED' not in values.values()
        # Atomic guard present on quote_revision + quote_status.
        assert 'ConditionExpression' in call

    def test_send_is_idempotent_for_already_sent(self, patched_auth, monkeypatch):
        req = make_request_record(
            quote_status='SENT', quote_amount_cents=5000, quote_revision=2, status='QUOTE_SENT',
        )
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=req))
        event = make_event(
            'POST', '/admin/requests/req-001/quote/send',
            body={}, path_params={'requestId': 'req-001'},
            query_params={'clientId': 'client-001'},
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['quote_status'] == 'SENT'
        assert body['quote_revision'] == 2

    def test_send_zero_amount_rejected(self, patched_auth, monkeypatch):
        req = make_request_record(quote_status='DRAFT', quote_amount_cents=0, quote_revision=1)
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=req))
        event = make_event(
            'POST', '/admin/requests/req-001/quote/send',
            body={}, path_params={'requestId': 'req-001'},
            query_params={'clientId': 'client-001'},
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 400
        assert len(table.update_calls) == 0

    def test_send_conditional_check_failure_maps_to_409(self, patched_auth, monkeypatch):
        req = make_request_record(quote_status='DRAFT', quote_amount_cents=5000, quote_revision=1)
        table = FakeTable(raise_conditional=True)
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=req))
        event = make_event(
            'POST', '/admin/requests/req-001/quote/send',
            body={}, path_params={'requestId': 'req-001'},
            query_params={'clientId': 'client-001'},
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 409

    def test_send_non_admin_forbidden(self, patched_auth, monkeypatch):
        patched_auth['role'].return_value = 'client'
        req = make_request_record(quote_status='DRAFT', quote_amount_cents=5000)
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=req))
        event = make_event(
            'POST', '/admin/requests/req-001/quote/send',
            body={}, path_params={'requestId': 'req-001'},
            query_params={'clientId': 'client-001'}, role='client',
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 403

    def test_send_tenant_mismatch_forbidden(self, patched_auth, monkeypatch):
        patched_auth['vto'].side_effect = PermissionError("cross tenant")
        req = make_request_record(quote_status='DRAFT', quote_amount_cents=5000, company_id='other')
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=req))
        event = make_event(
            'POST', '/admin/requests/req-001/quote/send',
            body={}, path_params={'requestId': 'req-001'},
            query_params={'clientId': 'client-001'},
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 403
        assert len(table.update_calls) == 0


# ===========================================================================
# GET /client/quotes/{requestId}
# ===========================================================================

class TestClientQuoteRead:

    def _invoke(self, event, table):
        orig = ah.table
        try:
            ah.table = table
            return admin_handler(event, None)
        finally:
            ah.table = orig

    def test_client_reads_own_canonical_quote(self, patched_auth, monkeypatch):
        patched_auth['role'].return_value = 'client'
        patched_auth['resolve'].return_value = 'client-001'
        req = make_request_record(
            quote_status='SENT', quote_amount_cents=5000, quote_revision=1,
            currency='USD', payment_requirement='FULL', payment_status='UNPAID',
            quote_notes_client='Standard walk', quote_notes_internal='SECRET internal',
            internal_pricing_notes='cost basis', stripe_payment_url='https://x',
            audit_log=[{'a': 1}],
        )
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=req))
        event = make_event(
            'GET', '/client/quotes/req-001', path_params={'requestId': 'req-001'}, role='client',
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        # Allowlisted fields present.
        assert body['quote_status'] == 'SENT'
        assert body['quote_amount_cents'] == 5000
        assert body['quote_notes_client'] == 'Standard walk'
        assert body['payment_required'] is True
        # Forbidden/internal fields absent.
        assert 'quote_notes_internal' not in body
        assert 'internal_pricing_notes' not in body
        assert 'quote_history' not in body
        assert 'audit_log' not in body
        assert 'stripe_payment_url' not in body
        assert 'company_id' not in body

    def test_client_other_client_request_is_404(self, patched_auth, monkeypatch):
        """A client resolving to client-002 cannot read client-001's quote."""
        patched_auth['role'].return_value = 'client'
        patched_auth['resolve'].return_value = 'client-002'
        table = FakeTable()
        # get_item is keyed by resolved client_id -> different SK -> miss (None).
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=None))
        event = make_event(
            'GET', '/client/quotes/req-001', path_params={'requestId': 'req-001'},
            role='client', email='other@example.com',
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 404

    def test_client_tenant_mismatch_is_404_non_disclosing(self, patched_auth, monkeypatch):
        patched_auth['role'].return_value = 'client'
        patched_auth['resolve'].return_value = 'client-001'
        patched_auth['vto'].side_effect = PermissionError("cross tenant")
        req = make_request_record(company_id='other', quote_status='SENT', quote_amount_cents=5000)
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=req))
        event = make_event(
            'GET', '/client/quotes/req-001', path_params={'requestId': 'req-001'}, role='client',
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 404

    def test_non_client_role_forbidden(self, patched_auth, monkeypatch):
        patched_auth['role'].return_value = 'admin'
        patched_auth['resolve'].return_value = 'client-001'
        req = make_request_record(quote_status='SENT', quote_amount_cents=5000)
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=req))
        event = make_event(
            'GET', '/client/quotes/req-001', path_params={'requestId': 'req-001'}, role='admin',
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 403

    def test_canonical_wins_over_legacy_pet(self, patched_auth, monkeypatch):
        """When quote_status exists, legacy PET pricing is ignored."""
        patched_auth['role'].return_value = 'client'
        patched_auth['resolve'].return_value = 'client-001'
        req = make_request_record(
            quote_status='SENT', quote_amount_cents=5000, quote_revision=1, pet_id='pet-9',
        )
        legacy_pet = {'PK': 'PET#pet-9', 'SK': 'CLIENT#client-001', 'quote_amount': '999.00'}
        get_item_mock = MagicMock(side_effect=[req, legacy_pet])
        monkeypatch.setattr(ah, 'get_item', get_item_mock)
        table = FakeTable()
        event = make_event(
            'GET', '/client/quotes/req-001', path_params={'requestId': 'req-001'}, role='client',
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        # Canonical cents win; legacy 999.00 is NOT used.
        assert body['quote_amount_cents'] == 5000
        # Legacy PET was NOT loaded because canonical quote_status is present.
        assert get_item_mock.call_count == 1

    def test_legacy_fallback_dual_read(self, patched_auth, monkeypatch):
        """No canonical quote_status: legacy PET pricing is converted at read time."""
        patched_auth['role'].return_value = 'client'
        patched_auth['resolve'].return_value = 'client-001'
        req = make_request_record(pet_id='pet-9', status='QUOTE_SENT')  # no quote_status
        req.pop('status', None)
        req['status'] = 'QUOTE_SENT'
        legacy_pet = {'PK': 'PET#pet-9', 'SK': 'CLIENT#client-001',
                      'quote_amount': '42.50', 'payment_status': 'Quote Sent'}
        get_item_mock = MagicMock(side_effect=[req, legacy_pet])
        monkeypatch.setattr(ah, 'get_item', get_item_mock)
        table = FakeTable()
        event = make_event(
            'GET', '/client/quotes/req-001', path_params={'requestId': 'req-001'}, role='client',
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['quote_amount_cents'] == 4250  # 42.50 -> cents
        # Legacy PET WAS loaded (second get_item call).
        assert get_item_mock.call_count == 2

    def test_not_required_quote_projection(self, patched_auth, monkeypatch):
        patched_auth['role'].return_value = 'client'
        patched_auth['resolve'].return_value = 'client-001'
        req = make_request_record(
            quote_status='NOT_REQUIRED', quote_amount_cents=0, quote_revision=1,
            payment_requirement='NONE',
        )
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=req))
        event = make_event(
            'GET', '/client/quotes/req-001', path_params={'requestId': 'req-001'}, role='client',
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['quote_status'] == 'NOT_REQUIRED'
        assert body['payment_required'] is False


# ===========================================================================
# OPS-3A.3A.1 — Client-read DRAFT/SUPERSEDED visibility guard
# ===========================================================================

class TestClientQuoteReadVisibilityGuard:
    """A quote is client-readable only once delivered. DRAFT and SUPERSEDED must
    return the non-disclosing 404; NOT_REQUIRED/SENT/ACCEPTED/DECLINED return 200.

    The accept/decline SENT-only state gating is unaffected by this read guard;
    the final two tests assert that non-regression at the handler layer.
    """

    def _invoke(self, event, table):
        orig = ah.table
        try:
            ah.table = table
            return admin_handler(event, None)
        finally:
            ah.table = orig

    def _read(self, patched_auth, monkeypatch, req):
        patched_auth['role'].return_value = 'client'
        patched_auth['resolve'].return_value = 'client-001'
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=req))
        event = make_event(
            'GET', '/client/quotes/req-001', path_params={'requestId': 'req-001'}, role='client',
        )
        return self._invoke(event, table)

    # --- DRAFT / SUPERSEDED are NOT client-readable (non-disclosing 404) ---

    def test_draft_quote_is_404_non_disclosing(self, patched_auth, monkeypatch):
        req = make_request_record(
            quote_status='DRAFT', quote_amount_cents=5000, quote_revision=1,
            quote_notes_client='work in progress',
        )
        resp = self._read(patched_auth, monkeypatch, req)
        assert resp['statusCode'] == 404
        body = json.loads(resp['body'])
        # Non-disclosing: no pricing/notes leak in the 404 body.
        assert 'quote_amount_cents' not in body
        assert 'quote_notes_client' not in body

    def test_superseded_quote_is_404_non_disclosing(self, patched_auth, monkeypatch):
        # SUPERSEDED should never be a current status, but the guard is defensive.
        req = make_request_record(
            quote_status='SUPERSEDED', quote_amount_cents=5000, quote_revision=2,
            quote_notes_client='old revision',
        )
        resp = self._read(patched_auth, monkeypatch, req)
        assert resp['statusCode'] == 404
        body = json.loads(resp['body'])
        assert 'quote_amount_cents' not in body
        assert 'quote_notes_client' not in body

    # --- Delivered / terminal / not-required statuses remain readable (200) ---

    def test_sent_quote_is_200(self, patched_auth, monkeypatch):
        req = make_request_record(
            quote_status='SENT', quote_amount_cents=5000, quote_revision=1,
            payment_requirement='FULL', payment_status='UNPAID',
            quote_notes_client='Standard walk',
        )
        resp = self._read(patched_auth, monkeypatch, req)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['quote_status'] == 'SENT'
        assert body['quote_amount_cents'] == 5000

    def test_accepted_quote_is_200(self, patched_auth, monkeypatch):
        req = make_request_record(
            quote_status='ACCEPTED', quote_amount_cents=5000, quote_revision=1,
            quote_accepted_revision=1, quote_accepted_at='2026-10-05T00:00:00Z',
            payment_requirement='FULL', payment_status='UNPAID',
        )
        resp = self._read(patched_auth, monkeypatch, req)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['quote_status'] == 'ACCEPTED'

    def test_declined_quote_is_200(self, patched_auth, monkeypatch):
        req = make_request_record(
            quote_status='DECLINED', quote_amount_cents=5000, quote_revision=1,
            payment_requirement='FULL', payment_status='UNPAID',
        )
        resp = self._read(patched_auth, monkeypatch, req)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['quote_status'] == 'DECLINED'

    def test_not_required_quote_is_200(self, patched_auth, monkeypatch):
        req = make_request_record(
            quote_status='NOT_REQUIRED', quote_amount_cents=0, quote_revision=1,
            payment_requirement='NONE',
        )
        resp = self._read(patched_auth, monkeypatch, req)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['quote_status'] == 'NOT_REQUIRED'

    # --- Non-owning client stays non-disclosing regardless of the status guard ---

    def test_non_owning_client_still_404(self, patched_auth, monkeypatch):
        patched_auth['role'].return_value = 'client'
        patched_auth['resolve'].return_value = 'client-002'
        table = FakeTable()
        # Resolved client_id keys a different SK -> ownership miss (None) before the
        # status guard is ever reached.
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=None))
        event = make_event(
            'GET', '/client/quotes/req-001', path_params={'requestId': 'req-001'},
            role='client', email='other@example.com',
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 404

    # --- Accept/Decline SENT-only gating is NOT affected by the read guard ---

    def test_accept_on_draft_still_409_not_404(self, patched_auth, monkeypatch):
        """The read guard does not change mutation gating: accept on a non-SENT
        quote is still a 409 lifecycle conflict (not the read 404)."""
        patched_auth['role'].return_value = 'client'
        patched_auth['resolve'].return_value = 'client-001'
        req = make_request_record(quote_status='DRAFT', quote_amount_cents=5000, quote_revision=1)
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=req))
        event = make_event(
            'POST', '/client/quotes/req-001/accept',
            body={'expected_revision': 1}, path_params={'requestId': 'req-001'},
            role='client',
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 409

    def test_decline_on_draft_still_409_not_404(self, patched_auth, monkeypatch):
        patched_auth['role'].return_value = 'client'
        patched_auth['resolve'].return_value = 'client-001'
        req = make_request_record(quote_status='DRAFT', quote_amount_cents=5000, quote_revision=1)
        table = FakeTable()
        monkeypatch.setattr(ah, 'get_item', MagicMock(return_value=req))
        event = make_event(
            'POST', '/client/quotes/req-001/decline',
            body={'expected_revision': 1}, path_params={'requestId': 'req-001'},
            role='client',
        )
        resp = self._invoke(event, table)
        assert resp['statusCode'] == 409


# ===========================================================================
# OPS-3A.3A.2 — Legacy dual-read derived status client visibility
# ===========================================================================

class TestLegacyQuoteReadVisibilityGuard:
    """The client-read visibility gate applies to the EFFECTIVE resolved status,
    so legacy dual-read records (no canonical quote_status) are gated by their
    derived status: derived DRAFT is hidden (404); derived SENT/ACCEPTED/
    NOT_REQUIRED remain client-readable (200).

    Legacy derivation rules (resolve_quote_from_record):
      amount==0 -> NOT_REQUIRED; legacy-accepted payment -> ACCEPTED;
      request status in {QUOTE_NEEDED,QUOTE_SENT,QUOTED} or any payment_status
      -> SENT; otherwise -> DRAFT. The legacy branch never derives SUPERSEDED.
    """

    def _invoke(self, event, table):
        orig = ah.table
        try:
            ah.table = table
            return admin_handler(event, None)
        finally:
            ah.table = orig

    def _read_legacy(self, patched_auth, monkeypatch, req, legacy_pet):
        patched_auth['role'].return_value = 'client'
        patched_auth['resolve'].return_value = 'client-001'
        get_item_mock = MagicMock(side_effect=[req, legacy_pet])
        monkeypatch.setattr(ah, 'get_item', get_item_mock)
        table = FakeTable()
        event = make_event(
            'GET', '/client/quotes/req-001', path_params={'requestId': 'req-001'}, role='client',
        )
        return self._invoke(event, table)

    def test_legacy_derived_draft_is_404_non_disclosing(self, patched_auth, monkeypatch):
        """Primary blocker regression: a legacy record that derives DRAFT (positive
        amount, not accepted, no payment_status, non-quote-summary request status)
        must be hidden with a non-disclosing 404 — no pricing leak."""
        req = make_request_record(pet_id='pet-9', status='PENDING_REVIEW')
        req.pop('quote_status', None)
        legacy_pet = {'PK': 'PET#pet-9', 'SK': 'CLIENT#client-001', 'quote_amount': '75.00'}
        resp = self._read_legacy(patched_auth, monkeypatch, req, legacy_pet)
        assert resp['statusCode'] == 404
        body = json.loads(resp['body'])
        assert 'quote_amount_cents' not in body
        assert 'quote_status' not in body

    def test_legacy_derived_sent_is_200(self, patched_auth, monkeypatch):
        """A legacy record whose request status is QUOTE_SENT derives SENT -> visible."""
        req = make_request_record(pet_id='pet-9')
        req.pop('quote_status', None)
        req['status'] = 'QUOTE_SENT'
        legacy_pet = {'PK': 'PET#pet-9', 'SK': 'CLIENT#client-001',
                      'quote_amount': '42.50', 'payment_status': 'Quote Sent'}
        resp = self._read_legacy(patched_auth, monkeypatch, req, legacy_pet)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['quote_status'] == 'SENT'
        assert body['quote_amount_cents'] == 4250

    def test_legacy_derived_accepted_is_200(self, patched_auth, monkeypatch):
        """A legacy PET payment_status of 'Paid in Full' derives ACCEPTED -> visible."""
        req = make_request_record(pet_id='pet-9', status='QUOTE_SENT')
        req.pop('quote_status', None)
        legacy_pet = {'PK': 'PET#pet-9', 'SK': 'CLIENT#client-001',
                      'quote_amount': '60.00', 'payment_status': 'Paid in Full'}
        resp = self._read_legacy(patched_auth, monkeypatch, req, legacy_pet)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['quote_status'] == 'ACCEPTED'

    def test_legacy_derived_not_required_is_200(self, patched_auth, monkeypatch):
        """A legacy record with no/zero amount derives NOT_REQUIRED -> visible."""
        req = make_request_record(pet_id='pet-9', status='PENDING_REVIEW')
        req.pop('quote_status', None)
        legacy_pet = {'PK': 'PET#pet-9', 'SK': 'CLIENT#client-001', 'quote_amount': '0'}
        resp = self._read_legacy(patched_auth, monkeypatch, req, legacy_pet)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['quote_status'] == 'NOT_REQUIRED'
