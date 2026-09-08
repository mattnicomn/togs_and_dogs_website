"""Offline prerequisite contracts: real ownership checks, mocked service boundaries."""
import json
import uuid
from unittest.mock import Mock

import pytest
from common import db, google_calendar as gc
from handlers import admin_handler as admin, job_handler as job, intake_handler as intake
from test_ptm0_s2d1_calendar_context import world, event, populate, TENANTS


@pytest.fixture
def admin_world(world, monkeypatch):
    monkeypatch.setattr(admin, 'get_item', db.get_item)
    monkeypatch.setattr(admin, 'table', world[1])
    monkeypatch.setattr(admin, 'log_action', Mock())
    monkeypatch.setattr(admin, 'notify_event', Mock())
    monkeypatch.setattr(admin, 'sync_calendar_event', world[2])
    monkeypatch.setattr(admin, 'delete_event', world[3])
    return world


def admin_call(tenant, action='ARCHIVE', **body):
    return admin.handler(event(tenant, {'action': action, 'PK': 'REQ#r', 'SK': 'CLIENT#c',
                                      'company_id': 'hostile_owner', **body}), None)


@pytest.mark.parametrize('tenant', TENANTS)
@pytest.mark.parametrize('lookup', ['direct', 'swapped', 'scan'])
def test_admin_lookup_validated(admin_world, monkeypatch, tenant, lookup):
    parent = populate(admin_world, tenant)
    def get(pk, sk):
        if lookup == 'direct' and (pk, sk) == ('REQ#r', 'CLIENT#c'):
            return parent
        if lookup == 'swapped' and (pk, sk) == ('REQ#r', 'CLIENT#c'):
            return parent
        return None
    monkeypatch.setattr(db, 'get_item', get)
    admin_world[1].scan.return_value = {'Items': [parent]}
    keys = {'PK': 'CLIENT#c', 'SK': 'REQ#r'} if lookup == 'swapped' else {}
    response = admin_call(tenant, **keys)
    assert json.loads(response['body'])['success'] == 1
    admin_world[3].assert_called_once_with('parent-event', 'REQ#r', company_id=tenant)


@pytest.mark.parametrize('lookup', ['direct', 'swapped', 'scan'])
@pytest.mark.parametrize('owner', ['tog_and_dogs', None, '', 'bad-id', 'AAA'])
def test_admin_rejects_owner_before_side_effects(admin_world, monkeypatch, lookup, owner):
    parent = populate(admin_world, owner)
    monkeypatch.setattr(db, 'get_item', lambda pk, sk: parent if lookup != 'scan' and
                        (pk, sk) == ('REQ#r', 'CLIENT#c') else None)
    admin_world[1].scan.return_value = {'Items': [parent]}
    keys = {'PK': 'CLIENT#c', 'SK': 'REQ#r'} if lookup == 'swapped' else {}
    response = admin_call('test_tenant_alpha', **keys)
    assert json.loads(response['body'])['failed'] == 1
    admin_world[1].update_item.assert_not_called()
    admin.log_action.assert_not_called()
    admin_world[3].assert_not_called()


def test_admin_missing_caller_rejected_even_single_mode(admin_world, monkeypatch):
    populate(admin_world, 'tog_and_dogs')
    monkeypatch.setenv('TENANT_RESOLUTION_MODE', 'single')
    response = admin_call(None)
    assert json.loads(response['body'])['failed'] == 1
    admin_world[1].update_item.assert_not_called()
    admin.log_action.assert_not_called()


def test_admin_mixed_batch_only_authorized_records(admin_world):
    populate(admin_world, 'test_tenant_alpha')
    admin_world[0]['REQ#foreign'] = {'PK': 'REQ#foreign', 'SK': 'CLIENT#c',
                                    'company_id': 'tog_and_dogs', 'google_event_id': 'foreign'}
    response = admin_call('test_tenant_alpha', records=[{'PK': 'REQ#r', 'SK': 'CLIENT#c'},
        {'PK': 'REQ#foreign', 'SK': 'CLIENT#c'}])
    result = json.loads(response['body'])
    assert (result['success'], result['failed']) == (1, 1)
    assert all(c.kwargs['Key']['PK'] == 'REQ#r' for c in admin_world[1].update_item.call_args_list)
    assert admin.log_action.call_count == 1
    admin_world[3].assert_called_once_with('parent-event', 'REQ#r', company_id='test_tenant_alpha')


