"""S2B.3 offline bound-token operations and disconnect policy."""
import json
import io
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock
import urllib.error
import pytest
from handlers import google_auth_handler as auth
from common import google_calendar as calendar

PRIMARY = 'togs-and-dogs-prod/google/user-tokens'
NAME = 'opaque/alpha-tokens'
def arn(name):
    return 'arn:aws:secretsmanager:us-east-1:123456789012:secret:' + name + '-Ab1234'


def event(company='test_tenant_alpha'):
    return {'path': '/admin/auth/google', 'httpMethod': 'DELETE', 'requestContext': {'authorizer': {
        'claims': {'custom:company_id': company, 'cognito:groups': 'admin'}}}}


@pytest.fixture
def rig(monkeypatch):
    monkeypatch.setenv('GOOGLE_USER_TOKENS_NAME', PRIMARY)
    r = SimpleNamespace(company='test_tenant_alpha', name=NAME, owner='test_tenant_alpha', missing=False, extra_tags=[])
    def metadata(**kw):
        assert kw['ConsistentRead'] is True
        if r.missing:
            return {}
        return {'Item': {'PK': 'TENANT#' + r.company, 'SK': 'METADATA', 'company_id': r.company,
                         'calendar_secret_ref': r.name}}
    r.get = Mock(side_effect=metadata)
    monkeypatch.setattr(auth.table, 'get_item', r.get)
    r.meta = Mock()
    r.meta.meta.region_name = 'us-east-1'
    def describe(SecretId):
        name = PRIMARY if SecretId == arn(PRIMARY) else SecretId
        return {'ARN': arn(name), 'Name': name, 'Tags': [{'Key': 'CompanyId', 'Value': r.owner}] + r.extra_tags}
    r.meta.describe_secret.side_effect = describe
    monkeypatch.setattr(calendar, 'secrets', r.meta)
    r.sdk = Mock()
    r.sdk.get_secret_value.return_value = {'SecretString': '{"refresh_token":"synthetic-refresh"}'}
    monkeypatch.setattr(auth, 'secrets', r.sdk)
    r.http = Mock(side_effect=AssertionError('Unexpected provider request'))
    monkeypatch.setattr(auth.urllib.request, 'urlopen', r.http)
    r.config = Mock(return_value={'client_id': 'synthetic', 'client_secret': 'synthetic'})
    monkeypatch.setattr(auth, 'get_google_config', r.config)
    return r


def test_read_canonical_once(rig):
    assert auth.get_stored_tokens(rig.company) == {'refresh_token': 'synthetic-refresh'}
    rig.sdk.get_secret_value.assert_called_once_with(SecretId=arn(NAME))
    rig.meta.describe_secret.assert_called_once_with(SecretId=NAME)
    rig.get.assert_called_once()


def test_save_merge_and_drift(rig):
    def read(SecretId):
        assert SecretId == arn(NAME)
        rig.name = 'other/binding'
        return {'SecretString': '{"refresh_token":"preserved"}'}
    rig.sdk.get_secret_value.side_effect = read
    assert auth.save_tokens({'access_token': 'new'}, rig.company) is True
    assert rig.sdk.put_secret_value.call_args.kwargs['SecretId'] == arn(NAME)
    saved = json.loads(rig.sdk.put_secret_value.call_args.kwargs['SecretString'])
    assert saved['refresh_token'] == 'preserved' and saved['access_token'] == 'new'
    rig.get.assert_called_once()
    rig.meta.describe_secret.assert_called_once()


@pytest.mark.parametrize('reason', ['owner', 'ambiguous', 'missing'])
@pytest.mark.parametrize('operation', ['read', 'save', 'disconnect'])
def test_denial_before_values(rig, reason, operation):
    if reason == 'owner':
        rig.owner = 'foreign'
    elif reason == 'ambiguous':
        rig.extra_tags = [{'Key': 'companyid', 'Value': rig.company}]
    else:
        rig.missing = True
    if operation == 'disconnect':
        assert auth.disconnect_auth(event())['statusCode'] == 403
    else:
        with pytest.raises(calendar.ProviderBindingError):
            if operation == 'read':
                auth.get_stored_tokens(rig.company)
            else:
                auth.save_tokens({'access_token': 'new'}, rig.company)
    rig.sdk.get_secret_value.assert_not_called()
    rig.sdk.put_secret_value.assert_not_called()


