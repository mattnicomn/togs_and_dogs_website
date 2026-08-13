"""
tests/backend/test_platform_onboarding_api.py
Integration and safety tests for handlers.platform_onboarding_handler
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from handlers.platform_onboarding_handler import handler


def _make_event(path: str, body: dict = None, groups: list = None, email: str = "admin@example.com"):
    groups = groups if groups is not None else ['platform_admin']
    event = {
        'httpMethod': 'POST',
        'path': path,
        'requestContext': {
            'authorizer': {
                'claims': {
                    'cognito:groups': groups,
                    'email': email,
                }
            }
        },
    }
    if body is not None:
        event['body'] = json.dumps(body)
    return event


class TestPlatformOnboardingAPI:
    def test_non_platform_admin_rejected_with_403(self):
        event = _make_event('/platform/onboarding/validate', {'company_id': 'acme_pets'}, groups=['staff'])
        res = handler(event)
        assert res['statusCode'] == 403
        body = json.loads(res['body'])
        assert 'Forbidden' in body['error']

    def test_unsupported_path_returns_404(self):
        event = _make_event('/platform/onboarding/apply', {'company_id': 'acme_pets'})
        res = handler(event)
        assert res['statusCode'] == 404

    def test_invalid_json_returns_400(self):
        event = _make_event('/platform/onboarding/validate')
        event['body'] = '{invalid-json'
        res = handler(event)
        assert res['statusCode'] == 400
        body = json.loads(res['body'])
        assert 'Invalid JSON' in body['error']

    def test_unknown_fields_returns_400(self):
        body = {
            'company_id': 'acme_pets',
            'display_name': 'Acme Pets',
            'malicious_field': 'drop table',
        }
        event = _make_event('/platform/onboarding/validate', body)
        res = handler(event)
        assert res['statusCode'] == 400
        res_body = json.loads(res['body'])
        assert 'Unknown fields' in res_body['error']

    @patch('common.tenant_read_adapter.get_tenant_by_company_id')
    @patch('common.tenant_read_adapter.check_display_name_conflict')
    def test_validate_success(self, mock_conflict, mock_get):
        mock_get.return_value = None  # No existing tenant
        mock_conflict.return_value = []  # No name collisions

        body = {
            'company_id': 'acme_pets',
            'display_name': 'Acme Pets Inc',
            'subscription_tier': 'professional',
            'subscription_status': 'active',
        }
        event = _make_event('/platform/onboarding/validate', body)
        res = handler(event)
        assert res['statusCode'] == 200
        data = json.loads(res['body'])

        assert data['valid'] is True
        assert data['errors'] == []
        assert data['no_writes'] is True
        assert data['validated_fields']['company_id'] == 'acme_pets'
        assert data['validated_fields']['subscription_tier'] == 'professional'

    @patch('common.tenant_read_adapter.get_tenant_by_company_id')
    def test_validate_existing_tenant_conflict(self, mock_get):
        mock_get.return_value = {'company_id': 'acme_pets', 'subscription_status': 'active'}

        body = {
            'company_id': 'acme_pets',
            'display_name': 'Acme Pets Inc',
        }
        event = _make_event('/platform/onboarding/validate', body)
        res = handler(event)
        assert res['statusCode'] == 200
        data = json.loads(res['body'])

        assert data['valid'] is False
        assert len(data['errors']) == 1
        assert 'already exists' in data['errors'][0]['error']
        assert data['no_writes'] is True

    @patch('common.tenant_read_adapter.get_tenant_by_company_id')
    @patch('common.tenant_read_adapter.check_display_name_conflict')
    def test_preview_success(self, mock_conflict, mock_get):
        mock_get.return_value = None
        mock_conflict.return_value = []

        body = {
            'company_id': 'acme_pets',
            'display_name': 'Acme Pets Inc',
            'subscription_tier': 'premium',
            'subscription_status': 'active',
            'notes': 'Test onboarding notes',
        }
        event = _make_event('/platform/onboarding/preview', body, email="admin@usmh.com")
        res = handler(event)
        assert res['statusCode'] == 200
        data = json.loads(res['body'])

        assert data['preview_state'] == 'PREVIEW_READY'
        assert data['no_writes'] is True
        assert 'preview_hash' in data
        assert data['proposed_metadata']['PK'] == 'TENANT#acme_pets'
        assert data['proposed_metadata']['created_by'] == 'platform_admin:admin@usmh.com'
        assert data['tier_limits']['max_staff'] == 15
        assert len(data['approval_checklist']) == 5
        assert data['catalog_version'] == 'v1'

    @patch('common.db.table')
    @patch('common.tenant_read_adapter.get_tenant_by_company_id')
    @patch('common.tenant_read_adapter.check_display_name_conflict')
    def test_no_write_operations_performed_during_preview(self, mock_conflict, mock_get, mock_table):
        mock_get.return_value = None
        mock_conflict.return_value = []

        body = {
            'company_id': 'acme_pets',
            'display_name': 'Acme Pets Inc',
        }
        event = _make_event('/platform/onboarding/preview', body)
        res = handler(event)
        assert res['statusCode'] == 200

        # Assert no write methods were called on table mock
        mock_table.put_item.assert_not_called()
        mock_table.update_item.assert_not_called()
        mock_table.delete_item.assert_not_called()
