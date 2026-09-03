"""S1 policy matrix and offline DynamoDB fixture shared by the handler tests.

Moto evaluates the real boto3 expressions over mixed, unfiltered input. This
avoids mocks that accidentally hide the original OR-untagged predicate defect.
"""
import copy
import json
from contextlib import ExitStack, contextmanager
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


@contextmanager
def s1_bounded_pages(table, status, evaluation_limit):
    """Exercise real filtering while emulating small database evaluation pages."""
    method = 'scan' if status == 'ALL' else 'query'
    original = getattr(table, method)
    pages = []

    def read(**kwargs):
        result = original(**dict(kwargs, Limit=min(kwargs['Limit'], evaluation_limit)))
        pages.append(copy.deepcopy(result))
        return result

    with patch.object(table, method, side_effect=read) as calls:
        yield calls, pages


def s1_ordered_rows(count, company='excluded-tenant-sensitive'):
    # Both the Moto table scan and descending StatusIndex query use this order.
    return [dict(s1_request(f'{i:03d}-sensitive', company, client='excluded-client-sensitive'),
                 created_at=f'2031-01-{count - i:02d}T00:00:00Z')
            for i in range(count)]


@pytest.mark.parametrize('company', TENANTS)
@pytest.mark.parametrize('status', ['ALL', 'PENDING_REVIEW', None])
@pytest.mark.parametrize('partial', [False, True], ids=['excluded-only', 'partial-authorized'])
def test_s1_cursor_cap_fails_closed_without_partial_success(
        s1_read_table, company, status, partial):
    from common.tenant_read_scope import MAX_TENANT_PAGE_READS
    from common.response import error
    assert MAX_TENANT_PAGE_READS == 16  # Documented S1-local safety boundary.
    rows = s1_ordered_rows(MAX_TENANT_PAGE_READS + 3)
    if partial:
        rows[0]['company_id'] = company
    rows[-1]['company_id'] = company  # Authorized data exists beyond the cap.
    s1_read_table.seed(rows)
    query = {'limit': '2' if partial else '1'}
    if status is not None:
        query['status'] = status
    event = s1_event(company, query=query)
    with s1_bounded_pages(s1_read_table.table, status, 2 if partial else 1) as (calls, pages):
        response = s1_read_table.handler(event, {})

    assert calls.call_count == MAX_TENANT_PAGE_READS
    assert bool(pages[0]['Items']) is partial
    assert pages[-1]['LastEvaluatedKey']  # Not database exhaustion.
    assert response == error(503, 'PAGINATION_TRAVERSAL_LIMIT_REACHED', event)
    body = json.loads(response['body'])
    assert set(body) == {'error'}  # No requests, cursor, counts or partial-success fields.
    serialized = json.dumps(response)
    for value in ('sensitive', company, 'PENDING_REVIEW', '2031-', 'LastEvaluatedKey',
                  'lastKey', 'nextToken', 'cursor', 'pageCount'):
        assert value not in serialized
    for row in rows:
        assert row['PK'] not in serialized
        assert row['request_id'] not in serialized
    assert all(call.kwargs['Limit'] == 1 for call in calls.call_args_list[1:]) if partial else True
    s1_read_table.audit.assert_not_called()


@pytest.mark.parametrize('status', ['ALL', 'PENDING_REVIEW', None])
@pytest.mark.parametrize('at_cap', [False, True], ids=['before-cap', 'on-cap'])
@pytest.mark.parametrize('authorized', [False, True], ids=['exhausted', 'later-authorized'])
def test_s1_cursor_exhaustion_or_safe_boundary_within_cap(
        s1_read_table, status, at_cap, authorized):
    from common.tenant_read_scope import MAX_TENANT_PAGE_READS
    count = MAX_TENANT_PAGE_READS if at_cap else 3
    rows = s1_ordered_rows(count + int(authorized))
    if authorized:
        rows[count - 1] = dict(s1_request(f'{count - 1:03d}-own', 'test_tenant_alpha'),
                               created_at=rows[count - 1]['created_at'])
    s1_read_table.seed(rows)
    query = {'limit': '1'}
    if status is not None:
        query['status'] = status
    with s1_bounded_pages(s1_read_table.table, status, 1) as (calls, pages):
        response = s1_read_table.handler(s1_event('test_tenant_alpha', query=query), {})
    assert calls.call_count == count
    assert response['statusCode'] == 200
    assert 'sensitive' not in json.dumps(response)
    body = json.loads(response['body'])
    if authorized:
        assert [row['request_id'] for row in body['requests']] == [f'{count - 1:03d}-own']
        fields = ('PK', 'SK') if status == 'ALL' else ('PK', 'SK', 'status', 'created_at')
        cursor = json.loads(body['lastKey'])
        assert cursor == {field: body['requests'][-1][field] for field in fields}
        assert cursor == pages[-1]['LastEvaluatedKey']
    else:
        assert body == {'requests': [], 'lastKey': None}
    s1_read_table.audit.assert_not_called()


