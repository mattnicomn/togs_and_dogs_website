"""S1 policy matrix and offline DynamoDB fixture shared by the handler tests.

Moto evaluates the real boto3 expressions over mixed, unfiltered input. This
avoids mocks that accidentally hide the original OR-untagged predicate defect.
"""
import copy
import json
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws


TENANTS = ('tog_and_dogs', 'test_tenant_alpha', 'future_tenant')
MISSING = object()


def s1_request(key, company=MISSING, client='shared-client', status='PENDING_REVIEW'):
    record = {
        'PK': f'REQ#{key}', 'SK': f'CLIENT#{client}',
        'request_id': key, 'client_id': client, 'entity_type': 'REQUEST',
        'status': status, 'created_at': '2030-01-01T00:00:00Z',
        'start_date': '2030-01-01',
    }
    if company is not MISSING:
        record['company_id'] = company
    return record


def s1_event(company, path='/admin/requests', role='admin', query=None):
    return {
        'httpMethod': 'GET', 'path': path, 'pathParameters': {},
        'queryStringParameters': query or {},
        'requestContext': {'authorizer': {'claims': {
            'sub': 's1-client-sub', 'email': 's1-user@example.test',
            'email_verified': 'true', 'cognito:groups': role,
            'custom:company_id': company,
        }}},
    }


@pytest.fixture
def s1_read_table(monkeypatch):
    """Real in-memory filter/pagination semantics; all side effects trip guards."""
    monkeypatch.setenv('TENANT_RESOLUTION_MODE', 'multi')
    with mock_aws():
        table = boto3.resource('dynamodb', region_name='us-east-1').create_table(
            TableName='s1-read-isolation',
            KeySchema=[{'AttributeName': 'PK', 'KeyType': 'HASH'},
                       {'AttributeName': 'SK', 'KeyType': 'RANGE'}],
            AttributeDefinitions=[{'AttributeName': key, 'AttributeType': 'S'}
                                  for key in ('PK', 'SK', 'status', 'created_at')],
            GlobalSecondaryIndexes=[{
                'IndexName': 'StatusIndex',
                'KeySchema': [{'AttributeName': 'status', 'KeyType': 'HASH'},
                              {'AttributeName': 'created_at', 'KeyType': 'RANGE'}],
                'Projection': {'ProjectionType': 'ALL'},
            }],
            BillingMode='PAY_PER_REQUEST',
        )
        from handlers import admin_handler
        original_put = table.put_item

        def seed(records):
            for record in records:
                original_put(Item=copy.deepcopy(record))

        with ExitStack() as stack:
            stack.enter_context(patch('common.db.table', table))
            stack.enter_context(patch.object(admin_handler, 'table', table))
            # S1 isolates reads; availability/feature policy is not under test.
            stack.enter_context(patch('common.entitlement.require_active_tenant', return_value=None))
            stack.enter_context(patch('common.entitlement.check_feature'))
            audit = stack.enter_context(patch.object(admin_handler, 'log_action'))
            guards = [stack.enter_context(patch.object(table, method))
                      for method in ('put_item', 'update_item', 'delete_item', 'batch_writer')]
            guards += [stack.enter_context(patch(target)) for target in (
                'handlers.admin_handler.notify_event',
                'handlers.admin_handler.sync_calendar_event',
                'handlers.admin_handler.delete_event',
                'boto3.client', 'common.db.put_item', 'common.db.update_item',
            )]
            for guard in guards:
                guard.side_effect = AssertionError('S1 read attempted a side effect')
            yield SimpleNamespace(table=table, seed=seed, audit=audit,
                                  handler=admin_handler.handler)
            for guard in guards:
                guard.assert_not_called()


@pytest.mark.parametrize('company', TENANTS)
@pytest.mark.parametrize('allow_legacy', [False, True])
def test_s1_policy_evaluates_tagged_absent_null_and_malformed(s1_read_table, company, allow_legacy):
    from common.tenant_read_scope import build_tenant_read_filter
    records = [s1_request('matching', company), s1_request('wrong', 'other_tenant'),
               s1_request('absent')]
    records += [s1_request(f'invalid-{i}', value) for i, value in enumerate(
        [None, '', ' ', f' {company}', f'{company} ', 7, False, [company], {'id': company}])]
    s1_read_table.seed(records)
    condition = build_tenant_read_filter(company, allow_primary_legacy=allow_legacy)
    result = s1_read_table.table.scan(FilterExpression=condition)['Items']
    expected = {'matching'}
    if company == 'tog_and_dogs' and allow_legacy:
        expected.add('absent')
    assert {item['request_id'] for item in result} == expected
    s1_read_table.audit.assert_not_called()


@pytest.mark.parametrize('invalid_company', [None, '', ' ', ' padded ', 7, False, [], {}])
def test_s1_invalid_resolved_company_matches_nothing(s1_read_table, invalid_company):
    from common.tenant_read_scope import build_tenant_read_filter
    s1_read_table.seed([s1_request('primary', 'tog_and_dogs'), s1_request('absent'),
                        s1_request('invalid', invalid_company)])
    condition = build_tenant_read_filter(invalid_company, allow_primary_legacy=True)
    assert s1_read_table.table.scan(FilterExpression=condition)['Items'] == []


