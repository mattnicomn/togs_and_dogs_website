"""D-1: client-portal cancellation-denial marker (client booking list projection).

The client list (GET /client/requests) is an explicit allowlist projection. D-1 adds two
DERIVED keys, ``cancellation_denied`` and (optionally) ``cancellation_denied_at``, computed
from persisted BE-CANCEL-1 decision state. They are an explicit exception: no raw
``cancellation_*`` attribute is ever copied into the client projection.

Marker rule (all must hold):
  * ``cancellation_decision`` == 'DENY'
  * ``cancellation_decision_request_id`` == the booking's CURRENT non-empty
    ``cancellation_request_id``
  * ``status`` is exactly 'APPROVED' or 'ASSIGNED'

LOCAL source-level suite. No AWS/Terraform/network: the table is a local fake, auth helpers
are patched at their source modules, and no production record is read. The fake table
raises on any write, so a passing handler test also proves the list path performs none.
"""
import copy
import json
import os
import sys
import uuid
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))
os.environ.setdefault('DATA_TABLE_NAME', 'test-table')

import handlers.admin_handler as ah
from handlers.admin_handler import handler as admin_handler
import common.auth as common_auth
import common.entitlement as common_entitlement
import common.tenant_read_scope as common_trs
from boto3.dynamodb.conditions import Attr, ConditionExpressionBuilder
from common.auth import (
    CLIENT_REQUEST_LIST_ALLOWLIST,
    CLIENT_REQUEST_LIST_DERIVED_FIELDS,
    project_client_request_list_item,
)

CYCLE = str(uuid.UUID('6f1c2a3b-4d5e-4f60-8a7b-9c0d1e2f3a4b'))
OTHER_CYCLE = str(uuid.UUID('0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d'))
DENIED_AT = '2026-11-10T15:30:00.123456+00:00'

# Strings that must never appear anywhere in a client response.
SECRET_NOTE = 'SECRET-ADMIN-NOTE-do-not-disclose'
SECRET_ACTOR = 'owner-actor@secret.example'
SECRET_REASON = 'SECRET-CLIENT-REASON'


def _denied_record(**overrides):
    """A booking after BE-CANCEL-1 denied its cancellation request (restored to ASSIGNED)."""
    rec = {
        'PK': 'REQ#req-1',
        'SK': 'CLIENT#client-1',
        'entity_type': 'REQUEST',
        'company_id': 'tog_and_dogs',
        'request_id': 'req-1',
        'client_id': 'client-1',
        'client_name': 'Jane Doe',
        'pet_name': 'Buddy',
        'service_type': 'WALK_20MIN',
        'start_date': '2026-11-20',
        'created_at': '2026-11-01T10:00:00Z',
        'status': 'ASSIGNED',
        'worker_id': 'worker-secret@example.com',
        'worker_name': 'Ryan',
        # Persisted cancellation cycle + decision (BE-CANCEL-1).
        'cancellation_request_id': CYCLE,
        'cancellation_prior_status': 'ASSIGNED',
        'cancellation_reason': SECRET_REASON,
        'cancellation_requested_at': '2026-11-09T09:00:00+00:00',
        'cancellation_requested_by': 'CLIENT#client-1',
        'cancellation_decision': 'DENY',
        'cancellation_decision_result_status': 'ASSIGNED',
        'cancellation_decision_request_id': CYCLE,
        'cancellation_decision_at': DENIED_AT,
        'cancellation_decision_by': 'ADMIN',
        'cancellation_decision_actor': SECRET_ACTOR,
        'cancellation_decision_note': SECRET_NOTE,
        'audit_log': [{'status': 'ASSIGNED', 'note': SECRET_NOTE, 'actor': SECRET_ACTOR}],
        'sync_failures': [{'type': 'GOOGLE_CALENDAR', 'error': SECRET_NOTE}],
    }
    rec.update(overrides)
    return rec


def _project(**overrides):
    return project_client_request_list_item(_denied_record(**overrides))


