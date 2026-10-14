import os
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from test_ptm0_s1_untagged_isolation import s1_read_table, s1_request, s1_event

# Set required env vars
os.environ.setdefault('DEFAULT_COMPANY_ID', 'tog_and_dogs')
os.environ.setdefault('DATA_TABLE_NAME', 'test-table')
os.environ.setdefault('ADMIN_USER_POOL_ID', 'us-east-1_xxxx')
os.environ.setdefault('GOOGLE_CLIENT_CREDS_NAME', 'google-creds')
os.environ.setdefault('GOOGLE_USER_TOKENS_NAME', 'google-tokens')

from handlers.google_auth_handler import get_status, calendar_health_check, initiate_auth, handle_callback, disconnect_auth
from handlers.admin_handler import handler as admin_handler


@pytest.fixture(autouse=True)
def _no_network():
    """Function-scoped, autouse guard (Gate C3b.3h.2): any UNMOCKED AWS/botocore
    call fails loudly rather than silently reaching the network. The Google-
    Calendar tests mock the provider-binding resolver and secrets above this
    layer; the S1 pagination tests use an in-memory seeded fake table. This only
    fires on a genuine leak. Auto-restored per test."""
    from unittest.mock import patch as _patch
    def _blocked(*args, **kwargs):
        raise AssertionError(
            "Unmocked AWS/botocore network call attempted in an isolated tenant-"
            "isolation test. Add an explicit scoped mock for the operation reached."
        )
    with _patch('botocore.httpsession.URLLib3Session.send', _blocked):
        yield


@pytest.mark.parametrize('company', ['tog_and_dogs', 'test_tenant_alpha', 'future_tenant'])
@pytest.mark.parametrize('status', ['ALL', 'PENDING_REVIEW', None])
def test_s1_admin_request_lists_scope_every_page(s1_read_table, company, status):
    rows = [s1_request('own', company), s1_request('wrong', 'other_company'),
            s1_request('primary', 'tog_and_dogs'), s1_request('legacy'),
            s1_request('null', None), s1_request('empty', ''),
            s1_request('space', ' '), s1_request('numeric', 42),
            s1_request('list', [company]), s1_request('map', {'id': company}),
            s1_request('deleted', company, status='DELETED'),
            s1_request('archived', company, status='ARCHIVED')]
    rows.append(dict(s1_request('job', company), PK='JOB#job', entity_type='JOB'))
    s1_read_table.seed(rows)
    query = {'limit': '1'}
    if status is not None:
        query['status'] = status
    original_scan = s1_read_table.table.scan
    with patch.object(s1_read_table.table, 'scan', side_effect=lambda **kw: original_scan(**dict(kw, Limit=1))) as scans, \
         patch.object(s1_read_table.table, 'query', wraps=s1_read_table.table.query) as queries:
        seen, cursors, empty_pages = [], [], 0
        for _ in range(30):
            response = admin_handler(s1_event(company, query=query), {})
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            seen.extend(item['request_id'] for item in body['requests'])
            empty_pages += not body['requests']
            cursor = body['lastKey']
            if not cursor:
                break
            assert cursor not in cursors
            cursors.append(cursor)
            query['startKey'] = cursor
        else:
            pytest.fail('S1 pagination did not terminate')
    expected = {'own', 'primary', 'legacy'} if company == 'tog_and_dogs' else {'own'}
    assert set(seen) == expected
    assert len(seen) == len(expected)
    assert empty_pages > 0  # Empty filtered pages must still allow safe continuation.
    calls = scans.call_args_list if status == 'ALL' else queries.call_args_list
    assert len(calls) > 1
    filters = [call.kwargs['FilterExpression'] for call in calls]
    assert all(condition == filters[0] for condition in filters)
    assert all('ExclusiveStartKey' in call.kwargs for call in calls[1:])
    s1_read_table.audit.assert_not_called()

def make_event(path, http_method='GET', groups=None, custom_company_id=None, email='user@example.com', sub='test-sub-123', body=None):
    claims = {
        'email': email,
        'sub': sub,
        'email_verified': 'true',
    }
    if groups:
        claims['cognito:groups'] = ','.join(groups) if isinstance(groups, list) else groups
    if custom_company_id is not None:
        claims['custom:company_id'] = custom_company_id

    event = {
        'requestContext': {
            'authorizer': {
                'claims': claims
            }
        },
        'httpMethod': http_method,
        'path': path,
    }
    if body:
        event['body'] = json.dumps(body)
    return event


# ==============================================================================
# 1. Google Calendar Tenant Gate Tests
# ==============================================================================

