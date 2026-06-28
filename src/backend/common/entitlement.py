"""
Release 17G: Entitlement Enforcement Observability and Denial Logging

Provides core exception EntitlementDenied and helper functions:
  - check_subscription_active(company_id, context=None)
  - check_feature(company_id, feature_name, context=None)
  - check_limit(company_id, limit_name, current_value, context=None)

Enforces SaaS subscription and feature tier constraints according to the
ENTITLEMENT_ENFORCEMENT_ENABLED environment variable and sandbox status.
Includes structured logging for entitlement decisions.
"""
import os
import logging
import json
from common.billing import TenantEntitlement, TIER_LIMITS
from common.protected_accounts import is_protected_email, is_protected_sub

# Configure logging level for AWS Lambda environment to ensure INFO events are captured
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)



class EntitlementDenied(Exception):
    """Raised when an action is denied due to entitlement limits or inactive status."""
    def __init__(self, message, upgrade_hint=None, feature=None, limit=None):
        super().__init__(message)
        self.upgrade_hint = upgrade_hint
        self.feature = feature
        self.limit = limit


def _get_request_id(context):
    """
    Safely extracts request/correlation ID from context without throwing exceptions.
    """
    if not context or not isinstance(context, dict):
        return None

    request_context = context.get('requestContext')
    if isinstance(request_context, dict):
        req_id = request_context.get('requestId')
        if req_id:
            return req_id

    return context.get('requestId') or context.get('request_id')