@pytest.mark.parametrize('tenant', TENANTS)
def test_admin_sync_pinned(admin_world, tenant):
    populate(admin_world, tenant)
    admin_call(tenant, 'APPROVED')
    admin_world[2].assert_called_once()
    assert admin_world[2].call_args.args[0]['company_id'] == tenant


@pytest.mark.parametrize('mutation', ['valid', 'foreign', 'missing', 'key', 'relation', 'failure', 'exception'])
def test_admin_child_deletion(admin_world, mutation):
    populate(admin_world, 'test_tenant_alpha', True)
    child = admin_world[0]['JOB#j']
    if mutation == 'foreign': child['company_id'] = 'tog_and_dogs'
    if mutation == 'missing': child.pop('company_id')
    if mutation == 'key': child['PK'] = 'JOB#other'
    if mutation == 'relation': child['SK'] = 'REQ#other'
    if mutation == 'failure': admin_world[3].return_value = False
    if mutation == 'exception': admin_world[3].side_effect = gc.ProviderBindingError('PROVIDER_OWNERSHIP_MISMATCH')
    admin_call('test_tenant_alpha')
    removes = [c for c in admin_world[1].update_item.call_args_list
               if c.kwargs.get('UpdateExpression') == 'REMOVE google_event_id']
    assert len(removes) == (1 if mutation == 'valid' else 0)
    if mutation in ['foreign', 'missing', 'key', 'relation']:
        admin_world[3].assert_not_called()
    else:
        admin_world[3].assert_called_once_with('child-event', 'REQ#r', company_id='test_tenant_alpha')


@pytest.fixture
def jobs(world, monkeypatch):
    from common import pet_profile
    monkeypatch.setattr(job, 'get_item', db.get_item)
    monkeypatch.setattr(job, 'table', world[1])
    put = Mock(return_value=True)
    pets = Mock(return_value={'pet_ids': ['p']})
    monkeypatch.setattr(job, 'put_item', put)
    monkeypatch.setattr(job.time, 'sleep', Mock())
    monkeypatch.setattr(pet_profile, 'create_or_link_pets_from_request', pets)
    request = populate(world, 'test_tenant_alpha')
    request.update(service_type='CHECK_IN', visits_per_day=1, visit_windows=['MORNING'],
                   start_date='2026-09-20', end_date='2026-09-20')
    return world, put, pets


def run_job(**fields):
    return job.handler({'request_id': 'r', 'client_id': 'c', **fields}, None)


def existing_child(jobs, owner='test_tenant_alpha'):
    jid = str(uuid.uuid5(uuid.NAMESPACE_URL, 'togs-and-dogs:check-in:r:2026-09-20:MORNING'))
    child = {'PK': 'JOB#'+jid, 'SK': 'REQ#r', 'company_id': owner,
             'request_id': 'r', 'calendar_event_id': 'td'+uuid.UUID(jid).hex}
    jobs[0][0][child['PK']] = child
    return child


@pytest.mark.parametrize('tenant', TENANTS)
def test_job_new_owner_from_request(jobs, tenant):
    jobs[0][0]['REQ#r']['company_id'] = tenant
    result = run_job(expected_company_id=tenant, company_id='hostile_body')
    assert 'error' not in result
    assert jobs[1].call_args.args[0]['company_id'] == tenant
    assert jobs[0][2].call_args.args[0]['company_id'] == tenant


@pytest.mark.parametrize('fields', [{}, {'expected_company_id': None}, {'expected_company_id': ''},
    {'expected_company_id': 'tog_and_dogs'}, {'expected_company_id': 'bad-id'},
    {'expected_company_id': []}, {'expected_company_id': ' TEST '},
    {'expected_company_id': 'test_tenant_alpha', 'google_event_id': 'foreign'}])
def test_job_invalid_envelope_before_side_effects(jobs, fields):
    assert 'error' in run_job(**fields)
    jobs[1].assert_not_called()
    jobs[2].assert_not_called()
    jobs[0][2].assert_not_called()
    jobs[0][1].update_item.assert_not_called()


