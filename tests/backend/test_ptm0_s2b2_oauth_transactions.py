"""Offline S2B.2 transaction contract, including atomic conditional-write races."""
import copy
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
from botocore.exceptions import ClientError
from handlers import google_auth_handler as auth
from common import google_calendar as calendar

STATE = '11111111-1111-4111-8111-111111111111'
NAME = 'togs-and-dogs-prod/google/user-tokens'
ARN = 'arn:aws:secretsmanager:us-east-1:123456789012:secret:' + NAME + '-Ab1234'


def event(callback=False, principal='synthetic-sub', origin=None):
    result = {'path': '/admin/auth/callback' if callback else '/admin/auth/google', 'httpMethod': 'GET',
              'requestContext': {'authorizer': {'claims': {'custom:company_id': 'tog_and_dogs',
                                 'sub': principal, 'cognito:groups': 'admin'}}}}
    if callback:
        result['requestContext'] = {}  # Public callback has no authenticated tenant.
        result['queryStringParameters'] = {'state': STATE, 'code': 'synthetic-code'}
    if origin:
        result['headers'] = {'origin': origin}
    return result


def transaction():
    now = int(time.time())
    return {'PK': 'OAUTHSTATE#' + STATE, 'SK': 'META', 'schema_version': 'v2',
            'company_id': 'tog_and_dogs', 'initiating_principal': 'synthetic-sub',
            'provider_secret_arn': ARN, 'redirect_uri': auth._OAUTH_PROD_REDIRECT,
            'post_auth_destination': auth._OAUTH_PROD_DESTINATION,
            'created_at': now, 'expires_at': now + 600, 'status': 'PENDING'}


