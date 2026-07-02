"""
Utility for safe derivation of per-tenant calendar provider metadata defaults in code.
"""

def get_tenant_calendar_config(tenant_record, company_id=None, google_status=None):
    """
    Derives calendar configuration from a tenant record with code-level defaults.
    Ensures safe graceful absence if fields are missing in DynamoDB.
    """
    if not tenant_record:
        tenant_record = {}
        
    comp_id = tenant_record.get('company_id') or company_id
    
    # Check if there are explicit calendar fields in the tenant record.
    provider = tenant_record.get('calendar_provider')
    
    if provider is not None:
        default_caps = {
            "create_events": False,
            "update_events": False,
            "delete_events": False,
            "read_events": False,
            "disconnect_supported": False
        }
        if provider in ['google', 'microsoft', 'caldav']:
            default_caps = {
                "create_events": True,
                "update_events": True,
                "delete_events": True,
                "read_events": True,
                "disconnect_supported": True
            }
        elif provider == 'ics_feed':
            default_caps = {
                "create_events": False,
                "update_events": False,
                "delete_events": False,
                "read_events": True,
                "disconnect_supported": True
            }
            
        caps = tenant_record.get('calendar_capabilities', default_caps)
        
        return {
            "calendar_provider": provider,
            "calendar_enabled": tenant_record.get('calendar_enabled', False),
            "calendar_connection_status": tenant_record.get('calendar_connection_status', 'not_configured'),
            "calendar_connected_account_label": tenant_record.get('calendar_connected_account_label'),
            "calendar_last_check_at": tenant_record.get('calendar_last_check_at'),
            "calendar_secret_ref": tenant_record.get('calendar_secret_ref'),
            "calendar_capabilities": caps
        }
        
    # Legacy fallback: if company is tog_and_dogs, it derives Google defaults
    from common.auth import DEFAULT_COMPANY_ID
    if comp_id == DEFAULT_COMPANY_ID:
        connection_status = 'connected'
        if google_status == 'NOT_CONNECTED':
            connection_status = 'not_connected'
        elif google_status == 'VALIDATION_FAILED':
            connection_status = 'needs_reconnect'
        elif google_status == 'CREDENTIALS_MISSING':
            connection_status = 'error'
        elif google_status:
            if google_status.lower() in ['connected', 'not_connected', 'needs_reconnect', 'error', 'disabled']:
                connection_status = google_status.lower()
                
        # Safe connected label
        connected_label = "Google Calendar" if connection_status == 'connected' else None
        secret_ref = "togs-and-dogs-prod/google/user-tokens"
        
        return {
            "calendar_provider": "google",
            "calendar_enabled": True,
            "calendar_connection_status": connection_status,
            "calendar_connected_account_label": connected_label,
            "calendar_last_check_at": None,
            "calendar_secret_ref": secret_ref,
            "calendar_capabilities": {
                "create_events": True,
                "update_events": True,
                "delete_events": True,
                "read_events": True,
                "disconnect_supported": True
            }
        }
        
    # All other tenants: not configured
    return {
        "calendar_provider": "none",
        "calendar_enabled": False,
        "calendar_connection_status": "not_configured",
        "calendar_connected_account_label": None,
        "calendar_last_check_at": None,
        "calendar_secret_ref": None,
        "calendar_capabilities": {
            "create_events": False,
            "update_events": False,
            "delete_events": False,
            "read_events": False,
            "disconnect_supported": False
        }
    }
