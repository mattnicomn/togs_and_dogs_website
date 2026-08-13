"""
tests/backend/test_r17w_tenant_provisioning.py
Release 17W: Tenant Provisioning Script Tests

Tests for scripts/provision_tenant.py covering:
  - Metadata payload construction and schema correctness
  - Tier limits derivation
  - Audit record schema
  - Idempotency guard behavior (apply mode)
  - Dry-run enforcement (no writes in dry-run)
  - CLI guardrails (company_id validation, reserved ID guard)
  - Cognito template output (text content, placeholder-only)
  - Rollback guidance text output

No live AWS credentials or DynamoDB writes are performed in these tests.
All DynamoDB interactions in apply mode are mocked.
"""

import json
import re
import sys
import os
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from io import StringIO

# Add scripts directory to path for import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scripts'))
import provision_tenant as pt
from common.tenant_catalog import get_all_tier_limits


# ---------------------------------------------------------------------------
# 1. Metadata Builder Tests
# ---------------------------------------------------------------------------

class TestBuildTenantMetadata:

    def test_cli_catalog_matches_shared_canonical_catalog(self):
        assert pt.TIER_LIMITS == get_all_tier_limits()

    def test_required_fields_present(self):
        meta = pt.build_tenant_metadata(
            company_id='acme_pets',
            display_name='Acme Pet Sitting',
        )
        required = [
            'PK', 'SK', 'company_id', 'display_name', 'entity_type',
            'subscription_tier', 'subscription_status', 'limits',
            'is_active', 'notes', 'created_at', 'updated_at',
            'created_by', 'updated_by',
        ]
        for field in required:
            assert field in meta, f"Missing required field: {field}"

    def test_pk_sk_format(self):
        meta = pt.build_tenant_metadata('acme_pets', 'Acme Pet Sitting')
        assert meta['PK'] == 'TENANT#acme_pets'
        assert meta['SK'] == 'METADATA'

    def test_entity_type(self):
        meta = pt.build_tenant_metadata('acme_pets', 'Acme Pet Sitting')
        assert meta['entity_type'] == 'TENANT'

    def test_default_tier_is_starter(self):
        meta = pt.build_tenant_metadata('acme_pets', 'Acme Pet Sitting')
        assert meta['subscription_tier'] == 'starter'

    def test_default_status_is_active(self):
        meta = pt.build_tenant_metadata('acme_pets', 'Acme Pet Sitting')
        assert meta['subscription_status'] == 'active'

    def test_is_active_true(self):
        meta = pt.build_tenant_metadata('acme_pets', 'Acme Pet Sitting')
        assert meta['is_active'] is True

    def test_custom_tier_sets_limits(self):
        meta = pt.build_tenant_metadata('acme_pets', 'Acme', tier='professional')
        assert meta['subscription_tier'] == 'professional'
        assert meta['limits']['max_staff'] == 5
        assert meta['limits']['google_calendar_enabled'] is True

    def test_starter_limits_correct(self):
        meta = pt.build_tenant_metadata('acme_pets', 'Acme', tier='starter')
        limits = meta['limits']
        assert limits['max_active_clients'] == 20
        assert limits['max_staff'] == 1
        assert limits['max_monthly_notifications'] == 100
        assert limits['google_calendar_enabled'] is False
        assert limits['export_enabled'] is False

    def test_enterprise_limits_unlimited(self):
        meta = pt.build_tenant_metadata('acme_pets', 'Acme', tier='enterprise')
        limits = meta['limits']
        assert limits['max_active_clients'] >= 999999
        assert limits['max_staff'] >= 999999

    def test_sensitive_fields_excluded(self):
        meta = pt.build_tenant_metadata('acme_pets', 'Acme Pet Sitting')
        forbidden = [
            'stripe_customer_id', 'stripe_subscription_id',
            'owner_email', 'owner_cognito_sub',
        ]
        for field in forbidden:
            assert field not in meta, f"Sensitive field should not be in metadata: {field}"

    def test_timestamps_are_iso_format(self):
        meta = pt.build_tenant_metadata('acme_pets', 'Acme Pet Sitting')
        for ts_field in ('created_at', 'updated_at'):
            ts = meta[ts_field]
            # Should parse as valid ISO datetime
            datetime.fromisoformat(ts.replace('Z', '+00:00'))

    def test_custom_actor(self):
        meta = pt.build_tenant_metadata('acme_pets', 'Acme', actor='platform_admin:tester@example.com')
        assert meta['created_by'] == 'platform_admin:tester@example.com'
        assert meta['updated_by'] == 'platform_admin:tester@example.com'

    def test_company_id_in_metadata(self):
        meta = pt.build_tenant_metadata('acme_pets', 'Acme Pet Sitting')
        assert meta['company_id'] == 'acme_pets'

    def test_display_name_in_metadata(self):
        meta = pt.build_tenant_metadata('acme_pets', 'Acme Pet Sitting')
        assert meta['display_name'] == 'Acme Pet Sitting'

    def test_default_notes_preserve_legacy_cli_text(self):
        meta = pt.build_tenant_metadata('acme_pets', 'Acme Pet Sitting')
        assert meta['notes'].startswith('Provisioned via provision_tenant.py on ')


