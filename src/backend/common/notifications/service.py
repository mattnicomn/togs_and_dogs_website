import logging
import json
from .config import NotificationConfig
from .templates import NotificationTemplates
from .resolver import resolve_notification_recipients, get_client_name, get_staff_name
from .ses_client import SESClient
from .postmark_client import PostmarkClient

logger = logging.getLogger(__name__)

from datetime import datetime, timezone
from common.db import table

def get_notification_client(config):
    """
    Factory to get the appropriate notification client based on provider.
    Strictly prioritizes Postmark in production.
    """
    provider = config.NOTIFICATION_PROVIDER
    
    if provider == 'postmark':
        return PostmarkClient(config)
    elif provider == 'ses':
        # SES is currently restricted to sandbox/explicit enablement
        return SESClient(config)
    elif provider == 'log_only':
        return SESClient(config)
    else:
        # If unknown, default to log_only via SESClient to prevent accidental delivery
        logger.warning(f"NOTIFICATION_CONFIG_WARNING: Unknown provider '{provider}'. Defaulting to log_only.")
        config.NOTIFICATION_MODE = 'log_only'
        return SESClient(config)

def notify_event(event_type, record=None, previous_record=None, **kwargs):
    """
    Main entry point for dispatching notifications.
    Safe and non-blocking.
    Returns: { "success": bool, "message": str }
    """
    try:
        config = NotificationConfig()
        
        # Support both positional 'record' and keyword 'context' (used for welcomes)
        if record is None and 'context' in kwargs:
            record = kwargs.get('context')
            
        if not record:
            msg = f"Notification skipped: No record or context provided for {event_type}."
            print(f"NOTIFICATION_IDLE: {msg}")
            return {"success": False, "message": msg}

        request_id = record.get('request_id')
        client_id = record.get('client_id')
        
        # 1. Duplicate Prevention for Approval
        if event_type == 'CUSTOMER_APPROVED':
            prev_status = record.get('approval_notification_status')
            if prev_status in ['Email sent.', 'Notification logged only.']:
                msg = f"Approved. Notification already sent via {record.get('approval_notification_mode', 'unknown')}."
                print(f"NOTIFICATION_SKIP: {msg}")
                return {"success": True, "message": msg}

        # 2. Resolve Recipients
        recipients = resolve_notification_recipients(event_type, record, previous_record, config)
        if not recipients:
            msg = f"Approved. No recipients resolved for {event_type}."
            print(f"NOTIFICATION_IDLE: {msg}")
            return {"success": True, "message": msg}

        # 3. Get Templates
        is_welcome_event = event_type in ['WELCOME_INVITE_CLIENT', 'WELCOME_INVITE_STAFF', 'WELCOME_INVITE']
        
        if is_welcome_event:
            # For welcome events, the 'record' (or context) already contains the necessary fields
            context = record
        else:
            # For standard booking events, we build the context from the DynamoDB record
            from .resolver import get_pet_names
            context = {
                "client_name": get_client_name(record),
                "client_email": record.get('client_email') or record.get('email') or '',
                "client_phone": record.get('client_phone') or '',
                "staff_name": get_staff_name(record),
                "request_id": request_id,
                "pet_names": get_pet_names(record),
                "service_type": record.get('service_type'),
                "start_date": record.get('start_date'),
                "start_time": record.get('start_time'),
                "details": record.get('details', 'No details provided.')
            }
        
        subject, body_text, body_html = NotificationTemplates.get_template(event_type, context)
        if not subject:
            msg = f"Notification failed: No template for {event_type}."
            print(f"NOTIFICATION_MISSING_TEMPLATE: {msg}")
            return {"success": False, "message": msg}

        # 4. Dispatch
        client = get_notification_client(config)
        event_key = f"{request_id}_{event_type}_{record.get('updated_at', 'v1')}"
        
        result = client.send_email(
            recipients=recipients,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            event_key=event_key
        )

        # 5. Metadata Update for Approval
        if event_type == 'CUSTOMER_APPROVED' and request_id and client_id:
            try:
                now = datetime.now(timezone.utc).isoformat()
                table.update_item(
                    Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                    UpdateExpression="SET approval_notification_status = :s, approval_notification_sent_at = :t, approval_notification_mode = :m, approval_notification_provider = :p, approval_notification_last_message = :msg",
                    ExpressionAttributeValues={
                        ":s": result['message'],
                        ":t": now,
                        ":m": result['mode'],
                        ":p": result.get('provider', 'unknown'),
                        ":msg": result['message']
                    }
                )
            except Exception as db_err:
                print(f"WARNING: Failed to update notification metadata for {request_id}: {db_err}")

        # 6. Log Safe Metadata
        try:
            recipient_domains = list(set([r.split('@')[-1] for r in recipients if '@' in r]))
            log_meta = {
                "event_type": event_type,
                "provider": result.get('provider', 'unknown'),
                "mode": result.get('mode', 'unknown'),
                "recipient_domains": recipient_domains,
                "status": "success" if result.get('delivered') else "failed",
                "message_id": result.get('message_id') if result.get('delivered') else None
            }
            print(f"NOTIFICATION_METADATA: {json.dumps(log_meta)}")
        except Exception as log_err:
            print(f"WARNING: Failed to log notification metadata: {log_err}")
            
        return {"success": result.get('delivered', False) or 'logged' in result.get('message', '').lower(), "message": result['message']}

    except Exception as e:
        # Crucial safety: notification failures must not block the main workflow
        err_msg = f"Notification failed but approval was completed."
        logger.error(f"NOTIFICATION_CRITICAL_FAILURE: {e}")
        return {"success": False, "message": err_msg}
