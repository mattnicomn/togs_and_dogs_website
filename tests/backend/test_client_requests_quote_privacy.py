"""Privacy regression tests for GET /client/requests (client booking list).

Proves that the client booking-LIST response is built from an explicit client-safe
allowlist (common.auth.project_client_request_list_item) and therefore never exposes
canonical quote commercial/internal fields that the quote lifecycle writes onto the
REQUEST record — regardless of the quote's status, including DRAFT.

Context: the approved quote contract keeps pricing OUT of the general booking list;
the dedicated GET /client/quotes/{requestId} projection is the authoritative client
commercial view (and additionally hides DRAFT). Before this remediation the list
passed raw REQUEST records through a denylist sanitizer, so quote fields could leak.

This is a LOCAL source-level regression suite. No AWS/Terraform/network: the table is
a local fake and auth helpers are patched at their source modules. No production
record is read. These tests do NOT change the dedicated quote endpoint or its DRAFT
404 behavior.
"""
import sys
import os
import json
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))
os.environ.setdefault('DATA_TABLE_NAME', 'test-table')

import handlers.admin_handler as ah
from handlers.admin_handler import handler as admin_handler
import common.auth as common_auth
import common.entitlement as common_entitlement
import common.tenant_read_scope as common_trs
from boto3.dynamodb.conditions import Attr
from common.auth import (
    project_client_request_list_item,
    CLIENT_REQUEST_LIST_ALLOWLIST,
)

# A real boto3 condition the handler can combine with & (the FakeTable.scan
# ignores the FilterExpression, but the handler still builds it).
_DUMMY_FILTER = Attr('company_id').eq('tog_and_dogs')


# Every commercial/internal quote field the canonical lifecycle can write onto a
# REQUEST record. None of these may ever appear in the client booking-list response.
FORBIDDEN_LIST_FIELDS = (
    "quote_amount_cents",
    "currency",
    "deposit_amount_cents",
    "payment_requirement",
    "payment_status",
    "quote_notes_client",
    "quote_notes_internal",
    "internal_pricing_notes",
    "quote_history",
    "quote_revision",
    "quote_sent_at",
    "quote_accepted_at",
    "quote_accepted_revision",
    "quote_declined_at",
    "quote_declined_revision",
    "quote_declined_reason_client",
    "audit_log",
    # quote_status is intentionally NOT exposed at the list level (future design).
    "quote_status",
)


class FakeTable:
    """Minimal DynamoDB table stand-in with a seedable scan()."""

    def __init__(self, items):
        self._items = items

    def scan(self, **kwargs):
        return {"Items": list(self._items)}


def _full_quote_request(status='SENT', **overrides):
    """A REQUEST carrying the full canonical quote field-set PLUS legitimate
    client-list fields. The quote fields must all be stripped from the list."""
    rec = {
        # Keys / identity.
        'PK': 'REQ#req-xyz',
        'SK': 'CLIENT#client-xyz',
        'entity_type': 'REQUEST',
        'company_id': 'tog_and_dogs',
        'request_id': 'req-xyz',
        'client_id': 'client-xyz',
        # Legitimate client-list display fields (must be preserved).
        'client_name': 'Jane Doe',
        'pet_name': 'Buddy',
        'pet_names': ['Buddy'],
        'service_type': '20-Minute Walk',
        'status': 'QUOTE_SENT',
        'selected_dates': ['2026-11-01'],
        'start_date': '2026-11-01',
        'end_date': '2026-11-01',
        'is_multi_day': False,
        'total_occurrences': 1,
        'completed_count': 0,
        'visit_windows': ['MORNING'],
        'worker_name': 'Ryan',
        'created_at': '2026-10-20T10:00:00Z',
        # Canonical quote commercial + internal fields (must all be stripped).
        'quote_status': status,
        'quote_revision': 2,
        'quote_amount_cents': 5000,
        'currency': 'USD',
        'deposit_amount_cents': 1000,
        'payment_requirement': 'DEPOSIT',
        'payment_status': 'UNPAID',
        'quote_notes_client': 'Thanks for booking!',
        'quote_notes_internal': 'margin 40%',
        'internal_pricing_notes': 'do not disclose',
        'quote_history': [{'quote_status': 'SUPERSEDED', 'quote_amount_cents': 4000}],
        'quote_sent_at': '2026-10-20T11:00:00Z',
        'quote_accepted_at': None,
        'quote_accepted_revision': None,
        'quote_declined_at': None,
        # Internal/admin/staff fields historically redacted by the denylist.
        'admin_notes': 'internal',
        'audit_log': [{'action': 'QUOTE_SENT'}],
        'worker_id': 'worker-1',
        'job_id': 'job-1',
        'is_test_booking': True,
    }
    rec.update(overrides)
    return rec


