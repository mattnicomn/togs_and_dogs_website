"""
Release 11E: Tenant Enforcement Hardening Tests

Covers:
  - Same-tenant access (must succeed — no regressions for current single-tenant system)
  - Cross-tenant access (must return 403)
  - Notification quota per-tenant parameterization
  - Export endpoint company_id filter
  - _resolve_admin_record company_id post-filter
  - Pet handler GET/PUT same-tenant vs cross-tenant checks
"""
import sys
import os
import json
from functools import wraps
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from unittest.mock import patch, MagicMock
from test_ptm0_s1_untagged_isolation import s1_read_table, s1_request, s1_event

# Import the handlers at module load time so their namespaces exist
from handlers.review_handler import handler as review_handler
from handlers.cancellation_handler import handler as cancellation_handler
from handlers.admin_handler import handler as admin_handler, _resolve_admin_record
from handlers.assignment_handler import handler as assignment_handler
from handlers.pet_handler import handler as pet_handler


def sync_mocks(func):
    """
    Decorator to copy mocked/patched common utilities to handler namespaces
    just before the test function body runs (while patch contexts are active),
    and restore them to their original values when the test finishes.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        import common.db
        import common.audit
        import common.notifications.service

        # Save original module-level references
        orig_review_get = review_handler.__globals__.get('get_item')
        orig_cancel_get = cancellation_handler.__globals__.get('get_item')
        orig_admin_get = admin_handler.__globals__.get('get_item')
        orig_pet_get = pet_handler.__globals__.get('get_item')

        orig_review_table = review_handler.__globals__.get('table')
        orig_cancel_table = cancellation_handler.__globals__.get('table')
        orig_admin_table = admin_handler.__globals__.get('table')
        orig_pet_table = pet_handler.__globals__.get('table')

        orig_review_log = review_handler.__globals__.get('log_action')
        orig_admin_log = admin_handler.__globals__.get('log_action')

        orig_review_notify = review_handler.__globals__.get('notify_event')
        orig_admin_notify = admin_handler.__globals__.get('notify_event')

        try:
            # Sync get_item
            review_handler.__globals__['get_item'] = common.db.get_item
            cancellation_handler.__globals__['get_item'] = common.db.get_item
            admin_handler.__globals__['get_item'] = common.db.get_item
            pet_handler.__globals__['get_item'] = common.db.get_item

            # Sync table
            review_handler.__globals__['table'] = common.db.table
            cancellation_handler.__globals__['table'] = common.db.table
            admin_handler.__globals__['table'] = common.db.table
            pet_handler.__globals__['table'] = common.db.table

            # Sync log_action
            review_handler.__globals__['log_action'] = common.audit.log_action
            admin_handler.__globals__['log_action'] = common.audit.log_action

            # Sync notify_event
            review_handler.__globals__['notify_event'] = common.notifications.service.notify_event
            admin_handler.__globals__['notify_event'] = common.notifications.service.notify_event

            return func(*args, **kwargs)
        finally:
            # Restore original module-level references
            review_handler.__globals__['get_item'] = orig_review_get
            cancellation_handler.__globals__['get_item'] = orig_cancel_get
            admin_handler.__globals__['get_item'] = orig_admin_get
            pet_handler.__globals__['get_item'] = orig_pet_get

            review_handler.__globals__['table'] = orig_review_table
            cancellation_handler.__globals__['table'] = orig_cancel_table
            admin_handler.__globals__['table'] = orig_admin_table
            pet_handler.__globals__['table'] = orig_pet_table

            review_handler.__globals__['log_action'] = orig_review_log
            admin_handler.__globals__['log_action'] = orig_admin_log

            review_handler.__globals__['notify_event'] = orig_review_notify
            admin_handler.__globals__['notify_event'] = orig_admin_notify
    return wrapper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_event(role='admin', company_id='tog_and_dogs', body=None, method='POST',
               path='/admin/review', path_params=None, query_params=None):
    """Build a minimal API Gateway event with Cognito authorizer claims."""
    return {
        'httpMethod': method,
        'path': path,
        'pathParameters': path_params or {},
        'queryStringParameters': query_params or {},
        'body': json.dumps(body or {}),
        'requestContext': {
            'authorizer': {
                'claims': {
                    'sub': 'test-sub-123',
                    'email': 'admin@example.com',
                    'cognito:groups': [role],
                    'custom:company_id': company_id
                }
            }
        }
    }


def make_req_record(company_id='tog_and_dogs', status='PENDING_REVIEW'):
    return {
        'PK': 'REQ#req-001',
        'SK': 'CLIENT#client-001',
        'entity_type': 'REQUEST',
        'company_id': company_id,
        'request_id': 'req-001',
        'client_id': 'client-001',
        'client_name': 'Jane Doe',
        'client_email': 'jane@example.com',
        'status': status,
        'workflow_type': 'VISIT_BOOKING',
        'start_date': '2030-01-01',
        'service_type': 'Dog Walking',
    }


def make_job_record(company_id='tog_and_dogs', status='ASSIGNED'):
    return {
        'PK': 'JOB#job-001',
        'SK': 'REQ#req-001',
        'entity_type': 'JOB',
        'company_id': company_id,
        'job_id': 'job-001',
        'request_id': 'req-001',
        'client_id': 'client-001',
        'worker_id': 'admin@example.com',
        'status': status,
    }


# ===========================================================================
# 1. review_handler — same-tenant access vs cross-tenant blocked
# ===========================================================================

@patch('common.audit.log_action')
@patch('common.db.table')
@patch('common.db.get_item')
@patch('common.cascade.cascade_status_to_job')
@patch('common.notifications.service.notify_event')
@sync_mocks
def test_review_handler_same_tenant_approved(mock_notify, mock_cascade, mock_get, mock_table,
                                              mock_log):
    """review_handler: same-tenant admin can transition a request (200 — no 403 regression)."""
    # Use PENDING_REVIEW -> DECLINED transition (simple, no side effects or M&G checks)
    req_item = make_req_record(company_id='tog_and_dogs', status='PENDING_REVIEW')

    mock_get.return_value = req_item
    mock_notify.return_value = {'success': True, 'message': 'ok'}
    mock_table.update_item.return_value = {}

    event = make_event(role='admin', company_id='tog_and_dogs',
                       body={'request_id': 'req-001', 'client_id': 'client-001',
                             'status': 'DECLINED'},
                       method='POST', path='/admin/review')

    resp = review_handler(event, {})
    assert resp['statusCode'] == 200, f"Expected 200, got {resp['statusCode']}: {resp['body']}"



@patch('common.db.get_item')
@sync_mocks
def test_review_handler_cross_tenant_blocked(mock_get):
    """review_handler: cross-tenant request must return 403."""
    # Record belongs to 'other_company'; caller is 'tog_and_dogs'
    cross_req = make_req_record(company_id='other_company', status='PENDING_REVIEW')
    mock_get.return_value = cross_req

    event = make_event(role='admin', company_id='tog_and_dogs',
                       body={'request_id': 'req-001', 'client_id': 'client-001', 'status': 'APPROVED'},
                       method='POST', path='/admin/review')

    resp = review_handler(event, {})
    assert resp['statusCode'] == 403, f"Expected 403, got {resp['statusCode']}"


# ===========================================================================
# 2. cancellation_handler — cross-tenant blocked on customer/admin cancel
# ===========================================================================

@patch('common.db.get_item')
@sync_mocks
def test_cancellation_customer_cross_tenant_blocked(mock_get):
    """cancellation_handler customer cancel: cross-tenant request must return 403."""
    cross_req = make_req_record(company_id='other_company')
    mock_get.return_value = cross_req

    event = make_event(role='client', company_id='tog_and_dogs',
                       body={'request_id': 'req-001', 'client_id': 'client-001',
                             'reason': 'Plans changed'},
                       method='POST', path='/client/cancel')

    resp = cancellation_handler(event, {})
    assert resp['statusCode'] == 403, f"Expected 403, got {resp['statusCode']}"


@patch('common.db.get_item')
@sync_mocks
def test_cancellation_admin_decision_cross_tenant_blocked(mock_get):
    """cancellation_handler admin decision: cross-tenant request must return 403."""
    cross_req = make_req_record(company_id='other_company')
    mock_get.return_value = cross_req

    event = make_event(role='admin', company_id='tog_and_dogs',
                       body={'request_id': 'req-001', 'client_id': 'client-001',
                             'decision': 'APPROVE'},
                       method='PUT', path='/admin/cancel/decision')

    resp = cancellation_handler(event, {})
    assert resp['statusCode'] == 403, f"Expected 403, got {resp['statusCode']}"


# ===========================================================================
# 3. admin_handler — single-item GET cross-tenant blocked
# ===========================================================================

@patch('common.db.get_item')
@sync_mocks
def test_admin_handler_get_single_request_cross_tenant_blocked(mock_get):
    """admin_handler GET single request: cross-tenant returns 403."""
    cross_req = make_req_record(company_id='other_company')
    mock_get.return_value = cross_req

    event = make_event(role='admin', company_id='tog_and_dogs',
                       body={},
                       method='GET', path='/admin/requests/req-001',
                       path_params={'requestId': 'req-001'},
                       query_params={'clientId': 'client-001'})

    resp = admin_handler(event, {})
    assert resp['statusCode'] == 403, f"Expected 403, got {resp['statusCode']}"


# ===========================================================================
# 4. admin_handler — job/complete cross-tenant blocked
# ===========================================================================

@patch('common.db.get_item')
@sync_mocks
def test_admin_handler_job_complete_cross_tenant_blocked(mock_get):
    """admin_handler job/complete: cross-tenant JOB returns 403."""
    cross_job = make_job_record(company_id='other_company')
    mock_get.return_value = cross_job

    event = make_event(role='admin', company_id='tog_and_dogs',
                       body={'job_id': 'job-001', 'request_id': 'req-001'},
                       method='POST', path='/admin/job/complete')

    resp = admin_handler(event, {})
    assert resp['statusCode'] == 403, f"Expected 403, got {resp['statusCode']}"


# ===========================================================================
# 5. admin_handler — export-data returns only caller's company records
# ===========================================================================

@pytest.mark.parametrize('company', ['tog_and_dogs', 'test_tenant_alpha', 'future_tenant'])
def test_admin_handler_export_filters_by_company(s1_read_table, company):
    """Evaluate the actual filter over mixed records, including absent fields."""
    records = [s1_request('own', company), s1_request('wrong', 'other_company'),
               s1_request('legacy'), s1_request('null', None), s1_request('empty', '')]
    for kind, prefix in [('PET', 'PET'), ('JOB', 'JOB'), ('STAFF', 'COMPANY'), ('CLIENT', 'COMPANY')]:
        for label, association in [('own', company), ('wrong', 'other_company'), ('legacy', None)]:
            row = {'PK': f'{prefix}#{label}-{kind}', 'SK': f'{kind}#{label}', 'entity_type': kind}
            if association is not None:
                row['company_id'] = association
            records.append(row)
    s1_read_table.seed(records)
    # Force small DynamoDB pages: every real scan must retain the same filter.
    original_scan = s1_read_table.table.scan
    with patch.object(s1_read_table.table, 'scan', side_effect=lambda **kw: original_scan(**dict(kw, Limit=2))) as scans:
        resp = admin_handler(s1_event(company, '/admin/export-data'), {})
    assert resp['statusCode'] == 200
    data = json.loads(resp['body'])
    all_items = sum((data[key] for key in ('requests', 'clients', 'pets', 'staff', 'jobs')), [])
    expected = {row['PK'] for row in records if row.get('company_id') == company
                or (company == 'tog_and_dogs' and 'company_id' not in row)}
    assert {item['PK'] for item in all_items} == expected
    assert len(scans.call_args_list) > 1
    filters = [call.kwargs['FilterExpression'] for call in scans.call_args_list]
    assert all(condition == filters[0] for condition in filters)
    assert all('ExclusiveStartKey' in call.kwargs for call in scans.call_args_list[1:])
    # Successful exports already audit once. S1 must not add or remove this write;
    # the audit is mocked, and no production export is invoked.
    s1_read_table.audit.assert_called_once()
    assert s1_read_table.audit.call_args.args[1] == 'EXPORT_BACKUP'


# ===========================================================================
# 6. _resolve_admin_record — scan fallback post-filtered by company_id
# ===========================================================================

@patch('common.db.table')
@patch('common.db.get_item')
@sync_mocks
def test_resolve_admin_record_scan_filters_by_company(mock_get, mock_table):
    """_resolve_admin_record: scan fallback only returns records matching company_id."""
    # Direct get_item returns None (forcing the scan fallback)
    mock_get.return_value = None

    # Scan returns one record from another company
    cross_record = {
        'PK': 'REQ#some-id',
        'SK': 'CLIENT#c-1',
        'company_id': 'other_company',
        'request_id': 'some-id'
    }
    mock_table.scan.return_value = {'Items': [cross_record]}

    item, actual_pk, actual_sk = _resolve_admin_record('REQ#some-id', 'CLIENT#c-1',
                                                        company_id='tog_and_dogs')
    # Should return None because the only found record is from a different tenant
    assert item is None, "Cross-tenant record should have been filtered out in scan fallback"


# ===========================================================================
# 7. notification quota — per-tenant company_id parameterization
# ===========================================================================

@patch('common.notifications.suppression.get_item')
@patch('common.db.put_item')
@patch('common.db.get_item')
@patch('common.db.table')
@patch('common.notifications.service.PostmarkClient.send_email')
def test_quota_uses_record_company_id(mock_send, mock_table, mock_get, mock_put, mock_suppress):
    """notify_event: quota get_item uses QUOTA#<company_id>, not hardcoded tog_and_dogs."""
    from common.notifications.service import notify_event

    mock_send.return_value = {
        'delivered': True, 'mode': 'external_provider',
        'provider': 'postmark', 'message': 'Email sent.',
        'message_id': 'pm-999'
    }
    mock_get.return_value = {'sent_count': 0}
    mock_suppress.return_value = None

    record = {
        'request_id': 'req-xyz',
        'client_id': 'client-xyz',
        'client_email': 'test@example.com',
        'client_name': 'Test User',
        'company_id': 'future_tenant',  # Different from tog_and_dogs
        'approval_notification_status': None,
    }

    with patch('common.notifications.config.NotificationConfig.ENABLED', True), \
         patch('common.notifications.config.NotificationConfig.DRY_RUN', False), \
         patch('common.notifications.config.NotificationConfig.NOTIFICATION_MODE', 'external_provider'), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_MONTHLY_LIMIT', 1000), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_QUOTA_WARN_THRESHOLD', 80), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_QUOTA_HARD_STOP', False):

        notify_event('CUSTOMER_APPROVED', record=record)

    # Verify the quota was checked/incremented using QUOTA#future_tenant, not QUOTA#tog_and_dogs
    quota_get_calls = [
        call for call in mock_get.call_args_list
        if call[0] and call[0][0].startswith('QUOTA#')
    ]
    assert any('future_tenant' in str(c) for c in quota_get_calls), \
        f"Expected QUOTA#future_tenant get_item call, got: {quota_get_calls}"

    quota_update_calls = [
        call for call in mock_table.update_item.call_args_list
        if call[1].get('Key', {}).get('PK', '').startswith('QUOTA#')
    ]
    assert any('future_tenant' in str(c) for c in quota_update_calls), \
        f"Expected QUOTA#future_tenant update_item call, got: {quota_update_calls}"


