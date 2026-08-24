import json
import os
from unittest.mock import patch

import pytest

from common.billing import TenantEntitlement
from common.tenant_route import TenantRouteAccessDenied, resolve_expected_tenant
from handlers.admin_handler import handler as admin_handler


def make_event(company_id=None, *, groups='owner', slug=None):
    claims = {
        'email': 'owner@example.com',
        'sub': 'owner-sub',
        'cognito:groups': groups,
    }
    if company_id is not None:
        claims['custom:company_id'] = company_id

    event = {
        'httpMethod': 'GET',
        'path': '/admin/tenant-info',
        'requestContext': {'authorizer': {'claims': claims}},
    }
    if slug is not None:
        event['queryStringParameters'] = {'expectedTenantSlug': slug}
    return event


def active_tenant(**overrides):
    return {
        'PK': 'TENANT#test_tenant_alpha',
        'SK': 'METADATA',
        'company_id': 'test_tenant_alpha',
        'display_name': 'Test Tenant Alpha',
        'subscription_tier': 'starter',
        'subscription_status': 'active',
        'is_active': True,
        **overrides,
    }


@patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'multi'})
@patch('common.tenant_route.get_item')
def test_valid_slug_claim_and_active_tenant_agree(mock_get_item):
    mock_get_item.return_value = active_tenant()

    result = resolve_expected_tenant(
        make_event('test_tenant_alpha'),
        'test-tenant-alpha',
    )

    assert result['company_id'] == 'test_tenant_alpha'
    mock_get_item.assert_called_once_with('TENANT#test_tenant_alpha', 'METADATA')


@patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'multi'})
@patch('common.tenant_route.get_item')
def test_wrong_tenant_claim_fails_closed_without_primary_fallback(mock_get_item):
    mock_get_item.return_value = active_tenant()

    with pytest.raises(TenantRouteAccessDenied):
        resolve_expected_tenant(make_event('tog_and_dogs'), 'test-tenant-alpha')


@patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'multi'})
@patch('common.tenant_route.get_item')
def test_unknown_slug_fails_before_tenant_lookup(mock_get_item):
    with pytest.raises(TenantRouteAccessDenied):
        resolve_expected_tenant(make_event('test_tenant_alpha'), 'unknown-tenant')

    mock_get_item.assert_not_called()


@pytest.mark.parametrize(
    'tenant_overrides',
    [
        {'is_active': False},
        {'subscription_status': 'disabled'},
        {'subscription_status': 'paused'},
    ],
)
@patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'multi'})
@patch('common.tenant_route.get_item')
def test_inactive_tenant_states_fail_closed(mock_get_item, tenant_overrides):
    mock_get_item.return_value = active_tenant(**tenant_overrides)

    with pytest.raises(TenantRouteAccessDenied):
        resolve_expected_tenant(make_event('test_tenant_alpha'), 'test-tenant-alpha')


@patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'multi'})
@patch('common.tenant_route.get_item')
def test_missing_company_claim_fails_closed(mock_get_item):
    mock_get_item.return_value = active_tenant()

    with pytest.raises(TenantRouteAccessDenied):
        resolve_expected_tenant(make_event(), 'test-tenant-alpha')


@patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'single'})
@patch('common.tenant_route.get_item')
def test_route_bridge_requires_strict_multi_mode(mock_get_item):
    with pytest.raises(TenantRouteAccessDenied):
        resolve_expected_tenant(make_event('test_tenant_alpha'), 'test-tenant-alpha')

    mock_get_item.assert_not_called()


@patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'multi'})
@patch('common.tenant_route.get_item')
def test_platform_admin_group_has_no_route_authority_exception(mock_get_item):
    mock_get_item.return_value = active_tenant()

    with pytest.raises(TenantRouteAccessDenied):
        resolve_expected_tenant(
            make_event(groups='platform_admin'),
            'test-tenant-alpha',
        )


@patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'multi'})
@patch('common.entitlement._get_entitlement_safely')
@patch('common.tenant_route.get_item')
def test_tenant_info_expected_context_returns_safe_verified_metadata(
    mock_get_item,
    mock_get_entitlement,
):
    mock_get_item.return_value = active_tenant()
    mock_get_entitlement.return_value = TenantEntitlement(
        company_id='test_tenant_alpha',
        subscription_tier='starter',
        subscription_status='active',
    )

    response = admin_handler(
        make_event('test_tenant_alpha', slug='test-tenant-alpha'),
        None,
    )
    body = json.loads(response['body'])

    assert response['statusCode'] == 200
    assert body['company_id'] == 'test_tenant_alpha'
    assert body['display_name'] == 'Test Tenant Alpha'
    assert body['is_access_allowed'] is True
    assert body['is_blocked'] is False


@pytest.mark.parametrize(
    'company_id,slug',
    [
        ('tog_and_dogs', 'test-tenant-alpha'),
        ('test_tenant_alpha', 'unknown-tenant'),
        (None, 'test-tenant-alpha'),
        ('test_tenant_alpha', ''),
    ],
)
@patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'multi'})
@patch('common.tenant_route.get_item')
def test_tenant_info_negative_cases_share_generic_denial(mock_get_item, company_id, slug):
    mock_get_item.return_value = active_tenant()

    response = admin_handler(make_event(company_id, slug=slug), None)
    body = json.loads(response['body'])

    assert response['statusCode'] == 403
    assert body == {'error': 'Tenant context could not be verified'}
