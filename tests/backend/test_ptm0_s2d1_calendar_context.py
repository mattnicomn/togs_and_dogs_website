"""Offline handler-level Calendar propagation; ownership validation stays real."""
import json
from unittest.mock import Mock

import pytest
from common import db, google_calendar as gc
from handlers import review_handler as review, cancellation_handler as cancellation
from handlers import assignment_handler as assignment

TENANTS = ['tog_and_dogs', 'test_tenant_alpha', 'future_tenant']


def event(tenant, body):
    return {'httpMethod': 'POST', 'path': '/admin/requests',
            'requestContext': {'authorizer': {'claims': {
                'custom:company_id': tenant, 'cognito:groups': 'owner',
                'email': 'owner@example.invalid'}}}, 'body': json.dumps(body)}


@pytest.fixture
def world(monkeypatch):
    from common import entitlement, cascade, status
    from common.notifications import service
    monkeypatch.setenv('TENANT_RESOLUTION_MODE', 'multi')
    monkeypatch.delenv('JOB_FUNCTION_NAME', raising=False)
    monkeypatch.setattr(entitlement, 'require_active_tenant', lambda e: None)
    monkeypatch.setattr(cascade, 'cascade_status_to_job', Mock())
    monkeypatch.setattr(status, 'is_valid_transition', lambda *a: True)
    monkeypatch.setattr(review, 'is_valid_transition', lambda *a: True)
    monkeypatch.setattr(review, 'handle_notifications', Mock(return_value={}))
    monkeypatch.setattr(service, 'notify_event', Mock())
    records = {}
    get = lambda pk, sk: records.get(pk)
    table = Mock()
    table.query.return_value = {'Items': [{'email': 'worker@example.invalid',
        'cognito_sub': 'linked', 'is_active': True, 'is_assignable': True}]}
    for mod in (db, review, cancellation):
        monkeypatch.setattr(mod, 'get_item', get)
        monkeypatch.setattr(mod, 'table', table)
    for mod in (review, cancellation):
        monkeypatch.setattr(mod, 'log_action', Mock())
        monkeypatch.setattr(mod, 'notify_event', Mock())
    monkeypatch.setattr(cancellation, 'record_sync_failure', Mock())
    sync = Mock(return_value={'status': 'calendar_updated'})
    delete = Mock(return_value=True)
    detailed = Mock(return_value=(True, False, None))
    monkeypatch.setattr(review, 'sync_calendar_event', sync)
    monkeypatch.setattr(gc, 'sync_calendar_event', sync)
    monkeypatch.setattr(review, 'delete_event', delete)
    monkeypatch.setattr(gc, 'delete_event_detailed', detailed)
    return records, table, sync, delete, detailed


def populate(world, tenant, children=False):
    parent = {'PK': 'REQ#r', 'SK': 'CLIENT#c', 'company_id': tenant,
              'status': 'SCHEDULED', 'workflow_type': 'VISIT_BOOKING',
              'google_event_id': 'parent-event', 'client_id': 'c'}
    world[0]['REQ#r'] = parent
    if children:
        parent['job_ids'] = ['j']
        world[0]['JOB#j'] = {'PK': 'JOB#j', 'SK': 'REQ#r', 'company_id': tenant,
                            'status': 'APPROVED', 'google_event_id': 'child-event'}
    return parent


@pytest.mark.parametrize('tenant', TENANTS)
@pytest.mark.parametrize('children', [False, True])
def test_review_delete_explicit_validated_owner(world, tenant, children):
    populate(world, tenant, children)
    response = review.handler(event(tenant, {'request_id': 'r', 'client_id': 'c',
        'status': 'CANCELLED', 'company_id': 'hostile_body_tenant'}), None)
    assert response['statusCode'] == 200
    world[3].assert_called_once_with('child-event' if children else 'parent-event',
                                     'r', company_id=tenant)


@pytest.mark.parametrize('tenant', TENANTS)
@pytest.mark.parametrize('children', [False, True])
def test_cancellation_explicit_validated_owner(world, tenant, children):
    populate(world, tenant, children)
    body = {'request_id': 'r', 'client_id': 'c', 'decision': 'APPROVE',
            'company_id': 'hostile_body_tenant'}
    response = cancellation.handle_admin_decision(body, event(tenant, body))
    assert response['statusCode'] == 200
    assert world[4].call_count == (2 if children else 1)
    assert all(c.kwargs == {'company_id': tenant} for c in world[4].call_args_list)


@pytest.mark.parametrize('tenant', TENANTS)
@pytest.mark.parametrize('handler', ['review', 'assignment'])
@pytest.mark.parametrize('has_event', [False, True])
def test_sync_pins_persisted_owner_despite_body(world, tenant, handler, has_event):
    populate(world, tenant, handler == 'assignment')
    if not has_event:
        for record in world[0].values():
            record.pop('google_event_id', None)
    body = {'request_id': 'r', 'req_id': 'r', 'client_id': 'c', 'job_id': 'j',
            'status': 'SCHEDULED', 'worker_id': 'worker@example.invalid',
            'company_id': 'tog_and_dogs' if tenant != 'tog_and_dogs' else 'test_tenant_alpha'}
    response = (review if handler == 'review' else assignment).handler(event(tenant, body), None)
    assert response['statusCode'] == 200
    world[2].assert_called_once()
    assert world[2].call_args.args[0]['company_id'] == tenant
    assert world[2].call_args.kwargs['google_event_id'] == (
        ('parent-event' if handler == 'review' else 'child-event') if has_event else None)