def _legacy_request():
    """A legacy/never-quoted REQUEST (no canonical quote fields at all)."""
    return {
        'PK': 'REQ#req-legacy',
        'SK': 'CLIENT#client-xyz',
        'entity_type': 'REQUEST',
        'company_id': 'tog_and_dogs',
        'request_id': 'req-legacy',
        'client_id': 'client-xyz',
        'pet_name': 'Rex',
        'service_type': 'OVERNIGHT',
        'status': 'PENDING_REVIEW',
        'selected_dates': ['2026-12-01'],
        'start_date': '2026-12-01',
        'created_at': '2026-10-18T09:00:00Z',
    }


def _client_event():
    return {
        'httpMethod': 'GET',
        'path': '/client/requests',
        'pathParameters': {},
        'queryStringParameters': {},
        'body': None,
        'requestContext': {
            'authorizer': {
                'claims': {
                    'sub': 'sub-client-1',
                    'email': 'jane@example.com',
                    'email_verified': True,
                    'cognito:groups': ['client'],
                    'custom:company_id': 'tog_and_dogs',
                }
            }
        },
    }


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(ah, 'get_effective_role', MagicMock(return_value='client'))
    monkeypatch.setattr(ah, 'get_claims',
                        MagicMock(return_value={'email': 'jane@example.com', 'sub': 'sub-client-1'}))
    monkeypatch.setattr(common_auth, 'resolve_client_identity', MagicMock(return_value='client-xyz'))
    monkeypatch.setattr(common_auth, 'get_current_company_id', MagicMock(return_value='tog_and_dogs'))
    monkeypatch.setattr(common_entitlement, 'require_active_tenant', MagicMock(return_value=None))
    # Tenant read filter -> a real boto3 condition the FakeTable ignores but the
    # handler can still combine with & when building the scan FilterExpression.
    monkeypatch.setattr(common_trs, 'build_tenant_read_filter', MagicMock(return_value=_DUMMY_FILTER))
    monkeypatch.setattr(ah, 'build_tenant_read_filter', MagicMock(return_value=_DUMMY_FILTER))


def _invoke_list(table):
    orig = ah.table
    try:
        ah.table = table
        import common.db as common_db
        orig_db = common_db.table
        common_db.table = table
        try:
            resp = admin_handler(_client_event(), None)
        finally:
            common_db.table = orig_db
        return resp
    finally:
        ah.table = orig


def _list_items(resp):
    assert resp['statusCode'] == 200, resp
    return json.loads(resp['body'])['requests']


# ---------------------------------------------------------------------------
# Pure projection helper (no handler/table involved).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('status', ['DRAFT', 'SENT', 'ACCEPTED', 'DECLINED', 'NOT_REQUIRED'])
def test_projection_strips_all_forbidden_fields_for_every_status(status):
    projected = project_client_request_list_item(_full_quote_request(status=status))
    for field in FORBIDDEN_LIST_FIELDS:
        assert field not in projected, f"{field} leaked for quote_status={status}"


def test_projection_preserves_legitimate_client_list_fields():
    projected = project_client_request_list_item(_full_quote_request())
    for field in ('request_id', 'status', 'service_type', 'pet_name', 'pet_names',
                  'selected_dates', 'start_date', 'end_date', 'worker_name',
                  'created_at', 'client_name', 'visit_windows'):
        assert projected.get(field) == _full_quote_request()[field], field


def test_projection_never_reuses_raw_record_object():
    raw = _full_quote_request()
    projected = project_client_request_list_item(raw)
    assert projected is not raw
    # Only allowlisted keys may be present.
    assert set(projected).issubset(set(CLIENT_REQUEST_LIST_ALLOWLIST))


def test_projection_legacy_request_renders_without_quote_fields():
    projected = project_client_request_list_item(_legacy_request())
    assert projected['request_id'] == 'req-legacy'
    assert projected['status'] == 'PENDING_REVIEW'
    for field in FORBIDDEN_LIST_FIELDS:
        assert field not in projected


# ---------------------------------------------------------------------------
# End-to-end through the /client/requests handler.
# ---------------------------------------------------------------------------

def test_handler_list_excludes_quote_fields_for_sent(patched):
    resp = _invoke_list(FakeTable([_full_quote_request(status='SENT')]))
    items = _list_items(resp)
    assert len(items) == 1
    for field in FORBIDDEN_LIST_FIELDS:
        assert field not in items[0], field


@pytest.mark.parametrize('status', ['SENT', 'ACCEPTED', 'DECLINED'])
def test_handler_list_does_not_widen_commercial_exposure(patched, status):
    resp = _invoke_list(FakeTable([_full_quote_request(status=status)]))
    items = _list_items(resp)
    for field in ('quote_amount_cents', 'deposit_amount_cents', 'payment_requirement',
                  'quote_notes_client', 'quote_notes_internal', 'quote_history'):
        assert field not in items[0], f"{field} leaked at {status}"