@patch('common.notifications.suppression.get_item')
@patch('common.db.put_item')
@patch('common.db.get_item')
@patch('common.db.table')
@patch('common.notifications.service.PostmarkClient.send_email')
def test_quota_defaults_to_tog_and_dogs_when_no_company_id(
        mock_send, mock_table, mock_get, mock_put, mock_suppress):
    """notify_event: quota falls back to tog_and_dogs when record has no company_id."""
    from common.notifications.service import notify_event

    mock_send.return_value = {
        'delivered': True, 'mode': 'external_provider',
        'provider': 'postmark', 'message': 'Email sent.',
        'message_id': 'pm-100'
    }
    mock_get.return_value = {'sent_count': 0}
    mock_suppress.return_value = None

    record = {
        'request_id': 'req-abc',
        'client_id': 'client-abc',
        'client_email': 'legacy@example.com',
        'client_name': 'Legacy User',
        # No company_id — legacy record
        'approval_notification_status': None,
    }

    with patch('common.notifications.config.NotificationConfig.ENABLED', True), \
         patch('common.notifications.config.NotificationConfig.DRY_RUN', False), \
         patch('common.notifications.config.NotificationConfig.NOTIFICATION_MODE', 'external_provider'), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_MONTHLY_LIMIT', 1000), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_QUOTA_WARN_THRESHOLD', 80), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_QUOTA_HARD_STOP', False):

        notify_event('CUSTOMER_APPROVED', record=record)

    quota_get_calls = [
        call for call in mock_get.call_args_list
        if call[0] and 'QUOTA#' in str(call[0][0])
    ]
    assert any('tog_and_dogs' in str(c) for c in quota_get_calls), \
        f"Expected QUOTA#tog_and_dogs get_item call for legacy record, got: {quota_get_calls}"