def conditional_failure():
    return ClientError({'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'synthetic'}}, 'UpdateItem')


@pytest.fixture
def rig(monkeypatch):
    monkeypatch.setenv('GOOGLE_USER_TOKENS_NAME', NAME)
    monkeypatch.setenv('ENTITLEMENT_ENFORCEMENT_ENABLED', 'false')
    row = {'PK': 'TENANT#tog_and_dogs', 'SK': 'METADATA', 'company_id': 'tog_and_dogs',
           'is_active': True, 'subscription_status': 'active', 'calendar_enabled': True,
           'calendar_provider': 'google'}
    r = SimpleNamespace(record=transaction(), tenant=row, barrier=None, lock=threading.Lock())
    def get(**kw):
        assert kw['ConsistentRead'] is True
        if kw['Key']['PK'].startswith('OAUTHSTATE#'):
            result = copy.deepcopy(r.record) if kw['Key']['PK'] == 'OAUTHSTATE#' + STATE else None
            if r.barrier:
                r.barrier.wait(timeout=5)
            return {'Item': result} if result else {}
        return {'Item': copy.deepcopy(r.tenant)} if r.tenant else {}
    def put(**kw):
        assert kw['ConditionExpression'] == 'attribute_not_exists(PK) AND attribute_not_exists(SK)'
        with r.lock:
            if r.record is not None:
                raise conditional_failure()
            r.record = copy.deepcopy(kw['Item'])
    def update(**kw):
        # Model the actual generated condition, including every equality guard.
        expression = kw['ConditionExpression']
        assert expression.startswith('attribute_exists(PK) AND attribute_exists(SK) AND #expires_at > :now AND ')
        assert kw['UpdateExpression'] == 'SET #status = :consumed'
        names, values = kw['ExpressionAttributeNames'], kw['ExpressionAttributeValues']
        assert values[':status'] == 'PENDING' and values[':schema_version'] == 'v2'
        with r.lock:
            valid = bool(r.record and r.record['PK'] == kw['Key']['PK'] and r.record['SK'] == kw['Key']['SK'])
            valid = valid and r.record['expires_at'] > values[':now']
            for equality in expression.split(' AND ')[3:]:
                key, val = equality.split(' = ')
                valid = valid and r.record.get(names[key]) == values[val]
            if not valid:
                raise conditional_failure()
            r.record['status'] = values[':consumed']
    r.get = Mock(side_effect=get)
    r.put = Mock(side_effect=put)
    r.update = Mock(side_effect=update)
    monkeypatch.setattr(auth.table, 'get_item', r.get)
    monkeypatch.setattr(auth.table, 'put_item', r.put)
    monkeypatch.setattr(auth.table, 'update_item', r.update)
    r.delete = Mock(side_effect=AssertionError('No unconditional delete'))
    monkeypatch.setattr(auth.table, 'delete_item', r.delete)
    metadata = Mock()
    metadata.meta.region_name = 'us-east-1'
    metadata.describe_secret.return_value = {'Name': NAME, 'ARN': ARN, 'Tags': [{'Key': 'CompanyId', 'Value': 'tog_and_dogs'}]}
    monkeypatch.setattr(calendar, 'secrets', metadata)
    r.metadata = metadata
    r.secrets = Mock()
    r.secrets.get_secret_value.return_value = {'SecretString': '{}'}
    monkeypatch.setattr(auth, 'secrets', r.secrets)
    r.config = Mock(return_value={'client_id': 'synthetic-id', 'client_secret': 'synthetic-secret'})
    monkeypatch.setattr(auth, 'get_google_config', r.config)
    r.response = MagicMock()
    r.response.__enter__.return_value.read.return_value = b'{"access_token":"synthetic-access","refresh_token":"synthetic-refresh","expires_in":3600}'
    r.http = Mock(return_value=r.response)
    monkeypatch.setattr(auth.urllib.request, 'urlopen', r.http)
    return r


def test_create_v2(rig):
    rig.record = None
    response = auth.initiate_auth(event())
    assert response['statusCode'] == 200
    state = parse_qs(urlparse(json.loads(response['body'])['auth_url']).query)['state'][0]
    assert uuid.UUID(state).version == 4
    assert rig.record['PK'] == 'OAUTHSTATE#' + state
    assert rig.record['schema_version'] == 'v2' and rig.record['status'] == 'PENDING'
    assert rig.record['provider_secret_arn'] == ARN
    assert rig.record['initiating_principal'] == 'synthetic-sub'
    assert rig.record['expires_at'] - rig.record['created_at'] == 600
    rig.http.assert_not_called()
    rig.secrets.get_secret_value.assert_not_called()


@pytest.mark.parametrize('principal', [None, '', ' ', 'bad\nsub', 123])
def test_principal_required(rig, principal):
    assert auth.initiate_auth(event(principal=principal))['statusCode'] == 403
    rig.put.assert_not_called()
    rig.config.assert_not_called()


def test_duplicate_creation(rig, monkeypatch):
    monkeypatch.setattr(auth.uuid, 'uuid4', lambda: uuid.UUID(STATE))
    before = copy.deepcopy(rig.record)
    assert auth.initiate_auth(event())['statusCode'] == 503
    assert rig.record == before


@pytest.mark.parametrize('origin', ['http://localhost:5173', 'https://toganddogs.usmissionhero.com', 'https://app.toganddogs.com'])
def test_allowlisted_start(rig, origin):
    rig.record = None
    assert auth.initiate_auth(event(origin=origin))['statusCode'] == 200
    if origin == 'http://localhost:5173':
        assert rig.record['redirect_uri'] == origin + '/admin/auth/callback'
        assert rig.record['post_auth_destination'] == origin + '/admin'
    else:
        assert rig.record['redirect_uri'] == auth._OAUTH_PROD_REDIRECT
        assert rig.record['post_auth_destination'] == auth._OAUTH_PROD_DESTINATION


def test_origin_substring_denied(rig):
    assert auth.initiate_auth(event(origin='https://localhost.attacker.invalid'))['statusCode'] == 403
    rig.put.assert_not_called()


@pytest.mark.parametrize('state', [None, '', 'forged-state', str(uuid.uuid4()), {'company_id': 'foreign'}])
def test_unknown_forged_state(rig, state):
    request = event(True)
    request['queryStringParameters']['state'] = state
    assert auth.handle_callback(request)['statusCode'] == 400
    rig.http.assert_not_called()
    rig.secrets.get_secret_value.assert_not_called()


@pytest.mark.parametrize('field,value', [('schema_version', 'v1'), ('schema_version', None), ('status', 'CONSUMED'),
    ('company_id', 'Bad Tenant'), ('initiating_principal', None), ('provider_secret_arn', None),
    ('redirect_uri', 'https://attacker.invalid'), ('post_auth_destination', 'https://attacker.invalid'),
    ('expires_at', 1), ('created_at', int(time.time()) + 500), ('SK', 'OTHER')])
def test_invalid_transaction(rig, field, value):
    rig.record[field] = value
    assert auth.handle_callback(event(True))['statusCode'] == 400
    rig.http.assert_not_called()
    rig.update.assert_not_called()


@pytest.mark.parametrize('condition', ['missing', 'disabled', 'inactive', 'wrong-owner', 'drift'])
def test_ineligible_before_exchange(rig, condition):
    if condition == 'missing':
        rig.tenant = None
    elif condition == 'disabled':
        rig.tenant['subscription_status'] = 'disabled'
    elif condition == 'inactive':
        rig.tenant['is_active'] = False
    elif condition == 'wrong-owner':
        rig.metadata.describe_secret.return_value['Tags'][0]['Value'] = 'foreign'
    else:
        rig.record['provider_secret_arn'] = ARN[:-6] + 'Xy9876'
    assert auth.handle_callback(event(True))['statusCode'] == 403
    rig.http.assert_not_called()
    rig.secrets.get_secret_value.assert_not_called()


def test_success_bound_merge_and_redirect(rig):
    rig.secrets.get_secret_value.return_value = {'SecretString': json.dumps({'refresh_token': 'preserved',
        'token_status': 'revoked', 'revoked_at': 'old', 'revoked_reason': 'old'})}
    rig.response.__enter__.return_value.read.return_value = b'{"access_token":"new","expires_in":3600}'
    rig.record['redirect_uri'] = 'http://localhost:5173/admin/auth/callback'
    rig.record['post_auth_destination'] = 'http://localhost:5173/admin'
    result = auth.handle_callback(event(True, origin='https://attacker.invalid'))
    assert result['statusCode'] == 302 and result['headers']['Location'] == 'http://localhost:5173/admin'
    assert rig.record['status'] == 'CONSUMED'
    assert parse_qs(rig.http.call_args.args[0].data.decode())['redirect_uri'] == ['http://localhost:5173/admin/auth/callback']
    rig.secrets.get_secret_value.assert_called_once_with(SecretId=ARN)
    assert rig.secrets.put_secret_value.call_args.kwargs['SecretId'] == ARN
    saved = json.loads(rig.secrets.put_secret_value.call_args.kwargs['SecretString'])
    assert saved['refresh_token'] == 'preserved' and saved['access_token'] == 'new'
    assert not {'token_status', 'revoked_at', 'revoked_reason'} & saved.keys()
    assert 'updated_at' in saved
    assert auth.handle_callback(event(True))['statusCode'] == 400
    rig.http.assert_called_once()


def test_concurrent_callbacks(rig):
    rig.barrier = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: auth.handle_callback(event(True)), range(2)))
    assert sorted(r['statusCode'] for r in results) == [302, 400]
    assert rig.update.call_count == 2
    rig.http.assert_called_once()
    rig.secrets.put_secret_value.assert_called_once()


