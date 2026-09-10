import json
from datetime import datetime, timezone
from unittest.mock import Mock
import pytest
from handlers import google_auth_handler as auth
from common import google_calendar as calendar
from common.calendar_metadata import get_tenant_calendar_config


def event(company='tog_and_dogs', path='/admin/auth/status'):
    return {'path': path, 'httpMethod': 'GET', 'requestContext': {'authorizer': {
        'claims': {'custom:company_id': company, 'cognito:groups': 'admin', 'sub': 'synthetic'}}}}


def body(result):
    return json.loads(result['body'])


@pytest.fixture
def passive(monkeypatch, primary_google_binding):
    sdk = Mock()
    sdk.get_secret_value.return_value = {'SecretString': '{}'}
    monkeypatch.setattr(auth, 'secrets', sdk)
    forbidden = Mock(side_effect=AssertionError('Passive operation attempted mutation/provider access'))
    monkeypatch.setattr(auth.urllib.request, 'urlopen', forbidden)
    monkeypatch.setattr(auth, 'get_google_config', forbidden)
    monkeypatch.setattr(auth, 'save_tokens', forbidden)
    monkeypatch.setattr(auth, '_mark_bound_auth_revoked', forbidden)
    monkeypatch.setattr(auth, '_save_bound_auth_tokens', forbidden)
    monkeypatch.setattr(calendar, '_mark_token_revoked', forbidden)
    yield sdk, forbidden
    sdk.put_secret_value.assert_not_called()
    forbidden.assert_not_called()


@pytest.mark.parametrize('company', [None, '', ' alpha ', 'Alpha', 7, {}, 'a/b'])
def test_invalid_tenant(passive, company):
    assert auth.get_status(event(company))['statusCode'] == 403
    passive[0].get_secret_value.assert_not_called()


def test_substitution(passive):
    request = event()
    request.update(body=json.dumps({'company_id': 'other_tenant'}),
                   queryStringParameters={'company_id': 'other_tenant'},
                   headers={'company_id': 'other_tenant'})
    assert body(auth.get_status(request))['status'] == 'NOT_CONNECTED'
    assert passive[0].get_secret_value.call_args.kwargs['SecretId'].endswith('/user-tokens-Ab1234')


def test_conflicting_claims(passive):
    request = event()
    request['requestContext']['authorizer']['jwt'] = {'claims': {'custom:company_id': 'other_tenant'}}
    assert auth.get_status(request)['statusCode'] == 403
    passive[0].get_secret_value.assert_not_called()


@pytest.mark.parametrize('tokens, expected', [
    ({}, 'NOT_CONNECTED'),
    ({'access_token': 'cached', 'refresh_token': 'cached', 'updated_at': datetime.now(timezone.utc).isoformat(), 'expires_in': 3600}, 'CONNECTED'),
    ({'access_token': 'cached', 'refresh_token': 'cached', 'updated_at': '2000-01-01T00:00:00Z'}, 'UNKNOWN'),
    ({'token_status': 'revoked'}, 'VALIDATION_FAILED'),
    ({'access_token': 'cached'}, 'UNKNOWN'),
    ([], 'UNKNOWN'),
])
def test_status_states(passive, tokens, expected):
    passive[0].get_secret_value.return_value = {'SecretString': json.dumps(tokens)}
    assert body(auth.get_status(event()))['status'] == expected


def test_no_binding(passive, monkeypatch):
    from common import db
    monkeypatch.setattr(db.table, 'get_item', Mock(return_value={'Item': {
        'PK': 'TENANT#test_tenant_alpha', 'SK': 'METADATA', 'company_id': 'test_tenant_alpha'}}))
    assert body(auth.get_status(event('test_tenant_alpha')))['status'] == 'NOT_CONNECTED'
    passive[0].get_secret_value.assert_not_called()


@pytest.mark.parametrize('failure', ['metadata', 'storage', 'ownership'])
def test_failures(passive, monkeypatch, failure):
    if failure == 'metadata':
        from common import db
        monkeypatch.setattr(db.table, 'get_item', Mock(side_effect=RuntimeError('private-marker')))
    elif failure == 'storage':
        passive[0].get_secret_value.side_effect = RuntimeError('private-marker')
    else:
        calendar.secrets.describe_secret.return_value['Tags'] = [{'Key': 'CompanyId', 'Value': 'foreign'}]
    result = auth.get_status(event())
    assert result['statusCode'] == (403 if failure == 'ownership' else 503)
    assert 'private-marker' not in result['body']


@pytest.mark.parametrize('unavailable', [False, True])
def test_tenant_info(passive, monkeypatch, unavailable):
    from handlers import admin_handler as admin
    from common import entitlement
    monkeypatch.setattr(admin, 'get_item', Mock(return_value={'company_id': 'tog_and_dogs', 'display_name': 'Synthetic'}))
    monkeypatch.setattr(entitlement, '_get_entitlement_safely', Mock(return_value=Mock(is_access_allowed=True, is_blocked=False)))
    if unavailable:
        passive[0].get_secret_value.side_effect = RuntimeError('private-marker')
    else:
        passive[0].get_secret_value.return_value = {'SecretString': '{"refresh_token":"cached"}'}
    result = admin.handler(event(path='/admin/tenant-info'), None)
    assert result['statusCode'] == 200
    assert body(result)['google_calendar_status'] == 'UNKNOWN'
    assert body(result)['calendar_connection_status'] == 'unknown'
    assert body(result)['display_name'] == 'Synthetic'