class TestGoogleCalendarTenantGate:

    @patch('handlers.google_auth_handler.secrets')
    @patch('common.google_calendar._resolve_google_token_binding')
    def test_default_tenant_status_connected(self, mock_binding, mock_secrets):
        """Default tenant: a resolved provider binding + valid cached tokens -> CONNECTED.

        AC-9 contract: get_status resolves the per-tenant provider binding via
        common.google_calendar._resolve_google_token_binding (the authoritative
        boundary — NOT the removed get_stored_tokens helper), then reads the
        bound secret from Secrets Manager and classifies the cached tokens. We
        model a bound default tenant and a valid, non-expired token blob so the
        REAL _classify_cached_status produces CONNECTED, without any live
        DynamoDB/Secrets access.
        """
        bound_arn = 'arn:aws:secretsmanager:us-east-1:123456789012:secret:togs-and-dogs-prod/calendar/tog_and_dogs/tokens-Ab1234'
        mock_binding.return_value = ('togs-and-dogs-prod/calendar/tog_and_dogs/tokens', bound_arn)
        mock_secrets.get_secret_value.return_value = {'SecretString': json.dumps({
            'access_token': 'valid-token',
            'refresh_token': 'refresh-token',
            'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'expires_in': 3600,
        })}

        event = make_event('/admin/auth/status', http_method='GET', groups=['owner'], custom_company_id='tog_and_dogs')
        resp = get_status(event)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['status'] == 'CONNECTED'
        # The bound secret was read exactly once from the resolved ARN.
        mock_secrets.get_secret_value.assert_called_once_with(SecretId=bound_arn)
        # No token/credential material leaks into the response.
        assert 'access_token' not in body and 'refresh_token' not in body

    @patch('handlers.google_auth_handler.secrets')
    @patch('common.google_calendar._resolve_google_token_binding')
    def test_non_default_tenant_status_not_connected(self, mock_binding, mock_secrets):
        """Non-default tenant with verified metadata but no calendar_secret_ref
        resolves to an UNBOUND provider (resolver returns None) -> NOT_CONNECTED,
        and NO secret is ever read. This is the AC-9 fail-closed outcome for an
        unconfigured tenant (a 200/NOT_CONNECTED denial of calendar data, not a
        connected state)."""
        mock_binding.return_value = None  # unbound non-default tenant

        event = make_event('/admin/auth/status', http_method='GET', groups=['owner'], custom_company_id='test_tenant_alpha')

        resp = get_status(event)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['status'] == 'NOT_CONNECTED'
        # Unbound tenant must never trigger a Secrets Manager read.
        mock_secrets.get_secret_value.assert_not_called()

    @patch('handlers.google_auth_handler.get_google_config')
    @patch('common.google_calendar._resolve_google_token_binding')
    def test_non_default_tenant_initiate_oauth_blocked(self, mock_binding, mock_get_config):
        """Non-default tenant is blocked from initiating Google OAuth.

        AC-9 contract: initiate_auth calls _require_oauth_binding, which treats an
        unbound tenant (resolver returns None) as OAUTH_ACCESS_DENIED (403). The
        request is denied before any Google config is read, so the tenant cannot
        start an OAuth flow. (The prior 'not supported' wording predates AC-9;
        the current fail-closed category is OAUTH_ACCESS_DENIED.)
        """
        mock_binding.return_value = None  # unbound non-default tenant

        event = make_event('/admin/auth/google', http_method='GET', groups=['owner'], custom_company_id='test_tenant_alpha')

        resp = initiate_auth(event)
        assert resp['statusCode'] == 403
        body = json.loads(resp['body'])
        assert body['error'] == 'OAUTH_ACCESS_DENIED'
        # Blocked before any Google OAuth client configuration is consulted.
        mock_get_config.assert_not_called()

    @patch('handlers.google_auth_handler.secrets')
    @patch('common.google_calendar._resolve_google_token_binding')
    @patch('handlers.google_auth_handler.table')
    def test_non_default_tenant_callback_blocked(self, mock_table, mock_binding, mock_secrets):
        """Non-default tenant callback exchange is blocked (fail-closed).

        AC-9 hardened the callback: handle_callback consumes the OAuth state via
        _load_oauth_transaction with strict schema-v2 integrity checks (schema_
        version, PENDING status, canonical provider_secret_arn, matched
        redirect/destination, and a bounded created/expiry window) BEFORE any
        token exchange. The 'state123' / minimal-record fixture does not satisfy
        that contract (it is not a valid, unconsumed v2 transaction), so the
        callback is denied with INVALID_OAUTH_STATE and the exchange never runs.
        This exercises the real replay/integrity protection rather than asserting
        stale 'not supported' wording. We also set the provider binding to None
        so that even a schema-valid state could only reach OAUTH_ACCESS_DENIED,
        never a connected/redirect outcome.
        """
        mock_binding.return_value = None
        mock_table.get_item.return_value = {
            'Item': {
                'PK': 'OAUTHSTATE#state123',
                'SK': 'META',
                'company_id': 'test_tenant_alpha'
            }
        }
        event = {
            'httpMethod': 'GET',
            'path': '/admin/auth/callback',
            'queryStringParameters': {
                'code': 'oauthcode123',
                'state': 'state123'
            }
        }
        resp = handle_callback(event)
        # Fail-closed: never a success/redirect; the hardened state-integrity
        # contract denies this transaction.
        assert resp['statusCode'] in (400, 403)
        body = json.loads(resp['body'])
        assert body['error'] in ('INVALID_OAUTH_STATE', 'OAUTH_ACCESS_DENIED')
        # No token exchange / secret write ever occurred.
        mock_secrets.put_secret_value.assert_not_called()

    @patch('common.google_calendar._resolve_google_token_binding')
    def test_non_default_tenant_disconnect_noop(self, mock_binding):
        """Non-default tenant disconnect is a no-op that never clears Secrets Manager.

        AC-9 contract: disconnect_auth resolves the provider binding; an unbound
        tenant (resolver returns None) returns 200 'Google Calendar is not
        configured.' and performs NO secret write (no cross-tenant or primary
        credential is touched)."""
        mock_binding.return_value = None  # unbound non-default tenant
        event = make_event('/admin/auth/google', http_method='DELETE', groups=['owner'], custom_company_id='test_tenant_alpha')
        with patch('handlers.google_auth_handler.secrets') as mock_secrets:
            resp = disconnect_auth(event)
            assert resp['statusCode'] == 200
            body = json.loads(resp['body'])
            assert "not configured" in body['message']
            mock_secrets.put_secret_value.assert_not_called()