@pytest.mark.parametrize('change', ['expiry', 'principal', 'redirect'])
def test_claim_rejects_changed_fields(rig, change):
    original = rig.update.side_effect
    def mutate(**kw):
        if change == 'expiry':
            rig.record['expires_at'] = 1
        elif change == 'principal':
            rig.record['initiating_principal'] = 'different'
        else:
            rig.record['post_auth_destination'] = 'https://attacker.invalid'
        return original(**kw)
    rig.update.side_effect = mutate
    assert auth.handle_callback(event(True))['statusCode'] == 400
    rig.http.assert_not_called()


@pytest.mark.parametrize('failure', ['exchange', 'read', 'save'])
def test_failures_consumed_sanitized(rig, capsys, failure):
    target = {'exchange': rig.http, 'read': rig.secrets.get_secret_value, 'save': rig.secrets.put_secret_value}[failure]
    target.side_effect = RuntimeError('PRIVATE-CODE-TOKEN-MARKER')
    result = auth.handle_callback(event(True))
    assert result['statusCode'] == (502 if failure == 'exchange' else 503)
    assert rig.record['status'] == 'CONSUMED'
    assert 'Location' not in result.get('headers', {})
    assert 'PRIVATE-CODE-TOKEN-MARKER' not in result['body'] + capsys.readouterr().out


