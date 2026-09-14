"""
AC-9 diagnostic instrumentation tests.

Proves that initiate_auth emits a branch-specific, sanitized diagnostic marker
for each of the three OAUTH_UNAVAILABLE origins, WITHOUT changing the HTTP
response contract and WITHOUT emitting any sensitive material.

Local/mock only. No production credentials, no external transport, no
production requests. These tests intentionally block real AWS/provider access
via mocks.
"""
import os
import json
import pytest
from unittest.mock import patch, MagicMock

os.environ['DEFAULT_COMPANY_ID'] = 'tog_and_dogs'
os.environ['DATA_TABLE_NAME'] = 'test-table'
os.environ['ADMIN_USER_POOL_ID'] = 'us-east-1_xxxx'
os.environ['GOOGLE_CLIENT_CREDS_NAME'] = 'google-creds'
os.environ['GOOGLE_USER_TOKENS_NAME'] = 'togs-and-dogs-prod/google/user-tokens'

from handlers.google_auth_handler import handler as google_auth_handler

# Sensitive substrings that must NEVER appear in emitted diagnostic output.
SENSITIVE_MARKERS = [
    'client_secret', 'refresh_token', 'access_token', 'Authorization',
    'Bearer', 'cognito:groups', 'custom:company_id', 'SecretString',
    'super-secret', 'THE-CLIENT-ID', 'refresh-XYZ', 'access-XYZ',
    # OAuth authorization-code leakage patterns. NOTE: intentionally NOT the bare
    # 'code=' substring, because the approved diagnostic marker legitimately emits
    # 'error_code=<AWS Error.Code>', which is a sanitized identifier, not a secret.
    '?code=', '&code=', "'code':", 'authorization_code',
]


def make_event(path='/admin/auth/google', http_method='GET', groups=('owner',),
               custom_company_id='tog_and_dogs', sub='test-sub-123'):
    claims = {'email': 'user@example.com', 'sub': sub, 'email_verified': 'true'}
    if groups:
        claims['cognito:groups'] = ','.join(groups)
    if custom_company_id is not None:
        claims['custom:company_id'] = custom_company_id
    return {
        'requestContext': {'authorizer': {'claims': claims}},
        'httpMethod': http_method,
        'path': path,
        'headers': {'origin': 'https://toganddogs.usmissionhero.com'},
        'queryStringParameters': None,
    }


@pytest.fixture(autouse=True)
def _multi_tenant_mode():
    with patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'multi'}):
        yield


@pytest.fixture
def _owned_provider_metadata():
    """Valid owned provider binding for tog_and_dogs (branch A does NOT fire)."""
    with patch('common.google_calendar.secrets') as sdk:
        sdk.meta.region_name = 'us-east-1'
        sdk.describe_secret.side_effect = lambda SecretId: {
            'Name': SecretId,
            'ARN': 'arn:aws:secretsmanager:us-east-1:123456789012:secret:' + SecretId + '-Ab1234',
            'Tags': [{'Key': 'CompanyId', 'Value': 'tog_and_dogs'}]}
        sdk.get_secret_value.return_value = {'SecretString': '{}'}
        yield


def _assert_no_sensitive(captured):
    combined = captured.out + captured.err
    for token in SENSITIVE_MARKERS:
        assert token not in combined, f"sensitive token leaked into logs: {token}"


# ---------------------------------------------------------------------------
# 1. Branch A — provider metadata / binding resolution failure
# ---------------------------------------------------------------------------
@patch('common.db.table.put_item')
@patch('handlers.google_auth_handler.get_google_config')
def test_branch_a_provider_metadata_marker(mock_config, mock_put, capsys):
    from common.google_calendar import ProviderBindingError
    mock_config.return_value = {"client_id": "THE-CLIENT-ID", "client_secret": "super-secret"}
    with patch('common.google_calendar._resolve_google_token_binding',
               side_effect=ProviderBindingError('PROVIDER_METADATA_INACCESSIBLE')):
        result = google_auth_handler(make_event(groups=('owner',)), None)
    assert result['statusCode'] == 503
    assert 'OAUTH_UNAVAILABLE' in result['body']
    out = capsys.readouterr()
    assert 'AC9_OAUTH_UNAVAILABLE_PROVIDER_METADATA' in out.out
    assert 'AC9_OAUTH_UNAVAILABLE_GOOGLE_CONFIG' not in out.out
    assert 'AC9_OAUTH_UNAVAILABLE_UNEXPECTED_EXCEPTION' not in out.out
    mock_put.assert_not_called()
    _assert_no_sensitive(out)