@pytest.mark.parametrize('status', [None, 'UNKNOWN', 'UNAVAILABLE'])
def test_composition(status):
    for record in ({'company_id': 'tog_and_dogs'}, {'company_id': 'tog_and_dogs', 'calendar_provider': 'google', 'calendar_connection_status': 'connected'}):
        assert get_tenant_calendar_config(record, google_status=status)['calendar_connection_status'] != 'connected'


def test_http_schedule_spoof(passive, monkeypatch):
    from common import entitlement
    monkeypatch.setattr(entitlement, 'require_active_tenant', Mock(return_value=None))
    request = event()
    request.update(source='aws.events', action='health_check')
    health = Mock(side_effect=AssertionError('HTTP selected scheduled health'))
    monkeypatch.setattr(auth, 'calendar_health_check', health)
    assert auth.handler(request, None)['statusCode'] == 200
    health.assert_not_called()


@pytest.mark.parametrize('saved', [True, False])
def test_active_schedule(primary_google_binding, monkeypatch, saved):
    from unittest.mock import MagicMock
    monkeypatch.setattr(auth, 'get_google_config', Mock(return_value={'client_id': 'fake', 'client_secret': 'fake'}))
    monkeypatch.setattr(auth, '_read_bound_auth_tokens', Mock(return_value={'refresh_token': 'fake'}))
    save = Mock(return_value=saved)
    monkeypatch.setattr(auth, '_save_bound_auth_tokens', save)
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"access_token":"fake"}'
    http = Mock(return_value=response)
    monkeypatch.setattr(auth.urllib.request, 'urlopen', http)
    result = auth.handler({'source': 'aws.events', 'action': 'health_check'}, None)
    assert result['status'] == ('CONNECTED' if saved else 'REFRESH_FAILED')
    http.assert_called_once()
    assert save.call_args.args[1] == 'arn:aws:secretsmanager:us-east-1:123456789012:secret:togs-and-dogs-prod/google/user-tokens-Ab1234'
    assert save.call_args.kwargs['require_unrevoked'] is True


def test_platform_summary(passive, monkeypatch):
    from handlers import platform_handler as platform
    monkeypatch.setattr(platform, 'get_item', Mock(return_value={'company_id': 'tog_and_dogs'}))
    monkeypatch.setattr(platform.table, 'query', Mock(return_value={'Items': []}))
    monkeypatch.setattr(platform.table, 'scan', Mock(return_value={'Items': []}))
    monkeypatch.setattr(platform, '_build_entitlement', Mock(return_value=Mock(to_dict=lambda: {})))
    status = Mock(side_effect=AssertionError('Platform used tenant status'))
    monkeypatch.setattr(auth, 'get_status', status)
    result = platform._handle_get_tenant(event('platform_tenant'), 'tog_and_dogs')
    assert result['statusCode'] == 200
    assert 'configured' in result['body']
    passive[0].get_secret_value.assert_not_called()
    status.assert_not_called()


@pytest.mark.parametrize('path', ['/admin/auth/status', '/admin/auth/google', '/admin/auth/health'])
def test_http_missing_tenant_dispatch(passive, path):
    assert auth.handler(event(None, path), None)['statusCode'] == 403
    passive[0].get_secret_value.assert_not_called()


def test_ambiguous_tags(passive):
    calendar.secrets.describe_secret.return_value['Tags'].append({'Key': 'companyid', 'Value': 'tog_and_dogs'})
    assert auth.get_status(event())['statusCode'] == 403
    passive[0].get_secret_value.assert_not_called()


def test_tenant_info_ownership_denial(passive, monkeypatch):
    from handlers import admin_handler as admin
    monkeypatch.setattr(admin, 'get_item', Mock(return_value={'company_id': 'foreign_tenant'}))
    assert admin.handler(event(path='/admin/tenant-info'), None)['statusCode'] == 403
    passive[0].get_secret_value.assert_not_called()


@pytest.mark.parametrize('lifetime', [float('inf'), float('nan'), True, '3600', -1])
def test_malformed_expiry(passive, lifetime):
    passive[0].get_secret_value.return_value = {'SecretString': json.dumps({
        'access_token': 'cached', 'refresh_token': 'cached',
        'updated_at': datetime.now(timezone.utc).isoformat(), 'expires_in': lifetime})}
    assert body(auth.get_status(event()))['status'] == 'UNKNOWN'


def test_http_health_denied(passive, monkeypatch):
    from common import entitlement
    monkeypatch.setattr(entitlement, 'require_active_tenant', Mock(return_value=None))
    assert auth.handler(event(path='/admin/auth/health'), None)['statusCode'] == 403


def test_malformed_token_json(passive):
    passive[0].get_secret_value.return_value = {'SecretString': 'invalid-json'}
    assert body(auth.get_status(event()))['status'] == 'UNKNOWN'