# ---------------------------------------------------------------------------
# Marker rule: positive case
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('status', ['APPROVED', 'ASSIGNED'])
def test_marker_present_for_the_two_restorable_statuses(status):
    projected = _project(status=status)
    assert projected['cancellation_denied'] is True
    assert projected['cancellation_denied_at'] == '2026-11-10T15:30:00.123456+00:00'
    # The normal booking status is passed through untouched for the normal status display.
    assert projected['status'] == status


def test_marker_survives_a_later_move_between_approved_and_assigned():
    # The decision's result status is deliberately not compared with the live status.
    assert _project(status='APPROVED', cancellation_decision_result_status='ASSIGNED')['cancellation_denied'] is True


# ---------------------------------------------------------------------------
# Marker rule: status
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('status', [
    'CANCELLED', 'COMPLETED', 'ARCHIVED', 'ARCHIVE', 'DELETED', 'TRASH', 'IN_PROGRESS',
    'CANCELLATION_REQUESTED', 'CANCELLATION_DENIED', 'PENDING_REVIEW', 'DECLINED',
    'BOOKED', 'SCHEDULED', 'JOB_CREATED',
    'approved', 'Assigned', ' APPROVED', 'APPROVED ', '', None, 7, ['APPROVED'],
])
def test_no_marker_for_any_other_status(status):
    projected = _project(status=status)
    assert 'cancellation_denied' not in projected
    assert 'cancellation_denied_at' not in projected


def test_missing_status_has_no_marker():
    rec = _denied_record()
    del rec['status']
    assert 'cancellation_denied' not in project_client_request_list_item(rec)


# ---------------------------------------------------------------------------
# Marker rule: decision literal
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('decision', ['APPROVE', 'deny', 'Deny', 'DENY ', ' DENY', '', None, True, 1, ['DENY']])
def test_no_marker_unless_decision_is_exactly_deny(decision):
    assert 'cancellation_denied' not in _project(cancellation_decision=decision)


def test_no_marker_when_decision_fields_are_absent():
    rec = _denied_record()
    for key in ('cancellation_decision', 'cancellation_decision_request_id', 'cancellation_decision_at'):
        del rec[key]
    assert 'cancellation_denied' not in project_client_request_list_item(rec)


# ---------------------------------------------------------------------------
# Marker rule: exact cancellation-cycle identity
# ---------------------------------------------------------------------------

def test_no_marker_when_decision_belongs_to_an_earlier_cycle():
    """A new cancellation request created a new cycle id; the older denial is not shown."""
    assert 'cancellation_denied' not in _project(cancellation_request_id=OTHER_CYCLE)


def test_no_marker_when_decision_cycle_id_is_missing():
    rec = _denied_record()
    del rec['cancellation_decision_request_id']
    assert 'cancellation_denied' not in project_client_request_list_item(rec)


def test_no_marker_when_current_cycle_id_is_missing():
    rec = _denied_record()
    del rec['cancellation_request_id']
    assert 'cancellation_denied' not in project_client_request_list_item(rec)


@pytest.mark.parametrize('value', ['', '   ', None, 123, ['x'], {'a': 1}, True])
def test_no_marker_for_empty_or_non_string_equal_cycle_ids(value):
    """Equal but empty / non-string ids must never produce a marker."""
    projected = _project(cancellation_request_id=value, cancellation_decision_request_id=value)
    assert 'cancellation_denied' not in projected


def test_no_marker_for_case_or_whitespace_variants_of_the_cycle_id():
    assert 'cancellation_denied' not in _project(cancellation_decision_request_id=CYCLE.upper())
    assert 'cancellation_denied' not in _project(cancellation_decision_request_id=CYCLE + ' ')


def test_new_cancellation_cycle_clears_the_marker():
    """BE-CANCEL-1 removes cancellation_decision* when a client starts a new cycle and the
    booking is CANCELLATION_REQUESTED again: the portal shows 'Cancellation Pending' only."""
    rec = _denied_record(status='CANCELLATION_REQUESTED', cancellation_request_id=OTHER_CYCLE)
    for key in ('cancellation_decision', 'cancellation_decision_result_status',
                'cancellation_decision_request_id'):
        del rec[key]
    projected = project_client_request_list_item(rec)
    assert 'cancellation_denied' not in projected
    assert 'cancellation_denied_at' not in projected
    assert projected['status'] == 'CANCELLATION_REQUESTED'