# ==============================================================================
# 2. Cognito User Filtering Tests
# ==============================================================================

class TestCognitoUserFiltering:

    @patch('handlers.admin_handler.boto3.client')
    @patch('common.db.table.query')
    @patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'multi'})
    def test_staff_list_filtering_multi_mode(self, mock_query, mock_cognito_client):
        """Under multi-tenant mode, staff list returns only Cognito users matching company_id."""
        mock_query.return_value = {'Items': []} # Empty DynamoDB profiles
        
        mock_cog = MagicMock()
        mock_cognito_client.return_value = mock_cog
        mock_cog.list_groups.return_value = {
            'Groups': [{'GroupName': 'Staff'}, {'GroupName': 'owner'}]
        }
        
        mock_cog.list_users_in_group.return_value = {
            'Users': [
                {
                    'Username': 'staff1',
                    'Enabled': True,
                    'UserStatus': 'CONFIRMED',
                    'Attributes': [
                        {'Name': 'email', 'Value': 'staff1@test.com'},
                        {'Name': 'sub', 'Value': 'sub1'},
                        {'Name': 'custom:company_id', 'Value': 'test_tenant_alpha'}
                    ]
                },
                {
                    'Username': 'staff2',
                    'Enabled': True,
                    'UserStatus': 'CONFIRMED',
                    'Attributes': [
                        {'Name': 'email', 'Value': 'staff2@test.com'},
                        {'Name': 'sub', 'Value': 'sub2'},
                        {'Name': 'custom:company_id', 'Value': 'tog_and_dogs'}
                    ]
                },
                {
                    'Username': 'staff3',
                    'Enabled': True,
                    'UserStatus': 'CONFIRMED',
                    'Attributes': [
                        {'Name': 'email', 'Value': 'staff3@test.com'},
                        {'Name': 'sub', 'Value': 'sub3'}
                    ]
                }
            ]
        }
        
        event = make_event('/admin/staff', http_method='GET', groups=['owner'], custom_company_id='test_tenant_alpha')
        resp = admin_handler(event, None)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        
        staff_list = body['staff']
        assert len(staff_list) == 1
        assert staff_list[0]['email'] == 'staff1@test.com'
        assert staff_list[0]['company_id'] == 'test_tenant_alpha'

    @patch('handlers.admin_handler.boto3.client')
    @patch('common.db.table.query')
    @patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'single'})
    def test_staff_list_filtering_single_mode_fallback(self, mock_query, mock_cognito_client):
        """Under single-tenant mode, users missing custom:company_id fall back to default company."""
        mock_query.return_value = {'Items': []}
        mock_cog = MagicMock()
        mock_cognito_client.return_value = mock_cog
        mock_cog.list_groups.return_value = {
            'Groups': [{'GroupName': 'Staff'}]
        }
        mock_cog.list_users_in_group.return_value = {
            'Users': [
                {
                    'Username': 'staff_legacy',
                    'Enabled': True,
                    'UserStatus': 'CONFIRMED',
                    'Attributes': [
                        {'Name': 'email', 'Value': 'legacy@test.com'},
                        {'Name': 'sub', 'Value': 'sub_leg'}
                    ]
                }
            ]
        }
        
        event = make_event('/admin/staff', http_method='GET', groups=['owner'], custom_company_id='tog_and_dogs')
        resp = admin_handler(event, None)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert len(body['staff']) == 1
        assert body['staff'][0]['email'] == 'legacy@test.com'

        event2 = make_event('/admin/staff', http_method='GET', groups=['owner'], custom_company_id='test_tenant_alpha')
        resp2 = admin_handler(event2, None)
        assert resp2['statusCode'] == 200
        body2 = json.loads(resp2['body'])
        assert len(body2['staff']) == 0


