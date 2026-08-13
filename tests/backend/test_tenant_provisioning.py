"""
tests/backend/test_tenant_provisioning.py
Unit tests for src/backend/common/tenant_provisioning.py
"""

import pytest
from common.tenant_provisioning import (
    ProvisioningValidationError,
    build_approval_checklist,
    build_proposed_audit,
    build_proposed_metadata,
    compute_preview_hash,
    validate_company_id,
    validate_display_name,
    validate_notes,
    validate_status,
    validate_tier,
)


class TestTenantProvisioningValidation:
    def test_validate_company_id_valid(self):
        assert validate_company_id('acme_pets') == 'acme_pets'
        assert validate_company_id('  pet123  ') == 'pet123'

    def test_validate_company_id_reserved_raises(self):
        with pytest.raises(ProvisioningValidationError) as exc:
            validate_company_id('tog_and_dogs')
        assert exc.value.field == 'company_id'
        assert 'reserved' in exc.value.message

    def test_validate_company_id_uppercase_or_invalid_chars_raises(self):
        with pytest.raises(ProvisioningValidationError):
            validate_company_id('AcmePets')
        with pytest.raises(ProvisioningValidationError):
            validate_company_id('acme-pets!')

    def test_validate_company_id_too_short_or_long(self):
        with pytest.raises(ProvisioningValidationError):
            validate_company_id('ab')
        with pytest.raises(ProvisioningValidationError):
            validate_company_id('a' * 65)

    def test_validate_company_id_none_or_non_string(self):
        with pytest.raises(ProvisioningValidationError):
            validate_company_id(None)
        with pytest.raises(ProvisioningValidationError):
            validate_company_id(12345)

    def test_validate_display_name_valid(self):
        assert validate_display_name(' Acme Pet Care ') == 'Acme Pet Care'

    def test_validate_display_name_too_long(self):
        with pytest.raises(ProvisioningValidationError) as exc:
            validate_display_name('A' * 101)
        assert exc.value.field == 'display_name'
        assert 'cannot exceed 100' in exc.value.message

    def test_validate_display_name_control_chars(self):
        with pytest.raises(ProvisioningValidationError) as exc:
            validate_display_name('Acme\x00Pet Care')
        assert exc.value.field == 'display_name'
        assert 'control characters' in exc.value.message

    def test_validate_display_name_empty_or_none(self):
        with pytest.raises(ProvisioningValidationError):
            validate_display_name('')
        with pytest.raises(ProvisioningValidationError):
            validate_display_name(None)

    def test_validate_tier(self):
        assert validate_tier(None) == 'starter'
        assert validate_tier('PROFESSIONAL') == 'professional'
        with pytest.raises(ProvisioningValidationError):
            validate_tier('invalid_tier')

    def test_validate_status(self):
        assert validate_status(None) == 'disabled'
        assert validate_status('ACTIVE') == 'active'
        with pytest.raises(ProvisioningValidationError):
            validate_status('invalid_status')

    def test_validate_notes(self):
        assert validate_notes(None) == ''
        assert validate_notes('  valid notes  ') == '  valid notes  '
        with pytest.raises(ProvisioningValidationError):
            validate_notes('A' * 2001)
        with pytest.raises(ProvisioningValidationError):
            validate_notes('notes\x07with bell')


class TestMetadataAndAuditBuilder:
    def test_build_proposed_metadata_schema(self):
        meta = build_proposed_metadata(
            company_id='bark_lounge',
            display_name='The Bark Lounge',
            tier='professional',
            status='active',
            notes='V1 test notes',
            actor='platform_admin:ryan@example.com',
            now_iso='2026-08-12T12:00:00Z',
        )

        assert meta['PK'] == 'TENANT#bark_lounge'
        assert meta['SK'] == 'METADATA'
        assert meta['company_id'] == 'bark_lounge'
        assert meta['display_name'] == 'The Bark Lounge'
        assert meta['entity_type'] == 'TENANT'
        assert meta['subscription_tier'] == 'professional'
        assert meta['subscription_status'] == 'active'
        assert meta['is_active'] is True
        assert meta['limits']['max_staff'] == 5
        assert meta['created_by'] == 'platform_admin:ryan@example.com'
        assert meta['created_at'] == '2026-08-12T12:00:00Z'

    def test_build_proposed_audit_schema(self):
        meta = build_proposed_metadata('bark_lounge', 'The Bark Lounge')
        audit = build_proposed_audit(
            company_id='bark_lounge',
            proposed_metadata=meta,
            actor='platform_admin:ryan@example.com',
            audit_id='test-uuid-1234',
            now_iso='2026-08-12T12:00:00Z',
        )

        assert audit['PK'] == 'PLATFORM_AUDIT'
        assert audit['SK'] == 'ACTION#2026-08-12T12:00:00Z#test-uuid-1234'
        assert audit['action'] == 'PROVISION_TENANT'
        assert audit['target_company_id'] == 'bark_lounge'
        assert audit['actor'] == 'platform_admin:ryan@example.com'

    def test_build_approval_checklist(self):
        checklist = build_approval_checklist('bark_lounge', 'professional', 'active')
        assert len(checklist) == 5
        items = [c['item'] for c in checklist]
        assert any('Matthew approval' in i for i in items)
        assert any('Stripe live billing' in i for i in items)

    def test_compute_preview_hash(self):
        payload1 = {'b': 2, 'a': 1}
        payload2 = {'a': 1, 'b': 2}
        # Keys sorted deterministically -> identical hash
        assert compute_preview_hash(payload1) == compute_preview_hash(payload2)

        payload3 = {'a': 1, 'b': 3}
        assert compute_preview_hash(payload1) != compute_preview_hash(payload3)