# ===========================================================================
# 8. assignment_handler — same-tenant vs cross-tenant blocked
# ===========================================================================

@patch('common.db.table')
@patch('common.db.get_item')
@patch('common.notifications.service.notify_event')
@patch('common.google_calendar.sync_calendar_event')
def test_assignment_handler_same_tenant_succeeds(mock_cal, mock_notify, mock_get, mock_table):
    """assignment_handler: same-tenant assignment with valid staff succeeds."""
    req_rec = make_req_record(company_id='tog_and_dogs', status='APPROVED')
    req_rec['job_ids'] = ['job-001']
    req_rec['is_multi_day'] = False
    req_rec['primary_job_id'] = 'job-001'

    job_rec = make_job_record(company_id='tog_and_dogs', status='APPROVED')

    staff_rec = {
        'PK': 'COMPANY#tog_and_dogs',
        'SK': 'STAFF#staff-001',
        'email': 'staff@example.com',
        'is_active': True,
        'is_assignable': True,
        'cognito_sub': 'sub-staff-001'
    }

    def _get_item(pk, sk):
        if pk.startswith('REQ#'):
            return req_rec
        if pk.startswith('JOB#'):
            return job_rec
        return None

    mock_get.side_effect = _get_item
    mock_table.query.return_value = {'Items': [staff_rec]}
    mock_table.update_item.return_value = {}
    mock_cal.return_value = {'status': 'ok', 'event_id': 'gcal-evt-1'}
    mock_notify.return_value = {'success': True, 'message': 'ok'}

    event = make_event(role='admin', company_id='tog_and_dogs',
                       body={
                           'job_id': 'job-001',
                           'req_id': 'req-001',
                           'client_id': 'client-001',
                           'worker_id': 'staff@example.com',
                           'worker_name': 'Staff Member'
                       },
                       method='POST', path='/admin/assign')

    resp = assignment_handler(event, {})
    assert resp['statusCode'] == 200, f"Expected 200, got {resp['statusCode']}: {resp['body']}"


