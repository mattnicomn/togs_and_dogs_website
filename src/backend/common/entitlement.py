"""
Release 17B: Entitlement Enforcement Core Helpers

Provides core exception EntitlementDenied and helper functions:
  - check_subscription_active(company_id, context=None)
  - check_feature(company_id, feature_name, context=None)
  - check_limit(company_id, limit_name, current_value, context=None)

Enforces SaaS subscription and feature tier constraints according to the
ENTITLEMENT_ENFORCEMENT_ENABLED environment variable and sandbox status.
"""
import os
from common.billing import TenantEntitlement, TIER_LIMITS
from common.protected_accounts import is_protected_email, is_protected_sub


class EntitlementDenied(Exception):
    """Raised when an action is denied due to entitlement limits or inactive status."""
    def __init__(self, message, upgrade_hint=None):
        super().__init__(message)
        self.upgrade_hint = upgrade_hint


def _is_bypass_active(context):
    """
    Check if the caller has protected/root admin bypass permissions.
    Accepts API Gateway event or Cognito claims dict.
    """
    if not context:
        return False

    if isinstance(context, dict):
        claims = {}
        if "requestContext" in context:
            try:
                from common.auth import get_claims
                claims = get_claims(context)
            except Exception:
                claims = {}
        else:
            claims = context

        # Check sub
        sub = claims.get('sub')
        if sub and is_protected_sub(sub):
            return True

        # Check email
        email = claims.get('email')
        if email and is_protected_email(email):
            return True

        # Check username/cognito:username
        username = claims.get('cognito:username') or claims.get('username')
        if username and is_protected_email(username):
            return True

    return False


def _get_entitlement_safely(company_id):
    """
    Load entitlement from DynamoDB but fail-open for load errors and missing tenants.
    """
    try:
        from common.db import get_item
        tenant = get_item(f"TENANT#{company_id}", "METADATA")

        if not tenant:
            # Fail-open for missing tenant: return active starter tier
            print(f"BILLING WARNING: Tenant metadata missing for company {company_id}. Failing open.")
            return TenantEntitlement(
                company_id=company_id,
                subscription_tier='starter',
                subscription_status='active',
            )

        # Build entitlement
        from common.billing import _build_entitlement
        return _build_entitlement(tenant)

    except Exception as e:
        # Fail-open for DynamoDB/load errors: return active starter tier
        print(f"BILLING ERROR: Failed to load tenant metadata for company {company_id}: {e}. Failing open.")
        return TenantEntitlement(
            company_id=company_id,
            subscription_tier='starter',
            subscription_status='active',
        )


def check_subscription_active(company_id, context=None):
    """
    Verify tenant has an active subscription.
    Default behavior: disabled (fail-open) unless ENTITLEMENT_ENFORCEMENT_ENABLED is true.
    """
    # 1. Check feature flag
    enforcement_enabled = os.environ.get('ENTITLEMENT_ENFORCEMENT_ENABLED', '').lower() == 'true'
    if not enforcement_enabled:
        return TenantEntitlement(
            company_id=company_id,
            subscription_tier='starter',
            subscription_status='active',
        )

    # 2. Check protected/root admin bypass
    if _is_bypass_active(context):
        return TenantEntitlement(
            company_id=company_id,
            subscription_tier='enterprise',
            subscription_status='active',
        )

    # 3. Load tenant entitlement
    ent = _get_entitlement_safely(company_id)

    # 4. Check sandbox mode: bypass subscription status blocks
    is_sandbox = os.environ.get('STRIPE_ENV', 'sandbox').lower() == 'sandbox'
    if is_sandbox:
        return ent

    # 5. Check active status
    if not ent.is_access_allowed:
        if ent.is_read_only:
            raise EntitlementDenied(
                "Account is past due. Read-only access until payment is updated.",
                upgrade_hint="update_payment"
            )
        raise EntitlementDenied(
            "Subscription is inactive. Please reactivate to continue.",
            upgrade_hint="resubscribe"
        )

    return ent


def check_feature(company_id, feature_name, context=None):
    """
    Check if a feature is enabled for the tenant.
    """
    # 1. Resolve subscription active status / get entitlement
    ent = check_subscription_active(company_id, context=context)

    # 2. Bypass checks if enforcement is off or bypass is active
    enforcement_enabled = os.environ.get('ENTITLEMENT_ENFORCEMENT_ENABLED', '').lower() == 'true'
    if not enforcement_enabled or _is_bypass_active(context):
        return ent

    # 3. Resolve feature status
    has_feature = ent.limits.get(feature_name, False) or ent.feature_flags.get(feature_name, False)
    if not has_feature:
        raise EntitlementDenied(
            "This feature requires a higher plan.",
            upgrade_hint="upgrade"
        )

    return ent


def check_limit(company_id, limit_name, current_value, context=None):
    """
    Check if a numeric limit has been met or exceeded.
    """
    # 1. Resolve subscription active status / get entitlement
    ent = check_subscription_active(company_id, context=context)

    # 2. Bypass checks if enforcement is off or bypass is active
    enforcement_enabled = os.environ.get('ENTITLEMENT_ENFORCEMENT_ENABLED', '').lower() == 'true'
    if not enforcement_enabled or _is_bypass_active(context):
        return ent

    # 3. Resolve limit value and enforce
    max_allowed = ent.limits.get(limit_name, 0)
    if current_value >= max_allowed:
        raise EntitlementDenied(
            f"Limit reached ({current_value}/{max_allowed}). Upgrade for more capacity.",
            upgrade_hint="upgrade"
        )

    return ent