@pytest.mark.parametrize('expected', ['absent', 'test_tenant_alpha', 'tog_and_dogs', None])
@pytest.mark.parametrize('mutation', ['valid', 'owner', 'missing', 'relation', 'key'])
def test_job_recovery_three_way_ownership(jobs, expected, mutation):
    child = existing_child(jobs)
    if mutation == 'owner': child['company_id'] = 'tog_and_dogs'
    if mutation == 'missing': child.pop('company_id')
    if mutation == 'relation': child['SK'] = 'REQ#foreign'
    if mutation == 'key': child['PK'] = 'JOB#foreign'
    fields = {} if expected == 'absent' else {'expected_company_id': expected}
    result = run_job(**fields)
    allowed = mutation == 'valid' and expected in ['absent', 'test_tenant_alpha']
    assert ('error' not in result) == allowed
    assert jobs[0][2].call_count == int(allowed)
    jobs[1].assert_not_called()
    jobs[2].assert_not_called()
    if not allowed: jobs[0][1].update_item.assert_not_called()


def test_job_legacy_partial_recovery_cannot_create_or_sync(jobs):
    existing_child(jobs)
    jobs[0][0]['REQ#r']['visit_windows'] = ['MORNING', 'EVENING']
    jobs[0][0]['REQ#r']['visits_per_day'] = 2
    assert 'error' in run_job()
    jobs[0][2].assert_not_called()
    jobs[1].assert_not_called()
    jobs[2].assert_not_called()


@pytest.mark.parametrize('hint', [None, 'parent-event'])
def test_job_event_hint_equal_only(jobs, hint):
    result = run_job(expected_company_id='test_tenant_alpha', google_event_id=hint)
    assert 'error' not in result


@pytest.mark.parametrize('owner', [None, '', 'bad-id', 'tog_and_dogs'])
def test_job_invalid_request_owner(jobs, owner):
    jobs[0][0]['REQ#r']['company_id'] = owner
    assert 'error' in run_job(expected_company_id='test_tenant_alpha')
    jobs[1].assert_not_called()
    jobs[2].assert_not_called()
    jobs[0][2].assert_not_called()


@pytest.mark.parametrize('tenant', TENANTS)
def test_review_producer_persisted_tenant(world, monkeypatch, tenant):
    from handlers import review_handler as review
    parent = populate(world, tenant)
    parent['status'] = 'QUOTED'
    client = Mock()
    monkeypatch.setattr(review.boto3, 'client', Mock(return_value=client))
    monkeypatch.setenv('JOB_FUNCTION_NAME', 'offline-job')
    response = review.handler(event(tenant, {'request_id': 'r', 'client_id': 'c',
        'status': 'APPROVED', 'company_id': 'hostile_body'}), None)
    assert response['statusCode'] == 200
    payload = json.loads(client.invoke.call_args.kwargs['Payload'])
    assert payload['expected_company_id'] == tenant


@pytest.mark.parametrize('tenant', TENANTS)
def test_admin_intake_producer(world, monkeypatch, tenant):
    client = Mock()
    monkeypatch.setattr(intake.boto3, 'client', Mock(return_value=client))
    monkeypatch.setenv('JOB_FUNCTION_NAME', 'offline-job')
    monkeypatch.setattr(intake, 'get_item', Mock(return_value={'company_id': tenant}))
    monkeypatch.setattr(intake, 'put_item', Mock(return_value=True))
    monkeypatch.setattr(intake, 'table', world[1])
    body = {'client_id': 'c', 'client_name': 'Client', 'pet_names': 'Dog',
            'start_date': '2026-09-20', 'is_test_booking': True, 'company_id': 'hostile_body'}
    response = intake._handle_admin_created_booking(event(tenant, body), body)
    assert response['statusCode'] == 200
    assert json.loads(client.invoke.call_args.kwargs['Payload'])['expected_company_id'] == tenant