@pytest.mark.parametrize('company', TENANTS)
@pytest.mark.parametrize('status', ['ALL', 'PENDING_REVIEW', None])
def test_s1_cursor_safe_continuation_has_no_skips_duplicates_or_hidden_metadata(
        s1_read_table, company, status):
    rows = s1_ordered_rows(9)
    for i in (0, 3, 6):
        rows[i] = dict(s1_request(f'{i:03d}-own', company), created_at=rows[i]['created_at'])
    if company == 'tog_and_dogs':
        # This absent-company row is authorized, including its continuation keys.
        del rows[3]['company_id']
    s1_read_table.seed(rows)
    query = {'limit': '2'}
    if status is not None:
        query['status'] = status
    seen, cursors = [], []
    with s1_bounded_pages(s1_read_table.table, status, 2) as (calls, pages):
        for _ in range(5):
            before = calls.call_count
            response = s1_read_table.handler(s1_event(company, query=query), {})
            assert response['statusCode'] == 200
            assert 'sensitive' not in json.dumps(response)
            body = json.loads(response['body'])
            assert len(body['requests']) <= 2
            seen.extend(row['request_id'] for row in body['requests'])
            assert calls.call_count - before <= 16
            if body['lastKey'] is None:
                break
            cursor = json.loads(body['lastKey'])
            fields = ('PK', 'SK') if status == 'ALL' else ('PK', 'SK', 'status', 'created_at')
            assert cursor == {field: body['requests'][-1][field] for field in fields}
            assert cursor == pages[-1]['LastEvaluatedKey']
            assert cursor not in cursors
            cursors.append(cursor)
            query['startKey'] = body['lastKey']
        else:
            pytest.fail('Confidential pagination did not terminate')
    assert seen == ['000-own', '003-own', '006-own']
    assert len(cursors) >= 1
    assert calls.call_args_list[0].kwargs['Limit'] == (1000 if status == 'ALL' else 2)
    assert all(call.kwargs['FilterExpression'] == calls.call_args_list[0].kwargs['FilterExpression']
               for call in calls.call_args_list)
    s1_read_table.audit.assert_not_called()


@pytest.mark.parametrize('company', TENANTS)
@pytest.mark.parametrize('status', ['ALL', 'PENDING_REVIEW'])
def test_s1_cursor_null_empty_malformed_and_wrong_company_are_never_observable(
        s1_read_table, company, status):
    associations = [None, '', ' ', f' {company}', f'{company} ', 7, False,
                    [company], {'id': company}, 'wrong-tenant-sensitive']
    rows = s1_ordered_rows(len(associations) + 1)
    for row, association in zip(rows, associations):
        row['company_id'] = association
    rows[-1] = s1_request('z-own', company)
    s1_read_table.seed(rows)
    with s1_bounded_pages(s1_read_table.table, status, 1) as (calls, _):
        response = s1_read_table.handler(s1_event(company, query={'status': status, 'limit': '1'}), {})
    assert calls.call_count == len(rows)
    assert response['statusCode'] == 200
    serialized = json.dumps(response)
    for value in ('sensitive', '2031-', 'wrong-tenant'):
        assert value not in serialized
    assert [row['request_id'] for row in json.loads(response['body'])['requests']] == ['z-own']
    s1_read_table.audit.assert_not_called()