# ---------------------------------------------------------------------------
# 2. Audit Record Tests
# ---------------------------------------------------------------------------

class TestBuildAuditRecord:

    def setup_method(self):
        self.meta = pt.build_tenant_metadata('acme_pets', 'Acme Pet Sitting')

    def test_audit_pk_is_platform_audit(self):
        audit = pt.build_audit_record('acme_pets', self.meta, actor='platform_admin:system')
        assert audit['PK'] == 'PLATFORM_AUDIT'

    def test_audit_sk_format(self):
        audit = pt.build_audit_record('acme_pets', self.meta, actor='platform_admin:system')
        # SK format: ACTION#<timestamp>#<uuid>
        assert audit['SK'].startswith('ACTION#')
        parts = audit['SK'].split('#')
        assert len(parts) == 3
        # Last part should be a UUID
        uuid_part = parts[2]
        assert re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', uuid_part)

    def test_audit_action_is_provision_tenant(self):
        audit = pt.build_audit_record('acme_pets', self.meta, actor='platform_admin:system')
        assert audit['action'] == 'PROVISION_TENANT'

    def test_audit_target_company_id(self):
        audit = pt.build_audit_record('acme_pets', self.meta, actor='platform_admin:system')
        assert audit['target_company_id'] == 'acme_pets'

    def test_audit_entity_type(self):
        audit = pt.build_audit_record('acme_pets', self.meta, actor='platform_admin:system')
        assert audit['entity_type'] == 'PLATFORM_AUDIT'

    def test_audit_changed_fields_present(self):
        audit = pt.build_audit_record('acme_pets', self.meta, actor='platform_admin:system')
        assert isinstance(audit['changed_fields'], list)
        assert len(audit['changed_fields']) > 0

    def test_audit_old_values_empty_on_first_provision(self):
        audit = pt.build_audit_record('acme_pets', self.meta, actor='platform_admin:system')
        assert audit['old_values'] == {}

    def test_audit_new_values_contains_key_fields(self):
        audit = pt.build_audit_record('acme_pets', self.meta, actor='platform_admin:system')
        nv = audit['new_values']
        assert nv['company_id'] == 'acme_pets'
        assert nv['display_name'] == 'Acme Pet Sitting'
        assert 'subscription_tier' in nv
        assert 'subscription_status' in nv

    def test_audit_actor_recorded(self):
        audit = pt.build_audit_record('acme_pets', self.meta, actor='platform_admin:test')
        assert audit['actor'] == 'platform_admin:test'

    def test_two_audit_records_have_unique_sks(self):
        audit1 = pt.build_audit_record('acme_pets', self.meta, actor='platform_admin:system')
        audit2 = pt.build_audit_record('acme_pets', self.meta, actor='platform_admin:system')
        assert audit1['SK'] != audit2['SK'], "Audit records must have unique SKs for idempotency"


# ---------------------------------------------------------------------------
# 3. Dry-Run Output Tests (no writes, no AWS)
# ---------------------------------------------------------------------------