@pytest.mark.parametrize('failure', ['read', 'write', 'malformed'])
def test_save_failure(rig, failure):
    if failure == 'read':
        rig.sdk.get_secret_value.side_effect = RuntimeError('private')
    elif failure == 'write':
        rig.sdk.put_secret_value.side_effect = RuntimeError('private')
    else:
        rig.sdk.get_secret_value.return_value = {'SecretString': '[]'}
    assert auth.save_tokens({'access_token': 'new'}, rig.company) is False
    if failure != 'write':
        rig.sdk.put_secret_value.assert_not_called()


def test_unrelated_save_preserves_revocation(rig):
    rig.sdk.get_secret_value.return_value = {'SecretString': json.dumps({
        'token_status': 'revoked', 'revoked_at': 'old', 'revoked_reason': 'invalid_grant', 'refresh_token': 'old'})}
    assert auth.save_tokens({'access_token': 'new', 'token_status': None}, rig.company)
    saved = json.loads(rig.sdk.put_secret_value.call_args.kwargs['SecretString'])
    assert saved['token_status'] == 'revoked'
    assert saved['revoked_at'] == 'old' and saved['revoked_reason'] == 'invalid_grant'


@pytest.mark.parametrize('configured_as_arn,reference_as_arn', [(False, False), (True, False), (True, True)])
def test_protected_primary(rig, monkeypatch, configured_as_arn, reference_as_arn):
    rig.company = rig.owner = 'tog_and_dogs'
    rig.name = arn(PRIMARY) if reference_as_arn else PRIMARY
    monkeypatch.setenv('GOOGLE_USER_TOKENS_NAME', arn(PRIMARY) if configured_as_arn else PRIMARY)
    response = auth.disconnect_auth(event('tog_and_dogs'))
    assert response['statusCode'] == 409
    assert json.loads(response['body']) == {'error': 'PROVIDER_DISCONNECT_PROTECTED'}
    rig.sdk.get_secret_value.assert_not_called()
    rig.sdk.put_secret_value.assert_not_called()
    rig.meta.describe_secret.assert_called_once()


@pytest.mark.parametrize('fails', [False, True])
def test_permitted_disconnect_single_write(rig, fails):
    if fails:
        rig.sdk.put_secret_value.side_effect = RuntimeError('private-marker')
    result = auth.disconnect_auth(event())
    assert result['statusCode'] == (503 if fails else 200)
    assert 'private-marker' not in result['body']
    rig.sdk.put_secret_value.assert_called_once()
    kwargs = rig.sdk.put_secret_value.call_args.kwargs
    assert kwargs['SecretId'] == arn(NAME)
    cleared = json.loads(kwargs['SecretString'])
    assert cleared['token_status'] == 'revoked' and cleared['revoked_reason'] == 'admin_disconnect'
    assert 'access_token' not in cleared and 'refresh_token' not in cleared
    rig.sdk.get_secret_value.assert_not_called()
    rig.meta.describe_secret.assert_called_once()


def setup_health(rig):
    rig.company = rig.owner = 'tog_and_dogs'
    rig.name = PRIMARY
    return {'source': 'aws.events', 'action': 'health_check'}


@pytest.mark.parametrize('fail_save', [False, True])
def test_health_pinned_refresh(rig, fail_save):
    request = setup_health(rig)
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"access_token":"new","expires_in":3600}'
    def exchange(*args, **kwargs):
        rig.name = 'drift/after-validation'
        return response
    rig.http.side_effect = exchange
    if fail_save:
        rig.sdk.put_secret_value.side_effect = RuntimeError('private')
    result = auth.calendar_health_check(request)
    assert result['status'] == ('REFRESH_FAILED' if fail_save else 'CONNECTED')
    assert rig.sdk.put_secret_value.call_args.kwargs['SecretId'] == arn(PRIMARY)
    assert all(c.kwargs['SecretId'] == arn(PRIMARY) for c in rig.sdk.get_secret_value.call_args_list)
    rig.meta.describe_secret.assert_called_once()
    rig.get.assert_called_once()