def test_repeated_projection_of_the_same_denial_is_stable():
    """A repeated DENY on the same cycle is an idempotent no-op server-side; the derived
    marker is a pure function of the record."""
    rec = _denied_record()
    assert project_client_request_list_item(rec) == project_client_request_list_item(copy.deepcopy(rec))


def test_second_denial_in_a_new_cycle_shows_the_new_decision_time():
    later = '2026-11-12T08:00:00+00:00'
    projected = _project(cancellation_request_id=OTHER_CYCLE, cancellation_decision_request_id=OTHER_CYCLE,
                         cancellation_decision_at=later)
    assert projected['cancellation_denied'] is True
    assert projected['cancellation_denied_at'] == later


# ---------------------------------------------------------------------------
# P-3: the date is emitted only when valid and safe
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('raw,expected', [
    ('2026-11-10T15:30:00Z', '2026-11-10T15:30:00+00:00'),
    ('2026-11-10T15:30:00z', '2026-11-10T15:30:00+00:00'),
    ('2026-11-10T15:30:00+00:00', '2026-11-10T15:30:00+00:00'),
    ('2026-11-10T15:30:00.5+00:00', '2026-11-10T15:30:00.500000+00:00'),
    ('2026-11-10T10:30:00-05:00', '2026-11-10T15:30:00+00:00'),  # normalized to UTC
    ('  2026-11-10T15:30:00+00:00  ', '2026-11-10T15:30:00+00:00'),
])
def test_valid_timestamps_are_normalized_to_utc(raw, expected):
    assert _project(cancellation_decision_at=raw)['cancellation_denied_at'] == expected


@pytest.mark.parametrize('raw', [
    None, '', '   ', 'garbage', 'yesterday', '2026-11-10', '2026-11-10T15:30:00',  # naive
    '2026-13-45T99:99:99+00:00', 12345, 1.5, True, ['2026-11-10T15:30:00+00:00'],
    {'at': '2026-11-10T15:30:00+00:00'}, '<script>alert(1)</script>',
    '2026-11-10T15:30:00+00:00' + 'x' * 64,  # over-long
    SECRET_NOTE,
])
def test_invalid_or_unsafe_timestamps_omit_the_date_but_keep_the_marker(raw):
    projected = _project(cancellation_decision_at=raw)
    assert projected['cancellation_denied'] is True
    assert 'cancellation_denied_at' not in projected
    assert SECRET_NOTE not in json.dumps(projected)


def test_missing_timestamp_omits_the_date_but_keeps_the_marker():
    rec = _denied_record()
    del rec['cancellation_decision_at']
    projected = project_client_request_list_item(rec)
    assert projected['cancellation_denied'] is True
    assert 'cancellation_denied_at' not in projected


# ---------------------------------------------------------------------------
# No leakage: explicit allowlist exception, never a pass-through
# ---------------------------------------------------------------------------

def test_derived_fields_are_exactly_two_and_not_in_the_allowlist():
    assert CLIENT_REQUEST_LIST_DERIVED_FIELDS == ('cancellation_denied', 'cancellation_denied_at')
    assert not set(CLIENT_REQUEST_LIST_DERIVED_FIELDS) & set(CLIENT_REQUEST_LIST_ALLOWLIST)
    assert not [f for f in CLIENT_REQUEST_LIST_ALLOWLIST if f.startswith('cancellation')]


def test_projection_emits_only_allowlisted_and_the_two_derived_keys():
    projected = _project()
    assert set(projected) <= set(CLIENT_REQUEST_LIST_ALLOWLIST) | set(CLIENT_REQUEST_LIST_DERIVED_FIELDS)
    assert {k for k in projected if k.startswith('cancellation')} == set(CLIENT_REQUEST_LIST_DERIVED_FIELDS)


