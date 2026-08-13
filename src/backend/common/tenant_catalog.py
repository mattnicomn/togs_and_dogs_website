"""
src/backend/common/tenant_catalog.py
Preview-Only V1: Tenant Onboarding Orchestrator — Domain Catalog

Canonical source of truth for:
  - Subscription tier definitions and limits
  - Valid subscription statuses
  - Catalog schema version

DESIGN PRINCIPLES:
  - Pure Python — no boto3, no env vars, no I/O, no HTTP
  - Always returns copies of dicts — caller cannot mutate shared state
  - Unknown tier → raises ValueError (fail-closed, no silent defaults)
  - Single import-safe source so billing.py, provision_tenant.py, and
    the new onboarding handler can all derive from the same values

CATALOG_VERSION is incremented when any limit value or tier name changes.
Do not change limit values without bumping CATALOG_VERSION.
"""

import copy

# ---------------------------------------------------------------------------
# Catalog Schema Version
# ---------------------------------------------------------------------------

CATALOG_VERSION = 'v1'

# ---------------------------------------------------------------------------
# Tier Limits
# ---------------------------------------------------------------------------
# This private mapping is the single canonical definition. Runtime consumers
# obtain deep copies through the public accessors below.

_TIER_LIMITS: dict = {
    'starter': {
        'max_active_clients': 20,
        'max_staff': 1,
        'max_monthly_notifications': 100,
        'max_monthly_bookings': 50,
        'google_calendar_enabled': False,
        'export_enabled': False,
        'custom_branding_enabled': False,
        'video_evidence_enabled': False,
    },
    'professional': {
        'max_active_clients': 100,
        'max_staff': 5,
        'max_monthly_notifications': 500,
        'max_monthly_bookings': 250,
        'google_calendar_enabled': True,
        'export_enabled': True,
        'custom_branding_enabled': False,
        'video_evidence_enabled': False,
    },
    'premium': {
        'max_active_clients': 500,
        'max_staff': 15,
        'max_monthly_notifications': 2000,
        'max_monthly_bookings': 1000,
        'google_calendar_enabled': True,
        'export_enabled': True,
        'custom_branding_enabled': True,
        'video_evidence_enabled': True,
    },
    'enterprise': {
        'max_active_clients': 999999,
        'max_staff': 999999,
        'max_monthly_notifications': 999999,
        'max_monthly_bookings': 999999,
        'google_calendar_enabled': True,
        'export_enabled': True,
        'custom_branding_enabled': True,
        'video_evidence_enabled': True,
    },
}

# ---------------------------------------------------------------------------
# Valid Subscription Statuses
# ---------------------------------------------------------------------------

VALID_STATUSES: frozenset = frozenset({
    'active',
    'trialing',
    'past_due',
    'canceled',
    'paused',
    'disabled',
})

# Statuses that permit full tenant access (mirrors billing.py ALLOWED_STATUSES)
ALLOWED_STATUSES: frozenset = frozenset({'active', 'trialing'})

# Statuses that block access entirely (mirrors billing.py BLOCKED_STATUSES)
BLOCKED_STATUSES: frozenset = frozenset({'canceled', 'paused', 'disabled'})

# ---------------------------------------------------------------------------
# Valid Tier Names
# ---------------------------------------------------------------------------

VALID_TIERS: frozenset = frozenset(_TIER_LIMITS.keys())

# Default tier for new tenants (fail-safe — minimal entitlements)
DEFAULT_TIER: str = 'starter'

# Default status for new tenants (fail-closed — requires explicit activation)
DEFAULT_STATUS: str = 'disabled'

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_tier_limits(tier: str) -> dict:
    """
    Return a copy of the limit dict for the given subscription tier.

    Args:
        tier: One of the VALID_TIERS values.

    Returns:
        dict with the 8 canonical limit keys.

    Raises:
        ValueError if tier is not recognized (fail-closed).
    """
    normalized = str(tier).lower().strip() if tier else ''
    if normalized not in _TIER_LIMITS:
        raise ValueError(
            f"Unknown subscription tier: {tier!r}. "
            f"Valid tiers: {sorted(VALID_TIERS)}"
        )
    return copy.deepcopy(_TIER_LIMITS[normalized])


def get_all_tier_limits() -> dict:
    """Return a deep copy of the complete tier-to-limits catalog."""
    return copy.deepcopy(_TIER_LIMITS)


def is_valid_tier(tier: str) -> bool:
    """Return True if tier is a recognized subscription tier."""
    if not isinstance(tier, str):
        return False
    return tier.lower().strip() in _TIER_LIMITS


def is_valid_status(status: str) -> bool:
    """Return True if status is a recognized subscription status."""
    if not isinstance(status, str):
        return False
    return status.lower().strip() in VALID_STATUSES


def get_all_tiers() -> list:
    """Return a sorted list of all valid tier names."""
    return sorted(VALID_TIERS)


def get_all_statuses() -> list:
    """Return a sorted list of all valid subscription statuses."""
    return sorted(VALID_STATUSES)


def get_tier_summary() -> list:
    """
    Return a list of tier summary dicts suitable for UI display.
    Sorted from lowest (starter) to highest (enterprise) by staff count.
    """
    order = ['starter', 'professional', 'premium', 'enterprise']
    result = []
    for tier_name in order:
        if tier_name in _TIER_LIMITS:
            entry = {
                'tier': tier_name,
                'limits': copy.deepcopy(_TIER_LIMITS[tier_name]),
                'catalog_version': CATALOG_VERSION,
            }
            result.append(entry)
    return result