@patch('common.db.table')
@patch('common.db.get_item')
def test_assignment_handler_cross_tenant_blocked(mock_get, mock_table):
    """assignment_handler: cross-tenant REQ# must return 403."""
    cross_req = make_req_record(company_id='other_company', status='APPROVED')
    cross_req['job_ids'] = ['job-001']

    mock_get.return_value = cross_req

    staff_rec = {
        'PK': 'COMPANY#tog_and_dogs',
        'SK': 'STAFF#staff-001',
        'email': 'staff@example.com',
        'is_active': True,
        'is_assignable': True,
        'cognito_sub': 'sub-staff-001'
    }
    mock_table.query.return_value = {'Items': [staff_rec]}

    event = make_event(role='admin', company_id='tog_and_dogs',
                       body={
                           'job_id': 'job-001',
                           'req_id': 'req-001',
                           'client_id': 'client-001',
                           'worker_id': 'staff@example.com',
                           'worker_name': 'Staff'
                       },
                       method='POST', path='/admin/assign')

    resp = assignment_handler(event, {})
    assert resp['statusCode'] == 403, f"Expected 403, got {resp['statusCode']}"


# ===========================================================================
# 9. pet_handler — indirect tenant validation same-tenant vs cross-tenant
# ===========================================================================

@patch('common.db.table')
@patch('common.db.get_item')
@sync_mocks
def test_pet_handler_get_same_tenant_succeeds(mock_get, mock_table):
    """pet_handler GET: same-tenant access returns 200 when client profile matches."""
    pet_record = {
        'PK': 'PET#pet-001',
        'SK': 'CLIENT#client-001',
        'company_id': 'tog_and_dogs',
        'pet_id': 'pet-001',
        'client_id': 'client-001',
        'name': 'Buddy'
    }
    client_profile = {
        'PK': 'COMPANY#tog_and_dogs',
        'SK': 'CLIENT#client-001',
        'client_id': 'client-001'
    }

    mock_get.return_value = pet_record
    mock_table.get_item.return_value = {'Item': client_profile}

    event = make_event(role='admin', company_id='tog_and_dogs',
                       method='GET', path='/admin/pets/pet-001',
                       path_params={'petId': 'pet-001'},
                       query_params={'clientId': 'client-001'})

    resp = pet_handler(event, {})
    assert resp['statusCode'] == 200, f"Expected 200, got {resp['statusCode']}: {resp['body']}"