def test_handler_list_draft_privacy_invariant(patched):
    """A DRAFT REQUEST carrying price/notes/deposit/history must expose NONE of them
    through the list — parity with the dedicated endpoint's DRAFT privacy boundary."""
    resp = _invoke_list(FakeTable([_full_quote_request(status='DRAFT')]))
    items = _list_items(resp)
    assert len(items) == 1
    for field in FORBIDDEN_LIST_FIELDS:
        assert field not in items[0], f"{field} leaked for DRAFT"
    # The list still renders the booking's non-commercial workflow fields.
    assert items[0]['request_id'] == 'req-xyz'
    assert items[0]['status'] == 'QUOTE_SENT'


def test_handler_list_quote_status_not_incidentally_exposed(patched):
    resp = _invoke_list(FakeTable([_full_quote_request(status='SENT')]))
    items = _list_items(resp)
    assert 'quote_status' not in items[0]


def test_handler_list_excludes_internal_admin_fields(patched):
    resp = _invoke_list(FakeTable([_full_quote_request()]))
    items = _list_items(resp)
    for field in ('admin_notes', 'audit_log', 'worker_id', 'job_id', 'is_test_booking'):
        assert field not in items[0], field


def test_handler_list_preserves_legitimate_fields(patched):
    resp = _invoke_list(FakeTable([_full_quote_request()]))
    items = _list_items(resp)
    assert items[0]['request_id'] == 'req-xyz'
    assert items[0]['service_type'] == '20-Minute Walk'
    assert items[0]['pet_name'] == 'Buddy'
    assert items[0]['status'] == 'QUOTE_SENT'
    assert items[0]['selected_dates'] == ['2026-11-01']
    assert items[0]['worker_name'] == 'Ryan'


def test_handler_list_legacy_request_renders(patched):
    resp = _invoke_list(FakeTable([_legacy_request()]))
    items = _list_items(resp)
    assert items[0]['request_id'] == 'req-legacy'
    assert items[0]['status'] == 'PENDING_REVIEW'
    for field in FORBIDDEN_LIST_FIELDS:
        assert field not in items[0]


# ---------------------------------------------------------------------------
# Issue #1 — fail-closed projection behavior.
# A non-dict / malformed input must NEVER pass through unchanged; it must yield
# an empty safe projection so arbitrary content cannot bypass the allowlist.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('bad', [
    None,
    "REQ#leak",
    12345,
    ['PK', 'SK'],
    ('request_id', 'x'),
    object(),
    b'bytes',
])
def test_projection_non_dict_fails_closed(bad):
    result = project_client_request_list_item(bad)
    assert result == {}, f"non-dict input {type(bad).__name__} did not fail closed"
    assert result is not bad


def test_projection_malformed_cannot_expose_arbitrary_content():
    # A list of (key, value) pairs must not be coerced/leaked as a mapping.
    sneaky = [('quote_amount_cents', 5000), ('PK', 'REQ#secret')]
    result = project_client_request_list_item(sneaky)
    assert result == {}


def test_projection_normal_dict_behavior_unchanged():
    # Fail-closed change must not alter normal DynamoDB dict projection.
    projected = project_client_request_list_item(_full_quote_request(status='SENT'))
    assert projected['request_id'] == 'req-xyz'
    assert projected['status'] == 'QUOTE_SENT'
    for field in FORBIDDEN_LIST_FIELDS:
        assert field not in projected


def test_projection_empty_dict_returns_empty():
    assert project_client_request_list_item({}) == {}


# ---------------------------------------------------------------------------
# Issue #2/#3 — identity contract: raw PK/SK are never exposed, and every
# legitimate REQUEST carries first-class request_id/client_id (fallback is NOT
# required). CLIENT_REQUEST_LEGACY_ID_FALLBACK_REQUIRED=NO.
# ---------------------------------------------------------------------------

def test_projection_never_exposes_raw_pk_sk():
    rec = _full_quote_request()
    rec['PK'] = 'REQ#req-xyz'
    rec['SK'] = 'CLIENT#client-xyz'
    projected = project_client_request_list_item(rec)
    assert 'PK' not in projected
    assert 'SK' not in projected
    # Public ids still available from the first-class attributes.
    assert projected['request_id'] == 'req-xyz'
    assert projected['client_id'] == 'client-xyz'


def test_projection_modern_record_exposes_first_class_ids_only():
    # Contract regression: a modern record carries request_id/client_id directly;
    # the projection surfaces them without ever touching PK/SK.
    rec = {
        'PK': 'REQ#abc',
        'SK': 'CLIENT#def',
        'entity_type': 'REQUEST',
        'request_id': 'abc',
        'client_id': 'def',
        'status': 'PENDING_REVIEW',
        'service_type': 'OVERNIGHT',
    }
    projected = project_client_request_list_item(rec)
    assert projected['request_id'] == 'abc'
    assert projected['client_id'] == 'def'
    assert 'PK' not in projected and 'SK' not in projected