def test_s1_legacy_tenant_is_not_configurable_or_role_selected(s1_read_table, monkeypatch):
    from common.tenant_read_scope import build_tenant_read_filter
    monkeypatch.setenv('DEFAULT_COMPANY_ID', 'test_tenant_alpha')
    s1_read_table.seed([s1_request('legacy')])
    assert s1_read_table.table.scan(FilterExpression=build_tenant_read_filter(
        'test_tenant_alpha', allow_primary_legacy=True))['Items'] == []


@pytest.mark.parametrize('company', TENANTS)
def test_s1_client_requests_use_real_tenant_bound_identity_and_record_scope(s1_read_table, company):
    # Same client_id may exist in different COMPANY partitions; no global unique
    # constraint binds every request with that ID to the caller's company.
    profiles = [{'PK': f'COMPANY#{tenant}', 'SK': 'CLIENT#shared-client',
                 'client_id': 'shared-client', 'company_id': tenant,
                 'cognito_sub': 's1-client-sub', 'is_active': True}
                for tenant in TENANTS]
    s1_read_table.seed(profiles + [
        s1_request('own', company), s1_request('wrong-tenant', 'other_tenant'),
        s1_request('legacy'), s1_request('null', None),
        s1_request('wrong-client', company, client='different-client'),
    ])
    response = s1_read_table.handler(s1_event(company, '/client/requests', 'client'), {})
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    expected = {'own', 'legacy'} if company == 'tog_and_dogs' else {'own'}
    assert {item['request_id'] for item in body['requests']} == expected
    assert body['lastKey'] is None  # Preserve the existing unpaginated contract.
    s1_read_table.audit.assert_not_called()


@pytest.mark.parametrize('path,query', [('/admin/requests', {'status': 'ALL'}),
                                      ('/admin/requests', {}),
                                      ('/admin/export-data', {})])
def test_s1_platform_only_role_gets_no_legacy_tenant_access(s1_read_table, path, query):
    s1_read_table.seed([s1_request('legacy')])
    response = s1_read_table.handler(s1_event('tog_and_dogs', path, 'platform_admin', query), {})
    assert response['statusCode'] == 403
    s1_read_table.audit.assert_not_called()


def test_s1_platform_control_plane_keeps_explicit_target_without_read_scope_helper(s1_read_table):
    from handlers.platform_handler import handler
    with patch('common.tenant_read_scope.build_tenant_read_filter', side_effect=AssertionError), \
         patch('handlers.platform_handler._handle_get_tenant', return_value={'statusCode': 200}) as read:
        event = s1_event('tog_and_dogs', '/platform/tenants/test_tenant_alpha', 'platform_admin')
        event['pathParameters'] = {'company_id': 'test_tenant_alpha'}
        assert handler(event, {})['statusCode'] == 200
        read.assert_called_once_with(event, 'test_tenant_alpha')


@pytest.mark.parametrize('path,query', [('/admin/requests', {'status': 'ALL'}),
                                      ('/admin/requests', {'status': 'PENDING_REVIEW'}),
                                      ('/client/requests', {})])
def test_s1_exclusion_only_reads_have_no_audit_or_side_effects(s1_read_table, path, query):
    s1_read_table.seed([s1_request('legacy'), s1_request('primary', 'tog_and_dogs'),
                        {'PK': 'COMPANY#test_tenant_alpha', 'SK': 'CLIENT#shared-client',
                         'client_id': 'shared-client', 'cognito_sub': 's1-client-sub'}])
    role = 'client' if path.startswith('/client/') else 'admin'
    response = s1_read_table.handler(s1_event('test_tenant_alpha', path, role, query), {})
    assert response['statusCode'] == 200
    assert json.loads(response['body'])['requests'] == []
    s1_read_table.audit.assert_not_called()


@pytest.mark.parametrize('role', ['owner', 'admin', 'staff', 'client'])
def test_s1_all_list_preserves_role_identity_and_terminal_filters(s1_read_table, role):
    own = s1_request('own', 'test_tenant_alpha')
    own.update(worker_id='s1-user@example.test', client_email='s1-user@example.test')
    other_identity = dict(own, PK='REQ#other-identity', request_id='other-identity',
                          worker_id='other@example.test', client_email='other@example.test')
    records = [own, other_identity,
               dict(own, PK='REQ#wrong-tenant', company_id='tog_and_dogs'),
               dict(own, PK='REQ#deleted', status='DELETED'),
               dict(own, PK='REQ#archived', status='ARCHIVED'),
               dict(own, PK='JOB#child', entity_type='JOB')]
    s1_read_table.seed(records)
    event = s1_event('test_tenant_alpha', role=role, query={
        'status': 'ALL', 'company_id': 'tog_and_dogs', 'allow_primary_legacy': 'true',
    })
    response = s1_read_table.handler(event, {})
    assert response['statusCode'] == 200
    expected = {'own', 'other-identity'} if role in ('owner', 'admin') else {'own'}
    assert {item['request_id'] for item in json.loads(response['body'])['requests']} == expected
    s1_read_table.audit.assert_not_called()