def test_projection_exact_key_set_for_a_denied_booking():
    assert set(_project()) == {
        'request_id', 'client_id', 'entity_type', 'status', 'client_name', 'pet_name',
        'service_type', 'start_date', 'worker_name', 'created_at',
        'cancellation_denied', 'cancellation_denied_at',
    }


@pytest.mark.parametrize('raw_field', [
    'cancellation_decision', 'cancellation_decision_note', 'cancellation_decision_actor',
    'cancellation_decision_by', 'cancellation_decision_at', 'cancellation_decision_request_id',
    'cancellation_decision_result_status', 'cancellation_request_id', 'cancellation_prior_status',
    'cancellation_reason', 'cancellation_requested_at', 'cancellation_requested_by',
    'audit_log', 'sync_failures', 'company_id', 'PK', 'SK', 'worker_id',
])
def test_raw_and_internal_fields_never_reach_the_client(raw_field):
    assert raw_field not in _project()


def test_no_secret_value_appears_anywhere_in_the_serialized_projection():
    serialized = json.dumps(_project())
    for secret in (SECRET_NOTE, SECRET_ACTOR, SECRET_REASON, CYCLE, 'worker-secret@example.com',
                   'tog_and_dogs', 'REQ#req-1', 'CLIENT#client-1', 'GOOGLE_CALENDAR'):
        assert secret not in serialized, secret


def test_projection_does_not_mutate_or_reuse_the_record():
    rec = _denied_record()
    snapshot = copy.deepcopy(rec)
    projected = project_client_request_list_item(rec)
    assert rec == snapshot
    assert projected is not rec


def test_non_dict_inputs_still_fail_closed():
    for bad in (None, 'x', 1, ['cancellation_decision', 'DENY'], object()):
        assert project_client_request_list_item(bad) == {}


def test_legacy_cancellation_denied_status_gets_no_marker_and_unchanged_status():
    """P-6: records written by the old backend (status CANCELLATION_DENIED) are unchanged."""
    legacy = _denied_record(status='CANCELLATION_DENIED')
    projected = project_client_request_list_item(legacy)
    assert projected['status'] == 'CANCELLATION_DENIED'
    assert 'cancellation_denied' not in projected


def test_legacy_pending_record_without_cycle_ids_has_no_marker():
    rec = {
        'PK': 'REQ#old', 'SK': 'CLIENT#client-1', 'entity_type': 'REQUEST', 'request_id': 'old',
        'client_id': 'client-1', 'status': 'CANCELLATION_REQUESTED',
        'cancellation_reason': SECRET_REASON, 'cancellation_requested_at': '2026-10-01T00:00:00Z',
    }
    projected = project_client_request_list_item(rec)
    assert set(projected) == {'request_id', 'client_id', 'entity_type', 'status'}


# ---------------------------------------------------------------------------
# End to end through GET /client/requests: authorization, scope, no writes
# ---------------------------------------------------------------------------

_DUMMY_FILTER = Attr('company_id').eq('tog_and_dogs')


class FakeTable:
    """Seedable scan() that records its kwargs and raises on any write."""

    def __init__(self, items):
        self._items = items
        self.scans = []

    def scan(self, **kwargs):
        self.scans.append(kwargs)
        return {'Items': list(self._items)}

    def put_item(self, *a, **k):
        raise AssertionError('client list must not write (put_item)')

    def update_item(self, *a, **k):
        raise AssertionError('client list must not write (update_item)')

    def delete_item(self, *a, **k):
        raise AssertionError('client list must not write (delete_item)')

    def batch_writer(self, *a, **k):
        raise AssertionError('client list must not write (batch_writer)')


def _client_event():
    return {
        'httpMethod': 'GET', 'path': '/client/requests', 'pathParameters': {},
        'queryStringParameters': {}, 'body': None,
        'requestContext': {'authorizer': {'claims': {
            'sub': 'sub-client-1', 'email': 'jane@example.com', 'email_verified': True,
            'cognito:groups': ['client'], 'custom:company_id': 'tog_and_dogs'}}},
    }