def _log_decision(event, company_id, check_type, subscription_tier, subscription_status,
                  enforcement_enabled, allowed, reason, protected_admin_bypass=False,
                  feature_key=None, limit_key=None, current_count=None, max_allowed=None,
                  context=None):
    """
    Emits a structured JSON log event for entitlement decisions.
    Guarantees no sensitive data (e.g. email, user IDs) is logged.
    """
    log_payload = {
        "event": event,
        "company_id": company_id,
        "check_type": check_type,
        "subscription_tier": subscription_tier,
        "subscription_status": subscription_status,
        "enforcement_enabled": enforcement_enabled,
        "allowed": allowed,
        "reason": reason,
        "protected_admin_bypass": protected_admin_bypass
    }

    if feature_key is not None:
        log_payload["feature_key"] = feature_key
    if limit_key is not None:
        log_payload["limit_key"] = limit_key
    if current_count is not None:
        log_payload["current_count"] = current_count
    if max_allowed is not None:
        log_payload["max_allowed"] = max_allowed

    if context:
        req_id = _get_request_id(context)
        if req_id:
            log_payload["request_id"] = req_id

    logger.info(json.dumps(log_payload))


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
    bypass_active = _is_bypass_active(context)
    if bypass_active:
        ent = TenantEntitlement(
            company_id=company_id,
            subscription_tier='enterprise',
            subscription_status='active',
        )
        _log_decision(
            event="ENTITLEMENT_ALLOWED",
            company_id=company_id,
            check_type="subscription",
            subscription_tier="enterprise",
            subscription_status="active",
            enforcement_enabled=enforcement_enabled,
            allowed=True,
            reason="Protected admin bypass active",
            protected_admin_bypass=True,
            context=context
        )
        return ent

    # 3. Load tenant entitlement
    ent = _get_entitlement_safely(company_id)

    # 4. Check sandbox mode: bypass subscription status blocks
    is_sandbox = os.environ.get('STRIPE_ENV', 'sandbox').lower() == 'sandbox'
    if is_sandbox:
        _log_decision(
            event="ENTITLEMENT_ALLOWED",
            company_id=company_id,
            check_type="subscription",
            subscription_tier=ent.subscription_tier,
            subscription_status=ent.subscription_status,
            enforcement_enabled=enforcement_enabled,
            allowed=True,
            reason="Subscription check allowed in sandbox mode",
            protected_admin_bypass=False,
            context=context
        )
        return ent

    # 5. Check active status
    if not ent.is_access_allowed:
        if ent.is_read_only:
            _log_decision(
                event="ENTITLEMENT_DENIED",
                company_id=company_id,
                check_type="subscription",
                subscription_tier=ent.subscription_tier,
                subscription_status=ent.subscription_status,
                enforcement_enabled=enforcement_enabled,
                allowed=False,
                reason="Account is past due. Read-only access until payment is updated.",
                protected_admin_bypass=False,
                context=context
            )
            raise EntitlementDenied(
                "Account is past due. Read-only access until payment is updated.",
                upgrade_hint="update_payment"
            )
        
        _log_decision(
            event="ENTITLEMENT_DENIED",
            company_id=company_id,
            check_type="subscription",
            subscription_tier=ent.subscription_tier,
            subscription_status=ent.subscription_status,
            enforcement_enabled=enforcement_enabled,
            allowed=False,
            reason="Subscription is inactive. Please reactivate to continue.",
            protected_admin_bypass=False,
            context=context
        )
        raise EntitlementDenied(
            "Subscription is inactive. Please reactivate to continue.",
            upgrade_hint="resubscribe"
        )

    _log_decision(
        event="ENTITLEMENT_ALLOWED",
        company_id=company_id,
        check_type="subscription",
        subscription_tier=ent.subscription_tier,
        subscription_status=ent.subscription_status,
        enforcement_enabled=enforcement_enabled,
        allowed=True,
        reason="Subscription is active",
        protected_admin_bypass=False,
        context=context
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
    if not enforcement_enabled:
        return ent

    if _is_bypass_active(context):
        _log_decision(
            event="ENTITLEMENT_ALLOWED",
            company_id=company_id,
            check_type="feature",
            feature_key=feature_name,
            subscription_tier=ent.subscription_tier,
            subscription_status=ent.subscription_status,
            enforcement_enabled=enforcement_enabled,
            allowed=True,
            reason="Protected admin bypass active",
            protected_admin_bypass=True,
            context=context
        )
        return ent

    # 3. Resolve feature status
    has_feature = ent.limits.get(feature_name, False) or ent.feature_flags.get(feature_name, False)
    if not has_feature:
        _log_decision(
            event="ENTITLEMENT_DENIED",
            company_id=company_id,
            check_type="feature",
            feature_key=feature_name,
            subscription_tier=ent.subscription_tier,
            subscription_status=ent.subscription_status,
            enforcement_enabled=enforcement_enabled,
            allowed=False,
            reason="This feature requires a higher plan.",
            protected_admin_bypass=False,
            context=context
        )
        raise EntitlementDenied(
            "This feature requires a higher plan.",
            upgrade_hint="upgrade",
            feature=feature_name
        )

    _log_decision(
        event="ENTITLEMENT_ALLOWED",
        company_id=company_id,
        check_type="feature",
        feature_key=feature_name,
        subscription_tier=ent.subscription_tier,
        subscription_status=ent.subscription_status,
        enforcement_enabled=enforcement_enabled,
        allowed=True,
        reason="Feature is enabled",
        protected_admin_bypass=False,
        context=context
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
    if not enforcement_enabled:
        return ent

    if _is_bypass_active(context):
        _log_decision(
            event="ENTITLEMENT_ALLOWED",
            company_id=company_id,
            check_type="limit",
            limit_key=limit_name,
            subscription_tier=ent.subscription_tier,
            subscription_status=ent.subscription_status,
            enforcement_enabled=enforcement_enabled,
            allowed=True,
            reason="Protected admin bypass active",
            protected_admin_bypass=True,
            current_count=current_value,
            max_allowed=ent.limits.get(limit_name, 0),
            context=context
        )
        return ent

    # 3. Resolve limit value and enforce
    max_allowed = ent.limits.get(limit_name, 0)
    if current_value >= max_allowed:
        # Customize message based on limit_name
        if limit_name == 'max_active_clients':
            reason_msg = f"Client limit reached ({current_value}/{max_allowed})."
        elif limit_name == 'max_monthly_bookings':
            reason_msg = f"Monthly booking limit reached ({current_value}/{max_allowed})."
        else:
            reason_msg = f"Limit reached ({current_value}/{max_allowed}). Upgrade for more capacity."

        _log_decision(
            event="ENTITLEMENT_DENIED",
            company_id=company_id,
            check_type="limit",
            limit_key=limit_name,
            subscription_tier=ent.subscription_tier,
            subscription_status=ent.subscription_status,
            enforcement_enabled=enforcement_enabled,
            allowed=False,
            reason=reason_msg,
            protected_admin_bypass=False,
            current_count=current_value,
            max_allowed=max_allowed,
            context=context
        )
        raise EntitlementDenied(
            reason_msg,
            upgrade_hint="upgrade",
            limit=limit_name
        )

    _log_decision(
        event="ENTITLEMENT_ALLOWED",
        company_id=company_id,
        check_type="limit",
        limit_key=limit_name,
        subscription_tier=ent.subscription_tier,
        subscription_status=ent.subscription_status,
        enforcement_enabled=enforcement_enabled,
        allowed=True,
        reason="Limit is within bounds",
        protected_admin_bypass=False,
        current_count=current_value,
        max_allowed=max_allowed,
        context=context
    )
    return ent


def get_active_client_count(company_id):
    """
    Get the count of active + disabled clients, excluding archived clients.
    """
    from common.db import table
    from boto3.dynamodb.conditions import Key
    try:
        response = table.query(
            KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("CLIENT#")
        )
        items = response.get('Items', [])
        count = 0
        for item in items:
            if item.get('status') == 'ARCHIVED' or item.get('is_archived') is True:
                continue
            count += 1
        return count
    except Exception as e:
        print(f"ERROR: Failed to query client count for {company_id}: {e}")
        return 0


def get_monthly_bookings_count(company_id, date_str=None):
    """
    Get the monthly booking count for a company in YYYY-MM format.
    Defaults to the current month in UTC if date_str is not provided.
    """
    from common.db import table
    if not date_str:
        from datetime import datetime
        date_str = datetime.utcnow().strftime('%Y-%m')
    else:
        if len(date_str) >= 7:
            date_str = date_str[:7]
            
    try:
        response = table.get_item(
            Key={
                'PK': f"USAGE#{company_id}",
                'SK': f"BOOKINGS#{date_str}"
            }
        )
        item = response.get('Item')
        if not item:
            return 0
        return int(item.get('booking_count', 0))
    except Exception as e:
        print(f"ERROR: Failed to get monthly bookings count for {company_id}: {e}")
        return 0


def increment_monthly_bookings(company_id, date_str=None):
    """
    Atomically increment the monthly booking counter for a company.
    Defaults to the current month in UTC if date_str is not provided.
    """
    from common.db import table
    if not date_str:
        from datetime import datetime
        date_str = datetime.utcnow().strftime('%Y-%m')
    else:
        if len(date_str) >= 7:
            date_str = date_str[:7]
            
    try:
        table.update_item(
            Key={
                'PK': f"USAGE#{company_id}",
                'SK': f"BOOKINGS#{date_str}"
            },
            UpdateExpression="ADD booking_count :val",
            ExpressionAttributeValues={
                ':val': 1
            }
        )
        return True
    except Exception as e:
        print(f"ERROR: Failed to increment monthly bookings count for {company_id}: {e}")
        return False


def require_active_tenant(event):
    """
    Validates that the resolved tenant for the request is active.
    - Resolves the company context via get_current_company_id(event).
    - Bypasses enforcement for platform_admin callers or root admin bypasses.
    - Loads the tenant's entitlement metadata from DynamoDB.
    - If the tenant is disabled/inactive (is_blocked = True or is_access_allowed = False):
      Returns a formatted 403 TenantDisabled response.
    - Returns None if the tenant is active.
    """
    from common.auth import get_current_company_id, is_platform_admin
    from common.entitlement import _is_bypass_active, _get_entitlement_safely
    from common.response import format_response

    # 1. Platform Admin Bypass
    if is_platform_admin(event) or _is_bypass_active(event):
        return None

    # 2. Resolve Company ID
    try:
        company_id = get_current_company_id(event)
    except PermissionError:
        # If tenant resolution fails (e.g. missing custom:company_id in multi-tenant mode),
        # let the handler's default resolution error handling execute.
        return None

    # 3. Fetch Entitlement (bypasses sandbox mode check to enforce actual status)
    ent = _get_entitlement_safely(company_id)

    # 4. Enforce Status Block
    if not ent.is_access_allowed or ent.is_blocked:
        return format_response(403, {
            "error": "TenantDisabled",
            "message": "Tenant is disabled"
        }, event)

    return None