@pytest.mark.parametrize('tenant', TENANTS)
@pytest.mark.parametrize('portal', [False, True])
def test_intake_workflow_producer(world, monkeypatch, tenant, portal):
    from common import auth
    monkeypatch.setattr(intake, 'put_item', Mock(return_value=True))
    monkeypatch.setattr(intake, 'table', world[1])
    monkeypatch.setattr(intake, 'notify_event', Mock())
    monkeypatch.setattr(intake, 'STATE_MACHINE_ARN', 'offline-state-machine')
    sfn = Mock()
    monkeypatch.setattr(intake, 'sfn', sfn)
    world[1].query.return_value = {'Items': [], 'Count': 0}
    body = {'client_name': 'Client', 'client_email': 'client@example.invalid',
            'pet_names': 'Dog', 'service_type': 'PET_SITTING', 'start_date': '2026-09-20',
            'is_test_booking': True, 'accepted_terms': True, 'accepted_privacy': True,
            'terms_version': '1.0', 'privacy_version': '1.0', 'company_id': 'hostile_body'}
    evt = event(tenant, body)
    if portal:
        evt['path'] = '/client/requests'
        evt['requestContext']['authorizer']['claims']['cognito:groups'] = 'client'
        monkeypatch.setattr(auth, 'resolve_client_identity', Mock(return_value='c'))
        monkeypatch.setattr(intake, 'get_item', Mock(return_value={
            'company_id': tenant, 'is_active': True, 'portal_enabled': True}))
    else:
        evt['path'] = '/requests'
        evt['requestContext'] = {'domainName': 'offline.example.invalid'}
        monkeypatch.setenv('PUBLIC_INTAKE_DOMAIN_MAP', json.dumps({'offline.example.invalid': {'tenant_id': tenant, 'active': True, 'public_intake_enabled': True}}))
        monkeypatch.setattr(db, 'get_item', Mock(return_value={
            'company_id': tenant, 'is_active': True, 'subscription_status': 'active'}))
    result = intake.handler(evt, None)
    assert result['statusCode'] == 200
    payload = json.loads(sfn.start_execution.call_args.kwargs['input'])
    assert payload['expected_company_id'] == tenant
    assert intake.put_item.call_args.args[0]['company_id'] == tenant


@pytest.mark.parametrize('failure', [False, gc.ProviderBindingError('PROVIDER_OWNERSHIP_MISMATCH')])
def test_admin_parent_failure_keeps_reference(admin_world, failure):
    populate(admin_world, 'test_tenant_alpha')
    if isinstance(failure, Exception): admin_world[3].side_effect = failure
    else: admin_world[3].return_value = failure
    result = admin_call('test_tenant_alpha')
    assert json.loads(result['body'])['failures']
    assert not any(c.kwargs.get('UpdateExpression') == 'REMOVE google_event_id'
                   for c in admin_world[1].update_item.call_args_list)


@pytest.mark.parametrize('foreign', [False, True])
def test_linked_replay_validates_existing_owner(jobs, foreign):
    child = existing_child(jobs, 'tog_and_dogs' if foreign else 'test_tenant_alpha')
    jobs[0][0]['REQ#r']['job_ids'] = [child['PK'].removeprefix('JOB#')]
    result = run_job()
    assert ('error' in result) == foreign
    jobs[1].assert_not_called()
    jobs[2].assert_not_called()
    jobs[0][2].assert_not_called()

@pytest.mark.parametrize('supplied', [False, True])
def test_single_job_inherits_only_persisted_event(jobs, supplied):
    request = jobs[0][0]['REQ#r']
    request.update(service_type='PET_SITTING')
    request.pop('visits_per_day')
    request.pop('visit_windows')
    fields = {'expected_company_id': request['company_id']}
    if supplied: fields['google_event_id'] = request['google_event_id']
    result = run_job(**fields)
    assert 'error' not in result
    assert jobs[1].call_args.args[0]['google_event_id'] == 'parent-event'
    jobs[0][2].assert_not_called()


def test_job_foreign_later_occurrence_denied_before_earlier_sync(jobs):
    existing_child(jobs)
    request = jobs[0][0]['REQ#r']
    request.update(visits_per_day=2, visit_windows=['MORNING', 'EVENING'])
    jid = str(uuid.uuid5(uuid.NAMESPACE_URL, 'togs-and-dogs:check-in:r:2026-09-20:EVENING'))
    jobs[0][0]['JOB#'+jid] = {'PK': 'JOB#'+jid, 'SK': 'REQ#r', 'company_id': 'tog_and_dogs'}
    assert 'error' in run_job(expected_company_id='test_tenant_alpha')
    jobs[0][2].assert_not_called()
    jobs[1].assert_not_called()
    jobs[2].assert_not_called()


def test_admin_completed_child_preserved(admin_world):
    populate(admin_world, 'test_tenant_alpha', True)
    admin_world[0]['JOB#j']['status'] = 'COMPLETED'
    admin_call('test_tenant_alpha')
    admin_world[3].assert_not_called()