# ---------------------------------------------------------------------------
# 2. Branch B — missing/invalid Google client configuration
# ---------------------------------------------------------------------------
@patch('common.db.table.get_item')
@patch('common.entitlement._get_entitlement_safely')
@patch('common.db.table.put_item')
@patch('handlers.google_auth_handler.get_google_config')
def test_branch_b_google_config_marker(mock_config, mock_put, mock_ent, mock_get_item,
                                       capsys, _owned_provider_metadata):
    # Config loads but has NO usable client_id -> branch B, client_id_present=false
    mock_ent.return_value = MagicMock(is_access_allowed=True, is_blocked=False)
    mock_get_item.return_value = {'Item': {
        "PK": "TENANT#tog_and_dogs", "SK": "METADATA", "company_id": "tog_and_dogs",
        "calendar_provider": "google", "calendar_enabled": True,
        "subscription_status": "active"}}
    mock_config.return_value = {"client_secret": "super-secret"}
    result = google_auth_handler(make_event(groups=('owner',)), None)
    assert result['statusCode'] == 503
    assert 'OAUTH_UNAVAILABLE' in result['body']
    out = capsys.readouterr()
    assert 'AC9_OAUTH_UNAVAILABLE_GOOGLE_CONFIG client_id_present=false' in out.out
    assert 'AC9_OAUTH_UNAVAILABLE_PROVIDER_METADATA' not in out.out
    assert 'AC9_OAUTH_UNAVAILABLE_UNEXPECTED_EXCEPTION' not in out.out
    mock_put.assert_not_called()
    _assert_no_sensitive(out)


@patch('common.db.table.get_item')
@patch('common.entitlement._get_entitlement_safely')
@patch('common.db.table.put_item')
@patch('handlers.google_auth_handler.get_google_config')
def test_branch_b_google_config_none_marker(mock_config, mock_put, mock_ent, mock_get_item,
                                            capsys, _owned_provider_metadata):
    # get_google_config returns None (unreadable creds) -> still branch B
    mock_ent.return_value = MagicMock(is_access_allowed=True, is_blocked=False)
    mock_get_item.return_value = {'Item': {
        "PK": "TENANT#tog_and_dogs", "SK": "METADATA", "company_id": "tog_and_dogs",
        "calendar_provider": "google", "calendar_enabled": True,
        "subscription_status": "active"}}
    mock_config.return_value = None
    result = google_auth_handler(make_event(groups=('owner',)), None)
    assert result['statusCode'] == 503
    out = capsys.readouterr()
    assert 'AC9_OAUTH_UNAVAILABLE_GOOGLE_CONFIG client_id_present=false' in out.out
    mock_put.assert_not_called()
    _assert_no_sensitive(out)


# ---------------------------------------------------------------------------
# 3 & 4. Branch C — generic unexpected exception, class only (no message)
# ---------------------------------------------------------------------------
@patch('common.db.table.get_item')
@patch('common.entitlement._get_entitlement_safely')
@patch('common.db.table.put_item')
@patch('handlers.google_auth_handler.get_google_config')
def test_branch_c_unexpected_exception_marker(mock_config, mock_put, mock_ent, mock_get_item,
                                              capsys, _owned_provider_metadata):
    mock_ent.return_value = MagicMock(is_access_allowed=True, is_blocked=False)
    mock_get_item.return_value = {'Item': {
        "PK": "TENANT#tog_and_dogs", "SK": "METADATA", "company_id": "tog_and_dogs",
        "calendar_provider": "google", "calendar_enabled": True,
        "subscription_status": "active"}}
    secret_message = 'super-secret-refresh_token-access_token-leak'
    mock_config.side_effect = RuntimeError(secret_message)
    result = google_auth_handler(make_event(groups=('owner',)), None)
    assert result['statusCode'] == 503
    assert 'OAUTH_UNAVAILABLE' in result['body']
    out = capsys.readouterr()
    assert 'AC9_OAUTH_UNAVAILABLE_UNEXPECTED_EXCEPTION exception_class=RuntimeError' in out.out
    # The raw exception message must NOT be logged.
    assert secret_message not in (out.out + out.err)
    assert 'AC9_OAUTH_UNAVAILABLE_PROVIDER_METADATA' not in out.out
    assert 'AC9_OAUTH_UNAVAILABLE_GOOGLE_CONFIG' not in out.out
    mock_put.assert_not_called()
    _assert_no_sensitive(out)


