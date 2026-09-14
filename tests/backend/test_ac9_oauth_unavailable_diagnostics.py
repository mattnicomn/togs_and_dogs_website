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
    'code=', 'authorization_code',
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