class TestDryRun:

    def _capture_dry_run(self, company_id='acme_pets', display_name='Acme Pet Sitting',
                         tier='starter', status='active', notes='', actor='platform_admin:system'):
        captured = StringIO()
        with patch('sys.stdout', captured):
            pt.run_dry_run(company_id, display_name, tier, status, notes, actor)
        return captured.getvalue()

    def test_dry_run_outputs_no_writes(self):
        output = self._capture_dry_run()
        assert 'NO WRITES WILL OCCUR' in output

    def test_dry_run_outputs_metadata(self):
        output = self._capture_dry_run()
        assert 'TENANT METADATA RECORD' in output
        assert 'acme_pets' in output

    def test_dry_run_outputs_audit_record(self):
        output = self._capture_dry_run()
        assert 'PLATFORM AUDIT RECORD' in output

    def test_dry_run_outputs_cognito_templates(self):
        output = self._capture_dry_run()
        assert 'COGNITO CLI COMMAND TEMPLATES' in output
        assert '<USER_POOL_ID>' in output

    def test_dry_run_cognito_templates_have_placeholders(self):
        output = self._capture_dry_run()
        # All sensitive values must be placeholders, not real credentials
        for placeholder in ('<USER_POOL_ID>', '<USERNAME_OR_EMAIL>', '<TEMP_PASSWORD>', '<EMAIL>'):
            assert placeholder in output, f"Missing placeholder: {placeholder}"

    def test_dry_run_outputs_rollback_guidance(self):
        output = self._capture_dry_run()
        assert 'ROLLBACK' in output

    def test_dry_run_outputs_idempotency_notes(self):
        output = self._capture_dry_run()
        assert 'IDEMPOTENCY' in output

    def test_dry_run_does_not_contain_real_credentials(self):
        output = self._capture_dry_run()
        # Must not contain real AWS account patterns or secrets
        forbidden_patterns = [
            r'us-east-1_[A-Za-z0-9]+',   # real user pool ID pattern
            r'AKIA[A-Z0-9]{16}',           # AWS access key
            r'whsec_[A-Za-z0-9]+',         # Stripe webhook secret
        ]
        for pattern in forbidden_patterns:
            assert not re.search(pattern, output), f"Output contains pattern that looks like a real credential: {pattern}"

    def test_dry_run_role_clarification_present(self):
        output = self._capture_dry_run()
        assert 'platform_admin' in output
        # Must warn that platform_admin group must not be assigned to tenant owners
        assert 'do NOT' in output.lower() or 'do not' in output.lower()

    def test_dry_run_sensitive_fields_not_in_metadata_output(self):
        output = self._capture_dry_run()
        for field in ('stripe_customer_id', 'stripe_subscription_id', 'owner_email', 'owner_cognito_sub'):
            assert field not in output, f"Sensitive field should not appear in dry-run output: {field}"


# ---------------------------------------------------------------------------
# 4. Apply Mode Idempotency Tests (mocked DynamoDB)
# ---------------------------------------------------------------------------

class TestApplyModeIdempotency:

    def _make_mock_table(self, existing_item=None):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {'Item': existing_item} if existing_item else {}
        mock_table.put_item.return_value = {}
        return mock_table

    def test_apply_skips_metadata_if_already_exists(self):
        existing = {
            'PK': 'TENANT#acme_pets',
            'SK': 'METADATA',
            'company_id': 'acme_pets',
            'display_name': 'Old Name',
        }
        mock_table = self._make_mock_table(existing_item=existing)

        with patch('boto3.Session') as mock_session:
            mock_session.return_value.resource.return_value.Table.return_value = mock_table
            captured = StringIO()
            with patch('sys.stdout', captured):
                result = pt.run_apply(
                    company_id='acme_pets',
                    display_name='Acme Pet Sitting',
                    tier='starter',
                    status='active',
                    notes='',
                    actor='platform_admin:system',
                    aws_profile='test-profile',
                    table_name='test-table',
                    force_overwrite=False,
                )
            assert result is False, "Should return False (skipped) when tenant exists without force_overwrite"
            output = captured.getvalue()
            assert 'SKIPPED' in output

    def test_apply_writes_metadata_when_no_existing(self):
        mock_table = self._make_mock_table(existing_item=None)

        with patch('boto3.Session') as mock_session:
            mock_session.return_value.resource.return_value.Table.return_value = mock_table
            captured = StringIO()
            with patch('sys.stdout', captured):
                result = pt.run_apply(
                    company_id='acme_pets',
                    display_name='Acme Pet Sitting',
                    tier='starter',
                    status='active',
                    notes='',
                    actor='platform_admin:system',
                    aws_profile='test-profile',
                    table_name='test-table',
                    force_overwrite=False,
                )
            assert result is True, "Should return True (written) when tenant does not exist"
            # put_item should be called at least twice (metadata + audit)
            assert mock_table.put_item.call_count >= 2

    def test_apply_always_writes_audit_record(self):
        existing = {
            'PK': 'TENANT#acme_pets',
            'SK': 'METADATA',
            'company_id': 'acme_pets',
        }
        mock_table = self._make_mock_table(existing_item=existing)

        with patch('boto3.Session') as mock_session:
            mock_session.return_value.resource.return_value.Table.return_value = mock_table
            with patch('sys.stdout', StringIO()):
                pt.run_apply(
                    company_id='acme_pets',
                    display_name='Acme Pet Sitting',
                    tier='starter',
                    status='active',
                    notes='',
                    actor='platform_admin:system',
                    aws_profile='test-profile',
                    table_name='test-table',
                    force_overwrite=False,
                )
            # Audit record should always be written even if metadata was skipped
            put_calls = mock_table.put_item.call_args_list
            audit_calls = [
                c for c in put_calls
                if c[1].get('Item', {}).get('PK') == 'PLATFORM_AUDIT'
                   or (c[0] and c[0][0].get('PK') == 'PLATFORM_AUDIT')
            ]
            assert len(audit_calls) >= 1, "Audit record must be written regardless of metadata skip"

    def test_apply_force_overwrite_overwrites_existing(self):
        existing = {
            'PK': 'TENANT#acme_pets',
            'SK': 'METADATA',
            'company_id': 'acme_pets',
            'display_name': 'Old Name',
        }
        mock_table = self._make_mock_table(existing_item=existing)

        with patch('boto3.Session') as mock_session:
            mock_session.return_value.resource.return_value.Table.return_value = mock_table
            with patch('sys.stdout', StringIO()):
                result = pt.run_apply(
                    company_id='acme_pets',
                    display_name='New Name',
                    tier='starter',
                    status='active',
                    notes='',
                    actor='platform_admin:system',
                    aws_profile='test-profile',
                    table_name='test-table',
                    force_overwrite=True,
                )
            assert result is True