# ==============================================================================
# 3. Tenant Info Endpoint Tests
# ==============================================================================

class TestTenantInfoEndpoint:

    @patch('handlers.google_auth_handler.secrets')
    @patch('common.google_calendar._resolve_google_token_binding')
    @patch('common.entitlement._get_entitlement_safely')
    @patch('handlers.admin_handler.get_item')
    def test_tenant_info_default_company(self, mock_get_item, mock_ent, mock_binding, mock_secrets):
        """tenant-info returns correct metadata for default tenant including calendar status.

        The tenant-info route derives google_calendar_status by calling the real
        get_status, which resolves the per-tenant provider binding (AC-9). We
        model an active default tenant with a resolved binding + valid cached
        tokens so the REAL status resolution yields CONNECTED — exercising the
        current logic, not the removed get_stored_tokens helper.
        """
        from common.billing import TenantEntitlement
        mock_get_item.return_value = {
            'company_id': 'tog_and_dogs',
            'display_name': 'Tog & Dogs Production',
            'subscription_tier': 'premium',
            'subscription_status': 'active'
        }
        mock_ent.return_value = TenantEntitlement(
            company_id='tog_and_dogs', subscription_tier='premium', subscription_status='active')
        bound_arn = 'arn:aws:secretsmanager:us-east-1:123456789012:secret:togs-and-dogs-prod/calendar/tog_and_dogs/tokens-Ab1234'
        mock_binding.return_value = ('togs-and-dogs-prod/calendar/tog_and_dogs/tokens', bound_arn)
        mock_secrets.get_secret_value.return_value = {'SecretString': json.dumps({
            'access_token': 'tok',
            'refresh_token': 'ref',
            'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'expires_in': 3600,
        })}

        event = make_event('/admin/tenant-info', http_method='GET', groups=['owner'], custom_company_id='tog_and_dogs')
        resp = admin_handler(event, None)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['company_id'] == 'tog_and_dogs'
        assert body['display_name'] == 'Tog & Dogs Production'
        assert body['subscription_tier'] == 'premium'
        assert body['subscription_status'] == 'active'
        assert body['google_calendar_status'] == 'CONNECTED'
        assert 'refresh_token' not in body
        assert 'access_token' not in body

    @patch('handlers.google_auth_handler.secrets')
    @patch('common.google_calendar._resolve_google_token_binding')
    @patch('common.entitlement._get_entitlement_safely')
    @patch('handlers.admin_handler.get_item')
    def test_tenant_info_second_company(self, mock_get_item, mock_ent, mock_binding, mock_secrets):
        """tenant-info for an active second tenant: calendar is unbound (resolver
        returns None) -> NOT_CONNECTED, with no Secrets Manager read. Proves the
        second tenant surfaces an unconfigured calendar, never a connected one."""
        from common.billing import TenantEntitlement
        mock_get_item.return_value = {
            'company_id': 'test_tenant_alpha',
            'display_name': 'Test Tenant Alpha LLC',
            'subscription_tier': 'starter',
            'subscription_status': 'active'
        }
        mock_ent.return_value = TenantEntitlement(
            company_id='test_tenant_alpha', subscription_tier='starter', subscription_status='active')
        mock_binding.return_value = None  # unbound second tenant

        event = make_event('/admin/tenant-info', http_method='GET', groups=['owner'], custom_company_id='test_tenant_alpha')
        resp = admin_handler(event, None)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['company_id'] == 'test_tenant_alpha'
        assert body['display_name'] == 'Test Tenant Alpha LLC'
        assert body['subscription_tier'] == 'starter'
        assert body['subscription_status'] == 'active'
        assert body['google_calendar_status'] == 'NOT_CONNECTED'
        mock_secrets.get_secret_value.assert_not_called()