def test_drift_before_save(rig):
    def read(**kw):
        rig.metadata.describe_secret.return_value['Tags'][0]['Value'] = 'foreign'
        return {'SecretString': '{}'}
    rig.secrets.get_secret_value.side_effect = read
    assert auth.handle_callback(event(True))['statusCode'] == 403
    rig.http.assert_called_once()
    rig.secrets.put_secret_value.assert_not_called()


@pytest.mark.parametrize('field', ['PK', 'SK', 'schema_version', 'status', 'company_id', 'initiating_principal',
                                   'provider_secret_arn', 'redirect_uri', 'post_auth_destination', 'created_at', 'expires_at'])
def test_missing_security_fields(rig, field):
    del rig.record[field]
    assert auth.handle_callback(event(True))['statusCode'] == 400
    rig.update.assert_not_called()
    rig.http.assert_not_called()


def test_missing_state_record(rig):
    rig.record = None
    assert auth.handle_callback(event(True))['statusCode'] == 400
    rig.http.assert_not_called()


def test_decimal_timestamps(rig):
    from decimal import Decimal
    rig.record['created_at'] = Decimal(rig.record['created_at'])
    rig.record['expires_at'] = Decimal(rig.record['expires_at'])
    assert auth.handle_callback(event(True))['statusCode'] == 302


@pytest.mark.parametrize('value', [True, '600', None, float('inf')])
def test_malformed_timestamp(rig, value):
    rig.record['expires_at'] = value
    assert auth.handle_callback(event(True))['statusCode'] == 400
    rig.http.assert_not_called()


def test_metadata_storage_failure(rig, capsys):
    rig.get.side_effect = RuntimeError('PRIVATE-STATE-MARKER')
    result = auth.handle_callback(event(True))
    assert result['statusCode'] == 503
    assert 'PRIVATE-STATE-MARKER' not in result['body'] + capsys.readouterr().out
    rig.http.assert_not_called()


def test_wrong_owner_after_exchange_before_read(rig):
    def exchange(*args, **kwargs):
        rig.metadata.describe_secret.return_value['Tags'][0]['Value'] = 'foreign'
        return rig.response
    rig.http.side_effect = exchange
    assert auth.handle_callback(event(True))['statusCode'] == 403
    rig.secrets.get_secret_value.assert_not_called()
    rig.secrets.put_secret_value.assert_not_called()


def test_no_missing_refresh_credential_success(rig):
    rig.response.__enter__.return_value.read.return_value = b'{"access_token":"new","expires_in":3600}'
    assert auth.handle_callback(event(True))['statusCode'] == 502
    rig.secrets.put_secret_value.assert_not_called()
    assert rig.record['status'] == 'CONSUMED'


def test_callback_ignores_authenticated_caller_context(rig):
    request = event(True)
    request['requestContext'] = {'authorizer': {'claims': {'custom:company_id': 'foreign'}}}
    assert auth.handler(request, None)['statusCode'] == 302
    assert rig.secrets.put_secret_value.call_args.kwargs['SecretId'] == ARN


def test_disabled_feature_before_exchange(rig, monkeypatch):
    monkeypatch.setenv('ENTITLEMENT_ENFORCEMENT_ENABLED', 'true')
    rig.tenant['limits'] = {'google_calendar_enabled': False}
    assert auth.handle_callback(event(True))['statusCode'] == 403
    rig.http.assert_not_called()


def test_same_tenant_body_substitution_cannot_select_owner(rig):
    rig.record = None
    request = event()
    request['body'] = json.dumps({'company_id': 'foreign'})
    request['queryStringParameters'] = {'company_id': 'foreign'}
    assert auth.initiate_auth(request)['statusCode'] == 200
    assert rig.record['company_id'] == 'tog_and_dogs'
    assert rig.record['provider_secret_arn'] == ARN