@pytest.mark.parametrize('fail_save', [False, True])
def test_health_revocation_pinned(rig, fail_save):
    request = setup_health(rig)
    rig.sdk.get_secret_value.return_value = {'SecretString': '{"refresh_token":"keep","access_token":"remove","expires_in":3600}'}
    def exchange(*args, **kwargs):
        rig.name = 'drift/after-validation'
        raise urllib.error.HTTPError('https://example.invalid', 400, 'synthetic', {}, io.BytesIO(b'{"error":"invalid_grant"}'))
    rig.http.side_effect = exchange
    if fail_save:
        rig.sdk.put_secret_value.side_effect = RuntimeError('private')
    result = auth.calendar_health_check(request)
    assert result['status'] == ('REFRESH_FAILED' if fail_save else 'TOKEN_REVOKED')
    kwargs = rig.sdk.put_secret_value.call_args.kwargs
    assert kwargs['SecretId'] == arn(PRIMARY)
    saved = json.loads(kwargs['SecretString'])
    assert saved['refresh_token'] == 'keep' and saved['token_status'] == 'revoked'
    assert 'access_token' not in saved and 'expires_in' not in saved
    rig.meta.describe_secret.assert_called_once()


def test_revocation_read_failure_no_write(rig):
    request = setup_health(rig)
    rig.sdk.get_secret_value.side_effect = [{'SecretString': '{"refresh_token":"cached"}'}, RuntimeError('private')]
    rig.http.side_effect = urllib.error.HTTPError('https://example.invalid', 400, 'synthetic', {}, io.BytesIO(b'{"error":"invalid_grant"}'))
    assert auth.calendar_health_check(request)['status'] == 'REFRESH_FAILED'
    rig.sdk.put_secret_value.assert_not_called()


def test_reconnect_clears_revocation(rig):
    rig.sdk.get_secret_value.return_value = {'SecretString': '{"token_status":"revoked","revoked_at":"old","revoked_reason":"old","refresh_token":"keep"}'}
    auth._persist_oauth_tokens({'company_id': rig.company, 'provider_secret_arn': arn(NAME)},
                              {'access_token': 'new', 'expires_in': 3600})
    saved = json.loads(rig.sdk.put_secret_value.call_args.kwargs['SecretString'])
    assert not {'token_status', 'revoked_at', 'revoked_reason'} & saved.keys()
    assert saved['refresh_token'] == 'keep'


def test_passive_status(rig):
    result = auth.get_status(event())
    assert json.loads(result['body'])['status'] == 'UNKNOWN'
    rig.http.assert_not_called()
    rig.config.assert_not_called()
    rig.sdk.put_secret_value.assert_not_called()


def test_missing_tenant_no_fallback(rig):
    with pytest.raises(PermissionError):
        auth.get_stored_tokens()
    with pytest.raises(PermissionError):
        auth.save_tokens({})
    rig.meta.describe_secret.assert_not_called()

@pytest.mark.parametrize('saved', [False, True])
def test_common_refresh_requires_persistence(rig, monkeypatch, capsys, saved):
    monkeypatch.setattr(calendar, '_get_google_config', Mock(return_value={'client_id': 'fake', 'client_secret': 'fake'}))
    save = Mock(return_value=saved)
    monkeypatch.setattr(calendar, '_save_bound_tokens', save)
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"access_token":"new","expires_in":3600}'
    rig.http.side_effect = None
    rig.http.return_value = response
    result = calendar._refresh_access_token({'refresh_token': 'synthetic'}, company_id=rig.company)
    assert result == ('new' if saved else None)
    save.assert_called_once_with({'access_token': 'new', 'expires_in': 3600}, arn(NAME))
    rig.meta.describe_secret.assert_called_once()
    if not saved:
        assert 'SUCCESS:' not in capsys.readouterr().out


def test_health_concurrent_revocation_stops_success(rig):
    request = setup_health(rig)
    rig.sdk.get_secret_value.side_effect = [
        {'SecretString': '{"refresh_token":"cached"}'},
        {'SecretString': '{"refresh_token":"cached","token_status":"revoked"}'}]
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"access_token":"new","expires_in":3600}'
    rig.http.side_effect = None
    rig.http.return_value = response
    assert auth.calendar_health_check(request)['status'] == 'REFRESH_FAILED'
    rig.sdk.put_secret_value.assert_not_called()