@patch('common.db.table')
@patch('common.db.get_item')
@sync_mocks
def test_pet_handler_get_cross_tenant_blocked(mock_get, mock_table):
    """pet_handler GET: cross-tenant access returns 403 when client profile check fails."""
    pet_record = {
        'PK': 'PET#pet-001',
        'SK': 'CLIENT#client-001',
        'company_id': 'other_company',
        'pet_id': 'pet-001',
        'client_id': 'client-001',
        'name': 'Buddy'
    }

    mock_get.return_value = pet_record
    mock_table.get_item.return_value = {'Item': None}  # Not found under tog_and_dogs

    event = make_event(role='admin', company_id='tog_and_dogs',
                       method='GET', path='/admin/pets/pet-001',
                       path_params={'petId': 'pet-001'},
                       query_params={'clientId': 'client-001'})

    resp = pet_handler(event, {})
    assert resp['statusCode'] == 403, f"Expected 403, got {resp['statusCode']}"


@patch('common.db.table')
@patch('common.db.get_item')
@sync_mocks
def test_pet_handler_put_same_tenant_succeeds(mock_get, mock_table):
    """pet_handler PUT: same-tenant pet creation/update succeeds."""
    mock_get.return_value = {}  # New pet
    client_profile = {
        'PK': 'COMPANY#tog_and_dogs',
        'SK': 'CLIENT#client-001',
        'client_id': 'client-001'
    }
    mock_table.get_item.return_value = {'Item': client_profile}
    mock_table.put_item.return_value = {}

    event = make_event(role='admin', company_id='tog_and_dogs',
                       body={'client_id': 'client-001', 'name': 'Buddy'},
                       method='PUT', path='/admin/pets/NEW',
                       path_params={'petId': 'NEW'})

    resp = pet_handler(event, {})
    assert resp['statusCode'] == 200, f"Expected 200, got {resp['statusCode']}: {resp['body']}"


@patch('common.db.table')
@patch('common.db.get_item')
@sync_mocks
def test_pet_handler_put_cross_tenant_blocked(mock_get, mock_table):
    """pet_handler PUT: cross-tenant pet creation/update returns 403."""
    mock_get.return_value = {}
    mock_table.get_item.return_value = {'Item': None}  # Not found under tog_and_dogs

    event = make_event(role='admin', company_id='tog_and_dogs',
                       body={'client_id': 'client-001', 'name': 'Buddy'},
                       method='PUT', path='/admin/pets/NEW',
                       path_params={'petId': 'NEW'})

    resp = pet_handler(event, {})
    assert resp['statusCode'] == 403, f"Expected 403, got {resp['statusCode']}"