@pytest.mark.parametrize('handler', ['review', 'cancellation', 'assignment'])
@pytest.mark.parametrize('missing', [None, ''])
def test_missing_persisted_owner_never_uses_primary(world, handler, missing):
    populate(world, missing, handler == 'assignment')
    body = {'request_id': 'r', 'req_id': 'r', 'client_id': 'c', 'job_id': 'j',
            'status': 'CANCELLED', 'decision': 'APPROVE',
            'worker_id': 'worker@example.invalid', 'company_id': 'tog_and_dogs'}
    evt = event('tog_and_dogs', body)
    if handler == 'cancellation':
        cancellation.handle_admin_decision(body, evt)
    else:
        (review if handler == 'review' else assignment).handler(evt, None)
    for mock in world[2:]:
        mock.assert_not_called()


@pytest.mark.parametrize('handler', ['review', 'cancellation', 'assignment'])
def test_caller_mismatch_cannot_target_foreign_record(world, handler):
    populate(world, 'tog_and_dogs', handler == 'assignment')
    body = {'request_id': 'r', 'req_id': 'r', 'client_id': 'c', 'job_id': 'j',
            'status': 'CANCELLED', 'decision': 'APPROVE',
            'worker_id': 'worker@example.invalid', 'company_id': 'test_tenant_alpha'}
    evt = event('test_tenant_alpha', body)
    response = (cancellation.handle_admin_decision(body, evt) if handler == 'cancellation'
                else (review if handler == 'review' else assignment).handler(evt, None))
    assert response['statusCode'] == 403
    for mock in world[2:]:
        mock.assert_not_called()


@pytest.mark.parametrize('handler', ['review', 'cancellation'])
@pytest.mark.parametrize('child_owner', [None, '', 'tog_and_dogs'])
def test_child_mismatch_retains_child_reference(world, handler, child_owner):
    populate(world, 'test_tenant_alpha', True)
    world[0]['JOB#j']['company_id'] = child_owner
    body = {'request_id': 'r', 'client_id': 'c', 'status': 'CANCELLED', 'decision': 'APPROVE'}
    evt = event('test_tenant_alpha', body)
    if handler == 'review':
        review.handler(evt, None)
        world[3].assert_not_called()
    else:
        cancellation.handle_admin_decision(body, evt)
        world[4].assert_called_once_with('parent-event', 'r', company_id='test_tenant_alpha')
    assert not any(c.kwargs.get('Key', {}).get('PK') == 'JOB#j' and
                   c.kwargs.get('UpdateExpression') == 'REMOVE google_event_id'
                   for c in world[1].update_item.call_args_list)


@pytest.mark.parametrize('handler', ['review', 'cancellation'])
@pytest.mark.parametrize('children', [False, True])
def test_provider_denial_retains_references(world, handler, children):
    populate(world, 'test_tenant_alpha', children)
    world[3].return_value = False
    world[4].return_value = (False, False, 'PROVIDER_OWNERSHIP_MISMATCH')
    body = {'request_id': 'r', 'client_id': 'c', 'status': 'CANCELLED', 'decision': 'APPROVE'}
    evt = event('test_tenant_alpha', body)
    if handler == 'review':
        response = review.handler(evt, None)
        assert json.loads(response['body'])['calendar_result']['status'] == 'calendar_failed'
    else:
        cancellation.handle_admin_decision(body, evt)
    assert not any(c.kwargs.get('UpdateExpression') == 'REMOVE google_event_id'
                   for c in world[1].update_item.call_args_list)

@pytest.mark.parametrize('missing', [None, ''])
def test_review_sync_missing_owner_does_not_trust_body(world, missing):
    populate(world, missing)
    review.handler(event('tog_and_dogs', {'request_id': 'r', 'client_id': 'c',
        'status': 'SCHEDULED', 'company_id': 'tog_and_dogs'}), None)
    world[2].assert_not_called()


@pytest.mark.parametrize('handler', ['review', 'assignment'])
def test_sync_provider_failure_does_not_persist_event(world, handler):
    populate(world, 'test_tenant_alpha', handler == 'assignment')
    world[2].return_value = {'status': 'calendar_failed', 'message': 'PROVIDER_OWNERSHIP_MISMATCH'}
    body = {'request_id': 'r', 'req_id': 'r', 'client_id': 'c', 'job_id': 'j',
            'status': 'SCHEDULED', 'worker_id': 'worker@example.invalid'}
    response = (review if handler == 'review' else assignment).handler(event('test_tenant_alpha', body), None)
    assert response['statusCode'] == 200
    assert not any(c.kwargs.get('UpdateExpression') == 'SET google_event_id = :gid'
                   for c in world[1].update_item.call_args_list)
