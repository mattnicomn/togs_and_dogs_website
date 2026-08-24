"""Fail-closed expected-tenant resolution for route-scoped Web access.

DOMAIN-1 intentionally keeps the short-term route registry server-owned and
centralized.  Tenant slugs are not derived from ``company_id`` values.  A
persisted registry populated by tenant provisioning replaces this bridge in
DOMAIN-6.
"""

import os
import re
from types import MappingProxyType

from common.auth import get_claims
from common.db import get_item


_TENANT_SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")

# B1A local bridge only. Keep every route mapping in this single server-side
# registry until DOMAIN-6 persists unique DNS-safe tenant slugs.
TENANT_ROUTE_REGISTRY = MappingProxyType({
    "test-tenant-alpha": "test_tenant_alpha",
})

_ACTIVE_SUBSCRIPTION_STATUSES = frozenset({"active", "trialing"})


class TenantRouteAccessDenied(PermissionError):
    """Raised when expected route context cannot be proven safely."""


def _registered_company_id(tenant_slug):
    if not isinstance(tenant_slug, str) or not _TENANT_SLUG_PATTERN.fullmatch(tenant_slug):
        return None
    return TENANT_ROUTE_REGISTRY.get(tenant_slug)


def resolve_expected_tenant(event, tenant_slug):
    """Resolve and authorize one expected tenant route.

    The route slug is context, never authority.  Access is allowed only when:
    strict multi mode is active, the server registry recognizes the slug, the
    authoritative tenant record is active, and the authenticated Cognito
    ``custom:company_id`` claim exactly matches the registered company ID.
    Every other case fails closed without a default-tenant fallback.
    """
    mode = os.environ.get("TENANT_RESOLUTION_MODE", "single").lower().strip()
    if mode != "multi":
        raise TenantRouteAccessDenied("Strict tenant route resolution is unavailable")

    company_id = _registered_company_id(tenant_slug)
    if not company_id:
        raise TenantRouteAccessDenied("Unknown tenant route")

    try:
        tenant = get_item(f"TENANT#{company_id}", "METADATA")
    except Exception as exc:
        raise TenantRouteAccessDenied("Tenant registry lookup failed") from exc

    if not isinstance(tenant, dict) or tenant.get("company_id") != company_id:
        raise TenantRouteAccessDenied("Tenant registry entry is unavailable")

    status = str(tenant.get("subscription_status") or "").lower().strip()
    if tenant.get("is_active") is not True or status not in _ACTIVE_SUBSCRIPTION_STATUSES:
        raise TenantRouteAccessDenied("Tenant is inactive")

    claims = get_claims(event) if isinstance(event, dict) else {}
    claim_company_id = claims.get("custom:company_id")
    if isinstance(claim_company_id, str):
        claim_company_id = claim_company_id.strip()

    if not claim_company_id or claim_company_id != company_id:
        raise TenantRouteAccessDenied("Authenticated tenant does not match expected tenant")

    return tenant