@pytest.mark.parametrize('status', ['ALL', 'PENDING_REVIEW'])
@pytest.mark.parametrize('boundary', ['repeated', 'cycle', 'extra-field', 'missing-field'])
def test_s1_cursor_stalled_or_invalid_boundary_fails_closed(s1_read_table, status, boundary):
    from common.response import error
    fields = ('PK', 'SK') if status == 'ALL' else ('PK', 'SK', 'status', 'created_at')
    row = s1_request('excluded-sensitive', 'wrong-tenant', client='excluded-client-sensitive')
    key = {field: row[field] for field in fields}
    second = dict(key, PK='REQ#another-excluded-sensitive')
    keys = [key, key]
    if boundary == 'cycle':
        keys = [key, second, key]
    elif boundary == 'extra-field':
        keys = [dict(key, private_field='excluded-sensitive')]
    elif boundary == 'missing-field':
        keys = [{field: value for field, value in key.items() if field != 'SK'}]
    event = s1_event('test_tenant_alpha', query={'status': status, 'limit': '1'})
    method = 'scan' if status == 'ALL' else 'query'
    with patch.object(s1_read_table.table, method,
                      side_effect=[{'Items': [], 'LastEvaluatedKey': k} for k in keys]) as calls:
        response = s1_read_table.handler(event, {})
    assert calls.call_count == len(keys)
    assert response == error(503, 'PAGINATION_TRAVERSAL_LIMIT_REACHED', event)
    assert 'sensitive' not in json.dumps(response)
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


@pytest.mark.parametrize('company', ['test_tenant_alpha', 'future_tenant'])
@pytest.mark.parametrize('status', ['ALL', 'PENDING_REVIEW'])
@pytest.mark.parametrize('association', ['tog_and_dogs', MISSING],
                         ids=['tagged-primary', 'untagged-legacy'])
@pytest.mark.parametrize('has_later_own_record', [False, True],
                         ids=['excluded-only', 'later-authorized'])
def test_s1_cursor_response_confidentiality(
        s1_read_table, company, status, association, has_later_own_record):
    """An excluded record must not reappear as response continuation metadata."""
    excluded = s1_request('a-excluded-sensitive', association,
                          client='excluded-client-sensitive')
    excluded['created_at'] = '2031-01-01T00:00:00Z'
    rows = [excluded, dict(excluded, PK='REQ#b-excluded-sensitive-tail',
                           request_id='b-excluded-sensitive-tail',
                           created_at='2030-12-31T00:00:00Z')]
    if has_later_own_record:
        rows.append(s1_request('z-own-visible', company))
    s1_read_table.seed(rows)

    original_scan = s1_read_table.table.scan
    with patch.object(s1_read_table.table, 'scan', side_effect=lambda **kw: original_scan(
            **dict(kw, Limit=1))):
        response = s1_read_table.handler(s1_event(company, query={
            'status': status, 'limit': '1',
        }), {})

    assert response['statusCode'] == 200
    serialized_response = json.dumps(response)
    for excluded_value in ('a-excluded-sensitive', 'excluded-client-sensitive',
                           '2031-01-01T00:00:00Z'):
        assert excluded_value not in serialized_response
    body = json.loads(response['body'])
    expected = {'z-own-visible'} if has_later_own_record else set()
    assert {item['request_id'] for item in body['requests']} == expected
    if not has_later_own_record:
        assert body['lastKey'] is None
    s1_read_table.audit.assert_not_called()


@pytest.mark.parametrize('company', ['test_tenant_alpha', 'future_tenant'])
@pytest.mark.parametrize('status', ['ALL', 'PENDING_REVIEW'])
@pytest.mark.parametrize('association', ['tog_and_dogs', MISSING],
                         ids=['tagged-primary', 'untagged-legacy'])
def test_s1_cursor_response_confidentiality_on_mixed_page(
        s1_read_table, company, status, association):
    """A nonempty filtered page can still end on an excluded evaluated key."""
    first = s1_request('a-own-visible', company)
    first['created_at'] = '2032-01-01T00:00:00Z'
    excluded = s1_request('b-excluded-sensitive', association,
                          client='excluded-client-sensitive')
    excluded['created_at'] = '2031-01-01T00:00:00Z'
    s1_read_table.seed([first, excluded, s1_request('z-own-visible', company)])

    original_scan = s1_read_table.table.scan
    with patch.object(s1_read_table.table, 'scan', side_effect=lambda **kw: original_scan(
            **dict(kw, Limit=2))):
        response = s1_read_table.handler(s1_event(company, query={
            'status': status, 'limit': '2',
        }), {})

    assert response['statusCode'] == 200
    serialized_response = json.dumps(response)
    for excluded_value in ('b-excluded-sensitive', 'excluded-client-sensitive',
                           '2031-01-01T00:00:00Z'):
        assert excluded_value not in serialized_response
    body = json.loads(response['body'])
    assert 'a-own-visible' in {item['request_id'] for item in body['requests']}
    s1_read_table.audit.assert_not_called()