@pytest.fixture
def patched(monkeypatch):
    resolve = MagicMock(return_value='client-1')
    tenant_filter = MagicMock(return_value=_DUMMY_FILTER)
    monkeypatch.setattr(ah, 'get_effective_role', MagicMock(return_value='client'))
    monkeypatch.setattr(ah, 'get_claims', MagicMock(return_value={'email': 'jane@example.com', 'sub': 'sub-client-1'}))
    monkeypatch.setattr(common_auth, 'resolve_client_identity', resolve)
    monkeypatch.setattr(common_auth, 'get_current_company_id', MagicMock(return_value='tog_and_dogs'))
    monkeypatch.setattr(common_entitlement, 'require_active_tenant', MagicMock(return_value=None))
    monkeypatch.setattr(common_trs, 'build_tenant_read_filter', tenant_filter)
    monkeypatch.setattr(ah, 'build_tenant_read_filter', tenant_filter)
    return {'resolve': resolve, 'tenant_filter': tenant_filter}


def _invoke(table):
    import common.db as common_db
    orig_ah, orig_db = ah.table, common_db.table
    ah.table = common_db.table = table
    try:
        return admin_handler(_client_event(), None)
    finally:
        ah.table, common_db.table = orig_ah, orig_db


def _items(resp):
    assert resp['statusCode'] == 200, resp
    return json.loads(resp['body'])['requests']


def test_handler_list_shows_the_marker_and_nothing_sensitive(patched):
    table = FakeTable([_denied_record()])
    resp = _invoke(table)
    items = _items(resp)
    assert len(items) == 1
    assert items[0]['cancellation_denied'] is True
    assert items[0]['cancellation_denied_at'] == '2026-11-10T15:30:00.123456+00:00'
    assert items[0]['status'] == 'ASSIGNED'
    body = resp['body']
    for secret in (SECRET_NOTE, SECRET_ACTOR, SECRET_REASON, CYCLE, 'worker-secret@example.com',
                   'REQ#req-1', 'CLIENT#client-1', 'audit_log', 'sync_failures',
                   'cancellation_decision', 'cancellation_prior_status'):
        assert secret not in body, secret


def test_handler_list_mixed_bookings_only_the_denied_one_has_the_marker(patched):
    other_cycle = _denied_record(request_id='req-2', PK='REQ#req-2', cancellation_request_id=OTHER_CYCLE)
    pending = _denied_record(request_id='req-3', PK='REQ#req-3', status='CANCELLATION_REQUESTED')
    plain = {'request_id': 'req-4', 'client_id': 'client-1', 'entity_type': 'REQUEST',
             'status': 'APPROVED', 'start_date': '2026-11-01'}
    items = _items(_invoke(FakeTable([_denied_record(), other_cycle, pending, plain])))
    by_id = {i['request_id']: i for i in items}
    assert by_id['req-1'].get('cancellation_denied') is True
    for rid in ('req-2', 'req-3', 'req-4'):
        assert 'cancellation_denied' not in by_id[rid], rid


def test_handler_list_remains_scoped_to_the_resolved_client_and_tenant(patched):
    table = FakeTable([_denied_record()])
    _items(_invoke(table))
    assert len(table.scans) == 1
    # The scan filter is built from the SERVER-RESOLVED client id and the tenant read
    # filter, never from anything in the request.
    patched['resolve'].assert_called_once()
    patched['tenant_filter'].assert_called_once()
    assert patched['tenant_filter'].call_args.args[0] == 'tog_and_dogs'
    built = ConditionExpressionBuilder().build_expression(table.scans[0]['FilterExpression'])
    values = set(built.attribute_value_placeholders.values())
    names = set(built.attribute_name_placeholders.values())
    assert {'client-1', 'REQUEST'} <= values
    assert {'client_id', 'entity_type'} <= names


def test_handler_list_unlinked_client_gets_no_data_and_no_marker(patched, monkeypatch):
    monkeypatch.setattr(common_auth, 'resolve_client_identity', MagicMock(return_value=None))
    table = FakeTable([_denied_record()])
    resp = _invoke(table)
    assert resp['statusCode'] == 200
    assert json.loads(resp['body'])['requests'] == []
    assert table.scans == []
    assert 'cancellation_denied' not in resp['body']