# ---------------------------------------------------------------------------
# 5. CLI Guardrail Tests
# ---------------------------------------------------------------------------

class TestCLIGuardrails:

    def test_reserved_company_id_rejected(self):
        """tog_and_dogs is the production tenant and must be protected."""
        with pytest.raises(SystemExit):
            with patch('sys.argv', ['provision_tenant.py',
                                    '--company-id', 'tog_and_dogs',
                                    '--display-name', 'Test']):
                with patch('sys.stdout', StringIO()):
                    with patch('sys.stderr', StringIO()):
                        pt.main()

    def test_invalid_company_id_format_rejected(self):
        """company_id must be lowercase letters, digits, underscores only (3-64 chars)."""
        invalid_ids = ['AB-CD', 'has space', '', 'a' * 65, 'has-hyphen', 'Has_Upper']
        for cid in invalid_ids:
            with pytest.raises(SystemExit):
                with patch('sys.argv', ['provision_tenant.py',
                                        '--company-id', cid,
                                        '--display-name', 'Test']):
                    with patch('sys.stdout', StringIO()):
                        with patch('sys.stderr', StringIO()):
                            pt.main()

    def test_apply_without_confirm_rejected(self):
        """--apply without --confirm-apply must be rejected for safety."""
        with pytest.raises(SystemExit):
            with patch('sys.argv', ['provision_tenant.py',
                                    '--company-id', 'acme_pets',
                                    '--display-name', 'Acme',
                                    '--apply']):
                with patch('sys.stdout', StringIO()):
                    with patch('sys.stderr', StringIO()):
                        pt.main()

    def test_valid_company_id_dry_runs_ok(self):
        """Valid company_id with dry-run should not raise SystemExit."""
        with patch('sys.argv', ['provision_tenant.py',
                                '--company-id', 'acme_pets_123',
                                '--display-name', 'Acme Pet Sitting']):
            with patch('sys.stdout', StringIO()):
                pt.main()  # Should not raise


# ---------------------------------------------------------------------------
# 6. Tier Limits Completeness Tests
# ---------------------------------------------------------------------------

class TestTierLimitsCompleteness:

    def test_all_tiers_defined(self):
        required_tiers = {'starter', 'professional', 'premium', 'enterprise'}
        assert set(pt.TIER_LIMITS.keys()) == required_tiers

    def test_each_tier_has_required_limit_keys(self):
        required_keys = {
            'max_active_clients', 'max_staff', 'max_monthly_notifications',
            'max_monthly_bookings', 'google_calendar_enabled', 'export_enabled',
            'custom_branding_enabled', 'video_evidence_enabled',
        }
        for tier, limits in pt.TIER_LIMITS.items():
            for key in required_keys:
                assert key in limits, f"Tier '{tier}' missing limit key: '{key}'"

    def test_starter_has_lowest_limits(self):
        starter = pt.TIER_LIMITS['starter']
        professional = pt.TIER_LIMITS['professional']
        assert starter['max_staff'] <= professional['max_staff']
        assert starter['max_active_clients'] <= professional['max_active_clients']

    def test_enterprise_is_unlimited(self):
        ent = pt.TIER_LIMITS['enterprise']
        for key in ('max_active_clients', 'max_staff', 'max_monthly_notifications', 'max_monthly_bookings'):
            assert ent[key] >= 999999, f"Enterprise {key} should be effectively unlimited"
