"""
src/backend/common/tenant_provisioning.py
Preview-Only V1: Tenant Onboarding Orchestrator — Provisioning Domain

Provides pure-Python functions for:
  - Company ID validation
  - Display name validation
  - Proposed tenant metadata construction (deterministic, for preview only)
  - Proposed audit record construction (for preview only, never written)
  - Preview hash generation (SHA-256 of canonical preview payload)

DESIGN PRINCIPLES:
  - Pure Python — no boto3, no env vars, no I/O, no HTTP, no DB
  - Receives timestamps and UUIDs as arguments for determinism/testability
  - Raises ProvisioningValidationError for any validation failure
  - Preview output includes explicit `no_writes: true` marker
  - Does NOT implement Apply logic — that remains in scripts/provision_tenant.py

RESERVED IDS:
  Reserved company IDs cannot be provisioned via this orchestrator.
  'tog_and_dogs' is the only confirmed production tenant ID.
"""

import copy
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone

from common.tenant_catalog import (
    DEFAULT_STATUS,
    DEFAULT_TIER,
    get_tier_limits,
    is_valid_status,
    is_valid_tier,
    CATALOG_VERSION,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMPANY_ID_PATTERN = re.compile(r'^[a-z0-9_]{3,64}$')

# Only IDs with confirmed production data or special platform significance
RESERVED_COMPANY_IDS: frozenset = frozenset({'tog_and_dogs'})

DISPLAY_NAME_MAX_LEN: int = 100
NOTES_MAX_LEN: int = 2000

# Characters that must not appear in any user-supplied string field
# Control chars 0x00–0x1F (except tab 0x09) and 0x7F–0x9F
_CONTROL_CHAR_RE = re.compile(r'[\x00-\x08\x0a-\x1f\x7f-\x9f]')

# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class ProvisioningValidationError(ValueError):
    """Raised when a provisioning input fails validation."""

    def __init__(self, message: str, field: str = None):
        super().__init__(message)
        self.field = field
        self.message = message

    def to_dict(self) -> dict:
        return {
            'error': self.message,
            'field': self.field,
        }


# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------


def _has_control_chars(value: str) -> bool:
    """Return True if the string contains disallowed control characters."""
    return bool(_CONTROL_CHAR_RE.search(value))


def validate_company_id(company_id) -> str:
    """
    Validate and return the normalized company_id.

    Raises ProvisioningValidationError on failure.
    """
    if company_id is None:
        raise ProvisioningValidationError(
            "company_id is required.", field='company_id'
        )
    if not isinstance(company_id, str):
        raise ProvisioningValidationError(
            "company_id must be a string.", field='company_id'
        )
    normalized = company_id.strip()
    if not normalized:
        raise ProvisioningValidationError(
            "company_id cannot be empty.", field='company_id'
        )
    if not COMPANY_ID_PATTERN.match(normalized):
        raise ProvisioningValidationError(
            "company_id must be 3–64 characters: lowercase letters, digits, and underscores only.",
            field='company_id',
        )
    if normalized in RESERVED_COMPANY_IDS:
        raise ProvisioningValidationError(
            f"company_id '{normalized}' is reserved and cannot be provisioned.",
            field='company_id',
        )
    return normalized


def validate_display_name(display_name) -> str:
    """
    Validate and return the trimmed display name.

    Raises ProvisioningValidationError on failure.
    """
    if display_name is None:
        raise ProvisioningValidationError(
            "display_name is required.", field='display_name'
        )
    if not isinstance(display_name, str):
        raise ProvisioningValidationError(
            "display_name must be a string.", field='display_name'
        )
    normalized = display_name.strip()
    if not normalized:
        raise ProvisioningValidationError(
            "display_name cannot be empty.", field='display_name'
        )
    if len(normalized) > DISPLAY_NAME_MAX_LEN:
        raise ProvisioningValidationError(
            f"display_name cannot exceed {DISPLAY_NAME_MAX_LEN} characters "
            f"(got {len(normalized)}).",
            field='display_name',
        )
    if _has_control_chars(normalized):
        raise ProvisioningValidationError(
            "display_name contains disallowed control characters.",
            field='display_name',
        )
    return normalized


def validate_tier(tier) -> str:
    """
    Validate and return the normalized subscription tier.

    Raises ProvisioningValidationError on failure.
    """
    if tier is None:
        return DEFAULT_TIER
    if not isinstance(tier, str):
        raise ProvisioningValidationError(
            "subscription_tier must be a string.", field='subscription_tier'
        )
    normalized = tier.strip().lower()
    if not is_valid_tier(normalized):
        from common.tenant_catalog import get_all_tiers
        raise ProvisioningValidationError(
            f"subscription_tier '{tier}' is not valid. "
            f"Valid tiers: {get_all_tiers()}.",
            field='subscription_tier',
        )
    return normalized


def validate_status(status) -> str:
    """
    Validate and return the normalized subscription status.

    Raises ProvisioningValidationError on failure.
    """
    if status is None:
        return DEFAULT_STATUS
    if not isinstance(status, str):
        raise ProvisioningValidationError(
            "subscription_status must be a string.", field='subscription_status'
        )
    normalized = status.strip().lower()
    if not is_valid_status(normalized):
        from common.tenant_catalog import get_all_statuses
        raise ProvisioningValidationError(
            f"subscription_status '{status}' is not valid. "
            f"Valid statuses: {get_all_statuses()}.",
            field='subscription_status',
        )
    return normalized


def validate_notes(notes) -> str:
    """
    Validate and return the notes string. None/empty → empty string.

    Raises ProvisioningValidationError on failure.
    """
    if notes is None:
        return ''
    if not isinstance(notes, str):
        raise ProvisioningValidationError(
            "notes must be a string or null.", field='notes'
        )
    if len(notes) > NOTES_MAX_LEN:
        raise ProvisioningValidationError(
            f"notes cannot exceed {NOTES_MAX_LEN} characters (got {len(notes)}).",
            field='notes',
        )
    if _has_control_chars(notes):
        raise ProvisioningValidationError(
            "notes contains disallowed control characters.", field='notes'
        )
    return notes


# ---------------------------------------------------------------------------
# Metadata Builder (PREVIEW-ONLY — no writes)
# ---------------------------------------------------------------------------


def build_proposed_metadata(
    company_id: str,
    display_name: str,
    tier: str = DEFAULT_TIER,
    status: str = DEFAULT_STATUS,
    notes: str = '',
    actor: str = 'platform_admin:unknown',
    now_iso: str = None,
    default_notes: str = None,
) -> dict:
    """
    Build the proposed DynamoDB tenant metadata record for preview.

    The returned dict represents EXACTLY what would be written by Apply mode.
    It is NEVER written by this function.

    Args:
        company_id: Validated company slug.
        display_name: Validated display name.
        tier: Validated subscription tier.
        status: Validated subscription status.
        notes: Optional notes string.
        actor: Cognito-derived actor identifier.
        now_iso: ISO timestamp; auto-generated if not provided.

    Returns:
        A dict matching the TENANT#<company_id>/METADATA schema.
    """
    company_id = validate_company_id(company_id)
    display_name = validate_display_name(display_name)
    tier = validate_tier(tier)
    status = validate_status(status)
    notes = validate_notes(notes)

    if now_iso is None:
        now_iso = _now_iso()

    limits = get_tier_limits(tier)

    return {
        'PK': f'TENANT#{company_id}',
        'SK': 'METADATA',
        'company_id': company_id,
        'display_name': display_name,
        'entity_type': 'TENANT',
        'subscription_tier': tier,
        'subscription_status': status,
        'limits': limits,
        'is_active': True,
        'notes': notes or default_notes or f'Provisioned via platform admin onboarding on {now_iso}',
        'created_at': now_iso,
        'updated_at': now_iso,
        'created_by': actor,
        'updated_by': actor,
    }


def build_proposed_audit(
    company_id: str,
    proposed_metadata: dict,
    actor: str,
    audit_id: str,
    now_iso: str = None,
) -> dict:
    """
    Build the proposed PLATFORM_AUDIT record for preview.

    NEVER written by this function (preview only).

    Args:
        company_id: Validated company slug.
        proposed_metadata: The metadata dict from build_proposed_metadata.
        actor: Cognito-derived actor identifier.
        audit_id: UUID string for the audit SK.
        now_iso: ISO timestamp; auto-generated if not provided.
    """
    company_id = validate_company_id(company_id)
    if not isinstance(proposed_metadata, dict):
        raise ProvisioningValidationError(
            "proposed_metadata must be a dictionary.", field='proposed_metadata'
        )
    if now_iso is None:
        now_iso = _now_iso()

    return {
        'PK': 'PLATFORM_AUDIT',
        'SK': f'ACTION#{now_iso}#{audit_id}',
        'entity_type': 'PLATFORM_AUDIT',
        'action': 'PROVISION_TENANT',
        'target_company_id': company_id,
        'changed_fields': [
            'company_id', 'display_name', 'subscription_tier',
            'subscription_status', 'limits', 'notes',
        ],
        'old_values': {},
        'new_values': {
            'company_id': company_id,
            'display_name': proposed_metadata['display_name'],
            'subscription_tier': proposed_metadata['subscription_tier'],
            'subscription_status': proposed_metadata['subscription_status'],
        },
        'actor': actor,
        'timestamp': now_iso,
    }


# ---------------------------------------------------------------------------
# Preview Checklist
# ---------------------------------------------------------------------------


def build_approval_checklist(company_id: str, tier: str, status: str) -> list:
    """
    Return the list of approval-gate items that must be satisfied before
    any Apply can be approved by Matthew.

    These items are informational in the preview; they do not block the
    preview generation itself.
    """
    return [
        {
            'item': 'Explicit Matthew approval for this specific company_id and scope',
            'required': True,
            'satisfied': False,
        },
        {
            'item': 'Product tier, pricing, and subscription semantics approved',
            'required': True,
            'satisfied': False,
        },
        {
            'item': 'Security/Cognito design approved for the invite path',
            'required': True,
            'satisfied': False,
        },
        {
            'item': 'EIN and Stripe live billing activation (if live payment required)',
            'required': status == 'active' and tier in ('professional', 'premium', 'enterprise'),
            'satisfied': False,
        },
        {
            'item': 'Rollback and disable procedure confirmed with Matthew',
            'required': True,
            'satisfied': False,
        },
    ]


# ---------------------------------------------------------------------------
# Preview Hash
# ---------------------------------------------------------------------------


def compute_preview_hash(preview_payload: dict) -> str:
    """
    Return the SHA-256 hex digest of the canonical JSON representation of
    the preview payload (keys sorted deterministically).

    Used by the frontend to detect edit-after-preview staleness.
    """
    canonical = json.dumps(preview_payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