# ---------------------------------------------------------------------------
# 5. No secret/token/code/client-secret/event payload from any branch (covered
#    per-branch above via _assert_no_sensitive); explicit combined check here.
# ---------------------------------------------------------------------------
@patch('common.db.table.get_item')
@patch('common.entitlement._get_entitlement_safely')
@patch('common.db.table.put_item')
@patch('handlers.google_auth_handler.get_google_config')
def test_no_sensitive_output_across_branches(mock_config, mock_put, mock_ent, mock_get_item,
                                             capsys, _owned_provider_metadata):
    mock_ent.return_value = MagicMock(is_access_allowed=True, is_blocked=False)
    mock_get_item.return_value = {'Item': {
        "PK": "TENANT#tog_and_dogs", "SK": "METADATA", "company_id": "tog_and_dogs",
        "calendar_provider": "google", "calendar_enabled": True,
        "subscription_status": "active"}}
    mock_config.return_value = {"client_secret": "super-secret", "client_id": ""}
    result = google_auth_handler(make_event(groups=('owner',)), None)
    assert result['statusCode'] == 503
    out = capsys.readouterr()
    assert 'AC9_OAUTH_UNAVAILABLE_GOOGLE_CONFIG client_id_present=false' in out.out
    _assert_no_sensitive(out)


# ---------------------------------------------------------------------------
# 6 & 7. HTTP behavior unchanged; successful initiation still works and emits
#        NONE of the diagnostic markers.
# ---------------------------------------------------------------------------
@patch('common.db.table.get_item')
@patch('common.entitlement._get_entitlement_safely')
@patch('handlers.google_auth_handler.get_google_config')
@patch('common.db.table.put_item')
def test_successful_initiation_unchanged(mock_put, mock_config, mock_ent, mock_get_item,
                                         capsys, _owned_provider_metadata):
    mock_ent.return_value = MagicMock(is_access_allowed=True, is_blocked=False)
    mock_get_item.return_value = {'Item': {
        "PK": "TENANT#tog_and_dogs", "SK": "METADATA", "company_id": "tog_and_dogs",
        "calendar_provider": "google", "calendar_enabled": True,
        "subscription_status": "active"}}
    mock_config.return_value = {"client_id": "THE-CLIENT-ID", "client_secret": "super-secret"}
    result = google_auth_handler(make_event(groups=('owner',)), None)
    assert result['statusCode'] == 200
    body = json.loads(result['body'])
    assert 'auth_url' in body
    mock_put.assert_called_once()
    out = capsys.readouterr()
    assert 'AC9_OAUTH_UNAVAILABLE' not in out.out
    # client_id/secret must not be logged even on success
    _assert_no_sensitive(out)


@patch('common.db.table.put_item')
def test_http_contract_unchanged_for_unavailable(mock_put, capsys):
    """Any OAUTH_UNAVAILABLE branch still returns HTTP 503 + OAUTH_UNAVAILABLE."""
    from common.google_calendar import ProviderBindingError
    with patch('common.google_calendar._resolve_google_token_binding',
               side_effect=ProviderBindingError('PROVIDER_METADATA_INACCESSIBLE')):
        result = google_auth_handler(make_event(groups=('owner',)), None)
    assert result['statusCode'] == 503
    body = json.loads(result['body'])
    # response contract preserved: category string still surfaced to caller
    assert 'OAUTH_UNAVAILABLE' in json.dumps(body)
    mock_put.assert_not_called()


# ---------------------------------------------------------------------------
# Category-C error_code instrumentation (botocore ClientError from the
# unwrapped DynamoDB GetItem in _require_oauth_tenant_eligible).
# ---------------------------------------------------------------------------
from botocore.exceptions import ClientError as _ClientError


def _clienterror(code, message='super-secret-should-not-be-logged', op='GetItem'):
    return _ClientError({'Error': {'Code': code, 'Message': message},
                         'ResponseMetadata': {'RequestId': 'REQ-SENSITIVE-123',
                                              'HTTPStatusCode': 400}}, op)


_TENANT_METADATA_ITEM = {'Item': {
    'PK': 'TENANT#tog_and_dogs', 'SK': 'METADATA', 'company_id': 'tog_and_dogs',
    'calendar_provider': 'google', 'calendar_enabled': True, 'is_active': True,
    'subscription_status': 'active'}}


def _run_clienterror(mock_get_item, exc, capsys):
    # Isolate the _require_oauth_tenant_eligible path: force _require_oauth_binding
    # to succeed (returns a valid ARN), then make the eligibility read
    # (ConsistentRead=True) raise the exception. This reproduces the production
    # scenario where the unwrapped eligibility GetItem is the Category-C source.
    def side_effect(*args, **kwargs):
        if kwargs.get('ConsistentRead') is True:
            raise exc
        return _TENANT_METADATA_ITEM
    mock_get_item.side_effect = side_effect
    with patch('handlers.google_auth_handler._require_oauth_binding',
               return_value='arn:aws:secretsmanager:us-east-1:123456789012:secret:togs-and-dogs-prod/google/user-tokens-Ab1234'):
        result = google_auth_handler(make_event(groups=('owner',)), None)
    return result, capsys.readouterr()


@patch('common.db.table.put_item')
@patch('common.db.table.get_item')
def test_clienterror_accessdenied_logs_code_only(mock_get_item, mock_put, capsys, _owned_provider_metadata):
    result, out = _run_clienterror(mock_get_item, _clienterror('AccessDeniedException'), capsys)
    assert result['statusCode'] == 503
    assert 'OAUTH_UNAVAILABLE' in result['body']
    assert ('AC9_OAUTH_UNAVAILABLE_UNEXPECTED_EXCEPTION exception_class=ClientError '
            'error_code=AccessDeniedException operation=DynamoDB.GetItem') in out.out
    mock_put.assert_not_called()
    _assert_no_sensitive(out)
    assert 'super-secret-should-not-be-logged' not in (out.out + out.err)
    assert 'REQ-SENSITIVE-123' not in (out.out + out.err)


@patch('common.db.table.put_item')
@patch('common.db.table.get_item')
def test_clienterror_validation_logs_code_only(mock_get_item, mock_put, capsys, _owned_provider_metadata):
    result, out = _run_clienterror(mock_get_item, _clienterror('ValidationException'), capsys)
    assert result['statusCode'] == 503
    assert 'error_code=ValidationException operation=DynamoDB.GetItem' in out.out
    assert 'AC9_OAUTH_UNAVAILABLE_UNEXPECTED_EXCEPTION exception_class=ClientError' in out.out
    mock_put.assert_not_called()
    _assert_no_sensitive(out)


@patch('common.db.table.put_item')
@patch('common.db.table.get_item')
def test_clienterror_malformed_code_logs_unknown(mock_get_item, mock_put, capsys, _owned_provider_metadata):
    # Missing Error.Code -> error_code=UNKNOWN
    exc = _ClientError({'ResponseMetadata': {'HTTPStatusCode': 500}}, 'GetItem')
    result, out = _run_clienterror(mock_get_item, exc, capsys)
    assert result['statusCode'] == 503
    assert 'error_code=UNKNOWN operation=DynamoDB.GetItem' in out.out
    mock_put.assert_not_called()
    _assert_no_sensitive(out)


@patch('common.db.table.put_item')
@patch('common.db.table.get_item')
def test_clienterror_message_and_requestid_not_logged(mock_get_item, mock_put, capsys, _owned_provider_metadata):
    result, out = _run_clienterror(
        mock_get_item, _clienterror('ThrottlingException', message='refresh_token=LEAK access_token=LEAK'), capsys)
    combined = out.out + out.err
    assert 'error_code=ThrottlingException' in out.out
    # Raw Error.Message / tokens / request id must NOT appear.
    assert 'refresh_token=LEAK' not in combined
    assert 'access_token=LEAK' not in combined
    assert 'REQ-SENSITIVE-123' not in combined
    _assert_no_sensitive(out)


@patch('common.db.table.put_item')
@patch('common.db.table.get_item')
def test_clienterror_injected_code_is_sanitized(mock_get_item, mock_put, capsys, _owned_provider_metadata):
    # A malicious/non-identifier Code must not leak arbitrary/multiline text.
    result, out = _run_clienterror(
        mock_get_item, _clienterror('Bad Code\nsecret-leak refresh_token=X'), capsys)
    assert result['statusCode'] == 503
    assert 'error_code=UNKNOWN operation=DynamoDB.GetItem' in out.out
    assert 'secret-leak' not in (out.out + out.err)
    assert 'refresh_token=X' not in (out.out + out.err)


@patch('common.db.table.put_item')
@patch('common.db.table.get_item')
def test_non_clienterror_exception_has_no_error_code(mock_get_item, mock_put, capsys, _owned_provider_metadata):
    secret_message = 'super-secret-refresh_token-leak'
    result, out = _run_clienterror(mock_get_item, RuntimeError(secret_message), capsys)
    assert result['statusCode'] == 503
    assert 'AC9_OAUTH_UNAVAILABLE_UNEXPECTED_EXCEPTION exception_class=RuntimeError' in out.out
    assert 'error_code=' not in out.out  # only ClientError carries error_code
    assert secret_message not in (out.out + out.err)
    mock_put.assert_not_called()
